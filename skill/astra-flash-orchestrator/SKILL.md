---
name: astra-flash-orchestrator
description: Plan and execute substantial multi-file builds, features, migrations, and refactors with Astra as orchestrator and DeepSeek V4.1 Flash as the native Codex implementation worker. Use for phased planning and delegated build execution, including existing Superpowers or GSD plans. Skip trivial edits and explicitly single-agent tasks. Worker children must not invoke this orchestration skill.
---

# Astra plans. Flash implements. Astra accepts.

Use the existing Codex Router, not a second agent CLI or API client. This skill
provides the workflow; the custom agent and router select the worker model. Do
not claim routing is verified from these instructions or a worker's self-report.

## 1. Orient and classify

Read the relevant repository guidance and current request. Preserve existing
work. Decide whether this is a direct small fix, a bounded build, or a large
multi-phase project. Keep trivial edits with Astra; do not force this process
onto a typo or a simple question. For a substantial build, say what Astra will
own and what Flash will implement.

Use the user's existing approvals and decisions. An explicit request to plan and
build authorizes the in-scope workflow; it is not necessary to ask again after
every phase. Ask only about material unresolved product/risk decisions that
cannot be established from the repo. When asked to plan only, do not implement.

## 2. Confirm routing before delegating

Read `routing.json` in this installed skill and `references/routing.md`. Run the
read-only `scripts/doctor.py` with the same CODEX_HOME/profile used by the session.
Its output is a static configuration check, not an end-to-end model test.
Confirm the current ROOT is the user's selected GPT-6 Astra and that the native
`astra_flash_builder` role is available. Do not change the root model or effort.
Inspect project/CLI/UI/managed overrides that the doctor cannot resolve.

For an already-verified setup, reuse the verified configuration evidence rather
than repeating a paid smoke test per task. For a first routed task, use a small
real, useful implementation bundle and inspect host/router metadata afterward.
No fake model-name check and no silent fallback. If routing cannot be established,
finish the plan and report the execution blocker before delegating private work.

## 3. Design before dividing the work

Read `references/planning.md`. Reuse an approved design/spec and phase plan when
one exists. Superpowers, GSD, and custom plans are all valid inputs; do not create
a competing spec or force a framework migration.

For new work, produce an appropriately sized design covering objective,
non-goals, repo evidence, important alternatives, interfaces, failure behavior,
risks, and acceptance criteria. Put stable shared contracts ahead of dependent
implementation. Astra makes architecture, auth/security, tenancy, payments,
secrets, and production-impacting decisions; do not hand those decisions to
Flash under a vague "build it" prompt.

## 4. Produce a phase plan and executable briefs

Default artifact home: `docs/agent-work/<feature>/`. Follow an existing project
convention instead when one is established. Use the templates as needed.

Write a dependency-ordered phase plan. Each Flash assignment is one coherent,
reviewable bundle with exact contracts, a bounded file scope, testable outcomes,
and verification commands. Internal implementation/test steps stay with Flash;
Astra does not write the entire implementation in the plan. Long work is welcome
inside a clear contract, not across unknown architecture boundaries.

Separate tasks at independent review boundaries, not at every function or
five-minute step. A phase can contain multiple bundles; a bundle can contain
multiple test/code/fix cycles. Complete early phases first and refine later briefs
when earlier interfaces stabilize. If a machine-readable plan is useful, use
`templates/plan.json` and run
`scripts/validate_plan.py <plan.json> --repo-root <repository-root>` before launch.
That linter checks structure, not the truth or quality of the design.

## 5. Dispatch and let the worker work

Read `references/execution.md`. Use the host's actual native delegation tool with
the installed `astra_flash_builder` role. Do not invent a slash command or tool
signature. If the tool exposes explicit model selection, use the exact installed
worker slug. Do not use a default explorer/reviewer role that could override it.

Give the worker the full task brief plus the minimum shared context, required
contracts, task ID, working directory, baseline, and relevant dependency outputs.
Prefer a clean child context where the host supports it; never claim its context
is empty if the host actually inherits history. No unnecessary full-transcript
forking, duplicate repository investigation, or play-by-play log forwarding.

Default to ONE active Flash writer in the current workspace. A native subagent
is not automatically a Git worktree or a security sandbox. Astra must not edit
its claimed paths. Use two writers only when the plan explicitly identifies
independent work and each has a real, verified separate workspace. See execution
reference for dirty-tree, contract, and integration rules. No recursive agents.

Let the worker complete its internal implementation and testing loop. Use the
native wait/continuation facilities, not rapid polling or arbitrary early kills.
Set a task-appropriate budget and checkpoint rule rather than assuming every
job fits a fixed time estimate. Resume the same worker for review fixes; start a
fresh context for an unrelated bundle.

## 6. Review the actual result

Read `references/review.md`. Worker completion means **ready for review**, not
accepted. Astra reviews the actual patch against the captured baseline, including
untracked additions and pre-existing changes. Never treat HEAD as the baseline
without checking the workspace state.

Run two explicit passes: specification compliance, then code quality/security.
They can be separate passes by the root Astra; there is no requirement to buy two
additional reviewer agents. Run independent relevant checks, inspect UI behavior
visually when applicable, and distinguish genuine failures from environment
limitations. Default reviewer subagents would also route to Flash, so do not
mistake a default child for an independent Astra review.

Accept only after both passes and relevant verification succeed. Return precise
file-level feedback to the same worker when needed. After two rejected correction
cycles, diagnose with Astra and re-scope, split, or take over the difficult portion;
do not blindly keep retrying. Never silently switch model/provider.

## 7. Integrate, checkpoint, and finish

Astra integrates accepted dependencies in order, with the user's existing Git
permissions. Do not auto-commit, merge branches, push, deploy, or apply production
migrations just because a phase finished. Shared-workspace edits already exist in
the workspace; don't invent a branch merge. Separate-worktree integration needs
an explicit, reviewed operation and a valid common baseline.

Rerun cross-task checks after integration. Update the plan and a compact
`CHECKPOINT.md`: completed/accepted work, current diff/workspace, contract
decisions, pending tasks, worker thread IDs, review status, exact resume action.
Preserve evidence before context compaction. Do not repeatedly reload full logs.

Conclude with what was built, what actually passed, outstanding limits, and the
verified or unverified routing state. Never estimate cost savings from task counts
or durations. Use actual provider usage records when measuring costs.
