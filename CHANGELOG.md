# Changelog

## 1.4.0 — Named builders

- Add `install.py --builder <preset>` for six separately pinned builder roles that
  coexist on one machine: `grok` (`astra_terra_builder_grok`), `fable`
  (`astra_terra_builder_fable`), `deepseek-flash`
  (`astra_terra_builder_deepseek_flash`), `deepseek-pro`
  (`astra_terra_builder_deepseek_pro`), `grok-4-5`
  (`astra_terra_builder_grok_4_5`) and `ollama`
  (`astra_terra_builder_ollama`). Grok defaults to the 4.6 OAuth route, Fable is
  OpenRouter, Flash and Pro are the direct DeepSeek routes, Grok 4.5 is the exact
  OAuth route, and Ollama is local-only. Role ids are human-readable labels with no
  slash or space, and each role description carries the requested label.
- Bind each role to its own `builders/<role>.json` under the installed skill, in a
  new centralized preset module. Installing or updating one builder writes only
  that role's agent file and binding: it never rewrites the legacy `routing.json`,
  the legacy `astra_flash_builder` role, or another builder. The legacy CLI path,
  role name, `routing.json` binding location, pinning rules and undo semantics are
  unchanged; its generated role file still carries the current
  `WORKER-INSTRUCTIONS.md` text, so editing those instructions changes that file.
- Restrict `--worker-route` to routes the paired preset may pin: Grok accepts 4.6
  or 4.5, Fable, DeepSeek Flash, DeepSeek Pro and Grok 4.5 accept their exact
  route, and Ollama requires a configured `local/<ollama-tag>` on the first
  install, then reuses its binding. A mismatch is refused before any write.
- Add `doctor.py --builder <preset>`, which reads that role's own binding, and keep
  the default doctor path on the legacy binding.
- Extend undo with an allowlist on top of the existing receipt checks: only known
  roles (`agents/<role>.toml`) and known bindings (`builders/<role>.json`) may be
  restored, so a tampered receipt cannot add a role or binding the package never
  installs.
- Fail undo closed when the receipt owns the shared skill files or the managed
  policy and another installed role or binding would be left behind, with
  reverse-install-order guidance. Role-only receipts stay allowed, so undoing a
  later builder is never blocked by an earlier one. The legacy role and its
  `routing.json` are covered by the same guard.
- Filter generated binding files out of the bundled skill copy. A stray
  `routing.json` or `builders/*.json` in a checkout can no longer be published
  over the installed legacy binding or another role's pinned route.
- Generalize the managed policy, skill and references for a root session running
  Astra or Terra: keep the operator's chosen orchestrator, dispatch to one
  explicitly named installed builder, and never start several writers because
  several roles happen to be installed.
- Add a reference example under `examples/named-builders/` plus offline coverage for
  coexistence, per-role isolation, doctor selection, undo order, cloud/`v1`/absent
  route refusal, preset/route mismatches and undo path allowlisting.

## 1.3.0 — Multi-model worker routes

- Accept an explicit, reviewed worker route beyond the DeepSeek V4.1 Flash family:
  `deepseek/deepseek-v4-pro`, `grok-oauth/grok-4.6`, `grok-oauth/grok-4.5` and
  `openrouter/claude-fable-5.1`, plus a dynamic `local/<ollama-tag>` Ollama route
  validated against the Router's own tag grammar. Flash stays the default and the
  `astra_flash_builder` role name is retained for install and update compatibility.
- Keep the fail-closed route contract for every route: the exact slug must appear
  once in the catalog the session actually uses and advertise
  `multi_agent_version: "v2"`, and an unknown, malformed, duplicated or `v1` route
  stops installation without substituting a provider. `grok-oauth/grok-4.5` is
  listed as `v1` in the published catalog, and no `local/*` entry is present at
  all, so both stay blocked until the operator enables that exact route in the
  Router.
- Refuse Ollama cloud alias variants (`<model>:cloud` and `<model>:<size>b-cloud`)
  under the `local/` prefix with their own message. They are served from Ollama's
  cloud, and a slug prefix is not evidence of where inference runs. Use the
  Router's `ollama-cloud` provider route for those models.
