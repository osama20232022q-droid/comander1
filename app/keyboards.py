from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from app.config import settings


def main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        ["📚 المواد", "🧠 خطة دراسية معمقة"],
        ["⏳ البومودورو", "🔥 حفزني"],
        ["📊 تقدمي", "🏅 شهاداتي"],
        ["👤 ملفي"],
    ]
    if is_admin:
        rows.append(["👑 لوحة الأدمن"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, input_field_placeholder="اختر أمرًا")


def nav_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["↩️ خطوة للوراء", "🏠 القائمة الرئيسية"]], resize_keyboard=True)


def confirm_back_keyboard(confirm_cb: str, back_cb: str = "back") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 تأكيد", callback_data=confirm_cb)],
        [InlineKeyboardButton("🔴 رجوع للتعديل", callback_data=back_cb)],
    ])


def subject_actions_keyboard(subject_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📎 رفع ملحقات المادة", callback_data=f"subject:upload:material:{subject_id}")],
        [InlineKeyboardButton("📘 رفع أسئلة سنوات", callback_data=f"subject:upload:past_question:{subject_id}")],
        [InlineKeyboardButton("📂 عرض الملحقات", callback_data=f"subject:list:material:{subject_id}")],
        [InlineKeyboardButton("📚 عرض أسئلة السنوات", callback_data=f"subject:list:past_question:{subject_id}")],
        [InlineKeyboardButton("🧠 تحليل سريع", callback_data=f"subject:analyze:{subject_id}")],
        [InlineKeyboardButton("↩️ خطوة للوراء", callback_data="subject:menu")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="home")],
    ])


def plan_choice_keyboard(prefix: str, values: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for v in values:
        rows.append([InlineKeyboardButton(v, callback_data=f"{prefix}:{v}")])
    rows.append([InlineKeyboardButton("🔴 رجوع", callback_data="plan:back")])
    return InlineKeyboardMarkup(rows)


def pomodoro_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("25 دراسة / 5 راحة", callback_data="pomo:start:25:5")],
        [InlineKeyboardButton("50 دراسة / 10 راحة", callback_data="pomo:start:50:10")],
        [InlineKeyboardButton("90 دراسة / 15 راحة", callback_data="pomo:start:90:15")],
        [InlineKeyboardButton("وقت مخصص", callback_data="pomo:custom")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="home")],
    ])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 طلبات التفعيل", callback_data="admin:pending")],
        [InlineKeyboardButton("📋 المستخدمون", callback_data="admin:users")],
        [InlineKeyboardButton("📦 نسخة احتياطية الآن", callback_data="admin:backup")],
        [InlineKeyboardButton("♻️ استرجاع من ملف", callback_data="admin:restore")],
        [InlineKeyboardButton("☁️ حالة قاعدة البيانات", callback_data="admin:db_status")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="home")],
    ])
