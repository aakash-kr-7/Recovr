"""₹ formatting and cost-calculation helpers, kept in one place so the
evaluation report and the API responses format money identically."""


def paise_to_inr(paise: int) -> float:
    """Razorpay amounts are always in paise (1/100 INR)."""
    return paise / 100.0


def format_inr(amount: float) -> str:
    """Formats with Indian-style comma grouping (lakh/crore), e.g.
    1234567.5 -> '₹12,34,567.50'."""
    is_negative = amount < 0
    amount = abs(amount)
    whole, _, frac = f"{amount:.2f}".partition(".")

    if len(whole) <= 3:
        grouped = whole
    else:
        last_three = whole[-3:]
        rest = whole[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        grouped = ",".join(parts) + "," + last_three

    sign = "-" if is_negative else ""
    return f"{sign}\u20b9{grouped}.{frac}"
