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
from local_config import ROUTE, ROLE, SKILL, SetupError, inspect, model_entries
from validate_plan import PlanError, validate


class SetupFixture(unittest.TestCase):
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
            '[agents]\ndefault_subagent_model = "' + ROUTE + '"\n'
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

    def changes(self, **kwargs):
        return install.plan_changes(self.home, self.codex, self.report(), kwargs.get('policy', True), kwargs.get('replace', False))

    def apply(self):
        report = self.report()
        changes = install.plan_changes(self.home, self.codex, report, True, False)
        return install.apply_changes(changes, self.codex, report['input_hashes'])

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

    def test_missing_worker_default_fails_without_writes(self):
        self.config.write_text(self.config.read_text().replace(ROUTE, 'fixture-other-model'))
        result = self.cli('--apply')
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.home / '.agents').exists())

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
        self.config.write_text(self.config.read_text().replace('[agents]', '[agents]\nenabled = false'))
        with self.assertRaises(SetupError):
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

    def test_unsupported_worker_effort_fails(self):
        self.config.write_text(self.config.read_text().replace('[agents]', '[agents]\ndefault_subagent_reasoning_effort = "medium"'))
        with self.assertRaises(SetupError):
            self.report()

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
                body = json.dumps({'data': [{'id': ROUTE}]}).encode()
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
            self.config.write_text(self.config.read_text().replace(':4202/', f':{server.server_port}/'))
            result = subprocess.run([sys.executable, str(SCRIPTS / 'doctor.py'), '--home', str(self.home),
                                     '--codex-home', str(self.codex), '--check-local-router'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(seen, ['/_codex-router/TEST_PRIVATE_CAPABILITY/v1/models'])
            self.assertNotIn('TEST_PRIVATE_CAPABILITY', result.stdout + result.stderr)
            self.assertFalse(json.loads(result.stdout)['runtime_verified'])
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


class PolicyTests(unittest.TestCase):
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
