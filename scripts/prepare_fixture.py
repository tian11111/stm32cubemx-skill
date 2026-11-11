#!/usr/bin/env python3
"""Prepare an independent F103 sample with a local, version-matched firmware copy."""
import argparse
import json
import os
import shutil
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


def prepare(baseline, firmware, destination):
    baseline = baseline.resolve(strict=True)
    firmware = firmware.resolve(strict=True)
    destination = destination.resolve()
    if not baseline.is_dir() or not firmware.is_dir():
        raise ValueError('baseline and firmware must be existing directories')
    if destination.exists() or any(destination == p or destination in p.parents or p in destination.parents
                                   for p in (baseline, firmware)):
        raise ValueError('destination must be new and separate from input directories')
    package = ET.parse(firmware / 'package.xml').getroot().find('PackDescription')
    if package is None or package.get('Patch') != 'FW.F1.1.8.7':
        raise ValueError('expected STM32Cube FW_F1 V1.8.7 package')
    for required in ('Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal.c',
                     'Drivers/CMSIS/Device/ST/STM32F1xx/Include/stm32f103xb.h'):
        if not (firmware / required).is_file():
            raise ValueError('firmware package missing required file: ' + required)
    ioc = baseline / 'FixedF103Patched.ioc'
    text = ioc.read_text(encoding='utf-8-sig')
    if 'ProjectManager.CustomerFirmwarePackage=..\\\\..\\\\firmware-f1' not in text:
        raise ValueError('baseline firmware path differs from expected layout')
    reject_links(baseline)
    reject_links(firmware)
    # Leave partial output for inspection on failure; never delete user data.
    destination.mkdir(parents=False)
    shutil.copytree(firmware, destination / 'firmware-f1')
    (destination / 'output').mkdir()
    project = destination / 'output' / 'FixedF103Patched'
    shutil.copytree(baseline, project)
    if not (project / '..' / '..' / 'firmware-f1' / 'package.xml').is_file():
        raise ValueError('prepared firmware layout verification failed')
    return {'result': 'pass', 'project': str(project), 'firmware': str(destination / 'firmware-f1'),
            'limits': 'Path and package metadata checked; CubeMX compatibility and hardware are not implied.'}


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
