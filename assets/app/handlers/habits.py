from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from app.db import get_session
from app.keyboards import (
    manual_settings_keyboard, habit_duration_keyboard, habit_review_keyboard,
    routine_type_keyboard, routine_review_keyboard, main_keyboard, nav_keyboard
)
from app.models import User, HabitPlan, RoutinePlan
from app.handlers.admin import is_admin_tg


async def show_manual_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("flow", None)
    await update.effective_message.reply_text(
        "⚙️ الضبط اليدوي\n\n"
        "من هنا تگدر تعدّل ملفك، تغيّر نظامك، أو تبني عادة جديدة بطريقة تدريجية علمية.",
        reply_markup=manual_settings_keyboard(),
    )


async def start_routine_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["flow"] = "routine_change"
    context.user_data["step"] = "routine_type"
    context.user_data["routine_draft"] = {}
    await update.effective_message.reply_text(
        "🔄 تغيير نظامي\n\n"
        "اختر نوع النظام الذي تريد تجربته. لا نحكم على النظام من يوم واحد؛ الأفضل تجربة 7-14 يوم.",
        reply_markup=routine_type_keyboard(),
    )


async def start_habit_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["flow"] = "habit_add"
    context.user_data["step"] = "habit_name"
    context.user_data["habit_draft"] = {}
    await update.effective_message.reply_text(
        "🌱 إضافة عادة\n\n"
        "اكتب اسم العادة بوضوح. مثال: الاستيقاظ 5 صباحًا، مراجعة 20 MCQ، قراءة صفحة قرآن، مشي 10 دقائق.",
        reply_markup=nav_keyboard(),
    )


async def list_habits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        if not user:
            return
        habits = db.scalars(select(HabitPlan).where(HabitPlan.user_id == user.id).order_by(HabitPlan.created_at.desc()).limit(20)).all()
        routines = db.scalars(select(RoutinePlan).where(RoutinePlan.user_id == user.id).order_by(RoutinePlan.created_at.desc()).limit(5)).all()
    lines = ["📋 عاداتي وأنظمتي"]
    if routines:
        lines.append("\n🔄 الأنظمة:")
        for r in routines:
            lines.append(f"• {r.name} — {r.status} — {r.duration_days} يوم — استيقاظ: {r.wake_time or '-'} / نوم: {r.sleep_time or '-'}")
    if habits:
        lines.append("\n🌱 العادات:")
        for h in habits:
            lines.append(f"• {h.title} — {h.status} — {h.duration_days} يوم — أقل خطوة: {h.tiny_action}")
    if not habits and not routines:
        lines.append("\nلا توجد عادات أو أنظمة محفوظة بعد.")
    await update.effective_message.reply_text("\n".join(lines), reply_markup=manual_settings_keyboard())


async def handle_habit_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    flow = context.user_data.get("flow")
    if flow not in ["habit_add", "routine_change"]:
        return False
    if text == "🏠 القائمة الرئيسية":
        context.user_data.clear()
        await update.effective_message.reply_text("🏠 القائمة الرئيسية", reply_markup=main_keyboard(is_admin_tg(update.effective_user.id)))
        return True
    if text == "⚙️ الضبط اليدوي" or text == "↩️ خطوة للوراء":
        await show_manual_settings(update, context)
        return True
    if flow == "habit_add":
        return await _handle_habit_add(update, context, text)
    if flow == "routine_change":
        return await _handle_routine_change(update, context, text)
    return False


