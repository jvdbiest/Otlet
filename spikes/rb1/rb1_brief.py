# SPDX-License-Identifier: AGPL-3.0-or-later
"""RB1, phase 2 (docs/spikes/RB1.md §3): for each question of /data/ask.jsonl, the list to check as
the labels confirm it (R as matter, C as context, from the kept then the close of the first sort),
a brief and its draft, through the routes of the product as Joël's user. Run in the api container;
the worker writes the drafts, one at a time:
    python /data/rb1_brief.py      -> /data/drafts.jsonl (one line per question; resumes)
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path
from uuid import UUID

from otlet.entrypoints.api.app import create_app
from otlet.platform import database
from otlet.platform.config import Settings
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces

WS = UUID("0150f5a4-a6bf-40db-ba7a-256b75d6d412")
USER = UUID("1fd3f00a-87b4-4473-aaf9-db737556c1b8")
BASE = f"/api/workspaces/{WS}"
MATTER_MAX = 20  # what a brief takes
CONTEXT_MAX = 3
settings = Settings.from_env()
engine = database.create_engine(settings.require_database_url())
app = create_app(settings)
context = Workspaces(PostgresWorkspaceStore(engine)).enter(USER, WS)
app.dependency_overrides[app.state.workspace_context] = lambda: context


async def _call(method, path, body):
    path, _, query = path.partition("?")
    headers = [
        (b"host", b"otlet"),
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
        "path": path, "raw_path": path.encode(), "query_string": query.encode(), "root_path": "",
        "scheme": "https", "server": ("otlet", 443), "client": ("banc", 1), "headers": headers,
    }
    sent = {"done": False}
    out = {"status": 0, "body": bytearray()}

    async def receive():
        if sent["done"]:
            await asyncio.sleep(3600)
        sent["done"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            out["status"] = message["status"]
        elif message["type"] == "http.response.body":
            out["body"].extend(message.get("body", b""))

    await app(scope, receive, send)
    return out["status"], json.loads(bytes(out["body"]) or b"null")


def api(method, path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else b""
    return asyncio.run(_call(method, BASE + path, body))


def label(spec, title):
    if any(re.search(p, title, re.I) for p in spec["R"]):
        return "R"
    if any(re.search(p, title, re.I) for p in spec["C"]):
        return "C"
    return None


SPEC = {q["n"]: q for q in json.load(open("/data/questions.json", encoding="utf-8"))["questions"]}
asked = [json.loads(line) for line in open("/data/ask.jsonl", encoding="utf-8")]
OUT = Path("/data/drafts.jsonl")
done = {json.loads(line)["n"] for line in OUT.open(encoding="utf-8")} if OUT.exists() else set()

for record in asked:
    n = record["n"]
    if n in done:
        continue
    spec = SPEC[n]
    line = {"n": n, "q": record["q"]}
    verdicts = record["sorts"][0]["verdicts"] if record["sorts"] else {}
    verdict = lambda c: (verdicts.get(c["id"]) or [None])[0]  # noqa: E731
    kept = [c for c in record["candidates"] if verdict(c) == "traite"]
    close = [c for c in record["candidates"] if verdict(c) not in ("traite", "hors_sujet")]
    shown = kept + close if verdicts else record["candidates"]
    matter = [c for c in shown if label(spec, c["title"]) == "R"][:MATTER_MAX]
    room = min(CONTEXT_MAX, MATTER_MAX - len(matter))
    ctx = [c for c in shown if label(spec, c["title"]) == "C"][:room]
    line.update({"matter": [c["title"][:90] for c in matter], "context": [c["title"][:90] for c in ctx]})
    if not matter:
        line["brief"] = "none: no item answers, the author writes no brief"
    else:
        status, brief = api("POST", "/briefs", {
            "title": spec["q"], "item_ids": [c["id"] for c in matter + ctx],
            "context_ids": [c["id"] for c in ctx], "conversation_id": record["conv"],
        })
        line["brief"] = status
        if status == 201:
            line["brief_id"] = brief["id"]
            time.sleep(5)
            status, generation = api("POST", f"/briefs/{brief['id']}/generations", {"force": True})
            started = time.time()
            got = {}
            while status == 202 and time.time() - started < 1800:
                _, got = api("GET", f"/generations/{generation['id']}")
                if got["status"] != "running":
                    break
                time.sleep(15)
            _, draft = api("GET", f"/briefs/{brief['id']}/draft")
            details = got.get("details") or {}
            keys = ("refusals", "sources", "unsupported", "answer", "lone_sections", "matter_words")
            line.update({
                "status": got.get("status"), "error": got.get("error"),
                "seconds": round(time.time() - started),
                "attempts": [[a.get("model"), a.get("result"), a.get("seconds")] for a in got.get("attempts", [])],
                "details": {k: details.get(k) for k in keys},
                "article": (draft or {}).get("article"),
            })
    with OUT.open("a", encoding="utf-8") as out:
        out.write(json.dumps(line, ensure_ascii=False) + chr(10))
    print(n, line.get("brief"), line.get("status"), line.get("seconds"), flush=True)
    time.sleep(20)
print("finished", flush=True)
sys.exit(0)
