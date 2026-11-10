import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = load('verify_project')
transaction = load('transaction')


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.original = self.root / 'original'
        self.original.mkdir()
        (self.original / 'project.ioc').write_text('PA5.Signal=GPIO_Output\nRCC.Clock=72\nADC.X\\#Y=1\n')
        (self.original / 'main.c').write_text('/* USER CODE BEGIN 0 */\nint x=1;\n/* USER CODE END 0 */\nvoid MX_TIM1_Init(void) { }\n')
        self.workspace = self.root / 'workspace'
        transaction.create(self.original, self.workspace)
        self.working = self.workspace / 'working'
        self.baseline = self.workspace / 'baseline'
        self.spec = {'ioc': 'project.ioc', 'ioc_values': {'PA5.Signal': 'GPIO_Output', 'ADC.X#Y': '1'},
                     'files': ['main.c'], 'functions': [{'file': 'main.c', 'name': 'MX_TIM1_Init'}],
                     'unchanged_ioc_prefixes': ['RCC.'], 'user_code_files': ['main.c']}

    def test_expected_project_and_diff(self):
        self.assertEqual(verify.verify(self.working, self.spec, self.baseline)['result'], 'pass')
        self.assertEqual(transaction.compare(self.workspace)['modified'], [])
        (self.working / 'new.h').write_text('new')
        (self.working / 'main.c').unlink()
        self.assertEqual(transaction.compare(self.workspace)['added'], ['new.h'])
        self.assertEqual(transaction.compare(self.workspace)['deleted'], ['main.c'])
        self.assertTrue((self.original / 'main.c').exists())
        restored = self.root / 'restored'
        transaction.restore(self.workspace, restored)
        self.assertEqual((restored / 'main.c').read_text(), (self.original / 'main.c').read_text())
        with self.assertRaises(ValueError):
            transaction.restore(self.workspace, self.original)

    def test_missing_file_and_wrong_ioc_fail(self):
        (self.working / 'main.c').unlink()
        (self.working / 'project.ioc').write_text('PA5.Signal=wrong\nRCC.Clock=72\n')
        result = verify.verify(self.working, self.spec, self.baseline)
        self.assertEqual(result['result'], 'fail')
        self.assertTrue(any(c['kind'] == 'file' and c['status'] == 'fail' for c in result['checks']))
        self.assertTrue(any(c['kind'] == 'ioc' and c['status'] == 'fail' for c in result['checks']))

    def test_user_code_and_unrelated_clock_changes_fail(self):
        (self.working / 'main.c').write_text('/* USER CODE BEGIN 0 */\nint x=2;\n/* USER CODE END 0 */\nvoid MX_TIM1_Init(void) {}')
        (self.working / 'project.ioc').write_text('PA5.Signal=GPIO_Output\nRCC.Clock=64\nADC.X\\#Y=1\n')
        result = verify.verify(self.working, self.spec, self.baseline)
        self.assertEqual({c['kind'] for c in result['checks'] if c['status'] == 'fail'}, {'user_code', 'ioc_unchanged'})

    def test_unmatched_markers_fail_closed(self):
        (self.working / 'main.c').write_text('/* USER CODE BEGIN 0 */\nint x;')
        with self.assertRaises(ValueError):
            verify.verify(self.working, self.spec, self.baseline)

    def test_baseline_and_paths_are_protected(self):
        with self.assertRaises(ValueError):
            transaction.create(self.original, self.original / 'nested')
        with self.assertRaises(ValueError):
            transaction.create(self.original, self.workspace)
        with self.assertRaises(ValueError):
            verify.within(self.working, '../original/main.c')
        (self.baseline / 'main.c').write_text('changed')
        with self.assertRaises(ValueError):
            transaction.compare(self.workspace)

    def test_missing_baseline_does_not_pass(self):
        result = verify.verify(self.working, self.spec)
        self.assertEqual(result['result'], 'fail')

    def test_function_in_comment_does_not_pass(self):
        (self.working / 'main.c').write_text('/* void MX_TIM1_Init(void) {} */')
        spec = {'ioc': 'project.ioc', 'functions': [{'file': 'main.c', 'name': 'MX_TIM1_Init'}]}
        self.assertEqual(verify.verify(self.working, spec)['result'], 'fail')

    def test_unmodified_baseline_required(self):
        (self.baseline / 'main.c').write_text('tampered')
        with self.assertRaises(ValueError):
            transaction.compare(self.workspace)

    def test_snapshot_rejects_symlinks_when_supported(self):
        link = self.original / 'link.c'
        try:
            link.symlink_to(self.original / 'main.c')
        except OSError:
            self.skipTest('creating symlinks is not available')
        with self.assertRaises(ValueError):
            transaction.create(self.original, self.root / 'other-workspace')

    def test_doctor_reports_missing_requested_ioc(self):
        run = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'doctor.py'), '--project', str(self.root / 'missing.ioc')],
                             capture_output=True, text=True, timeout=20)
        self.assertNotEqual(run.returncode, 0)
        self.assertIsNone(json.loads(run.stdout)['ioc'])

    def test_doctor_labels_event_version_separately(self):
        events = self.root / 'events.json'
        events.write_text(json.dumps({'result': 'passed', 'steps': [{'command': 'get version', 'result': 'passed', 'response_tail': '6.18.1\n0 OK\n'}]}))
        run = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'doctor.py'), '--version-events', str(events)],
                             capture_output=True, text=True, timeout=20)
        self.assertEqual(run.returncode, 0)
        self.assertEqual(json.loads(run.stdout)['cubemx_version_from_events'], '6.18.1')


if __name__ == '__main__':
    unittest.main()
