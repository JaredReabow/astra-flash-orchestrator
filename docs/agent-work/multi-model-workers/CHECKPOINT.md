# Multi-model worker checkpoint

Accepted after root review on 2026-09-21. Version 1.3.0 adds explicit worker
selection for DeepSeek V4 Pro, Grok 4.6/4.5 OAuth, Fable 5.1 and configured
local Ollama routes. Flash remains the default.

## Validation

- 82 offline tests passed on Python 3.14 and 3.13.
- Release inventory, archive creation, plan validation and diff checks passed.
- Root review covered installer changes, route validation, test coverage,
  configuration preservation, documentation and publication contents.
- No provider smoke tests or real installation changes were performed.

## Operational limits

Every route must appear exactly once in the configured catalog and advertise
native subagent v2 support. The observed Grok 4.5 entry was v1; no local Ollama
entry was present. Those are Router prerequisites, not installer overrides.
Python 3.11 grammar compatibility was checked, but no 3.11 runtime was available.

## Resume

Use README.md for preview/apply commands from the repository root. Existing
installations require --replace when package-owned files differ. No active
installation was upgraded during this repository task.
