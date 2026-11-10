import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


@unittest.skipUnless(os.name == 'nt', 'Windows AppContainer launcher')
class OfflineRunnerTests(unittest.TestCase):
    def test_launcher_compiles(self):
        csc = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework/v4.0.30319/csc.exe'
        with tempfile.TemporaryDirectory(dir=SCRIPTS.parent) as directory:
            exe = Path(directory) / 'launcher.exe'
            result = subprocess.run([str(csc), '/nologo', '/target:exe', f'/out:{exe}',
                str(SCRIPTS / 'offline_launcher.cs')], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(exe.is_file())
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Usage:', result.stderr)

    def test_invalid_work_directory_fails(self):
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-File',
            str(SCRIPTS / 'offline_run.ps1'), '-WorkDir', 'relative', '-ProfileName', 'unused',
            '-ProfileSid', 'unused', '-Python', 'unused', '-Launch', 'unused', '-Plan', 'unused',
            '-Events', 'unused', '-Transcript', 'unused'], capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('WorkDir must be', result.stderr)


if __name__ == '__main__':
    unittest.main()
