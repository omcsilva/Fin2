#!/bin/bash
set -euo pipefail
umask 077
exec 9>/run/lock/fin2-backup.lock
flock -n 9
was_active=0
if systemctl is-active --quiet fin2.service; then was_active=1; fi
restart_service() {
    if [ "$was_active" = 1 ]; then systemctl start fin2.service; fi
}
trap restart_service EXIT
systemctl stop fin2.service
snapshot="/var/backups/fin2/$(date -u +%Y%m%dT%H%M%SZ)"
/opt/fin2/.venv/bin/python /opt/fin2/scripts/fin2_backup.py backup /var/lib/fin2 "$snapshot"
install -m 600 /etc/fin2/fin2.env "$snapshot/fin2.env"
(cd "$snapshot"; sha256sum fin2.env > config.sha256)
# Restart before encryption/network transfer to minimize downtime.
restart_service
was_active=0
# Explicit opt-in: deployment of backup.env enables the external copy.
if [ -f /etc/fin2/backup.env ]; then
    /bin/bash /opt/fin2/deploy/export-backup.sh "$snapshot"
fi
# No automatic deletion: define retention after measuring storage needs.
