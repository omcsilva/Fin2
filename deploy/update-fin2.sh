#!/bin/bash
# Explicit production promotion of a committed revision. Run with sudo.
set -euo pipefail
umask 027
revision=${1:?Usage: update-fin2.sh FULL_COMMIT_HASH}
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo 'Use a full commit hash'; exit 1; }
repository=/home/mcsil/fin2.git
git -c safe.directory="$repository" --git-dir="$repository" cat-file -e "$revision^{commit}"
exec 9>/run/lock/fin2-backup.lock
flock -n 9
release="/opt/fin2-releases/$revision"
test ! -e "$release" || { echo 'Release directory already exists; inspect before retrying'; exit 1; }
mkdir -p "$release"
git -c safe.directory="$repository" --git-dir="$repository" archive "$revision" | tar -x -C "$release"
python3 -m venv "$release/.venv"
"$release/.venv/bin/pip" install -q -r "$release/requirements-production.txt"
set -a
source /etc/fin2/fin2.env
set +a
cd "$release"
.venv/bin/python manage.py check
.venv/bin/python manage.py collectstatic --noinput
chmod 755 /opt/fin2-releases
chmod -R a+rX "$release"
# Keep data and service untouched until the release is prepared.
systemctl stop fin2
snapshot="/var/backups/fin2/pre-update-$(date -u +%Y%m%dT%H%M%SZ)"
/opt/fin2/.venv/bin/python /opt/fin2/scripts/fin2_backup.py backup /var/lib/fin2 "$snapshot"
install -m 600 /etc/fin2/fin2.env "$snapshot/fin2.env"
systemctl cat fin2 > "$snapshot/fin2-service.txt"
# Any failure from here leaves the service stopped for explicit recovery.
runuser -u fin2 -- env FIN2_DATA_DIR=/var/lib/fin2 "$release/.venv/bin/python" -c 'from warehouse.database import connect,migrate; from pathlib import Path; db=connect(Path("/var/lib/fin2/fin2.duckdb")); c=db.__enter__(); migrate(c); db.__exit__(None,None,None)'
install -d /etc/systemd/system/fin2.service.d
cat > /etc/systemd/system/fin2.service.d/release.conf <<EOF
[Service]
WorkingDirectory=$release
ExecStart=
ExecStart=$release/.venv/bin/gunicorn --bind 127.0.0.1:8020 --workers 1 --threads 4 --timeout 120 --graceful-timeout 120 --access-logfile - --error-logfile - config.wsgi:application
EOF
# Nginx keeps its existing static alias; preserve old files for recovery.
cp -a /opt/fin2/staticfiles "$snapshot/staticfiles"
cp -a "$release/staticfiles/." /opt/fin2/staticfiles/
chmod -R a+rX /opt/fin2/staticfiles
systemctl daemon-reload
systemctl start fin2
curl --fail --retry 8 --retry-connrefused --retry-delay 1 http://127.0.0.1:8020/fin2/ -o /dev/null
printf '%s\n' "$revision" > /var/lib/fin2/deployed-revision
echo "Deployed $revision; recovery snapshot: $snapshot"
