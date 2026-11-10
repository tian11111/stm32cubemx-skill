#!/usr/bin/env python3
"""Check explicitly requested generated artifacts and compare a baseline."""
import argparse
import json
import re
import sys
from pathlib import Path


def within(root, name):
    root = root.resolve(strict=True)
    p = Path(name)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError('path must be relative and inside the project: ' + name)
    resolved = (root / p).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('path escapes project: ' + name)
    return resolved


def properties(path):
    result = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line or line.lstrip().startswith(('#', '!')):
            continue
        m = re.match(r'((?:\\.|[^=:])*)[=:](.*)$', line)
        if not m:
            continue
        key = re.sub(r'\\([#:=\\ ])', r'\1', m.group(1))
        if key in result:
            raise ValueError('duplicate .ioc key: ' + key)
        result[key] = m.group(2)
    return result


MARKER = re.compile(r'^\s*(?://|/\*)\s*USER CODE\s+(BEGIN|END)\s+([^\r\n*]+?)\s*(?:\*/)?\s*$', re.M)


def user_blocks(path):
    text = path.read_text(encoding='utf-8-sig')
    blocks, active = {}, None
    for m in MARKER.finditer(text):
        kind, name = m.group(1), m.group(2).strip()
        if kind == 'BEGIN':
            if active or name in blocks:
                raise ValueError('nested or duplicate USER CODE marker: ' + str(path))
            active = (name, m.end())
        else:
            if not active or active[0] != name:
                raise ValueError('unmatched USER CODE marker: ' + str(path))
            blocks[name] = text[active[1]:m.start()]
            active = None
    if active:
        raise ValueError('unclosed USER CODE marker: ' + str(path))
    return blocks


def verify(root, spec, baseline=None):
    checks = []
    def add(kind, name, ok, detail=''):
        checks.append(dict(kind=kind, target=name, status='pass' if ok else 'fail', detail=detail))
    ioc_name = spec['ioc']
    actual = properties(within(root, ioc_name))
    for key, value in spec.get('ioc_values', {}).items():
        add('ioc', key, actual.get(key) == value, 'actual=' + repr(actual.get(key)))
    for name in spec.get('files', []):
        add('file', name, within(root, name).is_file())
    for item in spec.get('functions', []):
        path = within(root, item['file'])
        # This detects a named function definition, not its behavior or C semantics.
        pattern = r'\b' + re.escape(item['name']) + r'\s*\([^;{}]*\)\s*\{'
        text = path.read_text(encoding='utf-8-sig') if path.is_file() else ''
        text = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', ' ', text, flags=re.S)
        add('function', item['file'] + ':' + item['name'], bool(re.search(pattern, text)))
    for prefix in spec.get('unchanged_ioc_prefixes', []):
        if baseline is None:
            add('ioc_unchanged', prefix, False, 'baseline required')
        else:
            old = properties(within(baseline, ioc_name))
            a = {k: v for k, v in actual.items() if k.startswith(prefix)}
            b = {k: v for k, v in old.items() if k.startswith(prefix)}
            add('ioc_unchanged', prefix, bool(a or b) and a == b, 'baseline comparison')
    for name in spec.get('user_code_files', []):
        if baseline is None:
            add('user_code', name, False, 'baseline required')
        elif not within(baseline, name).is_file() or not within(root, name).is_file():
            add('user_code', name, False, 'file missing')
        else:
            before, after = user_blocks(within(baseline, name)), user_blocks(within(root, name))
            add('user_code', name, bool(before) and before == after, 'all named regions compared')
    if not checks:
        raise ValueError('no checks requested')
    return {'result': 'pass' if all(c['status'] == 'pass' for c in checks) else 'fail', 'checks': checks,
            'limits': 'Only explicitly requested checks; no full C semantic, electrical or hardware validation.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', required=True)
    p.add_argument('--spec', required=True, help='JSON specification of explicit checks')
    p.add_argument('--baseline')
    args = p.parse_args()
    try:
        root = Path(args.project).resolve(strict=True)
        baseline = Path(args.baseline).resolve(strict=True) if args.baseline else None
        spec = json.loads(Path(args.spec).read_text(encoding='utf-8-sig'))
        if not isinstance(spec, dict) or not isinstance(spec.get('ioc'), str):
            raise ValueError('spec requires ioc relative path')
        output = verify(root, spec, baseline)
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        output = {'result': 'error', 'error': str(exc)}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output['result'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
