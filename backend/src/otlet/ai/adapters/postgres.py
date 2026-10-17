# SPDX-License-Identifier: AGPL-3.0-or-later
"""The AI settings on PostgreSQL: the providers and profile of each user under row-level
security (user scope), and the policy of the instance in instance_settings."""

import json
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from otlet.ai.domain.settings import (
    InstancePolicy,
    Profile,
    ProfileEntry,
    Provider,
    SettingsError,
)
from otlet.platform.database import scoped_transaction

POLICY_KEY = "ai:policy"
PROVIDER_COLUMNS = "id, user_id, name, kind, endpoint, key_hint, created_at"
OWN = "user_id = :user"  # explicit, beside the policy (M-12)


def _provider(row: sa.Row[Any]) -> Provider:
    return Provider(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        kind=row.kind,
        endpoint=row.endpoint,
        key_hint=row.key_hint,
        created_at=row.created_at,
    )


class PostgresAiSettings:
    def __init__(self, engine: sa.Engine) -> None:
        self._engine = engine

    def list_providers(self, user_id: UUID) -> list[Provider]:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            rows = connection.execute(
                sa.text(f"SELECT {PROVIDER_COLUMNS} FROM ai_providers WHERE {OWN} ORDER BY name"),
                {"user": user_id},
            ).all()
        return [_provider(row) for row in rows]

    def add_provider(
        self,
        user_id: UUID,
        provider_id: UUID,
        *,
        name: str,
        kind: str,
        endpoint: str,
        sealed_key: bytes | None,
        key_hint: str | None,
    ) -> Provider:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            row = connection.execute(
                sa.text(
                    "INSERT INTO ai_providers (id, user_id, name, kind, endpoint, api_key_sealed,"
                    " key_hint) VALUES (:id, :user, :name, :kind, :endpoint, :sealed, :hint)"
                    f" ON CONFLICT (user_id, name) DO NOTHING RETURNING {PROVIDER_COLUMNS}"
                ),
                {
                    "id": provider_id,
                    "user": user_id,
                    "name": name,
                    "kind": kind,
                    "endpoint": endpoint,
                    "sealed": sealed_key,
                    "hint": key_hint,
                },
            ).one_or_none()
        if row is None:
            raise SettingsError("name_taken", "a provider already has this name")
        return _provider(row)

    def update_provider(
        self,
        user_id: UUID,
        provider_id: UUID,
        *,
        name: str,
        endpoint: str,
        sealed_key: bytes | None,
        key_hint: str | None,
        replace_key: bool,
    ) -> Provider | None:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            try:
                with connection.begin_nested():
                    row = connection.execute(
                        sa.text(
                            "UPDATE ai_providers SET name = :name, endpoint = :endpoint,"
                            " api_key_sealed = CASE WHEN :replace THEN :sealed"
                            "   ELSE api_key_sealed END,"
                            " key_hint = CASE WHEN :replace THEN :hint ELSE key_hint END"
                            f" WHERE id = :id AND {OWN} RETURNING {PROVIDER_COLUMNS}"
                        ),
                        {
                            "id": provider_id,
                            "user": user_id,
                            "name": name,
                            "endpoint": endpoint,
                            "sealed": sealed_key,
                            "hint": key_hint,
                            "replace": replace_key,
                        },
                    ).one_or_none()
            except sa.exc.IntegrityError as error:
                raise SettingsError("name_taken", "a provider already has this name") from error
        return None if row is None else _provider(row)

    def delete_provider(self, user_id: UUID, provider_id: UUID) -> bool:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            deleted = connection.execute(
                sa.text(f"DELETE FROM ai_providers WHERE id = :id AND {OWN} RETURNING id"),
                {"id": provider_id, "user": user_id},
            ).one_or_none()
        return deleted is not None

    def profile(self, user_id: UUID) -> Profile:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            rows = connection.execute(
                sa.text(
                    f"SELECT provider_id, model FROM ai_profile_entries WHERE {OWN}"
                    " ORDER BY position"
                ),
                {"user": user_id},
            ).all()
        return Profile(tuple(ProfileEntry(row.provider_id, row.model) for row in rows))

    def save_profile(self, user_id: UUID, profile: Profile) -> None:
        with scoped_transaction(self._engine, user_id=user_id) as connection:
            connection.execute(
                sa.text(f"DELETE FROM ai_profile_entries WHERE {OWN}"), {"user": user_id}
            )
            for position, entry in enumerate(profile.entries):
                connection.execute(
                    sa.text(
                        "INSERT INTO ai_profile_entries (user_id, position, provider_id, model)"
                        " VALUES (:user, :position, :provider, :model)"
                    ),
                    {
                        "user": user_id,
                        "position": position,
                        "provider": entry.provider_id,
                        "model": entry.model,
                    },
                )

    def policy(self) -> InstancePolicy:
        with self._engine.connect() as connection:
            value = connection.execute(
                sa.text("SELECT value FROM instance_settings WHERE key = :key"),
                {"key": POLICY_KEY},
            ).scalar()
        if value is None:
            return InstancePolicy()
        return InstancePolicy(
            allowed_paid=frozenset(value.get("allowed_paid", [])),
            local_networks=tuple(value.get("local_networks", [])),
            local_ports=tuple(value.get("local_ports", [])),
        )

    def save_policy(self, policy: InstancePolicy) -> None:
        value = {
            "allowed_paid": sorted(policy.allowed_paid),
            "local_networks": list(policy.local_networks),
            "local_ports": list(policy.local_ports),
        }
        with self._engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO instance_settings (key, value)"
                    " VALUES (:key, CAST(:value AS jsonb))"
                    " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()"
                ),
                {"key": POLICY_KEY, "value": json.dumps(value)},
            )
