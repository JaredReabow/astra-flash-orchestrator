# Example: three named builders side by side

A root session running Astra or Terra can keep several builders installed and name
one per task. This example installs the three requested roles against routes that
are already configured in the local Codex Router catalog.

Run from the repository root. Each command previews first; add `--apply` to write.

```sh
# Grok OAuth 4.6 -> astra_terra_builder_grok
python3 -B install.py --builder grok --replace
python3 -B install.py --builder grok --replace --apply

# OpenRouter Claude Fable -> astra_terra_builder_fable
python3 -B install.py --builder fable --replace
python3 -B install.py --builder fable --replace --apply

# Direct DeepSeek V4.1 Flash -> astra_terra_builder_deepseek_flash
python3 -B install.py --builder deepseek-flash --replace
python3 -B install.py --builder deepseek-flash --replace --apply
```

Each install writes one agent file and one binding, and leaves the others alone:

```text
$CODEX_HOME/agents/astra_terra_builder_grok.toml
$CODEX_HOME/agents/astra_terra_builder_fable.toml
$CODEX_HOME/agents/astra_terra_builder_deepseek_flash.toml
~/.agents/skills/astra-flash-orchestrator/builders/astra_terra_builder_grok.json
~/.agents/skills/astra-flash-orchestrator/builders/astra_terra_builder_fable.json
~/.agents/skills/astra-flash-orchestrator/builders/astra_terra_builder_deepseek_flash.json
```

Check one role, or pre-check a route before installing it:

```sh
python3 -B skill/astra-flash-orchestrator/scripts/doctor.py --builder grok
python3 -B skill/astra-flash-orchestrator/scripts/doctor.py --builder grok --worker-route grok-oauth/grok-4.5
```

The optional `--worker-route` only refines the preset it is paired with. The two
extra requested options follow the same pattern:

```sh
# DeepSeek V4 Pro -> astra_terra_builder_deepseek_pro
python3 -B install.py --builder deepseek-pro --replace --apply

# Grok 4.5 -> astra_terra_builder_grok_4_5 (needs that route advertised as v2)
python3 -B install.py --builder grok-4-5 --replace --apply

# Local Ollama -> astra_terra_builder_ollama (name the model the first time)
python3 -B install.py --builder ollama --worker-route local/qwen3.8:27b-mlx --replace --apply
```

`builders.json` in this folder is the reference table for the presets; a test
asserts it matches the installer's own module. The installer never enables a
provider, never runs inference, and never rewrites the root model or another
builder's binding.
