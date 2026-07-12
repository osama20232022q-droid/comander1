from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import mean

from app.config import settings
from app.services.assets import logo_data_uri
from app.utils import html_escape


@dataclass(frozen=True)
class DisciplineScore:
    score: int
    status: str
    status_ar: str
    sleep_points: int
    phone_points: int
    theory_points: int
    practical_points: int
    mcq_points: int
    essay_points: int
    review_points: int
    accuracy: float
    total_study_minutes: int
    orders: list[str]
    warnings: list[str]


def parse_clock(value: str) -> str | None:
    raw = (value or "").strip().replace(".", ":").replace("،", ":")
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) == 1 and raw.isdigit():
        if len(raw) <= 2:
            hour, minute = int(raw), 0
        elif len(raw) in {3, 4}:
            hour, minute = int(raw[:-2]), int(raw[-2:])
        else:
            return None
    elif len(parts) == 2 and all(p.strip().isdigit() for p in parts):
        hour, minute = int(parts[0]), int(parts[1])
    else:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def calculate_sleep_minutes(sleep_time: str | None, wake_time: str | None) -> int:
    if not sleep_time or not wake_time:
        return 0
    try:
        sh, sm = [int(x) for x in sleep_time.split(":")]
        wh, wm = [int(x) for x in wake_time.split(":")]
    except (ValueError, AttributeError):
        return 0
    start = sh * 60 + sm
    end = wh * 60 + wm
    if end <= start:
        end += 24 * 60
    duration = end - start
    return duration if 0 <= duration <= 16 * 60 else 0


def _scaled(value: int, target: int, max_points: int) -> int:
    if target <= 0:
        return max_points
    return max(0, min(max_points, round(max_points * min(value, target) / target)))


def calculate_discipline_score(data: dict) -> DisciplineScore:
    sleep_minutes = int(data.get("sleep_minutes") or 0)
    phone_locked = bool(data.get("phone_locked"))
    theory = max(0, int(data.get("theory_minutes") or 0))
    practical = max(0, int(data.get("practical_minutes") or 0))
    mcq_total = max(0, int(data.get("mcq_total") or 0))
    mcq_correct = max(0, min(mcq_total, int(data.get("mcq_correct") or 0)))
    essays = max(0, int(data.get("essay_count") or 0))
    reviewed = bool(data.get("review_completed"))

    sleep_points = 10 if sleep_minutes >= 7 * 60 else _scaled(sleep_minutes, 7 * 60, 10)
    phone_points = 10 if phone_locked else 0
    theory_points = _scaled(theory, 90, 20)
    practical_points = _scaled(practical, 60, 15)

    volume_points = _scaled(mcq_total, 40, 12)
    accuracy = (mcq_correct / mcq_total * 100) if mcq_total else 0.0
    accuracy_points = 0
    if mcq_total:
        accuracy_points = max(0, min(8, round(8 * accuracy / 80)))
    mcq_points = min(20, volume_points + accuracy_points)

    essay_points = _scaled(essays, 2, 15)
    review_points = 10 if reviewed else 0

    score = min(
        100,
        sleep_points + phone_points + theory_points + practical_points + mcq_points + essay_points + review_points,
    )
    if score >= 85:
        status, status_ar = "green", "أخضر — يوم ناجح"
    elif score >= 70:
        status, status_ar = "yellow", "أصفر — مقبول ويحتاج تصحيح"
    else:
        status, status_ar = "red", "أحمر — فشل تنفيذي يحتاج إنقاذ"

    warnings: list[str] = []
    orders: list[str] = []
    if sleep_minutes < 6 * 60:
        warnings.append("النوم أقل من 6 ساعات؛ التركيز والتثبيت سيتأثران.")
        orders.append("قدّم النوم اليوم ولا تحاول تعويض الضعف بسهر إضافي.")
    elif sleep_minutes < 7 * 60:
        warnings.append("النوم أقل من الهدف العسكري 7 ساعات.")
        orders.append("زد النوم 30–60 دقيقة الليلة.")
    if not phone_locked:
        warnings.append("الهاتف دخل ساحة الدراسة وخسر اليوم نقاط الانضباط كاملة.")
        orders.append("ضع الهاتف خارج الغرفة قبل أول جلسة غدًا.")
    if theory < 90:
        orders.append(f"أكمل {max(0, 90 - theory)} دقيقة نظري صافي.")
    if practical < 60:
        orders.append(f"أكمل {max(0, 60 - practical)} دقيقة عملي/صور.")
    if mcq_total < 40:
        orders.append(f"حل {max(0, 40 - mcq_total)} MCQ إضافية مع تسجيل الأخطاء.")
    elif accuracy < 70:
        warnings.append("دقة MCQ منخفضة؛ كثرة الحل وحدها لا تكفي.")
        orders.append("راجع أخطاء MCQ قبل فتح أسئلة جديدة.")
    if essays < 2:
        orders.append(f"اكتب {max(0, 2 - essays)} سؤال مقالي من الذاكرة.")
    if not reviewed:
        orders.append("نفّذ إغلاق اليوم: أخطاء MCQ + صور العملي + أهم العناوين.")
    if not orders:
        orders.append("حافظ على نفس النظام ولا ترفع الحمل غدًا أكثر من 10٪.")

    return DisciplineScore(
        score=score,
        status=status,
        status_ar=status_ar,
        sleep_points=sleep_points,
        phone_points=phone_points,
        theory_points=theory_points,
        practical_points=practical_points,
        mcq_points=mcq_points,
        essay_points=essay_points,
        review_points=review_points,
        accuracy=accuracy,
        total_study_minutes=theory + practical,
        orders=orders[:6],
        warnings=warnings[:5],
    )


