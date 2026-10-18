# SPDX-License-Identifier: AGPL-3.0-or-later
"""The file storage on the local disk (ARCHITECTURE §5, « Stockage de fichiers »): each file
under its SHA-256, written once, atomically. A storage of objects could replace it."""

import hashlib
import os
import re
import tempfile
from pathlib import Path

SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXTENSION = re.compile(r"^[a-z0-9]{1,8}$")


class DiskFiles:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, sha256: str, extension: str) -> Path:
        if not SHA256.match(sha256) or not EXTENSION.match(extension):
            raise ValueError("invalid file address")
        return self._root / sha256[:2] / sha256[2:4] / f"{sha256}.{extension}"

    def put(self, data: bytes, extension: str) -> str:
        sha256 = hashlib.sha256(data).hexdigest()
        path = self._path(sha256, extension)
        if path.exists():
            return sha256
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".upload-")
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        return sha256

    def get(self, sha256: str, extension: str) -> bytes | None:
        path = self._path(sha256, extension)
        return path.read_bytes() if path.exists() else None
