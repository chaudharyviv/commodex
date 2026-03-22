from datetime import datetime as real_datetime

import core.ui_helpers as ui_helpers


class FixedDateTime(real_datetime):
    current = real_datetime(2026, 3, 20, 10, 0)

    @classmethod
    def now(cls, tz=None):
        dt = cls.current
        if tz is not None:
            return dt.replace(tzinfo=tz)
        return dt


def test_get_market_status_open_on_weekday(monkeypatch):
    FixedDateTime.current = real_datetime(2026, 3, 20, 10, 0)
    monkeypatch.setattr(ui_helpers, "datetime", FixedDateTime)

    status = ui_helpers.get_market_status()

    assert status["is_open"] is True
    assert status["day"] == "Friday"
    assert status["schedule"] == "Monday-Friday, 09:00–23:30 IST"


def test_get_market_status_closed_on_weekend(monkeypatch):
    FixedDateTime.current = real_datetime(2026, 3, 22, 10, 0)
    monkeypatch.setattr(ui_helpers, "datetime", FixedDateTime)

    status = ui_helpers.get_market_status()

    assert status["is_open"] is False
    assert status["day"] == "Sunday"
    assert status["schedule"] == "Monday-Friday, 09:00–23:30 IST"
