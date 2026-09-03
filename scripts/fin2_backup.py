"""Offline copy and integrity verification. Stop all database writers first."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symbolic links are not supported')
        if path.is_file():
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            result[path.relative_to(root).as_posix()] = digest.hexdigest()
    return result


def verify(snapshot):
    expected = json.loads((snapshot / 'manifest.json').read_text())
    if inventory(snapshot / 'data') != expected:
        raise ValueError('Backup integrity mismatch')
    return expected


def backup(source, destination):
    source, destination = source.resolve(), destination.resolve()
    if destination == source or source in destination.parents:
        raise ValueError('Backup must be outside the data directory')
    if not (source / 'fin2.duckdb').is_file():
        raise ValueError('Database missing')
    before = inventory(source)
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copytree(source, destination / 'data')
    if inventory(source) != before or inventory(destination / 'data') != before:
        raise ValueError('Source changed or copy failed; backup is incomplete')
    (destination / 'manifest.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
    verify(destination)


def restore(snapshot, destination):
    verify(snapshot)
    if destination.exists():
        raise ValueError('Restore destination must not exist')
    shutil.copytree(snapshot / 'data', destination)
    if inventory(destination) != verify(snapshot):
        raise ValueError('Restore integrity mismatch')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'verify', 'restore'])
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path, nargs='?')
    args = parser.parse_args()
    if args.action != 'verify' and args.destination is None:
        parser.error('destination is required')
    if args.action == 'backup': backup(args.source, args.destination)
    elif args.action == 'restore': restore(args.source, args.destination)
    else: verify(args.source)
    print('Integrity verification passed')
