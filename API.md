# HTTP API and Authorization

TrustVault currently exposes server-rendered HTML routes rather than a JSON API. All modifying requests require authentication and Django CSRF protection. Document authorization is enforced in the view for each request; UI visibility is not an authorization control.

| Method and path | Allowed caller | Behavior |
|---|---|---|
| `GET/POST /accounts/register/` | Anonymous | Creates a viewer account; submitted role values are ignored. |
| `GET /accounts/users/` | Administrator role or superuser | Lists viewer/owner accounts for role and activation management. |
| `GET/POST /accounts/users/{id}/` | Administrator role or superuser | Promotes viewer to owner or disables an account; administrators cannot create more administrators. |
| `GET/POST /accounts/login/` | Anonymous | Django authentication. |
| `POST /accounts/logout/` | Authenticated | Ends the session. |
| `GET /` | Authenticated | Lists only owned or explicitly granted documents. Filters by name, owner, category, and upload date. |
| `GET/POST /documents/upload/` | Owner role or superuser | Uploads a validated file to private storage. |
| `GET /documents/{id}/` | Owner or current read/edit grantee | Returns metadata and records a view event. |
| `GET /documents/{id}/download/` | Owner or current read/edit grantee | Opens the private file after rechecking authorization and records a download. |
| `GET/POST /documents/{id}/edit/` | Owner or current edit grantee | Changes metadata or replaces the file. |
| `POST /documents/{id}/delete/` | Owner only | Deletes the file and document; retains the audit event. |
| `GET/POST /documents/{id}/share/` | Owner only | Grants or changes read/edit access for a named active user. |
| `POST /documents/{id}/share/{grant_id}/revoke/` | Owner only | Removes a grant; later requests are denied. |
| `GET /audit/` | Administrator role or superuser | Shows recent audit events and the audit-chain verification result. |
| `/admin/` | Django staff/superuser | Account and platform management. Document file access is disabled in Django admin. |

Unauthorized and unknown document IDs return 404. Authenticated denied attempts for existing documents are written to the audit chain. Anonymous attempts are redirected to login and are not currently attributed. The administrator role does not grant document access; a named grant is still required.