# queen/tests/test_indicator_kwargs.py
from queen.helpers.common import indicator_call_kwargs


def test_indicator_call_kwargs_filters_meta():
    params = {"length": 14, "min_bars": 100, "timeframe": "5m", "smooth": 3}
    out = indicator_call_kwargs(params)
    assert out == {"length": 14, "smooth": 3}
