"""Regression tests for timestamp values bound to DB DateTime columns."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime

from db import models
from db.base import Base
from db.repository import _coerce_db_datetime, _coerce_db_values, _db_utcnow
from services.batch_service import _utcnow_naive as batch_utcnow_naive


def _generated_datetime(column_default):
    if column_default is None or not callable(column_default.arg):
        return None
    try:
        value = column_default.arg()
    except TypeError:
        value = column_default.arg(None)
    return value if isinstance(value, datetime) else None


def test_repository_datetime_helpers_emit_naive_utc_values():
    offset = timezone(timedelta(hours=5, minutes=30))
    aware_value = datetime(2026, 6, 6, 20, 35, 9, tzinfo=offset)
    naive_value = datetime(2026, 6, 6, 20, 35, 9)

    coerced = _coerce_db_datetime(aware_value)

    assert coerced == datetime(2026, 6, 6, 15, 5, 9)
    assert coerced.tzinfo is None
    assert _coerce_db_datetime(naive_value) == naive_value
    assert _coerce_db_datetime(None) is None
    assert _coerce_db_values({"completed_at": aware_value, "status": "completed"}) == {
        "completed_at": datetime(2026, 6, 6, 15, 5, 9),
        "status": "completed",
    }
    assert _db_utcnow().tzinfo is None
    assert batch_utcnow_naive().tzinfo is None


def test_orm_datetime_python_defaults_emit_naive_values():
    # PostgreSQL asyncpg rejects timezone-aware values for the current
    # timestamp-without-timezone migrations. Keep ORM-generated values naive UTC.
    checked_defaults = []

    # Import side effect: register every ORM class from db.models with Base.
    assert models.Analysis.__tablename__ == "analyses"

    for mapper in Base.registry.mappers:
        model = mapper.class_
        for column in model.__table__.columns:
            if not isinstance(column.type, DateTime):
                continue
            for column_default in (column.default, column.onupdate):
                value = _generated_datetime(column_default)
                if value is None:
                    continue
                checked_defaults.append(f"{model.__name__}.{column.name}")
                assert value.tzinfo is None, f"{model.__name__}.{column.name} produced {value!r}"

    assert checked_defaults
