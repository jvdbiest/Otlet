# SPDX-License-Identifier: AGPL-3.0-or-later
"""Opens the sealed key of a provider, in the worker only (DR6): it needs the private key of
the instance, which only the worker container mounts. The API must never import this module
(import contract « secrets-worker-only »)."""

from pathlib import Path
from uuid import UUID

import sqlalchemy as sa

from otlet.ai.application.settings import key_context
from otlet.platform.database import scoped_transaction
from otlet.platform.secrets.opening import load_private_key, open_sealed


class SealedKeys:
    def __init__(self, engine: sa.Engine, private_key_file: Path | None) -> None:
        self._engine = engine
        self._private_key_file = private_key_file

    def open(self, user_id: UUID, provider_id: UUID) -> str | None:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            sealed = connection.execute(
                sa.text(
                    "SELECT api_key_sealed FROM ai_providers WHERE id = :id AND user_id = :user"
                ),
                {"id": provider_id, "user": user_id},
            ).scalar()
        if sealed is None:
            return None
        private_key = load_private_key(self._private_key_file)
        return open_sealed(private_key, bytes(sealed), key_context(provider_id)).decode()
