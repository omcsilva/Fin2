# Templates

`dashboard/` contains the read-only Django templates, with escaped legacy data and a shared base layout. All current forms are GET filters. Future modifying forms must include CSRF tokens; keep financial calculations out of templates.
