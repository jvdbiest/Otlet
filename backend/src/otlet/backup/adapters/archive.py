# SPDX-License-Identifier: AGPL-3.0-or-later
"""A backup as one .tar file to download (Réglages › Sauvegardes), written as it is read: a
backup of several gigabytes never sits in memory nor in a temporary file."""

import tarfile
from collections.abc import Iterator
from pathlib import Path

BLOCK = 512
CHUNK = 1024 * 1024


def tar_stream(folder: Path) -> Iterator[bytes]:
    """The files of `folder`, under its name, in the POSIX tar format."""
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        info = tarfile.TarInfo(f"{folder.name}/{path.relative_to(folder).as_posix()}")
        stat = path.stat()
        info.size = stat.st_size
        info.mtime = int(stat.st_mtime)
        info.mode = 0o640
        yield info.tobuf(format=tarfile.PAX_FORMAT)
        with path.open("rb") as file:
            yield from iter(lambda: file.read(CHUNK), b"")
        remainder = info.size % BLOCK
        if remainder:
            yield b"\0" * (BLOCK - remainder)
    yield b"\0" * (2 * BLOCK)
