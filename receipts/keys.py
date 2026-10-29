"""Ed25519 keys and signing, with the `cryptography` library (RFC 8032).

A private key is a 32-byte seed; a public key is 32 bytes; a signature is 64.
The signing key lives outside the repo, at SIGNING_KEY_PATH (.secrets/).
"""

import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def backend():
    return "cryptography"


def generate_seed():
    return os.urandom(32)


def public_from_seed(seed):
    sk = Ed25519PrivateKey.from_private_bytes(seed)
    return sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def sign(seed, msg):
    return Ed25519PrivateKey.from_private_bytes(seed).sign(msg)


def verify(pub, msg, sig):
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(sig, msg)
        return True
    except (InvalidSignature, ValueError):
        return False


# -- key file (seed in hex), kept in .secrets/ with owner-only permissions ---

def save_seed(path, seed):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(seed.hex() + "\n", encoding="utf-8")
    p.chmod(0o600)


def load_seed(path):
    return bytes.fromhex(Path(path).read_text(encoding="utf-8").strip())


def load_or_create_seed(path):
    p = Path(path)
    if p.exists():
        return load_seed(p)
    seed = generate_seed()
    save_seed(p, seed)
    return seed
