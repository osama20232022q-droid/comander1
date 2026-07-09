from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlalchemy import select
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from app.config import settings
from app.db import init_db, get_session
from app.models import User
from app.repositories.users_repo import ensure_user
from app.keyboards import main_keyboard
from app.handlers.onboarding import start_onboarding, handle_onboarding_text, confirm_onboarding
from app.handlers.subjects import (
    show_subjects_menu, begin_add_subject, handle_add_subject, open_subject, begin_upload,
    handle_attachment_message, list_attachments, analyze_subject
)
from app.handlers.plans import start_plan_flow, handle_plan_text, handle_plan_callback
from app.handlers.pomodoro import show_pomodoro, handle_pomo_callback, handle_custom_pomo, handle_food_log
from app.handlers.motivation import motivate
from app.handlers.progress import show_progress, show_profile
from app.handlers.certificates import show_certificates, handle_cert_callback
from app.handlers.admin import show_admin_panel, handle_admin_callback, is_admin_tg, handle_restore_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("study_commander")


def _is_access_valid(user: User) -> bool:
    if user.role == "admin":
        return True
    if not user.is_active or user.is_banned:
        return False
    if user.access_until and user.access_until < datetime.now(timezone.utc):
        return False
    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        user = ensure_user(db, update.effective_user)
        profile_confirmed = bool(user.profile and user.profile.confirmed)
        access_ok = _is_access_valid(user)
    if not profile_confirmed:
        await start_onboarding(update, context)
        return
    if not access_ok:
        await update.effective_message.reply_text(
            "تم حفظ ملفك، لكن حسابك غير مفعل بعد أو انتهت صلاحيته.\n"
            f"معرفك الرقمي للأدمن: {update.effective_user.id}\n"
            "انتظر تفعيل الأدمن."
        )
        return
    await update.effective_message.reply_text(
        "✅ Study Commander Bot جاهز.\nاختر من لوحة الأوامر:",
        reply_markup=main_keyboard(is_admin_tg(update.effective_user.id)),
    )


async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    msg = update.effective_message or (update.callback_query.message if update.callback_query else None)
    if msg:
        await msg.reply_text("🏠 القائمة الرئيسية", reply_markup=main_keyboard(is_admin_tg(update.effective_user.id)))


