"""The clock: real time at the team's fixed offset (UTC-05:00, no DST).

The demo's timestamps keep one fixed offset so receipts and runs sort the same
on every machine; the offset is the team's local time (it never changes over
the year)."""

from datetime import datetime, timedelta, timezone

TEAM_TZ = timezone(timedelta(hours=-5), "UTC-05:00")


def now():
    return datetime.now(TEAM_TZ)


def iso(dt=None):
    """RFC 3339 timestamp with the fixed offset, e.g. 2026-10-28T09:15:44-05:00."""
    return (dt or now()).isoformat(timespec="seconds")


def today():
    return now().strftime("%Y-%m-%d")
