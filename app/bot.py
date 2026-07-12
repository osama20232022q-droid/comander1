from __future__ import annotations

import logging
from datetime import UTC, datetime

from telegram import BotCommand, Update
from telegram.ext import (
    AIORateLimiter,
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from app.config import settings
from app.db import get_session, init_db
from app.handlers.admin import (
    handle_admin_callback,
    handle_admin_text,
    handle_restore_file,
    is_admin_tg,
    show_admin_panel,
)
from app.handlers.ai_chat import handle_ai_chat_file, handle_ai_chat_text, show_ai_chat
from app.handlers.certificates import handle_cert_callback, handle_certificate_text, show_certificates
from app.handlers.discipline import (
    handle_discipline_text,
    send_today_html,
    show_operations_room,
)
from app.handlers.habits import (
    handle_habit_text,
    list_habits,
    show_manual_settings,
    start_habit_add,
    start_routine_change,
)
from app.handlers.motivation import motivate
from app.handlers.onboarding import confirm_onboarding, handle_onboarding_text, start_onboarding
from app.handlers.plans import handle_plan_callback, handle_plan_text, start_plan_flow
from app.handlers.pomodoro import (
    handle_custom_pomo,
    handle_food_log,
    handle_pomodoro_text,
    show_pomodoro,
    show_remaining,
)
from app.handlers.prayer_reminders import handle_prayer_text, prayer_notifier_job, show_prayer_menu
from app.handlers.progress import handle_profile_edit_text, show_profile, show_progress, start_profile_edit
from app.handlers.subjects import (
    analyze_current_subject,
    begin_add_subject,
    begin_upload_current,
    handle_add_subject,
    handle_attachment_message,
    list_current_attachments,
    open_subject_by_name,
    show_subjects_menu,
)
from app.keyboards import main_keyboard
from app.models import User
from app.repositories.users_repo import ensure_user
from app.services.buttons import (
    action_by_label,
    custom_button_response_by_id,
    ensure_default_buttons,
    inline_custom_keyboard,
)
from app.services.inbound_rate_limit import inbound_guard
from app.version import version_label

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("study_commander")


def _is_access_valid(user: User) -> bool:
    if user.role == "admin":
        return True
    if not user.is_active or user.is_banned:
        return False
    if user.access_until and user.access_until < datetime.now(UTC):
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
        "• يشغل بومودورو وجلسة إنقاذ عند التسويف.\n"
        "• غرفة عمليات تسجل النوم، الهاتف، النظري، العملي، MCQ والمقالي.\n"
        "• يولد تقرير HTML يومي وأسبوعي مع Discipline Score من 100.\n"
        "• يعطي أوامر تصحيح ثابتة بدل تعديل الجدول كل يوم.\n"
        "• Gemini مساعد للشرح وMCQ والمقالي، ولا يتحكم بالدرجات أو السجلات.\n"
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
                f"حسابك بانتظار تفعيل الأدمن أو انتهت صلاحيته.\nمعرفك الرقمي: {update.effective_user.id}"
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
            return action, text[len(p) :].strip()
    return None


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text or ""
    flow = context.user_data.get("flow")

    if text == "🏠 القائمة الرئيسية":
        await go_home(update, context)
        return

    if await handle_ai_chat_text(update, context, text):
        return

    if flow == "onboarding":
        await handle_onboarding_text(update, context, text)
        return

    if not await _require_ready(update, context):
        return

    if await handle_discipline_text(update, context, text):
        return

    # Admin flows and admin menu are processed first but only for admin.
    admin_related = False
    if is_admin_tg(update.effective_user.id):
        if flow and (flow.startswith("admin_") or flow.startswith("button_") or flow == "restore_backup"):
            admin_related = True
        else:
            admin_btn = action_by_label(
                text, scopes=("admin", "admin_buttons", "admin_button_edit", "admin_entry", "both")
            )
            admin_related = bool(
                admin_btn
                and (
                    admin_btn.scope in ["admin", "admin_buttons", "admin_button_edit", "admin_entry"]
                    or admin_btn.action_key == "admin_panel"
                )
            )
    if admin_related:
        if await handle_admin_text(update, context, text):
            return

    if flow == "profile_edit":
        if await handle_profile_edit_text(update, context, text):
            return
    if flow in ["habit_add", "routine_change"]:
        if await handle_habit_text(update, context, text):
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
    if flow == "prayer_choose_governorate":
        if await handle_prayer_text(update, context, text):
            return
    if flow == "restore_backup":
        await update.effective_message.reply_text("أرسل ملف JSON كوثيقة، وليس نصًا.")
        return

    # Main menu
    main_btn = action_by_label(text, scopes=("main", "profile", "both", "admin_entry"))
    main_action = main_btn.action_key if main_btn else None

    if main_action == "subjects" or text == "📚 المواد":
        await show_subjects_menu(update, context)
    elif text == "➕ إضافة مادة":
        await begin_add_subject(update, context)
    elif text == "📁 موادي":
        await show_subjects_menu(update, context)
    elif text.startswith("📘 "):
        await open_subject_by_name(update, context, text)
    elif act := _current_subject_action(text):
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
    elif main_action == "study_plan" or text == "🧠 خطة دراسية معمقة":
        await start_plan_flow(update, context)
    elif main_action == "pomodoro" or text == "⏳ البومودورو":
        await show_pomodoro(update, context)
    elif main_action == "ai_chat" or text == "🤖 دردشة AI":
        await show_ai_chat(update, context)
    elif main_action == "discipline" or text == "🪖 غرفة العمليات":
        await show_operations_room(update, context)
    elif await handle_pomodoro_text(update, context, text):
        return
    elif main_action == "motivate" or text == "🔥 حفزني":
        await motivate(update, context)
    elif main_action == "prayer_reminders" or text == "🕌 أذكار الصلاة":
        await show_prayer_menu(update, context)
    elif await handle_prayer_text(update, context, text):
        return
    elif main_action == "progress" or text == "📊 تقدمي":
        await show_progress(update, context)
    elif main_action == "certificates" or text == "🏅 شهاداتي":
        await show_certificates(update, context)
    elif await handle_certificate_text(update, context, text):
        return
    elif main_action == "profile" or text == "👤 ملفي":
        await show_profile(update, context)
    elif main_action == "manual_settings" or text == "⚙️ ضبط يدوي":
        await show_manual_settings(update, context)
    elif main_action == "profile_edit" or text == "✏️ تعديل معلوماتي":
        await start_profile_edit(update, context)
    elif main_action == "routine_change" or text == "🔄 تغيير نظامي":
        await start_routine_change(update, context)
    elif main_action == "habit_add" or text == "🌱 إضافة عادة":
        await start_habit_add(update, context)
    elif main_action == "habits_list" or text == "📋 عاداتي":
        await list_habits(update, context)
    elif main_action == "remaining" or text == "⌛ كم المتبقي؟":
        await show_remaining(update, context)
    elif main_action == "help" or text == "❓ ماذا يفعل هذا البوت؟":
        await cmd_help(update, context)
    elif main_action == "inline_buttons" or text == "🔘 الأزرار الشفافة":
        kb = inline_custom_keyboard()
        if not kb:
            await update.effective_message.reply_text(
                "لا توجد أزرار شفافة مضافة حاليًا.", reply_markup=main_keyboard(is_admin_tg(update.effective_user.id))
            )
        else:
            await update.effective_message.reply_text("🔘 الأزرار الشفافة المضافة:", reply_markup=kb)
    elif main_action == "admin_panel" and is_admin_tg(update.effective_user.id):
        await show_admin_panel(update, context)
    elif main_action and main_action.startswith("custom:"):
        await update.effective_message.reply_text(
            main_btn.response_text or "هذا زر مخصص بلا نص.",
            reply_markup=main_keyboard(is_admin_tg(update.effective_user.id)),
        )
    elif text == "↩️ خطوة للوراء":
        await update.effective_message.reply_text(
            "تم الرجوع للقائمة الرئيسية.", reply_markup=main_keyboard(is_admin_tg(update.effective_user.id))
        )
    else:
        await update.effective_message.reply_text(
            "لم أفهم الأمر. استخدم لوحة الأزرار.", reply_markup=main_keyboard(is_admin_tg(update.effective_user.id))
        )


async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await handle_ai_chat_file(update, context):
        return
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
    if data.startswith("custombtn:"):
        try:
            button_id = int(data.split(":", 1)[1])
        except ValueError:
            await q.answer("زر غير صالح.", show_alert=True)
            return
        response = custom_button_response_by_id(button_id)
        await q.answer()
        await q.message.reply_text(response or "هذا الزر غير متاح حاليًا.")
        return
    await q.answer("هذا الزر لم يعد نشطًا.", show_alert=True)


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
        BotCommand("prayer", "أذكار الصلاة وتذكيرات الأوقات"),
        BotCommand("profile", "عرض ملفي"),
        BotCommand("habits", "عاداتي وتغيير النظام"),
        BotCommand("ai", "دردشة AI للشرح والأسئلة"),
        BotCommand("report", "تقرير الانضباط اليومي"),
        BotCommand("admin", "لوحة الأدمن"),
    ]
    await app.bot.set_my_commands(commands)
    try:
        await app.bot.set_my_short_description("قيادة دراسة وانضباط: خطط، مؤقت، تقارير HTML وGemini.")
        await app.bot.set_my_description(
            "Study Commander Bot يقود الدراسة والانضباط: مواد وخطط وبومودورو، غرفة عمليات، تقارير HTML يومية وأسبوعية، وGemini للمساعدة الدراسية."
        )
    except Exception:
        log.warning("Could not set bot description/short description", exc_info=True)