def format_minutes(minutes: int) -> str:
    minutes = max(0, int(minutes or 0))
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} س و{mins} د"
    if hours:
        return f"{hours} ساعة"
    return f"{mins} دقيقة"


def daily_summary_text(report) -> str:
    score = calculate_discipline_score(report_to_dict(report))
    lines = [
        "🪖 تقرير قيادة اليوم",
        "",
        f"التاريخ: {report.date_key}",
        f"النوم: {report.sleep_time or '—'} ← {report.wake_time or '—'} ({format_minutes(report.sleep_minutes)})",
        f"الهاتف: {'خارج مكان الدراسة ✅' if report.phone_locked else 'استُخدم أثناء الدراسة ❌'}",
        f"النظري: {format_minutes(report.theory_minutes)}",
        f"العملي: {format_minutes(report.practical_minutes)}",
        f"MCQ: {report.mcq_correct}/{report.mcq_total} — الدقة {score.accuracy:.0f}%",
        f"المقالي: {report.essay_count}",
        f"مراجعة الإغلاق: {'تمت ✅' if report.review_completed else 'لم تتم ❌'}",
        "",
        f"النتيجة: {score.score}/100",
        f"التصنيف: {score.status_ar}",
        "",
        "أوامر التصحيح:",
    ]
    lines.extend(f"• {item}" for item in score.orders)
    return "\n".join(lines)


def report_to_dict(report) -> dict:
    return {
        "sleep_minutes": report.sleep_minutes,
        "phone_locked": report.phone_locked,
        "theory_minutes": report.theory_minutes,
        "practical_minutes": report.practical_minutes,
        "mcq_total": report.mcq_total,
        "mcq_correct": report.mcq_correct,
        "essay_count": report.essay_count,
        "review_completed": report.review_completed,
    }


def _metric_card(label: str, value: str, sub: str = "") -> str:
    return (
        '<div class="metric"><div class="metric-label">'
        + html_escape(label)
        + '</div><div class="metric-value">'
        + html_escape(value)
        + '</div><div class="metric-sub">'
        + html_escape(sub)
        + "</div></div>"
    )


