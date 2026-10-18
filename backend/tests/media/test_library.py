# SPDX-License-Identifier: AGPL-3.0-or-later
"""The images of a workspace on a real PostgreSQL (X03b): imported, read back, never by another
workspace; an article may show only the images of its workspace."""

import io
from pathlib import Path

import pytest
from PIL import Image as PilImage

from integration_support import TestDatabase, requires_database
from otlet.identity.adapters.argon2_hasher import Argon2Hasher
from otlet.identity.adapters.postgres import PostgresIdentityStore
from otlet.identity.application.authentication import Authentication
from otlet.media.adapters.files_disk import DiskFiles
from otlet.media.adapters.images_pillow import PillowImages
from otlet.media.adapters.postgres import PostgresMediaStore
from otlet.media.application.library import MediaLibrary
from otlet.media.domain.media import MAX_BYTES, MediaError
from otlet.platform import database as db
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces

pytestmark = requires_database


def png() -> bytes:
    out = io.BytesIO()
    PilImage.new("RGB", (40, 30), (10, 120, 200)).save(out, "PNG")
    return out.getvalue()


def test_an_image_stays_in_its_workspace(migrated: TestDatabase, tmp_path: Path) -> None:
    engine = db.create_engine(migrated.app_url)
    auth = Authentication(PostgresIdentityStore(engine), Argon2Hasher())
    workspaces = Workspaces(PostgresWorkspaceStore(engine))
    contexts = []
    for email in ("alice@example.org", "bob@example.org"):
        user = auth.create_user(email, email, "une phrase de passe assez longue")
        context = workspaces.enter(user, workspaces.create(user, email).id)
        assert context is not None
        contexts.append(context)
    alice, bob = contexts
    library = MediaLibrary(PostgresMediaStore(engine), DiskFiles(tmp_path), PillowImages())
    media = library.import_image(alice, png())
    assert (media.mime, media.width, media.height) == ("image/png", 40, 30)
    found = library.read(alice, media.id)
    assert found is not None and found[1].startswith(b"\x89PNG")
    assert library.read(bob, media.id) is None
    assert library.existing(alice.workspace_id, [media.id]) == {media.id}
    assert library.existing(bob.workspace_id, [media.id]) == set()
    with pytest.raises(MediaError) as error:
        library.import_image(alice, b"x" * (MAX_BYTES + 1))
    assert error.value.code == "too_large"
