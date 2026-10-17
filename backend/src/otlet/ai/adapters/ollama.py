# SPDX-License-Identifier: AGPL-3.0-or-later
"""The native API of Ollama: the models installed, and downloading one (F05b).

The address of the provider is the one of its OpenAI-compatible API (`…/v1`); the native API is
at the root of the same server. Every connection goes through the guarded client: the engine
must be on a network and a port the administrator allowed, as for the calls of the gateway.
"""

import json
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

import httpx2

from otlet.ai.adapters.providers import address_policy
from otlet.ai.application.models import InstalledModel
from otlet.ai.domain.model import AiError
from otlet.ai.domain.settings import InstancePolicy
from otlet.platform.http import BlockedAddressError
from otlet.platform.sdk_http import guarded_sdk_client, refused

LIST_TIMEOUT = 10.0
# Between two lines of progress: the engine checks the files it downloaded without saying a word.
PULL_TIMEOUT = 180.0
PROGRESS_EVERY = 1.0  # seconds


def root(endpoint: str) -> str:
    parts = urlsplit(endpoint)
    return f"{parts.scheme}://{parts.netloc}"


def _unavailable(error: Exception) -> AiError:
    if refused(error):
        return AiError("unavailable", "address_not_allowed")
    return AiError("unavailable", f"{type(error).__name__}")


class OllamaHost:
    def installed(self, endpoint: str, policy: InstancePolicy) -> list[InstalledModel]:
        try:
            with guarded_sdk_client(address_policy(policy), LIST_TIMEOUT) as client:
                response = client.get(f"{root(endpoint)}/api/tags")
            response.raise_for_status()
            found = response.json().get("models", [])
        except (httpx2.HTTPError, BlockedAddressError, ValueError, AttributeError) as error:
            raise _unavailable(error) from error
        return sorted(
            (InstalledModel(str(m["name"]), int(m.get("size", 0))) for m in found if "name" in m),
            key=lambda m: m.name.lower(),
        )

    def pull(
        self,
        endpoint: str,
        policy: InstancePolicy,
        model: str,
        progress: Callable[[str, int, int], None],
    ) -> None:
        layers: dict[str, tuple[int, int]] = {}  # digest → (completed, total)
        last = 0.0
        step = ""
        try:
            with (
                guarded_sdk_client(address_policy(policy), PULL_TIMEOUT) as client,
                client.stream(
                    "POST", f"{root(endpoint)}/api/pull", json={"model": model, "stream": True}
                ) as response,
            ):
                if response.status_code >= 400:
                    response.read()
                    raise AiError("refused", _error_text(response))
                for line in response.iter_lines():
                    if not line.strip():
                        continue
                    event: dict[str, Any] = json.loads(line)
                    if "error" in event:
                        raise AiError("refused", str(event["error"])[:200])
                    step = str(event.get("status", step))
                    digest = event.get("digest")
                    if digest and "total" in event:
                        layers[str(digest)] = (
                            int(event.get("completed", 0)),
                            int(event["total"]),
                        )
                    now = time.monotonic()
                    if now - last >= PROGRESS_EVERY or step == "success":
                        last = now
                        progress(
                            step,
                            sum(done for done, _ in layers.values()),
                            sum(total for _, total in layers.values()),
                        )
        except (httpx2.HTTPError, BlockedAddressError, ValueError) as error:
            raise _unavailable(error) from error
        if step != "success":
            raise AiError("unavailable", "the download ended before the engine said it was done")


def _error_text(response: httpx2.Response) -> str:
    try:
        return str(response.json().get("error", response.status_code))[:200]
    except (ValueError, AttributeError):
        return str(response.status_code)
