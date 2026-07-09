from __future__ import annotations

from telegram import ReplyKeyboardMarkup


def rk(rows: list[list[str]], placeholder: str = "اختر أمرًا") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False, input_field_placeholder=placeholder)


def _dynamic_rows(scope: str, include_admin_entry: bool = False) -> list[list[str]]:
    try:
        from app.services.buttons import keyboard_rows_for_scope
        rows = keyboard_rows_for_scope(scope, include_admin_entry=include_admin_entry)
        if rows:
            return rows
    except Exception:
        pass
    return []


def main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = _dynamic_rows("main", include_admin_entry=is_admin)
    if not rows:
        rows = [
            ["📚 المواد", "🧠 خطة دراسية معمقة"],
            ["⏳ البومودورو", "⌛ كم المتبقي؟"],
            ["🔥 حفزني", "📊 تقدمي"],
            ["🏅 شهاداتي", "👤 ملفي"],
            ["🔘 الأزرار الشفافة", "❓ ماذا يفعل هذا البوت؟"],
        ]
        if is_admin:
            rows.append(["👑 لوحة الأدمن"])
    return rk(rows)


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
    rows = _dynamic_rows("admin")
    if not rows:
        rows = [
            ["👥 طلبات التفعيل", "➕ تفعيل مشترك"],
            ["📊 إحصائيات النظام", "📋 المستخدمون"],
            ["🚫 حظر مستخدم", "✅ إلغاء الحظر"],
            ["🧩 الأزرار", "📦 نسخة احتياطية الآن"],
            ["♻️ فحص ملف استرجاع", "☁️ حالة قاعدة البيانات"],
            ["🏠 القائمة الرئيسية"],
        ]
    return rk(rows, "لوحة الأدمن")


def admin_buttons_keyboard() -> ReplyKeyboardMarkup:
    rows = _dynamic_rows("admin_buttons")
    if not rows:
        rows = [
            ["✏️ تعديل الأزرار", "🎨 تعديل ألوان الأزرار"],
            ["➕ زر لوحة كيبورد", "➕ زر شفاف"],
            ["🗑️ الأزرار المحذوفة", "🔄 استرجاع الأزرار الافتراضية"],
            ["👑 لوحة الأدمن", "🏠 القائمة الرئيسية"],
        ]
    return rk(rows, "إدارة الأزرار")


def admin_button_edit_keyboard() -> ReplyKeyboardMarkup:
    rows = _dynamic_rows("admin_button_edit")
    if not rows:
        rows = [
            ["🗑️ حذف زر معين", "✏️ إعادة تسمية زر معين"],
            ["➕ إضافة زر معين"],
            ["↩️ رجوع إلى الأزرار", "👑 لوحة الأدمن"],
        ]
    return rk(rows, "تعديل الأزرار")


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
