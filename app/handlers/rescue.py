from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message

from app.services.planner import rescue_plan
from app.services.user_service import upsert_user

router = Router()


@router.message(F.text == '🚨 أنقذ يومي')
async def rescue_day(message: Message) -> None:
    user = await upsert_user(message.from_user)
    await message.answer(await rescue_plan(user['id'], remaining_minutes=240, energy='متوسط'))
