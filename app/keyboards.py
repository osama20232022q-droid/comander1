from __future__ import annotations

from telegram import ReplyKeyboardMarkup


def rk(rows: list[list[str]], placeholder: str = "اختر أمرًا") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False, input_field_placeholder=placeholder)


def _buttons_version() -> int:
    try:
        from app.services.buttons import buttons_cache_version
        return buttons_cache_version()
    except Exception:
        return 0


_KB_CACHE: dict[tuple[str, bool, int], ReplyKeyboardMarkup] = {}


def clear_keyboard_cache() -> None:
    _KB_CACHE.clear()


def _dynamic_rows(scope: str, include_admin_entry: bool = False) -> list[list[str]]:
    try:
        from app.services.buttons import keyboard_rows_for_scope
        rows = keyboard_rows_for_scope(scope, include_admin_entry=include_admin_entry)
        if rows:
            return rows
    except Exception:
        pass
    return []


def _cached_dynamic_keyboard(scope: str, placeholder: str, include_admin_entry: bool = False, fallback_rows: list[list[str]] | None = None) -> ReplyKeyboardMarkup:
    version = _buttons_version()
    key = (scope, include_admin_entry, version)
    cached = _KB_CACHE.get(key)
    if cached is not None:
        return cached
    rows = _dynamic_rows(scope, include_admin_entry=include_admin_entry)
    if not rows:
        rows = fallback_rows or []
    markup = rk(rows, placeholder)
    _KB_CACHE[key] = markup
    # Keep cache bounded in long-running deployments.
    if len(_KB_CACHE) > 64:
        for old_key in list(_KB_CACHE.keys())[:16]:
            _KB_CACHE.pop(old_key, None)
    return markup


def main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    fallback = [
        ["📚 المواد", "🧠 خطة دراسية معمقة"],
        ["⏳ البومودورو", "⌛ كم المتبقي؟"],
        ["🔥 حفزني", "🕌 أذكار الصلاة"],
        ["📊 تقدمي", "🏅 شهاداتي"],
        ["👤 ملفي"],
        ["🔘 الأزرار الشفافة", "❓ ماذا يفعل هذا البوت؟"],
        ["⚙️ ضبط يدوي"],
    ]
    if is_admin:
        fallback.append(["👑 لوحة الأدمن"])
    return _cached_dynamic_keyboard("main", "اختر أمرًا", include_admin_entry=is_admin, fallback_rows=fallback)


def nav_keyboard() -> ReplyKeyboardMarkup:
    return rk([["↩️ خطوة للوراء", "🏠 القائمة الرئيسية"]])


def confirm_back_keyboard() -> ReplyKeyboardMarkup:
    return rk([["🔵 تأكيد", "🔴 رجوع للتعديل"], ["🏠 القائمة الرئيسية"]])


def subjects_menu_keyboard(subjects: list[str]) -> ReplyKeyboardMarkup:
    rows = [["➕ إضافة مادة", "📁 موادي"]]
    for name in subjects:
        rows.append([f"📘 {name}"])
    rows.append(["↩️ خطوة للوراء", "🏠 القائمة الرئيسية"])
    return rk(rows, "اختر مادة أو أضف مادة")


def subject_detail_keyboard(subject_name: str) -> ReplyKeyboardMarkup:
    return rk([
        [f"📎 رفع ملحقات {subject_name}"],
        [f"📘 رفع أسئلة سنوات {subject_name}"],
        [f"📂 عرض ملحقات {subject_name}", f"📚 عرض أسئلة سنوات {subject_name}"],
        [f"🧠 تحليل سريع {subject_name}"],
        ["↩️ خطوة للوراء", "🏠 القائمة الرئيسية"],
    ], "إجراءات المادة")


def plan_options_keyboard(values: list[str]) -> ReplyKeyboardMarkup:
    rows = []
    for i in range(0, len(values), 2):
        rows.append(values[i:i+2])
    rows.append(["↩️ خطوة للوراء", "🏠 القائمة الرئيسية"])
    return rk(rows)


def pomodoro_menu_keyboard() -> ReplyKeyboardMarkup:
    return rk([
        ["25 دراسة / 5 راحة", "50 دراسة / 10 راحة"],
        ["90 دراسة / 15 راحة", "وقت مخصص"],
        ["▶️ ابدأ", "⌛ كم المتبقي؟"],
        ["✅ أنهيت الجلسة", "🍽️ سجل الأكل"],
        ["↩️ خطوة للوراء", "🏠 القائمة الرئيسية"],
    ], "اختر نظام البومودورو")


def pomodoro_running_keyboard() -> ReplyKeyboardMarkup:
    return rk([
        ["⌛ كم المتبقي؟", "✅ أنهيت الجلسة"],
        ["🍽️ سجل الأكل"],
        ["🏠 القائمة الرئيسية"],
    ], "الجلسة تعمل")


def certificate_keyboard() -> ReplyKeyboardMarkup:
    return rk([
        ["📋 شروط الشهادة"],
        ["🏅 طلب شهادة يوم مميز", "🎖️ طلب شهادة أسبوعية"],
        ["📜 آخر شهاداتي"],
        ["↩️ خطوة للوراء", "🏠 القائمة الرئيسية"],
    ], "الشهادات")


