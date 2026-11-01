"""The receipt of a real run: build it, sign it, write it with its evidence.

The loop calls `signing_seed` once and `sign_order` after an approved
order. F8 plugs in by passing what it read after the click: the executed
crop bytes, the text read from them, and its verify.result.

A bundle is the run folder itself (one receipt per run):
  receipt.json
  approved_amount.png    approved_address.png
  executed_amount.png    executed_address.png   (when captured)

`testigo verify <run>/receipt.json` finds the PNGs next to the receipt.
"""

from pathlib import Path

from common import config
from common.money import usd
from . import keys
from .receipt import CROP_NAMES, build, dumps, sha_crop


def signing_seed(key=None):
    """(seed, None) or (None, why). `key` is a seed (bytes), a key-file path,
    or None for SIGNING_KEY_PATH. A missing key is not created here: the owner
    makes it on purpose with `testigo keygen`."""
    if isinstance(key, (bytes, bytearray)):
        return bytes(key), None
    path = Path(key) if key else config.settings().signing_key_path
    if not path.is_file():
        return None, "no signing key at %s (create it with `testigo keygen`)" % _show(path)
    try:
        seed = keys.load_seed(path)
        keys.public_from_seed(seed)
        return seed, None
    except (OSError, ValueError) as e:
        return None, "unreadable signing key at %s: %s" % (_show(path), e)


def crops_of(capture):
    """The evidence crops a capture has, as bytes ({} or a subset of
    CROP_NAMES when some are missing), or None if it has none."""
    crops = getattr(capture, "crops", None) or {}
    got = {n: crops[n] for n in CROP_NAMES if crops.get(n)}
    return got or None


def sign_order(policy, approval_event, approval_info, approved_crops, seed,
                 executed_crops=None, executed_read=None, verify_result=None,
                 run_dir=None, agent="agent", status=None, blocked_at=None,
                 approved_screen=b"", executed_screen=b""):
    """Build and sign the receipt of an approved order: confirmed, or blocked
    before confirming (`status="blocked"`, `blocked_at="review"`, F8-D2).

    approval_event   the approval.requested event (amount and address read
                     from the pixels, crop hashes)
    approval_info    what the approver returned (method, voice_transcript, ...)
    approved_crops   {'amount': bytes, 'address': bytes} from the checked capture
    executed_crops   the same after the click (possibly only some of them), or
                     None if not captured (F8)
    executed_read    {'amount': text, 'address': text} read after the click, or None
    verify_result    the verify.result event (not used for the executed hashes:
                     the receipt records only hashes of crops it writes)
    run_dir          where to write receipt.json and the PNGs; None writes nothing

    The executed side records exactly the crops written next to the receipt;
    with none, executed is null (not captured) and step 4 says so.

    approved_screen / executed_screen  the whole screenshots (spec 08 H2): their
                     sha256 and the configured model ids are signed under
                     `evidence`, and the PNGs are written next to the receipt

    Returns (receipt, path or None).
    """
    executed_crops = {n: b for n, b in (executed_crops or {}).items()
                      if n in CROP_NAMES and b} or None
    receipt = build(
        policy,
        action_text="confirm order {} -> ship to {}".format(
            usd(approval_event["amount_cents"]), approval_event["address"]),
        amount_cents=approval_event["amount_cents"],
        address_text=approval_event["address"],
        approved_crops=approved_crops,
        executed_crops=executed_crops,
        approval={"method": approval_info.get("method", ""),
                  "voice_transcript": approval_info.get("voice_transcript", ""),
                  "voice_match": approval_info.get("voice_match")},
        approved_read={"amount": usd(approval_event["amount_cents"]),
                       "address": approval_event["address"]},
        executed_read=executed_read,
        signed_by="%s:%s" % (approval_info.get("method") or "approval", policy.owner),
        agent=agent,
        seed=seed,
        evidence=evidence_of(approved_screen, None if status else executed_screen),
        **({"status": status, "blocked_at": blocked_at} if status else {}),
    )
    path = write(receipt, approved_crops, executed_crops, run_dir) if run_dir else None
    if run_dir:
        write_screens(run_dir, approved_screen, None if status else executed_screen)
    return receipt, path


SCREEN_FILES = {"approved": "approved_screen.png", "executed": "executed_screen.png"}


def evidence_of(approved_screen, executed_screen):
    """Spec 08 H2: what the receipt signs besides the crops: the sha256 of each
    whole screenshot (None when not captured) and the model ids configured for
    this run. None when there is no screenshot at all (test doubles)."""
    if not approved_screen and not executed_screen:
        return None
    s = config.settings()
    return {
        "screens": {"approved": sha_crop(approved_screen) if approved_screen else None,
                    "executed": sha_crop(executed_screen) if executed_screen else None},
        "models": {"agent": s.model_wonder, "reader": s.model_spark,
                   "segmenter": s.model_sam, "voice": s.model_voice},
    }


def write_screens(run_dir, approved_screen, executed_screen):
    out = Path(run_dir)
    for side, data in (("approved", approved_screen), ("executed", executed_screen)):
        if data:
            (out / SCREEN_FILES[side]).write_bytes(data)


def write(receipt, approved_crops, executed_crops, run_dir):
    out = Path(run_dir)
    out.mkdir(parents=True, exist_ok=True)
    for n in CROP_NAMES:
        (out / ("approved_%s.png" % n)).write_bytes(approved_crops[n])
        if executed_crops and executed_crops.get(n):
            (out / ("executed_%s.png" % n)).write_bytes(executed_crops[n])
    path = out / "receipt.json"
    path.write_text(dumps(receipt) + "\n", encoding="utf-8")
    return path


def runs_relative(path):
    """The path relative to RUNS_DIR (for receipt.signed.path), or None if outside."""
    try:
        return Path(path).resolve().relative_to(config.settings().runs_dir.resolve()).as_posix()
    except ValueError:
        return None


def _show(path):
    try:
        return Path(path).resolve().relative_to(config.ROOT).as_posix()
    except ValueError:
        return str(path)
