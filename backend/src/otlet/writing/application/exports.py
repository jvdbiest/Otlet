# SPDX-License-Identifier: AGPL-3.0-or-later
"""Exports of a version (X03c, ADR-0036): PDF, DOCX, HTML, Markdown, TXT and JSON, made on demand
from the version as it is, never stored."""

import base64
import io
import json
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from otlet.workspaces.domain.model import WorkspaceContext
from otlet.writing.application.library import GateOf
from otlet.writing.domain.article import Version
from otlet.writing.domain.document import media_of
from otlet.writing.domain.export import filename, html_page, markdown, text
from otlet.writing.domain.proximity import Gate, TooClose

FORMATS = ("pdf", "docx", "html", "md", "txt", "json")
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
REFUSALS: dict[Gate, str] = {
    "blocked": "trop proche d'une source. Ouvrez l'article pour voir les passages, reformulez ou "
    "justifiez.",
    "pending": "contrôle de proximité en cours. Réessayez dans quelques minutes.",
    "open": "",
}

# An image of the workspace by its id: bytes, type, width and height; None when it is gone.
MediaRead = Callable[[WorkspaceContext, str], tuple[bytes, str, int, int] | None]
DocxWriter = Callable[[str, dict[str, Any], Callable[[str], tuple[bytes, int, int] | None]], bytes]
PdfWriter = Callable[[str], bytes]


class Versions(Protocol):
    def version(self, workspace_id: UUID, article_id: UUID, number: int) -> Version | None: ...


@dataclass(frozen=True, slots=True)
class Exported:
    data: bytes
    mime: str
    filename: str
    refused: int = 0  # the versions of a selection left out (U05)


class Exports:
    def __init__(
        self,
        versions: Versions,
        media: MediaRead,
        docx: DocxWriter,
        pdf: PdfWriter,
        gate: GateOf | None = None,
    ) -> None:
        self._versions = versions
        self._media = media
        self._docx = docx
        self._pdf = pdf
        self._gate = gate

    def export_many(
        self, context: WorkspaceContext, picks: list[tuple[UUID, int]], kind: str
    ) -> Exported | None:
        """Several versions in one ZIP (Joël, 2026-10-20): a file each, in `kind`; a Markdown
        with images keeps its folder. None when none of them exists. A version that cannot go out
        (U05) does not stop the others: NON-EXPORTES.txt names it, and `refused` counts them.
        TooClose when none can go out."""
        buffer = io.BytesIO()
        names: set[str] = set()
        written = 0
        refused: list[tuple[str, Gate]] = []
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for article_id, number in picks:
                try:
                    exported = self.export(context, article_id, number, kind)
                except TooClose as error:
                    version = self._versions.version(context.workspace_id, article_id, number)
                    refused.append((version.title if version else str(article_id), error.gate))
                    continue
                if exported is None:
                    continue
                stem, _, extension = exported.filename.rpartition(".")
                name, n = exported.filename, 1
                while name in names:  # two articles of the same title
                    n += 1
                    name = f"{stem}-{n}.{extension}"
                names.add(name)
                if extension == "zip":
                    folder = name.rpartition(".")[0]
                    with zipfile.ZipFile(io.BytesIO(exported.data)) as inner:
                        for entry in inner.namelist():
                            archive.writestr(f"{folder}/{entry}", inner.read(entry))
                else:
                    archive.writestr(name, exported.data)
                written += 1
            if written > 0 and refused:
                archive.writestr(
                    "NON-EXPORTES.txt",
                    "\n".join(f"{title} : {REFUSALS[gate]}" for title, gate in refused) + "\n",
                )
        if written == 0:
            if refused:
                raise TooClose("blocked" if any(g == "blocked" for _, g in refused) else "pending")
            return None
        return Exported(
            buffer.getvalue(), "application/zip", f"articles-{kind}.zip", refused=len(refused)
        )

    def export(
        self, context: WorkspaceContext, article_id: UUID, number: int, kind: str
    ) -> Exported | None:
        """The version in `kind` (one of FORMATS); None when the version does not exist. A version
        too close to a source does not go out unless its author said why: TooClose (U05)."""
        version = self._versions.version(context.workspace_id, article_id, number)
        if version is None or kind not in FORMATS:
            return None
        if self._gate is not None:
            gate = self._gate(context.workspace_id, article_id, number)
            if gate != "open":
                raise TooClose(gate)
        title, document = version.title, version.document
        images = {m: self._media(context, m) for m in media_of(document)}

        def data_url(media: str) -> str:
            found = images.get(media)
            if found is None:
                return ""
            return f"data:{found[1]};base64,{base64.b64encode(found[0]).decode()}"

        if kind == "html":
            page = html_page(title, document, data_url)
            return Exported(page.encode(), "text/html; charset=utf-8", filename(title, "html"))
        if kind == "pdf":
            pdf = self._pdf(html_page(title, document, data_url))
            return Exported(pdf, "application/pdf", filename(title, "pdf"))
        if kind == "docx":

            def pixels(media: str) -> tuple[bytes, int, int] | None:
                found = images.get(media)
                return None if found is None else (found[0], found[2], found[3])

            return Exported(
                self._docx(title, document, pixels),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename(title, "docx"),
            )
        if kind == "txt":
            return Exported(
                text(title, document).encode(), "text/plain; charset=utf-8", filename(title, "txt")
            )
        if kind == "json":
            body = json.dumps({"titre": title, "document": document}, ensure_ascii=False, indent=2)
            return Exported(body.encode(), "application/json", filename(title, "json"))
        # Markdown: with images, a ZIP of the text and its images folder.
        present = {m: found for m, found in images.items() if found is not None}

        def path(media: str) -> str:
            found = present.get(media)
            return f"images/{media}.{EXTENSIONS.get(found[1], 'img')}" if found else ""

        written = markdown(title, document, path)
        if not present:
            return Exported(written.encode(), "text/markdown; charset=utf-8", filename(title, "md"))
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr(filename(title, "md"), written)
            for media, found in present.items():
                bundle.writestr(path(media), found[0])
        return Exported(archive.getvalue(), "application/zip", filename(title, "zip"))
