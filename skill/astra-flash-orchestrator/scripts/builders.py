#!/usr/bin/env python3
"""Named builder presets, their stable role ids, routes and binding locations.

One module owns this table so the installer, the doctor and the undo path cannot
disagree about which roles exist, which route a preset may pin, or where its
binding lives. Nothing here writes files, chooses a provider that the caller did
not name, or inspects the model catalog.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import re

from local_config import ROLE, SetupError, local_route_tag, require_route

# Bindings for named builders live beside the legacy routing.json, one file per
# role. The legacy file is deliberately a different name: an update to one builder
# must never be able to rewrite another role's pinned route.
BUILDERS_DIRNAME = "builders"
LEGACY_BINDING_NAME = "routing.json"

# A host agent name: lowercase, underscores, no slash, no space. Kept explicit so
# a future preset cannot introduce an id the host would reject.
ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


@dataclass(frozen=True)
class BuilderPreset:
    """One named builder: CLI key, native role id, label and route policy."""

    key: str
    role: str
    label: str
    default_route: str | None
    allowed_routes: tuple[str, ...] = ()
    allow_local: bool = False

    def allows(self, route: str) -> bool:
        """True when this preset may pin the route, ignoring catalog state."""
        if route in self.allowed_routes:
            return True
        return self.allow_local and local_route_tag(route) is not None

    def allowed_text(self) -> str:
        if self.allowed_routes:
            return ", ".join(self.allowed_routes)
        return "a configured local/<ollama-tag> route"


# The requested labels are the operator-facing names. DeepSeek V4.1 Flash stays the
# default builder of the package, but only as a preset: nothing here is selected
# automatically and no preset is installed unless it is named on the command line.
PRESETS: dict[str, BuilderPreset] = {
    "grok": BuilderPreset(
        key="grok",
        role="astra_terra_builder_grok",
        label="Astra/Terra builder Grok",
        default_route="grok-oauth/grok-4.6",
        allowed_routes=("grok-oauth/grok-4.6", "grok-oauth/grok-4.5"),
    ),
    "fable": BuilderPreset(
        key="fable",
        role="astra_terra_builder_fable",
        label="Astra/Terra builder Fable",
        default_route="openrouter/claude-fable-5.1",
        allowed_routes=("openrouter/claude-fable-5.1",),
    ),
    "deepseek-flash": BuilderPreset(
        key="deepseek-flash",
        role="astra_terra_builder_deepseek_flash",
        label="Astra/Terra builder DeepSeek Flash",
        default_route="deepseek/deepseek-v4.1-flash",
        allowed_routes=("deepseek/deepseek-v4.1-flash",),
    ),
    "deepseek-pro": BuilderPreset(
        key="deepseek-pro",
        role="astra_terra_builder_deepseek_pro",
        label="Astra/Terra builder DeepSeek Pro",
        default_route="deepseek/deepseek-v4-pro",
        allowed_routes=("deepseek/deepseek-v4-pro",),
    ),
    "grok-4-5": BuilderPreset(
        key="grok-4-5",
        role="astra_terra_builder_grok_4_5",
        label="Astra/Terra builder Grok 4.5",
        default_route="grok-oauth/grok-4.5",
        allowed_routes=("grok-oauth/grok-4.5",),
    ),
    "ollama": BuilderPreset(
        key="ollama",
        role="astra_terra_builder_ollama",
        label="Astra/Terra builder Ollama (local)",
        default_route=None,
        allow_local=True,
    ),
}

KNOWN_ROLES = frozenset({ROLE, *(preset.role for preset in PRESETS.values())})


def preset(key: str) -> BuilderPreset:
    """Return the preset for a CLI key, or refuse it."""
    try:
        return PRESETS[key]
    except KeyError:
        raise SetupError(
            "Unknown builder preset. Choose one of: " + ", ".join(sorted(PRESETS))
        ) from None


def known_role(role: str) -> bool:
    """True when a role id is one this package is allowed to write or restore."""
    return role in KNOWN_ROLES and bool(ROLE_PATTERN.fullmatch(role))


def binding_path(skill_dir: Path, role: str) -> Path:
    """Path of a role's binding inside the installed skill."""
    return skill_dir / BUILDERS_DIRNAME / f"{role}.json"


def binding_role(relative: Path) -> str | None:
    """Known role named by a `builders/<role>.json` path, else None."""
    if len(relative.parts) != 2 or relative.parts[0] != BUILDERS_DIRNAME:
        return None
    if relative.suffix != ".json" or not known_role(relative.stem):
        return None
    return relative.stem


def read_binding(path: Path) -> str | None:
    """Return the route recorded in a builder binding, or None when it is absent.

    A missing file is a normal first install. Anything unreadable, oversized,
    symlinked or malformed is refused rather than treated as absent, so a damaged
    binding can never silently change the pinned route.
    """
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise SetupError("Refusing to read a builder binding through a symlink.")
    if not path.exists():
        return None
    try:
        if path.stat().st_size > 64_000:
            raise SetupError("A builder binding is unexpectedly large; inspect it locally.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        route = payload.get("worker_model") if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise SetupError(f"Cannot read the existing builder binding ({type(exc).__name__}).") from None
    if not isinstance(route, str):
        raise SetupError("The existing builder binding does not name a worker model.")
    return route


def resolve_builder_route(key: str, requested: str | None = None, binding: Path | None = None) -> str:
    """Resolve one preset's route: explicit request, then binding, then default.

    The result is always a reviewed route this preset is allowed to pin. Nothing
    here falls back to a different provider or preset.
    """
    spec = preset(key)
    route = requested
    if route is None and binding is not None:
        route = read_binding(binding)
    if route is None:
        route = spec.default_route
    if route is None:
        raise SetupError(
            f"The {spec.label} preset pins a local Ollama route, so the first installation must "
            f"name it: python3 -B install.py --builder {spec.key} --worker-route local/<ollama-tag>"
        )
    route = require_route(route)
    if not spec.allows(route):
        raise SetupError(
            f"The {spec.key} builder cannot pin {route}. Allowed for this preset: "
            f"{spec.allowed_text()}. No file was written."
        )
    return route


def role_description(spec: BuilderPreset, route: str) -> str:
    """Human-readable role description carrying the requested label."""
    return (
        f"{spec.label}: implement an approved task bundle on {route}; "
        "never orchestrate or self-approve."
    )


def binding_payload(report: dict, spec: BuilderPreset) -> dict:
    """The per-role binding recorded for one installed builder."""
    return {
        "builder": spec.key,
        "custom_agent": spec.role,
        "worker_model": report["worker_model"],
        "worker_provider": report["worker_provider"],
        "worker_route_family": report["worker_route_family"],
        "worker_effort": report["worker_effort"],
        "profile_inspected": report["profile_inspected"],
    }
