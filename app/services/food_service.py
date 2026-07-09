from __future__ import annotations

from app.db import db, dt_iso
from app.utils.calories import estimate_food_calories


async def log_food(user_id: int, text: str) -> dict:
    est = estimate_food_calories(text)
    async with db.connect() as conn:
        cur = await conn.execute(
            '''INSERT INTO food_logs(user_id,logged_at,item,calories_min,calories_max,note)
               VALUES(?,?,?,?,?,?)''',
            (user_id, dt_iso(), text, est.calories_min, est.calories_max, est.note),
        )
    return {'id': cur.lastrowid, **est.__dict__}


async def log_water(user_id: int, ml: int) -> None:
    async with db.connect() as conn:
        await conn.execute('INSERT INTO water_logs(user_id,logged_at,ml) VALUES(?,?,?)', (user_id, dt_iso(), ml))


async def today_energy_summary(user_id: int, date_prefix: str) -> dict:
    async with db.connect() as conn:
        foods = await conn.execute_fetchall(
            'SELECT * FROM food_logs WHERE user_id=? AND logged_at LIKE ? ORDER BY logged_at',
            (user_id, f'{date_prefix}%'),
        )
        waters = await conn.execute_fetchall(
            'SELECT COALESCE(SUM(ml),0) AS total FROM water_logs WHERE user_id=? AND logged_at LIKE ?',
            (user_id, f'{date_prefix}%'),
        )
    return {
        'calories_min': sum(int(r['calories_min']) for r in foods),
        'calories_max': sum(int(r['calories_max']) for r in foods),
        'food_count': len(foods),
        'water_ml': int(waters[0]['total'] if waters else 0),
    }
