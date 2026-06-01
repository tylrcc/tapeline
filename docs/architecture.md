# Architecture

The short version: keep running sums, slide them one tick at a time, never loop
over the window. That single decision is what makes this cheap enough to sit in
the hot path.

## Datapath

```
            +-------------------+        +-----------------------+
 host  ---> | tick_sync_fifo    | -----> |     mac_engine        | ---> sma_out
 (dma)      | backpressure      |  tick  |  rolling accumulators |      vwap_out
            +-------------------+        +-----------------------+      ma_vld
```

Inside `mac_engine`:

- a ring buffer (`px_buf`, `vol_buf`) holds the last `WINDOW` ticks
- three accumulators carry the running state:
  - `ma_acc`  = sum of price            -> simple moving average
  - `num_acc` = sum of price * volume   -> vwap numerator
  - `den_acc` = sum of volume           -> vwap denominator
- each accepted tick adds the new sample and, once the window is full, subtracts
  the one rolling off the back. The slot at `wr_ptr` is both the next write
  target and the oldest live sample, so the drop and the overwrite use the same
  index.

## Why the sums and not a re-sum

A naive moving average re-adds `WINDOW` samples every tick, which is `O(WINDOW)`
and scales badly when you want a long lookback at line rate. The sliding
accumulator is `O(1)` per tick regardless of window length. The cost is that you
carry a little more state and you have to size the accumulator so it never
wraps.

## Fixed point

Price is Q16.16. Volume is a plain unsigned integer.

- SMA is `ma_acc >> log2(WINDOW)`. Because `WINDOW` is forced to a power of two,
  the divide is a shift and costs nothing.
- VWAP is `num_acc / den_acc`. The denominator is data-dependent, so that one is
  a real divide. It is currently a synth-time divider and it is the most
  expensive thing in the design. The plan is to replace it with a pipelined
  Newton-Raphson reciprocal so the divide stops gating timing.

## Sizing the accumulator

`num_acc` is the one to watch. Each product is up to `PX_W + VOL_W` = 56 bits,
and summing `WINDOW` of them adds `log2(WINDOW)` more. At the default `WINDOW=64`
that is 62 bits, comfortably inside the 64-bit accumulator. Push `WINDOW` past
256 and you need to widen `ACC_W` or saturate. There is a FIXME on this in the
rtl because it actually bit me once in sim on a synthetic gap-up.

## Timing

Today the 32x24 multiply and the 64-bit accumulator update share one cycle.
That single-cycle path is what caps fmax (roughly 210 MHz on the -2 speed grade
part I am targeting). The fix is to register the products and move the
accumulator update one stage later, trading one cycle of latency for headroom.
That is the next thing I want to do once the divider is sorted.

## Verification

`sim/reference.py` is the golden model and the source of truth. `gen_vectors.py`
runs the model over a synthetic tape and writes the expected outputs.
`tb/mac_engine_tb.v` replays that tape into the rtl and fails loudly on any
mismatch. So the laptop math and the silicon math are checked against each other
on every push, which is the only way I trust fixed-point hardware.
