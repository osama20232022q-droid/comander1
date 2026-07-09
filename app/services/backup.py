from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.inspection import inspect
from app.db import get_session
from app.models import Base


def _serialize_value(v):
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def export_database_to_json(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"schema": "study_commander_v3", "created_at": datetime.now(timezone.utc).isoformat(), "tables": {}}
    with get_session() as db:
        for mapper in Base.registry.mappers:
            cls = mapper.class_
            table = cls.__tablename__
            rows = []
            for obj in db.scalars(select(cls)).all():
                row = {}
                for col in inspect(cls).columns:
                    row[col.name] = _serialize_value(getattr(obj, col.name))
                rows.append(row)
            data["tables"][table] = rows
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
