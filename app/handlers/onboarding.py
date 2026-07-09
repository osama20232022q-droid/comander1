from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes
from app.db import get_session
from app.keyboards import confirm_back_keyboard, nav_keyboard
from app.repositories.users_repo import ensure_user, save_profile
from app.utils import validate_triple_name, normalize_text, parse_health, classify_college


async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["flow"] = "onboarding"
    context.user_data["step"] = "name"
    context.user_data["onboarding"] = {}
    await update.effective_message.reply_text(
        "أهلًا بك في Study Commander Bot.\n\n"
        "أول خطوة: اكتب اسمك الثلاثي الحقيقي.\n"
        "مثال: أحمد علي حسن\n"
        "يقبل عربي أو إنكليزي.",
        reply_markup=nav_keyboard(),
    )


async def handle_onboarding_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    step = context.user_data.get("step")
    draft = context.user_data.setdefault("onboarding", {})
    msg = update.effective_message

    if text == "↩️ خطوة للوراء":
        await _go_back(update, context)
        return

    if step == "name":
        ok, value = validate_triple_name(text)
        if not ok:
            await msg.reply_text(f"❌ {value}")
            return
        draft["full_name"] = value
        context.user_data["step"] = "college"
        await msg.reply_text("تمام.\n\nأنت بأي كلية؟ مثال: كلية الطب، صيدلة، هندسة، تمريض...")
        return

    if step == "college":
        college = normalize_text(text)
        if len(college) < 3:
            await msg.reply_text("اكتب اسم الكلية بشكل أوضح.")
            return
        domain, specialty = classify_college(college)
        draft["college"] = college
        draft["study_domain"] = domain
        draft["specialty"] = specialty
        context.user_data["step"] = "stage"
        await msg.reply_text(f"تم تحليل الكلية: {specialty}\n\nأنت بأي مرحلة؟ مثال: مرحلة أولى / ثانية / ثالثة / رابعة...")
        return

    if step == "stage":
        stage = normalize_text(text)
        if len(stage) < 2:
            await msg.reply_text("اكتب المرحلة بشكل أوضح.")
            return
        draft["stage"] = stage
        context.user_data["step"] = "health"
        await msg.reply_text(
            "المعلومات الصحية اختيارية لتحسين الاستراحات والنوم فقط.\n"
            "اكتب: العمر الطول الوزن\n"
            "مثال: 20 170 75\n"
            "أو اكتب: تخطي"
        )
        return

    if step == "health":
        if text.strip() in ["تخطي", "skip", "Skip"]:
            draft["age"] = draft["height_cm"] = draft["weight_kg"] = None
        else:
            age, height, weight = parse_health(text)
            if not any([age, height, weight]):
                await msg.reply_text("لم أفهم الأرقام. اكتب مثل: 20 170 75 أو اكتب تخطي.")
                return
            draft["age"] = age
            draft["height_cm"] = height
            draft["weight_kg"] = weight
        await show_review(update, context)
        return


async def _go_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    step = context.user_data.get("step")
    order = ["name", "college", "stage", "health"]
    if step in order and order.index(step) > 0:
        context.user_data["step"] = order[order.index(step)-1]
    prompts = {
        "name": "اكتب اسمك الثلاثي.",
        "college": "اكتب اسم الكلية.",
        "stage": "اكتب المرحلة.",
        "health": "اكتب العمر الطول الوزن أو تخطي.",
    }
    await update.effective_message.reply_text(prompts.get(context.user_data.get("step"), "اكتب البيانات."))


async def show_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = context.user_data.get("onboarding", {})
    text = (
        "راجع معلوماتك قبل التأكيد:\n\n"
        f"الاسم: {d.get('full_name')}\n"
        f"الكلية: {d.get('college')}\n"
        f"تحليل التخصص: {d.get('specialty')}\n"
        f"المرحلة: {d.get('stage')}\n"
        f"العمر: {d.get('age') or 'اختياري/غير مضاف'}\n"
        f"الطول: {d.get('height_cm') or 'اختياري/غير مضاف'}\n"
        f"الوزن: {d.get('weight_kg') or 'اختياري/غير مضاف'}\n\n"
        "إذا المعلومات صحيحة اضغط تأكيد."
    )
    await update.effective_message.reply_text(text, reply_markup=confirm_back_keyboard("onboard:confirm", "onboard:back"))


async def confirm_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get("onboarding", {})
    with get_session() as db:
        user = ensure_user(db, query.from_user)
        profile = save_profile(db, user, draft)
        if user.role == "admin":
            user.is_active = True
            db.commit()
            active_text = "تم تأكيد ملفك كأدمن."
        else:
            active_text = "تم حفظ ملفك. حسابك بانتظار تفعيل الأدمن."
    context.user_data.clear()
    await query.message.reply_text(f"✅ {active_text}\n\n{profile.specialty}")