async def _require_ready(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    with get_session() as db:
        user = ensure_user(db, update.effective_user)
        if user.is_banned:
            await update.effective_message.reply_text("حسابك محظور.")
            return False
        if not (user.profile and user.profile.confirmed):
            await start_onboarding(update, context)
            return False
        if not _is_access_valid(user):
            await update.effective_message.reply_text(
                "حسابك بانتظار تفعيل الأدمن أو انتهت صلاحيته.\n"
                f"معرفك الرقمي: {update.effective_user.id}"
            )
            return False
    return True


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text or ""
    flow = context.user_data.get("flow")

    if text == "🏠 القائمة الرئيسية":
        await go_home(update, context)
        return

    # Onboarding is allowed before activation.
    if flow == "onboarding":
        await handle_onboarding_text(update, context, text)
        return

    if not await _require_ready(update, context):
        return

    if flow == "add_subject":
        await handle_add_subject(update, context, text)
        return
    if flow == "upload_attachment":
        await handle_attachment_message(update, context)
        return
    if flow == "study_plan":
        await handle_plan_text(update, context, text)
        return
    if flow == "pomo_custom":
        await handle_custom_pomo(update, context, text)
        return
    if flow == "food_log":
        await handle_food_log(update, context, text)
        return
    if flow == "restore_backup":
        await update.effective_message.reply_text("أرسل ملف JSON كوثيقة، وليس نصًا.")
        return

    if text == "📚 المواد":
        await show_subjects_menu(update, context)
    elif text == "🧠 خطة دراسية معمقة":
        await start_plan_flow(update, context)
    elif text == "⏳ البومودورو":
        await show_pomodoro(update, context)
    elif text == "🔥 حفزني":
        await motivate(update, context)
    elif text == "📊 تقدمي":
        await show_progress(update, context)
    elif text == "🏅 شهاداتي":
        await show_certificates(update, context)
    elif text == "👤 ملفي":
        await show_profile(update, context)
    elif text == "👑 لوحة الأدمن" and is_admin_tg(update.effective_user.id):
        await show_admin_panel(update, context)
    elif text == "↩️ خطوة للوراء":
        await update.effective_message.reply_text("استخدم القائمة الرئيسية أو اختر القسم السابق.", reply_markup=main_keyboard(is_admin_tg(update.effective_user.id)))
    else:
        await update.effective_message.reply_text("لم أفهم الأمر. استخدم لوحة الأزرار.", reply_markup=main_keyboard(is_admin_tg(update.effective_user.id)))


async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    flow = context.user_data.get("flow")
    if flow == "restore_backup":
        await handle_restore_file(update, context)
        return
    if flow == "upload_attachment":
        if not await _require_ready(update, context):
            return
        await handle_attachment_message(update, context)
        return
    await update.effective_message.reply_text("لرفع الملفات: افتح 📚 المواد ← اختر المادة ← رفع ملحقات أو أسئلة سنوات.")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    data = q.data or ""

    if data == "home":
        await q.answer()
        await q.message.reply_text("🏠 القائمة الرئيسية", reply_markup=main_keyboard(is_admin_tg(q.from_user.id)))
        context.user_data.clear()
        return

    if data == "onboard:confirm":
        await confirm_onboarding(update, context)
        return
    if data == "onboard:back":
        await q.answer()
        context.user_data["flow"] = "onboarding"
        context.user_data["step"] = "name"
        await q.message.reply_text("اكتب الاسم الثلاثي من جديد.")
        return

    # access check after onboarding callbacks
    with get_session() as db:
        user = ensure_user(db, q.from_user)
        access_ok = _is_access_valid(user)
        profile_ok = bool(user.profile and user.profile.confirmed)
    if not profile_ok:
        await q.answer("أكمل ملفك أولًا", show_alert=True)
        await start_onboarding(update, context)
        return
    if not access_ok and not data.startswith("admin:"):
        await q.answer("بانتظار تفعيل الأدمن", show_alert=True)
        return

    if data == "subject:add":
        await q.answer()
        await begin_add_subject(update, context)
    elif data == "subject:menu":
        await q.answer()
        await show_subjects_menu(update, context)
    elif data.startswith("subject:open:"):
        await q.answer()
        await open_subject(update, context, int(data.split(":")[-1]))
    elif data.startswith("subject:upload:"):
        await q.answer()
        _, _, kind, sid = data.split(":")
        await begin_upload(update, context, int(sid), kind)
    elif data.startswith("subject:list:"):
        await q.answer()
        _, _, kind, sid = data.split(":")
        await list_attachments(update, context, int(sid), kind)
    elif data.startswith("subject:analyze:"):
        await q.answer()
        await analyze_subject(update, context, int(data.split(":")[-1]))
    elif data.startswith("plan:"):
        await handle_plan_callback(update, context, data)
    elif data.startswith("pomo:"):
        await handle_pomo_callback(update, context, data)
    elif data.startswith("cert:"):
        await handle_cert_callback(update, context, data)
    elif data.startswith("admin:"):
        await handle_admin_callback(update, context, data)
    else:
        await q.answer("أمر غير معروف")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled error", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("صار خطأ غير متوقع. أرسل /start أو راجع الأدمن.")
    except Exception:
        pass


async def main() -> None:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is missing. Put it in Railway Variables as BOT_TOKEN.")
    init_db()
    app = Application.builder().token(settings.bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler((filters.Document.ALL | filters.PHOTO | filters.AUDIO | filters.VIDEO) & ~filters.COMMAND, handle_files))
    app.add_error_handler(error_handler)
    log.info("Study Commander Bot v3 started")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    try:
        import asyncio
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
