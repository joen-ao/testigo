"""Amounts are integer cents (global scenario, 04); shown as "USD 1,240.00"."""


def usd(cents):
    """124000 -> "USD 1,240.00"."""
    cents = int(cents)
    sign = "-" if cents < 0 else ""
    return "%sUSD %s.%02d" % (sign, format(abs(cents) // 100, ","), abs(cents) % 100)
