# SPDX-License-Identifier: AGPL-3.0-or-later
"""Process-wide logging setup. Structured JSON logs (structlog) come later (TECH_CHOICES §20)."""

import logging


def configure(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
