# Security Policy

This core sits in a trading path, so a wrong number is not just a bug, it can
cost money. I take two classes of issue seriously.

## 1. Correctness of the math

A silent miscalculation is the worst failure mode here, worse than a crash,
because nothing tells you it happened. The kinds of things I treat as security
issues, not just bugs:

- An input that makes `sma_out` or `vwap_out` disagree with `sim/reference.py`.
- Accumulator overflow or wraparound that produces a plausible-looking but wrong
  average (the `ACC_W` sizing, especially at large `WINDOW`).
- A handshake or fifo bug that drops or duplicates ticks, since that quietly
  corrupts every reading after it.

If you can make the hardware and the golden model disagree, that is the report I
most want to see.

## 2. Ordinary software issues

Standard stuff in the tooling and host helpers: out-of-bounds packing, integer
issues in `host/fixed.py`, dependency problems.

## Reporting

- **Preferred:** open a private report through the repository's **Security
  advisories** tab ("Report a vulnerability").
- If that is not available, open a normal issue **without a working exploit
  tape** and ask me to open a private channel.

Please give a reasonable window before public disclosure. This is a one-person
project so timelines are best-effort, but correctness issues get triaged first.

## Supported versions

Alpha (`0.x`). Only the latest `main` is supported, there are no backported
fixes yet.
