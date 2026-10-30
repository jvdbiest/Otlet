# SPDX-License-Identifier: AGPL-3.0-or-later
"""The local encoder (ADR-0045): the model runs with ONNX Runtime, in the worker, with its own
tokenizer; the vector of a text is the mean of its token vectors, normalised (what the spike
measured with fastembed, which pins an older Pillow than Otlet's). The files are in the image
(OTLET_MODELS_DIR): nothing is downloaded at run time."""

import ctypes
import gc
import os
from collections.abc import Sequence
from pathlib import Path

MODELS_DIR = "OTLET_MODELS_DIR"
# The quantised ONNX export of the model (Qdrant, Apache-2.0), at a fixed revision.
FOLDER = "paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
REPOSITORY = "Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
REVISION = "faf4aa4225822f3bc6376869cb1164e8e3feedd0"
FILES = ("model_optimized.onnx", "tokenizer.json")
# Titles and the start of a summary fit; longer texts are cut.
MAX_TOKENS = 256
# Small batches keep the memory low on the NAS (725 MB at the peak with 8).
BATCH = 8


def download(models: Path) -> None:
    """Fetches the files of the model at REVISION; run once, when the image is built."""
    import urllib.request

    folder = models / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        url = f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{name}"
        urllib.request.urlretrieve(url, folder / name)  # noqa: S310 (a fixed https address)


class OnnxEncoder:
    def __init__(self) -> None:
        # Heavy: loaded only by the encoding job.
        import onnxruntime
        from tokenizers import Tokenizer

        folder = Path(os.environ.get(MODELS_DIR, "/opt/otlet/models")) / FOLDER
        self._tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self._tokenizer.enable_truncation(MAX_TOKENS)
        self._tokenizer.enable_padding()
        # Two threads at most: the worker shares the machine with the API and PostgreSQL (four
        # cores were taken on the work VM with the defaults).
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = min(2, os.cpu_count() or 1)
        options.inter_op_num_threads = 1
        options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
        self._session = onnxruntime.InferenceSession(
            str(folder / "model_optimized.onnx"), options, providers=["CPUExecutionProvider"]
        )
        self._inputs = {i.name for i in self._session.get_inputs()}

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        import numpy as np

        out: list[list[float]] = []
        for start in range(0, len(texts), BATCH):
            encodings = self._tokenizer.encode_batch(list(texts[start : start + BATCH]))
            ids = np.array([e.ids for e in encodings], dtype=np.int64)
            mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self._inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            tokens = self._session.run(None, feed)[0]
            weights = mask[..., None].astype(np.float32)
            means = (tokens * weights).sum(axis=1) / np.maximum(weights.sum(axis=1), 1e-9)
            means /= np.maximum(np.linalg.norm(means, axis=1, keepdims=True), 1e-12)
            out.extend(means.astype(float).tolist())
        return out


def release_memory() -> None:
    """Gives the memory of the model back to the system once it is no longer used: freed
    memory otherwise stays with the worker, which lives on between jobs."""
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except OSError:  # not glibc
        pass


def encode_question(question: str) -> list[float]:
    """The vector of one question, for the Reporter: the model is loaded for it and let go
    after (some 700 MB, for a second or two)."""
    encoder = OnnxEncoder()
    try:
        return encoder.encode([question])[0]
    finally:
        del encoder
        release_memory()
