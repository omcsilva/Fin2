# Deployment and security plan

This is a deployment design, not a ready-to-run installation guide. Service files, environment variable names, proxy configuration, and application entry points are not implemented yet.

## Target

Unprivileged Proxmox LXC on the 8 GB ThinkPad X230. Start with two vCPUs, 2 GB RAM, 1 GB swap, and 12–16 GB root storage, then measure actual usage and document storage retention. Select and verify the Linux release at deployment time.

Use one Gunicorn worker, initially four threads, under systemd and an unprivileged application account. Avoid concurrent worker replacement while the database is open. No Celery, Redis, or independent database service is planned.

## Persistent paths

```text
/opt/fin2/                       Application and virtual environment
/etc/fin2/fin2.env               Configuration and credentials
/var/lib/fin2/database/          fin2.duckdb
/var/lib/fin2/imports/pending/   Awaiting validation
/var/lib/fin2/imports/accepted/  Accepted sources
/var/lib/fin2/imports/rejected/  Rejected sources
/var/lib/fin2/source-documents/  Original documents
/var/lib/fin2/exports/           Generated reports
/var/lib/fin2/backups/           Local backup staging
/var/lib/fin2/tmp/               DuckDB spill and temporary files
/var/log/fin2/                  Logs, if not using journald alone
```

Restrict credentials and financial files to the service account and authorized administrators. Local backup staging is not an off-device backup.

## Network boundary

- The app has no login: every reachable client can access its features and financial data.
- Enforce LAN/VPN restrictions with firewall rules and/or a reverse-proxy allowlist. Private DNS alone is not access control.
- Bind Gunicorn to loopback when the proxy runs inside the LXC. If the proxy is remote, bind only as needed and restrict ingress to that proxy.
- Configure explicit allowed hosts, trusted origins, production secret, disabled debug, and HTTPS behavior when implementing Django settings.
- Retain CSRF middleware and tokens for mutations. Do not mutate state through GET requests.
- Do not expose the development server, database, or backup directories over HTTP, or serve source-document storage as a public/static directory.
- Document viewing/download must go through controlled application routes inside the same trusted-network boundary; do not publish the storage directory. Resolve managed document IDs, prevent path traversal, validate media types, and isolate previews of untrusted files. Do not render uploaded HTML or other active content in the application origin.

## URL prefix

Plan for `/fin2/` alongside Fin1. Decide whether the proxy strips the prefix and configure Django accordingly. Test redirects, URL reversing, static assets, forms, and HTMX requests under that prefix; do not combine conflicting prefix strategies.

## Maintenance and recovery

Stop the web service before separate migration, database update, or backup processes open DuckDB. A process-local write lock cannot protect a second process. The future scheduling design must preserve this constraint.

Back up the closed database, original sources, and protected configuration; keep an encrypted off-device copy. Test restoration separately and reconcile restored totals. Set retention and recovery targets before production use. Log operational identifiers and errors without dumping financial rows or secrets.
