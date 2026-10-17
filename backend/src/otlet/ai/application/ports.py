# SPDX-License-Identifier: AGPL-3.0-or-later
"""What the gateway needs from the outside world (ADR-0027 §1)."""

from typing import Protocol

from otlet.ai.domain.model import Answer, Catalogue, Completion


class Adapter(Protocol):
    def complete(self, call: Completion) -> Answer:
        """One call to the provider, without any retry of its own: the gateway alone decides
        (ADR-0027 §4). Raises AiError with a kind the gateway acts on."""
        ...


class CatalogueSource(Protocol):
    def load(self) -> Catalogue: ...
