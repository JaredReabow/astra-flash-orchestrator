#!/usr/bin/env python3
"""Read-only inspection of an existing Codex Router setup; no model requests."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ is required. No packages or settings were changed.")
import tomllib

# The installed default. Existing bindings, docs and the published policy point
# at this slug, so it stays first and stays the fallback when no explicit route
# and no installed binding exist.
DEFAULT_ROUTE = "deepseek/deepseek-v4.1-flash"
ROUTE = DEFAULT_ROUTE

# Reviewed DeepSeek V4.1 Flash routes. These are the package's original
# provider set: cheap, tool-capable and the reason the role exists.
FLASH_ROUTES = {
    ROUTE: "DeepSeek API",
    "openrouter/deepseek-v4.1-flash": "OpenRouter",
    "opencode-go/deepseek-v4.1-flash": "opencode Go",
    "commandcode/deepseek-v4.1-flash": "Command Code",
    "nousresearch/deepseek-v4.1-flash": "Nous Research",
    "ollama-cloud/deepseek-v4.1-flash": "Ollama Cloud",
}

# Additional reviewed worker routes an operator may pin explicitly. Nothing here
# is selected automatically: a route is used only when it is named with
# --worker-route or already recorded in a valid installed routing binding.
# Provider labels match the Router's own provider configuration.
MULTI_MODEL_ROUTES = {
    "deepseek/deepseek-v4-pro": "DeepSeek API",
    "grok-oauth/grok-4.6": "xAI Grok OAuth",
    "grok-oauth/grok-4.5": "xAI Grok OAuth",
    "openrouter/claude-fable-5.1": "OpenRouter",
}

SUPPORTED_ROUTES = {**FLASH_ROUTES, **MULTI_MODEL_ROUTES}

# Local Ollama routes are dynamic: the Router publishes one slug per model the
# operator has enabled, as `local/<ollama-tag>`. The tag grammar below is the
# Router's own (src/local-model-ref.mjs), so a route this package accepts is a
# route the Router could have produced. Membership is still decided by the live
# catalog, never by the shape alone.
LOCAL_ROUTE_PREFIX = "local/"
LOCAL_ROUTE_PROVIDER = "Local (Ollama)"
LOCAL_TAG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*(?::[A-Za-z0-9][A-Za-z0-9._-]*)?$")

# Ollama's cloud aliases are captured in the Router's local-model manifest with
# `codex: "cloud-only"` and `downloadable: false`: the plain `<model>:cloud`
# alias and the sized `<model>:<size>b-cloud` variant. They are served by
# Ollama's cloud and have no weights on this machine, so a `local/` slug must
# never carry one. A prefix is a namespace, not proof of where inference runs.
LOCAL_CLOUD_VARIANT = "cloud"
LOCAL_CLOUD_VARIANT_SUFFIX = "-cloud"

ROLE = "astra_flash_builder"
SKILL = "astra-flash-orchestrator"


def _local_route_candidate(route: str) -> str | None:
    """Return the tag text of anything shaped like a local route, cloud included."""
    if not route.startswith(LOCAL_ROUTE_PREFIX):
        return None
    tag = route[len(LOCAL_ROUTE_PREFIX):]
    if not tag or "//" in tag or not LOCAL_TAG_PATTERN.fullmatch(tag):
        return None
    return tag


def local_route_cloud_variant(route: str) -> str | None:
    """Return the Ollama cloud variant a local-shaped route names, if any."""
    tag = _local_route_candidate(route)
    if tag is None or ":" not in tag:
        return None
    variant = tag.rsplit(":", 1)[1]
    if variant == LOCAL_CLOUD_VARIANT or variant.endswith(LOCAL_CLOUD_VARIANT_SUFFIX):
        return variant
    return None


def local_route_tag(route: str) -> str | None:
    """Return a local-namespace tag after excluding known cloud aliases."""
    tag = _local_route_candidate(route)
    if tag is None or local_route_cloud_variant(route) is not None:
        return None
    return tag


def route_provider(route: str) -> str | None:
    """Return the provider label for a route, or None when it is not reviewed."""
    if route in SUPPORTED_ROUTES:
        return SUPPORTED_ROUTES[route]
    if local_route_tag(route) is not None:
        return LOCAL_ROUTE_PROVIDER
    return None


def route_family(route: str) -> str | None:
    """Classify a route for reporting: flash, cloud, or local."""
    if route in FLASH_ROUTES:
        return "flash"
    if route in SUPPORTED_ROUTES:
        return "cloud"
    if local_route_tag(route) is not None:
        return "local"
    return None


def route_hint() -> str:
    """Human-readable list of route names this package accepts."""
    return ", ".join(SUPPORTED_ROUTES) + ", or a configured local/<ollama-tag>"


def require_route(route: object) -> str:
    """Return a reviewed route unchanged, or refuse it without guessing."""
    if isinstance(route, str):
        variant = local_route_cloud_variant(route)
        if variant is not None:
            raise SetupError(
                f"The local route {route} names an Ollama cloud alias ({variant}). Those models "
                "run through Ollama's cloud service rather than on this machine, so they cannot be "
                "pinned as a local worker route. Use the Router's ollama-cloud provider route for "
                "that model instead."
            )
    if not isinstance(route, str) or route_provider(route) is None:
        raise SetupError(
            "Unsupported worker route. Choose one reviewed route explicitly: " + route_hint()
        )
    return route

# Keys Codex reads as scalar settings directly under [agents]. Every other key
# there is read as an agent NAME whose value must be a role table, so a scalar
# under an unrecognized name makes Codex reject the entire config with
# "invalid type: ..., expected struct AgentRoleToml in `agents`" -- which takes
# down the host app and the CLI together, not just subagent routing.
AGENT_SCALAR_SETTINGS = frozenset({
    "enabled",
    "default_subagent_model",
    "default_subagent_reasoning_effort",
    "interrupt_message",
    "max_concurrent_threads_per_session",
    "max_threads",
    "max_depth",
    "job_max_runtime_seconds",
})


class SetupError(ValueError):
    """An actionable configuration problem, without credential-bearing details."""


def read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        # TOML errors can embed source text. Never echo them or a full config.
        raise SetupError(f"Cannot read valid TOML from {path.name} ({type(exc).__name__}).") from None


def merge_tables(base: dict, overlay: dict) -> dict:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_tables(result[key], value)
        else:
            result[key] = value
    return result


def resolve_path(value: str, home: Path, codex_home: Path) -> Path:
    value = value.replace("${CODEX_HOME}", str(codex_home)).replace("$CODEX_HOME", str(codex_home))
    value = value.replace("${HOME}", str(home)).replace("$HOME", str(home))
    if value == "~":
        value = str(home)
    elif value.startswith("~/"):
        value = str(home / value[2:])
    path = Path(value)
    return path if path.is_absolute() else codex_home / path


def model_entries(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("models", "data"):
            if isinstance(payload.get(key), list):
                return model_entries(payload[key])
    raise SetupError("Unrecognized model catalog structure; inspect it locally before installing.")


def model_id(entry: dict) -> str | None:
    return entry.get("slug") or entry.get("id")


def resolve_worker_route(requested: str | None = None, binding: Path | None = None) -> str:
    """Validate an explicit route or reuse this package's existing routing binding.

    An explicit request always wins. Otherwise a valid installed binding is
    reused; with neither, the installed default is returned. Nothing here
    discovers or substitutes a provider that the caller did not name.
    """
    if requested is not None:
        route = requested
    elif binding is None:
        route = ROUTE
    else:
        if any(item.is_symlink() for item in (binding, *binding.parents)):
            raise SetupError("Refusing to read a worker route through a symlinked routing binding.")
        if not binding.exists():
            return ROUTE
        try:
            if binding.stat().st_size > 64_000:
                raise SetupError("The existing routing binding is unexpectedly large; inspect it locally.")
            payload = json.loads(binding.read_text(encoding="utf-8"))
            route = payload.get("worker_model") if isinstance(payload, dict) else None
        except (OSError, json.JSONDecodeError, UnicodeError) as exc:
            raise SetupError(f"Cannot read the existing routing binding ({type(exc).__name__}).") from None
        if not isinstance(route, str):
            raise SetupError("The existing routing binding does not name a worker model.")
    return require_route(route)


def inspect(
    home: Path,
    codex_home: Path,
    profile: str | None = None,
    worker_route: str = ROUTE,
    role: str = ROLE,
    builder: str | None = None,
) -> tuple[dict, str]:
    """Return a redacted static report and a PRIVATE local URL. Do not print URL.

    `role` is the native agent the report describes: the legacy default, or one
    named builder the caller already chose. `builder` records that preset in the
    report for the doctor and the binding; it never selects anything here.
    """
    worker_route = resolve_worker_route(worker_route)
    config_path = codex_home / "config.toml"
    config = read_toml(config_path)
    input_hashes = {str(config_path): hashlib.sha256(config_path.read_bytes()).hexdigest()}
    selected = profile if profile is not None else config.get("profile")
    warnings: list[str] = []
    if selected:
        if not isinstance(selected, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", selected):
            raise SetupError("Unsupported profile name; inspect the active profile manually.")
        standalone = codex_home / f"{selected}.config.toml"
        legacy = config.get("profiles", {}).get(selected)
        if standalone.exists() and legacy is not None:
            raise SetupError("Both standalone and legacy profile definitions exist; resolve that ambiguity first.")
        if standalone.exists():
            config = merge_tables(config, read_toml(standalone))
            input_hashes[str(standalone)] = hashlib.sha256(standalone.read_bytes()).hexdigest()
        elif isinstance(legacy, dict):
            config = merge_tables(config, legacy)
            warnings.append("A legacy inline profile was inspected; confirm your client still applies it.")
        else:
            raise SetupError("The selected profile is not available as a readable configuration file.")

    agents = config.get("agents", {})
    if not isinstance(agents, dict):
        raise SetupError("The existing [agents] setting is not a TOML table.")
    # Checking shape rather than a list of known top-level names catches any
    # absorbed key, not just the handful an installer happens to anticipate.
    misplaced = sorted(
        key for key, value in agents.items()
        if key not in AGENT_SCALAR_SETTINGS and not isinstance(value, dict)
    )
    if misplaced:
        raise SetupError(
            "Setting(s) that do not belong under [agents] were found there: "
            + ", ".join(misplaced)
            + ". In TOML, a table header remains active until the next table header, so a "
            "top-level key written after [agents] is absorbed into it; Codex then reads that "
            "key as an agent name and refuses to load the whole config. Move those keys above "
            "the first table header, or under the agent role they belong to, before installing. "
            "If your Codex build documents one of them as a genuine [agents] setting, it is newer "
            "than this check; verify with `codex doctor` rather than editing around this error."
        )
    if agents.get("enabled") is False:
        raise SetupError("Subagents are disabled in the inspected config. This installer will not enable them silently.")
    if "default_subagent_model" in agents:
        warnings.append(
            "The global default_subagent_model is not used or changed; the installed named role pins its own worker model."
        )
    # Retained from 1.2.0 for compatibility: this package's premise is an
    # orchestrator at the root delegating volume to a cheaper worker, so a Flash
    # root leaves nothing to save and the documented prerequisite is a non-Flash
    # root. That is the only root this check forbids. One model serving both roles
    # is allowed -- the saved default is not proof of what a running session uses,
    # and the same model can legally be the orchestrator for one task and the
    # delegated worker for another. Every root value is left exactly as configured.
    root_model = config.get("model")
    if isinstance(root_model, str) and root_model in FLASH_ROUTES:
        raise SetupError("The root model is Flash. Select your orchestrator model as root before installing this workflow.")
    if isinstance(root_model, str) and root_model and root_model == worker_route:
        warnings.append(
            f"The root model is also the selected worker route ({worker_route}). That is allowed and "
            "nothing here changes the root, but delegation will not change the model, so use a "
            "separate worker route when you expect a cost or quality difference."
        )

    catalog_value = config.get("model_catalog_json")
    if not isinstance(catalog_value, str) or not catalog_value:
        raise SetupError("No model_catalog_json was found. Confirm the existing Codex Router configuration.")
    catalog_path = resolve_path(catalog_value, home, codex_home)
    try:
        if catalog_path.stat().st_size > 20_000_000:
            raise SetupError("The model catalog is unexpectedly large; inspect it manually.")
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise SetupError(f"Cannot read the configured model catalog ({type(exc).__name__}).") from None
    matches = [entry for entry in model_entries(payload) if model_id(entry) == worker_route]
    if len(matches) != 1:
        raise SetupError(
            f"The selected worker route ({worker_route}) is missing or duplicated in the local catalog. "
            "Configure that exact route with the Router's own local setup, then rerun this installer. "
            "No provider was substituted."
        )
    entry = matches[0]
    if entry.get("multi_agent_version") != "v2":
        raise SetupError(
            f"The selected worker route ({worker_route}) exists in the catalog but is not "
            "advertised for native subagents "
            "(multi_agent_version must be v2). Select this exact route using your "
            "Router's documented subagent settings, republish the catalog, and fully "
            "quit/reopen the host app. Selection is not runtime verification. "
            "Do not run subagents certify, test-model --live, a smoke test, or another "
            "paid probe as part of this package's installation."
        )
    levels = entry.get("supported_reasoning_levels", [])
    supported = [x.get("effort") if isinstance(x, dict) else x for x in levels] if isinstance(levels, list) else []
    # The named role owns both worker settings. Do not couple installation to,
    # inherit, or encourage mutation of global defaults used by unrelated agents.
    effort = entry.get("default_reasoning_level")
    if effort is not None and (not isinstance(effort, str) or not re.fullmatch(r"[a-z_]+", effort)):
        raise SetupError("The worker reasoning effort is not a recognized string value.")
    if effort is not None and supported and effort not in supported:
        raise SetupError(
            f"The worker effort ({effort}) is not listed in the supported efforts for {worker_route} "
            "in the local catalog. Reconcile the route locally first."
        )
    if effort is None:
        warnings.append("No worker effort was pinned; use explicit model selection without an effort at spawn, then inspect the actual thread.")

    provider = config.get("model_provider", "openai")
    if provider == "openai":
        url = config.get("openai_base_url", "")
    else:
        url = config.get("model_providers", {}).get(provider, {}).get("base_url", "")
    try:
        parsed = urlsplit(url)
        loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        # Codex Router supports both native authenticated /v1 and capability paths.
        # Keep exact path shapes; never accept arbitrary loopback API paths.
        route_path = parsed.path.rstrip("/")
        recognized_path = route_path == "/v1" or bool(re.fullmatch(r"/_codex-router/[A-Za-z0-9_-]+/v1", route_path))
        valid = parsed.scheme in {"http", "https"} and loopback and recognized_path
        valid = valid and not parsed.query and not parsed.fragment
        valid = valid and not parsed.username and not parsed.password
        _ = parsed.port
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise SetupError("The inspected provider does not point at a recognized loopback Codex Router URL. URL withheld.")
    if not config.get("model"):
        warnings.append("No root model is set in this config; select GPT-6 Astra in the new session UI.")
    if config.get("features", {}).get("multi_agent") is False:
        warnings.append("A legacy features.multi_agent=false flag exists; check whether your client honors it.")
    warnings.append("Project, CLI, UI and managed-policy overrides are not resolved by this static inspection.")
    report = {
        "status": "static-ready",
        "runtime_verified": False,
        "inference_request_made": False,
        "root_model_observed": config.get("model"),
        "root_effort_observed": config.get("model_reasoning_effort"),
        "worker_model": worker_route,
        "worker_provider": route_provider(worker_route),
        "worker_route_family": route_family(worker_route),
        "worker_effort": effort,
        "custom_agent": role,
        "builder_preset": builder,
        "profile_inspected": selected,
        "catalog_contains_worker": True,
        "catalog_advertises_subagent": True,
        "loopback_router_configured": True,
        "input_hashes": input_hashes,
        "warnings": warnings,
    }
    return report, url


def default_locations(home_arg: str | None = None, codex_home_arg: str | None = None) -> tuple[Path, Path]:
    home = Path(home_arg).expanduser().resolve() if home_arg else Path.home().resolve()
    codex_home = Path(codex_home_arg or os.environ.get("CODEX_HOME", str(home / ".codex"))).expanduser().absolute()
    return home, codex_home
