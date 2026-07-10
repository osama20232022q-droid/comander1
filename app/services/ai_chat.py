from __future__ import annotations

import asyncio
import json
import os
import re
import socket
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
AI_REQUEST_TIMEOUT = int(os.getenv("AI_REQUEST_TIMEOUT", "90") or "90")
AI_MAX_RETRIES_PER_MODEL = int(os.getenv("AI_MAX_RETRIES_PER_MODEL", "2") or "2")
AI_RETRY_BACKOFF_SECONDS = float(os.getenv("AI_RETRY_BACKOFF_SECONDS", "2") or "2")
GEMINI_API_URL = os.getenv(
    "GEMINI_API_URL", "https://generativelanguage.googleapis.com/v1beta/models"
).strip()

# Error codes that are worth retrying (transient) either on the same model or the next one.
_RETRYABLE_ERROR_CODES = {"timeout", "rate_limited", "server_error", "connection_error"}
# Error codes that should trigger a jump to the next fallback model rather than retrying blindly.
_MODEL_SWITCH_ERROR_CODES = {"model_not_found", "rate_limited", "server_error"}

# In-memory usage limiter. It resets when the bot restarts. It is intentional: fast and simple.
_USAGE: dict[tuple[int, str], int] = {}
_USAGE_LAST_CLEAN: dict[str, str] = {"date": ""}


def _prune_usage() -> None:
    """Drop usage entries from previous days so the dict doesn't grow forever."""
    today = date.today().isoformat()
    if _USAGE_LAST_CLEAN["date"] == today:
        return
    _USAGE_LAST_CLEAN["date"] = today
    stale_keys = [key for key in _USAGE if key[1] != today]
    for key in stale_keys:
        _USAGE.pop(key, None)


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
    _prune_usage()
    today = date.today().isoformat()
    used = _USAGE.get((user_id, today), 0)
    return used < AI_DAILY_LIMIT, used, AI_DAILY_LIMIT


def increment_usage(user_id: int) -> None:
    _prune_usage()
    today = date.today().isoformat()
    key = (user_id, today)
    _USAGE[key] = _USAGE.get(key, 0) + 1


