<!-- BEGIN astra-flash-orchestrator managed policy -->
## Astra-led planning and Flash implementation

For substantial builds, multi-file features, migrations, or refactors, load
`$astra-flash-orchestrator` before implementation. Keep GPT-6 Astra as the root
planner, architect, reviewer, and integrator. Delegate well-specified implementation
bundles to the native `astra_flash_builder` agent through the existing Codex Router.
Use one Flash writer by default; do not create an agent for each tiny coding step.
Prefer this native workflow over an older `flash-build` external-runner skill for
the same task; do not load both execution paths.

This is a scoped exception to generic personal defaults such as "one agent" or
"no workers" in this instruction file. Keep those defaults for trivial changes,
unrelated work, and tasks explicitly requested without delegation. It does not
supersede a current user prohibition, repository restrictions, or managed policy.
A Flash child executes its assigned brief; it must not load the orchestration
workflow or delegate further.

Reuse an existing approved spec/plan, including Superpowers or GSD artifacts.
Otherwise establish scope and contracts, plan dependency-ordered phases, then
execute and review each task bundle. Do not repeat approval questions already
resolved by the user's instruction. Material scope changes still need resolution.
Keep final review and sensitive architecture decisions with Astra.

Do not switch the root to Flash, silently fall back to a different worker model,
launch another agent CLI, loosen permissions, expose secrets, auto-commit,
push, deploy, or start paid setup smoke tests. Normal delegated implementation
uses the configured DeepSeek provider; obey the user's data-sharing and spending
restrictions. Installation is not evidence of a successful routed model request.
<!-- END astra-flash-orchestrator managed policy -->
