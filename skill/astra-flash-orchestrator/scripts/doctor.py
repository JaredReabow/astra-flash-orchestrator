#!/usr/bin/env python3
"""Check local config; optionally query ONLY the loopback router's /models endpoint."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request
sys.dont_write_bytecode = True
from local_config import (
    DEFAULT_ROUTE, ROLE, SetupError, default_locations, inspect, model_entries, model_id,
    require_route, resolve_worker_route,
)
import builders


def route_argument(value: str) -> str:
    """Validate --worker-route as an argparse value before any inspection.

    The installer keeps its own copy of this adapter on purpose: this file is
    also installed as a standalone skill script and must not import the
    repository-root installer.
    """
    try:
        return require_route(value)
    except SetupError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SetupError("Local catalog redirected. Refusing to forward the private caller URL.")


def check_local_catalog(url: str, worker_route: str) -> None:
    # Disable ambient HTTP proxies and redirects: the capability must stay local.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url.rstrip("/") + "/models", headers={"Accept": "application/json"})
    try:
        with opener.open(request, timeout=5) as response:
            body = response.read(10_000_001)
        if len(body) > 10_000_000:
            raise SetupError("Local model response exceeded its size limit.")
        entries = model_entries(json.loads(body))
        if not any(model_id(entry) == worker_route for entry in entries):
            raise SetupError("The live local catalog does not advertise the requested worker route.")
    except (OSError, urllib.error.URLError, json.JSONDecodeError, UnicodeError) as exc:
        raise SetupError(f"Local catalog check failed ({type(exc).__name__}); private URL withheld.") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home")
    parser.add_argument("--codex-home")
    parser.add_argument("--profile")
    parser.add_argument(
        "--builder",
        choices=sorted(builders.PRESETS),
        help="check one named builder's own binding instead of the legacy worker binding",
    )
    parser.add_argument(
        "--worker-route",
        type=route_argument,
        metavar="ROUTE",
        help=(
            "check a reviewed route, including a configured local/<ollama-tag> route (with "
            "--builder it must be a route that preset allows) "
            f"(default: installed routing binding, then {DEFAULT_ROUTE})"
        ),
    )
    parser.add_argument(
        "--check-local-router",
        action="store_true",
        help="GET the loopback /models endpoint; never send an inference request",
    )
    args = parser.parse_args()
    try:
        home, codex_home = default_locations(args.home, args.codex_home)
        skill_dir = Path(__file__).resolve().parents[1]
        spec = builders.preset(args.builder) if args.builder else None
        if spec is None:
            binding = skill_dir / builders.LEGACY_BINDING_NAME
            worker_route = resolve_worker_route(args.worker_route, binding)
        else:
            binding = builders.binding_path(skill_dir, spec.role)
            if not binding.exists() and args.worker_route is None:
                raise SetupError(
                    f"No {spec.label} binding is installed beside this skill. Install that builder "
                    f"first with `--builder {spec.key}`, or check a route explicitly with "
                    "--worker-route."
                )
            worker_route = builders.resolve_builder_route(spec.key, args.worker_route, binding)
        report, url = inspect(
            home,
            codex_home,
            args.profile,
            worker_route,
            role=spec.role if spec else ROLE,
            builder=spec.key if spec else None,
        )
        if args.check_local_router:
            check_local_catalog(url, worker_route)
            report["status"] = "local-catalog-ready"
            report["local_catalog_checked"] = True
        print(json.dumps(report, indent=2))
        return 0
    except SetupError as exc:
        print(f"CHECK FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
