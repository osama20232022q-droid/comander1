from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.keyboards import back_keyboard
from app.services.discipline import pattern_summary, record_event
from app.services.report_service import save_daily_report
from app.services.user_service import upsert_user
from app.states import ReportStates
from app.utils.time_utils import human_minutes, today

router = Router()


@router.message(F.text == '📊 التقارير')
async def reports_home(message: Message) -> None:
    user = await upsert_user(message.from_user)
    data = await save_daily_report(user['id'], today())
    patterns = await pattern_summary(user['id'])
    await message.answer(
        f'📊 تقرير اليوم:\n'
        f'- دراسة صافية: {human_minutes(data["study_minutes"])}\n'
        f'- المخطط التقريبي: {human_minutes(data["planned_minutes"])}\n'
        f'- Discipline Score: {data["discipline_score"]}/100\n\n'
        f'سجل المخالفات:\n{patterns}\n\n'
        'إذا ضاع وقت اليوم، اكتب: سجل تأخير'
    )


@router.message(F.text == 'سجل تأخير')
async def delay_start(message: Message, state: FSMContext) -> None:
    await state.set_state(ReportStates.waiting_delay_reason)
    await message.answer('اكتب السبب الحقيقي للتأخير. لا تكتب عذر عام.', reply_markup=back_keyboard())


@router.message(ReportStates.waiting_delay_reason)
async def delay_save(message: Message, state: FSMContext) -> None:
    user = await upsert_user(message.from_user)
    result = await record_event(user['id'], 'delay', message.text)
    await state.clear()
    await message.answer(
        f'تم تسجيل السبب.\n'
        f'التصنيف: {result["classification"]}\n'
        f'الإجراء: {result["action"]}'
    )