async def main() -> None:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is missing. Put it in Railway Variables as BOT_TOKEN.")
    init_db()
    ensure_default_buttons()
    app = (
        Application.builder()
        .token(settings.bot_token)
        .concurrent_updates(settings.bot_concurrent_updates)
        .connection_pool_size(settings.tg_connection_pool_size)
        .pool_timeout(settings.tg_pool_timeout)
        .read_timeout(settings.tg_read_timeout)
        .write_timeout(settings.tg_write_timeout)
        .rate_limiter(AIORateLimiter())
        .build()
    )
    app.add_handler(TypeHandler(Update, inbound_guard), group=-100)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", go_home))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("remaining", show_remaining))
    app.add_handler(CommandHandler("prayer", show_prayer_menu))
    app.add_handler(CommandHandler("profile", show_profile))
    app.add_handler(CommandHandler("habits", show_manual_settings))
    app.add_handler(CommandHandler("ai", show_ai_chat))
    app.add_handler(CommandHandler("report", send_today_html))
    app.add_handler(CommandHandler("admin", show_admin_panel))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(
        MessageHandler(
            (filters.Document.ALL | filters.PHOTO | filters.AUDIO | filters.VIDEO) & ~filters.COMMAND, handle_files
        )
    )
    app.add_error_handler(error_handler)
    if app.job_queue:
        app.job_queue.run_repeating(
            prayer_notifier_job,
            interval=settings.prayer_job_interval,
            first=20,
            name="prayer_notifier",
        )
    log.info("%s started", version_label())
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
