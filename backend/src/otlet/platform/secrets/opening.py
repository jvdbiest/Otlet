# SPDX-License-Identifier: AGPL-3.0-or-later
"""Open a sealed secret with the instance private key. Worker only (DR6): the API entry
point may not import this module (import contract `secrets-worker-only`)."""

from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from otlet.platform.secrets import (
    HEADER_LENGTH,
    KEY_ID_LENGTH,
    PUBLIC_KEY_LENGTH,
    VERSION,
    PrivateKeyUnavailable,
    SecretError,
)
from otlet.platform.secrets.sealing import derive_key, key_id, raw_public_bytes


def load_private_key(path: Path | None) -> X25519PrivateKey:
    if path is None or not path.is_file():
        raise PrivateKeyUnavailable(
            "no private key in this process; secrets can only be opened by the worker"
        )
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, X25519PrivateKey):
        raise SecretError(f"{path} is not an X25519 private key")
    return key


def open_sealed(private_key: X25519PrivateKey, sealed: bytes, context: bytes) -> bytes:
    if len(sealed) < HEADER_LENGTH or sealed[0] != VERSION:
        raise SecretError("unknown sealed secret format")
    public_key = private_key.public_key()
    stored_key_id = sealed[1 : 1 + KEY_ID_LENGTH]
    if stored_key_id != key_id(public_key):
        raise SecretError("sealed with another key pair")
    ephemeral = sealed[1 + KEY_ID_LENGTH : 1 + KEY_ID_LENGTH + PUBLIC_KEY_LENGTH]
    nonce = sealed[1 + KEY_ID_LENGTH + PUBLIC_KEY_LENGTH : HEADER_LENGTH]
    shared = private_key.exchange(X25519PublicKey.from_public_bytes(ephemeral))
    key = derive_key(shared, ephemeral, raw_public_bytes(public_key))
    try:
        return AESGCM(key).decrypt(nonce, sealed[HEADER_LENGTH:], sealed[:HEADER_LENGTH] + context)
    except InvalidTag as error:
        raise SecretError("sealed secret altered, or opened under another name") from error
