#!/usr/bin/env sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# Regenerates frontend/src/api/schema.ts, the TypeScript types of the API, from the OpenAPI
# specification of the back-end (TECH_CHOICES §6.5: the interface uses the public API only).
# Run it after changing a route; tests/entrypoints/test_openapi.py fails until you do.
#
# Usage, from the repository root: sh tools/generate-api-types.sh
# Needs uv and Node.js 24. openapi-typescript runs through npx in its own environment: it asks
# for TypeScript 5, while the interface uses TypeScript 6.
set -eu

cd "$(dirname "$0")/.."
(cd backend && uv run otlet openapi) > frontend/src/api/openapi.json
npx --yes -p openapi-typescript@7.13.0 -p typescript@5.9.3 \
    openapi-typescript frontend/src/api/openapi.json -o frontend/src/api/schema.ts
