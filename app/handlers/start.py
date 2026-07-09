from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.config import settings
from app.keyboards import main_keyboard, subscription_keyboard
from app.services.access_service import create_subscription_request, has_access, subscription_status_text
from app.services.user_service import upsert_user

router = Router()


WELCOME_ACTIVE = '''
🧑‍✈️ Study Commander Bot جاهز.

هذا ليس بوت كلام. هذا نظام تنفيذ:
- يحسب ساعاتك الصافية.
- ينظم موادك وملازمك.
- يشغل بومودورو.
- يسجل الأكل والماء.
- يطلع تقارير وشهادات.
- يعطيك وضع إنقاذ إذا اليوم خرب.
- يختبر كل الميزات فورًا عبر زر 🧪 تجربة الخدمات.

الأمر الأول: اختر من لوحة الكيبورد.
'''

WELCOME_LOCKED = '''
Study Commander Bot موجود، لكن حسابك غير مفعل بعد.

أرسل معرفك الرقمي للمدير حتى يفتح لك الاشتراك.
'''


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await upsert_user(message.from_user)
    if user['is_blocked']:
        await message.answer('تم حظرك من استخدام البوت.')
        return

    is_admin = message.from_user.id in settings.admin_ids or user['role'] == 'admin'
    if await has_access(user):
        await message.answer(WELCOME_ACTIVE, reply_markup=main_keyboard(is_admin))
        return

    await message.answer(
        WELCOME_LOCKED + f'\nمعرفك الرقمي: <code>{message.from_user.id}</code>',
        reply_markup=subscription_keyboard(),
    )


@router.message(F.text == '⬅️ رجوع')
async def go_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await upsert_user(message.from_user)
    if await has_access(user):
        await message.answer('تم الرجوع للوحة الرئيسية.', reply_markup=main_keyboard(user['role'] == 'admin'))
    else:
        await message.answer('تم الرجوع للوحة الاشتراك.', reply_markup=subscription_keyboard())


@router.message(F.text == '🧾 حالة اشتراكي')
async def sub_status(message: Message) -> None:
    user = await upsert_user(message.from_user)
    await message.answer(await subscription_status_text(user), reply_markup=main_keyboard(user['role'] == 'admin') if await has_access(user) else subscription_keyboard())


@router.message(F.text == '🆔 معرفي')
async def my_id(message: Message) -> None:
    await message.answer(f'معرفك الرقمي:\n<code>{message.from_user.id}</code>')


@router.message(F.text == '📨 طلب اشتراك')
async def request_subscription(message: Message) -> None:
    user = await upsert_user(message.from_user)
    request_id = await create_subscription_request(user['id'], 'طلب من داخل البوت')
    await message.answer(
        f'تم تسجيل طلب الاشتراك رقم {request_id}.\n'
        f'أرسل هذا المعرف للمدير: <code>{message.from_user.id}</code>\n'
        'بعد الدفع، المدير يفعّل اشتراكك من لوحة الأدمن.'
    )


@router.message(F.text == '⚙️ الإعدادات')
async def settings_view(message: Message) -> None:
    user = await upsert_user(message.from_user)
    await message.answer(
        '⚙️ الإعدادات الحالية:\n'
        f'- التوقيت: {settings.timezone_name}\n'
        '- الوضع الافتراضي: صارم\n'
        '- بومودورو افتراضي: 50/10\n'
        '- الاشتراك: ' + ('Admin/Active' if await has_access(user) else 'غير مفعل') + '\n\n'
        'التعديل التفصيلي يتم من لوحة البوت أو قاعدة البيانات.'
    )
