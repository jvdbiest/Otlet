-- SPDX-License-Identifier: AGPL-3.0-or-later
-- S1: minimal schema covering the five reads of docs/spikes/S1.md §3.2. Throw-away: the
-- product schema is written in É1 by the modules, with Alembic.
-- Run by the migration role (member of otlet_owner) after `SET ROLE otlet_owner`, on a
-- database provisioned by otlet.platform.roles (extensions vector, pg_trgm, unaccent).

SET ROLE otlet_owner;

DROP TABLE IF EXISTS article_sources, articles, passages, items, sources, workspaces CASCADE;

CREATE TABLE workspaces (
    id   uuid PRIMARY KEY DEFAULT uuidv7(),
    name text NOT NULL
);

CREATE TABLE sources (
    workspace_id uuid NOT NULL REFERENCES workspaces,
    id           uuid NOT NULL DEFAULT uuidv7(),
    name         text NOT NULL,
    url          text NOT NULL,
    PRIMARY KEY (workspace_id, id)
);

CREATE TABLE items (
    workspace_id uuid        NOT NULL,
    id           uuid        NOT NULL DEFAULT uuidv7(),
    source_id    uuid        NOT NULL,
    title        text        NOT NULL,
    body         text        NOT NULL,
    language     text        NOT NULL,
    published_at timestamptz NOT NULL,
    score        real        NOT NULL,
    triage_state text        NOT NULL,
    search       tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('french', title), 'A') || setweight(to_tsvector('french', body), 'B')
    ) STORED,
    PRIMARY KEY (workspace_id, id),
    FOREIGN KEY (workspace_id, source_id) REFERENCES sources
);
-- L1 (triage feed): untriaged items of a workspace over the last days.
CREATE INDEX items_triage ON items (workspace_id, triage_state, published_at DESC);
-- L2 (full-text search).
CREATE INDEX items_search ON items USING gin (search);
CREATE INDEX items_published ON items (workspace_id, published_at DESC);

CREATE TABLE passages (
    workspace_id uuid          NOT NULL,
    id           uuid          NOT NULL DEFAULT uuidv7(),
    item_id      uuid          NOT NULL,
    position     smallint      NOT NULL,
    embedding    halfvec(384)  NOT NULL,
    PRIMARY KEY (workspace_id, id),
    FOREIGN KEY (workspace_id, item_id) REFERENCES items
);
-- L3 (vector search): built after loading, by the generator (faster than incremental).

CREATE TABLE articles (
    workspace_id uuid        NOT NULL REFERENCES workspaces,
    id           uuid        NOT NULL DEFAULT uuidv7(),
    title        text        NOT NULL,
    state        text        NOT NULL,
    body         jsonb       NOT NULL,
    created_at   timestamptz NOT NULL,
    updated_at   timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, id)
);
-- L4 (library).
CREATE INDEX articles_library ON articles (workspace_id, state, updated_at DESC);

CREATE TABLE article_sources (
    workspace_id uuid NOT NULL,
    article_id   uuid NOT NULL,
    item_id      uuid NOT NULL,
    PRIMARY KEY (workspace_id, article_id, item_id),
    FOREIGN KEY (workspace_id, article_id) REFERENCES articles,
    FOREIGN KEY (workspace_id, item_id) REFERENCES items
);

-- Row-level security, forced (M-12): without app.workspace_id, the setting is NULL, or empty
-- once a transaction-local value has been reset (hence NULLIF), and no row
-- passes. The application role gets its privileges from the default privileges of the owner.
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['sources', 'items', 'passages', 'articles', 'article_sources'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY workspace_isolation ON %I'
            ' USING (workspace_id = NULLIF(current_setting(''app.workspace_id'', true), '''')::uuid)'
            ' WITH CHECK (workspace_id = NULLIF(current_setting(''app.workspace_id'', true), '''')::uuid)', t);
    END LOOP;
END
$$;
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace_isolation ON workspaces
    USING (id = NULLIF(current_setting('app.workspace_id', true), '')::uuid)
    WITH CHECK (id = NULLIF(current_setting('app.workspace_id', true), '')::uuid);

RESET ROLE;
