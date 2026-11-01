"""The TESTIGO+ decision engine.

Nothing the agent proposes reaches the page without passing through `check`.
The rules run in order; the first that fires decides. This is the piece the
whole demo turns on, so it is kept pure (spec 10 P1): `decide` and
`compare_reread` take a Reading (what was read) and return events; they talk
to no browser, model, network or file. `Interceptor` only wires a pixel
channel in front of them.

Rules (spec order):
  1. SAM cannot find amount, address or the confirm button with confidence
        -> cannot_verify, block.
  2. Text in the page code that is not drawn, or drawn text not in the code
        -> divergence, block.
  3. Delivery address or total read from the pixels breaks the policy
        -> policy_violation, block.
  4. Everything agrees and the action confirms the order
        -> needs approval (voice + passkey).
  5. After the click, executed crops differ from the approved crops
        -> mismatch, the receipt is flagged.

"Read from the pixels" everywhere: the address and amount used for the policy
check come from the pixel channel, never from the DOM, so a hidden or swapped
value cannot slip an order through.
"""

import re
import time

from app.core.decision import events as ev
from app.core.decision.regions import REQUIRED_REGIONS, CONFIDENCE_MIN
from app.core.evidence.receipt import sha_crop
from app.core.decision.instruction_filter import filter_instructions


class Decision:
    """Result of a pre-action check."""

    def __init__(self, status, blocked, check_event, approval_event=None,
                 needs_approval=False, reason=""):
        self.status = status
        self.blocked = blocked
        self.needs_approval = needs_approval
        self.reason = reason
        self.check_event = check_event
        self.approval_event = approval_event

    @property
    def allowed_now(self):
        """True only for a non-confirming action that passed every check."""
        return not self.blocked and not self.needs_approval


class Reading:
    """What was read from one screen: plain data, no behaviour (spec 10 P1).

    regions         the pixel channel's labelled regions (text, box, confidence)
    code_lines      every text line in the page code, rendered or not
    rendered_lines  every line painted on screen, as the pixel channel read it
    crops           label -> crop bytes (their sha256 is the evidence)
    frame           which capture this is
    """

    __slots__ = ("frame", "regions", "code_lines", "rendered_lines", "crops")

    def __init__(self, frame, regions, code_lines=(), rendered_lines=(), crops=None):
        self.frame = frame
        self.regions = list(regions or [])
        self.code_lines = list(code_lines)
        self.rendered_lines = list(rendered_lines)
        self.crops = dict(crops or {})


def read_screen(pixel_channel, capture):
    """The adapter side: ask the pixel channel to read a capture and return the
    Reading the pure functions below decide on. The only call out of the core,
    and it goes through whatever channel the caller wired in."""
    regions = pixel_channel.read_regions(capture)
    return Reading(capture.frame, regions, capture.code_lines, capture.rendered_lines, capture.crops)


def decide(policy, action, reading, latency_ms=None, confidence_min=CONFIDENCE_MIN):
    """Rules 1-4 on what was read (spec 10 P1). Pure: no model, browser,
    network or file. `action` is {"kind": "confirm"|"click"|...}."""
    regions, frame = reading.regions, reading.frame
    by_label = {r["label"]: r for r in regions}

    def done(status, blocked, reason="", code_only=(), pixels_only=()):
        return Decision(status, blocked,
                        ev.check_result(frame, status, regions, list(code_only), list(pixels_only),
                                        latency_ms, reason),
                        reason=reason)

    # Rule 1: cannot_verify
    missing, low = confidence_gaps(by_label, confidence_min)
    if missing or low:
        return done(ev.CANNOT_VERIFY, True, _cannot_reason(missing, low, confidence_min))

    # Rule 1b: the amount must read as exactly one amount (app.core.evidence.receipt
    # _amount_cents); an odd separator or a second number is not guessed.
    if _amount_from(by_label["amount"]["text"]) is None:
        return done(ev.CANNOT_VERIFY, True,
                    "the amount on screen is not one readable amount: %r" % by_label["amount"]["text"])

    # Rule 2: divergence (both directions)
    code_only, pixels_only = divergence(reading.code_lines, reading.rendered_lines)
    if code_only or pixels_only:
        reason = "visible text not in page code" if pixels_only else "page code text not visible"
        return done(ev.DIVERGENCE, True, reason, code_only, pixels_only)

    # Rule 3a: an address the policy does not allow is painted on the screen
    # (a decoy next to the real field, review of F4). The pixels decide.
    stray = stray_addresses(policy, reading.rendered_lines)
    if stray:
        return done(ev.POLICY_VIOLATION, True,
                    "an address not in the deliver-only list is on screen: %s" % ", ".join(stray))

    # Rule 3: policy violation (address/amount read from pixels)
    address_text = by_label["address"]["text"]
    amount_cents = _amount_from(by_label["amount"]["text"])
    ok, why = policy.check_order(address_text, amount_cents)
    if not ok:
        return done(ev.POLICY_VIOLATION, True, why)

    # Rule 4: ok. Confirming the order needs approval; anything else is allowed.
    check_ev = ev.check_result(frame, ev.OK, regions, [], [], latency_ms, "")
    if _is_confirm(action):
        approval = ev.approval_requested(
            frame, amount_cents, address_text,
            sha_crop(reading.crops.get("amount", b"")), sha_crop(reading.crops.get("address", b"")))
        return Decision(ev.OK, False, check_ev, approval_event=approval, needs_approval=True)
    return Decision(ev.OK, False, check_ev)