def _score_row(label: str, points: int, max_points: int) -> str:
    width = 0 if max_points <= 0 else round(points / max_points * 100)
    return f"""
    <div class="score-row">
      <div class="score-head"><span>{html_escape(label)}</span><b>{points}/{max_points}</b></div>
      <div class="bar"><span style="width:{width}%"></span></div>
    </div>"""


def _base_css() -> str:
    return """
    :root{--bg:#eef2f7;--paper:#fff;--ink:#142033;--muted:#687386;--line:#dce3ed;--accent:#1f4f85;--good:#16794c;--warn:#9c6a00;--bad:#9f2d2d}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);font-family:Tahoma,Arial,sans-serif;color:var(--ink);line-height:1.65}
    .page{max-width:980px;margin:26px auto;background:var(--paper);border:1px solid var(--line);border-radius:22px;overflow:hidden;box-shadow:0 18px 50px rgba(20,32,51,.12)}
    .hero{padding:28px 32px;background:linear-gradient(135deg,#142a45,#1f4f85);color:#fff;display:flex;gap:20px;align-items:center}
    .logo{width:82px;height:82px;object-fit:contain;background:#fff;border-radius:18px;padding:8px}.hero h1{margin:0;font-size:29px}.hero p{margin:4px 0 0;opacity:.85}
    .content{padding:26px 30px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.metric{border:1px solid var(--line);border-radius:16px;padding:15px;background:#fbfcfe}
    .metric-label{font-size:13px;color:var(--muted)}.metric-value{font-size:23px;font-weight:800;margin:3px 0}.metric-sub{font-size:12px;color:var(--muted)}
    .section{margin-top:22px;border:1px solid var(--line);border-radius:18px;padding:20px}.section h2{margin:0 0 13px;font-size:20px}.score-wrap{display:grid;grid-template-columns:180px 1fr;gap:22px;align-items:center}
    .circle{width:160px;height:160px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(var(--accent) calc(var(--score)*1%),#e8edf4 0);position:relative;margin:auto}
    .circle:after{content:"";position:absolute;width:126px;height:126px;border-radius:50%;background:#fff}.circle strong{position:relative;z-index:1;font-size:37px}.circle small{position:absolute;z-index:2;margin-top:55px;color:var(--muted)}
    .score-row{margin:10px 0}.score-head{display:flex;justify-content:space-between;font-size:14px}.bar{height:9px;background:#e8edf4;border-radius:999px;overflow:hidden}.bar span{display:block;height:100%;background:var(--accent);border-radius:999px}
    .status{display:inline-block;padding:7px 13px;border-radius:999px;font-weight:700}.green{background:#e5f5ed;color:var(--good)}.yellow{background:#fff4d8;color:var(--warn)}.red{background:#fde7e7;color:var(--bad)}
    ul{margin:8px 0;padding-right:22px}.note{background:#f7f9fc;border-right:4px solid var(--accent);padding:12px 15px;border-radius:10px}.footer{padding:18px 30px;border-top:1px solid var(--line);color:var(--muted);font-size:12px;display:flex;justify-content:space-between;gap:10px}
    table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:10px;text-align:center}th{background:#f5f7fa}
    @media(max-width:760px){.grid{grid-template-columns:repeat(2,1fr)}.score-wrap{grid-template-columns:1fr}.hero{padding:22px}.content{padding:18px}.footer{display:block}.page{margin:0;border-radius:0}}
    @media print{body{background:#fff}.page{box-shadow:none;margin:0;max-width:none;border:0}.no-print{display:none}}
    """


