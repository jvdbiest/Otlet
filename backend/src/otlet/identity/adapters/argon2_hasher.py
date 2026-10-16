# SPDX-License-Identifier: AGPL-3.0-or-later
"""Argon2id password hashing with argon2-cffi (TECH_CHOICES §19, TC-14)."""

import argon2
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class Argon2Hasher:
    """argon2-cffi's default profile: RFC 9106 low-memory (Argon2id, t=3, m=64 MiB, p=4), above
    the OWASP minimum. A hash made with older parameters is upgraded at the next sign-in."""

    def __init__(self, hasher: argon2.PasswordHasher | None = None) -> None:
        self._hasher = hasher or argon2.PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, credential: str, password: str) -> bool:
        try:
            return self._hasher.verify(credential, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, credential: str) -> bool:
        return self._hasher.check_needs_rehash(credential)
