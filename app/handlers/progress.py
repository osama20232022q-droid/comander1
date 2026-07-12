from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import ContextTypes

from app.db import get_session
from app.handlers.admin import is_admin_tg
from app.keyboards import confirm_back_keyboard, main_keyboard, nav_keyboard, profile_keyboard
from app.models import (
    Attachment,
    Certificate,
    DailyDisciplineReport,
    FoodLog,
    PomodoroSession,
    StudyPlan,
    Subject,
    User,
)
from app.repositories.users_repo import save_profile
from app.utils import classify_college, local_now, normalize_text, parse_health, validate_triple_name


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    end_date = local_now().date()
    start_date = end_date - timedelta(days=6)
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        if not user:
            return
        subjects = db.scalar(select(func.count()).select_from(Subject).where(Subject.user_id == user.id)) or 0
        files = db.scalar(select(func.count()).select_from(Attachment).where(Attachment.user_id == user.id)) or 0
        sessions = db.scalars(
            select(PomodoroSession).where(PomodoroSession.user_id == user.id, PomodoroSession.status == "finished")
        ).all()
        hours = sum(s.study_minutes for s in sessions) / 60
        plans = db.scalar(select(func.count()).select_from(StudyPlan).where(StudyPlan.user_id == user.id)) or 0
        certs = db.scalar(select(func.count()).select_from(Certificate).where(Certificate.user_id == user.id)) or 0
        foods = db.scalar(select(func.count()).select_from(FoodLog).where(FoodLog.user_id == user.id)) or 0
        reports = list(
            db.scalars(
                select(DailyDisciplineReport)
                .where(
                    DailyDisciplineReport.user_id == user.id,
                    DailyDisciplineReport.date_key >= start_date.isoformat(),
                    DailyDisciplineReport.date_key <= end_date.isoformat(),
                )
                .order_by(DailyDisciplineReport.date_key)
            ).all()
        )
    legacy_score = min(100, int(hours * 4 + subjects * 5 + plans * 8 + certs * 5))
    if reports:
        avg_score = round(sum(r.score for r in reports) / len(reports))
        green = sum(1 for r in reports if r.status == "green")
        yellow = sum(1 for r in reports if r.status == "yellow")
        red = sum(1 for r in reports if r.status == "red")
        total_minutes = sum(r.theory_minutes + r.practical_minutes for r in reports)
        total_mcq = sum(r.mcq_total for r in reports)
        total_correct = sum(r.mcq_correct for r in reports)
        accuracy = (total_correct / total_mcq * 100) if total_mcq else 0
        last = reports[-1]
        report_block = (
            f"\n\n🪖 قيادة آخر 7 أيام\n"
            f"التقارير المسجلة: {len(reports)}/7\n"
            f"متوسط الانضباط: {avg_score}/100\n"
            f"الأيام: {green} أخضر · {yellow} أصفر · {red} أحمر\n"
            f"الدراسة المسجلة: {total_minutes / 60:.1f} ساعة\n"
            f"MCQ: {total_correct}/{total_mcq} — دقة {accuracy:.0f}%\n"
            f"آخر يوم: {last.date_key} — {last.score}/100"
        )
    else:
        report_block = "\n\n🪖 لم تسجل تقرير انضباط بعد. افتح غرفة العمليات وسجل تقرير اليوم."
    await update.effective_message.reply_text(
        "📊 مركز التقدم الشامل\n\n"
        f"المواد: {subjects}\n"
        f"الملفات/الملحقات: {files}\n"
        f"جلسات البومودورو المنجزة: {len(sessions)}\n"
        f"ساعات المؤقت الصافية: {hours:.1f}\n"
        f"الخطط الدراسية: {plans}\n"
        f"سجلات الأكل: {foods}\n"
        f"الشهادات: {certs}\n"
        f"مؤشر الإنجاز العام: {legacy_score}/100"
        f"{report_block}"
    )


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("flow", None)
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        profile = user.profile if user else None
        is_active = bool(user.is_active) if user else False
    if not profile:
        await update.effective_message.reply_text("لا يوجد ملف طالب مؤكد بعد.")
        return
    await update.effective_message.reply_text(
        "👤 ملفي\n\n"
        f"الاسم: {profile.full_name}\n"
        f"الكلية: {profile.college}\n"
        f"تحليل التخصص: {profile.specialty}\n"
        f"المرحلة: {profile.stage}\n"
        f"العمر: {profile.age or 'غير مضاف'}\n"
        f"الطول: {profile.height_cm or 'غير مضاف'}\n"
        f"الوزن: {profile.weight_kg or 'غير مضاف'}\n"
        f"الحالة: {'مفعل' if is_active else 'بانتظار التفعيل'}\n\n"
        "لتعديل معلوماتك اضغط: ✏️ تعديل معلوماتي",
        reply_markup=profile_keyboard(),
    )


async def start_profile_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        profile = user.profile if user else None
    if not profile:
        await update.effective_message.reply_text(
            "لا يوجد ملف طالب لتعديله. ابدأ /start من جديد.",
            reply_markup=main_keyboard(is_admin_tg(update.effective_user.id)),
        )
        return

    context.user_data["flow"] = "profile_edit"
    context.user_data["step"] = "name"
    context.user_data["profile_edit"] = {
        "full_name": profile.full_name,
        "college": profile.college,
        "stage": profile.stage,
        "age": profile.age,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
    }
    await update.effective_message.reply_text(
        "✏️ تعديل معلوماتي\n\n"
        "سأعيد أخذ المعلومات خطوة خطوة.\n"
        "اكتب الاسم الثلاثي الجديد، أو أرسل نفس الاسم إذا لا تريد تغييره.",
        reply_markup=nav_keyboard(),
    )


