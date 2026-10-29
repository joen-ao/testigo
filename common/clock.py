"""The clock: real time in Bogotá (America/Bogota, UTC-05:00, no DST)."""

from datetime import datetime
from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo("America/Bogota")


def now():
    return datetime.now(BOGOTA)


def iso(dt=None):
    """RFC 3339 timestamp with the Bogotá offset, e.g. 2026-10-28T09:15:44-05:00."""
    return (dt or now()).isoformat(timespec="seconds")


def today():
    return now().strftime("%Y-%m-%d")
