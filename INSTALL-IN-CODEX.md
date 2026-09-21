# Install using Codex

Give Codex the location of this repository and the prompt below. This authorization covers only installation, not a real delegated task.

```text
Install the Astra-led worker workflow for Codex from this repository.

Use worker route deepseek/deepseek-v4.1-flash unless I explicitly name another
route documented in this repository (for example deepseek/deepseek-v4-pro,
grok-oauth/grok-4.6, grok-oauth/grok-4.5, openrouter/claude-fable-5.1, or a
configured local/<ollama-tag>). Do not infer, enable or auto-select a provider.

If I ask for named builders, install each one I name with
`install.py --builder <preset>` (grok, fable, deepseek-flash, deepseek-pro,
grok-4-5, ollama). Each install writes only that role's agent file and its own
builders/<role>.json; never rewrite another builder's binding, never delete an
existing role, and leave routing.json and astra_flash_builder alone unless I ask
for the legacy worker. My root model may be Astra or Terra; leave it as it is.
Do not install a builder I did not name.

Read README.md, install.py, POLICY.md and WORKER-INSTRUCTIONS.md first.
Inspect relevant local configuration without printing secrets, full private
Router URLs, authentication contents or unrelated instructions.

Preserve my current Astra root model and reasoning effort, existing Router,
config.toml, authentication, permissions and unrelated instructions. Do not
install another runtime, dependencies or Router, restart services, or quit Codex.
Do not add, change or remove [agents].default_subagent_model or
[agents].default_subagent_reasoning_effort. The package's named role pins its own
worker model and catalog-supported effort.

Verify Python 3.11+, native subagent/custom-role client support, and the selected
worker route in the effective configuration/catalog. Pass it to install.py with
--worker-route when it is not the direct DeepSeek default. The route must appear
exactly once in that catalog and advertise multi_agent_version v2; if it does not,
stop and report the prerequisite instead of choosing another route. A route that is
the same as my root model is allowed: continue, warn me, and leave my root alone.
Only a root that is itself a DeepSeek V4.1 Flash route is refused.
The default python3 may be older than 3.11; find an existing 3.11+ interpreter
such as python3.12 and use it for every command here. Do not install or upgrade a
runtime to satisfy this.
The package supports loopback /v1 and /_codex-router/<capability>/v1 endpoints.
If configuration is contradictory or unsupported, report the discrepancy.
Do not silently change models/providers or bypass preflight.
Never edit config.toml to make a preflight check pass. Report the discrepancy and
stop. Appending a table header such as [agents] to config.toml absorbs every
top-level key written after it and can stop Codex loading its config at all.

I will enter any provider API key myself through the Router's private local prompt.
Do not ask me to paste a key into chat, inspect credential contents, or enter a key
for me. Do not run subagents certify, test-model --live, a Router smoke test or any
other paid inference command during installation. If the selected route is not
already advertised with multi_agent_version v2, stop and report that prerequisite.

Run the offline tests, then install.py for a dry run. If they pass and the
proposed files match the documented scope, apply with install.py --apply.
I authorize installation of the personal skill, native astra_flash_builder role,
and scoped managed AGENTS policy exception. Retain repository restrictions,
explicit no-delegation instructions and managed security controls.

The role must pin the exact route I named, inherit sandbox/approvals and disable
nested agents. Do not invoke an external worker CLI. Run the static doctor after
installation.
An optional local catalog GET may fail when authentication is required; do not
read or alter credentials to make it pass, or present it as inference evidence.

Verify config/auth files and existing permissions are unchanged and unrelated
policy content is preserved. Report installed paths, root/worker settings,
test results, undo receipt and remaining runtime limitations.

Do not launch workers, run paid inference, commit, push or deploy during setup.
Explain that I should fully quit/reopen the host app and start an Astra session and invoke
$astra-flash-orchestrator. Actual route verification belongs to the first
separately authorized useful task, using host/router metadata.
```
