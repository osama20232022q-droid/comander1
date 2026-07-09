from __future__ import annotations

import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from telegram import Update
from telegram.ext import ContextTypes

from app.config import settings
from app.db import get_session, DATABASE_URL
from app.models import (
    User, Subject, Attachment, BackupRecord, StudyPlan, PomodoroSession,
    Certificate, FoodLog, MotivationLog, AdminAction, ButtonConfig
)
from app.keyboards import (
    admin_keyboard, nav_keyboard, admin_buttons_keyboard, admin_button_edit_keyboard,
    button_selector_keyboard, button_confirm_delete_keyboard, button_style_keyboard
)
from app.services.backup import export_database_to_json
from app.services.buttons import (
    action_by_label, all_visible_buttons, button_selector_rows, delete_button,
    deleted_buttons, restore_button, rename_button, set_button_style,
    add_custom_button, restore_default_visibility, display_label, PROTECTED_ACTIONS
)


def is_admin_tg(tg_id: int) -> bool:
    return tg_id in settings.admin_ids


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin_tg(update.effective_user.id):
        return
    context.user_data["section"] = "admin"
    context.user_data.pop("flow", None)
    await update.effective_message.reply_text("👑 لوحة الأدمن\nهذه اللوحة تظهر لك فقط.", reply_markup=admin_keyboard())


async def show_buttons_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["section"] = "admin_buttons"
    context.user_data.pop("flow", None)
    await update.effective_message.reply_text(
        "🧩 إدارة الأزرار\n\n"
        "من هنا تستطيع حذف/إخفاء زر، استرجاع زر محذوف، إعادة تسمية، إضافة زر كيبورد أو زر شفاف، وتعديل نمط اللون.",
        reply_markup=admin_buttons_keyboard(),
    )


