# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from hypothesis import given
from hypothesis import strategies as st

from otlet.platform.secrets import PrivateKeyUnavailable, SecretError, opening, sealing

PRIVATE = X25519PrivateKey.generate()
PUBLIC = PRIVATE.public_key()


def test_round_trip() -> None:
    sealed = sealing.seal(PUBLIC, b"wp-application-password", b"secret:site")
    assert opening.open_sealed(PRIVATE, sealed, b"secret:site") == b"wp-application-password"


@given(st.binary(max_size=4096), st.binary(max_size=64))
def test_round_trip_any_value(plaintext: bytes, context: bytes) -> None:
    assert opening.open_sealed(PRIVATE, sealing.seal(PUBLIC, plaintext, context), context) == (
        plaintext
    )


def test_each_sealing_differs() -> None:
    assert sealing.seal(PUBLIC, b"same", b"c") != sealing.seal(PUBLIC, b"same", b"c")


def test_plaintext_does_not_appear() -> None:
    assert b"wp-application-password" not in sealing.seal(PUBLIC, b"wp-application-password", b"")


@pytest.mark.parametrize("position", [0, 5, 20, 50, -1])
def test_altered_value_is_rejected(position: int) -> None:
    sealed = bytearray(sealing.seal(PUBLIC, b"value", b"c"))
    sealed[position] ^= 0x01
    with pytest.raises(SecretError):
        opening.open_sealed(PRIVATE, bytes(sealed), b"c")


def test_value_moved_to_another_name_is_rejected() -> None:
    sealed = sealing.seal(PUBLIC, b"value", b"secret:site-a")
    with pytest.raises(SecretError):
        opening.open_sealed(PRIVATE, sealed, b"secret:site-b")


def test_another_private_key_cannot_open() -> None:
    sealed = sealing.seal(PUBLIC, b"value", b"c")
    with pytest.raises(SecretError, match="another key pair"):
        opening.open_sealed(X25519PrivateKey.generate(), sealed, b"c")


def test_without_private_key_nothing_opens(tmp_path: Path) -> None:
    with pytest.raises(PrivateKeyUnavailable):
        opening.load_private_key(None)
    with pytest.raises(PrivateKeyUnavailable):
        opening.load_private_key(tmp_path / "missing.pem")


def test_keys_generated_by_openssl_format_load(tmp_path: Path) -> None:
    # configure.sh writes PKCS#8 and SubjectPublicKeyInfo PEM files, as openssl does.
    private_file = tmp_path / "private.pem"
    public_file = tmp_path / "public.pem"
    private_file.write_bytes(
        PRIVATE.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_file.write_bytes(
        PUBLIC.public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    sealed = sealing.seal(sealing.load_public_key(public_file), b"v", b"c")
    assert opening.open_sealed(opening.load_private_key(private_file), sealed, b"c") == b"v"
