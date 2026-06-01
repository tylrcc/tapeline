"""sanity tests for the golden model. these are fast and run in CI before we
ever spin up a verilog sim, because if the python is wrong the hardware test is
just confidently wrong too.
"""

import pytest

from reference import rolling_mac, to_q


def test_warmup_holds_valid_low():
    # first WINDOW-1 ticks must not produce a reading
    window = 8
    ticks = [(to_q(100.0), 10)] * 20
    out = list(rolling_mac(ticks, window))
    assert all(not v for v, _, _ in out[: window - 1])
    assert all(v for v, _, _ in out[window - 1 :])


def test_constant_price_is_a_fixed_point():
    # constant price in -> same price out for sma and vwap
    window = 16
    px = to_q(42.5)
    ticks = [(px, 7)] * 100
    for valid, sma, vwap in rolling_mac(ticks, window):
        if valid:
            assert sma == px
            assert vwap == px


def test_rolling_matches_naive_recompute():
    # the running accumulators must agree with a dumb full re-sum of the window
    window = 32
    import random

    rng = random.Random(1234)
    ticks = [(to_q(rng.uniform(10, 200)), rng.randint(0, 100)) for _ in range(500)]

    buf = []
    for i, (valid, sma, vwap) in enumerate(rolling_mac(ticks, window)):
        buf.append(ticks[i])
        if len(buf) > window:
            buf.pop(0)
        if valid:
            naive_sma = sum(p for p, _ in buf) >> (window.bit_length() - 1)
            den = sum(v for _, v in buf)
            naive_vwap = (sum(p * v for p, v in buf) // den) if den > 0 else naive_sma
            assert sma == naive_sma
            assert vwap == naive_vwap


def test_zero_volume_window_falls_back_to_sma():
    # if every tick in the window had zero size, vwap is undefined, fall back to sma
    window = 4
    ticks = [(to_q(10.0), 0)] * 10
    for valid, sma, vwap in rolling_mac(ticks, window):
        if valid:
            assert vwap == sma


def test_non_pow2_window_rejected():
    with pytest.raises(ValueError):
        list(rolling_mac([(to_q(1.0), 1)], window=48))
