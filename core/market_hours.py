from datetime import datetime
from zoneinfo import ZoneInfo

from config import MCX_CLOSE_TIME, MCX_OPEN_TIME

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN_WEEKDAYS = {0, 1, 2, 3, 4}


def is_market_open(now: datetime | None = None) -> bool:
    """Return whether the market is open on a weekday during configured hours."""
    current = now or datetime.now(IST)
    now_time = current.strftime("%H:%M")
    return (
        current.weekday() in MARKET_OPEN_WEEKDAYS
        and MCX_OPEN_TIME <= now_time <= MCX_CLOSE_TIME
    )


def get_market_schedule_text() -> str:
    """Return human-readable market schedule text."""
    return f"Monday-Friday, {MCX_OPEN_TIME}–{MCX_CLOSE_TIME} IST"
