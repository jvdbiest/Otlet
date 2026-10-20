# SPDX-License-Identifier: AGPL-3.0-or-later
"""The bench of the drafts: the reference briefs (briefs.json), written by a model with the
prompt of the product as it stands, then measured (metrics.py). Two runs a brief at least: the
gap from one run to the next is large (the audit: 20 % on the length, twice the judgements).

Usage, from the repository root, after export.sh:
  python tools/bench_redaction/run.py --endpoint http://localhost:11434/v1 --model qwen3:14b \\
      [--repeat 2] [--only disney-top10,f1-panorama] [--no-charter]

Same call as the product (OpenAI-compatible endpoint, temperature 0.2, JSON schema, the room of
the window as configured), without the repair: the bench measures the first answer.
Writes results/<date>-<model>-<prompt>.jsonl (every run) and .md (the summary)."""

import argparse
import json
import statistics
import sys
import time
import urllib.request
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend" / "src"))
sys.path.insert(0, str(HERE))

from metrics import measure  # noqa: E402

from otlet.writing.domain.brief import BriefFields, Length, Mode  # noqa: E402
from otlet.writing.domain.charter import DEFAULT_CHARTER  # noqa: E402
from otlet.writing.domain.draft import (  # noqa: E402
    PROMPT_VERSION,
    WORDS,
    SourceText,
    check_answer,
    longest_for,
    messages,
    output_schema,
    prompt_sources,
    source_budget,
)

OUTPUT_TOKENS = {length: words * 3 + 1000 for length, words in WORDS.items()}  # as drafts.py
SUMMARY_KEYS = (
    "words",
    "length_ratio",
    "unsupported_per_100",
    "copy_share",
    "copied_passages",
    "judgements_per_100",
    "items_kept",
    "names_kept",
    "seconds",
)


def call(
    endpoint: str,
    model: str,
    prompt: list[tuple[str, str]],
    schema: dict,
    max_tokens: int,
    timeout: int,
) -> dict:
    body = {
        "model": model,
        "messages": [{"role": role, "content": content} for role, content in prompt],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "article_draft", "schema": schema},
        },
    }
    if not endpoint.startswith(("http://", "https://")):
        raise SystemExit("--endpoint is an http(s) address")
    request = urllib.request.Request(  # noqa: S310 (checked just above)
        endpoint.rstrip("/") + "/chat/completions",
        json.dumps(body).encode(),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (the bench's own endpoint)
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--only", default="")
    parser.add_argument("--window", type=int, default=16384, help="the window set on the provider")
    parser.add_argument("--no-charter", action="store_true")
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args()

    briefs = json.loads((HERE / "briefs.json").read_text(encoding="utf-8"))["briefs"]
    texts = {}
    for line in (HERE / "data" / "sources.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            source = json.loads(line)
            texts[source["url"]] = source
    only = {name for name in args.only.split(",") if name}
    charter = "" if args.no_charter else DEFAULT_CHARTER
    stamp = datetime.now(UTC).strftime("%Y-%m-%d-%H%M")
    name = f"{stamp}-{args.model.replace(':', '_').replace('/', '_')}-{PROMPT_VERSION}"
    (HERE / "results").mkdir(exist_ok=True)
    out = (HERE / "results" / f"{name}.jsonl").open("w", encoding="utf-8")
    rows = []
    for brief in briefs:
        if only and brief["id"] not in only:
            continue
        missing = [url for url in brief["sources"] if url not in texts]
        if missing:
            print(f"{brief['id']}: sources missing from data/ (run export.sh): {missing}")
            continue
        sources = [
            SourceText(texts[u]["title"], u, None, None, texts[u]["text"]) for u in brief["sources"]
        ]
        f = dict(brief["fields"])
        fields = BriefFields(
            title=f["title"],
            item_ids=(),
            angle=f.get("angle", ""),
            instructions=f.get("instructions", ""),
            audience=f.get("audience", ""),
            tone=f.get("tone", "neutral"),
            length=Length(f.get("length", "medium")),
            mode=Mode(f.get("mode", "synthesis")),
            language=f.get("language", "fr"),
            channel=f.get("channel", ""),
        )
        # As the drafts do (drafts.py): the length the matter allows, the room left to the sources.
        matter = sum(len(s.text.split()) for s in sources)
        longest = longest_for(matter)
        used = (
            Length.SHORT if longest is None else min(fields.length, longest, key=WORDS.__getitem__)
        )
        fields = replace(fields, length=used)
        output = OUTPUT_TOKENS[used]
        prompt_srcs = prompt_sources(
            sources, max(source_budget(args.window, output) - len(charter), 0)
        )
        keys = [s.key for s in prompt_srcs]
        prompt = messages(fields, prompt_srcs, charter)
        allowed = " ".join([fields.title, fields.angle, fields.instructions])
        source_texts = [f"{s.title}\n{s.text}" for s in sources]
        for rep in range(args.repeat):
            start = time.time()
            try:
                answer = call(
                    args.endpoint,
                    args.model,
                    prompt,
                    output_schema(keys),
                    max(output, 8192),
                    args.timeout,
                )
                raw = answer["choices"][0]["message"]["content"] or ""
                usage = answer.get("usage", {})
            except Exception as error:  # noqa: BLE001 (a failed call is a result of the bench)
                raw, usage = "", {"error": str(error)}
            seconds = round(time.time() - start)
            errors = (
                check_answer(raw, keys, every_source=True, words=WORDS[used], repeats=True)
                if raw
                else ["no answer"]
            )
            measures = measure(raw, source_texts, allowed, WORDS[used], brief.get("expect", {}))
            row = {
                "brief": brief["id"],
                "rep": rep,
                "model": args.model,
                "prompt_version": PROMPT_VERSION,
                "charter": bool(charter),
                "matter_words": matter,
                "length_asked": f.get("length", "medium"),
                "length_used": used.value,
                "thin_matter": longest is None,
                "seconds": seconds,
                "usage": usage,
                "errors": errors,
                **measures,
                "raw": raw,
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            rows.append(row)
            print(
                f"{brief['id']} {rep}: {seconds} s, {measures.get('words', 0)} words, "
                f"unsupported {measures.get('unsupported', [])}, "
                f"copy {measures.get('copy_share', '-')}, "
                f"errors {len(errors)}",
                flush=True,
            )
    out.close()
    (HERE / "results" / f"{name}.md").write_text(
        summary(rows, args.model, bool(charter)), encoding="utf-8"
    )
    print(f"results/{name}.md")


def summary(rows: list[dict], model: str, charter: bool) -> str:
    lines = [
        f"# Banc de rédaction : {model}, {PROMPT_VERSION}, charte {'oui' if charter else 'non'}",
        "",
        "| Brief | Essais | " + " | ".join(SUMMARY_KEYS) + " | Refus de forme |",
        "|---" * (len(SUMMARY_KEYS) + 3) + "|",
    ]
    for brief in dict.fromkeys(r["brief"] for r in rows):
        mine = [r for r in rows if r["brief"] == brief and r.get("valid")]
        cells = []
        for key in SUMMARY_KEYS:
            values = [r[key] for r in mine if r.get(key) is not None]
            cells.append("-" if not values else f"{statistics.mean(values):.2f}")
        refused = sum(1 for r in rows if r["brief"] == brief and r["errors"])
        lines.append(f"| {brief} | {len(mine)} | " + " | ".join(cells) + f" | {refused} |")
    names = sorted({n for r in rows for n in r.get("unsupported", [])})
    lines += ["", "Absents des sources (à relire) : " + (", ".join(names) or "aucun"), ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
