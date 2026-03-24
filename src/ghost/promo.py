import random
import time

_HEX_CHARS = "0123456789abcdef"
_RNG = random.SystemRandom()


def generate_promo_code(salt: int = 3, now: int | None = None) -> str:
    expiry_timestamp = (now if now is not None else int(time.time())) + 3600
    hex_time = f"{expiry_timestamp:08x}"

    slots = (0, 5, 10, 15, 20, 25, 30, 35)
    addr = [_RNG.choice(_HEX_CHARS) for _ in range(40)]

    for i, slot_index in enumerate(slots):
        addr[slot_index] = hex_time[i]

    time_sum = sum(int(c, 16) for c in hex_time)
    seal_value = (time_sum + salt) % 16
    addr[39] = f"{seal_value:x}"

    return "0x" + "".join(addr)
