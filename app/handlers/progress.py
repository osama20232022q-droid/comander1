from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from telegram import Update
from telegram.ext import ContextTypes
from app.db import get_session
from app.models import User, Subject, Attachment, PomodoroSession, FoodLog, StudyPlan, Certificate


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        if not user:
            return
        subjects = db.scalar(select(func.count()).select_from(Subject).where(Subject.user_id == user.id)) or 0
        files = db.scalar(select(func.count()).select_from(Attachment).where(Attachment.user_id == user.id)) or 0
        sessions = db.scalars(select(PomodoroSession).where(PomodoroSession.user_id == user.id, PomodoroSession.status == "finished")).all()
        hours = sum(s.study_minutes for s in sessions) / 60
        plans = db.scalar(select(func.count()).select_from(StudyPlan).where(StudyPlan.user_id == user.id)) or 0
        certs = db.scalar(select(func.count()).select_from(Certificate).where(Certificate.user_id == user.id)) or 0
        foods = db.scalar(select(func.count()).select_from(FoodLog).where(FoodLog.user_id == user.id)) or 0
    score = min(100, int(hours * 4 + subjects * 5 + plans * 8 + certs * 5))
    await update.effective_message.reply_text(
        "📊 تقرير تقدمك\n\n"
        f"المواد: {subjects}\n"
        f"الملفات/الملحقات: {files}\n"
        f"جلسات الدراسة المنجزة: {len(sessions)}\n"
        f"الساعات الصافية: {hours:.1f}\n"
        f"الخطط الدراسية: {plans}\n"
        f"سجلات الأكل داخل البومودورو: {foods}\n"
        f"الشهادات: {certs}\n"
        f"Discipline Score تقريبي: {score}/100"
    )


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        profile = user.profile if user else None
    if not profile:
        await update.effective_message.reply_text("لا يوجد ملف طالب مؤكد بعد.")
        return
    await update.effective_message.reply_text(
        "👤 ملفي\n\n"
        f"الاسم: {profile.full_name}\n"
        f"الكلية: {profile.college}\n"
        f"تحليل التخصص: {profile.specialty}\n"
        f"المرحلة: {profile.stage}\n"
        f"العمر: {profile.age or 'غير مضاف'}\n"
        f"الطول: {profile.height_cm or 'غير مضاف'}\n"
        f"الوزن: {profile.weight_kg or 'غير مضاف'}\n"
        f"الحالة: {'مفعل' if user.is_active else 'بانتظار التفعيل'}"
    )
