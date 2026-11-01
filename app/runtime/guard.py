"""TESTIGO+ for any agent (spec 07 M9): one call before a sensitive click.

    from app.runtime.guard import check_screen
    verdict = check_screen(png_bytes, page_text)

`png_bytes` is the screenshot the click would act on, taken at the click.
`page_text` is the text in the page code, rendered or not (for a browser,
document.body.textContent; one line per text node is best). The verdict is the
same decision engine the demo uses, with the real pixel channel (Spark + SAM
3.1), against the signed policy:

  ok                 the screen follows the rules; ask the person to approve
                     `approve` (the total and the address as read from the
                     pixels, and the sha256 of each crop) before clicking
  divergence         page code and pixels disagree (hidden or painted text)
  policy_violation   the screen shows an order the rules do not allow
  cannot_verify      the total or the address could not be read with confidence

Anything but ok means: do not click. The approval itself stays with the host
agent; this module never clicks and never approves.
"""

from app.common import config
from app.core.decision import events as ev
from app.adapters.meta.channels import Capture, SamSparkChannel
from app.core.decision.engine import Interceptor
from app.core.policy.model import load as load_policy


def check_screen(png, page_text, policy_path=None, channel=None):
    """The verdict for a confirming click on this screen, as a plain dict."""
    if not isinstance(png, (bytes, bytearray)) or not png:
        raise ValueError("a PNG screenshot is required")
    policy = load_policy(policy_path or config.policy_path())
    if channel is None:
        from app.adapters.meta.client import MetaClient
        channel = SamSparkChannel(MetaClient())
    lines = [x for x in str(page_text or "").splitlines() if x.strip()]
    capture = Capture(1, lines, [], {}, screenshot=bytes(png))
    decision = Interceptor(policy, channel).check({"kind": "confirm"}, capture)
    c = decision.check_event
    out = {
        "status": c["status"],
        "click_allowed": False,            # an order confirmation always needs the person
        "needs_approval": bool(decision.needs_approval),
        "reason": c.get("reason") or decision.reason or "",
        "code_only_text": c.get("code_only_text") or [],
        "pixels_only_text": c.get("pixels_only_text") or [],
        "latency_ms": c.get("latency_ms"),
        "policy_sha256": policy.sha256(),
    }
    if decision.needs_approval and decision.approval_event:
        a = decision.approval_event
        out["approve"] = {"amount_cents": a["amount_cents"], "address": a["address"],
                          "crops_sha256": a["crops"]}
    elif c["status"] == ev.OK and not decision.blocked:
        out["click_allowed"] = True        # a check that needs nobody (not a confirm)
    return out


def policy_summary(policy_path=None):
    """The signed rules in force, without key material."""
    path = policy_path or config.policy_path()
    p = load_policy(path)
    return {"owner": p.owner, "ship_only_to": p.deliver_only,
            "max_per_order_cents": p.max_per_order_cents, "ask_before": p.ask_before,
            "sha256": p.sha256(), "hash_ok": p.hash_matches_stored(), "signed": bool(p.signature)}
