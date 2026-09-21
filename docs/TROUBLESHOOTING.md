# Troubleshooting

## The skill is missing

Check that installation ended with `Installed` or `Already installed`, not only a successful dry run. The expected file is `~/.agents/skills/astra-flash-orchestrator/SKILL.md`. Fully quit/reopen the host app, then start an Astra session. Check custom home locations and client skill discovery before reinstalling.

## A named builder is missing or has the wrong route

Each named builder is installed on its own: `python3 -B install.py --builder grok
--replace --apply`. Installing one role never creates another, so a missing role
means that preset was never installed. Check it with
`python3 -B skill/astra-flash-orchestrator/scripts/doctor.py --builder grok`, which
reads that role's own `builders/<role>.json` beside the installed skill. The legacy
`astra_flash_builder` role keeps using `routing.json` and is unaffected either way.

A route mismatch is refused before any file is written: `grok` accepts 4.6 or 4.5,
`fable`, `deepseek-flash`, `deepseek-pro` and `grok-4-5` accept their exact route,
and `ollama` needs an explicit `local/<ollama-tag>` on its first install. Passing a
route from another preset is a configuration error, not something to work around by
editing a binding by hand. Undo restores only the role named in the receipt and
refuses unknown role or binding paths.

## Undo says the builders must be undone in reverse install order

The first builder installed in a machine also owns the shared skill files and the
managed policy block; later installs find those files already correct and do not
carry them. Restoring the first receipt while a later builder is still installed
would leave that builder pointing at a skill the package no longer provides, so the
undo is refused before anything is written. Undo the most recently installed
builder first and work backwards; a receipt that only owns one role and its binding
is never blocked this way. The legacy `astra_flash_builder` role and `routing.json`
are part of the same ordering rule.

## Expected worker route is missing or different

The direct default is `deepseek/deepseek-v4.1-flash`. A new alternate-provider
install requires the exact documented `--worker-route`. An installed doctor or
later update reuses the valid generated routing binding automatically; a doctor
run from a fresh source checkout needs the option again. Establish the
Router/provider configuration using the Router's own documentation first. An
entry in a model catalog alone does not establish credentials or paid inference
access. The installer does not auto-detect or silently substitute a provider.

The same option accepts `deepseek/deepseek-v4-pro`, `grok-oauth/grok-4.6`,
`grok-oauth/grok-4.5`, `openrouter/claude-fable-5.1` and a configured
`local/<ollama-tag>` route. A slug that is not one of those and does not look like
a local Ollama tag is refused before any file is written, so a typo cannot quietly
install a different provider. The role name stays `astra_flash_builder` whatever
route is pinned.

Ollama cloud aliases (`<model>:cloud` and `<model>:<size>b-cloud`) are refused
under `local/` with their own message. Those variants are served from Ollama's
cloud, so pinning one as `local/...` would label remote inference as on-machine.
Use the Router's `ollama-cloud` provider route instead. More generally, a `local/`
slug only records the namespace the Router published: it is not evidence that the
weights run on this machine. Confirm locality from your own Ollama/runtime
evidence, not from the slug.

Enter API keys yourself through the Router's private local prompt; never paste
one into assistant chat. If the route is absent, stop package installation and
finish provider setup separately.

## Router URL is rejected

Only HTTP(S) loopback URLs are accepted. Supported paths are `/v1` and `/_codex-router/<capability>/v1`, optionally with a trailing slash. Remote endpoints, queries, fragments and embedded URL credentials are rejected. Do not post a private capability URL in an issue.

## Static doctor passes but live catalog check fails

The optional doctor request deliberately does not read authentication files or send credentials. A Router requiring authentication may reject `/models`; a stopped Router or network restriction may also cause failure. Normal Codex requests can use an authenticated route. Keep authentication enabled and use the Router's documented diagnostic tools. Report only redacted HTTP status/error categories.

## The offline HTTP fixture cannot bind a port

One test starts a temporary local HTTP server. A restrictive sandbox can block it. Run the offline suite in an environment that permits a loopback fixture through the normal approval mechanism. Do not disable security controls or skip the failed test and call the suite passing.

## Custom role is unavailable in a new session

The installed client must support standalone personal agent TOML files and expose native delegation. Files on disk do not prove the running tool supports them. Check your installed client and project/managed overrides. Do not fall back to a different model or external agent CLI.

## Existing skill or role conflicts

The installer refuses symlinked targets, duplicate skill locations and differing package-owned files. Review existing content before using `--replace`; keep the resulting receipt. Do not remove unrelated skills to resolve discovery.

## Undo refuses because a file changed

This protects later edits, including changes to the shared personal AGENTS file. Preserve those edits, compare the receipt and backup locally, then reconcile deliberately. Do not publish receipts or original instruction backups.

## No savings or quality guarantee

Provider usage and real task outcomes determine cost and quality. Offline tests validate installation and planning helpers, not the performance of either model. Request metadata is routing evidence; a worker's self-description is not.

## The worker route is visible in the picker but unavailable for delegation

The merged catalog must advertise the exact selected route with
`multi_agent_version: "v2"`. A model entry or default-subagent setting alone is
insufficient. Use the installed Router's documented selection and catalog
publication controls, then fully quit/reopen the app. Do not let an installation
assistant run `subagents certify`, `test-model --live`, a smoke test or another
paid probe to make this check pass. Decide separately whether to spend provider
credit on certification yourself. Do not manually falsify certification records
or claim selection proves runtime capability.

Two cases are easy to misread. `grok-oauth/grok-4.5` is checked into the Router
with a `v2` certificate but the published catalog lists it as `v1`, so it stays
blocked until that route is enabled through the Router's own controls. Local Ollama
models are normally absent from the catalog until the operator enables them, and
the Router's default for a local entry is `v1`; a `local/<tag>` route installs only
once that exact model is enabled and republished as `v2`. In both cases the fix
belongs in the Router, not in this package.
