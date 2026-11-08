# HTTP Routes and Authorization

TrustVault currently serves HTML pages; it does not expose a JSON API. Django's CSRF middleware protects unsafe requests. The health endpoint performs a database query and returns only a generic status.


| Method and path | Allowed caller | Behavior |
|---|---|---|
| `GET /healthz/` | Public | Returns `200 {"status":"ok"}` when the database responds; otherwise returns `503`. |
| `GET /` | Public | Displays the welcome page. |
| `GET/POST /accounts/register/` | Anonymous | Creates an owner or viewer account pending approval. Administrator registration requires an invitation. |
| `GET/POST /accounts/login/` | Anonymous | Authenticates with Django; unapproved users are not logged in. |
| `POST /accounts/logout/` | Authenticated | Ends the session. |
| `GET /accounts/` | Authenticated | Redirects to the role-appropriate dashboard. |
| `GET /accounts/admin/` | Administrator role or superuser | Shows account, approval-request, or audit activity sections. |
| `GET/POST /accounts/admin/invitations/` | Administrator role or superuser | Creates an administrator invitation on POST. |
| `GET /accounts/admin/users/` | Administrator role or superuser | Lists user accounts. |
| `GET/POST /accounts/admin/users/create/` | Administrator role or superuser | Creates owner/viewer accounts; only superusers can create administrators. |
| `POST /accounts/admin/users/{id}/delete/` | Administrator role or superuser | Deletes an account, revokes its grants, and records audit events. |
| `GET /accounts/admin/requests/{id}/` | Administrator role or superuser | Displays a login access request. |
| `POST /accounts/admin/requests/{id}/review/` | Administrator role or superuser | Approves or declines a login access request. |
| `GET /documents/` | Authenticated | Lists the caller's owned or explicitly granted documents. |
| `GET/POST /documents/upload/` | Owner role | Uploads a validated file to private storage. |
| `GET /documents/{uuid}/` | Owner or current read/edit grantee | Returns document metadata and records a view event. |
| `GET /documents/{uuid}/download/` | Owner or current read/edit grantee | Opens the private file after rechecking authorization and records a download. |
| `GET /documents/{uuid}/open/` | Owner or current read/edit grantee | Opens the private file inline after rechecking authorization. |
| `GET/POST /documents/{uuid}/edit/` | Owner role | Updates metadata or replaces the file. |
| `POST /documents/{uuid}/delete/` | Owner role | Deletes the document and its stored files; retains the audit event. |
| `GET/POST /documents/{uuid}/share/` | Owner role | Grants or changes read/edit access for an approved viewer. |
| `POST /documents/{uuid}/revoke/{grant_id}/` | Owner role | Removes a document grant. |
| `GET/POST /documents/{uuid}/submit-change/` | Current edit grantee | Submits a replacement for owner approval. |
| `GET /owner/viewers/{viewer_id}/` | Owner role | Manages a viewer's document grants. Grant changes use POST. |
| `GET/POST /owner/approval-requests/{request_id}/` | Owner role for the related document | Reviews a pending viewer replacement. |
| `GET /owner/approval-requests/{request_id}/document/` | Owner role for the related document | Previews the pending replacement. |
| `/django-admin/` | Django staff/superuser | Django administration; document file access is disabled there. |

Audit events and chain verification are shown in the activity section of `/accounts/admin/?section=activity`. Unauthorized and unknown document IDs return 404. The administrator role does not grant document access; a named grant is still required. File uploads are limited to PDF, DOC, or DOCX files up to 10 MiB. User files are served only through authorization-checked views and are not exposed as static or public media.
