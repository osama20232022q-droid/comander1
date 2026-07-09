from __future__ import annotations

from app.db import db, dt_iso, loads


async def add_subject(user_id: int, name: str, exam_date: str | None, level: str, has_practical: bool) -> int:
    async with db.connect() as conn:
        cur = await conn.execute(
            'INSERT INTO subjects(user_id,name,exam_date,level,has_practical,created_at) VALUES(?,?,?,?,?,?)',
            (user_id, name, exam_date, level, 1 if has_practical else 0, dt_iso()),
        )
        return int(cur.lastrowid)


async def list_subjects(user_id: int) -> list[dict]:
    async with db.connect() as conn:
        rows = await conn.execute_fetchall('SELECT * FROM subjects WHERE user_id=? ORDER BY id DESC', (user_id,))
        return [dict(r) for r in rows]


async def add_lecture(subject_id: int, title: str, pages: int, difficulty: str, estimated_minutes: int, analysis_json: str = '{}', file_path: str | None = None) -> int:
    async with db.connect() as conn:
        cur = await conn.execute(
            '''INSERT INTO lectures(subject_id,title,pages,difficulty,estimated_minutes,analysis_json,file_path,created_at)
               VALUES(?,?,?,?,?,?,?,?)''',
            (subject_id, title, pages, difficulty, estimated_minutes, analysis_json, file_path, dt_iso()),
        )
        return int(cur.lastrowid)


async def list_lectures(user_id: int) -> list[dict]:
    async with db.connect() as conn:
        rows = await conn.execute_fetchall(
            '''SELECT l.*, s.name AS subject_name FROM lectures l
               JOIN subjects s ON s.id=l.subject_id WHERE s.user_id=? ORDER BY l.id DESC''',
            (user_id,),
        )
        result = []
        for row in rows:
            item = dict(row)
            item['analysis'] = loads(item.get('analysis_json'), {})
            result.append(item)
        return result


async def mark_lecture_done(lecture_id: int, user_id: int) -> bool:
    async with db.connect() as conn:
        rows = await conn.execute_fetchall(
            'SELECT l.id FROM lectures l JOIN subjects s ON s.id=l.subject_id WHERE l.id=? AND s.user_id=?',
            (lecture_id, user_id),
        )
        if not rows:
            return False
        await conn.execute('UPDATE lectures SET status="done" WHERE id=?', (lecture_id,))
        return True
