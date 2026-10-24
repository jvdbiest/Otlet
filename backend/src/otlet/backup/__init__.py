# SPDX-License-Identifier: AGPL-3.0-or-later
"""Backups of the instance (F08, ADR-0042): complete and consistent copies (the database, the
files of the médiathèque, a manifest, the secrets when encrypted) in a folder chosen at
installation; a full restore that never runs without a backup taken just before."""