- Keep the 1.2.0 Flash-root refusal, and report a root model equal to the selected
  worker route as a warning instead of an error: one model may serve both roles,
  and the saved default is not proof of the model a running session uses. Every
  root value, root effort, provider URL and credential is preserved untouched.
- Record the route family (`flash`, `cloud`, `local`) in the report and the
  installed routing binding, and keep validating the pinned effort against the
  route's advertised reasoning levels.
- Generalize Flash-only wording in the managed policy, skill, references, README,
  install prompt and troubleshooting to describe the installed worker route
  instead of assuming one provider.
- Add offline coverage for each new route, the binding round trip, dynamic local
  routes, cloud-alias refusal, malformed and unknown slugs, the `v1` rejection,
  the same-model root warning and the existing regression suite.
- Add an append-only `HISTORY.md` alongside `CHANGELOG.md` and include both in the
  release inventory; the two files are not substitutes for each other.
- Point the README clone/download instructions at this fork while keeping upstream
  attribution, and drop machine-specific paths and private root-configuration
  details from the published documents.
- Support explicit, reviewed DeepSeek V4.1 Flash routes through OpenRouter,
  opencode Go, Command Code, Nous Research and Ollama Cloud while retaining the
  direct DeepSeek API as the default. Existing alternate-route installations
  reuse their validated routing binding on doctor checks and updates.
- Make provider choice fail closed: no catalog auto-detection, silent fallback,
  credential handling or paid certification during package installation.
- State that users enter API keys only through the Router's private local prompt,
  and prohibit installation agents from running `subagents certify`,
  `test-model --live`, smoke tests or other paid probes.
- Detect keys absorbed into `[agents]` by shape instead of by a list of
  anticipated top-level names. A stray key there is read by Codex as an agent
  name and stops the whole config loading, and the previous check only covered
  five names, missing the realtime base-URL keys that caused a real failure.
- Accept a legitimate `[agents]` table containing the recognized scalar settings
  and agent role tables, and reject an agent name whose value is not a table.
- Tell installation agents to select an existing Python 3.11+ interpreter rather
  than assume `python3`, and never to edit `config.toml` to make a check pass.

## 1.2.0 — Measured workflow and simpler installation

- Add a measured efficiency graphic, per-token price comparison and transparent
  benchmark methodology to the README.
- Document thin orchestration as the only supported delegated workflow, not a
  user-selectable mode, while retaining direct handling for trivial work and
  targeted high-assurance review.
- Reduce the normal terminal installation path to a guarded preview and apply;
  keep the offline test suite as optional local verification.
- Remove the unnecessary global subagent-default prerequisite. The installer
  now relies only on its named role's pinned worker settings and explicitly
  warns installation agents not to edit shared Codex model defaults.
- Include SVG documentation assets in release archives.

## 1.1.0 — Thin-root orchestration by default

- Keep Astra to a planning batch, one worker dispatch/wait, one batched acceptance review and the final response for normal phases.
- Make Flash responsible for in-scope repository discovery, implementation, testing, debugging and routine browser/visual QA.
- Remove progress polling, duplicate root investigation and ritual full-suite reruns from the default workflow.
- Consolidate review findings into one correction request and one default correction cycle.
- Retain additional Astra investigation and verification for concrete high-assurance risks.

## 1.0.2 — Native delegation readiness

- Refuse installation when Flash is present but not advertised for native subagents.
- Explain full host-app restart, cached catalogs, and Router commands that can trigger paid verification.
- Distinguish local route selection from runtime capability evidence.

## 1.0.1 — Public repository preparation

- Support the Router's native authenticated `/v1` base path alongside capability paths; retain loopback and URL-shape validation.
- Preserve permissions on an existing installation-backup directory.
- Add regression tests for direct routing, rejected URL shapes and permission preservation.
- Exclude local backup/cache artifacts from installed skill files and release archives.
- Replace private handoff/audit notes with public installation, troubleshooting, contribution and security documentation.
- Add reproducible release inventory and ZIP packaging with integrity checks.

## 1.0.0 — Initial package

- Native Flash builder role, Astra orchestration skill, scoped personal policy, dry run and guarded undo.
- Offline installation tests, configuration doctor, task templates and optional plan validator.
