from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from app.constants import POMODORO_PRESETS
from app.keyboards import focus_score_keyboard, pomodoro_keyboard
from app.services.timer_service import finish_timer, get_active_timer, record_focus_score, start_timer
from app.services.user_service import upsert_user
from app.utils.time_utils import human_minutes, minutes_between, now

router = Router()


@router.message(F.text == '⏱️ بومودورو')
async def pomodoro_home(message: Message) -> None:
    await upsert_user(message.from_user)
    await message.answer('⏱️ اختر نظام الجلسة. التنفيذ أهم من المزاج.', reply_markup=pomodoro_keyboard())


@router.message(F.text.in_({'▶️ 25/5', '▶️ 50/10', '▶️ 90/15'}))
async def start_preset(message: Message) -> None:
    user = await upsert_user(message.from_user)
    preset = message.text.replace('▶️ ', '').strip()
    focus, brk = POMODORO_PRESETS[preset]
    await start_timer(user['id'], focus, brk, 'focus')
    await message.answer(
        f'بدأت جلسة {focus} دقيقة.\n'
        'الأمر: الهاتف خارج اليد. لا تفاوض.\n'
        f'بعدها استراحة {brk} دقائق.'
    )


@router.message(F.text == '📌 حالة المؤقت')
async def timer_status(message: Message) -> None:
    user = await upsert_user(message.from_user)
    timer = await get_active_timer(user['id'])
    if not timer:
        await message.answer('لا يوجد مؤقت فعال.')
        return
    elapsed = minutes_between(timer['started_at'])
    total = int(timer['focus_minutes'] if timer['kind'] == 'focus' else timer['break_minutes'])
    remaining = max(0, total - elapsed)
    await message.answer(f'المؤقت: {timer["kind"]}\nالمتبقي: {human_minutes(remaining)}')


@router.message(F.text == '⏹️ أنهي الجلسة')
async def stop_timer(message: Message) -> None:
    user = await upsert_user(message.from_user)
    session_id = await finish_timer(user['id'], 'manual_finish')
    if not session_id:
        await message.answer('لا توجد جلسة فعالة حتى تنهيها.')
        return
    await message.answer('انتهت الجلسة. قيّم تركيزك من 1 إلى 5:', reply_markup=focus_score_keyboard(session_id))


@router.callback_query(F.data.startswith('focus:'))
async def focus_score(callback: CallbackQuery) -> None:
    _, session_id, score = callback.data.split(':')
    await record_focus_score(int(session_id), int(score))
    await callback.message.answer(f'تم تسجيل التركيز: {score}/5. استمر.')
    await callback.answer()


@router.callback_query(F.data.startswith('timer_done:'))
async def timer_done_callback(callback: CallbackQuery) -> None:
    _, timer_id, status = callback.data.split(':')
    user = await upsert_user(callback.from_user)
    session_id = await finish_timer(user['id'], status)
    if not session_id:
        await callback.answer('المؤقت غير موجود أو انتهى.', show_alert=True)
        return
    await callback.message.answer('سجلنا الجلسة. قيّم التركيز:', reply_markup=focus_score_keyboard(session_id))
    await callback.answer()
