#!/bin/bash
set -euo pipefail
previous_file=/var/lib/fin2/previous-deployed-revision
if [ ! -f "$previous_file" ]; then
    echo "Previous release is not recorded; retention skipped"
    exit 0
fi
previous_hash=$(cat "$previous_file")
[[ "$previous_hash" =~ ^[0-9a-f]{40}$ ]] || { echo "Invalid previous revision"; exit 1; }
previous=/opt/fin2-releases/$previous_hash
[ -d "$previous" ] || { echo "Previous release directory is unavailable; retention skipped"; exit 0; }
active=$(systemctl show fin2 -p WorkingDirectory --value)
plan_file=$(mktemp /run/fin2-retention.XXXXXX.json)
trap 'rm -f "$plan_file"' EXIT
/opt/fin2/.venv/bin/python /opt/fin2/scripts/retention_plan.py \
  --backups /var/backups/fin2 --releases /opt/fin2-releases \
  --active "$active" --previous "$previous" --verify-external-ssh > "$plan_file"
/opt/fin2/.venv/bin/python /opt/fin2/scripts/apply_retention.py \
  --previous "$previous" --approved-plan "$plan_file"
