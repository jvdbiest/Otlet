# SPDX-License-Identifier: AGPL-3.0-or-later
"""Seal a secret with the instance public key. Usable by any role, including the API."""

import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from otlet.platform.secrets import (
    HKDF_INFO,
    KEY_ID_LENGTH,
    NONCE_LENGTH,
    VERSION,
    SecretError,
)


def raw_public_bytes(public_key: X25519PublicKey) -> bytes:
    return public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(public_key: X25519PublicKey) -> bytes:
    """Short identifier of the key pair, stored with each sealed value for key rotation."""
    return hashlib.sha256(raw_public_bytes(public_key)).digest()[:KEY_ID_LENGTH]


def load_public_key(path: Path) -> X25519PublicKey:
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, X25519PublicKey):
        raise SecretError(f"{path} is not an X25519 public key")
    return key


def derive_key(shared_secret: bytes, ephemeral: bytes, recipient: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=ephemeral + recipient,
        info=HKDF_INFO,
    ).derive(shared_secret)


def seal(public_key: X25519PublicKey, plaintext: bytes, context: bytes) -> bytes:
    ephemeral_private = X25519PrivateKey.generate()
    ephemeral = raw_public_bytes(ephemeral_private.public_key())
    recipient = raw_public_bytes(public_key)
    key = derive_key(ephemeral_private.exchange(public_key), ephemeral, recipient)
    nonce = os.urandom(NONCE_LENGTH)
    header = bytes([VERSION]) + key_id(public_key) + ephemeral + nonce
    return header + AESGCM(key).encrypt(nonce, plaintext, header + context)
