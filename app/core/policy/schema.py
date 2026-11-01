"""The shape a policy must have before anyone enforces it (spec 10 P2).

The signature proves who wrote the rules; this proves they are well formed.
`validate_policy(data)` returns the list of problems ([] when it is fine).
A policy with any problem is never used: `model.load` raises PolicyInvalid.
"""

TOP_LEVEL = {"version", "owner", "source", "transcript", "rules", "signed_by", "sha256", "signature"}
RULES = {"deliver_only", "max_per_order_cents", "ask_before"}
ASK_BEFORE = {"", "new_address"}
MAX_CENTS = 100_000_000            # USD 1,000,000: anything above is not a typo we enforce


class PolicyInvalid(ValueError):
    """The policy is not well formed. Nothing is enforced with it."""


def validate_policy(data):
    from app.common.address import ADDRESS_RE
    if not isinstance(data, dict):
        return ["the policy is not a mapping"]
    probs = []
    unknown = sorted(set(data) - TOP_LEVEL)
    if unknown:
        probs.append("unknown field(s): %s" % ", ".join(unknown))
    if data.get("version") != 1:
        probs.append("version must be 1")
    for k in ("owner", "source", "transcript"):
        if not isinstance(data.get(k, ""), str):
            probs.append("%s must be text" % k)
    if not str(data.get("owner") or "").strip():
        probs.append("owner is missing")
    rules = data.get("rules")
    if not isinstance(rules, list) or not rules:
        return probs + ["rules must be a non-empty list"]
    seen = {}
    for i, item in enumerate(rules):
        if not isinstance(item, dict) or len(item) != 1:
            probs.append("rule %d must be one key: value" % (i + 1))
            continue
        (key, value), = item.items()
        if key not in RULES:
            probs.append("unknown rule %r" % key)
        elif key in seen:
            probs.append("rule %r given twice" % key)
        seen[key] = value
    places = seen.get("deliver_only")
    if not isinstance(places, list) or not places:
        probs.append("deliver_only must name at least one place")
    else:
        for i, p in enumerate(places):
            if not isinstance(p, dict) or set(p) != {"name", "address"}:
                probs.append("deliver_only %d must have exactly name and address" % (i + 1))
                continue
            if not isinstance(p["name"], str) or not p["name"].strip():
                probs.append("deliver_only %d has no name" % (i + 1))
            if not isinstance(p["address"], str) or not ADDRESS_RE.search(p["address"]):
                probs.append("deliver_only %d has no readable street address" % (i + 1))
    cents = seen.get("max_per_order_cents")
    if isinstance(cents, bool) or not isinstance(cents, int) or not 1 <= cents <= MAX_CENTS:
        probs.append("max_per_order_cents must be a whole number from 1 to %d" % MAX_CENTS)
    if seen.get("ask_before", "") not in ASK_BEFORE:
        probs.append("ask_before must be empty or new_address")
    return probs


def check(data):
    """Raise PolicyInvalid with every problem, or return the data."""
    probs = validate_policy(data)
    if probs:
        raise PolicyInvalid("; ".join(probs))
    return data
