# Contributing

Thanks for looking. This is a solo project so far, and it gets better the more
eyes land on the fixed-point math, so anything from a typo to a new core is
welcome.

## Where help goes furthest

- **RTL / FPGA:** registering the multiplier, the Newton-Raphson reciprocal to
  kill the synth-time divide, a real async fifo for the PCIe clock crossing.
- **Verification:** more vector cases, especially nasty ones. Gap-ups, zero-vol
  runs, accumulator-overflow edges. If you can make the testbench go red with a
  realistic tape, that is a great PR.
- **Host side:** the XDMA driver glue and the AXI4-Lite register block are still
  vapor. That is the gap between "passes sim" and "actually runs on a card".
- **Real data:** I am testing on a synthetic random walk. If you have a clean
  recorded tick session for a liquid name, wiring it into `gen_vectors.py` would
  catch things the synthetic tape never will.

## Getting set up

```bash
git clone https://github.com/tylrcc/tapeline
cd tapeline
make test      # python golden-model tests, no fpga tools needed
make sim       # full rtl sim, needs iverilog
```

## A few rules

- The math lives in **two** places: `sim/reference.py` and `rtl/mac_engine.v`.
  If you change one you change the other, and the testbench has to still pass.
  The python is the source of truth.
- Sim has to pass before I merge. CI runs the model tests and the iverilog
  testbench on every PR.
- Keep PRs small and say *why*, not just *what*.
- Do not commit generated stuff (`sim/vectors.txt`, `build/`). It is git-ignored
  for a reason, `make vectors` regenerates it.

By sending a PR you agree your code goes out under MIT and any RTL/docs under
CERN-OHL-P, same as the rest of the repo.
