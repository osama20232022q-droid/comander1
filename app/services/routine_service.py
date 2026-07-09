from __future__ import annotations

from datetime import date, timedelta

from app.db import db, dt_iso


async def start_routine_trial(user_id: int, name: str, sleep_time: str, wake_time: str, days: int = 7, goal: str = '') -> int:
    start = date.today()
    end = start + timedelta(days=days - 1)
    async with db.connect() as conn:
        await conn.execute('UPDATE routine_experiments SET status="finished" WHERE user_id=? AND status="active"', (user_id,))
        cur = await conn.execute(
            '''INSERT INTO routine_experiments(user_id,name,start_date,end_date,sleep_time,wake_time,goal,created_at)
               VALUES(?,?,?,?,?,?,?,?)''',
            (user_id, name, start.isoformat(), end.isoformat(), sleep_time, wake_time, goal, dt_iso()),
        )
        await conn.execute(
            'UPDATE profiles SET sleep_time=?, wake_time=?, updated_at=? WHERE user_id=?',
            (sleep_time, wake_time, dt_iso(), user_id),
        )
        return int(cur.lastrowid)


async def active_trial(user_id: int) -> dict | None:
    async with db.connect() as conn:
        rows = await conn.execute_fetchall(
            'SELECT * FROM routine_experiments WHERE user_id=? AND status="active" ORDER BY id DESC LIMIT 1',
            (user_id,),
        )
        return dict(rows[0]) if rows else None
