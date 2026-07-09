from __future__ import annotations

from datetime import datetime, timedelta

from app.config import settings
from app.db import db, dt_iso
from app.services.user_service import resolve_user
from app.utils.time_utils import human_minutes, now


PLAN_DAYS = {
    '٧ أيام تجربة': 7,
    'شهري': 30,
    '٣ أشهر': 90,
    '٦ أشهر': 180,
    'سنوي': 365,
}


def is_admin_tg(tg_id: int) -> bool:
    return tg_id in settings.admin_ids


async def active_subscription(user_id: int) -> dict | None:
    current = dt_iso()
    async with db.connect() as conn:
        rows = await conn.execute_fetchall(
            '''SELECT * FROM subscriptions
               WHERE user_id=? AND status='active' AND paid=1 AND end_at>=?
               ORDER BY end_at DESC LIMIT 1''',
            (user_id, current),
        )
        return dict(rows[0]) if rows else None


async def has_access(user: dict) -> bool:
    if user['role'] == 'admin' or user['tg_id'] in settings.admin_ids:
        return True
    if user['is_blocked']:
        return False
    return await active_subscription(user['id']) is not None


async def subscription_status_text(user: dict) -> str:
    if user['role'] == 'admin' or user['tg_id'] in settings.admin_ids:
        return 'صلاحيتك: Admin. كل الخدمات مفتوحة.'
    sub = await active_subscription(user['id'])
    if not sub:
        return (
            'اشتراكك غير مفعل حاليًا.\n'
            f'معرفك الرقمي: <code>{user["tg_id"]}</code>\n\n'
            'أرسل هذا المعرف للمدير حتى يفعّل لك الاشتراك من لوحة الأدمن.'
        )
    end = datetime.fromisoformat(sub['end_at'])
    remaining = max(0, int((end - now()).total_seconds() // 60))
    return (
        f'اشتراكك فعال ✅\n'
        f'الخطة: {sub["plan"]}\n'
        f'ينتهي: {end.strftime("%Y-%m-%d %H:%M")}\n'
        f'المتبقي: {human_minutes(remaining)}'
    )


async def create_subscription_request(user_id: int, note: str = '') -> int:
    async with db.connect() as conn:
        cur = await conn.execute(
            '''INSERT INTO subscription_requests(user_id,requested_at,status,note)
               VALUES(?,?,?,?)''',
            (user_id, dt_iso(), 'pending', note),
        )
        return int(cur.lastrowid)


async def grant_subscription(identifier: str, plan: str, created_by_tg_id: int, paid: bool = True, note: str = '') -> dict | None:
    target = await resolve_user(identifier, created_by_admin_id=created_by_tg_id)
    if not target:
        return None
    days = PLAN_DAYS.get(plan, 30)
    start = now()
    existing = await active_subscription(target['id'])
    if existing:
        existing_end = datetime.fromisoformat(existing['end_at'])
        if existing_end > start:
            start = existing_end
    end = start + timedelta(days=days)
    async with db.connect() as conn:
        await conn.execute(
            '''INSERT INTO subscriptions(user_id,plan,status,paid,start_at,end_at,created_by,created_at,note)
               VALUES(?,?,?,?,?,?,?,?,?)''',
            (target['id'], plan, 'active' if paid else 'pending', 1 if paid else 0, dt_iso(start), dt_iso(end), created_by_tg_id, dt_iso(), note),
        )
    sub = await active_subscription(target['id'])
    return {'user': target, 'subscription': sub, 'start': start, 'end': end}


async def revoke_subscription(identifier: str) -> bool:
    target = await resolve_user(identifier)
    if not target:
        return False
    async with db.connect() as conn:
        await conn.execute(
            '''UPDATE subscriptions SET status='revoked', revoked_at=?
               WHERE user_id=? AND status='active' ''',
            (dt_iso(), target['id']),
        )
    return True


async def list_users_with_subscriptions(limit: int = 30) -> list[dict]:
    current = dt_iso()
    async with db.connect() as conn:
        rows = await conn.execute_fetchall(
            '''SELECT u.*,
                      (SELECT end_at FROM subscriptions s
                       WHERE s.user_id=u.id AND s.status='active' AND s.paid=1
                       ORDER BY s.end_at DESC LIMIT 1) AS sub_end,
                      (SELECT plan FROM subscriptions s
                       WHERE s.user_id=u.id AND s.status='active' AND s.paid=1
                       ORDER BY s.end_at DESC LIMIT 1) AS sub_plan
               FROM users u ORDER BY u.id DESC LIMIT ?''',
            (limit,),
        )
    result = []
    for row in rows:
        item = dict(row)
        item['sub_active'] = bool(item.get('sub_end') and item['sub_end'] >= current)
        result.append(item)
    return result


async def admin_stats() -> dict:
    current = dt_iso()
    async with db.connect() as conn:
        users = await conn.execute_fetchall('SELECT COUNT(*) AS c FROM users')
        blocked = await conn.execute_fetchall('SELECT COUNT(*) AS c FROM users WHERE is_blocked=1')
        active = await conn.execute_fetchall(
            '''SELECT COUNT(DISTINCT user_id) AS c FROM subscriptions
               WHERE status='active' AND paid=1 AND end_at>=?''',
            (current,),
        )
        expired = await conn.execute_fetchall(
            '''SELECT COUNT(DISTINCT user_id) AS c FROM subscriptions
               WHERE status='active' AND paid=1 AND end_at<?''',
            (current,),
        )
        requests = await conn.execute_fetchall(
            '''SELECT COUNT(*) AS c FROM subscription_requests WHERE status='pending' '''
        )
    return {
        'users': int(users[0]['c']),
        'blocked': int(blocked[0]['c']),
        'active_subscriptions': int(active[0]['c']),
        'expired_subscriptions': int(expired[0]['c']),
        'pending_requests': int(requests[0]['c']),
    }


async def expiring_subscriptions(days: int = 2) -> list[dict]:
    start = dt_iso()
    end = dt_iso(now() + timedelta(days=days))
    async with db.connect() as conn:
        rows = await conn.execute_fetchall(
            '''SELECT u.tg_id, u.full_name, s.plan, s.end_at
               FROM subscriptions s JOIN users u ON u.id=s.user_id
               WHERE s.status='active' AND s.paid=1 AND s.end_at BETWEEN ? AND ? AND u.is_blocked=0''',
            (start, end),
        )
    return [dict(r) for r in rows]
