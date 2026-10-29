"""`testigo` — check a receipt without trusting us.

  testigo verify runs/evidence/run/receipt.json
  testigo verify receipt.json --evidence <folder>
  testigo verify receipt.json --pubkey <hex>        # pin the signer's key
  testigo keygen                                    # create/show the key at SIGNING_KEY_PATH

The verify output mirrors View 7: a four-step checklist, then one line.
Exit code 0 only when every check passes.
"""

import argparse
import sys
from pathlib import Path

from common import config

from . import keys
from .verify import verify_receipt

CHECK = "✓"   # ✓
CROSS = "✗"   # ✗


def cmd_verify(args):
    evidence = args.evidence
    if evidence is None:
        guess = Path(args.receipt).resolve().parent
        if (guess / "approved_amount.png").exists():
            evidence = str(guess)
    pinned = bytes.fromhex(args.pubkey) if args.pubkey else None

    res = verify_receipt(args.receipt, evidence_dir=evidence,
                         policy_path=args.policy, pinned_pubkey=pinned)
    print("Checking %s …" % res.receipt_id)
    for c in res.checks:
        mark = CHECK if c.ok else CROSS
        print("[%d/4] %s %s %s" % (c.n, mark, c.name, ("· " + c.detail) if c.detail else ""))
    print()
    print(res.summary())
    return 0 if res.ok else 1


def cmd_keygen(args):
    path = args.path or config.settings().signing_key_path
    seed = keys.load_or_create_seed(path)
    print("key file :", path)
    print("pubkey   :", keys.public_from_seed(seed).hex())
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="testigo", description="TESTIGO+ receipt tools")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="verify a signed receipt")
    v.add_argument("receipt")
    v.add_argument("--evidence", help="folder with the crop PNGs (auto-detected next to the receipt)")
    v.add_argument("--policy", default=str(config.POLICY_PATH))
    v.add_argument("--pubkey", help="pin the signer's public key (hex)")
    v.set_defaults(func=cmd_verify)

    k = sub.add_parser("keygen", help="create or show the signing key")
    k.add_argument("path", nargs="?", default=None, help="default: SIGNING_KEY_PATH")
    k.set_defaults(func=cmd_keygen)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
