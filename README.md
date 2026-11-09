# TrustVault

TrustVault is a Django app for privately sharing documents between administrators, owners, and viewers. Production uses PostgreSQL; local development can use SQLite.

## Features

- Owners upload, open, download, edit, and delete their documents.
- Owners grant or revoke viewer read/edit access. Viewers with edit access can submit replacements for owner approval.
- Viewer and owner accounts need administrator approval to log in. Administrator registration requires a one-time invitation.
- Documents are private. PDF and DOC files up to 10 MiB are accepted; DOCX and other formats are rejected.
- Administrators manage accounts and login approvals and review the audit log.

## Run locally (Windows PowerShell)

SQLite is used when `DJANGO_DEBUG=True` and `DATABASE_URL` is unset. Existing `db.sqlite3` data is preserved. To use PostgreSQL locally, set `DATABASE_URL` to your PostgreSQL connection URL.

```powershell
$env:DJANGO_DEBUG = "True"
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/. The administrator dashboard is `/accounts/admin/`; Django admin is `/django-admin/`.

Run checks and tests:

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py test
.venv\Scripts\python.exe manage.py migrate --check
.venv\Scripts\python.exe manage.py collectstatic --no-input
```

## Deploy on Render

`render.yaml` configures Gunicorn, PostgreSQL, static files, migrations, and a health check. Document contents are stored in PostgreSQL alongside their metadata; no persistent disk, object-storage provider, or other file-storage service is used. Each PDF or DOC upload is limited to 10 MiB. Render sets `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, and `TRUSTED_PROXY_COUNT=1` so audit events record the client address from Render's forwarded-IP header. Set `TRUSTED_PROXY_COUNT` to the number of trusted proxies in front of the app; it defaults to `0`, which ignores forwarded-IP headers. An administrator can run the PostgreSQL file-storage check from the Login details section of the admin dashboard; it verifies database write, read, and delete operations without exposing uploaded content.

Deploy with a Render Blueprint, then verify `/healthz/` returns `{"status":"ok"}`. Create the first administrator from the Render Shell using `python manage.py createsuperuser`. The Blueprint creates a new database; it does not import local database records or files. Back them up and migrate separately if needed. The storage migration copies existing document files from `PRIVATE_MEDIA_ROOT` into PostgreSQL and stops with an error if referenced legacy files are missing. Never reset a production database.

Keep secrets out of Git. Documents are served only after authorization checks. Revoking a grant blocks future requests, but cannot recall downloaded copies. The audit chain is tamper-evident, not tamper-proof. Document contents are stored in PostgreSQL and are subject to the database's capacity, backup, and encryption-at-rest configuration.
