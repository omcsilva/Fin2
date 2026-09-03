"""Apply an explicitly approved retention plan under the deployment lock (Linux)."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

if __package__:
    from .retention_plan import plan, verify_external_ssh
else:
    from retention_plan import plan, verify_external_ssh


def apply(approved, current, backups, releases, active, previous, git_check, remove=shutil.rmtree):
    if sorted(approved, key=lambda r: r['path']) != sorted(current, key=lambda r: r['path']):
        raise ValueError('State changed: generate and approve a new plan')
    roots = (backups.resolve(strict=True), releases.resolve(strict=True))
    protected = {active.resolve(strict=True), previous.resolve(strict=True)}
    targets = []
    for row in current:
        if row['action'] != 'candidate':
            continue
        path = Path(row['path'])
        resolved = path.resolve(strict=True)
        if path.is_symlink() or resolved != path or resolved.parent not in roots or resolved in protected:
            raise ValueError('Unsafe removal target')
        if resolved.parent == roots[1] and not git_check(resolved.name):
            raise ValueError('Release commit unavailable in Git; preserving all candidates')
        targets.append(resolved)
    # All checks precede the first deletion. A filesystem error aborts further deletions.
    for path in targets:
        remove(path)
        print('Removed:', path, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', required=True, type=Path)
    parser.add_argument('--approved-plan', required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Production execution is supported only on Linux')
    import fcntl
    backups, releases = Path('/var/backups/fin2'), Path('/opt/fin2-releases')
    if any(p.is_symlink() or p.resolve() != p for p in (backups, releases)):
        raise ValueError('Storage roots must not be symbolic links')
    with open('/run/lock/fin2-backup.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = Path(subprocess.check_output(
            ['systemctl', 'show', 'fin2', '-p', 'WorkingDirectory', '--value'], text=True).strip())
        current = plan(backups, releases, active, args.previous, verify_external_ssh)
        approved = json.loads(args.approved_plan.read_text())
        def git_check(commit):
            repo = '/home/mcsil/fin2.git'
            return subprocess.run(['git', '-c', 'safe.directory='+repo, '--git-dir='+repo,
                'cat-file', '-e', commit+'^{commit}'], capture_output=True).returncode == 0
        apply(approved, current, backups, releases, active, args.previous, git_check)


if __name__ == '__main__':
    main()
