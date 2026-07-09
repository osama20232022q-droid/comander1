from __future__ import annotations

from datetime import date, datetime, timedelta

from app.db import db, dt_iso
from app.utils.time_utils import human_minutes


def _level_multiplier(level: str) -> float:
    return {'ضعيف': 1.35, 'متوسط': 1.15, 'جيد': 1.0, 'قوي': 0.8}.get(level, 1.15)


async def plan_overview(user_id: int) -> str:
    async with db.connect() as conn:
        subjects = await conn.execute_fetchall('SELECT * FROM subjects WHERE user_id=?', (user_id,))
        lectures = await conn.execute_fetchall(
            '''SELECT l.*, s.name AS subject_name, s.level, s.exam_date FROM lectures l
               JOIN subjects s ON s.id=l.subject_id WHERE s.user_id=? AND l.status!='done' ''',
            (user_id,),
        )
    if not subjects:
        return 'لا توجد مواد بعد. أضف المواد أولًا.'
    if not lectures:
        return 'لا توجد ملازم غير منجزة. أضف ملازم أو ارفع PDF للتحليل.'

    today = date.today()
    total_minutes = 0
    lines = ['🧠 تحليل واقعي للخطة الحالية:']
    by_subject: dict[str, int] = {}
    nearest_exam_days = None
    for lec in lectures:
        minutes = int(lec['estimated_minutes'] or 60) * _level_multiplier(lec['level'])
        total_minutes += int(minutes)
        by_subject[lec['subject_name']] = by_subject.get(lec['subject_name'], 0) + int(minutes)
        if lec['exam_date']:
            try:
                days = max(1, (date.fromisoformat(lec['exam_date']) - today).days)
                nearest_exam_days = days if nearest_exam_days is None else min(nearest_exam_days, days)
            except ValueError:
                pass
    days = nearest_exam_days or 30
    daily_need = int(total_minutes / max(1, days) * 1.25)  # مراجعات وتعويض
    lines.append(f'المتبقي التقريبي: {human_minutes(total_minutes)} صافي.')
    lines.append(f'أقرب امتحان/مدة افتراضية: {days} يوم.')
    lines.append(f'المطلوب يوميًا مع هامش مراجعة: {human_minutes(daily_need)}.')
    lines.append('تفصيل المواد:')
    for subject, minutes in sorted(by_subject.items(), key=lambda x: x[1], reverse=True):
        lines.append(f'- {subject}: {human_minutes(minutes)}')
    if daily_need > 420:
        lines.append('⚠️ الخطة ثقيلة. تحتاج تقليل الهاتف + جلسات صباحية + مراجعات ذكية، وليس قراءة مثالية.')
    elif daily_need < 240:
        lines.append('✅ الخطة ممكنة بشرط لا توجد أيام صفر.')
    else:
        lines.append('🟡 الخطة ممكنة لكن تحتاج ثبات يومي.')
    return '\n'.join(lines)


async def create_today_tasks(user_id: int, available_minutes: int = 300) -> list[dict]:
    async with db.connect() as conn:
        lectures = await conn.execute_fetchall(
            '''SELECT l.*, s.name AS subject_name FROM lectures l
               JOIN subjects s ON s.id=l.subject_id WHERE s.user_id=? AND l.status!='done'
               ORDER BY s.exam_date IS NULL, s.exam_date ASC, l.estimated_minutes DESC LIMIT 6''',
            (user_id,),
        )
        tasks = []
        start = datetime.now().replace(second=0, microsecond=0)
        remaining = available_minutes
        for lec in lectures:
            if remaining <= 0:
                break
            minutes = min(int(lec['estimated_minutes'] or 60), remaining, 90)
            end = start + timedelta(minutes=minutes)
            title = f"{lec['subject_name']} - {lec['title']} ({human_minutes(minutes)})"
            cur = await conn.execute(
                '''INSERT INTO tasks(user_id,subject_id,lecture_id,title,planned_start,planned_end,created_at)
                   VALUES(?,?,?,?,?,?,?)''',
                (user_id, lec['subject_id'], lec['id'], title, dt_iso(start), dt_iso(end), dt_iso()),
            )
            task = {'id': cur.lastrowid, 'title': title, 'start': start.strftime('%H:%M'), 'end': end.strftime('%H:%M')}
            tasks.append(task)
            start = end + timedelta(minutes=15)
            remaining -= minutes
        return tasks


async def rescue_plan(user_id: int, remaining_minutes: int, energy: str = 'متوسط') -> str:
    async with db.connect() as conn:
        lectures = await conn.execute_fetchall(
            '''SELECT l.*, s.name AS subject_name FROM lectures l
               JOIN subjects s ON s.id=l.subject_id WHERE s.user_id=? AND l.status!='done'
               ORDER BY l.estimated_minutes ASC LIMIT 4''',
            (user_id,),
        )
    if not lectures:
        return 'لا توجد ملازم متبقية. نفذ مراجعة MCQ 45 دقيقة.'
    block = 45 if energy in ('تعبان', 'ضعيف') else 60
    possible = max(1, remaining_minutes // (block + 10))
    lines = ['🚨 خطة إنقاذ اليوم:', 'نلغي الخطة المثالية. ننفذ المهم فقط.']
    for lec in lectures[:possible]:
        lines.append(f'- {block}د: {lec["subject_name"]} / {lec["title"]} — قراءة فخاخ + MCQ')
    lines.append('- 10د: تقرير صريح: أين ضاع الوقت؟')
    return '\n'.join(lines)
