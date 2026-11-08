# TrustVault

TrustVault is a Django application for sharing private documents with administrator, owner, and viewer roles. PostgreSQL is required.

## Features

- Viewer and owner accounts require administrator approval before login. Administrator registration requires an invitation.
- Owners upload and manage documents, grant approved viewers read or edit access, and review edit requests. A viewer's proposed replacement takes effect only after owner approval.
- Administrators manage accounts and login requests and review the activity log. Login request statuses include pending, approved, and declined.
- Only PDF, DOC, and DOCX files are accepted; uploads are limited to 10 MiB and checked for file signatures. Documents are stored privately and access is checked for each request.

## Run locally (Windows PowerShell)

Create a PostgreSQL database and user, then set the connection URL (replace the placeholders):

```powershell
$env:DATABASE_URL = "postgresql://<user>:<password>@localhost:5432/trustvault"
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/. The administrator dashboard is at `/accounts/admin/`; Django admin is at `/django-admin/`.

Run checks and tests:

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py test
```

## Deployment notes

Set `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, and `DJANGO_ALLOWED_HOSTS` for deployment. Vercel also requires a private S3-compatible bucket and the `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY` environment variables. Optionally set `AWS_S3_REGION_NAME` and `AWS_S3_ENDPOINT_URL` for your storage provider. Production mode requires a non-development secret key and enables HTTPS redirect, secure cookies, HSTS, and content-type protection. Use HTTPS; do not deploy Django's development server.

The audit log is hash-linked and records the direct connection IP; forwarded IP headers are not trusted. The chain is tamper-evident, not tamper-proof. Revoking access blocks future app requests but cannot recall downloaded files, and local document storage is not encrypted at rest.
