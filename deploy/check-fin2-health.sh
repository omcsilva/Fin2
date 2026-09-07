#!/bin/bash
set -euo pipefail

data_dir=/var/lib/fin2
backup_dir=/var/backups/fin2
max_disk_percent=85
max_backup_age_seconds=$((36 * 60 * 60))

systemctl is-active --quiet fin2.service
curl --fail --silent --show-error --output /dev/null http://127.0.0.1:8020/fin2/
test -s "$data_dir/fin2.duckdb"

disk_percent=$(df --output=pcent "$data_dir" | tail -n 1 | tr -cd '0-9')
if [ -z "$disk_percent" ] || [ "$disk_percent" -ge "$max_disk_percent" ]; then
    echo "Fin2 disk usage is ${disk_percent:-unknown}% (limit ${max_disk_percent}%)" >&2
    exit 1
fi

latest_backup=$(find "$backup_dir" -mindepth 1 -maxdepth 1 -type d \
    -regextype posix-extended -regex '.*/[0-9]{8}T[0-9]{6}Z' \
    -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)
if [ -z "$latest_backup" ]; then
    echo "No regular Fin2 backup found" >&2
    exit 1
fi

backup_age=$(( $(date +%s) - $(stat -c %Y "$latest_backup") ))
if [ "$backup_age" -gt "$max_backup_age_seconds" ]; then
    echo "Latest Fin2 backup is ${backup_age}s old (limit ${max_backup_age_seconds}s)" >&2
    exit 1
fi
test -s "$latest_backup/manifest.json"
test -s "$latest_backup/data/fin2.duckdb"
test -s "$latest_backup/external-copy.sha256"

echo "Fin2 healthy: disk=${disk_percent}% backup=$(basename "$latest_backup") age=${backup_age}s"
