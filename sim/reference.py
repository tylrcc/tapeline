"""golden model for the mac engine.

this is the source of truth. the verilog in rtl/mac_engine.v and the
self-checking testbench both have to match this bit for bit, so the cheapest
place to reason about the math is right here in plain python.

everything is integer / fixed point on purpose. px is Q16.16 (price * 2**16),
vol is a plain non-negative integer. no floats anywhere, because the hardware
cannot do floats and i want the laptop and the fpga to agree exactly.
"""

from collections import deque

Q = 16  # fractional bits. Q16.16


def _log2_exact(n):
    """log2 for power-of-two window sizes. blows up loudly otherwise, which is
    what i want, the rtl divides the sma by a shift and that only works on pow2."""
    if n <= 0 or (n & (n - 1)) != 0:
        raise ValueError("window must be a power of two, got %d" % n)
    return n.bit_length() - 1


def rolling_mac(ticks, window):
    """run the rolling sma + vwap over a stream of (px, vol) ticks.

    yields one (valid, sma, vwap) per input tick. valid is False until the
    window is full. once warm, every tick produces a fresh reading.

    the whole point of the design lives here: we never re-sum the window. we
    keep running accumulators and do add-new / drop-oldest per tick, so the
    cost is O(1) regardless of how long the lookback is.
    """
    shift = _log2_exact(window)
    buf = deque()
    ma_acc = 0   # sum(px)         -> sma
    num_acc = 0  # sum(px * vol)   -> vwap numerator
    den_acc = 0  # sum(vol)        -> vwap denominator

    for px, vol in ticks:
        if px < 0 or vol < 0:
            raise ValueError("px and vol are unsigned in the rtl, keep them >= 0")

        # add the new tick
        ma_acc += px
        num_acc += px * vol
        den_acc += vol
        buf.append((px, vol))

        # drop the one rolling off the back of the window
        if len(buf) > window:
            opx, ovol = buf.popleft()
            ma_acc -= opx
            num_acc -= opx * ovol
            den_acc -= ovol

        if len(buf) == window:
            sma = ma_acc >> shift                       # pow2 window, so just a shift
            vwap = (num_acc // den_acc) if den_acc > 0 else sma  # floor div, matches hw
            yield (True, sma, vwap)
        else:
            yield (False, 0, 0)


def to_q(price_float):
    """human price -> Q16.16. handy in tests and demos."""
    return int(round(price_float * (1 << Q)))


def from_q(px_fixed):
    """Q16.16 -> float, for printing only."""
    return px_fixed / float(1 << Q)
