from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.db import db
from app.handlers import admin, certificates, demo, files, food, pomodoro, reports, rescue, routine, start, subjects
from app.keyboards import timer_done_keyboard
from app.middlewares import AccessMiddleware
from app.services.access_service import expiring_subscriptions
from app.services.timer_service import due_timers, mark_timer_notified

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger(__name__)


async def notify_due_timers(bot: Bot) -> None:
    timers = await due_timers()
    for timer in timers:
        try:
            if timer['kind'] == 'focus':
                text = (
                    'انتهت جلسة الدراسة.\n'
                    'قيّم التنفيذ بصدق.\n'
                    'إذا هذه ثاني دورة: مشي إجباري 7 دقائق + ماء.'
                )
            else:
                text = 'انتهت الاستراحة. ارجع للجلسة التالية الآن.'
            await bot.send_message(timer['tg_id'], text, reply_markup=timer_done_keyboard(timer['id']))
            await mark_timer_notified(timer['id'])
        except Exception as exc:  # pragma: no cover
            logger.exception('Could not notify timer %s: %s', timer['id'], exc)


async def notify_expiring_subscriptions(bot: Bot) -> None:
    for sub in await expiring_subscriptions(days=2):
        try:
            await bot.send_message(
                sub['tg_id'],
                f'تنبيه اشتراك: اشتراكك ({sub["plan"]}) ينتهي بتاريخ {sub["end_at"]}.\n'
                'راسل المدير للتجديد إذا تريد استمرار الخدمة.'
            )
        except Exception as exc:  # pragma: no cover
            logger.exception('Could not notify subscription %s: %s', sub.get('tg_id'), exc)


async def main() -> None:
    if not settings.bot_token:
        raise RuntimeError('BOT_TOKEN is missing. Copy .env.example to .env and set BOT_TOKEN.')
    await db.migrate()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    access_middleware = AccessMiddleware()
    dp.message.middleware(access_middleware)
    dp.callback_query.middleware(access_middleware)

    for router in (
        start.router,
        subjects.router,
        files.router,
        pomodoro.router,
        food.router,
        routine.router,
        rescue.router,
        reports.router,
        certificates.router,
        demo.router,
        admin.router,
    ):
        dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone=settings.timezone_name)
    scheduler.add_job(notify_due_timers, 'interval', seconds=30, args=[bot], id='timer_notifications')
    scheduler.add_job(notify_expiring_subscriptions, 'interval', hours=12, args=[bot], id='subscription_expiry_notifications')
    scheduler.start()

    logger.info('Study Commander Bot started in timezone %s', settings.timezone_name)
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
