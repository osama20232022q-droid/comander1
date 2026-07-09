from __future__ import annotations

from aiogram.types import User as TgUser

from app.config import settings
from app.db import db, dt_iso


async def upsert_user(tg_user: TgUser) -> dict:
    role = 'admin' if tg_user.id in settings.admin_ids else 'student'
    async with db.connect() as conn:
        await conn.execute(
            '''INSERT INTO users(tg_id, username, full_name, role, created_at, last_seen_at)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(tg_id) DO UPDATE SET
               username=excluded.username,
               full_name=excluded.full_name,
               role=CASE WHEN excluded.role='admin' THEN 'admin' ELSE users.role END,
               last_seen_at=excluded.last_seen_at''',
            (tg_user.id, tg_user.username, tg_user.full_name, role, dt_iso(), dt_iso()),
        )
        row = await conn.execute_fetchall('SELECT * FROM users WHERE tg_id=?', (tg_user.id,))
        user = dict(row[0])
        await conn.execute(
            '''INSERT OR IGNORE INTO profiles(user_id, display_name, updated_at)
               VALUES(?,?,?)''',
            (user['id'], tg_user.full_name, dt_iso()),
        )
        return user


async def ensure_user_by_tg_id(tg_id: int, created_by_admin_id: int | None = None) -> dict:
    async with db.connect() as conn:
        rows = await conn.execute_fetchall('SELECT * FROM users WHERE tg_id=?', (tg_id,))
        if rows:
            return dict(rows[0])
        await conn.execute(
            '''INSERT INTO users(tg_id, username, full_name, role, is_blocked, created_by_admin_id, created_at, last_seen_at)
               VALUES(?,?,?,?,?,?,?,?)''',
            (tg_id, None, f'User {tg_id}', 'student', 0, created_by_admin_id, dt_iso(), dt_iso()),
        )
        rows = await conn.execute_fetchall('SELECT * FROM users WHERE tg_id=?', (tg_id,))
        user = dict(rows[0])
        await conn.execute(
            '''INSERT OR IGNORE INTO profiles(user_id, display_name, updated_at)
               VALUES(?,?,?)''',
            (user['id'], user['full_name'], dt_iso()),
        )
        return user


async def get_user_by_tg(tg_id: int) -> dict | None:
    async with db.connect() as conn:
        rows = await conn.execute_fetchall('SELECT * FROM users WHERE tg_id=?', (tg_id,))
        return dict(rows[0]) if rows else None


async def resolve_user(identifier: str, created_by_admin_id: int | None = None) -> dict | None:
    ident = identifier.strip().lstrip('@')
    async with db.connect() as conn:
        if ident.isdigit():
            rows = await conn.execute_fetchall('SELECT * FROM users WHERE tg_id=?', (int(ident),))
            if rows:
                return dict(rows[0])
            return await ensure_user_by_tg_id(int(ident), created_by_admin_id)
        rows = await conn.execute_fetchall('SELECT * FROM users WHERE lower(username)=lower(?)', (ident,))
        return dict(rows[0]) if rows else None


async def get_user_profile(user_id: int) -> dict:
    async with db.connect() as conn:
        rows = await conn.execute_fetchall('SELECT * FROM profiles WHERE user_id=?', (user_id,))
        return dict(rows[0]) if rows else {}


async def is_blocked(tg_id: int) -> bool:
    user = await get_user_by_tg(tg_id)
    return bool(user and user['is_blocked'])


async def block_user(identifier: str, blocked: bool = True) -> bool:
    user = await resolve_user(identifier)
    if not user:
        return False
    async with db.connect() as conn:
        await conn.execute('UPDATE users SET is_blocked=? WHERE id=?', (1 if blocked else 0, user['id']))
    return True
