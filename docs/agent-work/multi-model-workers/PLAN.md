# Multi-model worker routes

Phase plan for user-authorized multi-model adaptation of this package.
Status: implemented, including the acceptance correction batch (cloud-alias
refusal, warning-only root equality, `HISTORY.md`, path/detail redaction, fork
download link). Pending independent review by the root Astra agent.

## Objective

Let an operator pin one *explicitly named, already-configured* worker route other
than DeepSeek V4.1 Flash, without weakening the package's fail-closed behaviour.

## Non-goals

- No provider is enabled, configured, authenticated or probed by this package.
- No automatic provider selection and no fallback when the requested route is absent.
- No inference request, no `subagents certify`, no `test-model --live`, no smoke test.
- No change to `config.toml`, credentials, root model, root effort, Router state or
  global `[agents]` defaults.
- No new runtime dependency and no second agent CLI.

## Contract

1. The default stays `deepseek/deepseek-v4.1-flash`.
2. The role name stays `astra_flash_builder` for install/update compatibility; its
   `model` field is whatever route the operator pinned.
3. `--worker-route` additionally accepts these reviewed slugs:
   `deepseek/deepseek-v4-pro`, `grok-oauth/grok-4.6`, `grok-oauth/grok-4.5`,
   `openrouter/claude-fable-5.1`.
4. `--worker-route` accepts a dynamic local route of the form `local/<ollama-tag>`
   (`local/qwen3.8:27b-mlx`), validated by shape and then against the live catalog.
   Ollama cloud alias variants (`<model>:cloud`, `<model>:<size>b-cloud`) are
   refused: they are served from Ollama's cloud, so a `local/` slug must not be
   able to present them as on-machine inference.
5. The requested route must appear **exactly once** in the configured catalog and
   that entry must advertise `multi_agent_version: "v2"`. Otherwise installation
   stops and reports the prerequisite. Grok 4.5 is listed as `v1` in the published
   catalog (hidden in the Router), so it stays blocked until the operator enables
   it.
6. The catalog's declared `default_reasoning_level` must be one of the entry's
   `supported_reasoning_levels`; that value is what the role pins.
7. An installed `routing.json` binding is reused when `--worker-route` is omitted.
8. Backup, receipt, rollback and guarded-undo behaviour is unchanged.
9. A Flash root is still refused, as in 1.2.0. Any other root model is preserved
   untouched, including one equal to the selected worker route, which is reported
   as a warning: one model may serve both roles, and the saved default is not proof
   of the model a running session uses.

## Route namespace evidence

See `ROUTE-EVIDENCE.md`. Read-only inspection of the Router source and the
published catalog on this machine; no provider call was made.

## Work items

| ID | Item | Deliverable |
| --- | --- | --- |
| W1 | Route registry | `local_config.py` reviewed-route table plus `local/<tag>` shape validation |
| W2 | Installer | `install.py` CLI validation, report/binding fields, generalized root guard |
| W3 | Doctor | `doctor.py` reuses the shared route validation and reports local vs cloud |
| W4 | Tests | offline coverage for every new route, malformed/unknown input, v1 rejection, binding round trip, local vs cloud, existing regressions |
| W5 | Docs and policy | Flash-only wording generalized in README, POLICY, skill references, install prompt and troubleshooting |
| W6 | Release | `VERSION` 1.3.0, CHANGELOG section, append-only `HISTORY.md`, regenerated `MANIFEST.sha256` |

## Verification (offline only)

```sh
python3 -B -m unittest discover -s tests -v
python3 -B skill/astra-flash-orchestrator/scripts/validate_plan.py examples/invoice-filter/plan.json
python3 -B scripts/release.py --check
```

All tests use synthetic temporary homes and a loopback HTTP fixture. No provider
account, credential or model request is involved.

## Repository conventions noted

- The repository keeps `VERSION`, `CHANGELOG.md` (release notes grouped by version)
  and `HISTORY.md` (append-only dated record) as separate artifacts. Neither file
  substitutes for the other; a change is recorded in both.
- `scripts/release.py` owns the distributable file set, so any new file under
  `docs/`, `tests/`, `scripts/`, `examples/` or `skill/` must be reflected in a
  regenerated manifest before `--check` can pass. `HISTORY.md` is listed in
  `ROOT_FILES` for the same reason.

## Limitations carried forward

- No route in this package is runtime-verified by installation. Actual delegation
  evidence belongs to the first separately authorized useful task.
- No `local/*` entry is present in the current published catalog, and the Router's
  own default for a local entry is `v1`, so a local route cannot be installed until
  the operator enables and republishes that exact model.
- Benchmarks in `docs/BENCHMARK.md` describe a DeepSeek V4.1 Flash field run and do
  not transfer to the other routes.
