"""Load and validate the privacy policy YAML.

Pure Python, no rclpy dependency. A malformed policy raises PolicyError so
that callers fail closed: no policy means no capability is ever allowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

ALLOWED_RETENTION = frozenset({"not_stored", "interaction_only", "session_only"})


class PolicyError(Exception):
    """Raised when a policy file is missing, unreadable or invalid."""


@dataclass(frozen=True)
class CapabilityPolicy:
    capability_id: str
    sensor: str
    purpose: str
    prompt: str
    retention: str
    expiry_seconds: int
    refusal_fallback: str
    required: bool = False


@dataclass(frozen=True)
class Policy:
    version: str
    capabilities: Mapping[str, CapabilityPolicy]

    def get(self, capability_id: str) -> CapabilityPolicy | None:
        return self.capabilities.get(capability_id)

    def __contains__(self, capability_id: str) -> bool:
        return capability_id in self.capabilities


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys instead of silently
    keeping the last one."""


def _construct_mapping(loader, node, deep=False):
    keys = [loader.construct_object(key_node, deep=deep)
            for key_node, _ in node.value]
    duplicates = {k for k in keys if keys.count(k) > 1}
    if duplicates:
        raise PolicyError(f"duplicate keys in policy: {sorted(duplicates)}")
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def _require_string(raw: Mapping, key: str, capability_id: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(
            f"capability '{capability_id}': '{key}' must be a non-empty string")
    return value.strip()


def _parse_capability(capability_id, raw: object) -> CapabilityPolicy:
    if not isinstance(capability_id, str) or not capability_id.strip():
        raise PolicyError(f"invalid capability identifier: {capability_id!r}")
    capability_id = capability_id.strip()
    if not isinstance(raw, Mapping):
        raise PolicyError(f"capability '{capability_id}' must be a mapping")

    sensor = _require_string(raw, "sensor", capability_id)
    purpose = _require_string(raw, "purpose", capability_id)
    prompt = _require_string(raw, "prompt", capability_id)
    retention = _require_string(raw, "retention", capability_id)
    fallback = _require_string(raw, "refusal_fallback", capability_id)

    if retention not in ALLOWED_RETENTION:
        raise PolicyError(
            f"capability '{capability_id}': unknown retention '{retention}' "
            f"(allowed: {sorted(ALLOWED_RETENTION)})")

    expiry = raw.get("expiry_seconds")
    if isinstance(expiry, bool) or not isinstance(expiry, int) or expiry < 0:
        raise PolicyError(
            f"capability '{capability_id}': 'expiry_seconds' must be a "
            f"non-negative integer, got {expiry!r}")

    required = raw.get("required", False)
    if not isinstance(required, bool):
        raise PolicyError(
            f"capability '{capability_id}': 'required' must be a boolean")

    return CapabilityPolicy(
        capability_id=capability_id,
        sensor=sensor,
        purpose=purpose,
        prompt=prompt,
        retention=retention,
        expiry_seconds=expiry,
        refusal_fallback=fallback,
        required=required,
    )


def parse_policy(text: str) -> Policy:
    """Parse and validate a policy document from a YAML string."""
    try:
        data = yaml.load(text, Loader=_StrictLoader)
    except PolicyError:
        raise
    except yaml.YAMLError as exc:
        raise PolicyError(f"invalid YAML: {exc}") from exc

    if not isinstance(data, Mapping):
        raise PolicyError("policy root must be a mapping")

    version = data.get("policy_version")
    if not isinstance(version, str) or not version.strip():
        raise PolicyError("'policy_version' must be a non-empty string")

    raw_capabilities = data.get("capabilities")
    if not isinstance(raw_capabilities, Mapping) or not raw_capabilities:
        raise PolicyError("'capabilities' must be a non-empty mapping")

    capabilities = {}
    for capability_id, raw in raw_capabilities.items():
        parsed = _parse_capability(capability_id, raw)
        capabilities[parsed.capability_id] = parsed

    return Policy(version=version.strip(),
                  capabilities=MappingProxyType(capabilities))


def load_policy(path: str | Path) -> Policy:
    """Load and validate a policy file. Raises PolicyError on any problem."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PolicyError(f"cannot read policy file '{path}': {exc}") from exc
    return parse_policy(text)
