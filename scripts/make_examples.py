"""Regenerate examples/: two SYNTHETIC receipts for `testigo verify` (decision D7).

  .venv/bin/python -m scripts.make_examples

Writes:
  examples/clean/   every check passes
  examples/a3/      correctly signed, but the address that executed
                    (88 Mill Street) differs from the approved one
                    (120 Harbor Road, Unit 4): verify fails at step 4
  examples/pubkey.txt

The receipts are signed with an Ed25519 key generated in memory and dropped
when the script exits; only its public half is written. They reference the
committed policy (policy/larkspur.policy.yaml), which `testigo verify` trusts by
its hash, so they verify from a fresh clone. The "crop" files are placeholder
bytes, not screenshots. Signatures, ids and times change on every run; the
shape and the verdicts do not.

Product code may not import tests/ (tests/test_boundaries.py), so the
placeholder values live here.
"""

import shutil
from pathlib import Path

from app.common.config import POLICY_PATH, ROOT
from app.common.money import usd
from app.core.policy.model import load as load_policy
from app.core.evidence import keys
from app.core.evidence.bundle import sign_order
from app.core.evidence.receipt import CROP_NAMES

OUT = ROOT / "examples"
AMOUNT = 124000
BUYER = "Larkspur Market · 120 Harbor Road, Unit 4, Riverton"
OTHER = "Dock 9 Storage · 88 Mill Street, Riverton"
TRANSCRIPT = "Twelve hundred forty dollars, ship to Larkspur Market"


def placeholder(name, value):
    """Clearly synthetic crop bytes: not a PNG, just a label."""
    return ("SYNTHETIC PLACEHOLDER (not a screenshot) crop:%s:%s" % (name, value)).encode("utf-8")


def crops(address):
    return {"amount": placeholder("amount", usd(AMOUNT)),
            "address": placeholder("address", address)}


def make(out=OUT, policy_path=POLICY_PATH):
    out = Path(out)
    policy = load_policy(policy_path)
    seed = keys.generate_seed()       # in memory only; never written
    event = {"amount_cents": AMOUNT, "address": BUYER}
    approval = {"method": "passkey", "voice_transcript": TRANSCRIPT, "voice_match": True}
    for scenario, executed_address in (("clean", BUYER), ("a3", OTHER)):
        folder = out / scenario
        if folder.exists():
            shutil.rmtree(folder)
        sign_order(policy, event, approval, crops(BUYER), seed,
                   executed_crops=crops(executed_address),
                   executed_read={"amount": usd(AMOUNT), "address": executed_address},
                   run_dir=folder, agent="wonder@larkspur-market")
    (out / "pubkey.txt").write_text(keys.public_from_seed(seed).hex() + "\n", encoding="utf-8")
    del seed
    return out


def main():
    out = make()
    for scenario in ("clean", "a3"):
        files = ["receipt.json"] + ["%s_%s.png" % (side, n)
                                    for side in ("approved", "executed") for n in CROP_NAMES]
        print("wrote %s/%s/ (%s)" % (out.relative_to(ROOT), scenario, ", ".join(files)))
    print("wrote %s/pubkey.txt (the private key was not saved)" % out.relative_to(ROOT))


if __name__ == "__main__":
    main()
