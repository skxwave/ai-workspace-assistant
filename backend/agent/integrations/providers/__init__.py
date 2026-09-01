from ..registry import IntegrationRegistry
from .github import github_provider

PROVIDERS = (github_provider,)


def register_all(registry: IntegrationRegistry) -> None:
    for provider in PROVIDERS:
        registry.register(provider)


__all__ = ["PROVIDERS", "github_provider", "register_all"]
