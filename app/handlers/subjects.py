from __future__ import annotations

from sqlalchemy import select, func
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.db import get_session
from app.models import User, Subject, Attachment
from app.keyboards import subject_actions_keyboard, nav_keyboard
from app.utils import normalize_text


def _get_current_user(db, tg_id: int) -> User | None:
    return db.scalar(select(User).where(User.telegram_id == tg_id))


async def show_subjects_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        user = _get_current_user(db, update.effective_user.id)
        subjects = db.scalars(select(Subject).where(Subject.user_id == user.id).order_by(Subject.created_at.desc())).all() if user else []
    rows = [[InlineKeyboardButton("➕ إضافة مادة", callback_data="subject:add")]]
    for s in subjects:
        rows.append([InlineKeyboardButton(f"📘 {s.name}", callback_data=f"subject:open:{s.id}")])
    rows.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="home")])
    await update.effective_message.reply_text("📚 قسم المواد\nاختر مادة أو أضف مادة جديدة.", reply_markup=InlineKeyboardMarkup(rows))


async def begin_add_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["flow"] = "add_subject"
    await update.effective_message.reply_text("اكتب اسم المادة كما تريد أن يظهر كزر مستقل. مثال: Anatomy", reply_markup=nav_keyboard())


async def handle_add_subject(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    name = normalize_text(text)
    if len(name) < 2 or len(name) > 80:
        await update.effective_message.reply_text("اسم المادة غير واضح. اكتب اسمًا بين 2 و80 حرف.")
        return
    with get_session() as db:
        user = _get_current_user(db, update.effective_user.id)
        existing = db.scalar(select(Subject).where(Subject.user_id == user.id, func.lower(Subject.name) == name.lower()))
        if existing:
            await update.effective_message.reply_text("هذه المادة موجودة مسبقًا.")
            context.user_data.clear()
            return
        subject = Subject(user_id=user.id, name=name)
        db.add(subject)
        db.commit()
        db.refresh(subject)
    context.user_data.clear()
    await update.effective_message.reply_text(f"✅ تم إنشاء مادة: {name}")
    await show_subjects_menu(update, context)


async def open_subject(update: Update, context: ContextTypes.DEFAULT_TYPE, subject_id: int) -> None:
    with get_session() as db:
        subject = db.get(Subject, subject_id)
        if not subject:
            await update.callback_query.message.reply_text("المادة غير موجودة.")
            return
        material_count = db.scalar(select(func.count()).select_from(Attachment).where(Attachment.subject_id == subject_id, Attachment.kind == "material")) or 0
        past_count = db.scalar(select(func.count()).select_from(Attachment).where(Attachment.subject_id == subject_id, Attachment.kind == "past_question")) or 0
    await update.callback_query.message.reply_text(
        f"📘 {subject.name}\n\nملحقات المادة: {material_count}\nأسئلة السنوات: {past_count}\n\nاختر الإجراء:",
        reply_markup=subject_actions_keyboard(subject_id),
    )


async def begin_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, subject_id: int, kind: str) -> None:
    context.user_data["flow"] = "upload_attachment"
    context.user_data["upload_subject_id"] = subject_id
    context.user_data["upload_kind"] = kind
    kind_ar = "ملحقات المادة" if kind == "material" else "أسئلة السنوات"
    await update.callback_query.message.reply_text(
        f"أرسل الآن ملفات {kind_ar}.\n"
        "أقبل PDF، صور، صوتيات، فيديو، أو نص.\n"
        "عند الانتهاء اضغط 🏠 القائمة الرئيسية أو اكتب تم.",
        reply_markup=nav_keyboard(),
    )


