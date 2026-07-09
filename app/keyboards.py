from __future__ import annotations

from telegram import ReplyKeyboardMarkup


def rk(rows: list[list[str]], placeholder: str = "اختر أمرًا") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False, input_field_placeholder=placeholder)


def main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        ["📚 المواد", "🧠 خطة دراسية معمقة"],
        ["⏳ البومودورو", "⌛ كم المتبقي؟"],
        ["🔥 حفزني", "📊 تقدمي"],
        ["🏅 شهاداتي", "👤 ملفي"],
        ["❓ ماذا يفعل هذا البوت؟"],
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
    return rk([
        ["👥 طلبات التفعيل", "➕ تفعيل مشترك"],
        ["📋 المستخدمون", "🚫 حظر مستخدم"],
        ["✅ إلغاء الحظر", "📦 نسخة احتياطية الآن"],
        ["♻️ فحص ملف استرجاع", "☁️ حالة قاعدة البيانات"],
        ["🏠 القائمة الرئيسية"],
    ], "لوحة الأدمن")
