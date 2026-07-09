from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from types import SimpleNamespace
import os
import time
from sqlalchemy import select, func
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.db import get_session
from app.models import ButtonConfig

COLOR_PREFIX = {
    "default": "",
    "primary": "🔵",
    "success": "🟢",
    "danger": "🔴",
}

PROTECTED_ACTIONS = {
    "admin_panel",
    "admin_buttons",
    "admin_button_edit",
    "admin_deleted_buttons",
    "home",
}

# scope: main/admin/both. button_type: reply/inline
DEFAULT_BUTTONS: list[dict] = [
    # Main menu
    {"action_key": "subjects", "label": "📚 المواد", "scope": "main", "button_type": "reply", "row_order": 1, "col_order": 1, "style": "default"},
    {"action_key": "study_plan", "label": "🧠 خطة دراسية معمقة", "scope": "main", "button_type": "reply", "row_order": 1, "col_order": 2, "style": "default"},
    {"action_key": "pomodoro", "label": "⏳ البومودورو", "scope": "main", "button_type": "reply", "row_order": 2, "col_order": 1, "style": "default"},
    {"action_key": "remaining", "label": "⌛ كم المتبقي؟", "scope": "main", "button_type": "reply", "row_order": 2, "col_order": 2, "style": "primary"},
    {"action_key": "motivate", "label": "🔥 حفزني", "scope": "main", "button_type": "reply", "row_order": 3, "col_order": 1, "style": "default"},
    {"action_key": "prayer_reminders", "label": "🕌 أذكار الصلاة", "scope": "main", "button_type": "reply", "row_order": 3, "col_order": 2, "style": "success"},
    {"action_key": "progress", "label": "📊 تقدمي", "scope": "main", "button_type": "reply", "row_order": 4, "col_order": 1, "style": "default"},
    {"action_key": "certificates", "label": "🏅 شهاداتي", "scope": "main", "button_type": "reply", "row_order": 4, "col_order": 2, "style": "default"},
    {"action_key": "profile", "label": "👤 ملفي", "scope": "main", "button_type": "reply", "row_order": 5, "col_order": 1, "style": "default"},
    {"action_key": "inline_buttons", "label": "🔘 الأزرار الشفافة", "scope": "main", "button_type": "reply", "row_order": 5, "col_order": 2, "style": "default"},
    {"action_key": "help", "label": "❓ ماذا يفعل هذا البوت؟", "scope": "main", "button_type": "reply", "row_order": 6, "col_order": 1, "style": "default"},
    {"action_key": "admin_panel", "label": "👑 لوحة الأدمن", "scope": "admin_entry", "button_type": "reply", "row_order": 99, "col_order": 1, "style": "danger"},

    # Admin panel
    {"action_key": "admin_pending", "label": "👥 طلبات التفعيل", "scope": "admin", "button_type": "reply", "row_order": 1, "col_order": 1, "style": "default"},
    {"action_key": "admin_activate", "label": "➕ تفعيل مشترك", "scope": "admin", "button_type": "reply", "row_order": 1, "col_order": 2, "style": "success"},
    {"action_key": "admin_stats", "label": "📊 إحصائيات النظام", "scope": "admin", "button_type": "reply", "row_order": 2, "col_order": 1, "style": "primary"},
    {"action_key": "admin_users", "label": "📋 المستخدمون", "scope": "admin", "button_type": "reply", "row_order": 2, "col_order": 2, "style": "default"},
    {"action_key": "admin_ban", "label": "🚫 حظر مستخدم", "scope": "admin", "button_type": "reply", "row_order": 3, "col_order": 1, "style": "danger"},
    {"action_key": "admin_unban", "label": "✅ إلغاء الحظر", "scope": "admin", "button_type": "reply", "row_order": 3, "col_order": 2, "style": "success"},
    {"action_key": "admin_buttons", "label": "🧩 الأزرار", "scope": "admin", "button_type": "reply", "row_order": 4, "col_order": 1, "style": "primary"},
    {"action_key": "admin_backup", "label": "📦 نسخة احتياطية الآن", "scope": "admin", "button_type": "reply", "row_order": 4, "col_order": 2, "style": "default"},
    {"action_key": "admin_restore_check", "label": "♻️ فحص ملف استرجاع", "scope": "admin", "button_type": "reply", "row_order": 5, "col_order": 1, "style": "default"},
    {"action_key": "admin_db_status", "label": "☁️ حالة قاعدة البيانات", "scope": "admin", "button_type": "reply", "row_order": 5, "col_order": 2, "style": "default"},
    {"action_key": "home", "label": "🏠 القائمة الرئيسية", "scope": "both", "button_type": "reply", "row_order": 100, "col_order": 1, "style": "default"},

    # Button manager menus
    {"action_key": "admin_button_edit", "label": "✏️ تعديل الأزرار", "scope": "admin_buttons", "button_type": "reply", "row_order": 1, "col_order": 1, "style": "primary"},
    {"action_key": "admin_button_colors", "label": "🎨 تعديل ألوان الأزرار", "scope": "admin_buttons", "button_type": "reply", "row_order": 1, "col_order": 2, "style": "default"},
    {"action_key": "admin_add_keyboard", "label": "➕ زر لوحة كيبورد", "scope": "admin_buttons", "button_type": "reply", "row_order": 2, "col_order": 1, "style": "success"},
    {"action_key": "admin_add_inline", "label": "➕ زر شفاف", "scope": "admin_buttons", "button_type": "reply", "row_order": 2, "col_order": 2, "style": "success"},
    {"action_key": "admin_deleted_buttons", "label": "🗑️ الأزرار المحذوفة", "scope": "admin_buttons", "button_type": "reply", "row_order": 3, "col_order": 1, "style": "danger"},
    {"action_key": "admin_restore_defaults", "label": "🔄 استرجاع الأزرار الافتراضية", "scope": "admin_buttons", "button_type": "reply", "row_order": 3, "col_order": 2, "style": "default"},
    {"action_key": "admin_delete_button", "label": "🗑️ حذف زر معين", "scope": "admin_button_edit", "button_type": "reply", "row_order": 1, "col_order": 1, "style": "danger"},
    {"action_key": "admin_rename_button", "label": "✏️ إعادة تسمية زر معين", "scope": "admin_button_edit", "button_type": "reply", "row_order": 1, "col_order": 2, "style": "primary"},
    {"action_key": "admin_add_button_from_edit", "label": "➕ إضافة زر معين", "scope": "admin_button_edit", "button_type": "reply", "row_order": 2, "col_order": 1, "style": "success"},
    {"action_key": "admin_back_buttons", "label": "↩️ رجوع إلى الأزرار", "scope": "admin_button_edit", "button_type": "reply", "row_order": 3, "col_order": 1, "style": "default"},
]


