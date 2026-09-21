# Named builders

Phase plan for user-authorized named-builder support in this package.
Status: implemented, pending independent review by the root agent.
Review corrections applied: undo dependency guard with reverse-install-order
guidance, source-copy filtering of generated bindings, scoped legacy-compatibility
wording with a proven comparison, and public-document redaction.

## Objective

Let one machine keep several pinned builder roles installed at the same time, so a
root session running either Astra or Terra can pick an explicitly named builder for
a task instead of rewriting the single legacy worker.

## Non-goals

- No automatic selection, no parallel-writer fan-out, no model inference probe.
- No change to `config.toml`, credentials, Router state, root model, root effort or
  global `[agents]` defaults.
- No change to the legacy `astra_flash_builder` default path: `install.py` with no
  `--builder` behaves as before, including its `routing.json` binding.
- No dependency additions, no second agent CLI, no removal of files the package did
  not itself write.

## Contract

1. `install.py --builder PRESET` accepts one of six presets:
   `grok`, `fable`, `deepseek-flash`, `deepseek-pro`, `grok-4-5`, `ollama`.
2. Each preset maps to one stable native role id and one human-readable label:

| Preset | Native role id | Label | Default route |
| --- | --- | --- | --- |
| `grok` | `astra_terra_builder_grok` | Astra/Terra builder Grok | `grok-oauth/grok-4.6` |
| `fable` | `astra_terra_builder_fable` | Astra/Terra builder Fable | `openrouter/claude-fable-5.1` |
| `deepseek-flash` | `astra_terra_builder_deepseek_flash` | Astra/Terra builder DeepSeek Flash | `deepseek/deepseek-v4.1-flash` |
| `deepseek-pro` | `astra_terra_builder_deepseek_pro` | Astra/Terra builder DeepSeek Pro | `deepseek/deepseek-v4-pro` |
| `grok-4-5` | `astra_terra_builder_grok_4_5` | Astra/Terra builder Grok 4.5 | `grok-oauth/grok-4.5` |
| `ollama` | `astra_terra_builder_ollama` | Astra/Terra builder Ollama (local) | none; explicit local route on first install |

   Role ids contain no slash or space and match the pattern the host expects for an
   agent name.
3. Routes: Grok defaults to the 4.6 OAuth route, Fable is OpenRouter, Flash and Pro
   are the direct DeepSeek API routes, Grok 4.5 is the exact OAuth route, and Ollama
   is local-only.
4. `--worker-route` remains optional and, with `--builder`, is accepted only when it
   is compatible with that preset: `grok` allows 4.6 or 4.5; `fable`,
   `deepseek-flash`, `deepseek-pro` and `grok-4-5` allow their one exact route;
   `ollama` allows `local/<ollama-tag>` only, and requires it the first time.
5. Every route keeps the existing fail-closed contract: exactly one catalog entry,
   `multi_agent_version: "v2"`, and an effort that the route advertises. Any failure
   stops before the first write.
6. Bindings are per role: `builders/<role>.json` under the installed skill,
   separate from the legacy `routing.json`. Installing one builder never reads,
   rewrites or deletes another builder's binding or role file.
7. Installing one builder does not create, update or remove the legacy
   `astra_flash_builder` role or `routing.json`, and a legacy install does not touch
   `builders/`.
8. Existing different content is still refused without `--replace`; no role is
   overwritten silently.
9. Undo keeps its receipt checks and additionally allows only known roles and known
   bindings: `agents/<known role>.toml` and `builders/<known role>.json`.
10. The root may be Astra or Terra. Nothing in this package changes it, and no
    orchestration rule may spawn several writers automatically.

## Work items

| ID | Item | Deliverable |
| --- | --- | --- |
| N1 | Preset module | `scripts/builders.py`: presets, role ids, route compatibility, binding read/write |
| N2 | Installer | `--builder`, per-role target and binding, unchanged legacy path |
| N3 | Doctor | `--builder` reads the selected binding; default stays legacy |
| N4 | Undo | role/binding allowlist on top of the existing receipt checks |
| N5 | Tests | coexistence, isolation, per-builder doctor, undo order, fail-closed, mismatches, safe paths |
| N6 | Docs | README, POLICY, skill, references, install prompt, troubleshooting, example |
| N7 | Release | `VERSION` 1.4.0, `CHANGELOG.md`, `HISTORY.md`, regenerated `MANIFEST.sha256` |

## Verification (offline only)

```sh
python3 -B -m unittest discover -s tests -v
python3 -B skill/astra-flash-orchestrator/scripts/validate_plan.py examples/invoice-filter/plan.json
python3 -B scripts/release.py --check
```

All tests use synthetic temporary homes and a loopback HTTP fixture. No provider
account, credential or model request is involved, and no real installation is
modified.

## Limitations carried forward

- No route is runtime-verified by installation; delegation evidence belongs to the
  first separately authorized useful task.
- `grok-oauth/grok-4.5` is listed as `v1` in the published catalog, so the
  `grok-4-5` preset cannot install until the operator enables that route.
- No `local/*` entry is present in the published catalog, so the `ollama` preset
  needs the operator to enable and republish that exact model first.
- Python 3.11/3.12 interpreters are absent here, so the minimum runtime is covered
  by a grammar parse check.