def compare_reread(approved_read, approved_hashes, reading, moment, confidence_min=CONFIDENCE_MIN):
    """F8 on what was read again, before or after the click (spec 10 P1, pure).

    Compared by the values read from the pixels (app.core.evidence.receipt.norm_read:
    the amount's digits, the canonical delivery addresses), because crops of
    unchanged content never hash the same across two real captures. The
    hashes travel along as evidence. Returns (verify.result event, read)."""
    from app.core.evidence.receipt import norm_read
    by = {r["label"]: r for r in reading.regions}
    read = {n: by[n]["text"] for n in ("amount", "address")
            if n in by and by[n].get("confidence", 0) >= confidence_min}
    executed = {n: sha_crop(reading.crops[n]) for n in ("amount", "address") if reading.crops.get(n)}
    if any(norm_read(n, approved_read.get(n)) != norm_read(n, read[n]) for n in read):
        status = ev.MISMATCH           # any field read and different: proven
    elif len(read) < 2:
        status = ev.CANNOT_VERIFY      # what was read agrees, but not everything was
    else:
        status = ev.MATCH
    return ev.verify_result(reading.frame, status, dict(approved_hashes), executed,
                            moment=moment,
                            read={"approved": dict(approved_read), "executed": read}), read


class Interceptor:
    """The core with a pixel channel wired in: each method reads the screen
    through the channel (read_screen) and hands the Reading to a pure function."""

    def __init__(self, policy, pixel_channel, confidence_min=CONFIDENCE_MIN):
        self.policy = policy
        self.pixels = pixel_channel
        self.confidence_min = confidence_min
        self.last_regions = []     # the regions of the last read (the loop compares them at the click)

    # -- pre-action ---------------------------------------------------------

    def check(self, action, capture, latency_ms=None):
        """Decide on a proposed action. `action` is {"kind": "confirm"|"click"|"type", ...}."""
        t0 = time.perf_counter()
        reading = read_screen(self.pixels, capture)
        self.last_regions = reading.regions
        measured = int(round((time.perf_counter() - t0) * 1000))
        return decide(self.policy, action, reading,
                      latency_ms if latency_ms is not None else measured, self.confidence_min)

    # -- after the click ----------------------------------------------------

    def verify(self, approved_crops, executed_capture):
        """Rule 5: compare what executed against what was approved.

        approved_crops: {"amount": sha, "address": sha} from approval time.
        Returns a verify.result event; status is match or mismatch.
        """
        executed = {
            "amount": sha_crop(executed_capture.crops.get("amount", b"")),
            "address": sha_crop(executed_capture.crops.get("address", b"")),
        }
        status = ev.MATCH
        if (executed["amount"] != approved_crops.get("amount") or
                executed["address"] != approved_crops.get("address")):
            status = ev.MISMATCH
        return ev.verify_result(executed_capture.frame, status, dict(approved_crops), executed)

    def reread(self, approved_read, approved_hashes, capture, moment):
        """F8: read amount and address again (through the channel) and compare
        with what was approved (compare_reread)."""
        reading = read_screen(self.pixels, capture)
        self.last_regions = reading.regions
        return compare_reread(approved_read, approved_hashes, reading, moment, self.confidence_min)

    # -- explanation, after an unsupervised run (observe only) ---------------

    def explain(self, capture):
        """Read the pixels once and compare them with the page code, never
        deciding anything: no rule order, no block, no approval. Used by
        `app.runtime.loop.run --no-supervisor --explain` after the run has ended, to show
        what TESTIGO+ would have seen (view 3). Returns a dict with the regions,
        the instruction-like lines on each side and the addresses on screen that
        the policy does not allow."""
        t0 = time.perf_counter()
        reading = read_screen(self.pixels, capture)
        latency = int(round((time.perf_counter() - t0) * 1000))
        code_only, pixels_only = divergence(reading.code_lines, reading.rendered_lines)
        by_label = {r["label"]: r for r in reading.regions}
        policy_reason = ""
        stray = stray_addresses(self.policy, reading.rendered_lines)
        if stray:
            policy_reason = "an address not in the deliver-only list is on screen: %s" % ", ".join(stray)
        elif "address" in by_label and "amount" in by_label:
            amount = _amount_from(by_label["amount"]["text"])
            if amount is None:
                policy_reason = "the amount on screen is not one readable amount"
            else:
                ok, why = self.policy.check_order(by_label["address"]["text"], amount)
                policy_reason = "" if ok else why
        return {"regions": reading.regions, "code_only_text": code_only, "pixels_only_text": pixels_only,
                "policy_reason": policy_reason, "latency_ms": latency}

    def _stray_addresses(self, lines):
        return stray_addresses(self.policy, lines)


