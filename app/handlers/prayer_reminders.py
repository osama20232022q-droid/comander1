from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import settings
from app.db import get_session
from app.models import User, PrayerSetting, PomodoroSession
from app.keyboards import rk, main_keyboard
from app.services.prayer import (
    IRAQ_GOVERNORATES,
    governorate_buttons,
    BAGHDAD_TZ,
    prayer_events_for_day,
    build_prayer_text,
)


def prayer_menu_keyboard() -> ReplyKeyboardMarkup:
    return rk([
        ["✅ تفعيل أذكار الصلاة", "❌ إلغاء تفعيل أذكار الصلاة"],
        ["📍 تغيير المحافظة", "📋 حالة أذكار الصلاة"],
        ["🏠 القائمة الرئيسية"],
    ], "أذكار الصلاة")


def governorates_keyboard() -> ReplyKeyboardMarkup:
    return rk(governorate_buttons(), "اختر المحافظة")


def _current_user(db, tg_id: int) -> User | None:
    return db.scalar(select(User).where(User.telegram_id == tg_id))


def _get_or_create_setting(db, user_id: int) -> PrayerSetting:
    row = db.scalar(select(PrayerSetting).where(PrayerSetting.user_id == user_id))
    if not row:
        row = PrayerSetting(user_id=user_id, enabled=False)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


async def show_prayer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        user = _current_user(db, update.effective_user.id)
        setting = _get_or_create_setting(db, user.id) if user else None
    status = "مفعّلة" if setting and setting.enabled else "غير مفعّلة"
    gov = setting.governorate if setting and setting.governorate else "غير محددة"
    await update.effective_message.reply_text(
        f"🕌 أذكار الصلاة\n\nالحالة: {status}\nالمحافظة: {gov}\n\n"
        "عند التفعيل سيذكّرك البوت بثلاثة أوقات حسب النمط الشيعي:\n"
        "• صلاة الصبح\n• صلاة الظهر والعصر\n• صلاة المغرب والعشاء\n\n"
        "كل تذكير يحتوي آية ورسالة قصيرة تربط الصلاة بالدراسة.",
        reply_markup=prayer_menu_keyboard(),
    )


async def handle_prayer_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    if text == "🕌 أذكار الصلاة":
        await show_prayer_menu(update, context)
        return True

    if text == "✅ تفعيل أذكار الصلاة":
        context.user_data["flow"] = "prayer_choose_governorate"
        await update.effective_message.reply_text("اختر محافظتك حتى أعتمد توقيت الصلاة الصحيح:", reply_markup=governorates_keyboard())
        return True

    if text == "📍 تغيير المحافظة":
        context.user_data["flow"] = "prayer_choose_governorate"
        await update.effective_message.reply_text("اختر المحافظة الجديدة:", reply_markup=governorates_keyboard())
        return True

    if text == "❌ إلغاء تفعيل أذكار الصلاة":
        with get_session() as db:
            user = _current_user(db, update.effective_user.id)
            if user:
                setting = _get_or_create_setting(db, user.id)
                setting.enabled = False
                db.commit()
        context.user_data.pop("flow", None)
        await update.effective_message.reply_text("تم إيقاف أذكار الصلاة لهذا الحساب.", reply_markup=main_keyboard(False))
        return True

    if text == "📋 حالة أذكار الصلاة":
        with get_session() as db:
            user = _current_user(db, update.effective_user.id)
            setting = _get_or_create_setting(db, user.id) if user else None
        if not setting or not setting.enabled:
            await update.effective_message.reply_text("أذكار الصلاة غير مفعّلة حاليًا.", reply_markup=prayer_menu_keyboard())
            return True
        try:
            events = prayer_events_for_day(setting.governorate or "بغداد")
            lines = [f"🕌 أذكار الصلاة مفعّلة — {setting.governorate}", ""]
            for key, dt in events:
                label = {"fajr":"الصبح", "dhuhr_asr":"الظهر والعصر", "maghrib_isha":"المغرب والعشاء"}.get(key, key)
                lines.append(f"• {label}: {dt.strftime('%H:%M')}")
            await update.effective_message.reply_text("\n".join(lines), reply_markup=prayer_menu_keyboard())
        except Exception:
            await update.effective_message.reply_text("أذكار الصلاة مفعّلة، لكن تعذر جلب مواقيت اليوم الآن. سيعمل التذكير بالاحتياط.", reply_markup=prayer_menu_keyboard())
        return True

    if context.user_data.get("flow") == "prayer_choose_governorate":
        if text not in IRAQ_GOVERNORATES:
            await update.effective_message.reply_text("اختر محافظة من الأزرار الظاهرة فقط.", reply_markup=governorates_keyboard())
            return True
        with get_session() as db:
            user = _current_user(db, update.effective_user.id)
            if user:
                setting = _get_or_create_setting(db, user.id)
                setting.enabled = True
                setting.governorate = text
                # reset daily sent markers so new city can notify normally
                setting.last_sent_fajr = None
                setting.last_sent_dhuhr_asr = None
                setting.last_sent_maghrib_isha = None
                db.commit()
        context.user_data.pop("flow", None)
        await update.effective_message.reply_text(
            f"✅ تم تفعيل أذكار الصلاة لمحافظة: {text}\n"
            "سأذكّرك بصلاة الصبح، الظهر والعصر، والمغرب والعشاء مع آية ورسالة قصيرة.",
            reply_markup=prayer_menu_keyboard(),
        )
        return True

    return False


async def prayer_notifier_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now(BAGHDAD_TZ)
    date_key = now.strftime("%Y-%m-%d")
    # 90 second window to tolerate job delays. last_sent_* prevents duplicates.
    with get_session() as db:
        settings_rows = db.scalars(select(PrayerSetting).where(PrayerSetting.enabled == True)).all()  # noqa: E712
        for st in settings_rows:
            if not st.governorate:
                continue
            user = db.get(User, st.user_id)
            if not user or user.is_banned or not user.is_active:
                continue
            try:
                events = prayer_events_for_day(st.governorate, now)
            except Exception:
                continue
            for key, dt in events:
                delta = abs((now - dt).total_seconds())
                if delta > 90:
                    continue
                attr = f"last_sent_{key}"
                if getattr(st, attr, None) == date_key:
                    continue
                setattr(st, attr, date_key)
                db.commit()
                text = build_prayer_text(st.governorate, key, dt)
                try:
                    await context.bot.send_message(chat_id=user.telegram_id, text=text)
                except Exception:
                    pass
