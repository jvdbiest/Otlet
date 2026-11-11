"""LANG1 (docs/spikes/LANG1.md): 5 subjects x 3 languages x 3 local models, medium length, one
generation at a time. Resumable: a combination already in /data/lang1.jsonl is skipped.
Run in the api container: python /data/lang1.py"""

import asyncio
import json
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


PROVIDER = "8e985383-8ca8-4c82-99c3-b940039b2c14"  # « Modèles Locaux 2 », Ollama of Joël's PC
SUBJECTS = {
    "motogp": "3cc4fad5-8039-4765-be42-c74e4a3e0482",
    "rhum": "9618fc38-7653-42fc-a901-105c9c919dd9",
    "nvidia": "c22f90fc-83f4-48a2-95e9-ad89dde0b2cf",
    "cpas": "2e70f69f-dad1-4d0e-982b-4910638dbcc6",
    "cracovie": "e850ae32-7851-4d31-bb10-3772af5253d6",
}
LANGUAGES = ("fr", "nl", "en")
MODELS = ("qwen3:14b", "mistral-small:latest", "gemma4:latest")
LIMIT = 40 * 60  # a generation longer than this is stopped and counted as not finished

OUT = Path("/data/lang1.jsonl")
done = set()
if OUT.exists():
    for row in OUT.read_text(encoding="utf-8").splitlines():
        r = json.loads(row)
        done.add((r["subject"], r["language"], r["model"]))
out = OUT.open("a", encoding="utf-8")
for subject, source in SUBJECTS.items():
    status, brief = api("GET", f"/briefs/{source}")
    assert status == 200, brief
    for language in LANGUAGES:
        for model in MODELS:
            if (subject, language, model) in done:
                continue
            body = {
                "title": f"[LANG1] {language} {model} — {brief['title']}",
                "item_ids": [i["id"] for i in brief["items"]],
                "context_ids": [i["id"] for i in brief["items"] if i.get("context")],
                "angle": brief["angle"], "instructions": brief["instructions"],
                "length": "medium", "mode": brief["mode"], "nature": brief["nature"],
                "language": language, "provider_id": PROVIDER, "model": model,
                "conversation_id": brief.get("conversation_id"),
            }
            status, copy = api("POST", "/briefs", body)
            if status != 201:
                print(subject, language, model, "brief", status, copy, flush=True)
                continue
            time.sleep(5)
            started = time.time()
            status, generation = api("POST", f"/briefs/{copy['id']}/generations", {"force": True})
            got = {}
            stopped = False
            while status == 202:
                _, got = api("GET", f"/generations/{generation['id']}")
                if got["status"] != "running":
                    break
                if time.time() - started > LIMIT:
                    api("DELETE", f"/briefs/{copy['id']}/generations/running")
                    stopped = True
                    break
                time.sleep(20)
            _, draft = api("GET", f"/briefs/{copy['id']}/draft")
            line = {
                "subject": subject, "language": language, "model": model, "brief": copy["id"],
                "status": "stopped" if stopped else got.get("status"), "error": got.get("error"),
                "seconds": round(time.time() - started), "details": got.get("details"),
                "article": None if stopped else (draft or {}).get("article"),
            }
            out.write(json.dumps(line, ensure_ascii=False) + chr(10))
            out.flush()
            done.add((subject, language, model))
            print(len(done), subject, language, model, line["status"], line["seconds"], flush=True)
            time.sleep(30)
print("finished", flush=True)
