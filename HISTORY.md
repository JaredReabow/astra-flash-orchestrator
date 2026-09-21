# History

Append-only record for this package. Add new entries at the end and never edit or
delete an existing entry. `CHANGELOG.md` is the separate release-notes companion,
grouped by version; a change normally appears in both files. Entries before
2026-09-21 were not backfilled here and remain readable in `CHANGELOG.md`.

## 2026-09-21 — 1.3.0 multi-model worker routes

- Added `deepseek/deepseek-v4-pro`, `grok-oauth/grok-4.6`, `grok-oauth/grok-4.5`
  and `openrouter/claude-fable-5.1` as explicitly pinnable worker routes, plus a
  dynamic `local/<ollama-tag>` form. DeepSeek V4.1 Flash stays the default and the
  `astra_flash_builder` role name is unchanged so existing installations update.
- Kept the fail-closed contract for every route: one exact catalog entry, and
  `multi_agent_version: "v2"`, or installation stops without substituting a
  provider. `grok-oauth/grok-4.5` stays blocked because the published catalog
  lists it as `v1`.
- Refused Ollama cloud alias variants (`<model>:cloud`, `<model>:<size>b-cloud`)
  under the `local/` prefix. They are served from Ollama's cloud, so a local
  namespace must not be able to present them as on-machine inference.
- Root handling: the retained 1.2.0 guard still refuses a Flash root, and a root
  equal to the selected worker route is now a warning instead of an error. The
  root value is never rewritten.
- Recorded the route family (`flash`, `cloud`, `local`) in the report and the
  installed routing binding; the pinned effort is still validated against the
  route's advertised reasoning levels.
- Generalized Flash-only wording in the managed policy, skill, references, README,
  install prompt and troubleshooting.
- Added offline coverage for every new route, the binding round trip, malformed and
  unknown slugs, the `v1` rejection, cloud-alias refusal and the existing suite.
- Release bookkeeping: `VERSION` 1.3.0, a `CHANGELOG.md` section, this file added
  to the release inventory, and `MANIFEST.sha256` regenerated.

## 2026-09-21 — 1.3.0 acceptance corrections

- Same-model root handling corrected to a warning. A model may serve both roles,
  and a saved default is not proof of the model a running session uses, so the root
  is never rewritten. The 1.2.0 Flash-root refusal is retained deliberately and is
  now documented as the only forbidden root.
- Ollama cloud aliases are refused under `local/`. The Router's local-model capture
  marks these variants `cloud-only` and non-downloadable, and the same tag text
  would otherwise be able to render as a local slug.
- `HISTORY.md` created as the append-only companion to `CHANGELOG.md` and added to
  the release inventory; neither file is treated as a substitute for the other.
- Published documents redacted: machine-local paths and private root-configuration
  details removed, and the README clone instructions now point at this fork while
  keeping upstream attribution.
- Corrected the local-route statements: no `local/*` entry is present in the
  published catalog, and the Router's own default for a local entry is `v1`.
