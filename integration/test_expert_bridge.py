"""Independent QA tests. Fixtures are simulated agents; host unittest runs are real."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH_ROOT = Path(os.environ.get('AIADMIN_WORKBENCH_ROOT', str(ROOT / 'upstream')))
EXPERTS_ROOT = Path(os.environ.get('EXPERT_TEAMS_ROOT', str(ROOT / 'experts')))
sys.path.insert(0, str(WORKBENCH_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from workbench.store import Store
from workbench.runner import invoke
from expert_bridge import Bridge, BridgeError, safe_file


class ScriptedAgents:
    def __init__(self, mutation=None, host_output=None):
        self.calls = []
        self.mutation = mutation
        self.host_output = host_output

    def __call__(self, args, prompt='', timeout=90, cwd=None):
        folder = Path(cwd)
        self.calls.append(folder.name)
        if folder.name == 'verification':
            if self.host_output is not None:
                return self.host_output
            return invoke(args, prompt=prompt, timeout=timeout, cwd=cwd)
        role = folder.name
        files = {
            'product_analyst': {'requirements.md': 'Return a + b; negative and zero inputs work.'},
            'backend_engineer': {'math_task.py': 'def add(a, b):\n    return a + b\n',
                'tests/test_basic.py': 'import unittest\nfrom math_task import add\nclass Basic(unittest.TestCase):\n    def test_positive(self): self.assertEqual(add(2,3),5)\n'},
            'qa_engineer': {'tests/test_independent.py': 'import unittest\nfrom math_task import add\nclass Independent(unittest.TestCase):\n    def test_negative(self): self.assertEqual(add(-2,1),-1)\n    def test_zero(self): self.assertEqual(add(0,0),0)\n'},
        }[role]
        for name, content in files.items():
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        result = {'role': role, 'status': 'passed', 'summary': 'Fixture result', 'limitations': ['simulated agent'],
                  'artifacts': [{'path': name, 'sha256': hashlib.sha256(content.encode()).hexdigest()} for name, content in files.items()]}
        if self.mutation:
            code = self.mutation(role, folder, result)
            if code is not None:
                return code, ''
        (folder / 'result.json').write_text(json.dumps(result))
        return 0, '{"type":"turn.completed"}\n'


class BridgeQA(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'state.sqlite3')

    def bridge(self, agents=None):
        return Bridge(self.store, SimpleNamespace(codex_binary=lambda: 'fixture-codex'),
                      EXPERTS_ROOT, self.root / 'runs', executor=agents or ScriptedAgents())

    def run_case(self, agents=None):
        return self.bridge(agents).run('tenant', 'case', 'Create integer addition', allow_execution=True)

    def test_success_runs_independent_real_host_tests(self):
        result = self.run_case()
        self.assertEqual(result['state'], 'completed')
        self.assertEqual([s['role'] for s in result['evidence']['stages']], ['product_analyst', 'backend_engineer', 'qa_engineer'])
        self.assertEqual(result['evidence']['host_verification']['test_count'], 3)
        self.assertEqual(result['evidence']['host_verification']['qa_test_count'], 2)
        self.assertEqual(result['evidence']['host_verification']['exit_code'], 0)

    def test_prepare_is_nonexecuting_and_idempotent(self):
        agents = ScriptedAgents()
        bridge = self.bridge(agents)
        first = bridge.run('tenant', 'case', 'Task')
        self.assertEqual(first['state'], 'prepared')
        self.assertEqual(first['id'], bridge.prepare('tenant', 'case', 'Task')['id'])
        self.assertEqual(agents.calls, [])
        with self.assertRaises(BridgeError): bridge.prepare('tenant', 'case', 'Different task')

    def test_terminal_duplicate_never_executes_again(self):
        agents = ScriptedAgents()
        bridge = self.bridge(agents)
        first = bridge.run('tenant', 'case', 'Task', True)
        second = bridge.run('tenant', 'case', 'Task', True)
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(agents.calls), 4)

    def test_process_failure_cannot_succeed(self):
        result = self.run_case(ScriptedAgents(lambda role, folder, result: 9 if role == 'backend_engineer' else None))
        self.assertEqual(result['state'], 'failed')
        self.assertIsNone(result['evidence']['host_verification'])

    def test_qa_failed_verdict_blocks_host_test(self):
        def mutate(role, folder, result):
            if role == 'qa_engineer': result['status'] = 'failed'
        self.assertEqual(self.run_case(ScriptedAgents(mutate))['state'], 'failed')

    def test_digest_mismatch_fails(self):
        def mutate(role, folder, result):
            if role == 'backend_engineer': result['artifacts'][0]['sha256'] = '0' * 64
        self.assertEqual(self.run_case(ScriptedAgents(mutate))['state'], 'failed')

    def test_qa_overwrite_is_rejected(self):
        def mutate(role, folder, result):
            if role == 'qa_engineer':
                file = folder / 'tests/test_independent.py'
                renamed = folder / 'tests/test_basic.py'
                file.rename(renamed)
                result['artifacts'][0]['path'] = 'tests/test_basic.py'
        self.assertEqual(self.run_case(ScriptedAgents(mutate))['state'], 'failed')

    def test_qa_input_tamper_rejected(self):
        def mutate(role, folder, result):
            if role == 'qa_engineer': (folder / 'input/math_task.py').write_text('def add(a,b): return 0')
        self.assertEqual(self.run_case(ScriptedAgents(mutate))['state'], 'failed')

    def test_qa_receives_actual_product_acceptance_text(self):
        observed = []
        def inspect(role, folder, result):
            if role == 'qa_engineer':
                observed.append((folder / 'input/acceptance/requirements.md').read_text())
        result = self.run_case(ScriptedAgents(inspect))
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(observed, ['Return a + b; negative and zero inputs work.'])

    def test_added_input_file_is_rejected(self):
        def mutate(role, folder, result):
            if role == 'qa_engineer': (folder / 'input/extra.py').write_text('x=1')
        self.assertEqual(self.run_case(ScriptedAgents(mutate))['state'], 'failed')

    def test_original_development_tampering_before_verification_is_rejected(self):
        def mutate(role, folder, result):
            if role == 'qa_engineer':
                (folder.parent / 'backend_engineer/math_task.py').write_text('def add(a,b): return a+b+1')
        self.assertEqual(self.run_case(ScriptedAgents(mutate))['state'], 'failed')

    def test_qa_must_supply_own_tests(self):
        def mutate(role, folder, result):
            if role == 'qa_engineer':
                (folder / 'review.md').write_text('Looks good')
                result['artifacts'] = [{'path': 'review.md', 'sha256': hashlib.sha256(b'Looks good').hexdigest()}]
        self.assertEqual(self.run_case(ScriptedAgents(mutate))['state'], 'failed')

    def test_empty_independent_qa_suite_cannot_pass_on_developer_tests(self):
        def mutate(role, folder, result):
            if role == 'qa_engineer':
                data = b'# No independent test case exists here.\n'
                (folder / 'tests/test_independent.py').write_bytes(data)
                result['artifacts'][0]['sha256'] = hashlib.sha256(data).hexdigest()
        self.assertEqual(self.run_case(ScriptedAgents(mutate))['state'], 'failed')

    def test_zero_tests_cannot_pass(self):
        self.assertEqual(self.run_case(ScriptedAgents(host_output=(0, 'BRIDGE_QA_TESTS=1\nRan 0 tests in 0.000s\nOK\n')))['state'], 'failed')

    def test_failing_tests_cannot_pass(self):
        self.assertEqual(self.run_case(ScriptedAgents(host_output=(1, 'BRIDGE_QA_TESTS=1\nRan 3 tests in 0.000s\nFAILED\n')))['state'], 'failed')

    def test_recovery_requires_stopped_confirmation_and_preserves_unknown(self):
        bridge = self.bridge()
        bridge.prepare('tenant', 'case', 'Task')
        with self.store.connection() as c: c.execute("UPDATE expert_runs SET state='running'")
        with self.assertRaises(BridgeError): bridge.recover('tenant', 'case')
        self.assertEqual(bridge.get('tenant', 'case')['state'], 'running')
        self.assertEqual(bridge.recover('tenant', 'case', True)['state'], 'unknown')
        self.assertEqual(bridge.run('tenant', 'case', 'Task', True)['state'], 'unknown')

    def test_stale_completion_cannot_overwrite_recovered_state(self):
        bridge = self.bridge()
        job = bridge.prepare('tenant', 'case', 'Task')
        with self.store.connection() as c: c.execute("UPDATE expert_runs SET state='running'")
        bridge.recover('tenant', 'case', True)
        with self.assertRaises(BridgeError): bridge._save(job['id'], 'completed', {})
        self.assertEqual(bridge.get('tenant', 'case')['state'], 'unknown')

    def test_persistence_and_tenant_separation(self):
        first = self.bridge().prepare('tenant', 'key', 'Task')
        second = self.bridge().prepare('other', 'key', 'Task')
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(self.bridge().get('tenant', 'key')['id'], first['id'])
        with self.assertRaises(BridgeError): self.bridge().get('absent', 'key')

    def test_traversal_absolute_and_normalization_rejected(self):
        for name in ('../outside', '/tmp/a', 'input/../file', './file', 'a//b', 'a\\b'):
            with self.subTest(path=name), self.assertRaises(BridgeError): safe_file(self.root, name)

    def test_symlink_and_hardlink_rejected(self):
        target = self.root / 'target'
        target.write_text('secret')
        (self.root / 'link').symlink_to(target)
        with self.assertRaises(BridgeError): safe_file(self.root, 'link')
        os.link(target, self.root / 'hard')
        with self.assertRaises(BridgeError): safe_file(self.root, 'hard')

    def test_parent_directory_symlink_rejected(self):
        (self.root / 'real').mkdir()
        (self.root / 'real/file').write_text('text')
        (self.root / 'linked').symlink_to(self.root / 'real', target_is_directory=True)
        with self.assertRaises(BridgeError): safe_file(self.root, 'linked/file')

    def test_simulated_executor_is_never_real_cli_evidence(self):
        evidence = self.run_case()['evidence']
        self.assertIn('execution_mode', evidence)
        self.assertNotIn(evidence['execution_mode'], ('real', 'real_cli', 'cli'))


if __name__ == '__main__': unittest.main()
