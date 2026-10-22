"""Provider registry."""

from __future__ import annotations

from ..exceptions import ProviderNotSupported
from .base import BaseProvider
from .toapis import ToApisProvider
from .kling import KlingProvider
from .minimax import MiniMaxProvider
from .seedance import SeedanceProvider
from .wan import WanProvider

PROVIDERS: dict[str, type[BaseProvider]] = {
    "toapis": ToApisProvider,
    "seedance": SeedanceProvider,
    "kling": KlingProvider,
    "minimax": MiniMaxProvider,
    "wan": WanProvider,
}


def get_provider_class(name: str) -> type[BaseProvider]:
    try:
        return PROVIDERS[name.lower()]
    except KeyError:
        raise ProviderNotSupported(
            f"Unknown provider '{name}'. Available: {sorted(PROVIDERS)}"
        ) from None
