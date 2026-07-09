from __future__ import annotations

from app.db import db, dt_iso
from app.utils.scoring import classify_excuse


async def record_event(user_id: int, category: str, reason: str, severity: str = 'medium') -> dict:
    label, action = classify_excuse(reason)
    async with db.connect() as conn:
        await conn.execute(
            '''INSERT INTO discipline_events(user_id,event_at,category,severity,reason,action)
               VALUES(?,?,?,?,?,?)''',
            (user_id, dt_iso(), category, severity, reason, action),
        )
    return {'classification': label, 'action': action}


async def pattern_summary(user_id: int, limit: int = 20) -> str:
    async with db.connect() as conn:
        rows = await conn.execute_fetchall(
            'SELECT category, COUNT(*) AS c FROM discipline_events WHERE user_id=? GROUP BY category ORDER BY c DESC LIMIT ?',
            (user_id, limit),
        )
    if not rows:
        return 'لا توجد مخالفات مسجلة بعد.'
    return '\n'.join(f'- {r["category"]}: {r["c"]} مرات' for r in rows)
