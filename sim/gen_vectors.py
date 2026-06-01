"""generate test vectors for the verilog testbench.

writes sim/vectors.txt, one tick per line:

    px  vol  expected_valid  expected_sma  expected_vwap

all decimal, all unsigned. the testbench reads this with $fscanf and checks the
dut against the expected columns. the expected values come straight out of
reference.py so the laptop math and the silicon math are forced to agree.

the vectors are git-ignored on purpose. `make vectors` regenerates them, so
there is nothing stale to drift out of sync with the model.
"""

import os
import random

from reference import rolling_mac, to_q

WINDOW = 64          # keep in sync with the tb / rtl default
N_TICKS = 4000
SEED = 0xC0FFEE      # deterministic, so CI is reproducible


def synth_ticks(n, seed):
    """a cheap random walk in price with bursty volume. not a real tape, but it
    exercises the rolling window, the vwap weighting, and a few zero-vol ticks.

    TODO: feed this real ES/NQ tick data once i have a clean recorded session.
          a synthetic walk never hits the nasty gap-ups that stress the accumulators.
    """
    rng = random.Random(seed)
    px = 100.0
    out = []
    for _ in range(n):
        px += rng.gauss(0.0, 0.05)
        px = max(1.0, px)
        # mostly small lots, occasional block, and the odd zero-vol print
        if rng.random() < 0.03:
            vol = 0
        elif rng.random() < 0.10:
            vol = rng.randint(500, 5000)
        else:
            vol = rng.randint(1, 50)
        out.append((to_q(px), vol))
    return out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(here, "vectors.txt")

    ticks = synth_ticks(N_TICKS, SEED)
    results = rolling_mac(ticks, WINDOW)

    n_valid = 0
    with open(out_path, "w") as f:
        for (px, vol), (valid, sma, vwap) in zip(ticks, results):
            f.write("%d %d %d %d %d\n" % (px, vol, 1 if valid else 0, sma, vwap))
            n_valid += 1 if valid else 0

    print("wrote %d vectors (%d valid) -> %s" % (len(ticks), n_valid, out_path))


if __name__ == "__main__":
    main()