def generate_daily_html(profile, report, subject_names: Iterable[str] = (), signature: str | None = None) -> str:
    score = calculate_discipline_score(report_to_dict(report))
    student_name = getattr(profile, "full_name", None) or "الطالب"
    college = getattr(profile, "college", None) or "غير محدد"
    subjects = "، ".join(list(subject_names)[:8]) or "لم تُضف مواد بعد"
    status_class = score.status
    metrics = "".join(
        [
            _metric_card("إجمالي الدراسة", format_minutes(score.total_study_minutes), "نظري + عملي"),
            _metric_card("MCQ", f"{report.mcq_correct}/{report.mcq_total}", f"دقة {score.accuracy:.0f}%"),
            _metric_card("المقالي", str(report.essay_count), "الهدف اليومي: 2"),
            _metric_card(
                "النوم", format_minutes(report.sleep_minutes), f"{report.sleep_time or '—'} ← {report.wake_time or '—'}"
            ),
        ]
    )
    score_rows = "".join(
        [
            _score_row("النوم", score.sleep_points, 10),
            _score_row("حجر الهاتف", score.phone_points, 10),
            _score_row("النظري", score.theory_points, 20),
            _score_row("العملي", score.practical_points, 15),
            _score_row("MCQ", score.mcq_points, 20),
            _score_row("المقالي", score.essay_points, 15),
            _score_row("مراجعة الإغلاق", score.review_points, 10),
        ]
    )
    warnings = (
        "".join(f"<li>{html_escape(x)}</li>" for x in score.warnings) or "<li>لا توجد إنذارات حرجة لهذا اليوم.</li>"
    )
    orders = "".join(f"<li>{html_escape(x)}</li>" for x in score.orders)
    notes = html_escape(report.notes or "لا توجد ملاحظات مسجلة.")
    sig = signature or settings.signature
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Daily Discipline Report</title><style>{_base_css()}</style></head>
<body><main class="page"><header class="hero"><img class="logo" src="{logo_data_uri()}" onerror="this.style.display='none'"><div><h1>تقرير القيادة والانضباط اليومي</h1><p>{html_escape(sig)} · تقرير تنفيذي لا يعتمد على المزاج</p></div></header>
<section class="content">
<div class="grid">{metrics}</div>
<div class="section"><h2>هوية التقرير</h2><div class="grid">{_metric_card("الطالب", student_name)}{_metric_card("الكلية", college)}{_metric_card("التاريخ", report.date_key)}{_metric_card("المواد", subjects)}</div></div>
<div class="section"><h2>مؤشر الانضباط</h2><div class="score-wrap"><div><div class="circle" style="--score:{score.score}"><strong>{score.score}</strong><small>من 100</small></div><p style="text-align:center"><span class="status {status_class}">{html_escape(score.status_ar)}</span></p></div><div>{score_rows}</div></div></div>
<div class="section"><h2>أوامر التصحيح لليوم التالي</h2><ol>{orders}</ol></div>
<div class="section"><h2>الإنذارات</h2><ul>{warnings}</ul></div>
<div class="section"><h2>ملاحظة الطالب</h2><div class="note">{notes}</div></div>
</section><footer class="footer"><span>Generated by {html_escape(sig)}</span><span>{generated}</span></footer></main></body></html>"""


def _safe_average(values: list[float]) -> float:
    return mean(values) if values else 0.0


def generate_weekly_html(profile, reports: list, signature: str | None = None) -> str:
    reports = sorted(reports, key=lambda x: x.date_key)
    student_name = getattr(profile, "full_name", None) or "الطالب"
    college = getattr(profile, "college", None) or "غير محدد"
    scores = [r.score for r in reports]
    total_study = sum((r.theory_minutes + r.practical_minutes) for r in reports)
    total_mcq = sum(r.mcq_total for r in reports)
    total_correct = sum(r.mcq_correct for r in reports)
    accuracy = (total_correct / total_mcq * 100) if total_mcq else 0.0
    avg_score = round(_safe_average([float(s) for s in scores]))
    green_days = sum(1 for r in reports if r.status == "green")
    yellow_days = sum(1 for r in reports if r.status == "yellow")
    red_days = sum(1 for r in reports if r.status == "red")
    best = max(reports, key=lambda r: r.score) if reports else None
    worst = min(reports, key=lambda r: r.score) if reports else None
    date_range = f"{reports[0].date_key} — {reports[-1].date_key}" if reports else "لا توجد بيانات"
    table_rows = (
        "".join(
            f"<tr><td>{html_escape(r.date_key)}</td><td>{r.score}</td><td>{format_minutes(r.theory_minutes + r.practical_minutes)}</td><td>{r.mcq_correct}/{r.mcq_total}</td><td>{r.essay_count}</td><td>{'✅' if r.phone_locked else '❌'}</td></tr>"
            for r in reports
        )
        or '<tr><td colspan="6">لا توجد تقارير ضمن الفترة.</td></tr>'
    )
    sig = signature or settings.signature
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    metrics = "".join(
        [
            _metric_card("متوسط الانضباط", f"{avg_score}/100", f"{len(reports)} يوم مسجل"),
            _metric_card("الدراسة الصافية", format_minutes(total_study), "خلال الفترة"),
            _metric_card("MCQ", f"{total_correct}/{total_mcq}", f"دقة {accuracy:.0f}%"),
            _metric_card("الأيام", f"{green_days} أخضر", f"{yellow_days} أصفر · {red_days} أحمر"),
        ]
    )
    diagnosis: list[str] = []
    if len(reports) < 5:
        diagnosis.append("البيانات غير مكتملة؛ سجل التقرير يوميًا حتى يكون الحكم دقيقًا.")
    if avg_score >= 85:
        diagnosis.append("الانضباط ممتاز. المطلوب تثبيت النظام لا زيادة الحمل بسرعة.")
    elif avg_score >= 70:
        diagnosis.append("النتيجة مقبولة، لكن يوجد تسرب يومي يمنع الوصول للتقدير العالي.")
    else:
        diagnosis.append("الأسبوع أحمر؛ أوقف تعديل الجداول وطبّق بروتوكول الإنقاذ 3 أيام متتالية.")
    if red_days >= 2:
        diagnosis.append("تكرر اليوم الأحمر مرتين أو أكثر؛ راجع الهاتف والنوم قبل زيادة ساعات الدراسة.")
    diagnosis_html = "".join(f"<li>{html_escape(x)}</li>" for x in diagnosis)
    best_text = f"{best.date_key} ({best.score}/100)" if best else "—"
    worst_text = f"{worst.date_key} ({worst.score}/100)" if worst else "—"
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Weekly Discipline Report</title><style>{_base_css()}</style></head>
<body><main class="page"><header class="hero"><img class="logo" src="{logo_data_uri()}" onerror="this.style.display='none'"><div><h1>تقرير القيادة الأسبوعي</h1><p>{html_escape(sig)} · قراءة رقمية لأداء 7 أيام</p></div></header>
<section class="content"><div class="grid">{metrics}</div>
<div class="section"><h2>هوية الفترة</h2><div class="grid">{_metric_card("الطالب", student_name)}{_metric_card("الكلية", college)}{_metric_card("الفترة", date_range)}{_metric_card("أفضل/أضعف يوم", best_text, worst_text)}</div></div>
<div class="section"><h2>جدول التنفيذ</h2><div style="overflow:auto"><table><thead><tr><th>التاريخ</th><th>النتيجة</th><th>الدراسة</th><th>MCQ</th><th>مقالي</th><th>الهاتف بعيد</th></tr></thead><tbody>{table_rows}</tbody></table></div></div>
<div class="section"><h2>تشخيص الأسبوع</h2><ul>{diagnosis_html}</ul></div>
</section><footer class="footer"><span>Generated by {html_escape(sig)}</span><span>{generated}</span></footer></main></body></html>"""


def last_n_date_keys(days: int = 7, today: date | None = None) -> list[str]:
    today = today or date.today()
    start = today - timedelta(days=max(0, days - 1))
    return [(start + timedelta(days=i)).isoformat() for i in range(days)]
