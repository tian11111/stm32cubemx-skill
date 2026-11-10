import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


GUARD = Path(__file__).resolve().parents[1] / 'scripts' / 'cubemx_guard.py'
FAKE = r'''
import os, sys, time
mode, record = sys.argv[1:]
def emit(value):
    sys.stdout.buffer.write(value); sys.stdout.buffer.flush()
emit(b'MX> ')
for line in sys.stdin:
    command = line.strip()
    with open(record, 'a', encoding='utf-8') as f:
        f.write(command + '\n')
    if command == 'exit':
        if mode == 'exit_after_success':
            sys.exit(4)
        break
    if mode == 'exit':
        sys.exit(4)
    if mode == 'timeout':
        time.sleep(3)
    if mode == 'ko':
        emit(b'0 KO\r\nMX> ')
    elif mode == 'malformed':
        emit(b'0 OK\r\nMX>KO\r\n')
        time.sleep(3)
    elif mode == 'status_after_prompt':
        emit(b'0 OK\r\nMX> KO\r\n')
        time.sleep(3)
    elif mode == 'reject':
        emit(b'forbidden\r\n0 OK\r\nMX> ')
    elif mode == 'ambiguous':
        emit(b'0 OK\r\n1 KO\r\nMX> ')
    else:
        emit(b'2026-11-10 [INFO] log\r\nvalue\r\n0 OK\r\nMX>')
        time.sleep(0.02)
        emit(b' ')
'''


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fake = self.root / 'fake.py'
        self.fake.write_text(FAKE, encoding='utf-8')
        self.record = self.root / 'record.txt'

    def run_guard(self, mode='ok', plan=None, launch_extra=None, args=(), preexisting=None):
        launch = {'argv': [sys.executable, '-u', str(self.fake), mode, str(self.record)]}
        launch.update(launch_extra or {})
        (self.root / 'launch.json').write_text(json.dumps(launch), encoding='utf-8')
        (self.root / 'plan.json').write_text(json.dumps(plan if plan is not None else [
            {'command': 'first', 'expect': ['value']}, {'command': 'second'}]), encoding='utf-8')
        events = self.root / 'events.json'
        transcript = self.root / 'transcript.bin'
        if preexisting:
            (events if preexisting == 'events' else transcript).write_bytes(b'keep')
        result = subprocess.run([sys.executable, str(GUARD), '--launch', str(self.root / 'launch.json'),
            '--plan', str(self.root / 'plan.json'), '--events', str(events), '--transcript', str(transcript),
            '--startup-timeout', '.5', '--step-timeout', '.5', *args], capture_output=True, timeout=8)
        data = json.loads(events.read_text(encoding='utf-8')) if events.exists() and preexisting != 'events' else None
        commands = self.record.read_text(encoding='utf-8').splitlines() if self.record.exists() else []
        return result, data, commands

    def test_success_and_log_after_prompt(self):
        result, data, commands = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data['result'], 'passed')
        self.assertEqual(commands, ['first', 'second', 'exit'])
        self.assertEqual([s['result'] for s in data['steps']], ['passed', 'passed'])

    def test_failed_reply_stops_next_command(self):
        for mode, expected in [('ko', 'ambiguous'), ('ambiguous', 'ambiguous'),
                               ('malformed', 'timeout'), ('status_after_prompt', 'ambiguous'), ('timeout', 'timeout'),
                               ('exit', 'process exited'), ('reject', 'rejected')]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory)
                self.fake = self.root / 'fake.py'
                self.fake.write_text(FAKE, encoding='utf-8')
                self.record = self.root / 'record.txt'
                result, data, commands = self.run_guard(mode, [
                    {'command': 'first', 'reject': ['forbidden']}, {'command': 'second'}])
                self.assertEqual(result.returncode, 2)
                self.assertEqual(data['result'], 'failed')
                self.assertEqual(data['steps'][0]['result'], 'failed')
                self.assertIn(expected, data['error'])
                self.assertNotIn('second', commands)

    def test_missing_expected_stops_next_command(self):
        result, data, commands = self.run_guard(plan=[{'command': 'first', 'expect': ['missing']},
                                                       {'command': 'second'}])
        self.assertEqual(result.returncode, 2)
        self.assertIn('expected output', data['error'])
        self.assertNotIn('second', commands)

    def test_existing_outputs_are_not_overwritten(self):
        for name in ('events', 'transcript'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory)
                result, _, _ = self.run_guard(preexisting=name)
                path = self.root / ('events.json' if name == 'events' else 'transcript.bin')
                self.assertEqual(result.returncode, 2)
                self.assertEqual(path.read_bytes(), b'keep')

    def test_invalid_cwd_records_failure(self):
        result, data, commands = self.run_guard(launch_extra={'cwd': ['bad']})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(data['result'], 'failed')
        self.assertIn('cwd', data['error'])
        self.assertEqual(commands, [])

    def test_nonzero_exit_after_success_fails_run(self):
        result, data, commands = self.run_guard(mode='exit_after_success')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(data['result'], 'failed')
        self.assertEqual(data['process_exit'], 4)
        self.assertEqual(commands, ['first', 'second', 'exit'])

    def test_invalid_timeouts_are_rejected_before_launch(self):
        for value in (float('inf'), float('nan'), 1e100, -1, 0, '1', True, 10**400):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory)
                result, _, commands = self.run_guard(plan=[{'command': 'first', 'timeout': value}])
                self.assertEqual(result.returncode, 2)
                self.assertEqual(commands, [])
        for arg in ('--startup-timeout', '--step-timeout'):
            with self.subTest(arg=arg), tempfile.TemporaryDirectory() as directory:
                self.root = Path(directory)
                result, _, commands = self.run_guard(args=(arg, 'nan'))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(commands, [])


if __name__ == '__main__':
    unittest.main()
