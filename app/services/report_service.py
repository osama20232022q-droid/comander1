from __future__ import annotations

from datetime import date, timedelta

from app.db import db, dt_iso, dumps
from app.utils.scoring import discipline_score


async def daily_report(user_id: int, target_date: date) -> dict:
    prefix = target_date.isoformat()
    async with db.connect() as conn:
        sessions = await conn.execute_fetchall(
            'SELECT * FROM sessions WHERE user_id=? AND started_at LIKE ?',
            (user_id, f'{prefix}%'),
        )
        tasks = await conn.execute_fetchall(
            'SELECT * FROM tasks WHERE user_id=? AND created_at LIKE ?',
            (user_id, f'{prefix}%'),
        )
        phone_events = await conn.execute_fetchall(
            'SELECT * FROM discipline_events WHERE user_id=? AND event_at LIKE ? AND category="phone"',
            (user_id, f'{prefix}%'),
        )
    study_minutes = sum(int(r['duration_minutes']) for r in sessions if r['session_type'] in ('focus', 'study'))
    planned_minutes = sum(60 for _ in tasks) or max(study_minutes, 240)
    missed = sum(1 for r in tasks if r['status'] == 'missed')
    score = discipline_score(planned_minutes, study_minutes, len(phone_events), missed)
    return {
        'study_minutes': study_minutes,
        'planned_minutes': planned_minutes,
        'sessions': len(sessions),
        'tasks': len(tasks),
        'phone_events': len(phone_events),
        'discipline_score': score,
    }


async def save_daily_report(user_id: int, target_date: date, summary: str = '', delays: list[dict] | None = None) -> dict:
    data = await daily_report(user_id, target_date)
    async with db.connect() as conn:
        await conn.execute(
            '''INSERT INTO reports(user_id,report_date,study_minutes,planned_minutes,discipline_score,summary,delays_json,created_at)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(user_id,report_date) DO UPDATE SET
               study_minutes=excluded.study_minutes, planned_minutes=excluded.planned_minutes,
               discipline_score=excluded.discipline_score, summary=excluded.summary, delays_json=excluded.delays_json''',
            (user_id, target_date.isoformat(), data['study_minutes'], data['planned_minutes'], data['discipline_score'], summary, dumps(delays or []), dt_iso()),
        )
    return data


async def weekly_minutes(user_id: int, start: date, end: date) -> dict[str, int]:
    result: dict[str, int] = {}
    async with db.connect() as conn:
        d = start
        while d <= end:
            prefix = d.isoformat()
            rows = await conn.execute_fetchall(
                'SELECT COALESCE(SUM(duration_minutes),0) AS m FROM sessions WHERE user_id=? AND started_at LIKE ?',
                (user_id, f'{prefix}%'),
            )
            result[prefix] = int(rows[0]['m'] or 0)
            d += timedelta(days=1)
    return result