def _post_gemini(model: str, system_text: str, contents: list[dict[str, Any]], generation_config: dict[str, Any]) -> AIResult:
    api_key = getattr(settings, "gemini_api_key", "") or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return AIResult(
            ok=False,
            error_code="missing_key",
            text=(
                "🤖 دردشة AI غير مفعلة لأن GEMINI_API_KEY غير مضاف.\n\n"
                "أضفه في Railway Variables (مجاني من Google AI Studio):\n"
                "GEMINI_API_KEY=AIza...\n"
                "GEMINI_MODEL=gemini-3.5-flash"
            ),
        )

    # Catch obvious copy-paste mistakes early instead of sending a doomed request.
    if not re.match(r"^[A-Za-z0-9_\-]{20,}$", api_key):
        return AIResult(
            ok=False,
            error_code="invalid_key_format",
            text=(
                "🤖 قيمة GEMINI_API_KEY غير صحيحة الشكل (يبدو فيها مسافات/رموز غريبة أو ناقصة).\n"
                "تأكد إنك نسخت المفتاح كامل من Google AI Studio بدون مسافات إضافية."
            ),
        )

    if not model:
        return AIResult(ok=False, error_code="no_model", text="لا يوجد اسم موديل محدد للاتصال بـ Gemini.")

    url = f"{GEMINI_API_URL}/{model}:generateContent?key={api_key}"

    payload: dict[str, Any] = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system_text}]},
        "generationConfig": generation_config,
        "safetySettings": [
            {"category": c, "threshold": "BLOCK_ONLY_HIGH"}
            for c in (
                "HARM_CATEGORY_HARASSMENT",
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_DANGEROUS_CONTENT",
            )
        ],
    }

    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as e:
        return AIResult(ok=False, error_code="encode_error", text=f"تعذر تجهيز الطلب لخدمة AI: {e}")

    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=AI_REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")[:1200]
        except Exception:
            body = str(e)
        if e.code == 404:
            return AIResult(ok=False, error_code="model_not_found", text=f"صار خطأ من خدمة AI: {e.code}\n{body}")
        if e.code == 429:
            return AIResult(
                ok=False,
                error_code="rate_limited",
                text="🤖 وصلنا حد الطلبات المجاني المؤقت من Gemini (429). راح أجرب موديل ثاني أو انتظر شوي وحاول مرة ثانية.",
            )
        if e.code in (401, 403):
            return AIResult(
                ok=False,
                error_code="auth_error",
                text=(
                    "🤖 مفتاح GEMINI_API_KEY مرفوض من جوجل (غير صحيح أو ملغى أو ناقص صلاحيات).\n"
                    "تأكد إنك مسوي مفتاح جديد من https://aistudio.google.com/apikey وحاطه صح."
                ),
            )
        if e.code == 400:
            return AIResult(
                ok=False,
                error_code="bad_request",
                text=f"🤖 طلب غير صالح لخدمة AI (400). التفاصيل:\n{body[:500]}",
            )
        if e.code in (500, 502, 503, 504):
            return AIResult(
                ok=False,
                error_code="server_error",
                text="🤖 خدمة Gemini عندها ضغط أو مشكلة مؤقتة من طرفهم. راح أجرب موديل بديل أو حاول بعد شوي.",
            )
        return AIResult(ok=False, error_code="http_error", text=f"صار خطأ من خدمة AI: {e.code}\n{body}")
    except (TimeoutError, socket.timeout):
        return AIResult(ok=False, error_code="timeout", text="صار خطأ اتصال بالذكاء الاصطناعي: انتهت مهلة الاتصال.")
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        reason = getattr(e, "reason", e)
        text = str(reason).lower()
        if "timed out" in text or "timeout" in text:
            return AIResult(ok=False, error_code="timeout", text="صار خطأ اتصال بالذكاء الاصطناعي: انتهت مهلة الاتصال.")
        return AIResult(ok=False, error_code="connection_error", text=f"تعذر الاتصال بخدمة AI (مشكلة شبكة): {reason}")
    except Exception as e:
        error_code = "timeout" if "timed out" in str(e).lower() else "request_error"
        return AIResult(ok=False, error_code=error_code, text=f"صار خطأ اتصال بالذكاء الاصطناعي: {e}")

    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return AIResult(ok=False, error_code="bad_json", text="🤖 رجع رد غير مفهوم من خدمة AI. جرّب مرة ثانية.")

    if not isinstance(obj, dict):
        return AIResult(ok=False, error_code="bad_json", text="🤖 رجع رد بصيغة غير متوقعة من خدمة AI.")

    candidates = obj.get("candidates") or []
    if not candidates:
        reason = (obj.get("promptFeedback") or {}).get("blockReason", "unknown")
        if reason and reason != "unknown":
            return AIResult(
                ok=False,
                error_code="blocked",
                text=f"🤖 Gemini رفض الرد على هذا الطلب لأسباب تتعلق بسياسة المحتوى (السبب: {reason}). جرّب صياغة مختلفة.",
            )
        return AIResult(ok=False, error_code="empty_response", text="🤖 ما رجع Gemini أي جواب. جرّب مرة ثانية.")

    first = candidates[0] if isinstance(candidates[0], dict) else {}
    finish_reason = first.get("finishReason", "")
    content_obj = first.get("content") or {}
    parts = content_obj.get("parts") or []
    content = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()

    if not content:
        if finish_reason in {"SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST"}:
            return AIResult(
                ok=False,
                error_code="blocked",
                text="🤖 Gemini ما گدر يجاوب على هذا الطلب بسبب سياسات المحتوى. جرّب تعيد صياغة سؤالك.",
            )
        if finish_reason == "MAX_TOKENS":
            return AIResult(
                ok=False,
                error_code="truncated",
                text="🤖 الجواب طلع طويل وانقطع قبل يخلص. جرّب تسأل عن جزء أصغر أو أوضح.",
            )
        return AIResult(ok=False, error_code="empty_response", text="🤖 ما رجع Gemini جواب واضح. جرّب صياغة السؤال مرة ثانية.")

    return AIResult(ok=True, text=content)


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

    user_text = clean_text(user_text)
    if not user_text:
        return AIResult(False, "أرسل سؤال أو نص أولاً حتى أقدر أساعدك 🙂", "empty_input")

    allowed, used, limit = usage_available(user_id)
    if not allowed:
        return AIResult(False, f"وصلت حد دردشة AI اليومي: {used}/{limit}. جرّب باچر أو اطلب من الأدمن يرفع الحد.", "daily_limit")

    instruction = MODE_PREFIXES.get(mode, MODE_PREFIXES["study"])
    context_messages = (context_messages or [])[-AI_CONTEXT_MESSAGES:]

    system_text = SYSTEM_PROMPT
    if profile_context:
        system_text += "\n\nمعلومات الطالب للاستفادة في الأسلوب فقط:\n" + clean_text(profile_context, 1000)

    contents: list[dict[str, Any]] = []
    for m in context_messages:
        role = m.get("role", "user")
        role = "model" if role in {"assistant", "model"} else "user"
        msg_text = clean_text(m.get("content", ""), 1200)
        if msg_text:
            contents.append({"role": role, "parts": [{"text": msg_text}]})
    contents.append({"role": "user", "parts": [{"text": f"{instruction}\n\nسؤال/نص الطالب:\n{user_text}"}]})

    generation_config = {
        "temperature": 0.25,
        "maxOutputTokens": int(os.getenv("AI_MAX_OUTPUT_TOKENS", "1800") or "1800"),
    }

    primary_model = getattr(settings, "gemini_model", "") or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    fallback_models = [
        m.strip()
        for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3-flash-preview,gemini-3.1-flash-lite,gemini-2.5-flash").split(",")
        if m.strip() and m.strip() != primary_model
    ]
    # de-duplicate while preserving order
    seen: set[str] = set()
    models_to_try = []
    for m in [primary_model, *fallback_models]:
        if m not in seen:
            seen.add(m)
            models_to_try.append(m)

    result = AIResult(False, "لم تتم أي محاولة اتصال بـ Gemini.", "no_attempt")
    non_retryable_final = {"missing_key", "invalid_key_format", "auth_error", "bad_request", "encode_error", "no_model"}

    for model_name in models_to_try:
        for attempt in range(max(1, AI_MAX_RETRIES_PER_MODEL)):
            result = await asyncio.to_thread(_post_gemini, model_name, system_text, contents, generation_config)
            if result.ok:
                break
            if result.error_code in non_retryable_final:
                break
            if result.error_code in _RETRYABLE_ERROR_CODES and attempt < AI_MAX_RETRIES_PER_MODEL - 1:
                await asyncio.sleep(AI_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            break

        if result.ok or result.error_code not in _MODEL_SWITCH_ERROR_CODES:
            break
        # else: try the next model in the fallback chain

    if result.ok:
        increment_usage(user_id)
    return result


async def extract_document_text(file_path: str, file_name: str | None = None) -> str:
    """Extract text from simple text/PDF files. Keeps the bot alive if extraction fails."""
    path = Path(file_path)
    if not path.exists():
        return "[الملف غير موجود بعد التنزيل]"
    try:
        if path.stat().st_size == 0:
            return "[الملف فارغ]"
    except OSError:
        pass

    suffix = path.suffix.lower() or Path(file_name or "").suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:AI_MAX_FILE_CHARS]
        except Exception as e:
            return f"[تعذر قراءة الملف النصي: {e}]"
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # optional dependency in the patch requirements
        except ImportError:
            return "[مكتبة قراءة PDF غير مثبتة على السيرفر. أضف pypdf لـ requirements.txt]"
        try:
            reader = PdfReader(str(path))
            if getattr(reader, "is_encrypted", False):
                try:
                    reader.decrypt("")  # try empty password for casually-protected files
                except Exception:
                    return "[الملف محمي بكلمة مرور، تعذر فتحه تلقائيًا. أرسل نسخة غير محمية]"
            chunks: list[str] = []
            for page in reader.pages[:25]:
                try:
                    chunks.append(page.extract_text() or "")
                except Exception:
                    continue  # skip unreadable page, keep going
                if sum(len(c) for c in chunks) >= AI_MAX_FILE_CHARS:
                    break
            text = "\n".join(chunks)[:AI_MAX_FILE_CHARS]
            if not text.strip():
                return "[الـ PDF يبدو أنه صور ممسوحة (سكان) بدون نص قابل للاستخراج. أرسل نسخة نصية أو الصق النص يدويًا]"
            return text
        except Exception as e:
            return f"[تعذر استخراج PDF تلقائيًا: {e}]"
    return f"[نوع الملف {suffix or 'غير معروف'} غير مدعوم حاليًا. أرسل txt أو pdf]"


async def download_telegram_file(bot, file_id: str, file_name: str | None = None) -> str:
    tg_file = await bot.get_file(file_id)
    suffix = Path(file_name or "file.bin").suffix or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    await tg_file.download_to_drive(tmp.name)
    return tmp.name
