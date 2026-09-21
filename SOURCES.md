# Sources and provenance

Public documentation checked September 20, 2026. These are original package
instructions and utilities, not a copy or distribution of Superpowers or Codex
Router. Upstream documentation and local client behavior may change independently.

## Official Codex documentation

- [Build skills](https://learn.chatgpt.com/docs/build-skills): local skill layout,
  user discovery under ~/.agents/skills, explicit/implicit invocation, metadata.
- [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents): child
  model defaults, custom agent configuration and model precedence, native roles.
- [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference):
  model_catalog_json, user configuration and profile considerations.
- [Codex customization](https://developers.openai.com/codex/customization/overview):
  distinction between durable AGENTS guidance, skills, external tools and agents.

## Primary project/vendor documentation

- [Codex Router repository](https://github.com/duolahypercho/codex-router): published
  provider-specific model IDs, preserved native routing, local catalog/URL setup.
- [Codex Router V4.1 Flash route tests](https://github.com/duolahypercho/codex-router/blob/main/test/deepseek-v4-1-flash.test.mjs):
  reviewed provider slugs and upstream model mappings for DeepSeek, OpenRouter,
  opencode Go, Command Code, Nous Research and Ollama Cloud.
- [Codex Router route registry](https://github.com/duolahypercho/codex-router/tree/main/config):
  per-provider model slugs, including `deepseek/deepseek-v4-pro`,
  `grok-oauth/grok-4.6`, `grok-oauth/grok-4.5` and `openrouter/claude-fable-5.1`,
  checked locally September 21, 2026.
- [Codex Router local model reference](https://github.com/duolahypercho/codex-router/blob/main/src/local-model-ref.mjs):
  the Ollama tag grammar this package mirrors when validating a dynamic
  `local/<ollama-tag>` worker route.
- [Codex Router subagent state](https://github.com/duolahypercho/codex-router/blob/main/src/multi-agent-state.mjs):
  a hidden or disabled route is republished as `multi_agent_version: "v1"`, which
  is why the installer reads the effective catalog rather than a checked-in
  registry entry.
- [Codex Router installation guide](https://github.com/duolahypercho/codex-router/blob/main/docs/INSTALL.md):
  health/doctor process and explicit paid smoke-test distinction.
- [DeepSeek models](https://api-docs.deepseek.com/quick_start/pricing/): direct API
  name deepseek-flash and the documented V4.1 Flash version association.
- [OpenRouter DeepSeek V4.1 Flash](https://openrouter.ai/deepseek/deepseek-v4.1-flash):
  OpenRouter model identity, provider routing and tool support.
- [Superpowers brainstorming](https://github.com/obra/superpowers/blob/main/skills/brainstorming/SKILL.md):
  discovery/design before implementation.
- [Superpowers writing-plans](https://github.com/obra/superpowers/blob/main/skills/writing-plans/SKILL.md):
  explicit file/contracts/tests and independently reviewable deliverables.
- [Superpowers subagent-driven-development](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md):
  bounded implementer context, task review and broad final review.

## Provenance

The package contains original workflow instructions and Python utilities. Its design was informed by a private prototype review and the public references above. Private attachments, prototype runner code, local configuration and personal review notes are not distributed. Upstream projects are referenced, not bundled or relicensed.

## Fork

This fork is maintained at `https://github.com/JaredReabow/astra-flash-orchestrator`.
It tracks upstream `https://github.com/ethanplusai/astra-flash-orchestrator` and
keeps that project's attribution and license.
