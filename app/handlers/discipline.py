from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from app.db import get_session
from app.handlers.admin import is_admin_tg
from app.handlers.pomodoro import start_pomodoro
from app.keyboards import (
    discipline_menu_keyboard,
    discipline_phone_keyboard,
    discipline_review_keyboard,
    discipline_yes_no_keyboard,
    main_keyboard,
    nav_keyboard,
)
from app.models import DailyDisciplineReport, Subject, User
from app.services.discipline_report import (
    calculate_discipline_score,
    calculate_sleep_minutes,
    daily_summary_text,
    generate_daily_html,
    generate_weekly_html,
    parse_clock,
)
from app.services.temp_files import temporary_path
from app.utils import local_now

DISCIPLINE_BUTTON = "🪖 غرفة العمليات"
DAILY_REPORT_BUTTON = "📋 سجل تقرير اليوم"
DAILY_HTML_BUTTON = "🌐 تقرير HTML اليوم"
WEEKLY_HTML_BUTTON = "📆 تقرير 7 أيام"
ORDERS_BUTTON = "🎯 أوامر اليوم"
RESCUE_BUTTON = "🚨 جلسة إنقاذ 20 دقيقة"


def _current_user(db, telegram_id: int) -> User | None:
    return db.scalar(select(User).where(User.telegram_id == telegram_id))


def _parse_nonnegative_int(text: str, maximum: int) -> int | None:
    raw = (text or "").strip().replace("دقيقة", "").replace("سؤال", "")
    if not raw.isdigit():
        return None
    value = int(raw)
    if 0 <= value <= maximum:
        return value
    return None


def _draft_score(draft: dict):
    draft["sleep_minutes"] = calculate_sleep_minutes(draft.get("sleep_time"), draft.get("wake_time"))
    return calculate_discipline_score(draft)


