# SPDX-License-Identifier: AGPL-3.0-or-later
"""A backup as one .zip file to download (Réglages › Sauvegardes), written as it is read: a
backup of several gigabytes never sits in memory nor in a temporary file. Its files are stored,
not compressed again: they are encrypted, or already compressed."""

import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO, cast

CHUNK = 1024 * 1024

README = """Sauvegarde Otlet {name}

Ce fichier est une sauvegarde complète d'une instance Otlet, destinée à la restauration.
Il n'est pas fait pour être ouvert ni modifié : son contenu est chiffré quand la sauvegarde
l'est, et ne s'ouvre qu'avec la phrase de passe des sauvegardes.

Contenu :
- manifest.json : la date, les versions, ce que contient la sauvegarde (lisible) ;
- database.dump(.enc) : la base de données ;
- files/ : les images de la médiathèque ;
- secrets/ : les clés de l'instance (seulement si la sauvegarde est chiffrée).

Pour restaurer : copiez le dossier {name} (dézippé) dans le dossier de sauvegarde de
l'instance, puis suivez la documentation « Sauvegarde et restauration ».
"""


class _Sink:
    """What the archive writes, handed out as it comes."""

    def __init__(self) -> None:
        self._parts: list[bytes] = []
        self._written = 0

    def write(self, data: bytes) -> int:
        self._parts.append(bytes(data))
        self._written += len(data)
        return len(data)

    def tell(self) -> int:
        return self._written

    def flush(self) -> None:
        pass

    def take(self) -> bytes:
        data = b"".join(self._parts)
        self._parts.clear()
        return data


def zip_stream(folder: Path) -> Iterator[bytes]:
    """The files of `folder`, under its name, with a LISEZMOI.txt, in a ZIP (Zip64)."""
    sink = _Sink()
    with zipfile.ZipFile(
        cast(IO[bytes], sink), "w", zipfile.ZIP_STORED, allowZip64=True
    ) as archive:
        archive.writestr(f"{folder.name}/LISEZMOI.txt", README.format(name=folder.name))
        yield sink.take()
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            name = f"{folder.name}/{path.relative_to(folder).as_posix()}"
            with path.open("rb") as source, archive.open(name, "w", force_zip64=True) as target:
                for chunk in iter(lambda: source.read(CHUNK), b""):
                    target.write(chunk)
                    yield sink.take()
            yield sink.take()
    yield sink.take()
