# SPDX-License-Identifier: AGPL-3.0-or-later
"""The PDF export of a version (X03c): the HTML page of the export, printed by WeasyPrint on A4.
The same HTML as everywhere else in Otlet, floats and fonts included. WeasyPrint needs Pango,
installed in the image; it is imported only when a PDF is asked for."""


def pdf(html: str) -> bytes:
    # Pango is loaded with it: only when needed. WeasyPrint ships no types.
    from weasyprint import HTML  # type: ignore[import-untyped]  # noqa: PLC0415

    data = HTML(string=html).write_pdf()
    if data is None:  # only without a target, which is not the case here
        raise RuntimeError("WeasyPrint wrote no PDF")
    return bytes(data)
