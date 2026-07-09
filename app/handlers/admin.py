from __future__ import annotations

import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, or_
from telegram import Update
from telegram.ext import ContextTypes
from app.config import settings
from app.db import get_session, DATABASE_URL
from app.models import User, Subject, Attachment, BackupRecord
from app.keyboards import admin_keyboard, nav_keyboard
from app.repositories.users_repo import activate_user, ban_user
from app.services.backup import export_database_to_json


def is_admin_tg(tg_id: int) -> bool:
    return tg_id in settings.admin_ids


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin_tg(update.effective_user.id):
        return
    context.user_data["section"] = "admin"
    await update.effective_message.reply_text("👑 لوحة الأدمن\nهذه اللوحة تظهر لك فقط.", reply_markup=admin_keyboard())


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    if not is_admin_tg(update.effective_user.id):
        return False
    flow = context.user_data.get("flow")
    if flow == "admin_activate":
        await activate_by_input(update, context, text)
        return True
    if flow == "admin_ban":
        await ban_by_input(update, context, text, True)
        return True
    if flow == "admin_unban":
        await ban_by_input(update, context, text, False)
        return True
    if text == "👥 طلبات التفعيل":
        await pending_users(update, context)
        return True
    if text == "➕ تفعيل مشترك":
        context.user_data["flow"] = "admin_activate"
        await update.effective_message.reply_text("أرسل Telegram ID أو username. اختياريًا أضف الأيام.\nمثال: 123456789 30\nمثال: @student 365\nاكتب دائم للتفعيل بلا نهاية.", reply_markup=nav_keyboard())
        return True
    if text == "📋 المستخدمون":
        await list_users(update, context)
        return True
    if text == "🚫 حظر مستخدم":
        context.user_data["flow"] = "admin_ban"
        await update.effective_message.reply_text("أرسل Telegram ID أو username لحظره.", reply_markup=nav_keyboard())
        return True
    if text == "✅ إلغاء الحظر":
        context.user_data["flow"] = "admin_unban"
        await update.effective_message.reply_text("أرسل Telegram ID أو username لإلغاء الحظر.", reply_markup=nav_keyboard())
        return True
    if text == "📦 نسخة احتياطية الآن":
        await backup_now(update, context)
        return True
    if text == "♻️ فحص ملف استرجاع":
        context.user_data["flow"] = "restore_backup"
        await update.effective_message.reply_text("أرسل ملف backup JSON كوثيقة حتى أفحصه. الاسترجاع التلقائي غير مفعل حمايةً للبيانات.", reply_markup=nav_keyboard())
        return True
    if text == "☁️ حالة قاعدة البيانات":
        await db_status(update, context)
        return True
    return False


def _find_user(db, token: str) -> User | None:
    raw = token.strip()
    if raw.startswith("@"):
        raw = raw[1:]
    if raw.isdigit():
        # Try telegram_id first, then internal id
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
        admin = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
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
    provider = "PostgreSQL خارجي" if DATABASE_URL.startswith("postgres") else "SQLite محلي/Volume"
    await update.effective_message.reply_text(
        f"☁️ حالة قاعدة البيانات\n\nProvider: {provider}\nUsers: {users}\nSubjects: {subjects}\nFiles refs: {files}\n\n"
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


# compatibility
async def handle_admin_callback(update, context, data):
    await update.callback_query.answer("هذه النسخة تستخدم لوحة الكيبورد للأدمن.", show_alert=True)
