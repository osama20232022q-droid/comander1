from __future__ import annotations

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import ContextTypes

from app.db import get_session
from app.keyboards import nav_keyboard, subject_detail_keyboard, subjects_menu_keyboard
from app.models import Attachment, Subject, User
from app.utils import normalize_text


def _get_current_user(db, tg_id: int) -> User | None:
    return db.scalar(select(User).where(User.telegram_id == tg_id))


def _subjects_for_user(db, user_id: int):
    return db.scalars(select(Subject).where(Subject.user_id == user_id).order_by(Subject.created_at.desc())).all()


async def show_subjects_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        user = _get_current_user(db, update.effective_user.id)
        subjects = _subjects_for_user(db, user.id) if user else []
    context.user_data["section"] = "subjects"
    await update.effective_message.reply_text(
        "📚 قسم المواد\nاختر مادة أو أضف مادة جديدة.",
        reply_markup=subjects_menu_keyboard([s.name for s in subjects]),
    )


async def begin_add_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["flow"] = "add_subject"
    await update.effective_message.reply_text(
        "اكتب اسم المادة كما تريد أن يظهر كزر مستقل. مثال: Anatomy", reply_markup=nav_keyboard()
    )


async def handle_add_subject(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    name = normalize_text(text)
    if len(name) < 2 or len(name) > 80:
        await update.effective_message.reply_text("اسم المادة غير واضح. اكتب اسمًا بين 2 و80 حرف.")
        return
    with get_session() as db:
        user = _get_current_user(db, update.effective_user.id)
        existing = db.scalar(
            select(Subject).where(Subject.user_id == user.id, func.lower(Subject.name) == name.lower())
        )
        if existing:
            await update.effective_message.reply_text("هذه المادة موجودة مسبقًا.")
            context.user_data.clear()
            await show_subjects_menu(update, context)
            return
        subject = Subject(user_id=user.id, name=name)
        db.add(subject)
        db.commit()
        db.refresh(subject)
    context.user_data.clear()
    await update.effective_message.reply_text(f"✅ تم إنشاء مادة: {name}")
    await show_subjects_menu(update, context)


async def open_subject_by_name(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str) -> None:
    clean = name.replace("📘", "", 1).strip()
    with get_session() as db:
        user = _get_current_user(db, update.effective_user.id)
        subject = db.scalar(select(Subject).where(Subject.user_id == user.id, Subject.name == clean))
        if not subject:
            await update.effective_message.reply_text("المادة غير موجودة. افتح 📚 المواد وشوف القائمة.")
            return
        material_count = (
            db.scalar(
                select(func.count())
                .select_from(Attachment)
                .where(Attachment.subject_id == subject.id, Attachment.kind == "material")
            )
            or 0
        )
        past_count = (
            db.scalar(
                select(func.count())
                .select_from(Attachment)
                .where(Attachment.subject_id == subject.id, Attachment.kind == "past_question")
            )
            or 0
        )
        sid = subject.id
        sname = subject.name
    context.user_data["current_subject_id"] = sid
    context.user_data["current_subject_name"] = sname
    context.user_data["section"] = "subject_detail"
    await update.effective_message.reply_text(
        f"📘 {sname}\n\nملحقات المادة: {material_count}\nأسئلة السنوات: {past_count}\n\nاختر الإجراء:",
        reply_markup=subject_detail_keyboard(sname),
    )


async def begin_upload_current(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str) -> None:
    subject_id = context.user_data.get("current_subject_id")
    subject_name = context.user_data.get("current_subject_name", "المادة")
    if not subject_id:
        await update.effective_message.reply_text("اختر المادة أولًا من زر 📚 المواد.")
        return
    context.user_data["flow"] = "upload_attachment"
    context.user_data["upload_subject_id"] = subject_id
    context.user_data["upload_kind"] = kind
    kind_ar = "ملحقات المادة" if kind == "material" else "أسئلة السنوات"
    await update.effective_message.reply_text(
        f"أرسل الآن ملفات {kind_ar} لـ {subject_name}.\n"
        "أقبل PDF، صور، صوتيات، فيديو، أو نص.\n"
        "عند الانتهاء اضغط ✅ تم الرفع أو 🏠 القائمة الرئيسية.",
        reply_markup=nav_keyboard(),
    )


async def handle_attachment_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    subject_id = context.user_data.get("upload_subject_id")
    kind = context.user_data.get("upload_kind")
    msg = update.effective_message
    if msg.text and msg.text.strip() in ["✅ تم الرفع", "تم", "خلصت"]:
        context.user_data.pop("flow", None)
        await msg.reply_text("✅ تم إنهاء رفع الملفات.")
        await show_subjects_menu(update, context)
        return
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
            att.file_type = "text"
            att.text_content = msg.text
            att.file_name = "text_note.txt"
        else:
            await msg.reply_text("هذا النوع غير مدعوم حاليًا.")
            return
        db.add(att)
        db.commit()
    await msg.reply_text("✅ تم حفظ الملف وربطه بالمادة داخل قاعدة بيانات البوت. أرسل ملفًا آخر أو اضغط ✅ تم الرفع.")


async def list_current_attachments(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str) -> None:
    subject_id = context.user_data.get("current_subject_id")
    if not subject_id:
        await update.effective_message.reply_text("اختر المادة أولًا.")
        return
    with get_session() as db:
        subject = db.get(Subject, subject_id)
        attachments = db.scalars(
            select(Attachment)
            .where(Attachment.subject_id == subject_id, Attachment.kind == kind)
            .order_by(Attachment.uploaded_at.desc())
            .limit(20)
        ).all()
    if not attachments:
        await update.effective_message.reply_text("لا توجد ملفات بعد.")
        return
    await update.effective_message.reply_text(f"آخر الملفات في {subject.name}:")
    for att in attachments:
        caption = f"#{att.id} — {att.file_name or att.file_type}"
        if att.file_type == "document":
            await update.effective_message.reply_document(att.telegram_file_id, caption=caption)
        elif att.file_type == "photo":
            await update.effective_message.reply_photo(att.telegram_file_id, caption=caption)
        elif att.file_type == "audio":
            await update.effective_message.reply_audio(att.telegram_file_id, caption=caption)
        elif att.file_type == "video":
            await update.effective_message.reply_video(att.telegram_file_id, caption=caption)
        else:
            await update.effective_message.reply_text(
                f"{caption}\n{att.text_content[:1000] if att.text_content else ''}"
            )


async def analyze_current_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    subject_id = context.user_data.get("current_subject_id")
    if not subject_id:
        await update.effective_message.reply_text("اختر المادة أولًا.")
        return
    with get_session() as db:
        subject = db.get(Subject, subject_id)
        material_count = (
            db.scalar(
                select(func.count())
                .select_from(Attachment)
                .where(Attachment.subject_id == subject_id, Attachment.kind == "material")
            )
            or 0
        )
        past_count = (
            db.scalar(
                select(func.count())
                .select_from(Attachment)
                .where(Attachment.subject_id == subject_id, Attachment.kind == "past_question")
            )
            or 0
        )
        total_size = (
            db.scalar(
                select(func.coalesce(func.sum(Attachment.file_size), 0)).where(Attachment.subject_id == subject_id)
            )
            or 0
        )
    mb = total_size / (1024 * 1024)
    difficulty = "خفيفة/غير مكتملة"
    if material_count >= 6 or mb > 15:
        difficulty = "عالية"
    elif material_count >= 3 or past_count >= 2:
        difficulty = "متوسطة"
    await update.effective_message.reply_text(
        f"🧠 تحليل سريع للمادة: {subject.name}\n\n"
        f"ملحقات: {material_count}\nأسئلة سنوات: {past_count}\nحجم تقريبي: {mb:.1f} MB\n"
        f"الصعوبة التقديرية: {difficulty}\n\n"
        "التحليل المعمق يحتاج من زر الخطة: عدد الصفحات، نوع الامتحان، مستواك، الأيام، والهدف."
    )
