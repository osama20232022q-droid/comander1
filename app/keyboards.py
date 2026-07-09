from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text='📋 يومي'), KeyboardButton(text='📚 المواد')],
        [KeyboardButton(text='⏱️ بومودورو'), KeyboardButton(text='🍽️ أكل وماء')],
        [KeyboardButton(text='🛌 النوم والنظام'), KeyboardButton(text='🚨 أنقذ يومي')],
        [KeyboardButton(text='📊 التقارير'), KeyboardButton(text='🏅 الشهادات')],
        [KeyboardButton(text='🧪 تجربة الخدمات'), KeyboardButton(text='⚙️ الإعدادات')],
    ]
    if is_admin:
        rows.append([KeyboardButton(text='🧑‍✈️ الأدمن')])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder='اختر من لوحة الأوامر')


def subscription_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='🧾 حالة اشتراكي'), KeyboardButton(text='📨 طلب اشتراك')],
            [KeyboardButton(text='🆔 معرفي')],
        ],
        resize_keyboard=True,
        input_field_placeholder='اشتراكك غير مفعل بعد',
    )


def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='🔐 تفعيل اشتراك'), KeyboardButton(text='⛔️ إيقاف اشتراك')],
            [KeyboardButton(text='قائمة المستخدمين'), KeyboardButton(text='📊 إحصائيات الأدمن')],
            [KeyboardButton(text='حظر'), KeyboardButton(text='إلغاء حظر')],
            [KeyboardButton(text='🧪 تجربة الخدمات'), KeyboardButton(text='⬅️ رجوع')],
        ],
        resize_keyboard=True,
        input_field_placeholder='لوحة الأدمن',
    )


def subscription_plan_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='شهري'), KeyboardButton(text='٣ أشهر')],
            [KeyboardButton(text='٦ أشهر'), KeyboardButton(text='سنوي')],
            [KeyboardButton(text='٧ أيام تجربة'), KeyboardButton(text='⬅️ رجوع')],
        ],
        resize_keyboard=True,
    )


def paid_confirmation_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='✅ دفع'), KeyboardButton(text='❌ لم يدفع')],
            [KeyboardButton(text='⬅️ رجوع')],
        ],
        resize_keyboard=True,
    )


def back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='⬅️ رجوع')]], resize_keyboard=True)


def subjects_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='➕ إضافة مادة'), KeyboardButton(text='📖 عرض المواد')],
            [KeyboardButton(text='➕ إضافة ملزمة'), KeyboardButton(text='📎 رفع ملزمة PDF')],
            [KeyboardButton(text='🧠 حلل الخطة'), KeyboardButton(text='⬅️ رجوع')],
        ],
        resize_keyboard=True,
    )


def pomodoro_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='▶️ 25/5'), KeyboardButton(text='▶️ 50/10'), KeyboardButton(text='▶️ 90/15')],
            [KeyboardButton(text='⏹️ أنهي الجلسة'), KeyboardButton(text='📌 حالة المؤقت')],
            [KeyboardButton(text='⬅️ رجوع')],
        ],
        resize_keyboard=True,
    )


def food_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='🍱 سجل أكل'), KeyboardButton(text='💧 ماء 250ml'), KeyboardButton(text='💧 ماء 500ml')],
            [KeyboardButton(text='📊 ملخص الطاقة'), KeyboardButton(text='⬅️ رجوع')],
        ],
        resize_keyboard=True,
    )


def routine_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='🌅 تجربة نظام صباحي'), KeyboardButton(text='🌙 تجربة نظام ليلي')],
            [KeyboardButton(text='🛌 سجل نوم'), KeyboardButton(text='📈 تقييم النظام')],
            [KeyboardButton(text='⬅️ رجوع')],
        ],
        resize_keyboard=True,
    )


def demo_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='🧪 تشغيل تجربة كاملة')],
            [KeyboardButton(text='📊 التقارير'), KeyboardButton(text='🏅 الشهادات')],
            [KeyboardButton(text='⬅️ رجوع')],
        ],
        resize_keyboard=True,
    )


def focus_score_keyboard(session_id: int) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=str(i), callback_data=f'focus:{session_id}:{i}') for i in range(1, 6)]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def timer_done_keyboard(timer_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ أنهيت بتركيز', callback_data=f'timer_done:{timer_id}:ok')],
        [InlineKeyboardButton(text='😵 تعبت/مو مركز', callback_data=f'timer_done:{timer_id}:tired')],
        [InlineKeyboardButton(text='📵 ضيعت وقت', callback_data=f'timer_done:{timer_id}:wasted')],
    ])


def yes_no_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='نعم ✅', callback_data=f'{prefix}:yes'), InlineKeyboardButton(text='لا ❌', callback_data=f'{prefix}:no')]
    ])