async def show_operations_room(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("flow", None)
    await update.effective_message.reply_text(
        "🪖 غرفة العمليات\n\n"
        "هنا لا نقيس الواهس؛ نقيس التنفيذ بالدليل.\n"
        "سجّل تقريرك اليومي، استلم ملف HTML، وشوف أوامر التصحيح بدون تعديل الخطة كل يوم.",
        reply_markup=discipline_menu_keyboard(),
    )


async def start_daily_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["flow"] = "discipline_report"
    context.user_data["step"] = "sleep_time"
    context.user_data["discipline_draft"] = {}
    await update.effective_message.reply_text(
        "📋 تقرير القيادة اليومي\n\nاكتب وقت نومك الفعلي البارحة بصيغة 24 ساعة.\nمثال: 03:00 أو 21:30",
        reply_markup=nav_keyboard(),
    )


async def handle_discipline_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    flow = context.user_data.get("flow")

    if text == DISCIPLINE_BUTTON:
        await show_operations_room(update, context)
        return True
    if text == DAILY_REPORT_BUTTON:
        await start_daily_report(update, context)
        return True
    if text == DAILY_HTML_BUTTON:
        await send_today_html(update, context)
        return True
    if text == WEEKLY_HTML_BUTTON:
        await send_weekly_html(update, context)
        return True
    if text == ORDERS_BUTTON:
        await show_today_orders(update, context)
        return True
    if text == RESCUE_BUTTON:
        await start_rescue_session(update, context)
        return True

    if flow != "discipline_report":
        return False

    if text == "🏠 القائمة الرئيسية":
        context.user_data.clear()
        await update.effective_message.reply_text(
            "تم إلغاء التقرير والرجوع للقائمة الرئيسية.",
            reply_markup=main_keyboard(is_admin_tg(update.effective_user.id)),
        )
        return True

    msg = update.effective_message
    step = context.user_data.get("step")
    draft = context.user_data.setdefault("discipline_draft", {})

    if step == "sleep_time":
        value = parse_clock(text)
        if not value:
            await msg.reply_text("الوقت غير واضح. اكتب مثل: 03:00 أو 21:30")
            return True
        draft["sleep_time"] = value
        context.user_data["step"] = "wake_time"
        await msg.reply_text("اكتب وقت استيقاظك الفعلي اليوم. مثال: 09:00 أو 03:00")
        return True

    if step == "wake_time":
        value = parse_clock(text)
        if not value:
            await msg.reply_text("الوقت غير واضح. اكتب مثل: 09:00")
            return True
        draft["wake_time"] = value
        draft["sleep_minutes"] = calculate_sleep_minutes(draft.get("sleep_time"), value)
        if draft["sleep_minutes"] == 0:
            await msg.reply_text("لم أستطع حساب مدة النوم. أعد كتابة وقت الاستيقاظ بصيغة HH:MM.")
            return True
        context.user_data["step"] = "phone"
        await msg.reply_text(
            "خلال وقت الدراسة، شنو صار بالهاتف؟",
            reply_markup=discipline_phone_keyboard(),
        )
        return True

    if step == "phone":
        if text == "📵 الهاتف خارج المكان":
            draft["phone_locked"] = True
        elif text == "📱 استخدمت الهاتف أثناء الدراسة":
            draft["phone_locked"] = False
        else:
            await msg.reply_text("اختر حالة الهاتف من الأزرار.", reply_markup=discipline_phone_keyboard())
            return True
        context.user_data["step"] = "theory"
        await msg.reply_text(
            "كم دقيقة نظري درست اليوم دراسة صافية؟\nاكتب رقم فقط، مثال: 90",
            reply_markup=nav_keyboard(),
        )
        return True

    if step == "theory":
        value = _parse_nonnegative_int(text, 720)
        if value is None:
            await msg.reply_text("اكتب عدد دقائق من 0 إلى 720. مثال: 90")
            return True
        draft["theory_minutes"] = value
        context.user_data["step"] = "practical"
        await msg.reply_text("كم دقيقة عملي/صور/سلايدات؟ اكتب رقم فقط، مثال: 60")
        return True

    if step == "practical":
        value = _parse_nonnegative_int(text, 720)
        if value is None:
            await msg.reply_text("اكتب عدد دقائق من 0 إلى 720.")
            return True
        draft["practical_minutes"] = value
        context.user_data["step"] = "mcq"
        await msg.reply_text("اكتب عدد MCQ الكلي ثم عدد الصحيح.\nمثال: 40 29\nإذا ما حليت اكتب: 0 0")
        return True

    if step == "mcq":
        parts = [p for p in text.replace("/", " ").replace(",", " ").split() if p.isdigit()]
        if len(parts) != 2:
            await msg.reply_text("اكتب رقمين فقط: الكلي الصحيح. مثال: 40 29")
            return True
        total, correct = int(parts[0]), int(parts[1])
        if not (0 <= total <= 1000 and 0 <= correct <= total):
            await msg.reply_text("الأرقام غير منطقية. الصحيح يجب أن يكون أقل أو يساوي الكلي.")
            return True
        draft["mcq_total"] = total
        draft["mcq_correct"] = correct
        context.user_data["step"] = "essay"
        await msg.reply_text("كم سؤال مقالي كتبته من الذاكرة؟ اكتب رقم، والهدف 2.")
        return True

    if step == "essay":
        value = _parse_nonnegative_int(text, 50)
        if value is None:
            await msg.reply_text("اكتب رقمًا من 0 إلى 50.")
            return True
        draft["essay_count"] = value
        context.user_data["step"] = "review"
        await msg.reply_text(
            "هل نفذت مراجعة إغلاق اليوم؟\nأخطاء MCQ + صور العملي + أهم العناوين",
            reply_markup=discipline_yes_no_keyboard(),
        )
        return True

    if step == "review":
        if text == "✅ نعم":
            draft["review_completed"] = True
        elif text == "❌ لا":
            draft["review_completed"] = False
        else:
            await msg.reply_text("اختر نعم أو لا من الأزرار.", reply_markup=discipline_yes_no_keyboard())
            return True
        context.user_data["step"] = "notes"
        await msg.reply_text(
            "اكتب ملاحظة قصيرة عن سبب التعثر أو أفضل إنجاز اليوم.\nإذا ما عندك اكتب: لا",
            reply_markup=nav_keyboard(),
        )
        return True

    if step == "notes":
        draft["notes"] = None if text.strip() in {"لا", "لا يوجد", "none"} else text.strip()[:1000]
        context.user_data["step"] = "confirm"
        await _show_report_review(update, context)
        return True

    if step == "confirm":
        if text == "✅ اعتماد التقرير":
            await _save_report(update, context)
            return True
        if text == "🔴 إعادة الإدخال":
            await start_daily_report(update, context)
            return True
        await msg.reply_text("اختر اعتماد التقرير أو إعادة الإدخال.", reply_markup=discipline_review_keyboard())
        return True

    return True


async def _show_report_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = context.user_data.get("discipline_draft", {})
    score = _draft_score(d)
    sleep_h, sleep_m = divmod(d.get("sleep_minutes", 0), 60)
    accuracy = score.accuracy
    text = (
        "🪖 مراجعة تقرير اليوم\n\n"
        f"النوم: {d.get('sleep_time')} ← {d.get('wake_time')} ({sleep_h}س {sleep_m}د)\n"
        f"الهاتف: {'خارج المكان ✅' if d.get('phone_locked') else 'استُخدم ❌'}\n"
        f"النظري: {d.get('theory_minutes', 0)} دقيقة\n"
        f"العملي: {d.get('practical_minutes', 0)} دقيقة\n"
        f"MCQ: {d.get('mcq_correct', 0)}/{d.get('mcq_total', 0)} — {accuracy:.0f}%\n"
        f"المقالي: {d.get('essay_count', 0)}\n"
        f"مراجعة الإغلاق: {'تمت ✅' if d.get('review_completed') else 'لم تتم ❌'}\n\n"
        f"النتيجة المتوقعة: {score.score}/100\n"
        f"التصنيف: {score.status_ar}\n\n"
        "بعد الاعتماد سيُحفظ التقرير ويُرسل ملف HTML احترافي."
    )
    await update.effective_message.reply_text(text, reply_markup=discipline_review_keyboard())


async def _save_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    d = context.user_data.get("discipline_draft", {})
    score = _draft_score(d)
    date_key = local_now().date().isoformat()
    with get_session() as db:
        user = _current_user(db, update.effective_user.id)
        if not user:
            await update.effective_message.reply_text("لم أجد حسابك. أرسل /start.")
            return
        report = db.scalar(
            select(DailyDisciplineReport).where(
                DailyDisciplineReport.user_id == user.id,
                DailyDisciplineReport.date_key == date_key,
            )
        )
        if not report:
            report = DailyDisciplineReport(user_id=user.id, date_key=date_key)
            db.add(report)
        report.sleep_time = d.get("sleep_time")
        report.wake_time = d.get("wake_time")
        report.sleep_minutes = int(d.get("sleep_minutes") or 0)
        report.phone_locked = bool(d.get("phone_locked"))
        report.theory_minutes = int(d.get("theory_minutes") or 0)
        report.practical_minutes = int(d.get("practical_minutes") or 0)
        report.mcq_total = int(d.get("mcq_total") or 0)
        report.mcq_correct = int(d.get("mcq_correct") or 0)
        report.essay_count = int(d.get("essay_count") or 0)
        report.review_completed = bool(d.get("review_completed"))
        report.notes = d.get("notes")
        report.score = score.score
        report.status = score.status
        db.commit()
        db.refresh(report)
        summary = daily_summary_text(report)
    context.user_data.clear()
    await update.effective_message.reply_text(summary, reply_markup=discipline_menu_keyboard())
    await send_today_html(update, context)


async def send_today_html(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    date_key = local_now().date().isoformat()
    with get_session() as db:
        user = _current_user(db, update.effective_user.id)
        report = None
        if user:
            report = db.scalar(
                select(DailyDisciplineReport).where(
                    DailyDisciplineReport.user_id == user.id,
                    DailyDisciplineReport.date_key == date_key,
                )
            )
        if not user or not report:
            await update.effective_message.reply_text(
                "ما عندك تقرير معتمد لليوم. اضغط 📋 سجل تقرير اليوم أولًا.",
                reply_markup=discipline_menu_keyboard(),
            )
            return
        profile = user.profile
        subject_names = list(db.scalars(select(Subject.name).where(Subject.user_id == user.id)).all())
        html = generate_daily_html(profile, report, subject_names)
        report_id = report.id
    with temporary_path(suffix=".html", prefix=f"discipline_daily_{report_id}_") as path:
        path.write_text(html, encoding="utf-8")
        with path.open("rb") as fh:
            await update.effective_message.reply_document(
                document=fh,
                filename=f"discipline_report_{date_key}.html",
                caption="✅ تقرير HTML اليومي جاهز. افتحه بالمتصفح أو احفظه PDF من خيار الطباعة.",
                reply_markup=discipline_menu_keyboard(),
            )


async def send_weekly_html(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    end = local_now().date()
    start = end - timedelta(days=6)
    with get_session() as db:
        user = _current_user(db, update.effective_user.id)
        reports = []
        if user:
            reports = list(
                db.scalars(
                    select(DailyDisciplineReport)
                    .where(
                        DailyDisciplineReport.user_id == user.id,
                        DailyDisciplineReport.date_key >= start.isoformat(),
                        DailyDisciplineReport.date_key <= end.isoformat(),
                    )
                    .order_by(DailyDisciplineReport.date_key)
                ).all()
            )
        if not user or not reports:
            await update.effective_message.reply_text(
                "لا توجد تقارير ضمن آخر 7 أيام. سجل تقرير يوم واحد على الأقل.",
                reply_markup=discipline_menu_keyboard(),
            )
            return
        html = generate_weekly_html(user.profile, reports)
        user_id = user.id
    with temporary_path(suffix=".html", prefix=f"discipline_weekly_{user_id}_") as path:
        path.write_text(html, encoding="utf-8")
        with path.open("rb") as fh:
            await update.effective_message.reply_document(
                document=fh,
                filename=f"weekly_discipline_{start.isoformat()}_{end.isoformat()}.html",
                caption="📆 تقرير الانضباط لآخر 7 أيام.",
                reply_markup=discipline_menu_keyboard(),
            )


async def show_today_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    date_key = local_now().date().isoformat()
    with get_session() as db:
        user = _current_user(db, update.effective_user.id)
        report = None
        subjects = []
        if user:
            report = db.scalar(
                select(DailyDisciplineReport).where(
                    DailyDisciplineReport.user_id == user.id,
                    DailyDisciplineReport.date_key == date_key,
                )
            )
            subjects = list(db.scalars(select(Subject.name).where(Subject.user_id == user.id)).all())
    if report:
        score = calculate_discipline_score(
            {
                "sleep_minutes": report.sleep_minutes,
                "phone_locked": report.phone_locked,
                "theory_minutes": report.theory_minutes,
                "practical_minutes": report.practical_minutes,
                "mcq_total": report.mcq_total,
                "mcq_correct": report.mcq_correct,
                "essay_count": report.essay_count,
                "review_completed": report.review_completed,
            }
        )
        orders = score.orders
        heading = f"🎯 أوامر التصحيح بناءً على تقرير {date_key}"
    else:
        orders = [
            "ضع الهاتف خارج غرفة الدراسة قبل البداية.",
            "نفذ 90 دقيقة نظري باسترجاع، لا قراءة صامتة فقط.",
            "نفذ 60 دقيقة عملي/صور.",
            "حل 40 MCQ وسجل سبب كل خطأ.",
            "اكتب سؤالين مقاليين من الذاكرة.",
            "أغلق اليوم بمراجعة 30 دقيقة.",
        ]
        heading = "🎯 أوامر اليوم الافتراضية"
    subject_note = f"\nالمواد المسجلة: {('، '.join(subjects[:6]) if subjects else 'لا توجد مواد مضافة')}"
    await update.effective_message.reply_text(
        heading + "\n\n" + "\n".join(f"{i}. {o}" for i, o in enumerate(orders, 1)) + subject_note,
        reply_markup=discipline_menu_keyboard(),
    )


async def start_rescue_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "🚨 بروتوكول الإنقاذ بدأ\n\n"
        "1) الهاتف خارج المكان.\n"
        "2) افتح أول عنوان أو أول 5 أسئلة.\n"
        "3) ممنوع تقييم المزاج خلال الجلسة.\n"
        "4) بعد 20 دقيقة قرر الاستمرار فقط.\n\n"
        "سيبدأ مؤقت 20 دراسة / 5 راحة الآن.",
        reply_markup=discipline_menu_keyboard(),
    )
    await start_pomodoro(update.effective_message, context, update.effective_user.id, 20, 5)
