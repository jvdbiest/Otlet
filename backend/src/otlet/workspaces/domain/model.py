# SPDX-License-Identifier: AGPL-3.0-or-later
"""Workspaces, roles and the context every workspace operation runs in."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

NAME_MAX_LENGTH = 200


class Role(StrEnum):
    """Roles of a member in a workspace (ARCHITECTURE §19.3); stored as their value."""

    OWNER = "owner"
    EDITOR = "editor"
    VALIDATOR = "validator"
    OBSERVER = "observer"


class WorkspaceError(Exception):
    """A workspace rule was not met; the message is safe to show."""


@dataclass(frozen=True, slots=True)
class Workspace:
    id: UUID
    name: str
    role: Role


@dataclass(frozen=True, slots=True)
class WorkspaceContext:
    """Who acts, and in which workspace. Built only after the membership has been checked, so
    holding one means the user belongs to the workspace."""

    user_id: UUID
    workspace_id: UUID
    role: Role


def check_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not 1 <= len(cleaned) <= NAME_MAX_LENGTH:
        raise WorkspaceError(f"a workspace name has 1 to {NAME_MAX_LENGTH} characters")
    return cleaned
