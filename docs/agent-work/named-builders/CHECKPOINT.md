# Checkpoint: named builders

Resumable state for this bundle. Written by the implementation worker for the root
agent's review.

## Status

Accepted after root review. The Grok, Fable and DeepSeek Flash roles were
installed side by side and each passed the installed static doctor. Root config,
legacy role and binding, and unrelated personal instructions were preserved.
The suite passed 104 tests on Python 3.13 and 3.14. Native role discovery needs
a refreshed host session; no inference check was performed for the new roles.

## Completed

- `--builder` presets and the centralized preset module
  (`scripts/builders.py`): role ids, labels, permitted routes, binding locations.
- Per-role bindings at `builders/<role>.json`, separate from the legacy
  `routing.json`. Legacy compatibility is scoped to the CLI path, role name,
  binding location, pinning rules and undo semantics: the generated `routing.json`
  matched the previous release byte for byte, while the role file changed only in
  the worker-instruction text this release updated.
- Undo refuses to restore the shared skill or policy while another installed role
  or binding would be left behind, and tells the operator to undo in reverse
  install order; role-only receipts are never blocked.
- The installer filters generated binding files out of the source copy, so a stray
  `routing.json` or `builders/*.json` in a checkout cannot overwrite an installed
  binding.
- `doctor.py --builder`, undo allowlisting, and coverage for coexistence,
  isolation, undo order, fail-closed routes, mismatches and safe paths.
- Docs, managed policy, skill references, install prompt, troubleshooting, an
  example folder, `CHANGELOG.md`, `HISTORY.md` and `VERSION` 1.4.0.

## Unfinished or unverified

- No live inference on any builder; runtime routing evidence is still outstanding.
- `grok-4-5` cannot install while the published catalog lists `grok-oauth/grok-4.5`
  as `v1`; `ollama` needs an enabled `local/<tag>` entry first.
- Python 3.11/3.12 interpreters are not installed here, so only the 3.11 grammar
  parse check was run.

## Exact resume action

1. From the repository root, review the working-tree diff, including the new
   `scripts/builders.py`, `examples/named-builders/` and this bundle's documents.
2. Re-run the offline harness and release checks from `PLAN.md`.
3. Refresh the host session and choose one of the installed named builders.
   Use the installed doctor with --builder to recheck its binding when needed.

## Evidence logs

`docs/agent-work/named-builders/logs/` holds the read-only previews and doctor
runs, including the static-ready results for the requested builders. Those files
are `.gitignore`d and are not part of the release inventory; they contain
machine-local paths, so treat them as private.