async def show_button_edit_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("flow", None)
    await update.effective_message.reply_text(
        "✏️ تعديل الأزرار\nاختر العملية المطلوبة. فصلت الحذف عن الإضافة والتسمية حتى لا يحدث حذف بالخطأ.",
        reply_markup=admin_button_edit_keyboard(),
    )


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    if not is_admin_tg(update.effective_user.id):
        return False

    flow = context.user_data.get("flow")
    if flow:
        return await handle_admin_flow(update, context, text)

    btn = action_by_label(text, scopes=("admin", "admin_buttons", "admin_button_edit", "admin_entry", "both"))
    action = btn.action_key if btn else None

    # Compatibility with older labels even after DB reset.
    aliases = {
        "👥 طلبات التفعيل": "admin_pending",
        "➕ تفعيل مشترك": "admin_activate",
        "📋 المستخدمون": "admin_users",
        "📊 إحصائيات النظام": "admin_stats",
        "🚫 حظر مستخدم": "admin_ban",
        "✅ إلغاء الحظر": "admin_unban",
        "📦 نسخة احتياطية الآن": "admin_backup",
        "♻️ فحص ملف استرجاع": "admin_restore_check",
        "☁️ حالة قاعدة البيانات": "admin_db_status",
        "🧩 الأزرار": "admin_buttons",
        "✏️ تعديل الأزرار": "admin_button_edit",
        "🎨 تعديل ألوان الأزرار": "admin_button_colors",
        "➕ زر لوحة كيبورد": "admin_add_keyboard",
        "➕ زر شفاف": "admin_add_inline",
        "🗑️ الأزرار المحذوفة": "admin_deleted_buttons",
        "🔄 استرجاع الأزرار الافتراضية": "admin_restore_defaults",
        "🗑️ حذف زر معين": "admin_delete_button",
        "✏️ إعادة تسمية زر معين": "admin_rename_button",
        "➕ إضافة زر معين": "admin_add_button_from_edit",
        "↩️ رجوع إلى الأزرار": "admin_buttons",
        "👑 لوحة الأدمن": "admin_panel",
    }
    action = action or aliases.get(text)

    if action == "admin_panel":
        await show_admin_panel(update, context)
        return True
    if action == "admin_pending":
        await pending_users(update, context)
        return True
    if action == "admin_activate":
        context.user_data["flow"] = "admin_activate"
        await update.effective_message.reply_text(
            "أرسل Telegram ID أو username. اختياريًا أضف الأيام.\n"
            "مثال: 123456789 30\nمثال: @student 365\nاكتب دائم للتفعيل بلا نهاية.",
            reply_markup=nav_keyboard(),
        )
        return True
    if action == "admin_users":
        await list_users(update, context)
        return True
    if action == "admin_stats":
        await system_stats(update, context)
        return True
    if action == "admin_ban":
        context.user_data["flow"] = "admin_ban"
        await update.effective_message.reply_text("أرسل Telegram ID أو username لحظره.", reply_markup=nav_keyboard())
        return True
    if action == "admin_unban":
        context.user_data["flow"] = "admin_unban"
        await update.effective_message.reply_text("أرسل Telegram ID أو username لإلغاء الحظر.", reply_markup=nav_keyboard())
        return True
    if action == "admin_backup":
        await backup_now(update, context)
        return True
    if action == "admin_restore_check":
        context.user_data["flow"] = "restore_backup"
        await update.effective_message.reply_text("أرسل ملف backup JSON كوثيقة حتى أفحصه. الاسترجاع التلقائي غير مفعل حمايةً للبيانات.", reply_markup=nav_keyboard())
        return True
    if action == "admin_db_status":
        await db_status(update, context)
        return True

    # Button manager
    if action == "admin_buttons":
        await show_buttons_panel(update, context)
        return True
    if action == "admin_button_edit":
        await show_button_edit_panel(update, context)
        return True
    if action == "admin_button_colors":
        context.user_data["flow"] = "button_color_select"
        buttons = all_visible_buttons()
        await update.effective_message.reply_text("🎨 اختر الزر الذي تريد تعديل نمطه/لونه:", reply_markup=button_selector_keyboard(button_selector_rows(buttons)))
        return True
    if action == "admin_add_keyboard" or action == "admin_add_button_from_edit":
        context.user_data["flow"] = "button_add_label"
        context.user_data["new_button_type"] = "reply"
        await update.effective_message.reply_text("اكتب اسم زر لوحة الكيبورد الجديد:", reply_markup=nav_keyboard())
        return True
    if action == "admin_add_inline":
        context.user_data["flow"] = "button_add_label"
        context.user_data["new_button_type"] = "inline"
        await update.effective_message.reply_text("اكتب اسم الزر الشفاف الجديد:", reply_markup=nav_keyboard())
        return True
    if action == "admin_delete_button":
        context.user_data["flow"] = "button_delete_select"
        buttons = [b for b in all_visible_buttons() if b.action_key not in PROTECTED_ACTIONS]
        await update.effective_message.reply_text(
            "🗑️ اختر الزر الذي تريد حذفه/إخفاءه.\n"
            "لن يتم الحذف مباشرة؛ ستظهر لك شاشة تأكيد مستقلة.",
            reply_markup=button_selector_keyboard(button_selector_rows(buttons)),
        )
        return True
    if action == "admin_rename_button":
        context.user_data["flow"] = "button_rename_select"
        buttons = all_visible_buttons()
        await update.effective_message.reply_text("✏️ اختر الزر الذي تريد إعادة تسميته:", reply_markup=button_selector_keyboard(button_selector_rows(buttons)))
        return True
    if action == "admin_deleted_buttons":
        await show_deleted_buttons(update, context)
        return True
    if action == "admin_restore_defaults":
        restore_default_visibility()
        await update.effective_message.reply_text("✅ تم استرجاع الأزرار الافتراضية للنظام.", reply_markup=admin_buttons_keyboard())
        return True

    return False


