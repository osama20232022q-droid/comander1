from __future__ import annotations

from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from telegram import Update
from telegram.ext import ContextTypes
from app.db import get_session
from app.models import User, PomodoroSession, FoodLog
from app.keyboards import pomodoro_menu_keyboard, pomodoro_running_keyboard, nav_keyboard
from app.services.break_engine import build_break_recommendation
from app.services.calories import estimate_calories


def _current_user(db, tg_id: int) -> User | None:
    return db.scalar(select(User).where(User.telegram_id == tg_id))


def _active_session(db, user_id: int) -> PomodoroSession | None:
    return db.scalar(select(PomodoroSession).where(PomodoroSession.user_id == user_id, PomodoroSession.status == "running").order_by(PomodoroSession.started_at.desc()))


def _bar(done_ratio: float, width: int = 12) -> str:
    done = max(0, min(width, int(done_ratio * width)))
    return "█" * done + "░" * (width - done)


def _ensure_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def show_pomodoro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "⏳ البومودورو الذكي\nاختر نظام الدراسة/الراحة من لوحة الكيبورد.\nبعد بدء الجلسة استخدم زر ⌛ كم المتبقي؟ لرؤية الثواني والتقدم.",
        reply_markup=pomodoro_menu_keyboard(),
    )


async def handle_pomodoro_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    if text == "25 دراسة / 5 راحة":
        context.user_data["pomo_choice"] = (25, 5)
        await update.effective_message.reply_text("تم اختيار 25/5. اضغط ▶️ ابدأ.", reply_markup=pomodoro_menu_keyboard())
        return True
    if text == "50 دراسة / 10 راحة":
        context.user_data["pomo_choice"] = (50, 10)
        await update.effective_message.reply_text("تم اختيار 50/10. اضغط ▶️ ابدأ.", reply_markup=pomodoro_menu_keyboard())
        return True
    if text == "90 دراسة / 15 راحة":
        context.user_data["pomo_choice"] = (90, 15)
        await update.effective_message.reply_text("تم اختيار 90/15. اضغط ▶️ ابدأ.", reply_markup=pomodoro_menu_keyboard())
        return True
    if text == "وقت مخصص":
        context.user_data["flow"] = "pomo_custom"
        await update.effective_message.reply_text("اكتب وقت الدراسة ووقت الراحة بالدقائق. مثال: 70 12", reply_markup=nav_keyboard())
        return True
    if text == "▶️ ابدأ":
        study, brk = context.user_data.get("pomo_choice", (25, 5))
        await start_pomodoro(update.effective_message, context, update.effective_user.id, int(study), int(brk))
        return True
    if text == "⌛ كم المتبقي؟":
        await show_remaining(update, context)
        return True
    if text == "✅ أنهيت الجلسة":
        await finish_active_session(update, context)
        return True
    if text == "🍽️ سجل الأكل":
        context.user_data["flow"] = "food_log"
        await update.effective_message.reply_text("شنو أكلت أو شربت؟ اكتبها بجملة واحدة. إذا ما أكلت اكتب: لا", reply_markup=nav_keyboard())
        return True
    return False