async def handle_profile_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    if context.user_data.get("flow") != "profile_edit":
        return False

    msg = update.effective_message
    step = context.user_data.get("step")
    draft = context.user_data.setdefault("profile_edit", {})

    if text == "🏠 القائمة الرئيسية":
        context.user_data.clear()
        await msg.reply_text(
            "تم إلغاء التعديل والرجوع للقائمة الرئيسية.",
            reply_markup=main_keyboard(is_admin_tg(update.effective_user.id)),
        )
        return True

    if text in ["↩️ خطوة للوراء", "🔴 رجوع للتعديل"]:
        await _profile_edit_go_back(update, context)
        return True

    if text == "🔵 تأكيد" and step == "review":
        return await _confirm_profile_edit(update, context)

    if step == "name":
        ok, value = validate_triple_name(text)
        if not ok:
            await msg.reply_text(f"❌ {value}\nاكتب الاسم الثلاثي الحقيقي بدون رموز.")
            return True
        draft["full_name"] = value
        context.user_data["step"] = "college"
        await msg.reply_text("اكتب اسم الكلية الجديد. مثال: كلية الطب، صيدلة، هندسة، تمريض...")
        return True

    if step == "college":
        college = normalize_text(text)
        if len(college) < 3:
            await msg.reply_text("اكتب اسم الكلية بشكل أوضح.")
            return True
        domain, specialty = classify_college(college)
        draft["college"] = college
        draft["study_domain"] = domain
        draft["specialty"] = specialty
        context.user_data["step"] = "stage"
        await msg.reply_text(
            f"تم تحليل الكلية: {specialty}\n\nاكتب مرحلتك الجديدة. مثال: مرحلة أولى / ثانية / ثالثة..."
        )
        return True

    if step == "stage":
        stage = normalize_text(text)
        if len(stage) < 2:
            await msg.reply_text("اكتب المرحلة بشكل أوضح.")
            return True
        draft["stage"] = stage
        context.user_data["step"] = "health"
        await msg.reply_text("المعلومات الصحية اختيارية.\nاكتب: العمر الطول الوزن\nمثال: 20 170 75\nأو اكتب: تخطي")
        return True

    if step == "health":
        if text.strip() in ["تخطي", "skip", "Skip"]:
            draft["age"] = draft["height_cm"] = draft["weight_kg"] = None
        else:
            age, height, weight = parse_health(text)
            if not any([age, height, weight]):
                await msg.reply_text("لم أفهم الأرقام. اكتب مثل: 20 170 75 أو اكتب تخطي.")
                return True
            draft["age"] = age
            draft["height_cm"] = height
            draft["weight_kg"] = weight
        await _show_profile_edit_review(update, context)
        return True

    if step == "review":
        await msg.reply_text("اضغط 🔵 تأكيد أو 🔴 رجوع للتعديل من لوحة الكيبورد.", reply_markup=confirm_back_keyboard())
        return True

    return False


async def _profile_edit_go_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    step = context.user_data.get("step")
    order = ["name", "college", "stage", "health", "review"]
    if step in order and order.index(step) > 0:
        context.user_data["step"] = order[order.index(step) - 1]
    prompts = {
        "name": "اكتب الاسم الثلاثي.",
        "college": "اكتب اسم الكلية.",
        "stage": "اكتب المرحلة.",
        "health": "اكتب العمر الطول الوزن أو تخطي.",
        "review": "راجع معلوماتك ثم أكد.",
    }
    await update.effective_message.reply_text(
        prompts.get(context.user_data.get("step"), "اكتب البيانات."), reply_markup=nav_keyboard()
    )


async def _show_profile_edit_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = context.user_data.get("profile_edit", {})
    # ensure specialty is present if coming from old drafts
    if not d.get("specialty"):
        _, specialty = classify_college(d.get("college", ""))
        d["specialty"] = specialty
    context.user_data["step"] = "review"
    text = (
        "راجع معلوماتك الجديدة قبل الحفظ:\n\n"
        f"الاسم: {d.get('full_name')}\n"
        f"الكلية: {d.get('college')}\n"
        f"تحليل التخصص: {d.get('specialty')}\n"
        f"المرحلة: {d.get('stage')}\n"
        f"العمر: {d.get('age') or 'اختياري/غير مضاف'}\n"
        f"الطول: {d.get('height_cm') or 'اختياري/غير مضاف'}\n"
        f"الوزن: {d.get('weight_kg') or 'اختياري/غير مضاف'}\n\n"
        "إذا المعلومات صحيحة اضغط 🔵 تأكيد."
    )
    await update.effective_message.reply_text(text, reply_markup=confirm_back_keyboard())


async def _confirm_profile_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    draft = context.user_data.get("profile_edit", {})
    with get_session() as db:
        user = db.scalar(select(User).where(User.telegram_id == update.effective_user.id))
        if not user:
            await update.effective_message.reply_text("لم أجد حسابك. ابدأ /start.")
            return True
        profile = save_profile(db, user, draft)
        role_is_admin = user.role == "admin"
    context.user_data.clear()
    await update.effective_message.reply_text(
        f"✅ تم تحديث معلوماتك بنجاح.\n\nتحليل التخصص: {profile.specialty}",
        reply_markup=main_keyboard(role_is_admin),
    )
    return True
