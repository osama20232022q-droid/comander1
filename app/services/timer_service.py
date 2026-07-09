from __future__ import annotations

from datetime import timedelta

from app.db import db, dt_iso
from app.utils.time_utils import now, minutes_between


async def start_timer(user_id: int, focus_minutes: int, break_minutes: int, kind: str = 'focus') -> int:
    started = now()
    end_at = started + timedelta(minutes=focus_minutes if kind == 'focus' else break_minutes)
    async with db.connect() as conn:
        await conn.execute('DELETE FROM active_timers WHERE user_id=?', (user_id,))
        cur = await conn.execute(
            '''INSERT INTO active_timers(user_id,kind,focus_minutes,break_minutes,started_at,end_at)
               VALUES(?,?,?,?,?,?)''',
            (user_id, kind, focus_minutes, break_minutes, dt_iso(started), dt_iso(end_at)),
        )
        return int(cur.lastrowid)


async def get_active_timer(user_id: int) -> dict | None:
    async with db.connect() as conn:
        rows = await conn.execute_fetchall('SELECT * FROM active_timers WHERE user_id=? ORDER BY id DESC LIMIT 1', (user_id,))
        return dict(rows[0]) if rows else None


async def finish_timer(user_id: int, status_note: str = 'ok') -> int | None:
    timer = await get_active_timer(user_id)
    if not timer:
        return None
    duration = minutes_between(timer['started_at'])
    async with db.connect() as conn:
        cur = await conn.execute(
            '''INSERT INTO sessions(user_id,session_type,started_at,ended_at,duration_minutes,notes,created_at)
               VALUES(?,?,?,?,?,?,?)''',
            (user_id, timer['kind'], timer['started_at'], dt_iso(), duration, status_note, dt_iso()),
        )
        await conn.execute('DELETE FROM active_timers WHERE id=?', (timer['id'],))
        return int(cur.lastrowid)


async def due_timers() -> list[dict]:
    async with db.connect() as conn:
        rows = await conn.execute_fetchall(
            '''SELECT t.*, u.tg_id FROM active_timers t JOIN users u ON u.id=t.user_id
               WHERE t.notified=0 AND t.end_at <= ? AND u.is_blocked=0''',
            (dt_iso(),),
        )
        return [dict(r) for r in rows]


async def mark_timer_notified(timer_id: int) -> None:
    async with db.connect() as conn:
        await conn.execute('UPDATE active_timers SET notified=1 WHERE id=?', (timer_id,))


async def record_focus_score(session_id: int, score: int) -> None:
    async with db.connect() as conn:
        await conn.execute('UPDATE sessions SET focus_score=? WHERE id=?', (score, session_id))
