"""
Cryptographic Utilities for FLOP Network.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pure Python Substrate SS58 (Format 42) Address Derivation and Ed25519 Signing.
No C-compiler, MSVC, or external binary dependencies required.
"""

from __future__ import annotations

import hashlib
import os
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
SS58_PREFIX = b"SS58PRE"
DEFAULT_SS58_FORMAT = 42  # FLOP Devnet & Testnet Substrate default format 42


def b58encode(raw_bytes: bytes) -> str:
    """Encode bytes using Bitcoin Base58 alphabet."""
    num = int.from_bytes(raw_bytes, "big")
    chars = []
    while num > 0:
        num, rem = divmod(num, 58)
        chars.append(ALPHABET[rem])
    encoded = "".join(reversed(chars)) if chars else ""
    pad = 0
    for byte in raw_bytes:
        if byte == 0:
            pad += 1
        else:
            break
    return (ALPHABET[0] * pad) + encoded


def ss58_encode(pubkey_bytes: bytes, ss58_format: int = DEFAULT_SS58_FORMAT) -> str:
    """Encode a 32-byte public key into an SS58 address per Substrate spec."""
    if len(pubkey_bytes) != 32:
        raise ValueError(f"Public key must be 32 bytes, got {len(pubkey_bytes)}")

    if 0 <= ss58_format <= 63:
        format_bytes = bytes([ss58_format])
    elif 64 <= ss58_format <= 16383:
        first = ((ss58_format & 0xFC) >> 2) | 0x40
        second = (ss58_format >> 8) | ((ss58_format & 0x03) << 6)
        format_bytes = bytes([first, second])
    else:
        raise ValueError(f"Invalid ss58_format: {ss58_format}")

    payload = format_bytes + pubkey_bytes
    checksum = hashlib.blake2b(SS58_PREFIX + payload, digest_size=64).digest()[:2]
    return b58encode(payload + checksum)


def private_key_to_ss58(private_key_hex: str, ss58_format: int = DEFAULT_SS58_FORMAT) -> str:
    """Derive SS58 format 42 address from a 32-byte hex-encoded Ed25519 private key."""
    clean_hex = private_key_hex.removeprefix("0x").strip()
    raw_bytes = bytes.fromhex(clean_hex)
    if len(raw_bytes) != 32:
        raise ValueError(f"Private key hex must be 32 bytes (64 hex characters), got {len(raw_bytes)} bytes")

    priv = Ed25519PrivateKey.from_private_bytes(raw_bytes)
    pub_bytes = priv.public_key().public_bytes_raw()
    return ss58_encode(pub_bytes, ss58_format)


def sign_message(private_key_hex: str, message: str) -> str:
    """Sign UTF-8 string message using Ed25519 and return 0x-prefixed hex signature."""
    clean_hex = private_key_hex.removeprefix("0x").strip()
    raw_bytes = bytes.fromhex(clean_hex)
    priv = Ed25519PrivateKey.from_private_bytes(raw_bytes)
    sig_bytes = priv.sign(message.encode("utf-8"))
    return "0x" + sig_bytes.hex()


def generate_new_wallet() -> Tuple[str, str]:
    """Generate a fresh cryptographically secure Ed25519 private key (hex) and SS58 address."""
    priv = Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes_raw()
    priv_hex = priv_bytes.hex()
    pub_bytes = priv.public_key().public_bytes_raw()
    ss58_addr = ss58_encode(pub_bytes, DEFAULT_SS58_FORMAT)
    return priv_hex, ss58_addr
