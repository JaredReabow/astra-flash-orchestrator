from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skill' / 'astra-flash-orchestrator' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))
import install
import builders
from local_config import (
    DEFAULT_ROUTE, FLASH_ROUTES, MULTI_MODEL_ROUTES, ROUTE, ROLE, SKILL, SUPPORTED_ROUTES,
    SetupError, inspect, local_route_cloud_variant, model_entries, require_route,
    resolve_worker_route, route_family, route_hint, route_provider,
)
from validate_plan import PlanError, validate


class _Fixture(unittest.TestCase):
    """Synthetic home, config and catalog shared by more than one test case."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name).resolve()
        self.codex = self.home / '.codex'
        self.codex.mkdir()
        self.config = self.codex / 'config.toml'
        self.config.write_text(
            '# Preserve my exact config and comments.\n'
            'model = "fixture-astra-root"\nmodel_reasoning_effort = "medium"\n'
            'openai_base_url = "http://127.0.0.1:4202/_codex-router/TEST_PRIVATE_CAPABILITY/v1"\n'
            'model_catalog_json = "catalog.json"\n'
            '[model_providers.unused]\nexperimental_bearer_token = "TEST_SECRET_KEY"\n'
        )
        self.catalog = self.codex / 'catalog.json'
        self.catalog.write_text(json.dumps({'models': [{
            'slug': ROUTE, 'multi_agent_version': 'v2', 'default_reasoning_level': 'high',
            'supported_reasoning_levels': [{'effort': 'high'}, {'effort': 'max'}]
        }]}))
        self.policy = self.codex / 'AGENTS.md'
        self.policy.write_text('# Existing instructions\nUse one agent by default.\nPreserve my unrelated notes.\n')
        self.original_config = self.config.read_bytes()
        self.original_policy = self.policy.read_bytes()

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'install.py'), '--home', str(self.home),
                               '--codex-home', str(self.codex), *args], capture_output=True, text=True)

    def report(self):
        return inspect(self.home, self.codex)[0]

    def set_catalog_route(self, route, multi_agent_version='v2'):
        payload = json.loads(self.catalog.read_text())
        payload['models'][0]['slug'] = route
        payload['models'][0]['multi_agent_version'] = multi_agent_version
        self.catalog.write_text(json.dumps(payload))

    def changes(self, **kwargs):
        return install.plan_changes(self.home, self.codex, self.report(), kwargs.get('policy', True), kwargs.get('replace', False))

    def apply(self):
        report = self.report()
        changes = install.plan_changes(self.home, self.codex, report, True, False)
        return install.apply_changes(changes, self.codex, report['input_hashes'])


class SetupFixture(_Fixture):
    def test_dry_run_changes_nothing_and_redacts_secrets(self):
        before = {str(p): p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        after = {str(p): p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertNotIn('TEST_PRIVATE_CAPABILITY', result.stdout + result.stderr)
        self.assertNotIn('TEST_SECRET_KEY', result.stdout + result.stderr)

    def test_install_preserves_config_and_adds_narrow_policy(self):
        result = self.cli('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.assertTrue(self.policy.read_bytes().startswith(self.original_policy))
        self.assertIn(b'scoped exception', self.policy.read_bytes())
        role = tomllib.loads((self.codex / 'agents' / f'{ROLE}.toml').read_text())
        self.assertEqual(role['model'], ROUTE)
        self.assertEqual(role['model_reasoning_effort'], 'high')
        self.assertFalse(role['agents']['enabled'])
        self.assertNotIn('sandbox_mode', role)
        self.assertNotIn('model_provider', role)
        self.assertIn('No model request was made', result.stdout)

    def test_supported_worker_routes_are_selected_explicitly(self):
        for route, provider in SUPPORTED_ROUTES.items():
            with self.subTest(route=route):
                self.set_catalog_route(route)
                report, _ = inspect(self.home, self.codex, worker_route=route)
                self.assertEqual(report['worker_model'], route)
                self.assertEqual(report['worker_provider'], provider)

    def test_openrouter_route_is_pinned_in_role_and_routing_binding(self):
        route = 'openrouter/deepseek-v4.1-flash'
        self.set_catalog_route(route)
        result = self.cli('--worker-route', route, '--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        role = tomllib.loads((self.codex / 'agents' / f'{ROLE}.toml').read_text())
        self.assertEqual(role['model'], route)
        routing = json.loads(
            (self.home / '.agents' / 'skills' / SKILL / 'routing.json').read_text()
        )
        self.assertEqual(routing['worker_model'], route)
        self.assertEqual(routing['worker_provider'], 'OpenRouter')

    def test_required_multi_model_routes_are_registered_without_losing_flash(self):
        for route in ('deepseek/deepseek-v4-pro', 'grok-oauth/grok-4.6',
                      'grok-oauth/grok-4.5', 'openrouter/claude-fable-5.1'):
            with self.subTest(route=route):
                self.assertIn(route, MULTI_MODEL_ROUTES)
                self.assertIn(route, SUPPORTED_ROUTES)
                self.assertIsNotNone(route_provider(route))
        self.assertEqual(DEFAULT_ROUTE, ROUTE)
        self.assertEqual(SUPPORTED_ROUTES[DEFAULT_ROUTE], 'DeepSeek API')
        self.assertIn(DEFAULT_ROUTE, FLASH_ROUTES)
        self.assertEqual(len(FLASH_ROUTES), 6)
        self.assertEqual(route_family(DEFAULT_ROUTE), 'flash')

    def test_each_multi_model_route_pins_its_model_provider_and_family(self):
        for route, provider in MULTI_MODEL_ROUTES.items():
            with self.subTest(route=route):
                self.set_catalog_route(route)
                report, _ = inspect(self.home, self.codex, worker_route=route)
                self.assertEqual(report['worker_model'], route)
                self.assertEqual(report['worker_provider'], provider)
                self.assertEqual(report['worker_route_family'], 'cloud')
                self.assertEqual(report['worker_effort'], 'high')

    def test_multi_model_route_is_pinned_in_role_and_binding(self):
        route = 'deepseek/deepseek-v4-pro'
        self.set_catalog_route(route)
        result = self.cli('--worker-route', route, '--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        role = tomllib.loads((self.codex / 'agents' / f'{ROLE}.toml').read_text())
        self.assertEqual(role['model'], route)
        self.assertEqual(role['name'], ROLE)
        routing = json.loads(
            (self.home / '.agents' / 'skills' / SKILL / 'routing.json').read_text()
        )
        self.assertEqual(routing['worker_model'], route)
        self.assertEqual(routing['worker_provider'], 'DeepSeek API')
        self.assertEqual(routing['worker_route_family'], 'cloud')
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_local_route_roundtrips_through_the_installed_binding(self):
        route = 'local/qwen3.8:27b-mlx'
        self.set_catalog_route(route)
        first = self.cli('--worker-route', route, '--apply')
        self.assertEqual(first.returncode, 0, first.stderr)
        role = tomllib.loads((self.codex / 'agents' / f'{ROLE}.toml').read_text())
        self.assertEqual(role['model'], route)
        binding = self.home / '.agents' / 'skills' / SKILL / 'routing.json'
        routing = json.loads(binding.read_text())
        self.assertEqual(routing['worker_model'], route)
        self.assertEqual(routing['worker_provider'], 'Local (Ollama)')
        self.assertEqual(routing['worker_route_family'], 'local')
        second = self.cli('--apply')
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn('no changes needed', second.stdout)
        # The doctor path with no explicit route resolves it from the binding.
        report, _ = inspect(self.home, self.codex, worker_route=resolve_worker_route(binding=binding))
        self.assertEqual(report['worker_model'], route)
        self.assertEqual(report['worker_route_family'], 'local')
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_local_route_is_blocked_while_the_router_publishes_it_as_v1(self):
        # The Router intentionally publishes local Ollama entries as v1.
        self.set_catalog_route('local/qwen3.8:27b-mlx', 'v1')
        result = self.cli('--worker-route', 'local/qwen3.8:27b-mlx', '--apply')
        self.assertEqual(result.returncode, 2)
        self.assertIn('local/qwen3.8:27b-mlx', result.stderr)
        self.assertIn('not advertised for native subagents', result.stderr)
        self.assertFalse((self.home / '.agents').exists())
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_local_route_shape_is_validated_before_the_catalog(self):
        for route in ('local/', 'local', 'local//x', 'local/../config', 'local/-model',
                      'local/a b', 'local/a::b', 'local/a:b:c', 'local/.hidden'):
            with self.subTest(route=route):
                with self.assertRaisesRegex(SetupError, 'Unsupported worker route'):
                    require_route(route)

    def test_local_route_shape_accepts_the_router_tag_grammar(self):
        for route, provider in {'local/gemma4:12b': 'Local (Ollama)',
                                'local/hf.co/user/repo:Q4_K_M': 'Local (Ollama)',
                                'local/qwen3.8:27b-mlx': 'Local (Ollama)'}.items():
            with self.subTest(route=route):
                self.assertEqual(require_route(route), route)
                self.assertEqual(route_provider(route), provider)
                self.assertEqual(route_family(route), 'local')

    def test_grok_45_stays_blocked_at_v1_and_installs_once_advertised_as_v2(self):
        route = 'grok-oauth/grok-4.5'
        self.set_catalog_route(route, 'v1')
        blocked = self.cli('--worker-route', route, '--apply')
        self.assertEqual(blocked.returncode, 2)
        self.assertIn(route, blocked.stderr)
        self.assertIn('multi_agent_version must be v2', blocked.stderr)
        self.assertFalse((self.home / '.agents').exists())
        self.set_catalog_route(route, 'v2')
        installed = self.cli('--worker-route', route, '--apply')
        self.assertEqual(installed.returncode, 0, installed.stderr)
        role = tomllib.loads((self.codex / 'agents' / f'{ROLE}.toml').read_text())
        self.assertEqual(role['model'], route)
        self.assertEqual(role['model_reasoning_effort'], 'high')

    def test_unknown_or_malformed_route_is_refused_before_any_write(self):
        for route in ('custom/deepseek-v4.1-flash', 'grok-oauth/grok-9.9', 'deepseek/v4-pro',
                      'DEEPSEEK/deepseek-v4-pro', 'local', ''):
            with self.subTest(route=route):
                result = self.cli('--worker-route', route)
                self.assertEqual(result.returncode, 2)
                self.assertIn('Unsupported worker route', result.stderr)
                self.assertFalse((self.home / '.agents').exists())

    def test_non_flash_root_is_preserved_when_the_worker_route_differs(self):
        # The operator's real configuration can root on another reviewed route.
        self.config.write_text(self.config.read_text().replace('fixture-astra-root', 'grok-oauth/grok-4.6'))
        self.set_catalog_route('deepseek/deepseek-v4-pro')
        original = self.config.read_bytes()
        result = self.cli('--worker-route', 'deepseek/deepseek-v4-pro', '--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_bytes(), original)
        role = tomllib.loads((self.codex / 'agents' / f'{ROLE}.toml').read_text())
        self.assertEqual(role['model'], 'deepseek/deepseek-v4-pro')

    def test_root_equal_to_the_selected_worker_route_warns_and_installs(self):
        # One model may legally serve both roles, and the saved default is not
        # proof of the model a running session uses. Warn; never rewrite the root.
        route = 'grok-oauth/grok-4.6'
        self.config.write_text(self.config.read_text().replace('fixture-astra-root', route))
        self.set_catalog_route(route)
        original = self.config.read_bytes()
        report, _ = inspect(self.home, self.codex, worker_route=route)
        self.assertEqual(report['root_model_observed'], route)
        self.assertTrue(any('also the selected worker route' in w for w in report['warnings']))
        result = self.cli('--worker-route', route, '--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('also the selected worker route', result.stdout)
        self.assertEqual(self.config.read_bytes(), original)
        role = tomllib.loads((self.codex / 'agents' / f'{ROLE}.toml').read_text())
        self.assertEqual(role['model'], route)

    def test_local_cloud_aliases_are_refused_as_local_routes(self):
        # Ollama serves these alias variants from its cloud: `:cloud` and
        # `:<size>b-cloud` carry no weights on this machine, so a local/ slug
        # must not be able to mislabel them as local inference.
        for route, variant in {'local/model:cloud': 'cloud',
                               'local/model:123b-cloud': '123b-cloud',
                               'local/gemma4:cloud': 'cloud',
                               'local/qwen3.5:397b-cloud': '397b-cloud',
                               'local/nemotron-3-super:cloud': 'cloud'}.items():
            with self.subTest(route=route):
                self.assertEqual(local_route_cloud_variant(route), variant)
                with self.assertRaisesRegex(SetupError, 'cloud alias'):
                    require_route(route)
                self.assertIsNone(route_provider(route))
                self.assertIsNone(route_family(route))

    def test_local_cloud_alias_is_refused_before_any_write(self):
        self.set_catalog_route('local/model:cloud')
        result = self.cli('--worker-route', 'local/model:cloud', '--apply')
        self.assertEqual(result.returncode, 2)
        self.assertIn('cloud alias', result.stderr)
        self.assertIn('ollama-cloud provider route', result.stderr)
        self.assertFalse((self.home / '.agents').exists())
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_local_routes_that_only_look_like_cloud_aliases_are_allowed(self):
        for route in ('local/cloud', 'local/model-cloud', 'local/cloudy:12b', 'local/model:cloudy'):
            with self.subTest(route=route):
                self.assertIsNone(local_route_cloud_variant(route))
                self.assertEqual(require_route(route), route)
                self.assertEqual(route_family(route), 'local')

    def test_effort_that_the_route_does_not_support_is_refused(self):
        self.catalog.write_text(json.dumps({'models': [{
            'slug': ROUTE, 'multi_agent_version': 'v2', 'default_reasoning_level': 'xhigh',
            'supported_reasoning_levels': [{'effort': 'low'}, {'effort': 'high'}]
        }]}))
        with self.assertRaisesRegex(SetupError, 'not listed in the supported efforts'):
            self.report()

    def test_duplicate_catalog_route_is_refused(self):
        payload = json.loads(self.catalog.read_text())
        payload['models'].append(dict(payload['models'][0]))
        self.catalog.write_text(json.dumps(payload))
        with self.assertRaisesRegex(SetupError, 'missing or duplicated'):
            self.report()

    def test_existing_alternate_binding_is_reused_on_update(self):
        route = 'openrouter/deepseek-v4.1-flash'
        self.set_catalog_route(route)
        first = self.cli('--worker-route', route, '--apply')
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.cli('--apply')
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn('no changes needed', second.stdout)
        role = tomllib.loads((self.codex / 'agents' / f'{ROLE}.toml').read_text())
        self.assertEqual(role['model'], route)

    def test_default_route_does_not_fall_back_to_available_alternate(self):
        self.set_catalog_route('openrouter/deepseek-v4.1-flash')
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn(ROUTE, result.stderr)
        self.assertIn('No provider was substituted', result.stderr)
        self.assertFalse((self.home / '.agents').exists())

    def test_unreviewed_worker_route_is_rejected(self):
        with self.assertRaisesRegex(SetupError, 'Unsupported worker route'):
            inspect(self.home, self.codex, worker_route='custom/deepseek-v4.1-flash')

    def test_planned_writes_never_include_config(self):
        self.assertNotIn(self.config, {change['path'] for change in self.changes()})

    def test_install_excludes_local_backup_and_cache_artifacts(self):
        source = self.home / 'synthetic-skill'
        source.mkdir()
        for name in ['SKILL.md', 'helper.py', 'helper.py.before-v1-compat', '.DS_Store', 'helper.pyc', 'helper.bak']:
            (source / name).write_text('fixture')
        with patch.object(install, 'SKILL_SOURCE', source):
            changes = self.changes()
        names = {change['path'].name for change in changes}
        self.assertIn('helper.py', names)
        self.assertFalse(names & {'helper.py.before-v1-compat', '.DS_Store', 'helper.pyc', 'helper.bak'})

    def test_install_is_idempotent(self):
        self.apply()
        before = {str(p): p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        result = self.cli('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        after = {str(p): p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertIn('no changes needed', result.stdout)

    def test_no_policy_option(self):
        result = self.cli('--apply', '--no-policy')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.policy.read_bytes(), self.original_policy)

    def test_existing_override_file_is_the_policy_target(self):
        override = self.codex / 'AGENTS.override.md'
        override.write_text('Keep this active override.\n')
        self.apply()
        self.assertIn(install.BEGIN, override.read_bytes())
        self.assertEqual(self.policy.read_bytes(), self.original_policy)

    def test_install_does_not_require_global_subagent_default(self):
        result = self.cli('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_different_global_subagent_default_is_ignored(self):
        self.config.write_text(self.config.read_text() + '\n[agents]\ndefault_subagent_model = "fixture-other-model"\n')
        original = self.config.read_bytes()
        result = self.cli('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_bytes(), original)
        self.assertIn('global default_subagent_model is not used or changed', result.stdout)
        role = tomllib.loads((self.codex / 'agents' / f'{ROLE}.toml').read_text())
        self.assertEqual(role['model'], ROUTE)

    def test_missing_catalog_route_fails(self):
        self.catalog.write_text('{"models": []}')
        with self.assertRaises(SetupError):
            self.report()

    def test_non_spawnable_catalog_route_blocks_install(self):
        payload = json.loads(self.catalog.read_text())
        for value in ['v1', None]:
            with self.subTest(version=value):
                payload['models'][0]['multi_agent_version'] = value
                self.catalog.write_text(json.dumps(payload))
                result = self.cli('--apply')
                self.assertEqual(result.returncode, 2)
                self.assertIn('not advertised for native subagents', result.stderr)
                self.assertFalse((self.home / '.agents').exists())
                self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_non_spawnable_alternate_route_blocks_install_without_paid_probe_advice(self):
        route = 'openrouter/deepseek-v4.1-flash'
        self.set_catalog_route(route, 'v1')
        result = self.cli('--worker-route', route, '--apply')
        self.assertEqual(result.returncode, 2)
        self.assertIn(route, result.stderr)
        self.assertIn('Do not run subagents certify', result.stderr)
        self.assertFalse((self.home / '.agents').exists())

    def test_flash_root_is_rejected_for_every_supported_provider(self):
        route = 'openrouter/deepseek-v4.1-flash'
        self.set_catalog_route(route)
        self.config.write_text(self.config.read_text().replace('fixture-astra-root', route))
        with self.assertRaisesRegex(SetupError, 'root model is Flash'):
            inspect(self.home, self.codex, worker_route=route)

    def test_non_loopback_route_fails_without_exposing_url(self):
        self.config.write_text(self.config.read_text().replace('127.0.0.1', 'private.remote.test'))
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('TEST_PRIVATE_CAPABILITY', result.stdout + result.stderr)

    def test_native_direct_v1_route_is_supported(self):
        self.config.write_text(self.config.read_text().replace('/_codex-router/TEST_PRIVATE_CAPABILITY/v1', '/v1'))
        original = self.config.read_bytes()
        self.assertEqual(self.report()['worker_model'], ROUTE)
        result = self.cli('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_bytes(), original)

    def test_invalid_router_url_shapes_fail_closed(self):
        original = self.config.read_text()
        valid = 'http://127.0.0.1:4202/_codex-router/TEST_PRIVATE_CAPABILITY/v1'
        for url in ['http://example.invalid/v1', 'http://127.0.0.1:4202/arbitrary/v1',
                    'http://127.0.0.1:4202/v1?secret=TEST_PRIVATE_CAPABILITY',
                    'http://127.0.0.1:4202/v1#secret', 'http://user:secret@127.0.0.1:4202/v1',
                    'file:///v1', 'http://127.0.0.1:4202/_codex-router/a/extra/v1']:
            with self.subTest(url=url):
                self.config.write_text(original.replace(valid, url))
                with self.assertRaises(SetupError):
                    self.report()

    def test_existing_backup_directory_permissions_preserved(self):
        backup = self.codex / 'astra-flash-install-backups'
        backup.mkdir(mode=0o750)
        before = backup.stat().st_mode
        self.apply()
        self.assertEqual(backup.stat().st_mode, before)

    def test_malformed_toml_does_not_echo_secret(self):
        self.config.write_text('token = "TEST_SECRET_KEY\n')
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('TEST_SECRET_KEY', result.stdout + result.stderr)

    def test_disabled_subagents_fail_closed(self):
        self.config.write_text(self.config.read_text() + '\n[agents]\nenabled = false\n')
        with self.assertRaises(SetupError):
            self.report()

    def test_misplaced_top_level_setting_under_agents_gets_actionable_error(self):
        self.config.write_text(
            '# A misplaced table header makes the following URL part of agents.\n'
            '[agents]\ndefault_subagent_model = "fixture-other-model"\n'
            'openai_base_url = "http://127.0.0.1:4202/v1"\n'
            'model_catalog_json = "catalog.json"\n'
        )
        with self.assertRaisesRegex(SetupError, r'do not belong under \[agents\].*openai_base_url'):
            self.report()

    def test_absorbed_key_is_caught_by_shape_not_by_a_known_name_list(self):
        # Regression for a real incident: an agent satisfying an older installer
        # prerequisite appended [agents] to config.toml, which absorbed the two
        # top-level realtime keys that followed it. Codex refused to load the
        # config, taking down the host app and the CLI. Neither key is a
        # plausible member of a list of anticipated top-level names, so the
        # guard has to reject them on shape.
        self.config.write_text(
            'model = "fixture-astra-root"\n'
            'openai_base_url = "http://127.0.0.1:4202/v1"\n'
            'model_catalog_json = "catalog.json"\n'
            '[agents]\n'
            'default_subagent_model = "fixture-other-model"\n'
            'experimental_realtime_webrtc_call_base_url = "https://example.invalid/backend-api/codex"\n'
            'experimental_realtime_ws_base_url = "https://example.invalid/v1"\n'
        )
        with self.assertRaisesRegex(
            SetupError,
            r'experimental_realtime_webrtc_call_base_url, experimental_realtime_ws_base_url',
        ):
            self.report()

    def test_recognized_agent_settings_and_role_tables_are_accepted(self):
        # The guard must not fire on a legitimate [agents] table: Codex accepts
        # these scalars there, and any other key is an agent name owning a table.
        self.config.write_text(
            self.config.read_text()
            + '[agents]\n'
            'enabled = true\n'
            'default_subagent_model = "fixture-other-model"\n'
            'default_subagent_reasoning_effort = "high"\n'
            'max_concurrent_threads_per_session = 6\n'
            'max_depth = 2\n'
            'job_max_runtime_seconds = 600\n'
            f'[agents.{ROLE}]\n'
            'description = "fixture role"\n'
        )
        self.assertEqual(self.report()['status'], 'static-ready')

    def test_documented_interrupt_and_legacy_thread_settings_are_accepted(self):
        original = self.config.read_text()
        for setting in ('interrupt_message = false', 'max_threads = 4'):
            with self.subTest(setting=setting):
                self.config.write_text(original + f'[agents]\n{setting}\n')
                self.assertEqual(self.report()['status'], 'static-ready')

    def test_agent_name_holding_a_scalar_is_rejected(self):
        # An agent name must own a role table; a bare scalar is the exact shape
        # Codex rejects with "expected struct AgentRoleToml".
        self.config.write_text(
            self.config.read_text() + '[agents]\nastra_flash_builder = "not-a-table"\n'
        )
        with self.assertRaisesRegex(SetupError, r'do not belong under \[agents\].*astra_flash_builder'):
            self.report()

    def test_standalone_profile_is_read_without_modifying_it(self):
        profile = self.codex / 'work.config.toml'
        profile.write_text('model = "fixture-profile-astra"\nmodel_reasoning_effort = "high"\n')
        result, _ = inspect(self.home, self.codex, 'work')
        self.assertEqual(result['root_model_observed'], 'fixture-profile-astra')
        self.assertEqual(result['worker_model'], ROUTE)
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_ambiguous_profiles_fail(self):
        self.config.write_text(self.config.read_text() + '\n[profiles.work]\nmodel = "fixture-old"\n')
        (self.codex / 'work.config.toml').write_text('model = "fixture-new"\n')
        with self.assertRaises(SetupError):
            inspect(self.home, self.codex, 'work')

    def test_global_worker_effort_is_ignored(self):
        self.config.write_text(self.config.read_text() + '\n[agents]\ndefault_subagent_reasoning_effort = "medium"\n')
        original = self.config.read_bytes()
        report = self.report()
        self.assertEqual(report['worker_effort'], 'high')
        self.assertEqual(self.config.read_bytes(), original)

    def test_existing_foreign_content_requires_explicit_replace(self):
        folder = self.home / '.agents' / 'skills' / SKILL
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text('My existing custom content\n')
        with self.assertRaises(SetupError):
            self.changes()
        self.assertTrue(self.changes(replace=True))

    def test_symlink_destination_is_refused(self):
        external = self.home / 'external'
        external.mkdir()
        (self.home / '.agents').symlink_to(external, target_is_directory=True)
        with self.assertRaises(SetupError):
            self.changes()

    def test_legacy_same_name_installation_is_detected(self):
        (self.codex / 'skills' / SKILL).mkdir(parents=True)
        with self.assertRaises(SetupError):
            self.changes()

    def test_undo_restores_original_policy_and_removes_new_files(self):
        receipt = self.apply()
        result = self.cli('--undo', str(receipt), '--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.policy.read_bytes(), self.original_policy)
        self.assertEqual(self.config.read_bytes(), self.original_config)
        self.assertFalse((self.codex / 'agents' / f'{ROLE}.toml').exists())
        self.assertFalse((self.home / '.agents' / 'skills' / SKILL).exists())

    def test_undo_preserves_subsequent_user_edits_by_refusing(self):
        receipt = self.apply()
        self.policy.write_text(self.policy.read_text() + 'A later note.\n')
        changed = self.policy.read_bytes()
        result = self.cli('--undo', str(receipt), '--apply')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.policy.read_bytes(), changed)
        self.assertTrue((self.codex / 'agents' / f'{ROLE}.toml').exists())

    def test_install_rolls_back_completed_writes_on_error(self):
        report = self.report()
        changes = self.changes()
        target = changes[1]['path']
        real = install.atomic_write
        fired = False
        def failing_write(path, data, mode=0o600):
            nonlocal fired
            if path == target and not fired:
                fired = True
                raise OSError('Synthetic write failure')
            return real(path, data, mode)
        with patch.object(install, 'atomic_write', side_effect=failing_write):
            with self.assertRaises(OSError):
                install.apply_changes(changes, self.codex, report['input_hashes'])
        for change in changes:
            self.assertEqual(install.contents(change['path']), change['before'])
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_receipt_path_traversal_is_refused(self):
        receipt = self.apply()
        record = json.loads(receipt.read_text())
        record['files'][0]['path'] = str(self.home / '.agents' / 'skills' / SKILL / '..' / '..' / '..' / '.codex' / 'config.toml')
        receipt.write_text(json.dumps(record))
        result = self.cli('--undo', str(receipt), '--apply')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_local_doctor_uses_only_models_get_without_exposing_capability(self):
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.path)
                body = json.dumps({'data': [{'id': 'openrouter/deepseek-v4.1-flash'}]}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            route = 'openrouter/deepseek-v4.1-flash'
            self.set_catalog_route(route)
            self.config.write_text(self.config.read_text().replace(':4202/', f':{server.server_port}/'))
            result = subprocess.run([sys.executable, str(SCRIPTS / 'doctor.py'), '--home', str(self.home),
                                     '--codex-home', str(self.codex), '--worker-route', route,
                                     '--check-local-router'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(seen, ['/_codex-router/TEST_PRIVATE_CAPABILITY/v1/models'])
            self.assertNotIn('TEST_PRIVATE_CAPABILITY', result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['worker_model'], route)
            self.assertFalse(report['runtime_verified'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_config_changed_after_preflight_is_detected(self):
        report = self.report()
        changes = self.changes()
        self.config.write_text(self.config.read_text() + '# Changed by another process\n')
        with self.assertRaises(SetupError):
            install.apply_changes(changes, self.codex, report['input_hashes'])


class NamedBuilderTests(_Fixture):
    """One machine, several separately pinned builder roles."""

    REQUESTED = {
        'grok': ('astra_terra_builder_grok', 'grok-oauth/grok-4.6', 'cloud'),
        'fable': ('astra_terra_builder_fable', 'openrouter/claude-fable-5.1', 'cloud'),
        'deepseek-flash': ('astra_terra_builder_deepseek_flash', 'deepseek/deepseek-v4.1-flash', 'flash'),
    }

    def set_catalog(self, routes, multi_agent_version='v2'):
        """Publish one catalog entry per route, all at the same effort."""
        self.catalog.write_text(json.dumps({'models': [
            {'slug': route, 'multi_agent_version': multi_agent_version,
             'default_reasoning_level': 'high',
             'supported_reasoning_levels': [{'effort': 'high'}, {'effort': 'max'}]}
            for route in routes
        ]}))

    def skill_root(self):
        return self.home / '.agents' / 'skills' / SKILL

    def binding(self, role):
        return self.skill_root() / 'builders' / f'{role}.json'

    def legacy_binding(self):
        return self.skill_root() / 'routing.json'

    def role_file(self, role):
        return self.codex / 'agents' / f'{role}.toml'

    def installed_doctor(self, *args):
        """Run the doctor from the installed skill, as a user would."""
        return subprocess.run(
            [sys.executable, str(self.skill_root() / 'scripts' / 'doctor.py'),
             '--home', str(self.home), '--codex-home', str(self.codex), *args],
            capture_output=True, text=True)

    def source_doctor(self, *args):
        """Run the doctor from a source checkout, which installs no bindings."""
        return subprocess.run(
            [sys.executable, str(SCRIPTS / 'doctor.py'),
             '--home', str(self.home), '--codex-home', str(self.codex), *args],
            capture_output=True, text=True)

    def receipt_of(self, result):
        for line in result.stdout.splitlines():
            if 'Undo receipt:' in line:
                return Path(line.split('Undo receipt:', 1)[1].strip())
        raise AssertionError(f'no undo receipt in output: {result.stdout!r} {result.stderr!r}')

    def install_builder(self, key, *args):
        result = self.cli('--builder', key, '--apply', *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_preset_table_matches_the_accepted_contract(self):
        expected = {
            'grok': 'astra_terra_builder_grok',
            'fable': 'astra_terra_builder_fable',
            'deepseek-flash': 'astra_terra_builder_deepseek_flash',
            'deepseek-pro': 'astra_terra_builder_deepseek_pro',
            'grok-4-5': 'astra_terra_builder_grok_4_5',
            'ollama': 'astra_terra_builder_ollama',
        }
        self.assertEqual({key: spec.role for key, spec in builders.PRESETS.items()}, expected)
        for key, role in expected.items():
            with self.subTest(builder=key):
                self.assertNotIn('/', role)
                self.assertNotIn(' ', role)
                self.assertTrue(builders.ROLE_PATTERN.fullmatch(role))
                self.assertIn(role, builders.KNOWN_ROLES)
                self.assertEqual(builders.binding_role(Path('builders') / f'{role}.json'), role)
        self.assertIn(ROLE, builders.KNOWN_ROLES)
        self.assertEqual(builders.PRESETS['grok'].default_route, 'grok-oauth/grok-4.6')
        self.assertEqual(builders.PRESETS['fable'].default_route, 'openrouter/claude-fable-5.1')
        self.assertEqual(builders.PRESETS['deepseek-flash'].default_route, 'deepseek/deepseek-v4.1-flash')
        self.assertEqual(builders.PRESETS['deepseek-pro'].default_route, 'deepseek/deepseek-v4-pro')
        self.assertEqual(builders.PRESETS['grok-4-5'].default_route, 'grok-oauth/grok-4.5')
        self.assertIsNone(builders.PRESETS['ollama'].default_route)

    def test_example_table_matches_the_preset_module(self):
        table = json.loads((ROOT / 'examples' / 'named-builders' / 'builders.json').read_text())
        self.assertEqual(table['schema_version'], 1)
        entries = {entry['preset']: entry for entry in table['builders']}
        self.assertEqual(set(entries), set(builders.PRESETS))
        for key, spec in builders.PRESETS.items():
            with self.subTest(builder=key):
                entry = entries[key]
                self.assertEqual(entry['role'], spec.role)
                self.assertEqual(entry['label'], spec.label)
                self.assertEqual(entry['default_route'], spec.default_route)
                self.assertEqual(tuple(entry['allowed_routes']), spec.allowed_routes)
                self.assertEqual(entry['allow_local'], spec.allow_local)
                self.assertNotIn('/', entry['role'])
                self.assertNotIn(' ', entry['role'])

    def test_requested_builders_coexist_with_separate_routes(self):
        self.set_catalog(route for _, route, _ in self.REQUESTED.values())
        for key in self.REQUESTED:
            with self.subTest(builder=key):
                self.install_builder(key)
        for key, (role, route, family) in self.REQUESTED.items():
            with self.subTest(builder=key):
                raw = self.role_file(role).read_text()
                role_toml = tomllib.loads(raw)
                self.assertEqual(role_toml['name'], role)
                self.assertEqual(role_toml['model'], route)
                self.assertFalse(role_toml['agents']['enabled'])
                self.assertNotIn('sandbox_mode', role_toml)
                self.assertNotIn('model_provider', role_toml)
                self.assertIn(builders.PRESETS[key].label, raw)
                binding = json.loads(self.binding(role).read_text())
                self.assertEqual(binding['builder'], key)
                self.assertEqual(binding['custom_agent'], role)
                self.assertEqual(binding['worker_model'], route)
                self.assertEqual(binding['worker_route_family'], family)
                self.assertEqual(binding['worker_effort'], 'high')
        # A named install never creates or rewrites the legacy worker.
        self.assertFalse(self.role_file(ROLE).exists())
        self.assertFalse(self.legacy_binding().exists())
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_reinstalling_one_builder_preserves_the_others_bytes(self):
        self.set_catalog(['grok-oauth/grok-4.6', 'grok-oauth/grok-4.5',
                          'openrouter/claude-fable-5.1', 'deepseek/deepseek-v4.1-flash'])
        for key in self.REQUESTED:
            self.install_builder(key)
        untouched = {
            path: path.read_bytes()
            for role in ('astra_terra_builder_fable', 'astra_terra_builder_deepseek_flash')
            for path in (self.role_file(role), self.binding(role))
        }
        changed = self.cli('--builder', 'grok', '--worker-route', 'grok-oauth/grok-4.5',
                           '--apply', '--replace')
        self.assertEqual(changed.returncode, 0, changed.stderr)
        grok = tomllib.loads(self.role_file('astra_terra_builder_grok').read_text())
        self.assertEqual(grok['model'], 'grok-oauth/grok-4.5')
        grok_binding = json.loads(self.binding('astra_terra_builder_grok').read_text())
        self.assertEqual(grok_binding['worker_model'], 'grok-oauth/grok-4.5')
        for path, before in untouched.items():
            self.assertEqual(path.read_bytes(), before, path)

    def test_builder_content_change_requires_explicit_replace(self):
        self.set_catalog(['grok-oauth/grok-4.6'])
        self.install_builder('grok')
        target = self.role_file('astra_terra_builder_grok')
        edited = target.read_text() + '# edited by the operator\n'
        target.write_text(edited)
        refused = self.cli('--builder', 'grok', '--apply')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('--replace', refused.stderr)
        self.assertEqual(target.read_text(), edited)
        replaced = self.cli('--builder', 'grok', '--apply', '--replace')
        self.assertEqual(replaced.returncode, 0, replaced.stderr)
        self.assertNotIn('edited by the operator', target.read_text())

    def test_doctor_reads_each_selected_builder_binding(self):
        self.set_catalog(route for _, route, _ in self.REQUESTED.values())
        for key in self.REQUESTED:
            self.install_builder(key)
        for key, (role, route, family) in self.REQUESTED.items():
            with self.subTest(builder=key):
                result = self.installed_doctor('--builder', key)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report['status'], 'static-ready')
                self.assertEqual(report['worker_model'], route)
                self.assertEqual(report['worker_route_family'], family)
                self.assertEqual(report['custom_agent'], role)
                self.assertEqual(report['builder_preset'], key)
                self.assertTrue(report['catalog_advertises_subagent'])
                self.assertFalse(report['runtime_verified'])

    def test_doctor_refuses_an_uninstalled_builder_without_a_route(self):
        result = self.source_doctor('--builder', 'grok')
        self.assertEqual(result.returncode, 2)
        self.assertIn('No Astra/Terra builder Grok binding is installed', result.stderr)
        self.assertIn('--builder grok', result.stderr)

    def test_doctor_can_precheck_a_route_before_installing_that_builder(self):
        self.set_catalog(['grok-oauth/grok-4.6'])
        result = self.source_doctor('--builder', 'grok', '--worker-route', 'grok-oauth/grok-4.6')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['worker_model'], 'grok-oauth/grok-4.6')

    def test_legacy_and_named_bindings_are_isolated(self):
        self.set_catalog(['deepseek/deepseek-v4.1-flash', 'grok-oauth/grok-4.6'])
        self.apply()
        legacy_role = self.role_file(ROLE).read_bytes()
        legacy_binding = self.legacy_binding().read_bytes()
        self.install_builder('grok')
        self.assertEqual(self.role_file(ROLE).read_bytes(), legacy_role)
        self.assertEqual(self.legacy_binding().read_bytes(), legacy_binding)
        grok_role = self.role_file('astra_terra_builder_grok').read_bytes()
        grok_binding = self.binding('astra_terra_builder_grok').read_bytes()
        legacy_again = self.cli('--apply')
        self.assertEqual(legacy_again.returncode, 0, legacy_again.stderr)
        self.assertIn('no changes needed', legacy_again.stdout)
        self.assertEqual(self.role_file('astra_terra_builder_grok').read_bytes(), grok_role)
        self.assertEqual(self.binding('astra_terra_builder_grok').read_bytes(), grok_binding)
        self.assertEqual(self.config.read_bytes(), self.original_config)

    def snapshot_installation(self):
        """Every installed file, so a refused undo can be proved to change nothing."""
        return {
            str(path): path.read_bytes()
            for path in sorted((self.codex / 'agents').glob('*.toml'))
        } | {
            str(path): path.read_bytes()
            for path in sorted(self.skill_root().rglob('*')) if path.is_file()
        }

    def test_undo_of_the_first_install_is_refused_while_later_builders_remain(self):
        # The first receipt carries the shared skill files and the managed policy.
        # Restoring it first would strand the roles installed after it.
        self.set_catalog(route for _, route, _ in self.REQUESTED.values())
        receipts = {key: self.receipt_of(self.install_builder(key)) for key in self.REQUESTED}
        before = self.snapshot_installation()
        refused = self.cli('--undo', str(receipts['grok']), '--apply')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('reverse install order', refused.stderr)
        self.assertIn('astra_terra_builder_deepseek_flash.toml', refused.stderr)
        self.assertEqual(self.snapshot_installation(), before)
        preview = self.cli('--undo', str(receipts['grok']))
        self.assertEqual(preview.returncode, 2)
        self.assertEqual(self.snapshot_installation(), before)

    def test_undo_in_reverse_install_order_removes_every_builder(self):
        self.set_catalog(route for _, route, _ in self.REQUESTED.values())
        receipts = {key: self.receipt_of(self.install_builder(key)) for key in self.REQUESTED}
        for key in reversed(list(self.REQUESTED)):
            with self.subTest(undo=key):
                result = self.cli('--undo', str(receipts[key]), '--apply')
                self.assertEqual(result.returncode, 0, result.stderr)
        for role in builders.KNOWN_ROLES:
            self.assertFalse(self.role_file(role).exists())
        self.assertFalse((self.skill_root() / 'builders').exists())
        self.assertFalse(self.skill_root().exists())
        self.assertEqual(self.policy.read_bytes(), self.original_policy)

    def test_legacy_then_named_undo_follows_reverse_install_order(self):
        self.set_catalog(['deepseek/deepseek-v4.1-flash', 'grok-oauth/grok-4.6'])
        legacy_receipt = self.apply()
        named_receipt = self.receipt_of(self.install_builder('grok'))
        before = self.snapshot_installation()
        refused = self.cli('--undo', str(legacy_receipt), '--apply')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('reverse install order', refused.stderr)
        self.assertIn('astra_terra_builder_grok.toml', refused.stderr)
        self.assertEqual(self.snapshot_installation(), before)
        self.assertEqual(self.cli('--undo', str(named_receipt), '--apply').returncode, 0)
        self.assertEqual(self.cli('--undo', str(legacy_receipt), '--apply').returncode, 0)
        self.assertFalse(self.role_file(ROLE).exists())
        self.assertFalse(self.legacy_binding().exists())
        self.assertEqual(self.policy.read_bytes(), self.original_policy)

    def test_role_only_undo_is_not_blocked_by_other_installed_builders(self):
        # A receipt that only owns one role and its binding may always be undone.
        self.set_catalog(['deepseek/deepseek-v4.1-flash', 'grok-oauth/grok-4.6'])
        named_receipt = self.receipt_of(self.install_builder('grok'))
        legacy_receipt = self.apply()
        legacy_role = self.role_file(ROLE).read_bytes()
        done = self.cli('--undo', str(legacy_receipt), '--apply')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(self.role_file(ROLE).exists())
        self.assertTrue(self.role_file('astra_terra_builder_grok').exists())
        self.assertTrue(self.binding('astra_terra_builder_grok').exists())
        # The named builder's transaction still owns the policy and the skill.
        self.assertIn(install.BEGIN, self.policy.read_bytes())
        self.assertTrue(self.skill_root().exists())
        self.assertEqual(self.cli('--undo', str(named_receipt), '--apply').returncode, 0)
        self.assertFalse((self.home / '.agents' / 'skills' / SKILL).exists())
        self.assertEqual(self.policy.read_bytes(), self.original_policy)

    def test_undo_still_refuses_after_a_later_edit(self):
        self.set_catalog(['grok-oauth/grok-4.6'])
        receipt = self.receipt_of(self.install_builder('grok'))
        target = self.binding('astra_terra_builder_grok')
        target.write_text(target.read_text() + ' ')
        changed = target.read_bytes()
        result = self.cli('--undo', str(receipt), '--apply')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(target.read_bytes(), changed)
        self.assertTrue(self.role_file('astra_terra_builder_grok').exists())

    def test_undo_receipt_allowlist_rejects_unknown_roles_and_bindings(self):
        self.set_catalog(['grok-oauth/grok-4.6'])
        receipt = self.receipt_of(self.install_builder('grok'))
        record = json.loads(receipt.read_text())
        for index, entry in enumerate(record['files']):
            if Path(entry['path']).parent == self.codex / 'agents':
                entry['path'] = str(self.codex / 'agents' / 'unknown_builder_role.toml')
            elif Path(entry['path']).name == 'astra_terra_builder_grok.json':
                entry['path'] = str(self.skill_root() / 'builders' / 'unknown_builder_role.json')
        receipt.write_text(json.dumps(record))
        result = self.cli('--undo', str(receipt), '--apply')
        self.assertEqual(result.returncode, 2)
        self.assertIn('outside this package', result.stderr)
        self.assertTrue(self.role_file('astra_terra_builder_grok').exists())
        self.assertTrue(self.binding('astra_terra_builder_grok').exists())

    def test_absent_or_v1_route_fails_before_any_write(self):
        for spec, version in (({'std': ['openrouter/claude-fable-5.1']}, 'v2'),
                              ({'std': ['grok-oauth/grok-4.6']}, 'v1'),
                              ({'std': []}, 'v2')):
            with self.subTest(version=version, routes=spec['std']):
                self.set_catalog(spec['std'], version)
                result = self.cli('--builder', 'grok', '--apply')
                self.assertEqual(result.returncode, 2)
                self.assertFalse((self.home / '.agents').exists())
                self.assertFalse((self.codex / 'agents').exists())
                self.assertEqual(self.config.read_bytes(), self.original_config)

    def test_ollama_builder_requires_an_explicit_local_route_first(self):
        self.set_catalog(['local/qwen3.8:27b-mlx'])
        missing = self.cli('--builder', 'ollama', '--apply')
        self.assertEqual(missing.returncode, 2)
        self.assertIn('must name it', missing.stderr)
        self.assertFalse((self.home / '.agents').exists())
        self.install_builder('ollama', '--worker-route', 'local/qwen3.8:27b-mlx')
        binding = json.loads(self.binding('astra_terra_builder_ollama').read_text())
        self.assertEqual(binding['worker_model'], 'local/qwen3.8:27b-mlx')
        self.assertEqual(binding['worker_route_family'], 'local')
        again = self.cli('--builder', 'ollama', '--apply')
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn('no changes needed', again.stdout)

    def test_worker_route_override_must_match_the_preset(self):
        self.set_catalog(['grok-oauth/grok-4.6', 'grok-oauth/grok-4.5',
                          'openrouter/claude-fable-5.1', 'deepseek/deepseek-v4.1-flash',
                          'deepseek/deepseek-v4-pro', 'local/qwen3.8:27b-mlx'])
        mismatches = {
            'grok': 'openrouter/claude-fable-5.1',
            'fable': 'grok-oauth/grok-4.6',
            'deepseek-flash': 'openrouter/deepseek-v4.1-flash',
            'deepseek-pro': 'deepseek/deepseek-v4.1-flash',
            'grok-4-5': 'grok-oauth/grok-4.6',
            'ollama': 'grok-oauth/grok-4.6',
        }
        for key, route in mismatches.items():
            with self.subTest(builder=key, route=route):
                result = self.cli('--builder', key, '--worker-route', route, '--apply')
                self.assertEqual(result.returncode, 2)
                self.assertIn('cannot pin', result.stderr)
                self.assertFalse((self.home / '.agents').exists())

    def test_grok_builder_accepts_either_oauth_route(self):
        self.set_catalog(['grok-oauth/grok-4.6', 'grok-oauth/grok-4.5'])
        for route in ('grok-oauth/grok-4.6', 'grok-oauth/grok-4.5'):
            with self.subTest(route=route):
                args = ['--worker-route', route, '--apply'] + ([] if route.endswith('4.6') else ['--replace'])
                result = self.cli('--builder', 'grok', *args)
                self.assertEqual(result.returncode, 0, result.stderr)
                role = tomllib.loads(self.role_file('astra_terra_builder_grok').read_text())
                self.assertEqual(role['model'], route)

    def test_deepseek_pro_builder_pins_the_direct_route(self):
        self.set_catalog(['deepseek/deepseek-v4-pro'])
        self.install_builder('deepseek-pro')
        role = tomllib.loads(self.role_file('astra_terra_builder_deepseek_pro').read_text())
        self.assertEqual(role['model'], 'deepseek/deepseek-v4-pro')
        binding = json.loads(self.binding('astra_terra_builder_deepseek_pro').read_text())
        self.assertEqual(binding['worker_provider'], 'DeepSeek API')
        self.assertEqual(binding['worker_effort'], 'high')

    def test_named_builder_plan_never_writes_the_legacy_binding(self):
        self.set_catalog(['grok-oauth/grok-4.6'])
        report, _ = inspect(self.home, self.codex, worker_route='grok-oauth/grok-4.6',
                            role='astra_terra_builder_grok', builder='grok')
        changes = install.plan_changes(
            self.home, self.codex, report, True, False, builder=builders.PRESETS['grok']
        )
        targets = {change['path'] for change in changes}
        self.assertIn(self.role_file('astra_terra_builder_grok'), targets)
        self.assertIn(self.binding('astra_terra_builder_grok'), targets)
        self.assertNotIn(self.legacy_binding(), targets)
        self.assertNotIn(self.role_file(ROLE), targets)
        self.assertNotIn(self.config, targets)

    def test_stray_source_bindings_cannot_overwrite_installed_bindings(self):
        # A checkout that somehow contains runtime bindings must not be able to
        # publish them over the installed legacy binding or another role's route.
        self.set_catalog(['grok-oauth/grok-4.6', 'deepseek/deepseek-v4.1-flash'])
        self.install_builder('grok')
        self.apply()
        grok_before = self.binding('astra_terra_builder_grok').read_bytes()
        legacy_before = self.legacy_binding().read_bytes()
        stray = self.home / 'stray-source'
        (stray / 'builders').mkdir(parents=True)
        (stray / 'SKILL.md').write_text('# stray skill copy\n')
        (stray / 'routing.json').write_text(json.dumps({'worker_model': 'stray/route'}))
        for role in ('astra_terra_builder_grok', 'astra_terra_builder_fable'):
            (stray / 'builders' / f'{role}.json').write_text(
                json.dumps({'worker_model': 'stray/route'}))
        report, _ = inspect(self.home, self.codex, worker_route='grok-oauth/grok-4.6',
                            role='astra_terra_builder_grok', builder='grok')
        with patch.object(install, 'SKILL_SOURCE', stray):
            changes = install.plan_changes(self.home, self.codex, report, True, True,
                                           builder=builders.PRESETS['grok'])
            targets = {change['path'] for change in changes}
            install.apply_changes(changes, self.codex, report['input_hashes'])
        # An ordinary skill file is still copied; generated bindings never are.
        self.assertIn(self.skill_root() / 'SKILL.md', targets)
        self.assertNotIn(self.skill_root() / 'routing.json', targets)
        self.assertNotIn(self.binding('astra_terra_builder_fable'), targets)
        self.assertNotIn(self.binding('astra_terra_builder_grok'), targets)
        self.assertEqual(self.legacy_binding().read_bytes(), legacy_before)
        self.assertEqual(self.binding('astra_terra_builder_grok').read_bytes(), grok_before)
        self.assertFalse(self.binding('astra_terra_builder_fable').exists())
        self.assertEqual((self.skill_root() / 'SKILL.md').read_text(), '# stray skill copy\n')


class PolicyTests(unittest.TestCase):
    def test_worker_route_resolution_defaults_and_reuses_valid_binding(self):
        self.assertEqual(resolve_worker_route(), ROUTE)
        with tempfile.TemporaryDirectory() as directory:
            binding = Path(directory).resolve() / 'routing.json'
            route = 'openrouter/deepseek-v4.1-flash'
            binding.write_text(json.dumps({'worker_model': route}))
            self.assertEqual(resolve_worker_route(binding=binding), route)
            self.assertEqual(resolve_worker_route(ROUTE, binding), ROUTE)

    def test_worker_route_resolution_rejects_malformed_or_unreviewed_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            binding = Path(directory).resolve() / 'routing.json'
            binding.write_text('{broken')
            with self.assertRaises(SetupError):
                resolve_worker_route(binding=binding)
            binding.write_text(json.dumps({'worker_model': 'custom/deepseek-v4.1-flash'}))
            with self.assertRaisesRegex(SetupError, 'Unsupported worker route'):
                resolve_worker_route(binding=binding)

    def test_worker_route_resolution_reuses_a_local_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            binding = Path(directory).resolve() / 'routing.json'
            binding.write_text(json.dumps({'worker_model': 'local/qwen3.8:27b-mlx'}))
            self.assertEqual(resolve_worker_route(binding=binding), 'local/qwen3.8:27b-mlx')
            with self.assertRaisesRegex(SetupError, 'Unsupported worker route'):
                resolve_worker_route('local//broken', binding)

    def test_require_route_returns_the_route_or_refuses_it(self):
        for route in ('deepseek/deepseek-v4-pro', 'grok-oauth/grok-4.6', 'grok-oauth/grok-4.5',
                      'openrouter/claude-fable-5.1', 'local/gemma4:12b'):
            with self.subTest(route=route):
                self.assertEqual(require_route(route), route)
        for bad in (None, 7, 'lmstudio/local-model', 'ollama/deepseek-v4.1-flash', 'local/'):
            with self.subTest(route=bad):
                with self.assertRaisesRegex(SetupError, 'Unsupported worker route'):
                    require_route(bad)

    def test_route_hint_names_every_reviewed_route(self):
        hint = route_hint()
        for route in SUPPORTED_ROUTES:
            self.assertIn(route, hint)
        self.assertIn('local/<ollama-tag>', hint)

    def test_worker_route_resolution_refuses_symlinked_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / 'target.json'
            target.write_text(json.dumps({'worker_model': ROUTE}))
            binding = root / 'routing.json'
            binding.symlink_to(target)
            with self.assertRaisesRegex(SetupError, 'symlinked routing binding'):
                resolve_worker_route(binding=binding)

    def test_crlf_and_unrelated_text_are_preserved(self):
        block = install.BEGIN + b'\nnew\n' + install.END + b'\n'
        old = b'prefix\r\n' + install.BEGIN + b'\r\nold\r\n' + install.END + b'\r\nsuffix\r\n'
        updated = install.managed_policy(old, block)
        self.assertTrue(updated.startswith(b'prefix\r\n'))
        self.assertTrue(updated.endswith(b'suffix\r\n'))
        self.assertEqual(updated.count(install.BEGIN), 1)
        self.assertIn(b'new\r\n', updated)

    def test_malformed_markers_are_refused(self):
        with self.assertRaises(SetupError):
            install.managed_policy(install.BEGIN, b'new')

    def test_redirect_refused_before_forwarding(self):
        from doctor import NoRedirect
        with self.assertRaises(SetupError):
            NoRedirect().redirect_request(None, None, 302, 'Found', {}, 'https://example.invalid/secret')

    def test_catalog_shapes(self):
        for payload in ([{'id': ROUTE}], {'data': [{'id': ROUTE}]}, {'models': [{'slug': ROUTE}]}):
            self.assertEqual(len(model_entries(payload)), 1)
        with self.assertRaises(SetupError):
            model_entries({'not_models': []})


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'examples' / 'invoice-filter'
        self.plan = json.loads((self.root / 'plan.json').read_text())

    def test_example_is_structurally_valid(self):
        self.assertEqual(validate(self.plan, self.root)['status'], 'structure-valid')

    def test_placeholder_is_rejected(self):
        self.plan['tasks'][0]['acceptance'] = ['TODO']
        with self.assertRaises(PlanError):
            validate(self.plan, self.root)

    def test_missing_brief_is_rejected(self):
        self.plan['tasks'][0]['brief'] = 'missing.md'
        with self.assertRaises(PlanError):
            validate(self.plan, self.root)

    def test_unbounded_file_scope_is_rejected(self):
        for path in ['.', '../outside', '/absolute', 'src/**', '.git/config']:
            self.plan['tasks'][0]['allowed_paths'] = [path]
            with self.assertRaises(PlanError):
                validate(self.plan, self.root)

    def test_sensitive_task_cannot_be_assigned_to_flash(self):
        self.plan['tasks'][0]['risk'] = 'sensitive'
        with self.assertRaises(PlanError):
            validate(self.plan, self.root)

    def add_task(self):
        task = copy.deepcopy(self.plan['tasks'][0])
        task['id'] = 'T2'
        task['allowed_paths'] = ['src/other.py', 'tests/test_other.py']
        self.plan['tasks'].append(task)
        return task

    def test_dependency_cycle_is_rejected(self):
        second = self.add_task()
        second['depends_on'] = ['T1']
        self.plan['tasks'][0]['depends_on'] = ['T2']
        with self.assertRaises(PlanError):
            validate(self.plan, self.root)

    def test_duplicate_id_is_rejected(self):
        self.add_task()['id'] = 'T1'
        with self.assertRaises(PlanError):
            validate(self.plan, self.root)

    def test_parallel_independent_scopes_are_accepted(self):
        self.add_task()
        self.plan['max_flash_workers'] = 2
        for task in self.plan['tasks']:
            task['parallel_group'] = 'G1'
        validate(self.plan, self.root)

    def test_parallel_overlap_is_rejected(self):
        self.add_task()['allowed_paths'] = ['src/invoices/']
        self.plan['max_flash_workers'] = 2
        for task in self.plan['tasks']:
            task['parallel_group'] = 'G1'
        with self.assertRaises(PlanError):
            validate(self.plan, self.root)

    def test_parallel_dependency_is_rejected(self):
        self.add_task()['depends_on'] = ['T1']
        self.plan['max_flash_workers'] = 2
        for task in self.plan['tasks']:
            task['parallel_group'] = 'G1'
        with self.assertRaises(PlanError):
            validate(self.plan, self.root)

    def test_cross_phase_dependency_must_be_declared(self):
        second = self.add_task()
        self.plan['phases'].append({'id': 'P2', 'goal': 'Second milestone', 'depends_on': ['P1'],
                                  'integration_checks': [{'command': 'python3 -m unittest', 'expected': 'Tests pass'}]})
        second['phase'] = 'P2'
        self.plan['tasks'][0]['depends_on'] = ['T2']
        with self.assertRaises(PlanError):
            validate(self.plan, self.root)

    def test_excessive_parallelism_is_rejected(self):
        self.plan['max_flash_workers'] = 99
        with self.assertRaises(PlanError):
            validate(self.plan, self.root)


if __name__ == '__main__':
    unittest.main()