async def handle_custom_pomo(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    nums = [int(x) for x in text.replace(",", " ").split() if x.isdigit()]
    if len(nums) < 2:
        await update.effective_message.reply_text("اكتب رقمين: وقت الدراسة ووقت الراحة. مثال: 70 12")
        return
    study, brk = nums[0], nums[1]
    if not (5 <= study <= 180 and 1 <= brk <= 60):
        await update.effective_message.reply_text("المدى المقبول: الدراسة 5-180 دقيقة، الراحة 1-60 دقيقة.")
        return
    context.user_data.pop("flow", None)
    context.user_data["pomo_choice"] = (study, brk)
    await update.effective_message.reply_text(f"تم اختيار {study}/{brk}. اضغط ▶️ ابدأ.", reply_markup=pomodoro_menu_keyboard())


async def start_pomodoro(message, context: ContextTypes.DEFAULT_TYPE, tg_id: int, study_minutes: int, break_minutes: int) -> None:
    with get_session() as db:
        user = _current_user(db, tg_id)
        active = _active_session(db, user.id)
        if active:
            await message.reply_text("عندك جلسة تعمل حاليًا. استخدم ⌛ كم المتبقي؟ أو ✅ أنهيت الجلسة.", reply_markup=pomodoro_running_keyboard())
            return
        session = PomodoroSession(user_id=user.id, study_minutes=study_minutes, break_minutes=break_minutes)
        db.add(session)
        db.commit()
        db.refresh(session)
        sid = session.id
    await message.reply_text(
        f"⏳ بدأت جلسة الدراسة.\n"
        f"الدراسة: {study_minutes} دقيقة\nالراحة: {break_minutes} دقيقة\n\n"
        "استخدم زر ⌛ كم المتبقي؟ حتى تشوف الوقت بالثواني والتقدم.",
        reply_markup=pomodoro_running_keyboard(),
    )
    if context.job_queue:
        context.job_queue.run_once(pomodoro_time_up, when=study_minutes*60, data={"chat_id": message.chat_id, "user_id": tg_id, "session_id": sid}, name=f"pomo_{sid}")


async def show_remaining(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        user = _current_user(db, update.effective_user.id)
        session = _active_session(db, user.id) if user else None
    if not session:
        await update.effective_message.reply_text("لا توجد جلسة بومودورو تعمل الآن.", reply_markup=pomodoro_menu_keyboard())
        return
    start = _ensure_aware(session.started_at)
    total = session.study_minutes * 60
    elapsed = max(0, int((datetime.now(timezone.utc) - start).total_seconds()))
    remaining = max(0, total - elapsed)
    ratio = min(1.0, elapsed / total if total else 1)
    mm, ss = divmod(remaining, 60)
    em, es = divmod(elapsed, 60)
    await update.effective_message.reply_text(
        f"⌛ المتبقي: {mm:02d}:{ss:02d}\n"
        f"⏱️ المنجز: {em:02d}:{es:02d}\n"
        f"📈 التقدم: {_bar(ratio)} {int(ratio*100)}%\n"
        f"الدراسة: {session.study_minutes} دقيقة — الراحة: {session.break_minutes} دقيقة",
        reply_markup=pomodoro_running_keyboard(),
    )


async def finish_active_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        user = _current_user(db, update.effective_user.id)
        session = _active_session(db, user.id) if user else None
        if not session:
            await update.effective_message.reply_text("لا توجد جلسة تعمل الآن.", reply_markup=pomodoro_menu_keyboard())
            return
        sid = session.id
    await finish_pomodoro_by_ids(context, update.effective_chat.id, update.effective_user.id, sid, auto=False)


async def pomodoro_time_up(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data
    await finish_pomodoro_by_ids(context, data["chat_id"], data["user_id"], data["session_id"], auto=True)


async def finish_pomodoro_by_ids(context: ContextTypes.DEFAULT_TYPE, chat_id: int, tg_id: int, sid: int, auto: bool = False) -> None:
    with get_session() as db:
        user = _current_user(db, tg_id)
        session = db.get(PomodoroSession, sid)
        if not session or not user or session.user_id != user.id:
            await context.bot.send_message(chat_id, "الجلسة غير موجودة.")
            return
        if session.status != "finished":
            session.status = "finished"
            session.ended_at = datetime.now(timezone.utc)
            cycle = db.scalar(select(func.count()).select_from(PomodoroSession).where(PomodoroSession.user_id == user.id, PomodoroSession.status == "finished")) or 1
            rec = build_break_recommendation(cycle, session.break_minutes)
            session.break_recommendation = rec
            user.pending_food_session_id = sid
            db.commit()
        else:
            rec = session.break_recommendation or build_break_recommendation(1, session.break_minutes)
    await context.bot.send_message(
        chat_id,
        f"✅ انتهت جلسة الدراسة.\n\nاستراحة {session.break_minutes} دقيقة:\n{rec}\n\nإذا أكلت بالاستراحة اضغط 🍽️ سجل الأكل بعد الرجوع.",
        reply_markup=pomodoro_menu_keyboard(),
    )


async def handle_food_log(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    desc = "لم يأكل" if text.strip() in ["لا", "ما اكلت", "لم آكل", "none"] else text.strip()
    mn, mx, matches = estimate_calories(desc)
    with get_session() as db:
        user = _current_user(db, update.effective_user.id)
        sid = user.pending_food_session_id if user else None
        log = FoodLog(user_id=user.id, session_id=sid, description=desc, calories_min=mn, calories_max=mx)
        if user:
            user.pending_food_session_id = None
        db.add(log)
        db.commit()
    context.user_data.pop("flow", None)
    if mn is None:
        await update.effective_message.reply_text("تم تسجيل الأكل. لم أستطع حساب السعرات بدقة، لكنه محفوظ في التقرير.", reply_markup=pomodoro_menu_keyboard())
    else:
        await update.effective_message.reply_text(f"تم التسجيل. السعرات التقريبية: {mn}-{mx} kcal.\nالمطابقات: {', '.join(matches[:6])}", reply_markup=pomodoro_menu_keyboard())


# compatibility with old callback path
async def handle_pomo_callback(update, context, data):
    await update.callback_query.answer("هذه النسخة تستخدم أزرار لوحة الكيبورد فقط.", show_alert=True)
