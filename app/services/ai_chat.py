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
GEMINI_API_URL = os.getenv(
    "GEMINI_API_URL", "https://generativelanguage.googleapis.com/v1beta/models"
).strip()

# In-memory usage limiter. It resets when the bot restarts. It is intentional: fast and simple.
_USAGE: dict[tuple[int, str], int] = {}


@dataclass
class AIResult:
    ok: bool
    text: str
    error_code: str | None = None


SYSTEM_PROMPT = """
أنت Study Commander AI، مدرس خاص ذكي وصارم وعملي لطلاب الجامعات، خصوصًا طالب طب.
أسلوبك: عراقي سهل، واضح، مباشر، مع إبقاء المصطلحات الطبية والإنكليزية كما هي وشرحها بين قوسين عند الحاجة.

قواعد ثابتة:
1) لا تهلوس. إذا المعلومة غير موجودة في النص أو غير مؤكدة، قل ذلك بوضوح.
2) ابدأ بفهم سؤال الطالب، ثم رتّب الجواب خطوة بخطوة.
3) إذا أرسل الطالب نص ملزمة/محاضرة: اشرحها كأنها أول مرة يدرسها ليلة امتحان.
4) إذا طلب MCQ: اصنع أسئلة قوية مع 4 اختيارات، الجواب، وسبب مختصر.
5) إذا طلب short essay: أعطِ جوابًا امتحانيًا مركزًا، لا حشو.
6) إذا الطالب يقول "ما أفهم" أو "دخت": اشرح بأسلوب الطفل ثم اربطها بمثال طبي/دراسي.
7) استعمل جداول فقط عندما تجعل الفهم أسرع.
8) نهاية كل شرح طويل: اكتب "خلاصة حفظ" مختصرة.
9) لا تعطِ تشخيصًا طبيًا قاطعًا ولا علاجًا شخصيًا خطيرًا؛ قدم توجيهًا عامًا وانصح بمراجعة طبيب عند الحاجة.
10) ركز على الفهم والامتحان: definition, mechanism, causes, symptoms, diagnosis, treatment, comparison, traps.

صيغة الشرح المفضلة عند وجود مادة دراسية:
- الفكرة العامة
- شرح مبسط خطوة بخطوة
- الكلمات الإنكليزية المهمة
- الفروقات أو الفخاخ
- Key points in English
- MCQ محتملة
- Short essay محتملة
- خلاصة حفظ
""".strip()


MODE_PREFIXES: dict[str, str] = {
    "explain": "اشرح النص/السؤال التالي شرحًا عميقًا ومبسطًا، مع تركيز امتحاني قوي.",
    "mcq": "حوّل النص/الموضوع التالي إلى MCQ قوية، مع الإجابة والتفسير المختصر.",
    "essay": "حوّل النص/الموضوع التالي إلى أسئلة Short essay مع أجوبة امتحانية مركزة.",
    "medical": "اشرح الموضوع التالي كطالب طب: مصطلحات إنكليزية، آلية، مقارنة، فخاخ امتحانية، وخلاصة حفظ.",
    "study": "ساعد الطالب على الفهم والدراسة بعمق وبأسلوب عملي.",
}


def clean_text(text: str, max_chars: int = AI_MAX_INPUT_CHARS) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[تم اختصار النص بسبب الطول. أرسل جزءًا آخر إذا تريد تكملة.]"
    return text