def admin_keyboard() -> ReplyKeyboardMarkup:
    fallback = [
        ["👥 طلبات التفعيل", "➕ تفعيل مشترك"],
        ["📊 إحصائيات النظام", "📋 المستخدمون"],
        ["🚫 حظر مستخدم", "✅ إلغاء الحظر"],
        ["🧩 الأزرار", "📦 نسخة احتياطية الآن"],
        ["♻️ فحص ملف استرجاع", "☁️ حالة قاعدة البيانات"],
        ["🏠 القائمة الرئيسية"],
    ]
    return _cached_dynamic_keyboard("admin", "لوحة الأدمن", fallback_rows=fallback)


def admin_buttons_keyboard() -> ReplyKeyboardMarkup:
    fallback = [
        ["✏️ تعديل الأزرار", "🎨 تعديل ألوان الأزرار"],
        ["➕ زر لوحة كيبورد", "➕ زر شفاف"],
        ["🗑️ الأزرار المحذوفة", "↕️ ترتيب الأزرار"],
        ["🔄 استرجاع الأزرار الافتراضية"],
        ["👑 لوحة الأدمن", "🏠 القائمة الرئيسية"],
    ]
    return _cached_dynamic_keyboard("admin_buttons", "إدارة الأزرار", fallback_rows=fallback)


def admin_button_edit_keyboard() -> ReplyKeyboardMarkup:
    fallback = [
        ["🗑️ حذف زر معين", "✏️ إعادة تسمية زر معين"],
        ["➕ إضافة زر معين"],
        ["↩️ رجوع إلى الأزرار", "👑 لوحة الأدمن"],
    ]
    return _cached_dynamic_keyboard("admin_button_edit", "تعديل الأزرار", fallback_rows=fallback)


def button_selector_keyboard(rows: list[list[str]], placeholder: str = "اختر زرًا") -> ReplyKeyboardMarkup:
    if not rows:
        rows = [["↩️ رجوع إلى الأزرار", "👑 لوحة الأدمن"]]
    return rk(rows, placeholder)


def button_confirm_delete_keyboard() -> ReplyKeyboardMarkup:
    return rk([["✅ تأكيد حذف الزر", "❌ إلغاء الحذف"], ["↩️ رجوع إلى الأزرار", "👑 لوحة الأدمن"]], "تأكيد الحذف")


def button_style_keyboard() -> ReplyKeyboardMarkup:
    return rk([
        ["⚪ عادي", "🔵 أزرق"],
        ["🟢 أخضر", "🔴 أحمر"],
        ["↩️ رجوع إلى الأزرار", "👑 لوحة الأدمن"],
    ], "اختر نمط الزر")


def button_order_scope_keyboard() -> ReplyKeyboardMarkup:
    return rk([
        ["القائمة الرئيسية - main", "لوحة الأدمن - admin"],
        ["إدارة الأزرار - buttons", "تعديل الأزرار - edit"],
        ["↩️ رجوع إلى الأزرار", "👑 لوحة الأدمن"],
    ], "اختر الشاشة التي تريد ترتيب أزرارها")


def profile_keyboard() -> ReplyKeyboardMarkup:
    fallback = [
        ["✏️ تعديل معلوماتي"],
        ["🔄 تغيير نظامي", "🌱 إضافة عادة"],
        ["📋 عاداتي"],
        ["🏠 القائمة الرئيسية"],
    ]
    return _cached_dynamic_keyboard("profile", "ملفك الشخصي", fallback_rows=fallback)


def manual_settings_keyboard() -> ReplyKeyboardMarkup:
    fallback = [
        ["✏️ تعديل معلوماتي"],
        ["🔄 تغيير نظامي", "🌱 إضافة عادة"],
        ["📋 عاداتي"],
        ["🏠 القائمة الرئيسية"],
    ]
    return _cached_dynamic_keyboard("profile", "الضبط اليدوي", fallback_rows=fallback)


def habit_duration_keyboard() -> ReplyKeyboardMarkup:
    return rk([
        ["7 أيام", "14 يوم"],
        ["21 يوم", "30 يوم"],
        ["⚙️ الضبط اليدوي", "🏠 القائمة الرئيسية"],
    ], "اختر مدة العادة")


def habit_review_keyboard() -> ReplyKeyboardMarkup:
    return rk([
        ["✅ حفظ العادة", "🔴 رجوع للتعديل"],
        ["⚙️ الضبط اليدوي", "🏠 القائمة الرئيسية"],
    ], "تأكيد العادة")


def routine_type_keyboard() -> ReplyKeyboardMarkup:
    return rk([
        ["نظام صباحي", "نظام نوم مبكر"],
        ["نظام دراسة ثابت", "نظام مخصص"],
        ["⚙️ الضبط اليدوي", "🏠 القائمة الرئيسية"],
    ], "اختر نوع النظام")


def routine_review_keyboard() -> ReplyKeyboardMarkup:
    return rk([
        ["✅ حفظ النظام", "🔴 رجوع للتعديل"],
        ["⚙️ الضبط اليدوي", "🏠 القائمة الرئيسية"],
    ], "تأكيد النظام")
