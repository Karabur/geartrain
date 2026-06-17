"""Resolve ``${a.b.c}`` references in prompts against config namespaces.

A reference walks dotted keys through a namespace mapping where each top-level
key (``workspace``, ``engine``, ``memory``, ``workflow``) holds either a dict or
a Pydantic model. Every reference must resolve — an unknown one raises rather
than passing a literal ``${...}`` through to the LLM.
"""

from __future__ import annotations

import re
from typing import Any

_REFERENCE = re.compile(r"\$\{([^}]+)\}")
_MISSING = object()


class InterpolationError(Exception):
    """Raised when a ``${...}`` reference can't be resolved."""


def interpolate(template: str, namespaces: dict[str, Any]) -> str:
    """Replace every ``${path}`` in *template* with its resolved value.

    Raises ``InterpolationError`` on the first reference that doesn't resolve.
    """

    def _replace(match: re.Match[str]) -> str:
        path = match.group(1).strip()
        value = _lookup(path, namespaces)
        if value is _MISSING:
            raise InterpolationError(
                f"unresolved reference ${{{path}}} — "
                f"no such value in {sorted(namespaces)}"
            )
        return str(value)

    return _REFERENCE.sub(_replace, template)


def _lookup(path: str, namespaces: dict[str, Any]) -> Any:
    """Walk a dotted path through dicts and objects; return ``_MISSING`` if absent."""
    current: Any = namespaces
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return _MISSING
            current = current[part]
        else:
            if not hasattr(current, part):
                return _MISSING
            current = getattr(current, part)
    return current
