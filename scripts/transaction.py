#!/usr/bin/env python3
"""Copy a project to a new workspace and compare it with an immutable baseline."""
import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def scan(root):
    if not root.is_dir():
        raise ValueError('directory missing: ' + str(root))
    files = {}
    def fail(error):
        raise error
    for current, dirs, names in os.walk(root, followlinks=False, onerror=fail):
        for name in dirs + names:
            path = Path(current) / name
            if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
                raise ValueError('links or reparse points are unsupported: ' + str(path))
        for name in names:
            path = Path(current) / name
            if not path.is_file():
                raise ValueError('non-regular file unsupported: ' + str(path))
            files[path.relative_to(root).as_posix()] = digest(path)
    return files


def create(source, workspace):
    source = source.resolve(strict=True)
    if not source.is_dir():
        raise ValueError('source must be a directory')
    workspace = workspace.resolve()
    if workspace.exists() or source in workspace.parents or workspace in source.parents:
        raise ValueError('workspace must be a new, separate directory')
    before = scan(source)
    # A partially created workspace is deliberately retained for inspection on error.
    workspace.mkdir(parents=False)
    shutil.copytree(source, workspace / 'baseline', symlinks=False)
    shutil.copytree(source, workspace / 'working', symlinks=False)
    if before != scan(source) or before != scan(workspace / 'baseline') or before != scan(workspace / 'working'):
        raise ValueError('source changed during copy; discard workspace after review')
    (workspace / 'manifest.json').write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'result': 'pass', 'workspace': str(workspace), 'files': len(before)}


def compare(workspace):
    root = workspace.resolve(strict=True)
    recorded = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if scan(root / 'baseline') != recorded:
        raise ValueError('baseline changed since snapshot')
    new = scan(root / 'working')
    return {'result': 'pass', 'added': sorted(new.keys() - recorded.keys()),
            'deleted': sorted(recorded.keys() - new.keys()),
            'modified': sorted(k for k in new.keys() & recorded.keys() if new[k] != recorded[k]),
            'limits': 'No files are applied or restored to the original project.'}


def restore(workspace, destination):
    root = workspace.resolve(strict=True)
    recorded = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if scan(root / 'baseline') != recorded:
        raise ValueError('baseline changed since snapshot')
    destination = destination.resolve()
    if destination.exists() or root in destination.parents or destination in root.parents:
        raise ValueError('restore destination must be a new, separate directory')
    shutil.copytree(root / 'baseline', destination, symlinks=False)
    if scan(destination) != recorded:
        raise ValueError('restored copy differs from baseline; inspect destination')
    return {'result': 'pass', 'destination': str(destination), 'limits': 'Restored to a new directory only; original project was not modified.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    create_p = sub.add_parser('create')
    create_p.add_argument('--source', required=True)
    create_p.add_argument('--workspace', required=True)
    diff_p = sub.add_parser('diff')
    diff_p.add_argument('--workspace', required=True)
    restore_p = sub.add_parser('restore')
    restore_p.add_argument('--workspace', required=True)
    restore_p.add_argument('--destination', required=True)
    args = p.parse_args()
    try:
        if args.action == 'create':
            out = create(Path(args.source), Path(args.workspace))
        elif args.action == 'diff':
            out = compare(Path(args.workspace))
        else:
            out = restore(Path(args.workspace), Path(args.destination))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        out = {'result': 'error', 'error': str(exc)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out['result'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
