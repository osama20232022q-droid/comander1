from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.models import User, StudentProfile, AdminAction
from app.utils import classify_college


def ensure_user(db: Session, tg_user) -> User:
    user = db.scalar(select(User).where(User.telegram_id == tg_user.id))
    if user:
        changed = False
        if user.username != tg_user.username:
            user.username = tg_user.username
            changed = True
        if user.first_name != tg_user.first_name:
            user.first_name = tg_user.first_name
            changed = True
        if tg_user.id in settings.admin_ids and (user.role != "admin" or not user.is_active):
            user.role = "admin"
            user.is_active = True
            changed = True
        if changed:
            db.commit()
            try:
                from app.services.access_cache import invalidate_user_access
                invalidate_user_access(tg_user.id)
            except Exception:
                pass
        return user
    role = "admin" if tg_user.id in settings.admin_ids else "student"
    user = User(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        role=role,
        is_active=(role == "admin"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        from app.services.access_cache import invalidate_user_access
        invalidate_user_access(tg_user.id)
    except Exception:
        pass
    return user


def save_profile(db: Session, user: User, draft: dict) -> StudentProfile:
    domain, specialty = classify_college(draft["college"])
    profile = user.profile
    if not profile:
        profile = StudentProfile(user_id=user.id, full_name=draft["full_name"], college=draft["college"], specialty=specialty, study_domain=domain, stage=draft["stage"], confirmed=True)
        db.add(profile)
    profile.full_name = draft["full_name"]
    profile.college = draft["college"]
    profile.specialty = specialty
    profile.study_domain = domain
    profile.stage = draft["stage"]
    profile.age = draft.get("age")
    profile.height_cm = draft.get("height_cm")
    profile.weight_kg = draft.get("weight_kg")
    profile.confirmed = True
    db.commit()
    db.refresh(profile)
    try:
        from app.services.access_cache import invalidate_user_access
        invalidate_user_access(user.telegram_id)
    except Exception:
        pass
    return profile


def activate_user(db: Session, admin: User, target_id: int, days: int | None = None) -> User | None:
    target = db.get(User, target_id)
    if not target:
        return None
    target.is_active = True
    if days:
        target.access_until = datetime.now(timezone.utc) + timedelta(days=days)
    else:
        target.access_until = None
    db.add(AdminAction(admin_user_id=admin.id, target_user_id=target.id, action="activate", details=f"days={days}"))
    db.commit()
    try:
        from app.services.access_cache import invalidate_user_access
        invalidate_user_access(target.telegram_id)
    except Exception:
        pass
    return target


def ban_user(db: Session, admin: User, target_id: int, banned: bool = True) -> User | None:
    target = db.get(User, target_id)
    if not target:
        return None
    target.is_banned = banned
    db.add(AdminAction(admin_user_id=admin.id, target_user_id=target.id, action="ban" if banned else "unban"))
    db.commit()
    try:
        from app.services.access_cache import invalidate_user_access
        invalidate_user_access(target.telegram_id)
    except Exception:
        pass
    return target
