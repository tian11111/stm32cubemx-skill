#!/usr/bin/env python3
"""Generate an F103 sample from local firmware and an explicitly prepared CubeMX launch."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from prepare_fixture import manifest, reject_link_ancestors, verify_firmware, verify_ioc, verify_manifest
from verify_project import verify


def cube_path(path):
    value = path.as_posix()
    if any(c in value for c in ('"', '\n', '\r')):
        raise ValueError('CubeMX path contains an unsupported quote or newline')
    return '"' + value + '"'


def bootstrap(firmware, destination, launch):
    firmware = Path(os.path.abspath(firmware))
    destination = Path(os.path.abspath(destination))
    for path in (firmware, destination):
        reject_link_ancestors(path)
    firmware = firmware.resolve(strict=True)
    destination = destination.resolve()
    launch = launch.resolve(strict=True)
    if not firmware.is_dir() or not launch.is_file():
        raise ValueError('firmware directory and launch file must exist')
    if destination.exists() or destination == firmware or destination in firmware.parents or firmware in destination.parents:
        raise ValueError('destination must be a new directory separate from firmware')
    if destination == launch or destination in launch.parents:
        raise ValueError('launch file must be outside the new destination')
    verify_firmware(firmware)
    original = manifest(firmware)
    # Failure leaves partial output and logs for inspection; never remove user files.
    destination.mkdir(parents=False)
    copied = destination / 'firmware-f1'
    shutil.copytree(firmware, copied)
    verify_manifest(original, manifest(copied), 'copied firmware')
    verify_manifest(original, manifest(firmware), 'source firmware changed')
    output = destination / 'output'
    output.mkdir()
    project = output / 'FixedF103Patched'
    plan = [
        {'command': 'get version', 'expect': ['6.18.1\r\n']},
        {'command': 'load STM32F103C(8-B)Tx', 'timeout': 90},
        {'command': 'get mcu name', 'expect': ['STM32F103C(8-B)Tx']},
        {'command': 'set pin PA5 GPIO_Output'},
        {'command': 'get signal PA5', 'expect': ['PA5: GPIO_Output']},
        {'command': 'project name FixedF103Patched'},
        {'command': 'project path ' + cube_path(output)},
        {'command': 'project toolchain CMake'},
        {'command': 'project setCustomFWPath ' + cube_path(copied)},
        {'command': 'project couplefilesbyip 1'},
        {'command': 'project generate', 'timeout': 180,
         'reject': ['FileNotFoundException', 'OutOfMemoryError', 'Problem in the project generation',
                    'Problem in the update of the project', 'Error in Project Generation']},
    ]
    plan_file = destination / 'bootstrap-plan.json'
    plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    events = destination / 'bootstrap-events.json'
    transcript = destination / 'bootstrap-transcript.log'
    guard = Path(__file__).resolve().with_name('cubemx_guard.py')
    args = [sys.executable, str(guard), '--launch', str(launch), '--plan', str(plan_file),
            '--events', str(events), '--transcript', str(transcript), '--startup-timeout', '120',
            '--settle-seconds', '0.2', '--log-reject', 'FileNotFoundException',
            '--log-reject', 'OutOfMemoryError']
    run = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (destination / 'guard-output.log').write_text(run.stdout + run.stderr, encoding='utf-8')
    if run.returncode != 0:
        raise ValueError('CubeMX guard failed; inspect bootstrap-events.json and bootstrap-transcript.log')
    verify_ioc(project / 'FixedF103Patched.ioc')
    spec = {'ioc': 'FixedF103Patched.ioc', 'ioc_values': {'PA5.Signal': 'GPIO_Output'},
            'files': ['Src/gpio.c', 'Src/sysmem.c', 'Src/syscalls.c', 'CMakeLists.txt'],
            'functions': [{'file': 'Src/gpio.c', 'name': 'MX_GPIO_Init'}]}
    report = verify(project.resolve(strict=True), spec)
    (destination / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if report['result'] != 'pass':
        raise ValueError('generated output did not pass requested verification')
    verify_manifest(original, manifest(copied), 'copied firmware changed')
    verify_manifest(original, manifest(firmware), 'source firmware changed')
    return {'result': 'pass', 'project': str(project), 'events': str(events), 'verification': str(destination / 'verification.json'),
            'limits': 'Only stated files and settings checked; build and hardware not verified. Network and filesystem isolation must be provided externally.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--firmware', required=True)
    p.add_argument('--destination', required=True)
    p.add_argument('--launch', required=True, help='prepared CubeMX -i guard launch JSON; provide appropriate isolation externally')
    args = p.parse_args()
    try:
        out = bootstrap(Path(args.firmware), Path(args.destination), Path(args.launch))
    except (OSError, ValueError, TypeError) as exc:
        out = {'result': 'error', 'error': str(exc)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out['result'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
