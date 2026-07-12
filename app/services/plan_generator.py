from __future__ import annotations

from datetime import datetime, timedelta

from app.config import settings
from app.services.assets import logo_data_uri
from app.utils import html_escape


def _level_factor(level: str) -> float:
    return {"ضعيف": 1.45, "متوسط": 1.15, "جيد": 0.95, "ممتاز": 0.78}.get(level, 1.15)


def _target_factor(target: str) -> float:
    return {"مقبول": 0.8, "متوسط": 0.95, "جيد": 1.1, "جيد جدًا": 1.28, "امتياز": 1.5}.get(target, 1.1)


def _exam_factor(exam_type: str, qtype: str) -> float:
    f = {"يومي": 0.7, "Mid": 1.0, "End Module": 1.15, "شهري": 1.05, "Final": 1.45}.get(exam_type, 1.0)
    q = {"MCQ": 0.95, "Short essay": 1.25, "عملي": 1.15, "شفوي": 1.1, "مختلط": 1.35}.get(qtype, 1.1)
    return f * q


def _page_minutes(study_domain: str, question_type: str) -> float:
    # realistic page-minutes, not blind count of files
    base = 4.5
    if study_domain == "medicine":
        base = 5.5
    if question_type in ["Short essay", "مختلط"]:
        base += 1.3
    if question_type == "عملي":
        base += 0.8
    return base


def generate_plan_html(profile, subject, request: dict, material_stats: dict, past_stats: dict) -> str:
    level = request.get("level", "متوسط")
    target = request.get("target", "جيد")
    exam_type = request.get("exam_type", "Final")
    question_type = request.get("question_type", "مختلط")
    days_left = max(1, int(request.get("days_left", 7)))
    grade_out = request.get("grade_out", "100")
    pages = max(1, int(request.get("pages_count") or material_stats.get("estimated_pages") or 12))
    wake = request.get("wake_time", "05:00")
    sleep = request.get("sleep_time", "22:00") or "غير ثابت"
    other_materials = request.get("other_materials", "لا")

    l_factor = _level_factor(level)
    t_factor = _target_factor(target)
    e_factor = _exam_factor(exam_type, question_type)
    per_page = _page_minutes(profile.study_domain, question_type)

    reading_hours = pages * per_page / 60.0
    questions_hours = max(0.35, past_stats.get("count", 0) * 0.35)
    review_hours = max(0.5, reading_hours * 0.35)
    practical_hours = 0.0
    if question_type in ["عملي", "مختلط"] or profile.study_domain == "medicine":
        practical_hours = max(0.4, pages * 0.9 / 60.0)

    total = (reading_hours + questions_hours + review_hours + practical_hours) * l_factor * t_factor * e_factor
    # prevent absurd estimates: a tiny handout should not become 4 hours unless the target/exam requires it
    min_total = 0.75 if pages <= 8 and exam_type == "يومي" else 1.25
    estimated_total_hours = round(max(min_total, total), 1)
    daily_hours = round(max(0.5, estimated_total_hours / days_left), 1)

    focus = []
    if question_type == "Short essay":
        focus += ["حوّل كل عنوان إلى جواب قصير من 3-5 نقاط.", "احفظ التعاريف والمقارنات بصياغة إنكليزية دقيقة."]
    elif question_type == "MCQ":
        focus += [
            "استخرج الفروقات والأرقام والكلمات المفتاحية؛ هذه أكثر مصادر الفخاخ.",
            "بعد كل قراءة قصيرة حل أسئلة مباشرة ولا تؤجل الاختبار.",
        ]
    elif question_type == "عملي":
        focus += [
            "اجعل الصور/السلايدات مراجعة يومية قصيرة ولا تكتفي بالنظري.",
            "اكتب لكل صورة: الاسم، العلامة المميزة، سؤال محتمل.",
        ]
    else:
        focus += ["قسّم الوقت: فهم سريع ثم MCQ ثم Short essay ثم مراجعة أخطاء."]
    if past_stats.get("count", 0):
        focus.append("أسئلة السنوات تعتبر دليل تركيز الأساتذة: راجعها قبل وبعد قراءة الملزمة.")
    if other_materials and str(other_materials).strip() not in ["لا", "لا يوجد", "none"]:
        focus.append(
            "لأن عندك مواد أخرى، لا تضع كل الطاقة في هذه المادة؛ اعتمد جلسات قصيرة صافية لا جلسات طويلة وهمية."
        )

    start_date = datetime.now().date()
    rows = []
    for i in range(1, days_left + 1):
        day = start_date + timedelta(days=i - 1)
        if i == 1:
            mission = "مسح سريع + تقسيم العناوين + تحديد الفخاخ"
        elif i <= max(1, int(days_left * 0.45)):
            mission = "قراءة وفهم + استخراج Short notes"
        elif i <= max(2, int(days_left * 0.75)):
            mission = "أسئلة سنوات + MCQ/Short essay + تصحيح أخطاء"
        else:
            mission = "High-yield + مراجعة أخطاء + اختبار ذاتي"
        rows.append((i, str(day), mission, daily_hours))

    table = "".join(
        [f"<tr><td>{d}</td><td>{date}</td><td>{html_escape(m)}</td><td>{hrs} h</td></tr>" for d, date, m, hrs in rows]
    )
    bullets = "".join([f"<li>{html_escape(x)}</li>" for x in focus])

    file_note = f"ملحقات المادة: {material_stats.get('count', 0)} — أسئلة السنوات: {past_stats.get('count', 0)} — صفحات/وحدات مدخلة: {pages}"

    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>Study Plan</title>
