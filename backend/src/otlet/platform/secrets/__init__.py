# SPDX-License-Identifier: AGPL-3.0-or-later
"""Secrets sealed with the instance public key, opened by the worker only (DR6, M-06).

`sealing` needs only the public key and is what the API uses. `opening` needs the private
key, which is mounted in the worker container alone; an import contract forbids the API
entry point from importing it. The real guarantee is the absence of the key, not the
contract: see docs/spikes/S6.md, criterion C3.

Format (version 1), all lengths in bytes:
    version (1) | key id (8) | ephemeral X25519 public key (32) | nonce (12) | AES-GCM output
The AES-256-GCM key is derived with HKDF-SHA256 from the X25519 shared secret; the header
and the caller's context (for example the secret's name) are authenticated as associated
data, so a sealed value cannot be moved to another name unnoticed.
"""

VERSION = 1
KEY_ID_LENGTH = 8
PUBLIC_KEY_LENGTH = 32
NONCE_LENGTH = 12
HEADER_LENGTH = 1 + KEY_ID_LENGTH + PUBLIC_KEY_LENGTH + NONCE_LENGTH
HKDF_INFO = b"otlet sealed secret v1"


class SecretError(Exception):
    """A secret cannot be sealed or opened."""


class PrivateKeyUnavailable(SecretError):
    """This process has no private key: only the worker can open secrets."""