async def handle_attachment_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    subject_id = context.user_data.get("upload_subject_id")
    kind = context.user_data.get("upload_kind")
    msg = update.effective_message
    if not subject_id or not kind:
        await msg.reply_text("اختر المادة أولًا من زر المواد ثم ارفع الملف.")
        return
    with get_session() as db:
        user = _get_current_user(db, update.effective_user.id)
        subject = db.get(Subject, subject_id)
        if not user or not subject or subject.user_id != user.id:
            await msg.reply_text("لا يمكن ربط الملف بهذه المادة.")
            return
        att = Attachment(user_id=user.id, subject_id=subject_id, kind=kind, file_type="text")
        if msg.document:
            d = msg.document
            att.file_type = "document"
            att.telegram_file_id = d.file_id
            att.telegram_file_unique_id = d.file_unique_id
            att.file_name = d.file_name
            att.mime_type = d.mime_type
            att.file_size = d.file_size
        elif msg.photo:
            p = msg.photo[-1]
            att.file_type = "photo"
            att.telegram_file_id = p.file_id
            att.telegram_file_unique_id = p.file_unique_id
            att.file_size = p.file_size
            att.file_name = "photo.jpg"
        elif msg.audio:
            a = msg.audio
            att.file_type = "audio"
            att.telegram_file_id = a.file_id
            att.telegram_file_unique_id = a.file_unique_id
            att.file_name = a.file_name or a.title or "audio"
            att.mime_type = a.mime_type
            att.file_size = a.file_size
        elif msg.video:
            v = msg.video
            att.file_type = "video"
            att.telegram_file_id = v.file_id
            att.telegram_file_unique_id = v.file_unique_id
            att.file_name = v.file_name or "video.mp4"
            att.mime_type = v.mime_type
            att.file_size = v.file_size
        elif msg.text:
            if msg.text.strip() == "تم":
                context.user_data.clear()
                await msg.reply_text("تم إنهاء رفع الملفات.")
                return
            att.file_type = "text"
            att.text_content = msg.text
            att.file_name = "text_note.txt"
        else:
            await msg.reply_text("هذا النوع غير مدعوم حاليًا.")
            return
        db.add(att)
        db.commit()
    await msg.reply_text("✅ تم حفظ الملف وربطه بالمادة داخل قاعدة بيانات البوت.")


async def list_attachments(update: Update, context: ContextTypes.DEFAULT_TYPE, subject_id: int, kind: str) -> None:
    query = update.callback_query
    with get_session() as db:
        subject = db.get(Subject, subject_id)
        attachments = db.scalars(select(Attachment).where(Attachment.subject_id == subject_id, Attachment.kind == kind).order_by(Attachment.uploaded_at.desc()).limit(10)).all()
    if not attachments:
        await query.message.reply_text("لا توجد ملفات بعد.")
        return
    await query.message.reply_text(f"آخر الملفات في {subject.name}:")
    for att in attachments:
        caption = f"#{att.id} — {att.file_name or att.file_type}"
        if att.file_type == "document":
            await query.message.reply_document(att.telegram_file_id, caption=caption)
        elif att.file_type == "photo":
            await query.message.reply_photo(att.telegram_file_id, caption=caption)
        elif att.file_type == "audio":
            await query.message.reply_audio(att.telegram_file_id, caption=caption)
        elif att.file_type == "video":
            await query.message.reply_video(att.telegram_file_id, caption=caption)
        else:
            await query.message.reply_text(f"{caption}\n{att.text_content[:1000] if att.text_content else ''}")


async def analyze_subject(update: Update, context: ContextTypes.DEFAULT_TYPE, subject_id: int) -> None:
    query = update.callback_query
    with get_session() as db:
        subject = db.get(Subject, subject_id)
        material_count = db.scalar(select(func.count()).select_from(Attachment).where(Attachment.subject_id == subject_id, Attachment.kind == "material")) or 0
        past_count = db.scalar(select(func.count()).select_from(Attachment).where(Attachment.subject_id == subject_id, Attachment.kind == "past_question")) or 0
    difficulty = "متوسطة"
    if material_count >= 8 or past_count >= 4:
        difficulty = "عالية"
    elif material_count <= 2 and past_count == 0:
        difficulty = "خفيفة/غير مكتملة"
    await query.message.reply_text(
        f"🧠 تحليل سريع للمادة: {subject.name}\n\n"
        f"ملحقات: {material_count}\nأسئلة سنوات: {past_count}\n"
        f"الصعوبة التقديرية: {difficulty}\n\n"
        "ملاحظة: التحليل المعمق الحقيقي يتم من زر خطة دراسية معمقة لأنه يربط المادة بمستواك ونوع الامتحان والأيام المتبقية."
    )
