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
from otlet.writing.domain.article import Version
from otlet.writing.domain.document import media_of
from otlet.writing.domain.export import filename, html_page, markdown, text

FORMATS = ("pdf", "docx", "html", "md", "txt", "json")
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

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


class Exports:
    def __init__(
        self, versions: Versions, media: MediaRead, docx: DocxWriter, pdf: PdfWriter
    ) -> None:
        self._versions = versions
        self._media = media
        self._docx = docx
        self._pdf = pdf

    def export(
        self, context: WorkspaceContext, article_id: UUID, number: int, kind: str
    ) -> Exported | None:
        """The version in `kind` (one of FORMATS); None when the version does not exist."""
        version = self._versions.version(context.workspace_id, article_id, number)
        if version is None or kind not in FORMATS:
            return None
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
