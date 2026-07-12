from __future__ import annotations

import json

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import ContextTypes

from app.db import get_session
from app.keyboards import confirm_back_keyboard, nav_keyboard, plan_options_keyboard
from app.models import Attachment, StudyPlan, Subject, User
from app.services.plan_generator import generate_plan_html
from app.services.temp_files import temporary_path
from app.utils import normalize_text


def _current_user(db, tg_id: int) -> User | None:
    return db.scalar(select(User).where(User.telegram_id == tg_id))


def _plan_prompt(step: str) -> tuple[str, list[str] | None]:
    prompts: dict[str, tuple[str, list[str] | None]] = {
        "wake": ("ما وقت استيقاظك المعتاد؟ مثال: 04:30", None),
        "sleep": ("ما وقت نومك الثابت إن وجد؟ مثال: 22:00 أو اكتب غير ثابت", None),
        "subject": ("اختر المادة من لوحة الكيبورد.", None),
        "level": ("مستواك بالمادة؟", ["ضعيف", "متوسط", "جيد", "ممتاز"]),
        "target": ("شنو التقدير الذي تريده؟", ["مقبول", "متوسط", "جيد", "جيد جدًا", "امتياز"]),
        "exam_type": ("نوع الامتحان؟", ["يومي", "Mid", "End Module", "شهري", "Final"]),
        "question_type": ("نمط الأسئلة؟", ["MCQ", "Short essay", "عملي", "شفوي", "مختلط"]),
        "grade_out": ("الامتحان من كم درجة؟ مثال: 5، 10، 50، 100", None),
        "pages_count": ("كم صفحة/محاضرة تقريبًا في هذه المادة؟ اكتب رقمًا. إذا لا تعرف اكتب 0.", None),
        "days_left": ("كم يوم متبقي للامتحان؟ اكتب رقم فقط. مثال: 12", None),
        "other_materials": ("هل توجد مواد أخرى بنفس الفترة؟ اكتب نعم/لا، وإذا نعم اذكرها باختصار.", None),
    }
    return prompts.get(step, ("أكمل الإجابة.", None))


async def start_plan_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        user = _current_user(db, update.effective_user.id)
        subjects = (
            db.scalars(select(Subject).where(Subject.user_id == user.id).order_by(Subject.name)).all() if user else []
        )
    if not subjects:
        await update.effective_message.reply_text("لا توجد مواد. أضف مادة أولًا من زر 📚 المواد.")
        return
    context.user_data.clear()
    context.user_data["flow"] = "study_plan"
    context.user_data["step"] = "wake"
    context.user_data["plan"] = {}
    await update.effective_message.reply_text(
        "🧠 الخطة الدراسية المعمقة\nهذه النسخة تعتمد على الصفحات، الملفات، أسئلة السنوات، هدفك، ونوع الامتحان.",
        reply_markup=nav_keyboard(),
    )
    await update.effective_message.reply_text("ما وقت استيقاظك المعتاد؟ مثال: 04:30")


async def handle_plan_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    step = context.user_data.get("step")
    draft = context.user_data.setdefault("plan", {})
    msg = update.effective_message

    if text in ["↩️ خطوة للوراء", "🔴 رجوع للتعديل"]:
        await _plan_back(update, context)
        return
    if text == "🔵 تأكيد" and step == "review":
        await generate_plan(update, context)
        return

    if step == "wake":
        draft["wake_time"] = normalize_text(text)
        await _advance(update, context, "sleep")
    elif step == "sleep":
        draft["sleep_time"] = normalize_text(text)
        await _advance(update, context, "subject")
    elif step == "subject":
        clean = text.replace("📘", "", 1).strip()
        with get_session() as db:
            user = _current_user(db, update.effective_user.id)
            subject = db.scalar(select(Subject).where(Subject.user_id == user.id, Subject.name == clean))
        if not subject:
            await msg.reply_text("اختر مادة من القائمة الظاهرة فقط.")
            await _advance(update, context, "subject")
            return
        draft["subject_id"] = subject.id
        await _advance(update, context, "level")
    elif step in ["level", "target", "exam_type", "question_type"]:
        key = {"level": "level", "target": "target", "exam_type": "exam_type", "question_type": "question_type"}[step]
        valid = _plan_prompt(step)[1] or []
        if text not in valid:
            await msg.reply_text("اختر من الأزرار فقط.")
            await _advance(update, context, step)
            return
        draft[key] = text
        next_step = {
            "level": "target",
            "target": "exam_type",
            "exam_type": "question_type",
            "question_type": "grade_out",
        }[step]
        await _advance(update, context, next_step)
    elif step == "grade_out":
        draft["grade_out"] = normalize_text(text)
        await _advance(update, context, "pages_count")
    elif step == "pages_count":
        if not text.strip().isdigit():
            await msg.reply_text("اكتب رقمًا فقط. إذا لا تعرف اكتب 0.")
            return
        draft["pages_count"] = int(text.strip())
        await _advance(update, context, "days_left")
    elif step == "days_left":
        if not text.strip().isdigit() or int(text.strip()) <= 0:
            await msg.reply_text("اكتب عدد الأيام كرقم صحيح. مثال: 10")
            return
        draft["days_left"] = int(text.strip())
        await _advance(update, context, "other_materials")
    elif step == "other_materials":
        draft["other_materials"] = normalize_text(text)
        await confirm_plan(update, context)
    elif step == "review":
        await msg.reply_text("اضغط 🔵 تأكيد أو 🔴 رجوع للتعديل.", reply_markup=confirm_back_keyboard())


