from __future__ import annotations

import base64
from pathlib import Path


def logo_data_uri() -> str:
    path = Path(__file__).resolve().parents[2] / "assets" / "logo.png"
    if not path.exists():
        return ""
    try:
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{data}"
    except Exception:
        return ""
