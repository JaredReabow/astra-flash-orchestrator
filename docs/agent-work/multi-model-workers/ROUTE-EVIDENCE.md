# Route namespace evidence

Read-only inspection of the installed Codex Router and its published catalog on
this machine. No provider request, credential read or configuration write was
performed. Private capability URLs, tokens and account identifiers are not
reproduced here.

## Where the names come from

- Reviewed cloud routes are directory-scoped model files in the Router
  configuration, for example `config/grok/oauth/grok-4.6.json`,
  `config/deepseek/deepseek-v4-pro.json` and
  `config/openrouter/claude-fable-5.1.json`. Each file carries the public `slug`
  the catalog publishes.
- Provider display names come from the matching provider config
  (`config/deepseek/deepseek.json`: "DeepSeek API", `config/grok/grok.json`:
  "xAI Grok OAuth", `config/openrouter/openrouter.json`: "OpenRouter",
  `config/local/local.json`: "Local (Ollama)").
- Local Ollama routes are dynamic. `src/user-models.mjs` builds the public slug as
  `${providerId}/${publicId}` for the provider id `local`, so the route is
  `local/<ollama-tag>` with the operator's own tag as the variable part. The tag
  grammar is `src/local-model-ref.mjs`: a first alphanumeric character, then
  `[A-Za-z0-9._/-]`, an optional `:variant`, no doubled slash.

## Published catalog snapshot

From the catalog the active configuration points at (`model_catalog_json`), as
read on 2026-09-21. The installer reads this file at run time; these values are
evidence for the contract, not a hard-coded allowlist.

| Route | `multi_agent_version` | `visibility` | Default effort | Supported efforts |
| --- | --- | --- | --- | --- |
| `deepseek/deepseek-v4.1-flash` | v2 | list | high | low, high, max |
| `deepseek/deepseek-v4-pro` | v2 | list | high | high, max |
| `grok-oauth/grok-4.6` | v2 | list | high | low, medium, high, xhigh |
| `grok-oauth/grok-4.5` | **v1** | hide | high | low, medium, high |
| `openrouter/claude-fable-5.1` | v2 | list | high | low, medium, high, xhigh, max |
| `local/<tag>` | not published | - | - | - |

## Why Grok 4.5 is v1 here

`config/grok/oauth/grok-4.5.json` does declare `multiAgentVersion: "v2"`, but the
effective catalog still publishes the route as `v1` with `visibility: "hide"`.
The Router's promotion path (`src/multi-agent-state.mjs`) forces any hidden or
disabled slug back to `v1` before publication, and only an explicit operator
selection clears that. The installer therefore must not treat a checked-in
registry entry as sufficient: it has to read the catalog entry the session will
actually use. This is exactly the "must remain blocked unless enabled properly"
case in the brief.

## Local models

No `local/*` entry is present in the current published catalog, and the Router's
own default for a local entry is `v1` (`src/local-models.mjs` writes
`multiAgentVersion: "v1"` on purpose). A local route therefore validates as a
*known* route shape but is refused by the `v2` gate until the operator enables that
exact model in the Router. The package accepts the manual promotion and never
performs it.

## Cloud aliases inside the local namespace

`src/local-ollama-catalog.mjs` captures Ollama's cloud alias variants in the
local-model manifest with `codex: "cloud-only"` and `downloadable: false`:
`gemma4:cloud`, `nemotron-3-super:cloud`, `gemma4:31b-cloud`,
`qwen3.5:397b-cloud` and similar. They are served by Ollama's cloud service and
have no weights on this machine, yet the Router's slug builder would still render
either a local or a cloud provider prefix from the same tag text. `local/` is a
namespace, not proof of where inference runs, so this package refuses those two
variant shapes under `local/` and points the operator at the `ollama-cloud`
provider route instead.

## What this changed in the package

- `SUPPORTED_ROUTES` in `local_config.py` gained the four reviewed cloud slugs,
  and `local/<tag>` is validated by the Router's own tag grammar instead of a
  hard-coded list.
- `local/<model>:cloud` and `local/<model>:<size>b-cloud` are refused with a
  dedicated message rather than being accepted as on-machine routes.
- Provider display names follow the Router's provider configuration so the
  installed binding and doctor output describe the same route the Router does.
