from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.keyboards import subscription_keyboard
from app.services.access_service import has_access
from app.services.user_service import upsert_user


ALLOWED_TEXTS_WITHOUT_SUB = {
    '/start',
    '🧾 حالة اشتراكي',
    '📨 طلب اشتراك',
    '🆔 معرفي',
}


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get('event_from_user')
        if tg_user is None:
            return await handler(event, data)

        user = await upsert_user(tg_user)
        data['db_user'] = user

        if user['is_blocked']:
            if isinstance(event, Message):
                await event.answer('تم حظرك من استخدام البوت.')
            elif isinstance(event, CallbackQuery):
                await event.answer('تم حظرك من استخدام البوت.', show_alert=True)
            return None

        if await has_access(user):
            return await handler(event, data)

        if isinstance(event, Message):
            text = (event.text or '').strip()
            if text in ALLOWED_TEXTS_WITHOUT_SUB or text.startswith('/start'):
                return await handler(event, data)
            await event.answer(
                'البوت مقفل لأن اشتراكك غير مفعل.\n'
                f'معرفك الرقمي: <code>{tg_user.id}</code>\n'
                'أرسله للمدير حتى يفعّل لك اشتراك شهري/٣ أشهر/٦ أشهر/سنوي.',
                reply_markup=subscription_keyboard(),
            )
            return None

        if isinstance(event, CallbackQuery):
            await event.answer('اشتراكك غير مفعل بعد.', show_alert=True)
            return None

        return None