async def handle_admin_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    flow = context.user_data.get("flow")

    if text in ["🏠 القائمة الرئيسية"]:
        context.user_data.clear()
        return False
    if text in ["👑 لوحة الأدمن"]:
        await show_admin_panel(update, context)
        return True
    if text in ["↩️ رجوع إلى الأزرار"]:
        await show_buttons_panel(update, context)
        return True

    if flow == "admin_activate":
        await activate_by_input(update, context, text)
        return True
    if flow == "admin_ban":
        await ban_by_input(update, context, text, True)
        return True
    if flow == "admin_unban":
        await ban_by_input(update, context, text, False)
        return True

    if flow == "button_delete_select":
        selected = action_by_label(text, scopes=("main", "admin", "admin_buttons", "admin_button_edit", "admin_entry", "both"))
        if not selected:
            await update.effective_message.reply_text("لم أتعرف على الزر. اختر من القائمة فقط.")
            return True
        context.user_data["delete_action_key"] = selected.action_key
        context.user_data["delete_label"] = display_label(selected)
        await update.effective_message.reply_text(
            f"⚠️ تأكيد حذف الزر:\n{display_label(selected)}\n\n"
            "هذا سيخفي الزر من الواجهة، ويمكن استرجاعه لاحقًا من خانة الأزرار المحذوفة.",
            reply_markup=button_confirm_delete_keyboard(),
        )
        context.user_data["flow"] = "button_delete_confirm"
        return True

    if flow == "button_delete_confirm":
        if text == "✅ تأكيد حذف الزر":
            ok, msg = delete_button(context.user_data.get("delete_action_key", ""))
            context.user_data.pop("flow", None)
            context.user_data.pop("delete_action_key", None)
            await update.effective_message.reply_text(("✅ " if ok else "⚠️ ") + msg, reply_markup=admin_buttons_keyboard())
            return True
        if text == "❌ إلغاء الحذف":
            context.user_data.pop("flow", None)
            context.user_data.pop("delete_action_key", None)
            await update.effective_message.reply_text("تم إلغاء الحذف.", reply_markup=admin_buttons_keyboard())
            return True
        await update.effective_message.reply_text("اختر تأكيد الحذف أو إلغاء الحذف فقط.", reply_markup=button_confirm_delete_keyboard())
        return True

    if flow == "button_rename_select":
        selected = action_by_label(text, scopes=("main", "admin", "admin_buttons", "admin_button_edit", "admin_entry", "both"))
        if not selected:
            await update.effective_message.reply_text("اختر زرًا من القائمة فقط.")
            return True
        context.user_data["rename_action_key"] = selected.action_key
        context.user_data["flow"] = "button_rename_value"
        await update.effective_message.reply_text(f"اكتب الاسم الجديد للزر:\n{display_label(selected)}", reply_markup=nav_keyboard())
        return True

    if flow == "button_rename_value":
        ok, msg = rename_button(context.user_data.get("rename_action_key", ""), text)
        context.user_data.pop("flow", None)
        context.user_data.pop("rename_action_key", None)
        await update.effective_message.reply_text(("✅ " if ok else "⚠️ ") + msg, reply_markup=admin_buttons_keyboard())
        return True

    if flow == "button_color_select":
        selected = action_by_label(text, scopes=("main", "admin", "admin_buttons", "admin_button_edit", "admin_entry", "both"))
        if not selected:
            await update.effective_message.reply_text("اختر زرًا من القائمة فقط.")
            return True
        context.user_data["style_action_key"] = selected.action_key
        context.user_data["flow"] = "button_color_value"
        await update.effective_message.reply_text(f"اختر لون/نمط الزر:\n{display_label(selected)}", reply_markup=button_style_keyboard())
        return True

    if flow == "button_color_value":
        mapping = {"⚪ عادي": "default", "🔵 أزرق": "primary", "🟢 أخضر": "success", "🔴 أحمر": "danger"}
        if text not in mapping:
            await update.effective_message.reply_text("اختر لونًا من الأزرار فقط.", reply_markup=button_style_keyboard())
            return True
        ok, msg = set_button_style(context.user_data.get("style_action_key", ""), mapping[text])
        context.user_data.pop("flow", None)
        context.user_data.pop("style_action_key", None)
        await update.effective_message.reply_text(("✅ " if ok else "⚠️ ") + msg, reply_markup=admin_buttons_keyboard())
        return True

    if flow == "button_add_label":
        context.user_data["new_button_label"] = text.strip()
        context.user_data["flow"] = "button_add_response"
        await update.effective_message.reply_text("اكتب النص الذي يرسله البوت عند ضغط هذا الزر:", reply_markup=nav_keyboard())
        return True

    if flow == "button_add_response":
        ok, msg = add_custom_button(context.user_data.get("new_button_label", ""), text, context.user_data.get("new_button_type", "reply"))
        context.user_data.pop("flow", None)
        context.user_data.pop("new_button_label", None)
        context.user_data.pop("new_button_type", None)
        await update.effective_message.reply_text(("✅ " if ok else "⚠️ ") + msg, reply_markup=admin_buttons_keyboard())
        return True

    if flow == "button_restore_select":
        # Deleted buttons are not visible, so match by raw display labels from deleted list.
        deleted = deleted_buttons()
        selected = None
        for b in deleted:
            if text == display_label(b) or text.strip() == b.label.strip():
                selected = b
                break
        if not selected:
            await update.effective_message.reply_text("اختر زرًا محذوفًا من القائمة فقط.")
            return True
        ok, msg = restore_button(selected.action_key)
        context.user_data.pop("flow", None)
        await update.effective_message.reply_text(("✅ " if ok else "⚠️ ") + msg, reply_markup=admin_buttons_keyboard())
        return True

    if flow == "restore_backup":
        await update.effective_message.reply_text("أرسل ملف JSON كوثيقة، وليس نصًا.")
        return True

    return False


