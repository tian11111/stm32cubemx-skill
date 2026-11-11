import importlib.util
import tempfile
import unittest
from pathlib import Path
spec = importlib.util.spec_from_file_location('prepare_fixture', Path(__file__).resolve().parents[1] / 'scripts' / 'prepare_fixture.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
prepare = module.prepare


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.baseline = self.root / 'baseline'
        self.firmware = self.root / 'firmware'
        self.baseline.mkdir(); self.firmware.mkdir()
        (self.baseline / 'FixedF103Patched.ioc').write_text('ProjectManager.CustomerFirmwarePackage=..\\\\..\\\\firmware-f1\n')
        (self.firmware / 'package.xml').write_text('<Package><PackDescription Patch="FW.F1.1.8.7"/></Package>')
        for relative in ('Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal.c',
                         'Drivers/CMSIS/Device/ST/STM32F1xx/Include/stm32f103xb.h'):
            path = self.firmware / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('test')

    def test_prepares_relocatable_layout_without_modifying_source(self):
        result = prepare(self.baseline, self.firmware, self.root / 'new')
        project = Path(result['project'])
        self.assertTrue((project / '..' / '..' / 'firmware-f1' / 'package.xml').is_file())
        self.assertTrue((self.baseline / 'FixedF103Patched.ioc').is_file())
        with self.assertRaises(ValueError):
            prepare(self.baseline, self.firmware, self.root / 'new')

    def test_rejects_wrong_package_and_nested_destination(self):
        (self.firmware / 'package.xml').write_text('<Package><PackDescription Patch="FW.F4.1.2.3"/></Package>')
        with self.assertRaises(ValueError):
            prepare(self.baseline, self.firmware, self.root / 'other')
        with self.assertRaises(ValueError):
            prepare(self.baseline, self.firmware, self.baseline / 'child')

    def test_rejects_incomplete_package(self):
        (self.firmware / 'Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal.c').unlink()
        with self.assertRaises(ValueError):
            prepare(self.baseline, self.firmware, self.root / 'other')


if __name__ == '__main__':
    unittest.main()
