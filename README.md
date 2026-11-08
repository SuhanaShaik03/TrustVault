# TrustVault

TrustVault is a Django application for sharing private documents with administrator, owner, and viewer roles. PostgreSQL is required.

## Features

- Viewer and owner accounts require administrator approval before login. Administrator registration requires an invitation.
- Owners upload and manage documents, grant approved viewers read or edit access, and review edit requests. A viewer's proposed replacement takes effect only after owner approval.
- Administrators manage accounts and login requests and review document activity.
- PDF, DOC, and DOCX uploads are limited to 10 MiB and stored privately. Document access is checked for each request.

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

Set `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, and `DJANGO_ALLOWED_HOSTS` for deployment. Production mode requires a non-development secret key and enables HTTPS redirect, secure cookies, HSTS, and content-type protection. Use HTTPS and do not deploy Django's development server. Document files use local private storage, which may not persist on serverless hosts such as Vercel.

The audit log is hash-linked and records the direct connection IP; forwarded IP headers are not trusted. The chain is tamper-evident, not tamper-proof. Revoking access blocks future app requests but cannot recall downloaded files, and local document storage is not encrypted at rest.
