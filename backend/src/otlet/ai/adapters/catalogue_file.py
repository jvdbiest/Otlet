# SPDX-License-Identifier: AGPL-3.0-or-later
"""The catalogue of models, read from the versioned data file of the module."""

import json
from importlib import resources

from otlet.ai.domain.model import Catalogue


class PackagedCatalogue:
    def load(self) -> Catalogue:
        text = resources.files("otlet.ai").joinpath("catalogue.json").read_text(encoding="utf-8")
        return Catalogue.of(json.loads(text))
