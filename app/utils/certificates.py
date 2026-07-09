from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.config import settings


@dataclass
class CertificateData:
    student_name: str
    week_start: date
    week_end: date
    study_hours: float
    sessions: int
    subjects_done: list[str]
    discipline_score: int
    daily_minutes: dict[str, int]


def _bars_svg(daily_minutes: dict[str, int]) -> str:
    max_min = max(daily_minutes.values() or [1])
    x = 20
    bars = []
    for day, minutes in daily_minutes.items():
        height = int((minutes / max_min) * 120) if max_min else 0
        y = 150 - height
        bars.append(f"<rect x='{x}' y='{y}' width='34' height='{height}' rx='5'></rect>")
        bars.append(f"<text x='{x+17}' y='170' text-anchor='middle' font-size='10'>{html.escape(day[-5:])}</text>")
        bars.append(f"<text x='{x+17}' y='{max(15, y-5)}' text-anchor='middle' font-size='10'>{minutes//60}h</text>")
        x += 52
    return f"<svg width='420' height='190' viewBox='0 0 420 190' aria-label='Study hours chart'>{''.join(bars)}</svg>"


def render_certificate(data: CertificateData, output_dir: Path | None = None) -> Path:
    output_dir = output_dir or settings.certificates_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = ''.join(c if c.isalnum() else '_' for c in data.student_name)[:40]
    filename = f'certificate_{safe_name}_{data.week_start}_{data.week_end}.html'
    path = output_dir / filename
    subjects = ', '.join(data.subjects_done) if data.subjects_done else 'Progress recorded'
    chart = _bars_svg(data.daily_minutes)
    content = f"""<!doctype html>
<html lang='ar' dir='rtl'>
<head>
<meta charset='utf-8'>
<title>Certificate of Achievement</title>
<style>
  body {{ margin:0; background:#f6f6f6; font-family: Arial, Tahoma, sans-serif; }}
  .page {{ width: 900px; min-height: 1250px; margin: 24px auto; background: white; border: 1px solid #ddd; padding: 70px; box-sizing: border-box; }}
  .border {{ border: 4px solid #222; min-height: 1080px; padding: 45px; text-align:center; }}
  h1 {{ font-size: 44px; margin: 10px 0 0; letter-spacing: 1px; }}
  h2 {{ font-size: 34px; margin: 20px 0; }}
  .sub {{ font-size: 20px; color:#555; }}
  .name {{ font-size: 42px; font-weight: bold; margin: 35px 0; }}
  .stats {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; margin:30px 0; text-align:right; }}
  .card {{ border:1px solid #ddd; border-radius:14px; padding:18px; font-size:20px; }}
  .score {{ font-size:52px; font-weight:bold; }}
  svg rect {{ fill:#222; }}
  .signature {{ margin-top:45px; display:flex; justify-content:space-between; font-size:18px; }}
  @media print {{ body {{ background:white; }} .page {{ margin:0; border:0; }} }}
</style>
</head>
<body>
<div class='page'>
  <div class='border'>
    <div class='sub'>Study Commander Bot</div>
    <h1>Certificate of Achievement</h1>
    <div class='sub'>شهادة تقدير للالتزام الدراسي الأسبوعي</div>
    <p class='sub'>تُمنح هذه الشهادة إلى</p>
    <div class='name'>{html.escape(data.student_name)}</div>
    <p class='sub'>عن الفترة من {data.week_start} إلى {data.week_end}</p>
    <div class='stats'>
      <div class='card'><b>ساعات الدراسة الصافية:</b><br>{data.study_hours:.1f} ساعة</div>
      <div class='card'><b>عدد الجلسات:</b><br>{data.sessions}</div>
      <div class='card'><b>المواد/المهام المنجزة:</b><br>{html.escape(subjects)}</div>
      <div class='card'><b>Discipline Score:</b><br><span class='score'>{data.discipline_score}</span>/100</div>
    </div>
    <h2>مخطط ساعات الأسبوع</h2>
    {chart}
    <div class='signature'>
      <div>التاريخ: {date.today().isoformat()}</div>
      <div>التوقيع: {html.escape(settings.bot_signature)}</div>
    </div>
  </div>
</div>
</body>
</html>"""
    path.write_text(content, encoding='utf-8')
    return path
