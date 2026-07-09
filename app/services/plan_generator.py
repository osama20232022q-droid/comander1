from __future__ import annotations

import json
from datetime import datetime, timedelta
from app.utils import html_escape
from app.config import settings
from app.services.assets import logo_data_uri


def _difficulty_multiplier(level: str, target: str) -> float:
    base = {"ضعيف": 1.6, "متوسط": 1.25, "جيد": 1.0, "ممتاز": 0.85}.get(level, 1.2)
    target_add = {"مقبول": 0.85, "متوسط": 1.0, "جيد": 1.1, "جيد جدًا": 1.25, "امتياز": 1.45}.get(target, 1.1)
    return base * target_add


def generate_plan_html(profile, subject, request: dict, material_count: int, past_count: int) -> str:
    level = request.get("level", "متوسط")
    target = request.get("target", "جيد")
    exam_type = request.get("exam_type", "Final")
    question_type = request.get("question_type", "مختلط")
    days_left = max(1, int(request.get("days_left", 7)))
    grade_out = request.get("grade_out", "100")
    wake = request.get("wake_time", "05:00")
    sleep = request.get("sleep_time", "22:00") or "غير ثابت"
    other_materials = request.get("other_materials", "لا")

    multiplier = _difficulty_multiplier(level, target)
    file_weight = max(1, material_count) * 1.1 + past_count * 0.7
    estimated_total_hours = round(max(3.0, file_weight * multiplier * 2.1), 1)
    daily_hours = round(estimated_total_hours / days_left, 1)
    daily_hours = max(1.0, daily_hours)

    rows = []
    start_date = datetime.now().date()
    for i in range(1, days_left + 1):
        day = start_date + timedelta(days=i-1)
        if i <= max(1, int(days_left * 0.55)):
            mission = "قراءة وفهم + تعليم النقاط الصعبة"
        elif i <= max(2, int(days_left * 0.8)):
            mission = "MCQ/Short essay + مراجعة أسئلة السنوات"
        else:
            mission = "High-yield + اختبار ذاتي + سد الثغرات"
        rows.append((i, str(day), mission, daily_hours))

    high_yield = [
        "ابدأ بالتعاريف والمقارنات والجداول قبل التفاصيل الطويلة.",
        "أسئلة السنوات تُراجع يوميًا لأنّها تكشف تركيز الأساتذة.",
        "كل جلسة ثقيلة يعقبها MCQ حتى تتحول القراءة إلى درجات.",
        "لا تعتمد على ساعات الجلوس؛ اعتمد على ناتج الجلسة: صفحات/أسئلة/أخطاء.",
    ]
    if profile.study_domain == "medicine":
        high_yield.append("للمواد الطبية: افصل النظري عن العملي، واجعل الصور/السلايدات مراجعة يومية قصيرة.")

    table = "".join([f"<tr><td>{d}</td><td>{date}</td><td>{html_escape(m)}</td><td>{hrs} h</td></tr>" for d, date, m, hrs in rows])
    bullets = "".join([f"<li>{html_escape(x)}</li>" for x in high_yield])
    req_json = html_escape(json.dumps(request, ensure_ascii=False, indent=2))

    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>Study Plan</title>
<style>
body{{font-family:Tahoma,Arial,sans-serif;background:#f1f5f9;margin:0;color:#14213d}}
.wrap{{max-width:1050px;margin:28px auto;background:#fff;border-radius:24px;box-shadow:0 16px 55px rgba(15,23,42,.12);overflow:hidden}}
.hero{{background:linear-gradient(135deg,#0b2d5c,#0f766e);color:white;padding:34px 42px;position:relative}}
.hero h1{{margin:0;font-size:34px}} .hero p{{margin:10px 0 0;color:#dff7f5}}
.logo{{width:78px;height:78px;border-radius:18px;float:left;background:white;padding:5px}}
.content{{padding:34px 42px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:18px 0}}
.card{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:18px;padding:18px}}
.k{{color:#64748b;font-size:14px}} .v{{font-size:22px;font-weight:bold;color:#0b2d5c;margin-top:6px}}
table{{width:100%;border-collapse:collapse;margin-top:18px}} th,td{{border:1px solid #dbe4ef;padding:12px;text-align:center}} th{{background:#0b2d5c;color:#fff}} tr:nth-child(even){{background:#f8fafc}}
.section{{margin-top:30px}} li{{margin:10px 0;line-height:1.6}}
pre{{direction:ltr;text-align:left;background:#0f172a;color:#d1e7ff;padding:16px;border-radius:12px;overflow:auto}}
.footer{{margin-top:32px;border-top:1px solid #e2e8f0;padding-top:18px;color:#64748b;font-size:13px}}
</style></head><body><div class="wrap">
<div class="hero"><img class="logo" src="{logo_data_uri()}" onerror="this.style.display='none'"><h1>خطة دراسية معمقة</h1><p>{html_escape(settings.signature)} — خطة ذكية حسب بيانات الطالب والمادة والامتحان.</p></div>
<div class="content">
<div class="grid">
<div class="card"><div class="k">الطالب</div><div class="v">{html_escape(profile.full_name)}</div></div>
<div class="card"><div class="k">المادة</div><div class="v">{html_escape(subject.name)}</div></div>
<div class="card"><div class="k">الكلية/المرحلة</div><div class="v">{html_escape(profile.college)} / {html_escape(profile.stage)}</div></div>
<div class="card"><div class="k">المستوى الحالي</div><div class="v">{html_escape(level)}</div></div>
<div class="card"><div class="k">الهدف</div><div class="v">{html_escape(target)}</div></div>
<div class="card"><div class="k">نوع الامتحان</div><div class="v">{html_escape(exam_type)}</div></div>
<div class="card"><div class="k">نمط الأسئلة</div><div class="v">{html_escape(question_type)}</div></div>
<div class="card"><div class="k">الدرجة</div><div class="v">من {html_escape(str(grade_out))}</div></div>
<div class="card"><div class="k">الأيام المتبقية</div><div class="v">{days_left}</div></div>
</div>
<div class="section"><h2>التحليل الواقعي</h2><p>عدد ملحقات المادة: <b>{material_count}</b>، أسئلة السنوات: <b>{past_count}</b>. الوقت الكلي المتوقع: <b>{estimated_total_hours}</b> ساعة، والمعدل اليومي المطلوب: <b>{daily_hours}</b> ساعة صافية تقريبًا.</p><p>وقت الاستيقاظ: <b>{html_escape(wake)}</b> — وقت النوم: <b>{html_escape(sleep)}</b> — وجود مواد أخرى: <b>{html_escape(other_materials)}</b>.</p></div>
<div class="section"><h2>الجدول التنفيذي</h2><table><tr><th>اليوم</th><th>التاريخ</th><th>المهمة</th><th>ساعات صافية</th></tr>{table}</table></div>
<div class="section"><h2>نقاط تركيز ذكية</h2><ul>{bullets}</ul></div>
<div class="section"><h2>قانون التنفيذ</h2><p>كل يوم يجب أن ينتج عنه: صفحات مفهومة + أسئلة محلولة + أخطاء مسجلة. لا تُحسب الجلسة إذا كان الملف مفتوحًا فقط بدون ناتج.</p></div>
<div class="section"><h2>بيانات الطلب الخام</h2><pre>{req_json}</pre></div>
<div class="footer">Generated by {html_escape(settings.signature)} — هذه الخطة تنظيمية تعليمية وليست نصيحة طبية أو نفسية.</div>
</div></div></body></html>"""