_DEFAULTS_READY = False
_BUTTON_CACHE_TTL = float(os.getenv("BUTTON_CACHE_TTL", "30"))
_BUTTON_CACHE_EXPIRES = 0.0
_BUTTON_CACHE: list[SimpleNamespace] | None = None


def invalidate_buttons_cache() -> None:
    global _BUTTON_CACHE, _BUTTON_CACHE_EXPIRES
    _BUTTON_CACHE = None
    _BUTTON_CACHE_EXPIRES = 0.0


def _snapshot_button(b: ButtonConfig) -> SimpleNamespace:
    return SimpleNamespace(
        id=b.id,
        action_key=b.action_key,
        label=b.label,
        scope=b.scope,
        button_type=b.button_type,
        row_order=b.row_order,
        col_order=b.col_order,
        style=b.style,
        visible=b.visible,
        response_text=b.response_text,
        deleted_at=b.deleted_at,
        created_at=b.created_at,
        updated_at=b.updated_at,
    )


def _all_buttons_cached() -> list[SimpleNamespace]:
    global _BUTTON_CACHE, _BUTTON_CACHE_EXPIRES
    ensure_default_buttons()
    now = time.monotonic()
    if _BUTTON_CACHE is not None and now < _BUTTON_CACHE_EXPIRES:
        return list(_BUTTON_CACHE)
    with get_session() as db:
        buttons = db.scalars(select(ButtonConfig).order_by(ButtonConfig.scope, ButtonConfig.row_order, ButtonConfig.col_order, ButtonConfig.id)).all()
        _BUTTON_CACHE = [_snapshot_button(b) for b in buttons]
        _BUTTON_CACHE_EXPIRES = now + _BUTTON_CACHE_TTL
        return list(_BUTTON_CACHE)


