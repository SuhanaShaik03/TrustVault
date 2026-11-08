# TrustVault

TrustVault is a Django application for sharing private documents with administrator, owner, and viewer roles. PostgreSQL is required in production. Set `DJANGO_DEBUG=True` for local development to use the existing `db.sqlite3` file when `DATABASE_URL` is not set; otherwise Django defaults to production mode and requires PostgreSQL.

## Features


- Viewer and owner accounts require administrator approval before login. Administrator registration requires an invitation.
- Owners upload and manage documents, grant approved viewers read or edit access, and review edit requests. A viewer's proposed replacement takes effect only after owner approval.
- Administrators manage accounts and login requests and review document activity.
- PDF and DOC uploads are limited to 10 MiB and stored privately. DOCX and other formats are rejected. Document access is checked for each request.

## Run locally (Windows PowerShell)

For the default local setup, Django uses `db.sqlite3` and preserves any existing data in that file. To use PostgreSQL locally instead, create a database and user, then set the connection URL (replace the placeholders):

```powershell
$env:DJANGO_DEBUG = "True"
# Optional: set this to use PostgreSQL locally instead of SQLite.
# $env:DATABASE_URL = "postgresql://<user>:<password>@localhost:5432/trustvault"
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/. The administrator dashboard is at `/accounts/admin/`; Django admin is at `/django-admin/`.

Run checks and tests:

```powershell
$env:DJANGO_DEBUG = "True"
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py test
```

## Deploy on Render

The root `render.yaml` defines a Django web service, managed PostgreSQL database, private-media disk, static-file collection, database migration step, and database-aware health check. Review the selected Render plans and pricing before creating the Blueprint. The persistent disk requires a paid web service and keeps this single web instance's uploaded files between deploys; use private object storage if you need multiple web instances. If using the free web service without a disk, uploads fall back to writable application storage and can be lost when Render replaces the instance. Render logs a warning when this fallback is used.

Render supplies `DATABASE_URL` from the managed database and generates `DJANGO_SECRET_KEY`. `DJANGO_DEBUG=False` is set in the Blueprint. Keep `DATABASE_URL` and `DJANGO_SECRET_KEY` secret; never commit them. Production fails closed if PostgreSQL or the secret key is missing. Do not set `DJANGO_DEBUG=True` on a deployed service.

To deploy:

1. Push this repository to GitHub.
2. In Render, create a new Blueprint from the repository and review the web, database, and persistent-disk plans and costs.
3. Apply the Blueprint and wait for the build and pre-deploy migration to finish.
4. Verify the service's `/healthz/` endpoint returns `{"status":"ok"}`.
5. Create the initial administrator from the Render Shell with `python manage.py createsuperuser`.

The Blueprint creates a new PostgreSQL database. It does not copy records from local `db.sqlite3` or files from local `media_private`; back up and migrate those separately if they are needed in production. Never point the local SQLite database at Render or reset an existing production database.

Static assets are served by WhiteNoise. User documents remain private and are served only through authorization-checked views; the Render disk is mounted at `/var/data/media_private`.

The audit log is hash-linked and records the direct connection IP; forwarded IP headers are not trusted. The chain is tamper-evident, not tamper-proof. Revoking access blocks future app requests but cannot recall downloaded files, and local document storage is not encrypted at rest.
