import importlib.util
import tempfile
import unittest
from unittest import mock
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
        (self.baseline / 'FixedF103Patched.ioc').write_text(
            'Mcu.CPN=STM32F103CBT6\nMcu.Name=STM32F103C(8-B)Tx\n'
            'PA5.Signal=GPIO_Output\nPA5.Locked=true\n'
            'ProjectManager.CustomerFirmwarePackage=..\\\\..\\\\firmware-f1\n')
        (self.baseline / 'generated.c').write_text('original generated code')
        (self.firmware / 'package.xml').write_text('<Package><PackDescription Patch="FW.F1.1.8.7"/></Package>')
        for relative in ('Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal.c',
                         'Drivers/CMSIS/Device/ST/STM32F1xx/Include/stm32f103xb.h'):
            path = self.firmware / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('test')

    def test_prepares_relocatable_layout_without_modifying_source(self):
        before_baseline = module.manifest(self.baseline)
        before_firmware = module.manifest(self.firmware)
        result = prepare(self.baseline, self.firmware, self.root / 'new')
        project = Path(result['project'])
        self.assertTrue((project / '..' / '..' / 'firmware-f1' / 'package.xml').is_file())
        self.assertTrue((self.baseline / 'FixedF103Patched.ioc').is_file())
        self.assertEqual(before_baseline, module.manifest(self.baseline))
        self.assertEqual(before_firmware, module.manifest(self.firmware))
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

    def test_rejects_changed_source_after_copy(self):
        original_copytree = module.shutil.copytree
        def copy_then_change(source, target, *args, **kwargs):
            result = original_copytree(source, target, *args, **kwargs)
            if Path(source) == self.baseline:
                (self.firmware / 'package.xml').write_text('changed')
            return result
        with mock.patch.object(module.shutil, 'copytree', side_effect=copy_then_change):
            with self.assertRaisesRegex(ValueError, 'source firmware changed SHA-256 mismatch: package.xml'):
                prepare(self.baseline, self.firmware, self.root / 'new')
        self.assertTrue((self.root / 'new').exists())

    def test_rejects_added_source_file_after_copy(self):
        original_copytree = module.shutil.copytree
        def copy_then_add(source, target, *args, **kwargs):
            result = original_copytree(source, target, *args, **kwargs)
            if Path(source) == self.baseline:
                (self.baseline / 'new.c').write_text('new')
            return result
        with mock.patch.object(module.shutil, 'copytree', side_effect=copy_then_add):
            with self.assertRaisesRegex(ValueError, 'source baseline changed unexpected file: new.c'):
                prepare(self.baseline, self.firmware, self.root / 'new')

    def test_rejects_target_missing_or_changed_file(self):
        original_copytree = module.shutil.copytree
        for missing in (True, False):
            def corrupt(source, target, *args, **kwargs):
                result = original_copytree(source, target, *args, **kwargs)
                if Path(source) == self.baseline:
                    path = Path(target) / 'generated.c'
                    path.unlink() if missing else path.write_text('wrong')
                return result
            with self.subTest(missing=missing), mock.patch.object(module.shutil, 'copytree', side_effect=corrupt):
                expected = 'missing file' if missing else 'SHA-256 mismatch'
                with self.assertRaisesRegex(ValueError, 'target baseline ' + expected + ': generated.c'):
                    prepare(self.baseline, self.firmware, self.root / ('missing' if missing else 'changed'))

    def test_rejects_bad_target_configuration(self):
        ioc = self.baseline / 'FixedF103Patched.ioc'
        ioc.write_text(ioc.read_text().replace('PA5.Signal=GPIO_Output', 'PA5.Signal=wrong'))
        with self.assertRaisesRegex(ValueError, 'target .ioc configuration mismatch: PA5.Signal'):
            prepare(self.baseline, self.firmware, self.root / 'new')

    def test_rejects_source_link(self):
        try:
            (self.baseline / 'link').symlink_to(self.baseline / 'generated.c')
        except (OSError, NotImplementedError):
            self.skipTest('symlink creation unavailable')
        with self.assertRaisesRegex(ValueError, 'links or reparse points'):
            prepare(self.baseline, self.firmware, self.root / 'new')


if __name__ == '__main__':
    unittest.main()
