# SPDX-License-Identifier: AGPL-3.0-or-later
"""Start the API under Uvicorn."""

import uvicorn


def run(host: str, port: int, workers: int) -> None:
    uvicorn.run(
        "otlet.entrypoints.api.app:create_app_from_env",
        factory=True,
        host=host,
        port=port,
        workers=workers,
        proxy_headers=True,
        server_header=False,
    )
