# SPDX-License-Identifier: AGPL-3.0-or-later
"""P02 §3.1: the translations and paraphrases, one call at a time, by a local Ollama.

    OLLAMA_URL=http://… OLLAMA_MODEL=qwen3:14b python3 generate.py <corpus folder>

Standard library only: it runs on the VM itself. Resumes where it stopped; never writes to Otlet.
"""

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

MAX_SECONDS = 3 * 3600
MAX_RETRIES = 10
PAUSE = 2
THINK = re.compile(r"<think>.*?</think>", re.S)
NAMES = {"fr": "French", "en": "English", "nl": "Dutch"}
TARGET = {"fr": "en", "en": "fr", "nl": "fr"}
STOP_WORDS = {
    "fr": {"le", "la", "les", "des", "une", "est", "dans", "pour", "que", "qui", "sur", "avec"},
    "en": {"the", "of", "and", "to", "in", "is", "that", "for", "with", "was", "on", "by"},
    "nl": {"de", "het", "een", "van", "en", "in", "is", "dat", "op", "voor", "met", "zijn"},
}
PROMPTS = {
    "translation": (
        "Translate this article into {target}, sentence by sentence, keeping every piece of "
        "information in the same order. Write only the translation.\n\n{text}"
    ),
    "paraphrase": (
        "Rewrite this article in {target}, sentence by sentence: the same information in the same "
        "order, with other words and other turns of phrase. Write only the new text.\n\n{text}"
    ),
}


def language_of(text: str) -> str:
    tokens = re.findall(r"\w+", text.lower())
    return max(STOP_WORDS, key=lambda lang: sum(t in STOP_WORDS[lang] for t in tokens))


def call(url: str, model: str, prompt: str, seed: int) -> str:
    body = {
        "model": model,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "seed": seed, "num_ctx": 8192, "num_predict": 1600},
        "messages": [{"role": "user", "content": prompt}],
    }
    request = urllib.request.Request(  # noqa: S310 (the address of the local model)
        f"{url}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=900) as response:  # noqa: S310
        text = json.load(response)["message"]["content"]
    return THINK.sub("", text).strip()


def main() -> None:
    corpus = Path(sys.argv[1])
    url, model = os.environ["OLLAMA_URL"].rstrip("/"), os.environ["OLLAMA_MODEL"]
    selected = json.loads((corpus / "selected.json").read_text(encoding="utf-8"))
    path = corpus / "generated.jsonl"
    done = []
    if path.exists():
        with path.open(encoding="utf-8") as lines:
            done = [json.loads(line) for line in lines if line.strip()]
    accepted = {(d["id"], d["kind"]) for d in done if d["accepted"]}
    tried = {(d["id"], d["kind"]): 0 for d in done}
    for d in done:
        tried[(d["id"], d["kind"])] += 1
    retries = sum(not d["accepted"] for d in done)
    started = time.monotonic()
    for item in selected:
        for kind in PROMPTS:
            key = (item["id"], kind)
            while key not in accepted and tried.get(key, 0) < 2:
                if time.monotonic() - started > MAX_SECONDS:
                    print("3 h reached: stopping (P02 §3.4)")
                    return
                if tried.get(key, 0) == 1 and retries >= MAX_RETRIES:
                    break
                target = TARGET[item["lang"]] if kind == "translation" else item["lang"]
                prompt = PROMPTS[kind].format(target=NAMES[target], text=item["text"])
                began = time.monotonic()
                text = call(url, model, prompt, 2026 + tried.get(key, 0))
                ratio = len(text.split()) / len(item["text"].split())
                good = 0.7 <= ratio <= 1.4 and language_of(text) == target
                row = {
                    "id": item["id"],
                    "kind": kind,
                    "target": target,
                    "ratio": round(ratio, 2),
                    "seconds": round(time.monotonic() - began, 1),
                    "accepted": good,
                    "text": text,
                }
                with path.open("a", encoding="utf-8") as out:
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                print({k: row[k] for k in ("id", "kind", "ratio", "seconds", "accepted")}, flush=True)
                tried[key] = tried.get(key, 0) + 1
                retries += not good
                if good:
                    accepted.add(key)
                time.sleep(PAUSE)
    print("done", flush=True)


if __name__ == "__main__":
    main()