async def _handle_habit_add(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    msg = update.effective_message
    step = context.user_data.get("step")
    draft = context.user_data.setdefault("habit_draft", {})

    if step == "habit_name":
        if len(text.strip()) < 3:
            await msg.reply_text("اكتب اسم عادة أوضح.")
            return True
        draft["title"] = text.strip()
        context.user_data["step"] = "habit_reason"
        await msg.reply_text(
            "ليش تريد هذه العادة؟ اكتب سبب واحد قوي.\n"
            "مثال: حتى أبدأ يومي قبل الفوضى / حتى أثبت مراجعة يومية.",
            reply_markup=nav_keyboard(),
        )
        return True

    if step == "habit_reason":
        draft["reason"] = text.strip()[:500]
        context.user_data["step"] = "habit_anchor"
        await msg.reply_text(
            "حدد المثير/المرساة Habit Anchor.\n"
            "يعني بعد شنو راح تسوي العادة؟\n"
            "مثال: بعد صلاة الفجر، بعد الفطور، بعد أول جلسة بومودورو.",
            reply_markup=nav_keyboard(),
        )
        return True

    if step == "habit_anchor":
        draft["anchor"] = text.strip()[:255]
        context.user_data["step"] = "habit_tiny"
        await msg.reply_text(
            "اكتب أقل نسخة من العادة Tiny Action.\n"
            "القاعدة العلمية: ابدأ صغير جدًا حتى لا يقاومك الدماغ.\n"
            "مثال: أفتح الملزمة 5 دقائق / أحل 3 MCQ / أجهز ملابس الصبح.",
            reply_markup=nav_keyboard(),
        )
        return True

    if step == "habit_tiny":
        draft["tiny_action"] = text.strip()[:500]
        context.user_data["step"] = "habit_reward"
        await msg.reply_text(
            "شنو المكافأة الصغيرة بعد تنفيذ العادة؟\n"
            "مثال: كوب شاي، علامة ✅ بالتقرير، 5 دقائق راحة. لا تجعل المكافأة سوشال طويل.",
            reply_markup=nav_keyboard(),
        )
        return True

    if step == "habit_reward":
        draft["reward"] = text.strip()[:255]
        context.user_data["step"] = "habit_duration"
        await msg.reply_text("اختار مدة التجربة:", reply_markup=habit_duration_keyboard())
        return True

    if step == "habit_duration":
        mapping = {"7 أيام": 7, "14 يوم": 14, "21 يوم": 21, "30 يوم": 30}
        if text not in mapping:
            await msg.reply_text("اختر مدة من الأزرار فقط.", reply_markup=habit_duration_keyboard())
            return True
        draft["duration_days"] = mapping[text]
        context.user_data["step"] = "habit_review"
        await _show_habit_review(update, context)
        return True

    if step == "habit_review":
        if text == "✅ حفظ العادة":
            await _save_habit(update, context)
            return True
        if text == "🔴 رجوع للتعديل":
            context.user_data["step"] = "habit_name"
            await msg.reply_text("اكتب اسم العادة من جديد.", reply_markup=nav_keyboard())
            return True
        await msg.reply_text("اختر حفظ العادة أو رجوع للتعديل.", reply_markup=habit_review_keyboard())
        return True

    return True


async def _show_habit_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = context.user_data.get("habit_draft", {})
    text = (
        "🌱 مراجعة خطة العادة\n\n"
        f"العادة: {d.get('title')}\n"
        f"السبب: {d.get('reason')}\n"
        f"المثير/المرساة: {d.get('anchor')}\n"
        f"أقل خطوة: {d.get('tiny_action')}\n"
        f"المكافأة: {d.get('reward')}\n"
        f"مدة التجربة: {d.get('duration_days')} يوم\n\n"
        "طريقة التنفيذ العلمية:\n"
        "1) اربط العادة بمرساة ثابتة.\n"
        "2) ابدأ بأقل خطوة ممكنة.\n"
        "3) لا تكسر السلسلة يومين متتالين.\n"
        "4) قيّم بعد انتهاء التجربة، لا بعد أول يوم."
    )
    await update.effective_message.reply_text(text, reply_markup=habit_review_keyboard())


async def _save_habit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = context.user_data.get("habit_draft", {})
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        if not user:
            return
        db.add(HabitPlan(
            user_id=user.id,
            title=d.get("title", "عادة جديدة"),
            reason=d.get("reason"),
            anchor=d.get("anchor"),
            tiny_action=d.get("tiny_action", "خطوة صغيرة"),
            reward=d.get("reward"),
            duration_days=int(d.get("duration_days") or 14),
            status="active",
        ))
        db.commit()
    context.user_data.clear()
    await update.effective_message.reply_text(
        "✅ تم حفظ العادة.\n\n"
        "ابدأ بأقل خطوة اليوم، ولا تقيس النجاح بالمزاج. قِسه بالتنفيذ.",
        reply_markup=main_keyboard(is_admin_tg(update.effective_user.id)),
    )


async def _handle_routine_change(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    msg = update.effective_message
    step = context.user_data.get("step")
    draft = context.user_data.setdefault("routine_draft", {})

    if step == "routine_type":
        valid = ["نظام صباحي", "نظام نوم مبكر", "نظام دراسة ثابت", "نظام مخصص"]
        if text not in valid:
            await msg.reply_text("اختر نوع النظام من الأزرار أو اضغط رجوع.", reply_markup=routine_type_keyboard())
            return True
        draft["name"] = text
        context.user_data["step"] = "routine_wake"
        await msg.reply_text("اكتب وقت الاستيقاظ المستهدف. مثال: 05:00", reply_markup=nav_keyboard())
        return True

    if step == "routine_wake":
        draft["wake_time"] = text.strip()[:20]
        context.user_data["step"] = "routine_sleep"
        await msg.reply_text("اكتب وقت النوم المستهدف. مثال: 21:30", reply_markup=nav_keyboard())
        return True

    if step == "routine_sleep":
        draft["sleep_time"] = text.strip()[:20]
        context.user_data["step"] = "routine_rule"
        await msg.reply_text(
            "اكتب أهم قانون لهذا النظام.\n"
            "مثال: الهاتف خارج الغرفة بعد 10 مساءً / لا سرير بعد أول جلسة.",
            reply_markup=nav_keyboard(),
        )
        return True

    if step == "routine_rule":
        draft["rule"] = text.strip()[:500]
        context.user_data["step"] = "routine_review"
        await _show_routine_review(update, context)
        return True

    if step == "routine_review":
        if text == "✅ حفظ النظام":
            await _save_routine(update, context)
            return True
        if text == "🔴 رجوع للتعديل":
            context.user_data["step"] = "routine_type"
            await msg.reply_text("اختر نوع النظام من جديد.", reply_markup=routine_type_keyboard())
            return True
        await msg.reply_text("اختر حفظ النظام أو رجوع للتعديل.", reply_markup=routine_review_keyboard())
        return True

    return True


async def _show_routine_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = context.user_data.get("routine_draft", {})
    text = (
        "🔄 مراجعة النظام الجديد\n\n"
        f"النوع: {d.get('name')}\n"
        f"الاستيقاظ: {d.get('wake_time')}\n"
        f"النوم: {d.get('sleep_time')}\n"
        f"القانون الأساسي: {d.get('rule')}\n\n"
        "طريقة التجربة العلمية:\n"
        "• التجربة 14 يوم.\n"
        "• لا تحكم على النظام من أول 3 أيام.\n"
        "• إذا فشلت يومًا، لا تغيّر النظام؛ ارجع باليوم التالي.\n"
        "• المعيار: ساعات دراسة صافية + نوم أهدأ + هاتف أقل."
    )
    await update.effective_message.reply_text(text, reply_markup=routine_review_keyboard())


async def _save_routine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = context.user_data.get("routine_draft", {})
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        if not user:
            return
        db.add(RoutinePlan(
            user_id=user.id,
            name=d.get("name", "نظام جديد"),
            wake_time=d.get("wake_time"),
            sleep_time=d.get("sleep_time"),
            rule=d.get("rule"),
            duration_days=14,
            status="trial",
        ))
        db.commit()
    context.user_data.clear()
    await update.effective_message.reply_text(
        "✅ تم حفظ تجربة النظام.\n\n"
        "نفذها 14 يومًا قبل الحكم عليها. أول 3 أيام تكيف، وليست مقياسًا للفشل.",
        reply_markup=main_keyboard(is_admin_tg(update.effective_user.id)),
    )
