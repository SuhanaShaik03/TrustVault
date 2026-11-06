# TrustVault

TrustVault is a Django document-sharing application with administrator, owner, and viewer roles. It uses explicit per-document grants, approval-gated viewer login, and an audit trail.

## Features

- Administrators can review login requests, inspect user IDs and names, create and delete accounts, and review document activity, including the recorded client IP address.
- New public registrations create viewer accounts and remain unable to log in until an administrator approves their request. A declined login attempt displays an access error and submits a fresh request.
- Owners have separate Documents, Login details, and Approval requests tabs. They can upload PDF, DOC, or DOCX files, assign viewers read or edit access, revoke access, and remove their own documents.
- Viewers with read access can open and download a document. Viewers with edit access can submit a modified PDF, DOC, or DOCX file for owner approval; the original is replaced only when the owner approves, and declined requests are shown to the viewer.
- Owners can review the viewer and other-owner account login IDs and last-login times. Passwords are never displayed. Administrators do not automatically gain access to private documents.
- Document files are stored under `media_private/` and are not served directly by a public media URL. The audit log is hash-linked and read-only in Django admin.

Audit IP addresses are taken from the direct connection's `REMOTE_ADDR` value. When deploying behind a reverse proxy, configure the proxy and application so this value reflects the actual client only when supplied by a trusted proxy; forwarded IP headers are not trusted by the application.

## Run locally (Windows PowerShell)

```powershell
$env:DATABASE_URL = "postgresql://trustvault:YOUR_PASSWORD@localhost:5432/trustvault"
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/. Register a viewer at `/accounts/register/`. Sign in as the superuser to review requests at `/accounts/admin/`. Use the administrator dashboard to create owner/viewer accounts; only a superuser can create additional administrator accounts. The Django administration site is available at `/django-admin/`.

Run checks and tests with:

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py test
```

## Configuration and security

Local development and deployment use PostgreSQL, configured through the `DATABASE_URL` environment variable. Create a PostgreSQL database and user before running the setup commands. Local development uses a development-only secret key. For deployment, set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, and `DJANGO_ALLOWED_HOSTS`, and run behind an HTTPS reverse proxy. Production mode refuses the development secret and enables secure cookies, HTTPS redirect, HSTS, and content-type protections. Do not use Django's development server in production.

Passwords use Django hashing and validation. Uploads are limited to 10 MiB and checked for supported extensions and basic file signatures. Document types are limited to PDF, DOC, and DOCX. Authorization is enforced on the server for every document action; denied access is recorded. Grant revocation blocks subsequent requests but cannot recall a copy already downloaded. The audit chain is tamper-evident, not tamper-proof against an operator able to rewrite the database. Local files are not encrypted at rest; production should use private encrypted storage, malware scanning, external signed audit checkpoints, backups, and retention controls.