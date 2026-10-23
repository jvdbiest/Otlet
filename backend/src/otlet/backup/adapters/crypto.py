# SPDX-License-Identifier: AGPL-3.0-or-later
"""Encryption of the backups (ADR-0042): a key derived from the administrator's passphrase
(scrypt), files sealed by chunks with AES-256-GCM. The passphrase is never written in a backup;
the salt is, with a key id that tells which backups share a key (and so their files)."""

import hashlib
import hmac
import json
import os
import struct
from pathlib import Path
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"OTLETBK1"
CHUNK = 1024 * 1024
KEYRING = "keyring.json"  # salt and key id, at the root of the destination: not secret
SCRYPT = {"n": 2**15, "r": 8, "p": 1}


class WrongPassphrase(ValueError):
    pass


class Cipher:
    def __init__(self, key: bytes) -> None:
        self._aead = AESGCM(key)
        self.key_id = hmac.new(key, b"otlet-backup-key-id", hashlib.sha256).hexdigest()[:16]

    @classmethod
    def for_destination(cls, destination: Path, passphrase: str) -> "Cipher":
        """The key of this destination: its salt is made once and kept beside the backups.
        Another passphrase gives another key id: those backups then share no files."""
        keyring = destination / KEYRING
        if keyring.exists():
            salt = bytes.fromhex(json.loads(keyring.read_text("utf-8"))["salt"])
        else:
            salt = os.urandom(16)
            keyring.write_text(
                json.dumps({"salt": salt.hex(), "kdf": "scrypt", **SCRYPT}) + "\n", "utf-8"
            )
        key = Scrypt(salt=salt, length=32, **SCRYPT).derive(passphrase.encode("utf-8"))
        return cls(key)

    def seal(self, source: BinaryIO, target: BinaryIO) -> None:
        """Chunks of 1 MiB, each with its own nonce (a random prefix and its number) and the
        last one marked, so that a cut or reordered file does not open."""
        prefix = os.urandom(8)
        target.write(MAGIC + prefix)
        number = 0
        chunk = source.read(CHUNK)
        while True:
            following = source.read(CHUNK)
            last = not following
            nonce = prefix + struct.pack(">I", number)
            target.write(self._aead.encrypt(nonce, chunk, b"last" if last else b"more"))
            if last:
                return
            chunk, number = following, number + 1

    def open(self, source: BinaryIO, target: BinaryIO) -> None:
        head = source.read(len(MAGIC) + 8)
        if head[: len(MAGIC)] != MAGIC:
            raise WrongPassphrase("not an encrypted backup file")
        prefix = head[len(MAGIC) :]
        number = 0
        sealed = source.read(CHUNK + 16)
        while True:
            following = source.read(CHUNK + 16)
            last = not following
            nonce = prefix + struct.pack(">I", number)
            try:
                target.write(self._aead.decrypt(nonce, sealed, b"last" if last else b"more"))
            except InvalidTag as error:
                raise WrongPassphrase("wrong passphrase, or a damaged file") from error
            if last:
                return
            sealed, number = following, number + 1
