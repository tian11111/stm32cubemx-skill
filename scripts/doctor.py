#!/usr/bin/env python3
"""Read-only discovery; never starts CubeMX or installs software."""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', help='optional .ioc path')
    p.add_argument('--cubemx', help='optional CubeMX executable path')
    p.add_argument('--firmware', help='optional local firmware directory')
    p.add_argument('--version-events', help='optional events JSON from a checked CubeMX get version probe')
    a = p.parse_args()
    tools = {}
    for name in ('cmake', 'ninja', 'arm-none-eabi-gcc'):
        path = shutil.which(name)
        info = {'path': path, 'version': None}
        if path:
            try:
                run = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=5)
                info['version'] = run.stdout.splitlines()[0] if run.returncode == 0 and run.stdout else None
            except (OSError, subprocess.TimeoutExpired, UnicodeError):
                pass
        tools[name] = info
    candidates = [shutil.which('STM32CubeMX')]
    for env in ('LOCALAPPDATA', 'PROGRAMFILES'):
        if os.environ.get(env):
            base = Path(os.environ[env])
            candidates.extend([str(base / 'Programs/STM32CubeMX/STM32CubeMX.exe'), str(base / 'STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX.exe')])
    discovered = next((str(Path(c).resolve()) for c in candidates if c and Path(c).is_file()), None)
    version = None
    if a.version_events:
        try:
            events = json.loads(Path(a.version_events).read_text(encoding='utf-8-sig'))
            if events.get('result') == 'passed':
                for step in events.get('steps', []):
                    if step.get('command') == 'get version' and step.get('result') == 'passed':
                        import re
                        match = re.search(r'(?m)^\s*(\d+\.\d+\.\d+)\s*$', step.get('response_tail', ''))
                        if match:
                            version = match.group(1)
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    result = {'platform': platform.platform(), 'python': platform.python_version(),
              'tools': tools,
              'cubemx': str(Path(a.cubemx).resolve()) if a.cubemx and Path(a.cubemx).is_file() else (discovered if not a.cubemx else None),
              'cubemx_version_from_events': version,
              'firmware': str(Path(a.firmware).resolve()) if a.firmware and Path(a.firmware).is_dir() else None,
              'ioc': str(Path(a.project).resolve()) if a.project and Path(a.project).is_file() else None,
              'limits': 'Build tools were queried with --version. CubeMX was not started; event-derived version is not tied to the detected installation. Firmware compatibility and offline isolation are unverified.'}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if any((a.project and not result['ioc'], a.cubemx and not result['cubemx'], a.firmware and not result['firmware'])) else 0


if __name__ == '__main__':
    sys.exit(main())
