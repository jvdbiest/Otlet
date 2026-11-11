"""LANG3: the reading aid of REL2 for every sentence of the 15 drafts, as the product shows it
(POST /briefs/{id}/support), written to /data/aide.jsonl for the blind reading. No model.
Run in the api container: python /data/aide.py"""

import json
import re
import sys

sys.argv = ["lang1"]  # the helpers of lang1.py, without running its generations
source = open("/data/lang3.py", encoding="utf-8").read().split("from otlet.ai.adapters.postgres")[0]
exec(compile(source, "lang1_helpers", "exec"))

MIN_CHARS = 40  # as REL2: shorter sentences are not checked


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) >= MIN_CHARS]


out = open("/data/aide.jsonl", "w", encoding="utf-8")
for line in open("/data/lang3.jsonl", encoding="utf-8"):
    r = json.loads(line)
    versions = (r.get("article") or {}).get("versions") or []
    if not versions:
        continue
    document = versions[-1]["document"]
    titles = {s["id"]: s.get("titre", "") for s in document["attrs"].get("sources") or []}
    checks = []
    for node in document.get("content") or []:
        if node.get("type") != "paragraph":
            continue
        parts = node.get("content") or []
        cited = []
        for p in parts:
            for m in p.get("marks") or []:
                if m.get("type") == "source_ref" and m["attrs"]["source"] not in cited:
                    cited.append(m["attrs"]["source"])
        text = "".join(p.get("text", "") for p in parts if not p.get("marks"))
        body = [{"key": k, "title": titles.get(k, "")} for k in cited]
        for s in sentences(text):
            status, shown = api("POST", f"/briefs/{r['brief']}/support",
                                {"text": s[:2000], "sources": body})
            checks.append({"sentence": s, "shown": shown if status == 200 else []})
    out.write(json.dumps({"brief": r["brief"], "checks": checks}, ensure_ascii=False) + chr(10))
    out.flush()
print("finished", flush=True)
