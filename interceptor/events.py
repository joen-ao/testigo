"""Events the interceptor emits to the interface.

One JSON object per event. These constructors fix the contract from the spec;
if a field changes, it changes here first. The interface (WebSocket/SSE) and
WitnessBench both read these shapes.

Event types:
  agent.step          the agent proposed or completed a step
  frame.captured      a screenshot was taken
  check.result        the pre-action verdict (ok|divergence|policy_violation|cannot_verify)
  approval.requested  a payment that passed checks now needs the person
  approval.granted    the person approved (voice + passkey)
  verify.result       the after-the-click comparison (match|mismatch)
  receipt.signed      the signed receipt was written

check.result.status is one of: ok, divergence, policy_violation, cannot_verify.
When status is ok and the action is a payment, the engine follows it with an
approval.requested; a non-payment ok action is simply allowed.
"""

import time


# Verdict constants (check.result.status)
OK = "ok"
DIVERGENCE = "divergence"
POLICY_VIOLATION = "policy_violation"
CANNOT_VERIFY = "cannot_verify"

# verify.result.status
MATCH = "match"
MISMATCH = "mismatch"


def _ts(ts=None):
    # RFC3339 with the demo's fixed -05:00 (Bogotá) offset.
    if ts:
        return ts
    return time.strftime("%Y-%m-%dT%H:%M:%S-05:00", time.localtime())


def agent_step(frame, label, detail="", ts=None):
    return {"type": "agent.step", "frame": frame, "ts": _ts(ts),
            "label": label, "detail": detail}


def frame_captured(frame, sha, ts=None):
    return {"type": "frame.captured", "frame": frame, "ts": _ts(ts), "sha256": sha}


def check_result(frame, status, regions, code_only_text, pixels_only_text,
                 latency_ms, reason="", ts=None):
    return {
        "type": "check.result", "frame": frame, "ts": _ts(ts),
        "status": status,
        "regions": regions,
        "code_only_text": code_only_text,
        "pixels_only_text": pixels_only_text,
        "latency_ms": latency_ms,
        "reason": reason,
    }


def approval_requested(frame, amount_cop, recipient_text,
                       crop_amount_sha, crop_recipient_sha, ts=None):
    return {
        "type": "approval.requested", "frame": frame, "ts": _ts(ts),
        "amount_cop": amount_cop,
        "recipient": recipient_text,
        "crops": {"amount": crop_amount_sha, "recipient": crop_recipient_sha},
    }


def approval_granted(method, voice_transcript, voice_match, ts=None):
    return {
        "type": "approval.granted", "ts": _ts(ts),
        "method": method,
        "voice_transcript": voice_transcript,
        "voice_match": voice_match,
    }


def verify_result(frame, status, approved, executed, ts=None):
    return {
        "type": "verify.result", "frame": frame, "ts": _ts(ts),
        "status": status,
        "approved": approved,   # {"amount": sha, "recipient": sha}
        "executed": executed,   # {"amount": sha, "recipient": sha}
    }


def receipt_signed(receipt_id, signature, ts=None):
    return {"type": "receipt.signed", "ts": _ts(ts),
            "id": receipt_id, "signature": signature}


def region(label, box, text, confidence):
    """One SAM region as it appears in check.result.regions."""
    return {"label": label, "box": list(box), "text": text,
            "confidence": round(float(confidence), 2)}
