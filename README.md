# Astra Flash Orchestrator

**Astra plans and reviews. DeepSeek Flash implements.**

A personal Codex skill that turns an approved plan into substantial implementation tasks, delegates them through your existing Codex Router, and keeps architecture, verification and acceptance with Astra.

Bring an existing plan or start with a feature request. The workflow covers specification, dependency-ordered tasks, implementation, review, corrections and resumable checkpoints.

> **Status:** early release. Offline installation tests pass. Real Astra-to-Flash worker routing and end-to-end build quality have not yet been verified for this package. Installation never runs paid inference.

## How it works

```text
Astra  →  scope + design + task brief
Flash  →  implement + test + report
Astra  →  review + verify + accept or request fixes
       →  integrate + checkpoint + next task
```

- **Native delegation:** uses the `astra_flash_builder` role, not a separate agent CLI.
- **Coherent assignments:** one feature slice can include many edit/test/fix steps.
- **Thin Astra root:** normally one planning batch, one dispatch, one wait, one
  batched acceptance review and one final response.
- **Worker-owned execution:** Flash handles in-scope discovery, implementation,
  testing, debugging and routine browser/visual QA without progress polling.
- **Review before acceptance:** the builder submits evidence; Astra decides whether it is complete.
- **Existing plans welcome:** works with repository plans, Superpowers/GSD artifacts, or the included templates.
- **Controlled parallel work:** one writer by default; two only with independent tasks and verified separate workspaces.
- **Reversible installation:** dry run, backups and a guarded undo receipt.

This is workflow guidance, not a deterministic scheduler, a security sandbox, or a guarantee of model quality or cost savings. It is independent of OpenAI, DeepSeek and Codex Router.

## Requirements

Before installing, you need:

1. A Codex client that supports native subagents and standalone custom agent TOML files under `$CODEX_HOME/agents/`.
2. GPT-6 Astra selected as the root model.
3. Python **3.11 or newer**. No third-party Python dependencies are needed.
4. An existing [Codex Router installation](https://github.com/duolahypercho/codex-router), configured and authenticated for the exact route `deepseek/deepseek-v4.1-flash`.
5. A local Codex model catalog advertising that route with `multi_agent_version: "v2"`, and this existing setting in your effective configuration:

```toml
[agents]
default_subagent_model = "deepseek/deepseek-v4.1-flash"
```

The setting above is a prerequisite to verify, not a replacement configuration to paste over your own. The installer **does not install the Router, add credentials, select your root model, or rewrite config.toml**. If your routing differs, it stops instead of silently choosing another provider.

The installer supports loopback Router URLs using `/v1` or `/_codex-router/<capability>/v1`. It rejects remote hosts, embedded credentials, queries, fragments and unexpected paths. Client/project/UI overrides still need checking in your actual session. Router subagent selection enables discovery; it does not prove successful inference. Some Router enable commands automatically launch paid verification, so inspect the installed version before changing selection. This installer never enables routes or runs those probes.

## Install

Download this repository as a ZIP and extract it, or clone it:

```sh
git clone https://github.com/ethanplusai/astra-flash-orchestrator.git
cd astra-flash-orchestrator
```

Run the following commands from that repository folder.

### With Codex

Ask Codex:

```text
Read INSTALL-IN-CODEX.md in this folder and install the package following it.
Preserve my root model, reasoning effort, Router, config and authentication.
Do not launch workers or run paid inference during installation.
```

### From a terminal

Run each command only after the previous one succeeds:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B install.py
python3 -B install.py --apply
```

The second command is a dry run: inspect its report and proposed file destinations. The third installs. Save the printed undo receipt path.

For a nondefault profile, pass `--profile PROFILE` to the dry run, apply and doctor consistently. `--home` and `--codex-home` are available for explicit location overrides. Use the same locations for undo.

### What changes

| Location | Installed content |
| --- | --- |
| `~/.agents/skills/astra-flash-orchestrator/` | Skill, references, templates, doctor, plan validator and routing binding |
| `$CODEX_HOME/agents/astra_flash_builder.toml` | Native builder pinned to Flash; nested agents disabled |
| `$CODEX_HOME/AGENTS.md` | A marked, scoped workflow policy block |
| `$CODEX_HOME/astra-flash-install-backups/` | Original files and an undo receipt |

`CODEX_HOME` defaults to `~/.codex`. An existing nonempty `AGENTS.override.md` receives the policy instead of `AGENTS.md`. Other instructions are preserved. The policy keeps trivial work single-agent and honors explicit no-delegation requests, repository restrictions and managed policies. Use `--no-policy` for a skill/role-only installation.

Root model/effort, provider configuration, authentication and existing permissions stay unchanged. Installation does not start services, workers or model requests, and does not commit, push or deploy anything.

## Start your first task

**Fully quit and reopen the host app (ChatGPT or Codex), then start an Astra session.** A new chat alone may reuse a cached model catalog. Use:

```text
$astra-flash-orchestrator Use the existing plan in docs/plan.md to implement
this feature. Keep Astra as the thin orchestrator and reviewer. Use one installed
Flash builder for a coherent implementation and verification bundle. Do not poll
the worker; review its completed patch and evidence in one batched pass.
```

Replace the example plan path with your actual plan or describe the feature. Your first authorized useful task should verify the child model and provider using host/router request metadata. A worker saying its model name is not proof.

If the session does not expose the custom role or exact worker model, do not substitute another model or launch a second CLI. Check client support and session configuration first.

## Check your setup

From the repository folder:

```sh
python3 -B skill/astra-flash-orchestrator/scripts/doctor.py
python3 -B skill/astra-flash-orchestrator/scripts/doctor.py --check-local-router
```

The first checks local configuration/catalog data. The optional second command makes only a local `/models` GET, with proxies and redirects disabled. It does not read authentication files or attach credentials; an authenticated Router may reject it even when normal Codex requests work. Do not disable Router authentication to make this check pass.

Neither check proves paid inference works. See [troubleshooting](docs/TROUBLESHOOTING.md) and [validation evidence](docs/VALIDATION.md).

## Updating and uninstalling

For an update, download the new source, run its tests, and preview `python3 -B install.py --replace`. Review the differences before applying with `--replace --apply`. Existing package-owned files are backed up; unrelated files are not deleted. Do not edit generated `routing.json` or the agent model to force a different provider through preflight.

Preview undo using the exact receipt printed during installation:

```sh
python3 -B install.py --undo /path/to/receipt.json
```

Add `--apply` to restore. Undo refuses if a managed file changed afterward, protecting later edits. Backups remain available. Keep a copy of the installer and receipt; receipts may contain private paths and original instructions and should never be published.

## Contributing and distribution

- [Contributing](CONTRIBUTING.md): tests, changes and evidence expectations.
- [Security](SECURITY.md): privacy boundaries and safe reporting.
- [Sources](SOURCES.md): provenance and upstream references.
- [Release preparation](docs/RELEASE.md): GitHub description, topics and release checks.
- [Changelog](CHANGELOG.md): changes from the original package.

To validate the synthetic plan example:

```sh
python3 -B skill/astra-flash-orchestrator/scripts/validate_plan.py examples/invoice-filter/plan.json
```

The example is a planning fixture, not a runnable application. Markdown plans work without the optional manifest validator.
