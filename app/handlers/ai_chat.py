from __future__ import annotations

from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from app.config import settings
from app.handlers.admin import is_admin_tg
from app.keyboards import main_keyboard, rk
from app.services.ai_chat import (
    AI_CONTEXT_MESSAGES,
    clean_text,
    download_telegram_file,
    extract_document_text,
    generate_ai_reply,
    split_reply,
    usage_available,
)

AI_CHAT_BUTTON = "🤖 دردشة AI"
AI_EXIT_BUTTON = "🔙 خروج من دردشة AI"
AI_CLEAR_BUTTON = "🧹 مسح سياق AI"
AI_EXPLAIN_BUTTON = "🧠 اشرحلي"
AI_MCQ_BUTTON = "📝 MCQ"
AI_ESSAY_BUTTON = "✍️ Short essay"
AI_MEDICAL_BUTTON = "🩺 فهم طبي"
AI_TEST_BUTTON = "🧪 فحص Gemini"


def ai_chat_keyboard():
    return rk(
        [
            [AI_EXPLAIN_BUTTON, AI_MCQ_BUTTON],
            [AI_ESSAY_BUTTON, AI_MEDICAL_BUTTON],
            [AI_CLEAR_BUTTON, AI_TEST_BUTTON],
            [AI_EXIT_BUTTON, "🏠 القائمة الرئيسية"],
        ],
        "اكتب سؤالك للذكاء الاصطناعي",
    )


def _history(context: ContextTypes.DEFAULT_TYPE) -> list[dict[str, str]]:
    hist = context.user_data.setdefault("ai_history", [])
    if not isinstance(hist, list):
        hist = []
        context.user_data["ai_history"] = hist
    return hist


def _profile_context(update: Update) -> str:
    u = update.effective_user
    return f"Telegram user id: {u.id}; username: @{u.username or 'none'}; first_name: {u.first_name or ''}"


async def show_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["flow"] = "ai_chat"
    allowed, used, limit = usage_available(update.effective_user.id)
    await update.effective_message.reply_text(
        "🤖 دخلت وضع دردشة AI.\n\n"
        "اكتب أي سؤال أو الصق نص الملزمة، وأنا أشرحه بفهم وترتيب.\n"
        "تگدر تختار: شرح، MCQ، Short essay، أو فهم طبي.\n\n"
        f"استخدامك اليوم: {used}/{limit}",
        reply_markup=ai_chat_keyboard(),
    )


async def exit_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("flow", None)
    context.user_data.pop("ai_mode", None)
    await update.effective_message.reply_text(
        "تم الخروج من دردشة AI.",
        reply_markup=main_keyboard(is_admin_tg(update.effective_user.id)),
    )


async def clear_ai_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["ai_history"] = []
    await update.effective_message.reply_text("تم مسح سياق دردشة AI. ابدأ بسؤال جديد.", reply_markup=ai_chat_keyboard())


async def handle_ai_chat_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    if context.user_data.get("flow") != "ai_chat" and text != AI_CHAT_BUTTON:
        return False

    if text == AI_CHAT_BUTTON:
        await show_ai_chat(update, context)
        return True
    if text in {AI_EXIT_BUTTON, "🏠 القائمة الرئيسية"}:
        await exit_ai_chat(update, context)
        return True
    if text == AI_CLEAR_BUTTON:
        await clear_ai_context(update, context)
        return True
    if text == AI_TEST_BUTTON:
        thinking = await update.effective_message.reply_text("🧪 أفحص اتصال Gemini...", reply_markup=ai_chat_keyboard())
        try:
            result = await generate_ai_reply(
                user_id=update.effective_user.id,
                user_text="أجب بكلمتين فقط: الاتصال يعمل",
                context_messages=[],
                profile_context="",
                mode="study",
            )
        except Exception:
            result = None
            await update.effective_message.reply_text(
                "❌ فشل اختبار Gemini. راجع Railway Logs أو إعدادات المفتاح والموديل.", reply_markup=ai_chat_keyboard()
            )
        try:
            await thinking.delete()
        except Exception:
            pass
        if result is not None:
            prefix = "✅ Gemini يعمل" if result.ok else "❌ Gemini لا يعمل"
            await update.effective_message.reply_text(f"{prefix}\n\n{result.text}", reply_markup=ai_chat_keyboard())
        return True

    mode_map = {
        AI_EXPLAIN_BUTTON: "explain",
        AI_MCQ_BUTTON: "mcq",
        AI_ESSAY_BUTTON: "essay",
        AI_MEDICAL_BUTTON: "medical",
    }
    if text in mode_map:
        context.user_data["ai_mode"] = mode_map[text]
        await update.effective_message.reply_text(
            f"تم اختيار النمط: {text}\nأرسل النص أو السؤال الآن.",
            reply_markup=ai_chat_keyboard(),
        )
        return True

    mode = context.user_data.get("ai_mode", "study")
    hist = _history(context)
    thinking_msg = await update.effective_message.reply_text("⏳ جاري التفكير...", reply_markup=ai_chat_keyboard())
    try:
        result = await generate_ai_reply(
            user_id=update.effective_user.id,
            user_text=text,
            context_messages=hist,
            profile_context=_profile_context(update),
            mode=mode,
        )
    except Exception:
        result = None
        try:
            await thinking_msg.delete()
        except Exception:
            pass
        await update.effective_message.reply_text(
            "🤖 صار خطأ غير متوقع بالاتصال بالذكاء الاصطناعي. جرّب مرة ثانية بعد شوي.",
            reply_markup=ai_chat_keyboard(),
        )
        return True

    if result.ok:
        hist.append({"role": "user", "content": clean_text(text, 1200)})
        hist.append({"role": "assistant", "content": clean_text(result.text, 1600)})
        del hist[: -AI_CONTEXT_MESSAGES * 2]
    for part in split_reply(result.text):
        await update.effective_message.reply_text(part, reply_markup=ai_chat_keyboard())
    return True


