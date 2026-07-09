from __future__ import annotations

import tempfile
from pathlib import Path
from sqlalchemy import select, func
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.db import get_session
from app.models import User, Subject, PomodoroSession, Certificate
from app.services.certificate import certificate_html


async def show_certificates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "🏅 الشهادات\nاختر إنشاء شهادة جديدة أو عرض آخر شهاداتك.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏅 إنشاء شهادة أسبوعية", callback_data="cert:create")],
            [InlineKeyboardButton("📜 آخر شهاداتي", callback_data="cert:list")],
        ])
    )


async def handle_cert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    q = update.callback_query
    await q.answer()
    if data == "cert:create":
        await create_certificate(update, context)
    elif data == "cert:list":
        await list_certificates(update, context)


async def create_certificate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == q.from_user.id))
        sessions = db.scalars(select(PomodoroSession).where(PomodoroSession.user_id == user.id, PomodoroSession.status == "finished")).all()
        hours = sum(s.study_minutes for s in sessions) / 60
        subjects_count = db.scalar(select(func.count()).select_from(Subject).where(Subject.user_id == user.id)) or 0
        score = min(100, int(hours * 4 + subjects_count * 5 + len(sessions)))
        html = certificate_html(user.profile.full_name if user.profile else user.first_name or "طالب", hours, len(sessions), subjects_count, score)
        cert = Certificate(user_id=user.id, title="شهادة تقدير أسبوعية", html_content=html, hours=hours, score=score)
        db.add(cert)
        db.commit()
        db.refresh(cert)
    tmp = Path(tempfile.gettempdir()) / f"certificate_{cert.id}.html"
    tmp.write_text(html, encoding="utf-8")
    await q.message.reply_document(tmp.open("rb"), filename=f"certificate_{cert.id}.html", caption="✅ شهادة تقدير بتصميم رسمي.")


async def list_certificates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == q.from_user.id))
        certs = db.scalars(select(Certificate).where(Certificate.user_id == user.id).order_by(Certificate.created_at.desc()).limit(5)).all()
    if not certs:
        await q.message.reply_text("لا توجد شهادات بعد.")
        return
    for cert in certs:
        tmp = Path(tempfile.gettempdir()) / f"certificate_{cert.id}.html"
        tmp.write_text(cert.html_content, encoding="utf-8")
        await q.message.reply_document(tmp.open("rb"), filename=f"certificate_{cert.id}.html", caption=f"{cert.title} — {cert.hours:.1f}h — Score {cert.score}")