# -- the rules' pieces (pure) -------------------------------------------------

def stray_addresses(policy, lines):
    """Addresses painted on screen that the policy does not allow."""
    from app.core.evidence.receipt import ADDRESS_RE, norm_read
    allowed = policy.allowed_addresses()
    seen = []
    for line in lines:
        if not ADDRESS_RE.search(str(line)):
            continue
        for addr in norm_read("address", line).split(","):
            if addr and addr not in allowed and addr not in seen:
                seen.append(addr)
    return seen


def confidence_gaps(by_label, confidence_min=CONFIDENCE_MIN):
    missing = [r for r in REQUIRED_REGIONS if r not in by_label]
    low = [r for r in REQUIRED_REGIONS
           if r in by_label and by_label[r].get("confidence", 0) < confidence_min]
    return missing, low


def divergence(code_lines, rendered_lines):
    """Differences in both directions, kept only where they look like an
    instruction for the agent (F5). Legitimate hidden text does not block."""
    code = _compact_all(code_lines)
    pixels = _compact_all(rendered_lines)
    code_only = [x for x in code_lines if not _covered(x, pixels)]
    pixels_only = [x for x in rendered_lines if not _covered(x, code)]
    return (filter_instructions(_dedupe(code_only)),
            filter_instructions(_dedupe(pixels_only)))


def _compact(s):
    """Letters and digits only, lower case: the DOM splits text into nodes and a
    reader groups it into lines, so a line is "in" the other channel when its
    letters and digits appear there in order, whatever the spacing or case."""
    return re.sub(r"[\W_]+", "", str(s).lower())


def _compact_all(lines):
    return "".join(_compact(x) for x in lines)


def _covered(line, other):
    """Every word of `line` is somewhere in the other channel. A reader may join
    on one line what the DOM keeps apart (the address field's value and the
    name beside it, 31 Oct), so whole lines are not compared; an instruction
    still shows, because its words (the attacker's address, "agent") are not
    in the other channel at all."""
    words = [_compact(w) for w in str(line).split()]
    words = [w for w in words if w]
    return not words or all(w in other for w in words)


def _norm(s):
    return " ".join(str(s).split()).strip().lower()


def _dedupe(xs):
    seen, out = set(), []
    for x in xs:
        k = _norm(x)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _amount_from(text):
    """The amount read from the pixels, in integer cents ("USD 1,240.00" ->
    124000), or None when it is not exactly one readable amount."""
    from app.core.evidence.receipt import norm_read
    cents = norm_read("amount", text or "")
    return int(cents) if cents else None


def _is_confirm(action):
    return action.get("kind") == "confirm"


def _cannot_reason(missing, low, cmin):
    bits = []
    if missing:
        bits.append("not found: " + ", ".join(missing))
    if low:
        bits.append("low confidence: " + ", ".join(low) + " (needs %.2f)" % cmin)
    return "; ".join(bits)
