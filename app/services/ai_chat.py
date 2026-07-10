from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.config import settings

AI_CHAT_ENABLED = os.getenv("AI_CHAT_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
AI_DAILY_LIMIT = int(os.getenv("AI_DAILY_LIMIT", "30") or "30")
AI_CONTEXT_MESSAGES = int(os.getenv("AI_CONTEXT_MESSAGES", "10") or "10")
AI_MAX_INPUT_CHARS = int(os.getenv("AI_MAX_INPUT_CHARS", "3500") or "3500")
AI_MAX_FILE_CHARS = int(os.getenv("AI_MAX_FILE_CHARS", "12000") or "12000")
AI_REQUEST_TIMEOUT = int(os.getenv("AI_REQUEST_TIMEOUT", "45") or "45")

# تم التحديث إلى الموديل gemini-1.5-flash لضمان عمله على الحسابات المجانية بدون أخطاء
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

# In-memory usage limiter. It resets when the bot restarts.
_USAGE: dict[tuple[int, str], int] = {}


@dataclass
class AIResult:
    ok: bool
    text: str
    error_code: str | None = None


SYSTEM_PROMPT = """
أنت Study Commander AI، مدرس خاص ذكي لطلاب الطب والجامعات.
مهمتك:
- شرح المواضيع بتبسيط.
- إجابة الأسئلة بدقة.
- تقديم MCQ أو Short essay.
- التحدث باللغة العربية بلهجة واضحة (ومصطلحات طبية إنجليزية).
"""


def usage_available(user_id: int) -> tuple[bool, int, int]:
    today = date.today().isoformat()
    used = _USAGE.get((user_id, today), 0)
    return used < AI_DAILY_LIMIT, used, AI_DAILY_LIMIT


def increment_usage(user_id: int) -> None:
    today = date.today().isoformat()
    _USAGE[(user_id, today)] = _USAGE.get((user_id, today), 0) + 1


def clean_text(text: str, max_len: int) -> str:
    if not text:
        return ""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text[:max_len]


def split_reply(text: str, chunk_size: int = 3900) -> list[str]:
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunks.append(text[i : i + chunk_size])
    return chunks or ["(إجابة فارغة)"]


def _post_gemini(payload: dict[str, Any]) -> AIResult:
    """Send request to Google Gemini API using urllib"""
    req = urllib.request.Request(
        GEMINI_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=AI_REQUEST_TIMEOUT) as response:
            body = response.read()
            data = json.loads(body.decode("utf-8"))
            
            try:
                reply = data["candidates"][0]["content"]["parts"][0]["text"]
                return AIResult(True, reply)
            except (KeyError, IndexError):
                return AIResult(False, "صيغة الرد من جمناي غير متوقعة.")
                
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            err_data = json.loads(body)
            msg = err_data.get("error", {}).get("message", str(e))
        except Exception:
            msg = body[:200]
        return AIResult(False, f"خطأ من خدمة الذكاء الاصطناعي ({e.code}): {msg}", str(e.code))
    except Exception as e:
        return AIResult(False, f"فشل الاتصال بخوادم الذكاء الاصطناعي: {e}")


async def generate_ai_reply(
    user_id: int, user_text: str, context_messages: list[dict[str, str]], profile_context: str, mode: str
) -> AIResult:
    if not AI_CHAT_ENABLED:
        return AIResult(False, "🤖 دردشة AI غير مفعلة مؤقتًا من قبل الإدارة.")

    if not GEMINI_API_KEY:
        # رسالة احترافية تظهر في حال نسيان إضافة المفتاح
        return AIResult(
            False,
            "🤖 خدمة الذكاء الاصطناعي غير مفعلة حالياً.\n"
            "(ملاحظة للإدارة: يرجى إضافة مفتاح GEMINI_API_KEY في إعدادات Railway لكي يعمل البوت)"
        )

    allowed, _, _ = usage_available(user_id)
    if not allowed:
        return AIResult(False, "⚠️ استنفدت حد أسئلتك اليومي. راجع البوت غدًا.")

    contents = []
    for m in context_messages:
        role = "user" if m.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})

    sys_intro = f"[معلومات: {profile_context}]\n\n"
    if mode == "explain":
        sys_intro += "اشرح هذا الموضوع بتفصيل وتبسيط عالي:\n"
    elif mode == "mcq":
        sys_intro += "اكتب أسئلة MCQ امتحانية مع الحل عن هذا الموضوع:\n"
    elif mode == "essay":
        sys_intro += "اكتب Short essay مرتب عن هذا الموضوع:\n"
    elif mode == "medical":
        sys_intro += "بفهم طبي دقيق، اشرح أو شخّص هذا الموضوع:\n"

    final_user_text = clean_text(sys_intro + user_text, AI_MAX_INPUT_CHARS)
    contents.append({"role": "user", "parts": [{"text": final_user_text}]})

    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }

    result = await asyncio.to_thread(_post_gemini, payload)
    if result.ok:
        increment_usage(user_id)
    return result


async def extract_document_text(file_path: str, file_name: str | None = None) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower() or Path(file_name or "").suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:AI_MAX_FILE_CHARS]
        except Exception:
            return ""
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            chunks: list[str] = []
            for page in reader.pages[:25]:
                chunks.append(page.extract_text() or "")
                if sum(len(c) for c in chunks) >= AI_MAX_FILE_CHARS:
                    break
            return "\n".join(chunks)[:AI_MAX_FILE_CHARS]
        except Exception as e:
            return f"[تعذر استخراج PDF تلقائيًا: {e}]"
    return ""


async def download_telegram_file(bot, file_id: str, file_name: str | None = None) -> str:
    tg_file = await bot.get_file(file_id)
    suffix = Path(file_name or "").suffix if file_name else ""
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, f"{file_id}{suffix}")
    await tg_file.download_to_drive(custom_path=file_path)
    return file_path
