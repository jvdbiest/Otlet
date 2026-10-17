# SPDX-License-Identifier: AGPL-3.0-or-later
"""Seals the keys of AI providers with the public key of the instance (DR6): the API can seal,
only the worker, which holds the private key, can open."""

from pathlib import Path

from otlet.platform.secrets import SecretError, sealing


class PublicKeySealer:
    def __init__(self, public_key_file: Path | None) -> None:
        self._public_key = (
            None if public_key_file is None else sealing.load_public_key(public_key_file)
        )

    def seal(self, plaintext: bytes, context: bytes) -> bytes:
        if self._public_key is None:
            raise SecretError("the instance has no public key (OTLET_SECRETS_PUBLIC_KEY_FILE)")
        return sealing.seal(self._public_key, plaintext, context)
