#!/bin/bash
# Encrypt a verified, closed snapshot; transfer only ciphertext to the NAS.
set -euo pipefail
umask 077
snapshot=${1:?Snapshot directory required}
name=$(basename "$snapshot")
[[ "$name" =~ ^(pre-update-)?[0-9]{8}T[0-9]{6}Z$ ]] || { echo 'Invalid snapshot name'; exit 1; }
[[ "$(realpath "$snapshot")" = "/var/backups/fin2/$name" ]] || exit 1
source /etc/fin2/backup.env
[[ "${FIN2_BACKUP_RECIPIENT:-}" =~ ^([0-9A-Fa-f]{40}|[0-9A-Fa-f]{64})$ ]] || { echo 'Full public-key fingerprint required'; exit 1; }
app=$(dirname "$(dirname "$(realpath "$0")")")
"$app/.venv/bin/python" "$app/scripts/fin2_backup.py" verify "$snapshot"
test -f "$snapshot/fin2.env"
(cd "$snapshot"; sha256sum -c config.sha256 >/dev/null)
work=$(mktemp -d /var/backups/fin2-export.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
file="fin2-$name.tar.gz.gpg"
# Only the public encryption key is installed on production.
tar -czf - -C /var/backups/fin2 "$name" | gpg --homedir /etc/fin2/gnupg --batch --trust-model always --encrypt --recipient "$FIN2_BACKUP_RECIPIENT" --output "$work/$file"
digest=$(sha256sum "$work/$file" | cut -d ' ' -f 1)
ssh_args=(-o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -i /etc/fin2/backup_ed25519 -o UserKnownHostsFile=/etc/fin2/backup_known_hosts)
host=mcsil@rpi5.lan
destination=/mnt/MERGERFS/Backup/Fin2
partial="$file.$(cat /proc/sys/kernel/random/uuid).partial"
scp "${ssh_args[@]}" "$work/$file" "$host:$destination/$partial"
# Never replace an existing archive; a failed upload remains explicitly partial.
ssh "${ssh_args[@]}" "$host" "set -eu; cd '$destination'; test ! -e '$file'; printf '%s  %s\n' '$digest' '$partial' | sha256sum -c -; ln -- '$partial' '$file'; rm -- '$partial'"
printf '%s  %s\n' "$digest" "$file" > "$snapshot/external-copy.sha256"
echo "External encrypted copy verified: $file"
