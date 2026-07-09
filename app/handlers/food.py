from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.keyboards import back_keyboard, food_keyboard
from app.services.food_service import log_food, log_water, today_energy_summary
from app.services.user_service import upsert_user
from app.states import FoodStates
from app.utils.time_utils import today

router = Router()


@router.message(F.text == '🍽️ أكل وماء')
async def food_home(message: Message) -> None:
    await upsert_user(message.from_user)
    await message.answer('🍽️ سجل الطاقة. الطالب جسم + عقل، وليس ملف PDF فقط.', reply_markup=food_keyboard())


@router.message(F.text == '🍱 سجل أكل')
async def food_start(message: Message, state: FSMContext) -> None:
    await state.set_state(FoodStates.waiting_food)
    await message.answer('اكتب شنو أكلت. مثال: صحن تمن + تونة + نصف صدر دجاج', reply_markup=back_keyboard())


@router.message(FoodStates.waiting_food)
async def food_save(message: Message, state: FSMContext) -> None:
    user = await upsert_user(message.from_user)
    data = await log_food(user['id'], message.text)
    await state.clear()
    await message.answer(
        f'تم تسجيل الأكل.\nالسعرات التقريبية: {data["calories_min"]}-{data["calories_max"]} kcal\n'
        f'ملاحظة: {data["note"]}',
        reply_markup=food_keyboard(),
    )


@router.message(F.text.in_({'💧 ماء 250ml', '💧 ماء 500ml'}))
async def water_save(message: Message) -> None:
    user = await upsert_user(message.from_user)
    ml = 500 if '500' in message.text else 250
    await log_water(user['id'], ml)
    await message.answer(f'تم تسجيل ماء: {ml}ml. جيد. كمل.')


@router.message(F.text == '📊 ملخص الطاقة')
async def energy_summary(message: Message) -> None:
    user = await upsert_user(message.from_user)
    data = await today_energy_summary(user['id'], today().isoformat())
    await message.answer(
        f'📊 ملخص اليوم:\n'
        f'- الأكل المسجل: {data["food_count"]}\n'
        f'- السعرات التقريبية: {data["calories_min"]}-{data["calories_max"]} kcal\n'
        f'- الماء: {data["water_ml"]}ml\n\n'
        'بعد كل دورتين: مشي 7 دقائق + ماء. هذا أمر، مو اقتراح.'
    )