def _find_user(db, token: str) -> User | None:
    raw = token.strip()
    if raw.startswith("@"):
        raw = raw[1:]
    if raw.isdigit():
        return db.scalar(select(User).where(User.telegram_id == int(raw))) or db.get(User, int(raw))
    return db.scalar(select(User).where(func.lower(User.username) == raw.lower()))


async def activate_by_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    parts = text.split()
    if not parts:
        await update.effective_message.reply_text("أرسل ID أو username.")
        return
    token = parts[0]
    days = 30
    if len(parts) > 1:
        if parts[1] in ["دائم", "none", "permanent"]:
            days = None
        elif parts[1].isdigit():
            days = int(parts[1])
    with get_session() as db:
        target = _find_user(db, token)
        if not target:
            await update.effective_message.reply_text("المستخدم غير موجود بقاعدة البيانات. لازم يفتح البوت مرة أولًا ويرسل /start.", reply_markup=admin_keyboard())
            context.user_data.pop("flow", None)
            return
        target.is_active = True
        target.is_banned = False
        target.access_until = None if days is None else datetime.now(timezone.utc) + timedelta(days=days)
        db.commit()
        tg_id = target.telegram_id
    context.user_data.pop("flow", None)
    await update.effective_message.reply_text("✅ تم تفعيل المشترك.", reply_markup=admin_keyboard())
    try:
        await context.bot.send_message(tg_id, "✅ تم تفعيل حسابك. أرسل /start لفتح الواجهة الرئيسية.")
    except Exception:
        pass


async def ban_by_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, banned: bool) -> None:
    token = text.split()[0] if text.split() else ""
    with get_session() as db:
        target = _find_user(db, token)
        if not target:
            await update.effective_message.reply_text("المستخدم غير موجود.", reply_markup=admin_keyboard())
            context.user_data.pop("flow", None)
            return
        target.is_banned = banned
        if banned:
            target.is_active = False
        db.commit()
    context.user_data.pop("flow", None)
    await update.effective_message.reply_text("تم الحظر." if banned else "تم إلغاء الحظر.", reply_markup=admin_keyboard())


