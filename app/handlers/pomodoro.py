from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select, func
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.db import get_session
from app.models import User, PomodoroSession, FoodLog
from app.keyboards import pomodoro_keyboard, nav_keyboard
from app.services.break_engine import build_break_recommendation
from app.services.calories import estimate_calories
from app.utils import local_now


def _current_user(db, tg_id: int) -> User | None:
    return db.scalar(select(User).where(User.telegram_id == tg_id))


async def show_pomodoro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "⏳ البومودورو الذكي\nاختر نظام الدراسة/الراحة:",
        reply_markup=pomodoro_keyboard(),
    )


async def handle_pomo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    q = update.callback_query
    await q.answer()
    if data == "pomo:custom":
        context.user_data["flow"] = "pomo_custom"
        await q.message.reply_text("اكتب وقت الدراسة ووقت الراحة بالدقائق. مثال: 70 12", reply_markup=nav_keyboard())
        return
    if data.startswith("pomo:start:"):
        _, _, study, brk = data.split(":")
        await start_pomodoro(q.message, context, q.from_user.id, int(study), int(brk))
        return
    if data.startswith("pomo:done:"):
        sid = int(data.split(":")[-1])
        await finish_pomodoro(q.message, context, q.from_user.id, sid)
        return
    if data.startswith("pomo:food:"):
        sid = int(data.split(":")[-1])
        context.user_data["flow"] = "food_log"
        context.user_data["food_session_id"] = sid
        await q.message.reply_text("شنو أكلت أو شربت؟ اكتبها بجملة واحدة. إذا ما أكلت اكتب: لا")
        return


async def handle_custom_pomo(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    nums = [int(x) for x in text.replace(",", " ").split() if x.isdigit()]
    if len(nums) < 2:
        await update.effective_message.reply_text("اكتب رقمين: وقت الدراسة ووقت الراحة. مثال: 70 12")
        return
    study, brk = nums[0], nums[1]
    if not (5 <= study <= 180 and 1 <= brk <= 60):
        await update.effective_message.reply_text("المدى المقبول: الدراسة 5-180 دقيقة، الراحة 1-60 دقيقة.")
        return
    context.user_data.clear()
    await start_pomodoro(update.effective_message, context, update.effective_user.id, study, brk)


async def start_pomodoro(message, context: ContextTypes.DEFAULT_TYPE, tg_id: int, study_minutes: int, break_minutes: int) -> None:
    with get_session() as db:
        user = _current_user(db, tg_id)
        session = PomodoroSession(user_id=user.id, study_minutes=study_minutes, break_minutes=break_minutes)
        db.add(session)
        db.commit()
        db.refresh(session)
        sid = session.id
    end_at = local_now().strftime("%H:%M")
    await message.reply_text(
        f"⏳ بدأت جلسة الدراسة.\n"
        f"الدراسة: {study_minutes} دقيقة\nالراحة: {break_minutes} دقيقة\n"
        f"الوقت المحلي الآن: {end_at}\n\n"
        "قاعدة الجلسة: لا هاتف، لا تفاوض، ناتج واضح.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ أنهيت الجلسة", callback_data=f"pomo:done:{sid}")]])
    )
    if context.job_queue:
        context.job_queue.run_once(pomodoro_time_up, when=study_minutes*60, data={"chat_id": message.chat_id, "user_id": tg_id, "session_id": sid}, name=f"pomo_{sid}")


async def pomodoro_time_up(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data
    chat_id = data["chat_id"]
    tg_id = data["user_id"]
    sid = data["session_id"]
    await finish_pomodoro_by_ids(context, chat_id, tg_id, sid, auto=True)


async def finish_pomodoro(message, context: ContextTypes.DEFAULT_TYPE, tg_id: int, sid: int) -> None:
    await finish_pomodoro_by_ids(context, message.chat_id, tg_id, sid, auto=False)


async def finish_pomodoro_by_ids(context: ContextTypes.DEFAULT_TYPE, chat_id: int, tg_id: int, sid: int, auto: bool = False) -> None:
    with get_session() as db:
        user = _current_user(db, tg_id)
        session = db.get(PomodoroSession, sid)
        if not session or session.user_id != user.id:
            await context.bot.send_message(chat_id, "الجلسة غير موجودة.")
            return
        if session.status != "finished":
            session.status = "finished"
            session.ended_at = datetime.now(timezone.utc)
            # cycle number = sessions finished today roughly
            cycle = db.scalar(select(func.count()).select_from(PomodoroSession).where(PomodoroSession.user_id == user.id, PomodoroSession.status == "finished")) or 1
            rec = build_break_recommendation(cycle, session.break_minutes)
            session.break_recommendation = rec
            user.pending_food_session_id = sid
            db.commit()
        else:
            rec = session.break_recommendation or build_break_recommendation(1, session.break_minutes)
    await context.bot.send_message(
        chat_id,
        f"✅ انتهت جلسة الدراسة.\n\nاستراحة {session.break_minutes} دقيقة:\n{rec}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🍽️ سجل ما أكلت", callback_data=f"pomo:food:{sid}")]])
    )


async def handle_food_log(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    sid = context.user_data.get("food_session_id")
    if text.strip() in ["لا", "ما اكلت", "لم آكل", "none"]:
        desc = "لم يأكل"
    else:
        desc = text.strip()
    mn, mx, matches = estimate_calories(desc)
    with get_session() as db:
        user = _current_user(db, update.effective_user.id)
        log = FoodLog(user_id=user.id, session_id=sid, description=desc, calories_min=mn, calories_max=mx)
        user.pending_food_session_id = None
        db.add(log)
        db.commit()
    context.user_data.clear()
    if mn is None:
        await update.effective_message.reply_text("تم تسجيل الأكل. لم أستطع حساب السعرات بدقة، لكنه محفوظ في التقرير.")
    else:
        await update.effective_message.reply_text(f"تم التسجيل. السعرات التقريبية: {mn}-{mx} kcal.\nالمطابقات: {', '.join(matches[:6])}")
