"""Read-only retention proposal: this command never deletes files."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re


def plan(backups, releases, active, daily=7, updates=3, versions=3):
    if min(daily, updates, versions) < 1:
        raise ValueError('Keep at least one item in each category')
    active = active.resolve(strict=True)
    root = releases.resolve(strict=True)
    if active.parent != root or not re.fullmatch('[0-9a-f]{40}', active.name):
        raise ValueError('Active release must be an immediate child of releases')
    result = []
    groups = {'daily': [], 'pre-update': [], 'release': []}
    for item in backups.iterdir():
        match = re.fullmatch(r'(pre-update-)?(\d{8}T\d{6}Z)', item.name)
        if item.is_symlink() or not item.is_dir() or not match:
            result.append({'path': str(item), 'action': 'keep', 'reason': 'unrecognized'})
            continue
        try:
            stamp = datetime.strptime(match[2], '%Y%m%dT%H%M%SZ').timestamp()
        except ValueError:
            result.append({'path': str(item), 'action': 'keep', 'reason': 'invalid date'})
            continue
        # Incomplete snapshots are not safe to remove automatically.
        if not (item/'manifest.json').is_file() or not (item/'data/fin2.duckdb').is_file():
            result.append({'path': str(item), 'action': 'keep', 'reason': 'needs inspection'})
            continue
        groups['pre-update' if match[1] else 'daily'].append((stamp, item))
    for item in releases.iterdir():
        if item.is_symlink() or not item.is_dir() or not re.fullmatch('[0-9a-f]{40}', item.name):
            result.append({'path': str(item), 'action': 'keep', 'reason': 'unrecognized'})
        else:
            groups['release'].append((item.stat().st_mtime, item))
    for category, count in [('daily', daily), ('pre-update', updates), ('release', versions)]:
        ordered = sorted(groups[category], reverse=True)
        keep = {item for _, item in ordered[:count]}
        if category == 'release':
            keep.add(active)
        for _, item in ordered:
            retained = item.resolve() == active or item in keep
            result.append({'path': str(item), 'action': 'keep' if retained else 'candidate',
                           'reason': category})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backups', required=True, type=Path)
    parser.add_argument('--releases', required=True, type=Path)
    parser.add_argument('--active', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(plan(args.backups, args.releases, args.active), indent=2))
