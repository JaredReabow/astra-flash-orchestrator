#!/usr/bin/env python3
"""Preview/install the Astra-led worker skill without changing Codex model/provider settings."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from datetime import datetime, timezone
import uuid

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ is required. No packages or settings were changed.")
sys.dont_write_bytecode = True
BUNDLE = Path(__file__).resolve().parent
SKILL_SOURCE = BUNDLE / "skill" / "astra-flash-orchestrator"
sys.path.insert(0, str(SKILL_SOURCE / "scripts"))
from local_config import (
    DEFAULT_ROUTE, ROLE, SKILL, SetupError, default_locations, inspect, require_route,
    resolve_worker_route,
)
import builders

BEGIN = b"<!-- BEGIN astra-flash-orchestrator managed policy -->"
END = b"<!-- END astra-flash-orchestrator managed policy -->"

# The legacy unnamed worker keeps its own role name, binding path and pinning
# semantics. Its embedded developer instructions track WORKER-INSTRUCTIONS.md, so
# a release that edits those instructions changes this role file on purpose.
LEGACY_ROLE_DESCRIPTION = (
    "Implement an orchestrator-approved task bundle using the installed worker route; "
    "never orchestrate or self-approve."
)
LEGACY_BINDING_KEYS = (
    "worker_model", "worker_provider", "worker_route_family", "worker_effort",
    "custom_agent", "profile_inspected",
)

# Generated at install time, never copied from the bundle: a stray binding in a
# checkout must not be able to overwrite the installed legacy binding or another
# role's pinned route. This mirrors the release inventory's own exclusions.
GENERATED_SKILL_FILES = frozenset({"routing.json", "receipt.json", "auth.json"})


def route_argument(value: str) -> str:
    """Validate --worker-route as an argparse value instead of at first write."""
    try:
        return require_route(value)
    except SetupError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def digest(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def no_symlinks(path: Path) -> None:
    for item in (path, *path.parents):
        if item.is_symlink():
            raise SetupError(f"Refusing to write through a symlink: {item}. Use the documented manual installation instead.")


def contents(path: Path) -> bytes | None:
    no_symlinks(path)
    if not path.exists():
        return None
    if not path.is_file():
        raise SetupError(f"Expected a regular file: {path}")
    return path.read_bytes()


def managed_policy(original: bytes, block: bytes) -> bytes:
    if original.count(BEGIN) != original.count(END) or original.count(BEGIN) > 1:
        raise SetupError("The managed instruction block is malformed or duplicated; reconcile it before installation.")
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    block = block.replace(b"\r\n", b"\n").replace(b"\n", newline).rstrip() + newline
    if BEGIN in original:
        start, end = original.index(BEGIN), original.index(END) + len(END)
        if end < start:
            raise SetupError("The managed policy markers are reversed.")
        if original[end:end + len(newline)] == newline:
            end += len(newline)
        return original[:start] + block + original[end:]
    separator = b"" if not original else (newline if original.endswith(newline) else newline + newline)
    return original + separator + block


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    no_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".astra-flash-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def plan_changes(
    home: Path,
    codex_home: Path,
    report: dict,
    with_policy: bool,
    replace: bool,
    builder: builders.BuilderPreset | None = None,
) -> list[dict]:
    """Plan the reviewed writes for the legacy worker or one named builder."""
    target = home / ".agents" / "skills" / SKILL
    role_id = builder.role if builder else ROLE
    role_path = codex_home / "agents" / f"{role_id}.toml"
    no_symlinks(target)
    # Detect a second copy instead of silently creating duplicate skill activations.
    legacy = codex_home / "skills" / SKILL
    if legacy.exists():
        raise SetupError(f"An existing same-named skill is at {legacy}. Reconcile duplicate locations first.")
    requested: dict[Path, bytes] = {}
    for source in sorted(SKILL_SOURCE.rglob("*")):
        if source.is_symlink():
            raise SetupError("The bundle contains an unexpected symlink.")
        relative = source.relative_to(SKILL_SOURCE)
        if relative.parts and relative.parts[0] == builders.BUILDERS_DIRNAME:
            # Per-role bindings are written from the report for one role only.
            continue
        if relative.name in GENERATED_SKILL_FILES:
            continue
        if (source.is_file() and "__pycache__" not in source.parts
                and source.suffix not in {".pyc", ".pyo", ".bak"}
                and ".before-" not in source.name and source.name != ".DS_Store"):
            requested[target / relative] = source.read_bytes()
    # Each role owns one binding file. A named builder's binding is written only
    # for that role, so installing it cannot rewrite the legacy binding or another
    # builder's pinned route. Nothing here deletes files the package did not write.
    if builder is None:
        binding_path = target / builders.LEGACY_BINDING_NAME
        binding = {key: report[key] for key in LEGACY_BINDING_KEYS}
        description = LEGACY_ROLE_DESCRIPTION
    else:
        binding_path = builders.binding_path(target, role_id)
        binding = builders.binding_payload(report, builder)
        description = builders.role_description(builder, report["worker_model"])
    requested[binding_path] = (json.dumps(binding, indent=2) + "\n").encode()
    instructions = (BUNDLE / "WORKER-INSTRUCTIONS.md").read_text(encoding="utf-8").strip()
    # JSON basic strings are valid TOML basic strings for these generated values.
    role = (
        f'name = {json.dumps(role_id)}\n'
        f'description = {json.dumps(description, ensure_ascii=False)}\n'
        f'model = {json.dumps(report["worker_model"])}\n'
    )
    if report["worker_effort"]:
        role += f'model_reasoning_effort = {json.dumps(report["worker_effort"])}\n'
    role += f'developer_instructions = {json.dumps(instructions, ensure_ascii=False)}\n\n'
    role += '# Inherit the parent sandbox/approvals. Prevent recursive subagent spawning.\n[agents]\nenabled = false\n'
    requested[role_path] = role.encode()
    policy_path = None
    if with_policy:
        override = codex_home / "AGENTS.override.md"
        override_data = contents(override)
        policy_path = override if override_data and override_data.strip() else codex_home / "AGENTS.md"
        requested[policy_path] = managed_policy(contents(policy_path) or b"", (BUNDLE / "POLICY.md").read_bytes())
    changes = []
    for path, new in requested.items():
        old = contents(path)
        if old == new:
            continue
        if old is not None and path != policy_path and not replace:
            raise SetupError(f"Different content already exists at {path}. Inspect it, then explicitly use --replace to back it up and update it.")
        changes.append({"path": path, "before": old, "after": new, "mode": path.stat().st_mode & 0o777 if path.exists() else 0o600})
    return changes


def apply_changes(changes: list[dict], codex_home: Path, input_hashes: dict[str, str]) -> Path | None:
    if not changes:
        return None
    for name, expected in input_hashes.items():
        if digest(Path(name).read_bytes()) != expected:
            raise SetupError("The Codex configuration changed during inspection. Rerun the installer.")
    for change in changes:
        if contents(change["path"]) != change["before"]:
            raise SetupError("An installation target changed during inspection. Rerun the installer.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    backup_dir = codex_home / "astra-flash-install-backups" / stamp
    no_symlinks(backup_dir)
    backup_dir.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    backup_dir.mkdir(mode=0o700)
    entries = []
    for index, change in enumerate(changes):
        backup = f"before-{index}.bin" if change["before"] is not None else None
        if backup:
            atomic_write(backup_dir / backup, change["before"], 0o600)
        entries.append({"path": str(change["path"]), "before_file": backup, "before_hash": digest(change["before"]), "after_hash": digest(change["after"]), "mode": change["mode"]})
    receipt = backup_dir / "receipt.json"
    record = {"format": 1, "status": "prepared", "files": entries}
    atomic_write(receipt, (json.dumps(record, indent=2) + "\n").encode())
    completed = []
    try:
        for change in changes:
            atomic_write(change["path"], change["after"], change["mode"])
            completed.append(change)
    except BaseException:
        for change in reversed(completed):
            if change["before"] is None:
                change["path"].unlink(missing_ok=True)
            else:
                atomic_write(change["path"], change["before"], change["mode"])
        record["status"] = "rolled-back"
        atomic_write(receipt, (json.dumps(record, indent=2) + "\n").encode())
        raise
    record["status"] = "installed"
    atomic_write(receipt, (json.dumps(record, indent=2) + "\n").encode())
    return receipt


def allowed_undo_target(path: Path, agents: Path, policy: set[Path], root: Path) -> bool:
    """Allowlist for undo: known roles, known bindings, policy files, skill files.

    Skill files are package-owned, so their paths stay allowed as before. Agent
    roles and builder bindings are restricted to the roles this module knows, so a
    tampered receipt cannot add a role or binding this package never installs.
    """
    if path in policy:
        return True
    if path.parent == agents and path.suffix == ".toml":
        return builders.known_role(path.stem)
    if not path.resolve().is_relative_to(root.resolve()):
        return False
    relative = path.resolve().relative_to(root.resolve())
    if relative.parts and relative.parts[0] == builders.BUILDERS_DIRNAME:
        return builders.binding_role(relative) is not None
    return True


def transaction_shared_targets(targets: set[Path], agents: Path, policy: set[Path], root: Path) -> list[Path]:
    """Entries of a transaction that other installed roles depend on.

    A role's own agent file and its own `builders/<role>.json` binding are private
    to that role. Everything else the package installs - the shared skill files and
    the managed policy block - is depended on by every installed role, so undoing
    it while another role remains would leave that role pointing at a skill the
    package no longer installs.
    """
    shared = []
    for path in sorted(targets):
        if path in policy:
            shared.append(path)
            continue
        if path.parent == agents:
            continue
        resolved = path.resolve()
        if resolved.is_relative_to(root.resolve()):
            relative = resolved.relative_to(root.resolve())
            if relative.parts and relative.parts[0] == builders.BUILDERS_DIRNAME:
                continue
            if relative == Path(builders.LEGACY_BINDING_NAME):
                continue
            shared.append(path)
    return shared


def remaining_package_targets(exclude: set[Path], agents: Path, root: Path) -> list[Path]:
    """Installed roles and bindings outside this transaction, legacy included."""
    found = []
    for role in sorted(builders.KNOWN_ROLES):
        path = agents / f"{role}.toml"
        if path not in exclude and path.exists():
            found.append(path)
    candidates = [root / builders.LEGACY_BINDING_NAME]
    candidates += [builders.binding_path(root, role) for role in sorted(builders.KNOWN_ROLES)]
    for path in candidates:
        if path not in exclude and path.exists():
            found.append(path)
    return found


def undo(receipt: Path, home: Path, codex_home: Path, apply: bool) -> None:
    no_symlinks(receipt)
    if ".." in receipt.parts or not receipt.resolve().is_relative_to((codex_home / "astra-flash-install-backups").resolve()):
        raise SetupError("The receipt must be inside this CODEX_HOME's astra-flash-install-backups folder.")
    record = json.loads(receipt.read_text())
    if record.get("format") != 1 or record.get("status") != "installed":
        raise SetupError("This receipt does not describe an installed, undoable transaction.")
    root = home / ".agents" / "skills" / SKILL
    agents = codex_home / "agents"
    policy = {codex_home / "AGENTS.md", codex_home / "AGENTS.override.md"}
    pending = []
    for entry in record["files"]:
        path = Path(entry["path"])
        if not path.is_absolute() or ".." in path.parts or not allowed_undo_target(path, agents, policy, root):
            raise SetupError("The receipt contains a target outside this package's installation paths.")
        current = contents(path)
        if digest(current) != entry["after_hash"]:
            raise SetupError(f"Refusing undo: {path} changed after installation. Preserve/reconcile those edits first.")
        before = None
        if entry["before_file"]:
            name = entry["before_file"]
            if Path(name).name != name:
                raise SetupError("Invalid backup filename in receipt.")
            before = (receipt.parent / name).read_bytes()
        if digest(before) != entry["before_hash"]:
            raise SetupError("A backup no longer matches its receipt. Nothing was restored.")
        pending.append((path, before, entry["mode"]))
    # Fail closed before the first write. A receipt for the first installed role
    # carries the shared skill files and the policy; restoring them while a later
    # role is still installed would strand that role without the skill it depends
    # on. Role-only transactions stay allowed, so undoing later roles in reverse
    # install order is never blocked.
    targets = {path for path, _before, _mode in pending}
    if transaction_shared_targets(targets, agents, policy, root):
        remaining = remaining_package_targets(targets, agents, root)
        if remaining:
            names = ", ".join(sorted(path.name for path in remaining))
            raise SetupError(
                "Refusing undo: this transaction owns the shared skill files or the managed "
                f"policy, and {names} would remain installed without them. Undo the installed "
                "builders in reverse install order (most recently installed first), then retry "
                "this receipt. Nothing was restored."
            )
    for path, before, mode in pending:
        print(f"{'RESTORE' if before is not None else 'REMOVE'} {path}")
        if apply:
            if before is None:
                path.unlink()
            else:
                atomic_write(path, before, mode)
    if apply:
        record["status"] = "restored"
        atomic_write(receipt, (json.dumps(record, indent=2) + "\n").encode())
        if root.exists():
            for directory in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            try:
                root.rmdir()
            except OSError:
                pass
    else:
        print("Preview only. Add --apply to perform this undo.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the reviewed installation; otherwise preview only")
    parser.add_argument("--no-policy", action="store_true", help="install skill/role without changing personal AGENTS guidance")
    parser.add_argument("--replace", action="store_true", help="back up and replace different existing package-owned files")
    parser.add_argument("--home", help="override HOME (primarily for isolated tests)")
    parser.add_argument("--codex-home", help="override CODEX_HOME")
    parser.add_argument("--profile", help="inspect a specific existing profile; does not change profile selection")
    parser.add_argument(
        "--builder",
        choices=sorted(builders.PRESETS),
        help=(
            "install one named builder role next to any others already installed; "
            "without this option the legacy astra_flash_builder worker is installed or updated"
        ),
    )
    parser.add_argument(
        "--worker-route",
        type=route_argument,
        metavar="ROUTE",
        help=(
            "pin one reviewed route for this install (with --builder it must be a route that "
            "preset allows, including a configured local/<ollama-tag> route for the ollama preset) "
            f"(default: existing routing binding, then {DEFAULT_ROUTE})"
        ),
    )
    parser.add_argument("--undo", type=Path, metavar="RECEIPT", help="preview restoration from an installation receipt; combine with --apply to restore")
    args = parser.parse_args()
    try:
        home, codex_home = default_locations(args.home, args.codex_home)
        if args.undo:
            undo(args.undo, home, codex_home, args.apply)
            return 0
        skill_dir = home / ".agents" / "skills" / SKILL
        spec = builders.preset(args.builder) if args.builder else None
        if spec is None:
            binding = skill_dir / builders.LEGACY_BINDING_NAME
            worker_route = resolve_worker_route(args.worker_route, binding)
        else:
            binding = builders.binding_path(skill_dir, spec.role)
            worker_route = builders.resolve_builder_route(spec.key, args.worker_route, binding)
        report, _private_url = inspect(
            home,
            codex_home,
            args.profile,
            worker_route,
            role=spec.role if spec else ROLE,
            builder=spec.key if spec else None,
        )
        changes = plan_changes(home, codex_home, report, not args.no_policy, args.replace, builder=spec)
        print(json.dumps(report, indent=2))
        for change in changes:
            print(f"{'UPDATE' if change['before'] is not None else 'CREATE'} {change['path']}")
        if not args.apply:
            print("Preview only. No files changed. Add --apply after reviewing these destinations.")
            return 0
        receipt = apply_changes(changes, codex_home, report["input_hashes"])
        if receipt and spec:
            print(f"Installed builder {spec.label} as {spec.role} on {worker_route}.")
        print(f"Installed. Undo receipt: {receipt}" if receipt else "Already installed; no changes needed.")
        print("config.toml and router/authentication files were not written. No model request was made.")
        print("Fully quit/reopen the host app, then start a session with your orchestrator "
              "(Astra or Terra). Runtime model identity still needs a real delegated-task check.")
        return 0
    except (SetupError, OSError, ValueError) as exc:
        message = str(exc) if isinstance(exc, SetupError) else f"Local installation error ({type(exc).__name__}); inspect locally."
        print(f"INSTALL FAILED: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
