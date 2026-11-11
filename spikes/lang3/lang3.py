"""LANG3 (docs/spikes/LANG3.md): 5 subjects x FR/NL/EN briefs on sources in the three
languages; gemma4 set for each language through the language setting; one generation at a
time. The language setting of Joel is put back exactly. Resumable.
Run in the api container: python /data/lang3.py (with subjects.json beside it)"""

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


from otlet.ai.adapters.postgres import PostgresAiSettings  # noqa: E402
from otlet.ai.domain.settings import ProfileEntry  # noqa: E402

PROVIDER = UUID("8e985383-8ca8-4c82-99c3-b940039b2c14")  # « Modèles Locaux 2 », Ollama of Joël's PC
MODEL = "gemma4:latest"
LANGUAGES = ("fr", "nl", "en")
LIMIT = 40 * 60
SUBJECTS = json.loads(Path("/data/subjects.json").read_text(encoding="utf-8"))

store = PostgresAiSettings(engine)
ORIGINAL = store.language_models(USER)
OUT = Path("/data/lang3.jsonl")
done = set()
if OUT.exists():
    for row in OUT.read_text(encoding="utf-8").splitlines():
        r = json.loads(row)
        done.add((r["subject"], r["language"]))
out = OUT.open("a", encoding="utf-8")
try:
    store.save_language_models(USER, {lang: ProfileEntry(PROVIDER, MODEL) for lang in LANGUAGES})
    for subject, spec in SUBJECTS.items():
        for language in LANGUAGES:
            if (subject, language) in done:
                continue
            body = {
                "title": f"[TEST_LANG3] {language} — {spec['titles'][language]}",
                "item_ids": [i["id"] for i in spec["items"]],
                "angle": "", "instructions": "", "length": "medium", "mode": "synthesis",
                "nature": "news", "language": language,
            }
            status, copy = api("POST", "/briefs", body)
            if status != 201:
                print(subject, language, "brief", status, copy, flush=True)
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
            details = got.get("details") or {}
            line = {
                "subject": subject, "language": language, "brief": copy["id"],
                "status": "stopped" if stopped else got.get("status"), "error": got.get("error"),
                "seconds": round(time.time() - started), "details": details,
                "article": None if stopped else (draft or {}).get("article"),
            }
            out.write(json.dumps(line, ensure_ascii=False) + chr(10))
            out.flush()
            done.add((subject, language))
            versions = ((draft or {}).get("article") or {}).get("versions") or [{}]
            print(len(done), subject, language, line["status"],
                  (versions[-1].get("details") or {}).get("model_reason"),
                  (versions[-1].get("details") or {}).get("language_written"),
                  line["seconds"], flush=True)
            time.sleep(30)
finally:
    store.save_language_models(USER, ORIGINAL)
    assert store.language_models(USER) == ORIGINAL, "language setting not restored"
    print("language setting restored", flush=True)
print("finished", flush=True)
