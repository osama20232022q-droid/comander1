from __future__ import annotations

import logging
from datetime import datetime, timezone
from telegram import Update, BotCommand
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from app.config import settings
from app.db import init_db, get_session
from app.models import User
from app.repositories.users_repo import ensure_user
from app.keyboards import main_keyboard
from app.handlers.onboarding import start_onboarding, handle_onboarding_text, confirm_onboarding
from app.handlers.subjects import (
    show_subjects_menu, begin_add_subject, handle_add_subject, open_subject_by_name,
    begin_upload_current, handle_attachment_message, list_current_attachments, analyze_current_subject,
)
from app.handlers.plans import start_plan_flow, handle_plan_text, handle_plan_callback
from app.handlers.pomodoro import show_pomodoro, handle_pomodoro_text, handle_custom_pomo, handle_food_log, show_remaining
from app.handlers.motivation import motivate
from app.handlers.progress import show_progress, show_profile
from app.handlers.certificates import show_certificates, handle_certificate_text, handle_cert_callback
from app.handlers.admin import show_admin_panel, handle_admin_callback, is_admin_tg, handle_restore_file, handle_admin_text

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


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "❓ ماذا يفعل هذا البوت؟\n\n"
        "• ينظم موادك وملفاتك وأسئلة السنوات.\n"
        "• يصنع خطة دراسية حسب مستواك ونوع امتحانك والأيام المتبقية.\n"
        "• يشغل بومودورو مع وقت متبقٍ وتقدم بالثواني.\n"
        "• يتابع ساعاتك وتقدمك وشهاداتك.\n"
        "• يعطي رسائل تحفيزية متوازنة بدون تكرار سريع.\n"
        "• لوحة الأدمن والتفعيل والنسخ الاحتياطي تظهر للأدمن فقط.",
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


def _current_subject_action(text: str) -> tuple[str, str] | None:
    prefixes = [
        ("📎 رفع ملحقات ", "upload_material"),
        ("📘 رفع أسئلة سنوات ", "upload_past"),
        ("📂 عرض ملحقات ", "list_material"),
        ("📚 عرض أسئلة سنوات ", "list_past"),
        ("🧠 تحليل سريع ", "analyze"),
    ]
    for p, action in prefixes:
        if text.startswith(p):
            return action, text[len(p):].strip()
    return None


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text or ""
    flow = context.user_data.get("flow")

    if text == "🏠 القائمة الرئيسية":
        await go_home(update, context)
        return

    if flow == "onboarding":
        await handle_onboarding_text(update, context, text)
        return

    if not await _require_ready(update, context):
        return

    # Admin flows and admin menu are processed first but only for admin.
    if is_admin_tg(update.effective_user.id) and (flow in ["admin_activate", "admin_ban", "admin_unban"] or text in ["👥 طلبات التفعيل", "➕ تفعيل مشترك", "📋 المستخدمون", "🚫 حظر مستخدم", "✅ إلغاء الحظر", "📦 نسخة احتياطية الآن", "♻️ فحص ملف استرجاع", "☁️ حالة قاعدة البيانات"]):
        if await handle_admin_text(update, context, text):
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

    # Main menu
    if text == "📚 المواد":
        await show_subjects_menu(update, context)
    elif text == "➕ إضافة مادة":
        await begin_add_subject(update, context)
    elif text == "📁 موادي":
        await show_subjects_menu(update, context)
    elif text.startswith("📘 "):
        await open_subject_by_name(update, context, text)
    elif (act := _current_subject_action(text)):
        action, _ = act
        if action == "upload_material":
            await begin_upload_current(update, context, "material")
        elif action == "upload_past":
            await begin_upload_current(update, context, "past_question")
        elif action == "list_material":
            await list_current_attachments(update, context, "material")
        elif action == "list_past":
            await list_current_attachments(update, context, "past_question")
        elif action == "analyze":
            await analyze_current_subject(update, context)
    elif text == "🧠 خطة دراسية معمقة":
        await start_plan_flow(update, context)
    elif text == "⏳ البومودورو":
        await show_pomodoro(update, context)
    elif await handle_pomodoro_text(update, context, text):
        return
    elif text == "🔥 حفزني":
        await motivate(update, context)
    elif text == "📊 تقدمي":
        await show_progress(update, context)
    elif text == "🏅 شهاداتي":
        await show_certificates(update, context)
    elif await handle_certificate_text(update, context, text):
        return
    elif text == "👤 ملفي":
        await show_profile(update, context)
    elif text == "⌛ كم المتبقي؟":
        await show_remaining(update, context)
    elif text == "❓ ماذا يفعل هذا البوت؟":
        await cmd_help(update, context)
    elif text == "👑 لوحة الأدمن" and is_admin_tg(update.effective_user.id):
        await show_admin_panel(update, context)
    elif text == "↩️ خطوة للوراء":
        await update.effective_message.reply_text("تم الرجوع للقائمة الرئيسية.", reply_markup=main_keyboard(is_admin_tg(update.effective_user.id)))
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
    # Left only so old inline messages do not crash. New v4 uses ReplyKeyboard buttons only.
    q = update.callback_query
    data = q.data or ""
    if data == "onboard:confirm":
        await confirm_onboarding(update, context)
        return
    if data.startswith("plan:"):
        await handle_plan_callback(update, context, data)
        return
    if data.startswith("cert:"):
        await handle_cert_callback(update, context, data)
        return
    if data.startswith("admin:"):
        await handle_admin_callback(update, context, data)
        return
    await q.answer("هذه النسخة تستخدم أزرار لوحة الكيبورد فقط.", show_alert=True)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled error", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("صار خطأ غير متوقع. أرسل /start أو راجع الأدمن.")
    except Exception:
        pass


async def configure_bot_profile(app: Application) -> None:
    commands = [
        BotCommand("start", "تشغيل البوت وفتح القائمة"),
        BotCommand("menu", "القائمة الرئيسية"),
        BotCommand("help", "ماذا يفعل هذا البوت؟"),
        BotCommand("remaining", "عرض الوقت المتبقي للبومودورو"),
        BotCommand("profile", "عرض ملفي"),
        BotCommand("admin", "لوحة الأدمن"),
    ]
    await app.bot.set_my_commands(commands)
    try:
        await app.bot.set_my_short_description("بوت قيادة دراسة: مواد، خطط، بومودورو، تقدم وشهادات.")
        await app.bot.set_my_description(
            "Study Commander Bot ينظم مواد الطالب وملفاته، يصنع خطط دراسة واقعية، يحسب جلسات البومودورو، يتابع التقدم، ويمنح شهادات إنجاز عند تحقق الشروط."
        )
    except Exception:
        log.warning("Could not set bot description/short description", exc_info=True)


async def main() -> None:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is missing. Put it in Railway Variables as BOT_TOKEN.")
    init_db()
    app = Application.builder().token(settings.bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", go_home))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("remaining", show_remaining))
    app.add_handler(CommandHandler("profile", show_profile))
    app.add_handler(CommandHandler("admin", show_admin_panel))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler((filters.Document.ALL | filters.PHOTO | filters.AUDIO | filters.VIDEO) & ~filters.COMMAND, handle_files))
    app.add_error_handler(error_handler)
    log.info("Study Commander Bot v4 started")
    await app.initialize()
    await configure_bot_profile(app)
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    try:
        import asyncio
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