async def pending_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        users = db.scalars(select(User).where(User.is_active == False, User.is_banned == False, User.role != "admin").order_by(User.created_at.desc()).limit(20)).all()
    if not users:
        await update.effective_message.reply_text("لا توجد طلبات تفعيل.", reply_markup=admin_keyboard())
        return
    lines = ["👥 طلبات التفعيل:\n"]
    for u in users:
        name = u.profile.full_name if u.profile else (u.first_name or "بدون ملف")
        lines.append(f"• {name}\nTelegram ID: {u.telegram_id}\nUsername: @{u.username or '-'}\n")
    lines.append("للتفعيل اضغط ➕ تفعيل مشترك ثم أرسل الـ ID.")
    await update.effective_message.reply_text("\n".join(lines), reply_markup=admin_keyboard())


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        users = db.scalars(select(User).order_by(User.created_at.desc()).limit(30)).all()
    lines = ["📋 آخر المستخدمين:"]
    for u in users:
        name = u.profile.full_name if u.profile else (u.first_name or "-")
        status = "✅" if u.is_active else "⏳"
        ban = "🚫" if u.is_banned else ""
        until = u.access_until.date().isoformat() if u.access_until else "دائم/غير محدد"
        lines.append(f"{status}{ban} #{u.id} — {name} — TG:{u.telegram_id} — @{u.username or '-'} — إلى: {until}")
    await update.effective_message.reply_text("\n".join(lines), reply_markup=admin_keyboard())


async def system_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now(timezone.utc)
    with get_session() as db:
        total = db.scalar(select(func.count()).select_from(User)) or 0
        active = db.scalar(select(func.count()).select_from(User).where(User.is_active == True, User.is_banned == False)) or 0
        pending = db.scalar(select(func.count()).select_from(User).where(User.is_active == False, User.is_banned == False, User.role != "admin")) or 0
        banned = db.scalar(select(func.count()).select_from(User).where(User.is_banned == True)) or 0
        admins = db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) or 0
        expired = db.scalar(select(func.count()).select_from(User).where(User.access_until.is_not(None), User.access_until < now, User.is_banned == False)) or 0
        subjects = db.scalar(select(func.count()).select_from(Subject)) or 0
        files = db.scalar(select(func.count()).select_from(Attachment)) or 0
        plans = db.scalar(select(func.count()).select_from(StudyPlan)) or 0
        sessions = db.scalar(select(func.count()).select_from(PomodoroSession)) or 0
        certs = db.scalar(select(func.count()).select_from(Certificate)) or 0
        food = db.scalar(select(func.count()).select_from(FoodLog)) or 0
        motivations = db.scalar(select(func.count()).select_from(MotivationLog)) or 0
        buttons = db.scalar(select(func.count()).select_from(ButtonConfig)) or 0
        deleted_btns = db.scalar(select(func.count()).select_from(ButtonConfig).where(ButtonConfig.deleted_at.is_not(None))) or 0
        banned_users = db.scalars(select(User).where(User.is_banned == True).order_by(User.updated_at.desc()).limit(10)).all()
    lines = [
        "📊 إحصائيات النظام",
        "",
        f"👥 إجمالي المستخدمين: {total}",
        f"✅ المشتركين/المفعلين: {active}",
        f"⏳ بانتظار التفعيل: {pending}",
        f"⌛ اشتراكات منتهية: {expired}",
        f"🚫 المحظورين: {banned}",
        f"👑 الأدمن: {admins}",
        "",
        f"📚 المواد: {subjects}",
        f"📎 الملفات/المراجع: {files}",
        f"🧠 الخطط الدراسية: {plans}",
        f"⏳ جلسات البومودورو: {sessions}",
        f"🍽️ سجلات الأكل: {food}",
        f"🔥 رسائل التحفيز المستخدمة: {motivations}",
        f"🏅 الشهادات: {certs}",
        f"🧩 الأزرار المسجلة: {buttons}",
        f"🗑️ الأزرار المحذوفة: {deleted_btns}",
    ]
    if banned_users:
        lines.append("\n🚫 آخر المحظورين:")
        for u in banned_users:
            name = u.profile.full_name if u.profile else (u.first_name or "-")
            lines.append(f"• {name} — TG:{u.telegram_id} — @{u.username or '-'}")
    await update.effective_message.reply_text("\n".join(lines), reply_markup=admin_keyboard())


