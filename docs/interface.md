# Interface

How the host (the python strategy) and the card talk to each other. Two halves:
a streaming tick path going in, and a small register block for status and
control.

## Tick stream in

Ticks arrive over an AXI4-Stream-ish ready/valid handshake. The host packs each
tick with `host/fixed.py` and DMAs it into `tick_sync_fifo`, which feeds the MAC
engine.

| field      | width | format        | notes                               |
|------------|-------|---------------|-------------------------------------|
| `px_in`    | 32    | Q16.16        | last trade price, unsigned          |
| `tick_vol` | 24    | unsigned int  | size on that print, 0 is allowed    |

Handshake rules, the normal stream ones:

- a tick transfers on a rising clock edge when `tick_vld` and `tick_rdy` are both high
- `tick_rdy` is just the fifo's not-full. when the fifo fills, ready drops and
  the producer waits. that is the backpressure path, we never drop a tick on a
  full ring.
- the host packs a tick as `[px 32b][vol 24b]`, little-endian, 7 bytes. See
  `pack_tick` in `host/fixed.py`.

## Result out

| field      | width | format        | notes                               |
|------------|-------|---------------|-------------------------------------|
| `ma_vld`   | 1     | pulse         | high for one cycle when a reading is fresh |
| `sma_out`  | 32    | Q16.16        | simple moving average over WINDOW   |
| `vwap_out` | 32    | Q16.16        | volume weighted average over WINDOW |

`ma_vld` stays low until the window is full (the first `WINDOW-1` ticks are
warmup). After that it pulses once per accepted tick.

If every tick in the current window had zero volume, `vwap_out` falls back to
`sma_out` rather than dividing by zero.

## Control / status registers

Planned memory-mapped block. Not all of this is wired yet, flagged where it is
aspirational.

| offset | name        | access | meaning                                  |
|--------|-------------|--------|------------------------------------------|
| 0x00   | `CTRL`      | rw     | bit0 = enable, bit1 = soft reset         |
| 0x04   | `STATUS`    | r      | bit0 = warm, bit1 = fifo full            |
| 0x08   | `WINDOW`    | r      | compiled-in window size (ticks)          |
| 0x0C   | `FIFO_LVL`  | r      | current fifo occupancy                   |
| 0x10   | `SMA`       | r      | latest sma, Q16.16                       |
| 0x14   | `VWAP`      | r      | latest vwap, Q16.16                      |

> TODO: the register block itself is not in this repo yet. The plan is a thin
> AXI4-Lite shim over these fields. For now you read results straight off the
> stream in sim.

## Latency

A reading lands one clock after the tick that produced it is accepted. There is
no multi-cycle pipeline yet, see the architecture notes for where that changes
when the multiplier gets registered.
