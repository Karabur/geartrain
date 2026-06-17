"""External service integrations (GitHub, …).

Each integration wraps a service API behind a small client with an injectable
transport, so workflows and tests run offline against a fake.
"""

from geartrain.integrations.github import (
    GitHubClient,
    GitHubError,
    GitHubResponse,
    github_client_from_config,
    resolve_github_token,
)

__all__ = [
    "GitHubClient",
    "GitHubError",
    "GitHubResponse",
    "github_client_from_config",
    "resolve_github_token",
]
