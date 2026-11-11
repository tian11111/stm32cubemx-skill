import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('bootstrap_fixture', SCRIPTS / 'bootstrap_fixture.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.firmware = self.root / 'firmware'
        self.firmware.mkdir()
        (self.firmware / 'package.xml').write_text('<Package><PackDescription Patch="FW.F1.1.8.7"/></Package>')
        for name in ('Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal.c',
                     'Drivers/CMSIS/Device/ST/STM32F1xx/Include/stm32f103xb.h'):
            path = self.firmware / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('test')
        self.launch = self.root / 'launch.json'
        self.launch.write_text('{}')
        self.destination = self.root / 'out'

    def create_generated(self):
        root = self.destination / 'output' / 'FixedF103Patched'
        (root / 'Src').mkdir(parents=True)
        (root / 'FixedF103Patched.ioc').write_text('Mcu.CPN=STM32F103CBT6\nMcu.Name=STM32F103C(8-B)Tx\nPA5.Signal=GPIO_Output\nPA5.Locked=true\nProjectManager.CustomerFirmwarePackage=..\\\\..\\\\firmware-f1\n')
        (root / 'Src/gpio.c').write_text('void MX_GPIO_Init(void) {}')
        for name in ('Src/sysmem.c', 'Src/syscalls.c', 'CMakeLists.txt'):
            (root / name).write_text('test')

    def test_guard_failure_does_not_claim_success(self):
        with mock.patch.object(bootstrap.subprocess, 'run', return_value=SimpleNamespace(returncode=2, stdout='', stderr='stop')):
            with self.assertRaisesRegex(ValueError, 'guard failed'):
                bootstrap.bootstrap(self.firmware, self.destination, self.launch)
        self.assertTrue((self.destination / 'bootstrap-plan.json').is_file())
        plan = json.loads((self.destination / 'bootstrap-plan.json').read_text(encoding='utf-8'))
        self.assertEqual(plan[0]['expect'], ['6.18.1\r\n'])
        self.assertNotIn('6.18.1\r\n', '6.18.10\r\n')

    def test_guard_success_still_rejects_missing_generated_file(self):
        def run(*args, **kwargs):
            self.create_generated()
            (self.destination / 'output/FixedF103Patched/Src/syscalls.c').unlink()
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        with mock.patch.object(bootstrap.subprocess, 'run', side_effect=run):
            with self.assertRaisesRegex(ValueError, 'did not pass'):
                bootstrap.bootstrap(self.firmware, self.destination, self.launch)

    def test_existing_destination_rejected(self):
        self.destination.mkdir()
        with self.assertRaisesRegex(ValueError, 'new directory'):
            bootstrap.bootstrap(self.firmware, self.destination, self.launch)
        self.assertEqual(list(self.destination.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
