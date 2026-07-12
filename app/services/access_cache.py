from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.config import settings
from app.db import get_session
from app.models import StudentProfile, User


@dataclass(frozen=True)
class AccessSnapshot:
    user_id: int
    telegram_id: int
    role: str
    is_active: bool
    is_banned: bool
    access_until: datetime | None
    profile_confirmed: bool


_TTL = float(os.getenv("ACCESS_CACHE_TTL", "30"))
_CACHE: dict[int, tuple[float, AccessSnapshot]] = {}
_MAX_CACHE = int(os.getenv("ACCESS_CACHE_MAX", "20000"))


def invalidate_user_access(telegram_id: int | None = None) -> None:
    """Clear cached access data after admin/profile changes."""
    if telegram_id is None:
        _CACHE.clear()
    else:
        _CACHE.pop(int(telegram_id), None)


def _trim_cache_if_needed() -> None:
    if len(_CACHE) <= _MAX_CACHE:
        return
    # Remove oldest quarter; cheap enough and keeps memory bounded.
    old = sorted(_CACHE.items(), key=lambda item: item[1][0])[: max(1, len(_CACHE) // 4)]
    for key, _ in old:
        _CACHE.pop(key, None)


def _make_snapshot(user: User, profile_confirmed: bool) -> AccessSnapshot:
    return AccessSnapshot(
        user_id=user.id,
        telegram_id=user.telegram_id,
        role=user.role,
        is_active=bool(user.is_active),
        is_banned=bool(user.is_banned),
        access_until=user.access_until,
        profile_confirmed=bool(profile_confirmed),
    )


def get_access_snapshot(tg_user: Any) -> AccessSnapshot:
    """Fast user/profile/access loader with short memory cache.

    Normal button clicks should not hit PostgreSQL on every message. This caches
    only permission/profile state for a short TTL. Admin actions invalidate it.
    """
    tg_id = int(tg_user.id)
    now = time.monotonic()
    cached = _CACHE.get(tg_id)
    if cached and now < cached[0]:
        return cached[1]

    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == tg_id))
        changed = False
        if user is None:
            role = "admin" if tg_id in settings.admin_ids else "student"
            user = User(
                telegram_id=tg_id,
                username=getattr(tg_user, "username", None),
                first_name=getattr(tg_user, "first_name", None),
                role=role,
                is_active=(role == "admin"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            username = getattr(tg_user, "username", None)
            first_name = getattr(tg_user, "first_name", None)
            if user.username != username:
                user.username = username
                changed = True
            if user.first_name != first_name:
                user.first_name = first_name
                changed = True
            if tg_id in settings.admin_ids and (user.role != "admin" or not user.is_active):
                user.role = "admin"
                user.is_active = True
                changed = True
            if changed:
                db.commit()
                db.refresh(user)

        profile_confirmed = bool(db.scalar(select(StudentProfile.confirmed).where(StudentProfile.user_id == user.id)))
        snapshot = _make_snapshot(user, profile_confirmed)

    _CACHE[tg_id] = (now + _TTL, snapshot)
    _trim_cache_if_needed()
    return snapshot


def access_is_valid(snapshot: AccessSnapshot) -> bool:
    if snapshot.role == "admin":
        return True
    if snapshot.is_banned or not snapshot.is_active:
        return False
    if snapshot.access_until and snapshot.access_until < datetime.now(UTC):
        return False
    return True
