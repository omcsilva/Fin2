"""Read-only retention proposal; never removes files or versions."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
if __package__:
    from .fin2_backup import verify
else:
    from fin2_backup import verify


def receipt(snapshot):
    path = snapshot / 'external-copy.sha256'
    if path.is_symlink():
        return None
    try:
        digest, name = path.read_text().split()
    except (OSError, ValueError):
        return None
    if not re.fullmatch('[0-9a-f]{64}', digest) or name != f'fin2-{snapshot.name}.tar.gz.gpg':
        return None
    return digest, name


def verify_external_ssh(name, digest):
    # Names come from validated snapshot IDs, never arbitrary shell input.
    if not re.fullmatch(r'fin2-(pre-update-)?[0-9]{8}T[0-9]{6}Z\.tar\.gz\.gpg', name):
        return False
    try:
        result = subprocess.run([
            'ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'ConnectTimeout=10', '-i', '/etc/fin2/backup_ed25519',
            '-o', 'UserKnownHostsFile=/etc/fin2/backup_known_hosts',
            'mcsil@rpi5.lan', 'sha256sum /mnt/MERGERFS/Backup/Fin2/' + name
        ], capture_output=True, text=True, timeout=120, check=True)
        return result.stdout.split()[0] == digest
    except (OSError, subprocess.SubprocessError, IndexError):
        return False


def plan(backups, releases, active, previous=None, external_check=None):
    backups, releases = backups.resolve(strict=True), releases.resolve(strict=True)
    def release_path(path):
        if path.is_symlink():
            raise ValueError('Release cannot be a symbolic link')
        path = path.resolve(strict=True)
        if path.parent != releases or not path.is_dir() or not re.fullmatch('[0-9a-f]{40}', path.name):
            raise ValueError('Release must be an immediate child of releases')
        return path
    active = release_path(active)
    previous = release_path(previous) if previous else None
    result, valid = [], []
    def add(path, action, reason):
        result.append({'path': str(path), 'action': action, 'reason': reason})
    for item in backups.iterdir():
        match = re.fullmatch(r'(pre-update-)?(\d{8}T\d{6}Z)', item.name)
        if item.is_symlink() or not item.is_dir() or not match:
            add(item, 'keep', 'unrecognized')
            continue
        try:
            stamp = datetime.strptime(match[2], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
            if not (item / 'data/fin2.duckdb').is_file():
                raise ValueError('Missing database')
            verify(item)
        except (OSError, ValueError):
            add(item, 'keep', 'incomplete or invalid; inspect manually')
            continue
        valid.append((stamp, item))
    ordered = sorted(valid, reverse=True)
    for index, (_, item) in enumerate(ordered):
        if index == 0:
            add(item, 'keep', 'newest verified local backup')
            continue
        evidence = receipt(item)
        confirmed = bool(evidence and external_check and external_check(evidence[1], evidence[0]))
        add(item, 'candidate' if confirmed else 'keep',
            'external hash verified' if confirmed else 'external copy not confirmed')
    for item in releases.iterdir():
        if item.is_symlink() or not item.is_dir() or not re.fullmatch('[0-9a-f]{40}', item.name):
            add(item, 'keep', 'unrecognized')
        elif item == active or item == previous:
            add(item, 'keep', 'active or explicitly identified previous release')
        elif previous is None or previous == active:
            add(item, 'keep', 'previous release not identified')
        else:
            add(item, 'candidate', 'older release; verify Git recovery before removal')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('backups', 'releases', 'active'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--verify-external-ssh', action='store_true')
    args = parser.parse_args()
    print(json.dumps(plan(args.backups, args.releases, args.active, args.previous,
        verify_external_ssh if args.verify_external_ssh else None), indent=2))
