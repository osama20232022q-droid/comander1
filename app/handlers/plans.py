from __future__ import annotations

import json
import tempfile
from pathlib import Path
from sqlalchemy import select, func
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.db import get_session
from app.models import User, Subject, Attachment, StudyPlan
from app.keyboards import plan_choice_keyboard, nav_keyboard
from app.services.plan_generator import generate_plan_html
from app.utils import normalize_text


def _current_user(db, tg_id: int) -> User | None:
    return db.scalar(select(User).where(User.telegram_id == tg_id))


async def start_plan_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        user = _current_user(db, update.effective_user.id)
        subjects = db.scalars(select(Subject).where(Subject.user_id == user.id).order_by(Subject.name)).all() if user else []
    if not subjects:
        await update.effective_message.reply_text("لا توجد مواد. أضف مادة أولًا من زر 📚 المواد.")
        return
    context.user_data["flow"] = "study_plan"
    context.user_data["step"] = "wake"
    context.user_data["plan"] = {}
    await update.effective_message.reply_text("🧠 الخطة الدراسية المعمقة\n\nما وقت استيقاظك المعتاد؟ مثال: 04:30", reply_markup=nav_keyboard())


async def handle_plan_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    step = context.user_data.get("step")
    draft = context.user_data.setdefault("plan", {})
    msg = update.effective_message

    if text in ["↩️ خطوة للوراء", "رجوع"]:
        await msg.reply_text("رجوع خطوة. أكمل من السؤال السابق أو اضغط القائمة الرئيسية.")
        return

    if step == "wake":
        draft["wake_time"] = normalize_text(text)
        context.user_data["step"] = "sleep"
        await msg.reply_text("ما وقت نومك الثابت إن وجد؟ مثال: 22:00 أو اكتب غير ثابت")
        return
    if step == "sleep":
        draft["sleep_time"] = normalize_text(text)
        context.user_data["step"] = "subject"
        with get_session() as db:
            user = _current_user(db, update.effective_user.id)
            subjects = db.scalars(select(Subject).where(Subject.user_id == user.id).order_by(Subject.name)).all()
        rows = [[InlineKeyboardButton(s.name, callback_data=f"plan:subject:{s.id}")] for s in subjects]
        rows.append([InlineKeyboardButton("🔴 رجوع", callback_data="plan:back")])
        await msg.reply_text("اختر المادة:", reply_markup=InlineKeyboardMarkup(rows))
        return
    if step == "grade_out":
        draft["grade_out"] = normalize_text(text)
        context.user_data["step"] = "days_left"
        await msg.reply_text("كم يوم متبقي للامتحان؟ اكتب رقم فقط. مثال: 12")
        return
    if step == "days_left":
        if not text.strip().isdigit() or int(text.strip()) <= 0:
            await msg.reply_text("اكتب عدد الأيام كرقم صحيح. مثال: 10")
            return
        draft["days_left"] = int(text.strip())
        context.user_data["step"] = "other_materials"
        await msg.reply_text("هل توجد مواد أخرى بنفس الفترة؟ اكتب نعم/لا، وإذا نعم اذكرها باختصار.")
        return
    if step == "other_materials":
        draft["other_materials"] = normalize_text(text)
        await confirm_plan(update, context)
        return


async def handle_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    q = update.callback_query
    await q.answer()
    draft = context.user_data.setdefault("plan", {})
    if data.startswith("plan:subject:"):
        draft["subject_id"] = int(data.split(":")[-1])
        context.user_data["step"] = "level"
        await q.message.reply_text("مستواك بالمادة؟", reply_markup=plan_choice_keyboard("plan:level", ["ضعيف", "متوسط", "جيد", "ممتاز"]))
    elif data.startswith("plan:level:"):
        draft["level"] = data.split(":", 2)[2]
        context.user_data["step"] = "target"
        await q.message.reply_text("شنو التقدير الذي تريده؟", reply_markup=plan_choice_keyboard("plan:target", ["مقبول", "متوسط", "جيد", "جيد جدًا", "امتياز"]))
    elif data.startswith("plan:target:"):
        draft["target"] = data.split(":", 2)[2]
        context.user_data["step"] = "exam_type"
        await q.message.reply_text("نوع الامتحان؟", reply_markup=plan_choice_keyboard("plan:exam", ["يومي", "Mid", "End Module", "شهري", "Final"]))
    elif data.startswith("plan:exam:"):
        draft["exam_type"] = data.split(":", 2)[2]
        context.user_data["step"] = "question_type"
        await q.message.reply_text("نمط الأسئلة؟", reply_markup=plan_choice_keyboard("plan:qtype", ["MCQ", "Short essay", "عملي", "شفوي", "مختلط"]))
    elif data.startswith("plan:qtype:"):
        draft["question_type"] = data.split(":", 2)[2]
        context.user_data["step"] = "grade_out"
        await q.message.reply_text("الامتحان من كم درجة؟ مثال: 5، 10، 50، 100")
    elif data == "plan:generate":
        await generate_plan(update, context)
    elif data == "plan:back":
        await q.message.reply_text("استخدم زر 🏠 القائمة الرئيسية أو أعد بدء الخطة من جديد.")


async def confirm_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = context.user_data.get("plan", {})
    with get_session() as db:
        subject = db.get(Subject, d.get("subject_id"))
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
        f"الأيام: {d.get('days_left')}\n"
        f"مواد أخرى: {d.get('other_materials')}\n\n"
        "اضغط توليد الخطة لبدء التحليل."
    )
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 توليد الخطة", callback_data="plan:generate")],
        [InlineKeyboardButton("🔴 رجوع للتعديل", callback_data="plan:back")],
    ]))


async def generate_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("⏳ جاري توليد الخطة المعمقة... انتظر لحظات.")
    d = context.user_data.get("plan", {})
    with get_session() as db:
        user = _current_user(db, q.from_user.id)
        subject = db.get(Subject, d["subject_id"])
        material_count = db.scalar(select(func.count()).select_from(Attachment).where(Attachment.subject_id == subject.id, Attachment.kind == "material")) or 0
        past_count = db.scalar(select(func.count()).select_from(Attachment).where(Attachment.subject_id == subject.id, Attachment.kind == "past_question")) or 0
        html = generate_plan_html(user.profile, subject, d, material_count, past_count)
        plan = StudyPlan(user_id=user.id, subject_id=subject.id, title=f"خطة {subject.name}", request_json=json.dumps(d, ensure_ascii=False), html_content=html)
        db.add(plan)
        db.commit()
        db.refresh(plan)
    tmp = Path(tempfile.gettempdir()) / f"study_plan_{plan.id}.html"
    tmp.write_text(html, encoding="utf-8")
    await q.message.reply_document(document=tmp.open("rb"), filename=f"study_plan_{subject.name}_{plan.id}.html", caption="✅ تم توليد الخطة الدراسية المعمقة.")
    context.user_data.clear()
