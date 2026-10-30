# SPDX-License-Identifier: AGPL-3.0-or-later
"""What is encoded, and with which model (ADR-0045).

The spike of 2026-10-30 compared two multilingual models on the Veille of Joël: MiniLM-L12 did
as well as mpnet-base for a third of the time and half the memory (322 ms per item and 725 MB
on the NAS). A vector is only compared with vectors of the same model: the model is kept with
each vector.
"""

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSIONS = 384
# The title and the start of the summary: what the spike encoded.
SUMMARY_CHARS = 300


def text_of(title: str, summary: str) -> str:
    """The text of an item as the model reads it."""
    title = " ".join(title.split())
    summary = " ".join(summary.split())[:SUMMARY_CHARS]
    return f"{title}. {summary}" if summary else title
