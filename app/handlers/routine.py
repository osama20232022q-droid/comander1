from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.db import db, dt_iso
from app.keyboards import back_keyboard, routine_keyboard
from app.services.routine_service import active_trial, start_routine_trial
from app.services.user_service import upsert_user
from app.states import RoutineStates, SleepStates
from app.utils.time_utils import today

router = Router()


@router.message(F.text == '🛌 النوم والنظام')
async def routine_home(message: Message) -> None:
    user = await upsert_user(message.from_user)
    trial = await active_trial(user['id'])
    text = '🛌 نظام النوم والتجارب. لا نحكم على نظام جديد قبل 7 أيام.'
    if trial:
        text += f'\n\nتجربة فعالة: {trial["name"]}\nالنوم: {trial["sleep_time"]}\nالاستيقاظ: {trial["wake_time"]}\nتنتهي: {trial["end_date"]}'
    await message.answer(text, reply_markup=routine_keyboard())


@router.message(F.text.in_({'🌅 تجربة نظام صباحي', '🌙 تجربة نظام ليلي'}))
async def routine_trial_start(message: Message, state: FSMContext) -> None:
    name = 'Morning Routine Trial' if 'صباحي' in message.text else 'Night Routine Trial'
    await state.update_data(name=name)
    await state.set_state(RoutineStates.waiting_sleep)
    await message.answer('اكتب وقت النوم بصيغة HH:MM. مثال: 21:30', reply_markup=back_keyboard())


@router.message(RoutineStates.waiting_sleep)
async def routine_sleep(message: Message, state: FSMContext) -> None:
    await state.update_data(sleep_time=message.text.strip())
    await state.set_state(RoutineStates.waiting_wake)
    await message.answer('اكتب وقت الاستيقاظ بصيغة HH:MM. مثال: 04:30')


@router.message(RoutineStates.waiting_wake)
async def routine_wake(message: Message, state: FSMContext) -> None:
    await state.update_data(wake_time=message.text.strip())
    await state.set_state(RoutineStates.waiting_days)
    await message.answer('مدة التجربة كم يوم؟ أنصح: 7 أو 14')


@router.message(RoutineStates.waiting_days)
async def routine_done(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    days = int(message.text.strip()) if message.text.strip().isdigit() else 7
    user = await upsert_user(message.from_user)
    await start_routine_trial(user['id'], data['name'], data['sleep_time'], data['wake_time'], days, 'قياس ساعات الدراسة والتركيز والهاتف')
    await state.clear()
    await message.answer(
        f'✅ بدأت تجربة النظام: {data["name"]}\n'
        f'النوم: {data["sleep_time"]}\nالاستيقاظ: {data["wake_time"]}\n'
        f'المدة: {days} أيام\n\n'
        'القاعدة: لا تحكم على النظام قبل نهاية التجربة.',
        reply_markup=routine_keyboard(),
    )


@router.message(F.text == '🛌 سجل نوم')
async def sleep_log_start(message: Message, state: FSMContext) -> None:
    await state.set_state(SleepStates.waiting_sleep_log)
    await message.answer(
        'اكتب سجل النوم بصيغة:\n'
        'نمت 22:30 كعدت 04:40 جودة 4\n\n'
        'أو اكتب عدد الساعات فقط مثل: 6.5',
        reply_markup=back_keyboard(),
    )


@router.message(SleepStates.waiting_sleep_log)
async def sleep_log_save(message: Message, state: FSMContext) -> None:
    user = await upsert_user(message.from_user)
    text = message.text.strip()
    hours = None
    slept_at = None
    woke_at = None
    quality = None
    parts = text.replace('،', ' ').split()
    for i, part in enumerate(parts):
        if part.replace('.', '', 1).isdigit() and hours is None:
            value = float(part)
            if 0 < value <= 16:
                hours = value
        if ':' in part and slept_at is None:
            slept_at = part
        elif ':' in part and slept_at is not None and woke_at is None:
            woke_at = part
        if part == 'جودة' and i + 1 < len(parts) and parts[i + 1].isdigit():
            quality = int(parts[i + 1])
    async with db.connect() as conn:
        await conn.execute(
            '''INSERT INTO sleep_logs(user_id,sleep_date,slept_at,woke_at,hours,quality,note,created_at)
               VALUES(?,?,?,?,?,?,?,?)''',
            (user['id'], today().isoformat(), slept_at, woke_at, hours, quality, text, dt_iso()),
        )
    await state.clear()
    await message.answer('تم تسجيل النوم. البوت سيستخدمه في تقييم الطاقة والروتين.', reply_markup=routine_keyboard())


@router.message(F.text == '📈 تقييم النظام')
async def routine_eval(message: Message) -> None:
    user = await upsert_user(message.from_user)
    trial = await active_trial(user['id'])
    async with db.connect() as conn:
        sleep_rows = await conn.execute_fetchall(
            'SELECT * FROM sleep_logs WHERE user_id=? ORDER BY id DESC LIMIT 7',
            (user['id'],),
        )
        sessions = await conn.execute_fetchall(
            'SELECT COALESCE(SUM(duration_minutes),0) AS m, COUNT(*) AS c FROM sessions WHERE user_id=?',
            (user['id'],),
        )
    avg_sleep = None
    values = [float(r['hours']) for r in sleep_rows if r['hours']]
    if values:
        avg_sleep = sum(values) / len(values)
    text = ''
    if trial:
        text += (
            f'التجربة الحالية: {trial["name"]}\n'
            f'من {trial["start_date"]} إلى {trial["end_date"]}\n'
            f'النوم المستهدف: {trial["sleep_time"]} | الاستيقاظ: {trial["wake_time"]}\n\n'
        )
    else:
        text += 'لا توجد تجربة فعالة. ابدأ تجربة صباحية أو ليلية أولًا.\n\n'
    text += f'- مجموع الدراسة المسجلة: {int(sessions[0]["m"] or 0)} دقيقة\n'
    text += f'- عدد الجلسات: {int(sessions[0]["c"] or 0)}\n'
    text += f'- متوسط النوم المسجل: {avg_sleep:.1f} ساعة\n' if avg_sleep else '- لا يوجد نوم كافٍ مسجل بعد.\n'
    text += '\nقرار البوت: لا تغيّر النظام يوميًا. قيّمه بعد 7 أيام على الأقل.'
    await message.answer(text)
