# SPDX-License-Identifier: AGPL-3.0-or-later
"""The images of a workspace on a real PostgreSQL (X03b): imported, read back, never by another
workspace; an article may show only the images of its workspace."""

import io
from pathlib import Path
from typing import Literal
from uuid import UUID

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
from otlet.media.domain.media import MAX_BYTES, Description, MediaError
from otlet.platform import database as db
from otlet.workspaces.adapters.postgres import PostgresWorkspaceStore
from otlet.workspaces.application.workspaces import Workspaces
from otlet.writing.adapters.articles_postgres import PostgresArticleStore

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


def test_the_mediatheque_shows_two_views_of_the_same_images(
    migrated: TestDatabase, tmp_path: Path
) -> None:
    """ADR-0040: one image, two views; described; deleted only while no article shows it."""
    engine = db.create_engine(migrated.app_url)
    auth = Authentication(PostgresIdentityStore(engine), Argon2Hasher())
    workspaces = Workspaces(PostgresWorkspaceStore(engine))
    user = auth.create_user("carla@example.org", "Carla", "une phrase de passe assez longue")
    context = workspaces.enter(user, workspaces.create(user, "Carla").id)
    assert context is not None
    articles = PostgresArticleStore(engine, lambda connection, name, **kwargs: 0)
    library = MediaLibrary(
        PostgresMediaStore(engine), DiskFiles(tmp_path), PillowImages(), articles
    )
    pasted = library.import_image(context, png())
    kept = library.import_image(context, png(), "  Carte   du circuit ", bank=True)
    assert (pasted.origin, pasted.in_bank) == ("editor", False)
    assert (kept.origin, kept.in_bank, kept.name) == ("library", True, "Carte du circuit")
    thumbnail = library.thumbnail(context, kept.id)
    assert thumbnail is not None and thumbnail[8:12] == b"WEBP"
    # The article shows the pasted image, in its first version.
    document = {
        "type": "doc",
        "attrs": {"version_schema": 1, "langue": "fr", "sources": []},
        "content": [{"type": "image", "attrs": {"id": "b1", "media": str(pasted.id)}}],
    }
    article = articles.create_article(context.workspace_id, context.user_id, "Billet", document)

    def ids(
        view: Literal["articles", "bank"], query: str = "", used: bool | None = None
    ) -> list[UUID]:
        return [e.media.id for e in library.entries(context, view, query, used)]

    assert ids("articles") == [pasted.id]  # the bank's own image is used by no article
    assert ids("bank") == [kept.id]
    assert ids("articles", used=True) == [pasted.id]
    (usage,) = library.usages(context, pasted.id)
    assert (usage.article_id, usage.title, usage.versions) == (article, "Billet", (1,))
    # Added to the bank, it stays where it is: in both views.
    assert library.keep_many(context, [pasted.id], True).done == (pasted.id,)
    assert set(ids("bank")) == {pasted.id, kept.id} and ids("articles") == [pasted.id]
    described = library.describe(
        context, kept.id, Description("Carte", " Le tracé ", "Otlet", "CC BY 4.0", "")
    )
    assert described is not None and (described.description, described.source_url) == (
        "Le tracé",
        None,
    )
    assert ids("bank", query="tracé") == [kept.id]
    # Tags (lot 2): cleaned, listed, filtered on, searched.
    tagged = library.set_tags(context, kept.id, [" Circuits ", "circuits", "Cartes", ""])
    assert tagged is not None and tagged.tags == ("Circuits", "Cartes")
    assert library.tags(context) == ["Cartes", "Circuits"]
    assert [e.media.id for e in library.entries(context, "bank", tag="Cartes")] == [kept.id]
    assert library.entries(context, "bank", tag="Autre") == []
    assert ids("bank", query="circuits") == [kept.id]
    with pytest.raises(MediaError):
        library.set_tags(context, kept.id, ["x" * 41])
    with pytest.raises(MediaError) as error:
        library.describe(context, kept.id, Description(None, None, None, None, "ftp://x"))
    assert error.value.code == "invalid_url"
    # Shown by an article: refused; free: deleted.
    outcome = library.delete_many(context, [pasted.id, kept.id])
    assert outcome.done == (kept.id,) and outcome.failed == ((pasted.id, "in_use"),)
    assert library.read(context, kept.id) is None
