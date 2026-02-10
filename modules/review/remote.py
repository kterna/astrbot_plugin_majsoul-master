def decode_account_id2(value: int) -> int:
    return int(((value - 1358437 ^ 86216345) - 1117113) / 7)


def decode_log_id(log_id: str) -> str:
    zero = ord("0")
    alpha = ord("a")
    ret = ""

    for i, ch in enumerate(log_id):
        code = ord(ch)
        if zero <= code < zero + 10:
            o = code - zero
        elif alpha <= code < alpha + 26:
            o = code - alpha + 10
        else:
            ret += ch
            continue

        o = (o + 55 - i) % 36
        if o < 10:
            ret += chr(o + zero)
        else:
            ret += chr(o + alpha - 10)

    return ret


def encode_account_id2(account_id: int) -> int:
    p = 6139246 ^ account_id
    h_mask = 67108863
    s = p & ~h_mask
    z = p & h_mask
    for _ in range(5):
        z = ((511 & z) << 17) | (z >> 9)
    return z + s + 10000000
