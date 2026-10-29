"""Build and sign a receipt, in the spec's shape.

A receipt records one action: the policy it ran under, the approved evidence
crops, the executed crops, how it was approved, and an Ed25519 signature over
everything else. The crop hashes are the same sha256 the interceptor used, so
the number on the receipt is the number that was checked.

The signature covers the canonical content (every field except `signature`),
which includes `pubkey`. Trust comes from pinning that public key out of band;
`testigo verify --pubkey <hex>` does exactly that.
"""

import hashlib
import json

from interceptor.channels import sha_crop
from . import keys


def canonical(receipt):
    """Stable bytes signed over: the receipt without its signature."""
    body = {k: v for k, v in receipt.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def hash_crops(crop_bytes):
    """{'amount': b'...', 'recipient': b'...'} -> {'amount': sha, 'recipient': sha}."""
    return {name: sha_crop(data) for name, data in crop_bytes.items()}


def build(policy, action_text, amount_cop, recipient_text,
          approved_crops, executed_crops, approval, seed,
          receipt_id="rcpt_2041_7f3a", time="2026-10-28T09:16:05-05:00",
          agent="wonder@marta-shop"):
    """Assemble and sign a receipt.

    approved_crops / executed_crops: {'amount': bytes, 'recipient': bytes}.
    """
    receipt = {
        "id": receipt_id,
        "time": time,
        "agent": agent,
        "action": action_text,
        "amount_cop": amount_cop,
        "recipient": recipient_text,
        "policy_sha256": policy.sha256(),
        "approved": hash_crops(approved_crops),
        "executed": hash_crops(executed_crops),
        "approval": approval,
        "signed_by": "passkey:%s" % policy.owner,
        "pubkey": keys.public_from_seed(seed).hex(),
    }
    sig = keys.sign(seed, canonical(receipt))
    receipt["signature"] = "ed25519:" + sig.hex()
    return receipt


def parse_signature(receipt):
    raw = receipt.get("signature", "")
    if not raw.startswith("ed25519:"):
        return None
    try:
        return bytes.fromhex(raw.split(":", 1)[1])
    except ValueError:
        return None


def verify_signature(receipt, pinned_pubkey=None):
    sig = parse_signature(receipt)
    if sig is None:
        return False
    pub = pinned_pubkey
    if pub is None:
        try:
            pub = bytes.fromhex(receipt.get("pubkey", ""))
        except ValueError:
            return False
    return keys.verify(pub, canonical(receipt), sig)


def dumps(receipt):
    return json.dumps(receipt, indent=2, ensure_ascii=False)


def short(h):
    return "%s…%s" % (h[:6], h[-4:])
