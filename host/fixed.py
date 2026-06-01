"""Q16.16 fixed-point helpers, shared between the trading repo and the accelerator.

the card speaks Q16.16 for price and plain unsigned ints for volume. keep the
conversions in one place so the strategy code and the hardware never disagree on
where the binary point sits. import this from the python side:

    from hw_accelerator.host.fixed import price_to_q, q_to_price, pack_tick
"""

import struct

Q = 16
SCALE = 1 << Q
PX_MASK = (1 << 32) - 1
VOL_MASK = (1 << 24) - 1


def price_to_q(price):
    """float price -> 32-bit Q16.16. raises if it will not fit, better loud than wrapped."""
    fixed = int(round(price * SCALE))
    if fixed < 0 or fixed > PX_MASK:
        raise ValueError("price %r does not fit in unsigned Q16.16" % price)
    return fixed


def q_to_price(fixed):
    """32-bit Q16.16 -> float. display only, do not feed back into the math."""
    return (fixed & PX_MASK) / float(SCALE)


def pack_tick(price, volume):
    """pack one (price, volume) tick into the 56-bit dma payload the fifo expects,
    returned as 8 bytes little-endian. layout: [px 32b][vol 24b], lsb first.

    TODO: this has to match the descriptor format in the xdma driver once that is
          written. right now it is just the obvious packing and nothing reads it
          on the host besides the loopback test.
    """
    px = price_to_q(price)
    vol = int(volume)
    if vol < 0 or vol > VOL_MASK:
        raise ValueError("volume %r does not fit in 24 bits" % volume)
    payload = px | (vol << 32)
    return struct.pack("<Q", payload)[:7]   # 56 bits -> 7 bytes


def unpack_tick(raw):
    """inverse of pack_tick, mostly for tests."""
    payload = struct.unpack("<Q", raw.ljust(8, b"\x00"))[0]
    px = payload & PX_MASK
    vol = (payload >> 32) & VOL_MASK
    return px, vol
