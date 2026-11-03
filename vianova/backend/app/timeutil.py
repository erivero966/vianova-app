"""Utilidades de fecha y hora. Todas las fechas se guardan en hora de Perú (UTC-5) sin tzinfo."""
from datetime import datetime, timedelta, timezone

PERU = timezone(timedelta(hours=-5))


def now() -> datetime:
    return datetime.now(PERU).replace(tzinfo=None, microsecond=0)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=PERU).isoformat()


def parse(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(PERU).replace(tzinfo=None)
    return dt
