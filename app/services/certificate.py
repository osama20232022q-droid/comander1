from __future__ import annotations

from datetime import datetime
from app.config import settings
from app.services.assets import logo_data_uri
from app.utils import html_escape


def certificate_html(student_name: str, hours: float, sessions: int, subjects_count: int, score: int) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head><meta charset="utf-8"><title>Certificate</title>
<style>
body{{margin:0;background:#eef2f7;font-family:Tahoma,Arial,sans-serif;color:#102033}}
.page{{width:980px;margin:32px auto;background:linear-gradient(145deg,#fff,#f8fbff);border:14px solid #0b2d5c;box-shadow:0 20px 70px rgba(0,0,0,.18);position:relative;padding:48px 58px}}
.page:before{{content:"";position:absolute;inset:18px;border:3px solid #d6a13a;pointer-events:none}}
.header{{text-align:center;border-bottom:2px solid #d6a13a;padding-bottom:18px}}
.logo{{width:96px;height:96px;border-radius:22px;object-fit:cover;margin-bottom:10px}}
h1{{margin:0;font-size:42px;color:#0b2d5c;letter-spacing:1px}}
.subtitle{{font-size:18px;color:#5d6b80;margin-top:8px}}
.name{{font-size:38px;margin:40px 0 14px;text-align:center;color:#0b2d5c;font-weight:bold}}
.text{{font-size:21px;line-height:1.9;text-align:center}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:36px 0}}
.card{{border:1px solid #d9e2ef;border-radius:16px;padding:18px;background:#fbfdff;text-align:center}}
.num{{font-size:30px;color:#0b7d91;font-weight:bold}}
.label{{font-size:15px;color:#58677a;margin-top:8px}}
.seal{{width:150px;height:150px;border:5px double #d6a13a;border-radius:50%;display:flex;align-items:center;justify-content:center;text-align:center;color:#0b2d5c;font-weight:bold;transform:rotate(-8deg);background:rgba(214,161,58,.08)}}
.footer{{display:flex;justify-content:space-between;align-items:end;margin-top:42px}}
.sign{{text-align:left;font-size:16px;color:#34455c}}
.small{{font-size:13px;color:#718096}}
</style></head><body>
<div class="page">
  <div class="header">
    <img class="logo" src="{logo_data_uri()}" onerror="this.style.display='none'">
    <h1>شهادة تقدير</h1>
    <div class="subtitle">Academic Discipline Achievement Certificate</div>
  </div>
  <div class="text">تُمنح هذه الشهادة إلى الطالب/ـة</div>
  <div class="name">{html_escape(student_name)}</div>
  <div class="text">تقديرًا لالتزامه/ها في نظام الدراسة، وإنجاز جلسات متابعة وانضباط خلال هذا الأسبوع.</div>
  <div class="stats">
    <div class="card"><div class="num">{hours:.1f}</div><div class="label">ساعة دراسة صافية</div></div>
    <div class="card"><div class="num">{sessions}</div><div class="label">جلسات منجزة</div></div>
    <div class="card"><div class="num">{subjects_count}</div><div class="label">مواد منظمة</div></div>
    <div class="card"><div class="num">{score}</div><div class="label">Discipline Score</div></div>
  </div>
  <div class="footer">
    <div class="seal">ختم<br>{html_escape(settings.signature)}</div>
    <div class="sign"><b>{html_escape(settings.signature)}</b><br>Academic Discipline System<br><span class="small">Date: {date}</span></div>
  </div>
</div>
</body></html>"""
