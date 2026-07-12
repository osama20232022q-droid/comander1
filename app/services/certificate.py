from __future__ import annotations

from datetime import datetime

from app.config import settings
from app.services.assets import logo_data_uri
from app.utils import html_escape


def certificate_html(
    student_name: str, cert_type: str, hours: float, sessions: int, subjects_count: int, score: int, reason: str
) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    signature_letters = "S C B · A D S"
    title = "شهادة إنجاز يوم مميز" if cert_type == "daily" else "شهادة إنجاز أسبوعي"
    subtitle = "Academic Discipline Merit Certificate"
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>Certificate</title>
<style>
body{{margin:0;background:#edf2f7;font-family:Tahoma,Arial,sans-serif;color:#102033}}
.page{{width:1040px;margin:32px auto;background:linear-gradient(145deg,#ffffff,#f8fbff);border:1px solid #d6a13a;box-shadow:0 22px 80px rgba(0,0,0,.18);position:relative;padding:54px 64px;overflow:hidden}}
.page:before{{content:"";position:absolute;inset:18px;border:5px double #0b2d5c;pointer-events:none}}
.page:after{{content:"";position:absolute;left:-90px;top:-90px;width:260px;height:260px;background:radial-gradient(circle,#d6a13a44,#ffffff00 70%);}}
.header{{text-align:center;border-bottom:2px solid #d6a13a;padding-bottom:22px}}
.logo{{width:104px;height:104px;border-radius:24px;object-fit:cover;margin-bottom:10px}}
h1{{margin:0;font-size:44px;color:#0b2d5c;letter-spacing:1px}}
.subtitle{{font-size:18px;color:#5d6b80;margin-top:8px}}
.present{{font-size:21px;line-height:1.9;text-align:center;margin-top:35px}}
.name{{font-size:42px;margin:18px 0;text-align:center;color:#0b2d5c;font-weight:800}}
.reason{{text-align:center;font-size:20px;line-height:1.8;color:#25364a;max-width:820px;margin:0 auto}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:38px 0}}
.card{{border:1px solid #d9e2ef;border-radius:18px;padding:18px;background:#fbfdff;text-align:center}}
.num{{font-size:31px;color:#0b7d91;font-weight:bold}}
.label{{font-size:15px;color:#58677a;margin-top:8px}}
.footer{{display:flex;justify-content:space-between;align-items:end;margin-top:48px}}
.signature{{text-align:left;color:#0b2d5c}}
.sigline{{font-family:Georgia,serif;font-style:italic;font-size:28px;letter-spacing:3px;color:#0f766e;border-bottom:2px solid #d6a13a;padding-bottom:7px;display:inline-block}}
.small{{font-size:13px;color:#718096;margin-top:8px}}
.badge{{background:#0b2d5c;color:white;border-radius:999px;padding:12px 20px;font-weight:bold;border:2px solid #d6a13a}}
</style></head><body><div class="page">
  <div class="header"><img class="logo" src="{logo_data_uri()}" onerror="this.style.display='none'"><h1>{html_escape(title)}</h1><div class="subtitle">{html_escape(subtitle)}</div></div>
  <div class="present">تُمنح هذه الشهادة إلى الطالب/ـة</div>
  <div class="name">{html_escape(student_name)}</div>
  <div class="reason">{html_escape(reason)}</div>
  <div class="stats">
    <div class="card"><div class="num">{hours:.1f}</div><div class="label">ساعة دراسة صافية</div></div>
    <div class="card"><div class="num">{sessions}</div><div class="label">جلسات منجزة</div></div>
    <div class="card"><div class="num">{subjects_count}</div><div class="label">مواد منظمة</div></div>
    <div class="card"><div class="num">{score}</div><div class="label">Discipline Score</div></div>
  </div>
  <div class="footer"><div class="badge">Verified by {html_escape(settings.signature)}</div><div class="signature"><div class="sigline">{html_escape(signature_letters)}</div><div class="small">Bot Signature · {date}</div></div></div>
</div></body></html>"""
