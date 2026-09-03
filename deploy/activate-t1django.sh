#!/bin/bash
set -euo pipefail
# Run as root after transferring application, data and the private env file.
printf '\n/fin2/fin2.env\n' >> /etc/.gitignore
install -m 600 /home/mcsil/fin2-deploy/fin2.env /etc/fin2/fin2.env
chown -R fin2:fin2 /var/lib/fin2
chmod 700 /var/lib/fin2
find /opt/fin2/deploy -type f -exec sed -i 's/\r$//' {} +
install -m 644 /opt/fin2/deploy/fin2.service /opt/fin2/deploy/fin2-backup.service /opt/fin2/deploy/fin2-backup.timer /etc/systemd/system/
set -a
source /etc/fin2/fin2.env
set +a
cd /opt/fin2
.venv/bin/python manage.py check
.venv/bin/python manage.py collectstatic --noinput
chmod -R a+rX /opt/fin2/staticfiles
sed -e 's/fin2.example.internal/t1django.lan 10.0.0.17/' -e 's@192.168.1.0/24@10.0.0.0/24@' deploy/nginx-fin2.conf > /etc/nginx/sites-available/fin2
ln -sf /etc/nginx/sites-available/fin2 /etc/nginx/sites-enabled/fin2
if [ -L /etc/nginx/sites-enabled/default ]; then unlink /etc/nginx/sites-enabled/default; fi
nginx -t
systemctl daemon-reload
systemctl enable --now fin2.service
systemctl reload nginx
systemctl enable --now fin2-backup.timer
systemctl is-active fin2 nginx fin2-backup.timer