def split_reply(text: str, limit: int = 3600) -> list[str]:
    text = text.strip() or "لم يرجع الذكاء جوابًا واضحًا. جرّب صياغة السؤال مرة ثانية."
    parts: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(". ", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        parts.append(text)
    return parts


def usage_available(user_id: int) -> tuple[bool, int, int]:
    today = date.today().isoformat()
    used = _USAGE.get((user_id, today), 0)
    return used < AI_DAILY_LIMIT, used, AI_DAILY_LIMIT


def increment_usage(user_id: int) -> None:
    today = date.today().isoformat()
    key = (user_id, today)
    _USAGE[key] = _USAGE.get(key, 0) + 1


def _post_gemini(system_text: str, contents: list[dict[str, Any]], generation_config: dict[str, Any]) -> AIResult:
    api_key = getattr(settings, "gemini_api_key", "") or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return AIResult(
            ok=False,
            error_code="missing_key",
            text=(
                "🤖 دردشة AI غير مفعلة لأن GEMINI_API_KEY غير مضاف.\n\n"
                "أضفه في Railway Variables (مجاني من Google AI Studio):\n"
                "GEMINI_API_KEY=AIza...\n"
                "GEMINI_MODEL=gemini-2.0-flash"
            ),
        )

    model = getattr(settings, "gemini_model", "") or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"{GEMINI_API_URL}/{model}:generateContent?key={api_key}"

    payload: dict[str, Any] = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system_text}]},
        "generationConfig": generation_config,
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=AI_REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            obj = json.loads(raw)
            candidates = obj.get("candidates") or []
            if not candidates:
                reason = obj.get("promptFeedback", {}).get("blockReason", "unknown")
                return AIResult(ok=False, error_code="empty_response", text=f"ما رجع Gemini جواب (السبب: {reason}).")
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts).strip()
            return AIResult(ok=True, text=content)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")[:1200]
        except Exception:
            body = str(e)
        return AIResult(ok=False, error_code="http_error", text=f"صار خطأ من خدمة AI: {e.code}\n{body}")
    except Exception as e:
        return AIResult(ok=False, error_code="request_error", text=f"صار خطأ اتصال بالذكاء الاصطناعي: {e}")


async def generate_ai_reply(
    *,
    user_id: int,
    user_text: str,
    context_messages: list[dict[str, str]] | None = None,
    profile_context: str = "",
    mode: str = "study",
) -> AIResult:
    if not AI_CHAT_ENABLED:
        return AIResult(False, "دردشة AI متوقفة من إعدادات البوت.", "disabled")

    allowed, used, limit = usage_available(user_id)
    if not allowed:
        return AIResult(False, f"وصلت حد دردشة AI اليومي: {used}/{limit}. جرّب باچر أو اطلب من الأدمن يرفع الحد.", "daily_limit")

    user_text = clean_text(user_text)
    instruction = MODE_PREFIXES.get(mode, MODE_PREFIXES["study"])
    context_messages = (context_messages or [])[-AI_CONTEXT_MESSAGES:]

    system_text = SYSTEM_PROMPT
    if profile_context:
        system_text += "\n\nمعلومات الطالب للاستفادة في الأسلوب فقط:\n" + clean_text(profile_context, 1000)

    contents: list[dict[str, Any]] = []
    for m in context_messages:
        role = m.get("role", "user")
        role = "model" if role in {"assistant", "model"} else "user"
        contents.append({"role": role, "parts": [{"text": clean_text(m.get("content", ""), 1200)}]})
    contents.append({"role": "user", "parts": [{"text": f"{instruction}\n\nسؤال/نص الطالب:\n{user_text}"}]})

    generation_config = {
        "temperature": 0.25,
        "maxOutputTokens": int(os.getenv("AI_MAX_OUTPUT_TOKENS", "1800") or "1800"),
    }
    result = await asyncio.to_thread(_post_gemini, system_text, contents, generation_config)
    if result.ok:
        increment_usage(user_id)
    return result


async def extract_document_text(file_path: str, file_name: str | None = None) -> str:
    """Extract text from simple text/PDF files. Keeps the bot alive if extraction fails."""
    path = Path(file_path)
    suffix = path.suffix.lower() or Path(file_name or "").suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:AI_MAX_FILE_CHARS]
        except Exception:
            return ""
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # optional dependency in the patch requirements
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
    suffix = Path(file_name or "file.bin").suffix or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    await tg_file.download_to_drive(tmp.name)
    return tmp.name
