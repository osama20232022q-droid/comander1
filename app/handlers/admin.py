from __future__ import annotations

import tempfile
from pathlib import Path
from datetime import datetime
from sqlalchemy import select, func
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.config import settings
from app.db import get_session, DATABASE_URL
from app.models import User, StudentProfile, Subject, Attachment, BackupRecord
from app.keyboards import admin_keyboard
from app.repositories.users_repo import activate_user, ban_user
from app.services.backup import export_database_to_json


def is_admin_tg(tg_id: int) -> bool:
    return tg_id in settings.admin_ids


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin_tg(update.effective_user.id):
        return
    await update.effective_message.reply_text("👑 لوحة الأدمن\nالأزرار أدناه تظهر لك فقط.", reply_markup=admin_keyboard())


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    q = update.callback_query
    if not is_admin_tg(q.from_user.id):
        await q.answer("غير مصرح", show_alert=True)
        return
    await q.answer()
    if data == "admin:pending":
        await pending_users(update, context)
    elif data == "admin:users":
        await list_users(update, context)
    elif data.startswith("admin:activate:"):
        _, _, uid, days = data.split(":")
        await activate(update, context, int(uid), None if days == "none" else int(days))
    elif data.startswith("admin:ban:"):
        await ban(update, context, int(data.split(":")[-1]), True)
    elif data.startswith("admin:unban:"):
        await ban(update, context, int(data.split(":")[-1]), False)
    elif data == "admin:backup":
        await backup_now(update, context)
    elif data == "admin:restore":
        context.user_data["flow"] = "restore_backup"
        await q.message.reply_text("أرسل ملف backup JSON الآن. ملاحظة: الاسترجاع الكامل يحتاج مراجعة قبل التشغيل بالإنتاج؛ هذه النسخة تحفظ الملف وتفحصه ولا تستبدل البيانات تلقائيًا حمايةً لك.")
    elif data == "admin:db_status":
        await db_status(update, context)


async def pending_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    with get_session() as db:
        users = db.scalars(select(User).where(User.is_active == False, User.role != "admin").order_by(User.created_at.desc()).limit(10)).all()
    if not users:
        await q.message.reply_text("لا توجد طلبات تفعيل.")
        return
    for u in users:
        name = u.profile.full_name if u.profile else (u.first_name or "بدون ملف")
        rows = [
            [InlineKeyboardButton("تفعيل 30 يوم", callback_data=f"admin:activate:{u.id}:30"), InlineKeyboardButton("تفعيل دائم", callback_data=f"admin:activate:{u.id}:none")],
            [InlineKeyboardButton("حظر", callback_data=f"admin:ban:{u.id}")],
        ]
        await q.message.reply_text(f"طلب تفعيل\nID: {u.id}\nTelegram: {u.telegram_id}\nالاسم: {name}\nUsername: @{u.username or '-'}", reply_markup=InlineKeyboardMarkup(rows))


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    with get_session() as db:
        users = db.scalars(select(User).order_by(User.created_at.desc()).limit(20)).all()
    lines = ["📋 آخر المستخدمين:"]
    for u in users:
        name = u.profile.full_name if u.profile else (u.first_name or "-")
        status = "✅" if u.is_active else "⏳"
        ban = "🚫" if u.is_banned else ""
        lines.append(f"{status}{ban} #{u.id} — {name} — {u.telegram_id}")
    await q.message.reply_text("\n".join(lines))


async def activate(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: int, days: int | None) -> None:
    q = update.callback_query
    with get_session() as db:
        admin = db.scalar(select(User).where(User.telegram_id == q.from_user.id))
        target = activate_user(db, admin, uid, days)
    if not target:
        await q.message.reply_text("المستخدم غير موجود.")
        return
    await q.message.reply_text("✅ تم التفعيل.")
    try:
        await context.bot.send_message(target.telegram_id, "✅ تم تفعيل حسابك. أرسل /start لفتح الواجهة الرئيسية.")
    except Exception:
        pass


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: int, banned: bool) -> None:
    q = update.callback_query
    with get_session() as db:
        admin = db.scalar(select(User).where(User.telegram_id == q.from_user.id))
        target = ban_user(db, admin, uid, banned)
    await q.message.reply_text("تم تحديث الحظر." if target else "المستخدم غير موجود.")


async def backup_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(tempfile.gettempdir()) / f"study_commander_backup_{ts}.json"
    try:
        export_database_to_json(path)
        with get_session() as db:
            admin = db.scalar(select(User).where(User.telegram_id == q.from_user.id))
            db.add(BackupRecord(admin_user_id=admin.id, file_name=path.name, status="created", details="telegram_export"))
            db.commit()
        await q.message.reply_document(path.open("rb"), filename=path.name, caption="📦 نسخة احتياطية JSON. حمّلها واحتفظ بها. هذا الزر أدمن فقط.")
    except Exception as e:
        await q.message.reply_text(f"فشل إنشاء النسخة الاحتياطية: {e}")


async def db_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    with get_session() as db:
        users = db.scalar(select(func.count()).select_from(User)) or 0
        subjects = db.scalar(select(func.count()).select_from(Subject)) or 0
        files = db.scalar(select(func.count()).select_from(Attachment)) or 0
    provider = "PostgreSQL خارجي" if DATABASE_URL.startswith("postgres") else "SQLite محلي/Volume"
    await q.message.reply_text(
        f"☁️ حالة قاعدة البيانات\n\nProvider: {provider}\nUsers: {users}\nSubjects: {subjects}\nFiles refs: {files}\n\n"
        "ملاحظة: الملفات نفسها مخزنة كـ Telegram file_id، لذلك لا نحتاج مساحة سيرفر كبيرة للملحقات."
    )


async def handle_restore_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin_tg(update.effective_user.id):
        return
    doc = update.effective_message.document
    if not doc:
        await update.effective_message.reply_text("أرسل ملف JSON فقط.")
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
            "لأمان البيانات، الاسترجاع التلقائي غير مفعل في هذه النسخة. إذا تريد أفعّله لاحقًا نضيف تأكيد مزدوج قبل الكتابة."
        )
    except Exception as e:
        await update.effective_message.reply_text(f"الملف غير صالح: {e}")
    context.user_data.clear()