def ensure_default_buttons(db=None) -> None:
    global _DEFAULTS_READY
    if _DEFAULTS_READY and db is None:
        return
    close = False
    if db is None:
        db = get_session()
        close = True
    try:
        existing = set(db.scalars(select(ButtonConfig.action_key)).all())
        changed = False
        for item in DEFAULT_BUTTONS:
            if item["action_key"] not in existing:
                db.add(ButtonConfig(**item))
                changed = True
        if changed:
            db.commit()
            invalidate_buttons_cache()
        _DEFAULTS_READY = True
    finally:
        if close:
            db.close()


def _strip_color_prefix(text: str) -> str:
    t = text.strip()
    for prefix in ["🔵 ", "🟢 ", "🔴 ", "⚪ "]:
        if t.startswith(prefix):
            return t[len(prefix):].strip()
    return t


def display_label(btn: ButtonConfig) -> str:
    prefix = COLOR_PREFIX.get(btn.style or "default", "")
    label = btn.label
    if prefix:
        # Do not duplicate if admin already included a color marker manually.
        clean = _strip_color_prefix(label)
        return f"{prefix} {clean}"
    return label


def action_by_label(text: str, scopes: Iterable[str] = ("main", "both")) -> ButtonConfig | None:
    raw = text.strip()
    clean = _strip_color_prefix(raw)
    scope_set = set(scopes)
    for b in _all_buttons_cached():
        if b.visible and b.deleted_at is None and b.scope in scope_set:
            if raw == display_label(b) or clean == _strip_color_prefix(b.label):
                return b
    return None


def get_button(action_key: str) -> ButtonConfig | None:
    for b in _all_buttons_cached():
        if b.action_key == action_key:
            return b
    return None


def label_for(action_key: str, fallback: str | None = None) -> str:
    b = get_button(action_key)
    if b and b.visible and not b.deleted_at:
        return display_label(b)
    return fallback or action_key


def buttons_for_scope(scope: str, include_admin_entry: bool = False) -> list[ButtonConfig]:
    scopes = {scope, "both"}
    if include_admin_entry:
        scopes.add("admin_entry")
    return sorted(
        [b for b in _all_buttons_cached() if b.visible and b.deleted_at is None and b.button_type == "reply" and b.scope in scopes],
        key=lambda b: (b.row_order, b.col_order, b.id),
    )


def keyboard_rows_for_scope(scope: str, include_admin_entry: bool = False) -> list[list[str]]:
    rows: dict[int, list[tuple[int, str]]] = {}
    for b in buttons_for_scope(scope, include_admin_entry=include_admin_entry):
        rows.setdefault(b.row_order, []).append((b.col_order, display_label(b)))
    return [[label for _, label in sorted(items)] for _, items in sorted(rows.items())]


def all_visible_buttons() -> list[ButtonConfig]:
    return sorted(
        [b for b in _all_buttons_cached() if b.visible and b.deleted_at is None],
        key=lambda b: (b.scope, b.row_order, b.col_order, b.id),
    )


def deleted_buttons() -> list[ButtonConfig]:
    return sorted(
        [b for b in _all_buttons_cached() if b.deleted_at is not None],
        key=lambda b: b.deleted_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )


def button_selector_rows(buttons: list[ButtonConfig], add_nav: bool = True) -> list[list[str]]:
    rows: list[list[str]] = []
    current: list[str] = []
    for b in buttons:
        current.append(display_label(b))
        if len(current) == 2:
            rows.append(current)
            current = []
    if current:
        rows.append(current)
    if add_nav:
        rows.append([label_for("admin_back_buttons", "↩️ رجوع إلى الأزرار"), label_for("admin_panel", "👑 لوحة الأدمن")])
    return rows


def delete_button(action_key: str) -> tuple[bool, str]:
    if action_key in PROTECTED_ACTIONS:
        return False, "هذا زر محمي حتى لا تفقد السيطرة على لوحة الأدمن."
    with get_session() as db:
        b = db.scalar(select(ButtonConfig).where(ButtonConfig.action_key == action_key))
        if not b:
            return False, "الزر غير موجود."
        b.visible = False
        b.deleted_at = datetime.now(timezone.utc)
        db.commit()
        invalidate_buttons_cache()
    return True, "تم حذف/إخفاء الزر. تستطيع استرجاعه من الأزرار المحذوفة."


