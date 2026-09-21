# Validation evidence

Version 1.3.0. Offline suite checked September 21, 2026 on macOS with Python
3.14.7, and repeated with Python 3.13.14. No provider account, credential or model
request was involved.

## Verified

- 82 offline tests passed, up from 63 in 1.2.0. Coverage includes installation dry
  runs, idempotence, original configuration preservation, scoped policy handling,
  profile/collision/symlink checks, URL validation, fake-secret redaction,
  generated role TOML, rollback, guarded undo, plan validation and release-file
  filtering.
- Every reviewed worker route is accepted only when explicitly selected or
  preserved from an existing valid package binding and advertised as
  `multi_agent_version: "v2"`. Tests cover each new route
  (`deepseek/deepseek-v4-pro`, `grok-oauth/grok-4.6`, `grok-oauth/grok-4.5`,
  `openrouter/claude-fable-5.1`), OpenRouter role generation, remembered update
  behavior, unreviewed-route rejection, uncertified-route rejection and refusal to
  fall back from direct DeepSeek to an available alternate provider.
- Dynamic `local/<ollama-tag>` routes are validated against the Router's tag
  grammar, round-trip through the generated routing binding, and are refused when
  the catalog still publishes that model as `v1`. Ollama cloud aliases
  (`<model>:cloud`, `<model>:<size>b-cloud`) are refused under `local/` with their
  own message, and names that merely contain "cloud" stay usable. Malformed local
  shapes and unknown cloud slugs are refused before any file is written, and the
  refusal names the accepted routes.
- `grok-oauth/grok-4.5` is blocked at `v1` and installs once the same fixture
  advertises it as `v2`, which is the documented "enable it properly first" case.
- The root guard refuses a Flash root and preserves config bytes for every other
  root model, including a non-Flash root. A root equal to the selected worker route
  is allowed and reported as a warning instead of an error. Config, effort,
  provider URL and permissions are asserted unchanged in those tests.
- Native `/v1` and capability-path Router configurations are accepted; non-loopback hosts and unsupported URL shapes are rejected.
- Existing backup-directory permissions are preserved, backup files and caches are
  excluded from skill installation, and release tests also cover private artifact
  exclusion, symlink rejection and inventory changes.
- The static doctor was additionally run read-only against a local Codex Router
  configuration: each newly supported route was either reported `static-ready` or
  refused with its documented reason (`v1`, absent from the published catalog, a
  cloud alias, or an unknown slug), and a same-model root reported the warning
  instead of a refusal. Those runs read configuration only; nothing was written and
  no request reached a provider.
- All seven Python files parse under the Python 3.11 grammar via
  `ast.parse(..., feature_version=(3, 11))`. A real 3.11 or 3.12 interpreter is not
  installed on this machine, so the suite itself was not re-run on the documented
  minimum runtime.

All tests use synthetic configuration, temporary directories and a loopback HTTP
fixture. Other operating systems have not been tested here.

## Prior local installation evidence

The 1.2.0 package was installed in a macOS Codex setup and its static configuration
checks passed; root configuration and authentication bytes were preserved. Its
optional unauthenticated local catalog GET was rejected. The 1.3.0 installer is
verified with synthetic homes and read-only static runs; this report does not claim
it was applied to that real installation.

## Still unverified

Actual delegated inference through any route, native role loading for a non-Flash
route in a fresh session, provider request attribution, long-running build quality
and cost savings remain unverified for this candidate. A static report, a model
catalog entry, or a worker naming itself cannot establish these facts.

Validate real routing during the first authorized useful task, using host/router request metadata. Do not run an extra paid test as part of installation, and do not publish raw private logs or local configuration as evidence.
