from collections.abc import Iterator

from .base import IntegrationProvider


class IntegrationRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, IntegrationProvider] = {}

    def register(self, provider: IntegrationProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"Integration already registered: {provider.name}")
        self._providers[provider.name] = provider

    def get(self, name: str) -> IntegrationProvider:
        try:
            return self._providers[name]
        except KeyError:
            raise KeyError(f"Unknown integration: {name}") from None

    def has(self, name: str) -> bool:
        return name in self._providers

    def names(self) -> frozenset[str]:
        return frozenset(self._providers)

    def __iter__(self) -> Iterator[IntegrationProvider]:
        return iter(self._providers.values())

    def __len__(self) -> int:
        return len(self._providers)


integration_registry = IntegrationRegistry()
