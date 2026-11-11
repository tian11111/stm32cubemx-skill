#!/usr/bin/env python3
"""Prepare an independent F103 sample with a local, version-matched firmware copy."""
import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def reject_links(root):
    def fail(error):
        raise error
    for current, dirs, files in os.walk(root, followlinks=False, onerror=fail):
        for name in dirs + files:
            path = Path(current) / name
            if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
                raise ValueError('links or reparse points are not supported: ' + str(path))


def reject_link_ancestors(path):
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            if part.is_symlink() or getattr(part.lstat(), 'st_file_attributes', 0) & 0x400:
                raise ValueError('links or reparse points are not supported: ' + str(part))


def manifest(root):
    reject_links(root)
    result = {}
    def fail(error):
        raise error
    for current, _, files in os.walk(root, followlinks=False, onerror=fail):
        for name in files:
            path = Path(current) / name
            if not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError('non-regular file is not supported: ' + str(path))
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            result[path.relative_to(root).as_posix()] = digest.hexdigest()
    return result


def verify_manifest(expected, actual, label):
    for name in sorted(expected.keys() | actual.keys()):
        if name not in actual:
            raise ValueError(label + ' missing file: ' + name)
        if name not in expected:
            raise ValueError(label + ' unexpected file: ' + name)
        if expected[name] != actual[name]:
            raise ValueError(label + ' SHA-256 mismatch: ' + name)


def verify_ioc(ioc):
    expected = {'Mcu.CPN': 'STM32F103CBT6', 'Mcu.Name': 'STM32F103C(8-B)Tx',
                'PA5.Signal': 'GPIO_Output', 'PA5.Locked': 'true',
                'ProjectManager.CustomerFirmwarePackage': '..\\\\..\\\\firmware-f1'}
    values = {}
    for line in ioc.read_text(encoding='utf-8-sig').splitlines():
        key, separator, value = line.partition('=')
        if separator and key in expected:
            if key in values:
                raise ValueError('duplicate target .ioc key: ' + key)
            values[key] = value
    for key, value in expected.items():
        if values.get(key) != value:
            raise ValueError('target .ioc configuration mismatch: ' + key)


def verify_firmware(firmware):
    package = ET.parse(firmware / 'package.xml').getroot().find('PackDescription')
    if package is None or package.get('Patch') != 'FW.F1.1.8.7':
        raise ValueError('expected STM32Cube FW_F1 V1.8.7 package')
    for required in ('Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal.c',
                     'Drivers/CMSIS/Device/ST/STM32F1xx/Include/stm32f103xb.h'):
        if not (firmware / required).is_file():
            raise ValueError('firmware package missing required file: ' + required)


def prepare(baseline, firmware, destination):
    baseline = Path(os.path.abspath(baseline))
    firmware = Path(os.path.abspath(firmware))
    destination = Path(os.path.abspath(destination))
    for path in (baseline, firmware, destination):
        reject_link_ancestors(path)
    baseline = baseline.resolve(strict=True)
    firmware = firmware.resolve(strict=True)
    destination = destination.resolve()
    if not baseline.is_dir() or not firmware.is_dir():
        raise ValueError('baseline and firmware must be existing directories')
    if destination.exists() or any(destination == p or destination in p.parents or p in destination.parents
                                   for p in (baseline, firmware)):
        raise ValueError('destination must be new and separate from input directories')
    baseline_before = manifest(baseline)
    firmware_before = manifest(firmware)
    verify_firmware(firmware)
    ioc = baseline / 'FixedF103Patched.ioc'
    text = ioc.read_text(encoding='utf-8-sig')
    if 'ProjectManager.CustomerFirmwarePackage=..\\\\..\\\\firmware-f1' not in text:
        raise ValueError('baseline firmware path differs from expected layout')
    # Leave partial output for inspection on failure; never delete user data.
    destination.mkdir(parents=False)
    shutil.copytree(firmware, destination / 'firmware-f1')
    (destination / 'output').mkdir()
    project = destination / 'output' / 'FixedF103Patched'
    shutil.copytree(baseline, project)
    verify_manifest(baseline_before, manifest(project), 'target baseline')
    verify_manifest(firmware_before, manifest(destination / 'firmware-f1'), 'target firmware')
    verify_ioc(project / 'FixedF103Patched.ioc')
    verify_firmware(destination / 'firmware-f1')
    if not (project / '..' / '..' / 'firmware-f1' / 'package.xml').is_file():
        raise ValueError('prepared firmware layout verification failed')
    verify_manifest(baseline_before, manifest(baseline), 'source baseline changed')
    verify_manifest(firmware_before, manifest(firmware), 'source firmware changed')
    return {'result': 'pass', 'project': str(project), 'firmware': str(destination / 'firmware-f1'),
            'limits': 'SHA-256 file manifests and key configuration checked; CubeMX compatibility and hardware are not implied.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--baseline', required=True, help='existing FixedF103Patched generated project')
    args = parser.parse_args()
    try:
        result = prepare(Path(args.baseline), Path(args.firmware), Path(args.destination))
    except (OSError, ValueError, ET.ParseError) as exc:
        result = {'result': 'error', 'error': str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['result'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
