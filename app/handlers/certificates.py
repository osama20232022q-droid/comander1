from __future__ import annotations

from aiogram import Router, F
from aiogram.types import FSInputFile, Message

from app.db import db, dt_iso
from app.services.report_service import daily_report, weekly_minutes
from app.services.user_service import get_user_profile, upsert_user
from app.utils.certificates import CertificateData, render_certificate
from app.utils.time_utils import week_bounds

router = Router()


@router.message(F.text == '🏅 الشهادات')
async def certificates_home(message: Message) -> None:
    user = await upsert_user(message.from_user)
    profile = await get_user_profile(user['id'])
    start, end = week_bounds()
    minutes = await weekly_minutes(user['id'], start, end)
    total = sum(minutes.values())
    today_report = await daily_report(user['id'], end)
    async with db.connect() as conn:
        subjects = await conn.execute_fetchall(
            '''SELECT DISTINCT s.name FROM lectures l JOIN subjects s ON s.id=l.subject_id
               WHERE s.user_id=? AND l.status='done' LIMIT 8''',
            (user['id'],),
        )
    if total < 60:
        await message.answer('الشهادة تحتاج على الأقل ساعة دراسة مسجلة هذا الأسبوع. شغل البومودورو وسجل جلساتك أولًا.')
        return
    cert_data = CertificateData(
        student_name=profile.get('display_name') or user.get('full_name') or 'Student',
        week_start=start,
        week_end=end,
        study_hours=total / 60,
        sessions=sum(1 for v in minutes.values() if v > 0),
        subjects_done=[r['name'] for r in subjects],
        discipline_score=today_report['discipline_score'],
        daily_minutes=minutes,
    )
    path = render_certificate(cert_data)
    async with db.connect() as conn:
        await conn.execute(
            'INSERT INTO certificates(user_id,week_start,week_end,html_path,created_at) VALUES(?,?,?,?,?)',
            (user['id'], start.isoformat(), end.isoformat(), str(path), dt_iso()),
        )
    await message.answer_document(FSInputFile(path), caption='🏅 شهادة التقدير الأسبوعية بصيغة HTML. افتحها واطبعها PDF إذا تريد.')
    await message.answer('تم فتح خانة تقييم المستوى بعد أول شهادة: استخدم 📊 التقارير لمتابعة Discipline Score ومستوى الالتزام.')