async def show_deleted_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    buttons = deleted_buttons()
    if not buttons:
        await update.effective_message.reply_text("لا توجد أزرار محذوفة.", reply_markup=admin_buttons_keyboard())
        return
    context.user_data["flow"] = "button_restore_select"
    lines = ["🗑️ الأزرار المحذوفة", "اختر زرًا من القائمة لاسترجاعه:"]
    for b in buttons[:20]:
        lines.append(f"• {b.label} — النوع: {b.button_type} — القسم: {b.scope}")
    await update.effective_message.reply_text("\n".join(lines), reply_markup=button_selector_keyboard(button_selector_rows(buttons)))


async def backup_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(tempfile.gettempdir()) / f"study_commander_backup_{ts}.json"
    try:
        export_database_to_json(path)
        with get_session() as db:
            admin = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
            if admin:
                db.add(BackupRecord(admin_user_id=admin.id, file_name=path.name, status="created", details="telegram_export"))
                db.commit()
        await update.effective_message.reply_document(path.open("rb"), filename=path.name, caption="📦 نسخة احتياطية JSON. هذا الزر أدمن فقط.", reply_markup=admin_keyboard())
    except Exception as e:
        await update.effective_message.reply_text(f"فشل إنشاء النسخة الاحتياطية: {e}", reply_markup=admin_keyboard())


async def db_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        users = db.scalar(select(func.count()).select_from(User)) or 0
        subjects = db.scalar(select(func.count()).select_from(Subject)) or 0
        files = db.scalar(select(func.count()).select_from(Attachment)) or 0
        buttons = db.scalar(select(func.count()).select_from(ButtonConfig)) or 0
    provider = "PostgreSQL خارجي" if DATABASE_URL.startswith("postgres") else "SQLite محلي/Volume"
    await update.effective_message.reply_text(
        f"☁️ حالة قاعدة البيانات\n\nProvider: {provider}\nUsers: {users}\nSubjects: {subjects}\nFiles refs: {files}\nButtons: {buttons}\n\n"
        "الملفات محفوظة كـ Telegram file_id داخل قاعدة البيانات، لذلك لا تحتاج مساحة سيرفر كبيرة للملحقات.",
        reply_markup=admin_keyboard(),
    )


async def handle_restore_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin_tg(update.effective_user.id):
        return
    doc = update.effective_message.document
    if not doc:
        await update.effective_message.reply_text("أرسل ملف JSON فقط.", reply_markup=admin_keyboard())
        return
    file = await context.bot.get_file(doc.file_id)
    raw = await file.download_as_bytearray()
    try:
        import json
        data = json.loads(raw.decode("utf-8"))
        tables = list(data.get("tables", {}).keys())[:20]
        await update.effective_message.reply_text(
            "✅ تم فحص ملف النسخة الاحتياطية.\n"
            f"Schema: {data.get('schema')}\n"
            f"Tables: {', '.join(tables)}\n\n"
            "الاسترجاع التلقائي غير مفعل حتى لا تُمسح البيانات بالخطأ.",
            reply_markup=admin_keyboard(),
        )
    except Exception as e:
        await update.effective_message.reply_text(f"الملف غير صالح: {e}", reply_markup=admin_keyboard())
    context.user_data.clear()


# compatibility for old inline admin callbacks
async def handle_admin_callback(update, context, data):
    await update.callback_query.answer("هذه النسخة تستخدم لوحة الكيبورد للأدمن.", show_alert=True)
