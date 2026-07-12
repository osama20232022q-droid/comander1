from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.inspection import inspect

from app.config import settings
from app.db import get_session
from app.models import Base
from app.version import APP_VERSION

BACKUP_SCHEMA = "study_commander_v8"


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def build_database_export() -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema": BACKUP_SCHEMA,
        "app_version": APP_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "tables": {},
    }
    with get_session() as db:
        for mapper in Base.registry.mappers:
            cls = mapper.class_
            table = cls.__tablename__
            rows: list[dict[str, Any]] = []
            for obj in db.scalars(select(cls)).all():
                row: dict[str, Any] = {}
                for col in inspect(cls).columns:
                    row[col.name] = _serialize_value(getattr(obj, col.name))
                rows.append(row)
            data["tables"][table] = rows
    return data


def _fernet() -> Fernet | None:
    key = settings.backup_encryption_key
    if not key:
        return None
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise ValueError("BACKUP_ENCRYPTION_KEY غير صالح. يجب أن يكون Fernet key.") from exc


def export_database(path: str | Path) -> tuple[Path, bool]:
    """Export the database, encrypting it when a Fernet key is configured."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(build_database_export(), ensure_ascii=False, indent=2).encode("utf-8")
    fernet = _fernet()
    if fernet is None:
        if settings.require_encrypted_backups:
            raise RuntimeError("النسخ الاحتياطي المشفر مطلوب لكن BACKUP_ENCRYPTION_KEY غير مضاف.")
        path.write_bytes(payload)
        return path, False

    encrypted_path = path.with_suffix(path.suffix + ".enc")
    encrypted_path.write_bytes(fernet.encrypt(payload))
    return encrypted_path, True


def decode_backup_bytes(raw: bytes, filename: str = "") -> dict[str, Any]:
    encrypted = filename.endswith(".enc") or not raw.lstrip().startswith(b"{")
    if encrypted:
        fernet = _fernet()
        if fernet is None:
            raise ValueError("هذا الملف مشفر. أضف BACKUP_ENCRYPTION_KEY نفسه الذي استُخدم عند إنشائه.")
        try:
            raw = fernet.decrypt(raw)
        except InvalidToken as exc:
            raise ValueError("تعذر فك التشفير: المفتاح غير مطابق أو الملف تالف.") from exc

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("الملف ليس نسخة JSON صالحة.") from exc
    validate_backup_payload(data)
    return data


def validate_backup_payload(data: Any) -> None:
    if not isinstance(data, dict):
        raise ValueError("بنية النسخة الاحتياطية غير صحيحة.")
    schema = data.get("schema")
    if schema not in {"study_commander_v3", "study_commander_v8"}:
        raise ValueError(f"Schema غير مدعوم: {schema!r}")
    tables = data.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("قسم tables غير موجود أو غير صالح.")
    known_tables = {mapper.class_.__tablename__ for mapper in Base.registry.mappers}
    unknown = set(tables) - known_tables
    if unknown:
        raise ValueError("النسخة تحتوي جداول غير معروفة: " + ", ".join(sorted(unknown)[:10]))
    for table_name, rows in tables.items():
        if not isinstance(rows, list):
            raise ValueError(f"محتوى الجدول {table_name} يجب أن يكون قائمة.")
        if len(rows) > 1_000_000:
            raise ValueError(f"عدد السجلات في {table_name} غير منطقي.")