<style>
body{{font-family:Tahoma,Arial,sans-serif;background:#eef3f8;margin:0;color:#14213d}}
.wrap{{max-width:1080px;margin:28px auto;background:#fff;border-radius:26px;box-shadow:0 18px 60px rgba(15,23,42,.14);overflow:hidden}}
.hero{{background:linear-gradient(135deg,#071f45,#0f766e);color:white;padding:34px 42px;position:relative}}
.hero h1{{margin:0;font-size:34px}} .hero p{{margin:10px 0 0;color:#dff7f5}}
.logo{{width:82px;height:82px;border-radius:20px;float:left;background:white;padding:5px}}
.content{{padding:34px 42px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:18px 0}}
.card{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:18px;padding:18px}}
.k{{color:#64748b;font-size:14px}} .v{{font-size:22px;font-weight:bold;color:#0b2d5c;margin-top:6px}}
table{{width:100%;border-collapse:collapse;margin-top:18px}} th,td{{border:1px solid #dbe4ef;padding:12px;text-align:center}} th{{background:#0b2d5c;color:#fff}} tr:nth-child(even){{background:#f8fafc}}
.section{{margin-top:30px}} li{{margin:10px 0;line-height:1.7}}
.warn{{background:#fff7ed;border:1px solid #fed7aa;border-radius:16px;padding:16px;line-height:1.7}}
.footer{{margin-top:32px;border-top:1px solid #e2e8f0;padding-top:18px;color:#64748b;font-size:13px}}
</style></head><body><div class="wrap">
<div class="hero"><img class="logo" src="{logo_data_uri()}" onerror="this.style.display='none'"><h1>خطة دراسية تنفيذية معمقة</h1><p>{html_escape(settings.signature)} — خطة حسب المادة، مستوى الطالب، نوع الامتحان، الأيام، وأسئلة السنوات.</p></div>
<div class="content">
<div class="grid">
<div class="card"><div class="k">المادة</div><div class="v">{html_escape(subject.name)}</div></div>
<div class="card"><div class="k">المستوى الحالي</div><div class="v">{html_escape(level)}</div></div>
<div class="card"><div class="k">الهدف</div><div class="v">{html_escape(target)}</div></div>
<div class="card"><div class="k">نوع الامتحان</div><div class="v">{html_escape(exam_type)}</div></div>
<div class="card"><div class="k">نمط الأسئلة</div><div class="v">{html_escape(question_type)}</div></div>
<div class="card"><div class="k">الدرجة</div><div class="v">من {html_escape(str(grade_out))}</div></div>
<div class="card"><div class="k">الأيام المتبقية</div><div class="v">{days_left}</div></div>
<div class="card"><div class="k">الوقت الكلي المتوقع</div><div class="v">{estimated_total_hours} h</div></div>
<div class="card"><div class="k">المعدل اليومي</div><div class="v">{daily_hours} h</div></div>
</div>
<div class="section"><h2>التحليل الواقعي</h2><div class="warn"><b>{html_escape(file_note)}</b><br>وقت الاستيقاظ: <b>{html_escape(wake)}</b> — وقت النوم: <b>{html_escape(sleep)}</b> — مواد أخرى: <b>{html_escape(other_materials)}</b><br>التقدير لا يعتمد على عدد الملفات وحده؛ يعتمد على الصفحات، نمط السؤال، مستواك، هدفك، ووجود أسئلة سنوات.</div></div>
<div class="section"><h2>الجدول التنفيذي</h2><table><tr><th>اليوم</th><th>التاريخ</th><th>المهمة</th><th>ساعات صافية</th></tr>{table}</table></div>
<div class="section"><h2>أين تركز؟</h2><ul>{bullets}</ul></div>
<div class="section"><h2>قانون التنفيذ</h2><p>اليوم الناجح = قراءة محددة + أسئلة محلولة + أخطاء مسجلة. لا تُحسب الساعات إذا كان الملف مفتوحًا فقط.</p></div>
<div class="footer">Generated by {html_escape(settings.signature)} — لا تُعرض البيانات الخام للطالب في الملف النهائي.</div>
</div></div></body></html>"""