async def _advance(update: Update, context: ContextTypes.DEFAULT_TYPE, step: str) -> None:
    context.user_data["step"] = step
    prompt, values = _plan_prompt(step)
    if step == "subject":
        with get_session() as db:
            user = _current_user(db, update.effective_user.id)
            subjects = db.scalars(select(Subject).where(Subject.user_id == user.id).order_by(Subject.name)).all()
        await update.effective_message.reply_text(
            prompt, reply_markup=plan_options_keyboard([f"📘 {s.name}" for s in subjects])
        )
    elif values:
        await update.effective_message.reply_text(prompt, reply_markup=plan_options_keyboard(values))
    else:
        await update.effective_message.reply_text(prompt, reply_markup=nav_keyboard())


async def _plan_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    order = [
        "wake",
        "sleep",
        "subject",
        "level",
        "target",
        "exam_type",
        "question_type",
        "grade_out",
        "pages_count",
        "days_left",
        "other_materials",
        "review",
    ]
    step = context.user_data.get("step")
    if step in order and order.index(step) > 0:
        await _advance(update, context, order[order.index(step) - 1])
    else:
        await _advance(update, context, "wake")


async def confirm_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = context.user_data.get("plan", {})
    with get_session() as db:
        subject = db.get(Subject, d.get("subject_id"))
    context.user_data["step"] = "review"
    text = (
        "راجع بيانات الخطة:\n\n"
        f"المادة: {subject.name if subject else 'غير محددة'}\n"
        f"الاستيقاظ: {d.get('wake_time')}\n"
        f"النوم: {d.get('sleep_time')}\n"
        f"المستوى: {d.get('level')}\n"
        f"الهدف: {d.get('target')}\n"
        f"نوع الامتحان: {d.get('exam_type')}\n"
        f"نمط الأسئلة: {d.get('question_type')}\n"
        f"الدرجة: {d.get('grade_out')}\n"
        f"الصفحات/المحاضرات: {d.get('pages_count')}\n"
        f"الأيام: {d.get('days_left')}\n"
        f"مواد أخرى: {d.get('other_materials')}\n\n"
        "اضغط 🔵 تأكيد لتوليد ملف الخطة."
    )
    await update.effective_message.reply_text(text, reply_markup=confirm_back_keyboard())


async def generate_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("⏳ جاري توليد الخطة المعمقة... انتظر لحظات.")
    d = context.user_data.get("plan", {})
    with get_session() as db:
        user = _current_user(db, update.effective_user.id)
        subject = db.get(Subject, d["subject_id"])
        mat_count = (
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
        mat_size = (
            db.scalar(
                select(func.coalesce(func.sum(Attachment.file_size), 0)).where(
                    Attachment.subject_id == subject.id, Attachment.kind == "material"
                )
            )
            or 0
        )
        past_size = (
            db.scalar(
                select(func.coalesce(func.sum(Attachment.file_size), 0)).where(
                    Attachment.subject_id == subject.id, Attachment.kind == "past_question"
                )
            )
            or 0
        )
        html = generate_plan_html(
            user.profile, subject, d, {"count": mat_count, "size": mat_size}, {"count": past_count, "size": past_size}
        )
        plan = StudyPlan(
            user_id=user.id,
            subject_id=subject.id,
            title=f"خطة {subject.name}",
            request_json=json.dumps(d, ensure_ascii=False),
            html_content=html,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        plan_id = plan.id
        subject_name = subject.name
    with temporary_path(suffix=".html", prefix=f"study_plan_{plan_id}_") as tmp:
        tmp.write_text(html, encoding="utf-8")
        with tmp.open("rb") as fh:
            await update.effective_message.reply_document(
                document=fh,
                filename=f"study_plan_{subject_name}_{plan_id}.html",
                caption="✅ تم توليد الخطة الدراسية المعمقة.",
            )
    context.user_data.clear()


# compatibility placeholder
async def handle_plan_callback(update, context, data):
    await update.callback_query.answer("هذه النسخة تستخدم أزرار لوحة الكيبورد فقط.", show_alert=True)
