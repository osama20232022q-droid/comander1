from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import ContextTypes

from app.db import get_session
from app.keyboards import certificate_keyboard
from app.models import Certificate, PomodoroSession, Subject, User
from app.services.certificate import certificate_html
from app.services.temp_files import temporary_path


def _start_of_day_utc(days_ago: int = 0):
    now = datetime.now(UTC)
    return datetime(now.year, now.month, now.day, tzinfo=UTC) - timedelta(days=days_ago)


def _hours(sessions):
    return sum(s.study_minutes for s in sessions) / 60


async def show_certificates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "🏅 الشهادات\nالشهادة لا تُمنح بالضغط فقط؛ تُمنح عند تحقق شرط إنجاز واضح.",
        reply_markup=certificate_keyboard(),
    )


async def handle_certificate_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    if text == "📋 شروط الشهادة":
        await update.effective_message.reply_text(
            "<b>شروط الحصول على شهادة:</b>\n\n"
            "<b>1) شهادة يوم مميز:</b>\n"
            "- تنجز 3 ساعات دراسة صافية على الأقل خلال اليوم.\n"
            "- أو يكون يومك أقوى من متوسط آخر 7 أيام بنسبة واضحة.\n\n"
            "<b>2) شهادة أسبوعية:</b>\n"
            "- 5 أيام دراسة فعّالة خلال آخر 7 أيام.\n"
            "- و10 ساعات صافية على الأقل.\n"
            "- أو 20 جلسة بومودورو منجزة.\n\n"
            "الشهادة تحتوي توقيع البوت بالحروف الإنكليزية وليس ختمًا دائريًا.",
            parse_mode="HTML",
            reply_markup=certificate_keyboard(),
        )
        return True
    if text == "🏅 طلب شهادة يوم مميز":
        await create_certificate_if_earned(update, "daily")
        return True
    if text == "🎖️ طلب شهادة أسبوعية":
        await create_certificate_if_earned(update, "weekly")
        return True
    if text == "📜 آخر شهاداتي":
        await list_certificates(update)
        return True
    return False


async def create_certificate_if_earned(update: Update, cert_type: str) -> None:
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        subjects_count = db.scalar(select(func.count()).select_from(Subject).where(Subject.user_id == user.id)) or 0
        if cert_type == "daily":
            start = _start_of_day_utc(0)
            sessions = db.scalars(
                select(PomodoroSession).where(
                    PomodoroSession.user_id == user.id,
                    PomodoroSession.status == "finished",
                    PomodoroSession.ended_at >= start,
                )
            ).all()
            today_hours = _hours(sessions)
            prev_start = _start_of_day_utc(7)
            prev_sessions = db.scalars(
                select(PomodoroSession).where(
                    PomodoroSession.user_id == user.id,
                    PomodoroSession.status == "finished",
                    PomodoroSession.ended_at >= prev_start,
                    PomodoroSession.ended_at < start,
                )
            ).all()
            avg = (_hours(prev_sessions) / 7) if prev_sessions else 0
            earned = today_hours >= 3 or (today_hours >= 2 and avg > 0 and today_hours >= avg * 1.25)
            if not earned:
                await update.effective_message.reply_text(
                    f"لم تستحق شهادة اليوم بعد. ساعات اليوم: {today_hours:.1f}h. المطلوب: 3h على الأقل أو يوم أقوى من متوسطك.",
                    reply_markup=certificate_keyboard(),
                )
                return
            hours = today_hours
            reason = "لإنجازه يومًا دراسيًا مميزًا بساعات صافية أعلى من الحد المطلوب."
        else:
            start = _start_of_day_utc(7)
            sessions = db.scalars(
                select(PomodoroSession).where(
                    PomodoroSession.user_id == user.id,
                    PomodoroSession.status == "finished",
                    PomodoroSession.ended_at >= start,
                )
            ).all()
            hours = _hours(sessions)
            active_days = len(set((s.ended_at.date() if s.ended_at else s.started_at.date()) for s in sessions))
            earned = (active_days >= 5 and hours >= 10) or len(sessions) >= 20
            if not earned:
                await update.effective_message.reply_text(
                    f"لم تستحق الشهادة الأسبوعية بعد. آخر 7 أيام: {hours:.1f}h / أيام فعالة: {active_days} / جلسات: {len(sessions)}.",
                    reply_markup=certificate_keyboard(),
                )
                return
            reason = "لإكماله أسبوعًا دراسيًا فعّالًا بتحقيق ساعات وجلسات انضباط واضحة."
        score = min(100, int(hours * 6 + len(sessions) * 2 + subjects_count * 4))
        html = certificate_html(
            user.profile.full_name if user.profile else user.first_name or "طالب",
            cert_type,
            hours,
            len(sessions),
            subjects_count,
            score,
            reason,
        )
        cert = Certificate(
            user_id=user.id,
            title="شهادة يوم مميز" if cert_type == "daily" else "شهادة أسبوعية",
            html_content=html,
            hours=hours,
            score=score,
        )
        db.add(cert)
        db.commit()
        db.refresh(cert)
    with temporary_path(suffix=".html", prefix=f"certificate_{cert.id}_") as tmp:
        tmp.write_text(html, encoding="utf-8")
        with tmp.open("rb") as fh:
            await update.effective_message.reply_document(
                fh,
                filename=f"certificate_{cert.id}.html",
                caption="✅ تم منح الشهادة لأن الشرط تحقق.",
                reply_markup=certificate_keyboard(),
            )


async def list_certificates(update: Update) -> None:
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        certs = db.scalars(
            select(Certificate).where(Certificate.user_id == user.id).order_by(Certificate.created_at.desc()).limit(5)
        ).all()
    if not certs:
        await update.effective_message.reply_text("لا توجد شهادات بعد.", reply_markup=certificate_keyboard())
        return
    for cert in certs:
        with temporary_path(suffix=".html", prefix=f"certificate_{cert.id}_") as tmp:
            tmp.write_text(cert.html_content, encoding="utf-8")
            with tmp.open("rb") as fh:
                await update.effective_message.reply_document(
                    fh,
                    filename=f"certificate_{cert.id}.html",
                    caption=f"{cert.title} — {cert.hours:.1f}h — Score {cert.score}",
                )


# compatibility
async def handle_cert_callback(update, context, data):
    await update.callback_query.answer("هذه النسخة تستخدم أزرار لوحة الكيبورد فقط.", show_alert=True)
