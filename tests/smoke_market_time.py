# queen/tests/smoke_market_time.py
from __future__ import annotations

from queen.helpers.market import (
    current_historical_service_day,
    get_market_state,
    is_market_open,
)


def test():
    st = get_market_state()
    assert "session" in st and "gate" in st and "service_day" in st
    assert isinstance(is_market_open(), bool)
    sd = current_historical_service_day()
    assert len(str(sd)) == 10  # YYYY-MM-DD
    print("✅ smoke_market_time: passed")


if __name__ == "__main__":
    test()