def restore_button(action_key: str) -> tuple[bool, str]:
    with get_session() as db:
        b = db.scalar(select(ButtonConfig).where(ButtonConfig.action_key == action_key))
        if not b:
            return False, "الزر غير موجود."
        b.visible = True
        b.deleted_at = None
        db.commit()
        invalidate_buttons_cache()
    return True, "تم استرجاع الزر."


def rename_button(action_key: str, new_label: str) -> tuple[bool, str]:
    new_label = new_label.strip()
    if not new_label or len(new_label) > 80:
        return False, "اسم الزر غير صالح. يجب أن يكون بين 1 و80 حرفًا."
    with get_session() as db:
        b = db.scalar(select(ButtonConfig).where(ButtonConfig.action_key == action_key))
        if not b:
            return False, "الزر غير موجود."
        b.label = _strip_color_prefix(new_label)
        db.commit()
        invalidate_buttons_cache()
    return True, "تمت إعادة تسمية الزر."


def set_button_style(action_key: str, style: str) -> tuple[bool, str]:
    if style not in ["default", "primary", "success", "danger"]:
        return False, "لون غير مدعوم."
    with get_session() as db:
        b = db.scalar(select(ButtonConfig).where(ButtonConfig.action_key == action_key))
        if not b:
            return False, "الزر غير موجود."
        b.style = style
        db.commit()
        invalidate_buttons_cache()
    return True, "تم تعديل نمط الزر. ملاحظة: Telegram قد يعرض اللون حسب إصدار التطبيق؛ وإلا سيظهر رمز اللون."


def add_custom_button(label: str, response_text: str, button_type: str = "reply") -> tuple[bool, str]:
    label = label.strip()
    response_text = response_text.strip()
    if not label or len(label) > 80:
        return False, "اسم الزر غير صالح."
    if button_type not in ["reply", "inline"]:
        return False, "نوع الزر غير مدعوم."
    with get_session() as db:
        max_row = db.scalar(select(func.max(ButtonConfig.row_order)).where(ButtonConfig.scope == "main", ButtonConfig.button_type == "reply")) or 5
        key = f"custom:{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        scope = "main"
        row = max_row + 1 if button_type == "reply" else 1
        db.add(ButtonConfig(
            action_key=key,
            label=label,
            scope=scope,
            button_type=button_type,
            row_order=row,
            col_order=1,
            style="default",
            response_text=response_text,
            visible=True,
        ))
        db.commit()
        invalidate_buttons_cache()
    return True, "تمت إضافة الزر."


def inline_custom_keyboard() -> InlineKeyboardMarkup | None:
    buttons = sorted(
        [b for b in _all_buttons_cached() if b.visible and b.deleted_at is None and b.button_type == "inline" and str(b.action_key).startswith("custom:")],
        key=lambda b: b.id,
    )
    if not buttons:
        return None
    rows = [[InlineKeyboardButton(display_label(b), callback_data=f"custombtn:{b.id}")] for b in buttons]
    return InlineKeyboardMarkup(rows)


def custom_button_response_by_id(button_id: int) -> str | None:
    with get_session() as db:
        b = db.get(ButtonConfig, button_id)
        if not b or not b.visible or b.deleted_at:
            return None
        return b.response_text or "هذا زر مخصص بلا نص."


def restore_default_visibility() -> None:
    ensure_default_buttons()
    with get_session() as db:
        defaults = {x["action_key"]: x for x in DEFAULT_BUTTONS}
        for b in db.scalars(select(ButtonConfig)).all():
            if b.action_key in defaults:
                d = defaults[b.action_key]
                b.label = d["label"]
                b.scope = d["scope"]
                b.button_type = d["button_type"]
                b.row_order = d["row_order"]
                b.col_order = d["col_order"]
                b.style = d.get("style", "default")
                b.visible = True
                b.deleted_at = None
        db.commit()
        invalidate_buttons_cache()