async def handle_ai_chat_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.user_data.get("flow") != "ai_chat":
        return False
    msg = update.effective_message
    await msg.reply_text("📎 استلمت الملف. أحاول أقرأه وأشرحه...", reply_markup=ai_chat_keyboard())

    file_id = None
    file_name = None
    if msg.document:
        if msg.document.file_size and msg.document.file_size > settings.ai_max_file_bytes:
            max_mb = settings.ai_max_file_bytes / (1024 * 1024)
            await msg.reply_text(
                f"حجم الملف أكبر من الحد المسموح ({max_mb:.1f} MB). أرسل ملفًا أصغر.", reply_markup=ai_chat_keyboard()
            )
            return True
        file_id = msg.document.file_id
        file_name = msg.document.file_name
    elif msg.photo:
        await msg.reply_text(
            "حاليًا قراءة الصور تحتاج Vision API. اكتب النص الظاهر بالصورة أو أرسل PDF/ملف نصي.",
            reply_markup=ai_chat_keyboard(),
        )
        return True
    elif msg.audio:
        await msg.reply_text(
            "استلمت صوت، لكن التفريغ الصوتي غير مفعل في هذا الباتش. أرسل نص المحاضرة أو PDF.",
            reply_markup=ai_chat_keyboard(),
        )
        return True
    elif msg.video:
        await msg.reply_text(
            "استلمت فيديو، لكن تحليل الفيديو غير مفعل. أرسل النص أو PDF حتى أشرحه.", reply_markup=ai_chat_keyboard()
        )
        return True

    if not file_id:
        await msg.reply_text("نوع الملف غير مدعوم في دردشة AI حاليًا.", reply_markup=ai_chat_keyboard())
        return True

    path: str | None = None
    try:
        path = await download_telegram_file(context.bot, file_id, file_name)
        extracted = await extract_document_text(path, file_name)
    except Exception:
        await msg.reply_text(
            "تعذر تنزيل أو قراءة الملف. جرّب ملفًا أصغر أو بصيغة PDF/TXT واضحة.", reply_markup=ai_chat_keyboard()
        )
        return True
    finally:
        if path:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass

    if not extracted or extracted.startswith("["):
        await msg.reply_text(
            (extracted or "ما قدرت أستخرج نص واضح من الملف.") + "\n\nأرسل النص يدويًا أو PDF واضح النص.",
            reply_markup=ai_chat_keyboard(),
        )
        return True

    prompt = "اشرح هذا الملف بعمق وطلّع منه نقاط امتحانية وMCQ وShort essay:\n\n" + extracted
    try:
        result = await generate_ai_reply(
            user_id=update.effective_user.id,
            user_text=prompt,
            context_messages=_history(context),
            profile_context=_profile_context(update),
            mode="medical",
        )
    except Exception:
        await msg.reply_text(
            "🤖 صار خطأ غير متوقع أثناء تحليل الملف. جرّب مرة ثانية بعد شوي.",
            reply_markup=ai_chat_keyboard(),
        )
        return True
    for part in split_reply(result.text):
        await msg.reply_text(part, reply_markup=ai_chat_keyboard())
    return True
