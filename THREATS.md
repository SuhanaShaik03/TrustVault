# TrustVault Threat Register

| Threat | Control | Automated test | Accepted limitation |
|---|---|---|---|
| Guessing an ID to view or download an unshared file | Every detail/download request checks owner or current grant; denied IDs return 404 | `test_unshared_user_cannot_view_or_download_and_attempt_is_audited` | Anonymous attempts are redirected to login and not attributed. |
| Viewer forges edit or delete requests | Edit requires `edit`; deletion and grant management require owner; deletion/revocation are POST-only | `test_read_grant_cannot_edit_or_delete` | No rate limiting or central alerting is configured. |
| Administrator role becomes a document-access bypass | Admin activity access is separate from document checks | `test_administrator_role_does_not_grant_document_access` | A database or host administrator can access files outside the application. |
| A revoked user reuses a URL | Grant is queried on every request; no long-lived signed URLs or permission cache | `test_grant_allows_read_and_revoke_immediately_denies_next_request` | Revocation cannot recall copies already downloaded. |
| Extension spoofing or oversized upload | 10 MiB size cap, PDF/DOC extension allowlist, signature checks, random storage names | Upload validation tests | This is not malware scanning; malware risks need a production scanning pipeline. |
| Audit event altered or deleted in the application | Read-only Django admin, chained SHA-256 values, administrator integrity check | `test_audit_chain_verifies_then_detects_event_tampering`; `test_audit_chain_stays_valid_after_document_deletion` | A database operator can rewrite the whole chain. Independently signed external checkpoints are not implemented. |
| File exposed through a predictable media URL | `MEDIA_ROOT` is not routed by Django; authorized view opens files by opaque generated path | Unauthorized download test above | Production storage and reverse-proxy configuration must remain private. |
| Privileged role submitted during registration | Registration form excludes role and save always sets viewer | `test_public_registration_cannot_select_privileged_role` | Staff with Django admin access can promote roles; protect those credentials. |
| CSRF against permission/deletion forms | Django CSRF middleware, template tokens, POST-only mutation endpoints | Framework protection is enabled; explicit CSRF-enforced client tests remain to be added | Django `TestCase` disables CSRF enforcement by default. |
| Script injection via title, category, or filename | Django template autoescaping; file path is generated independently of the filename | Not yet covered by a dedicated test | No rich-text rendering or document preview is implemented. |

## Operational limits

- PostgreSQL and local filesystem storage are used in development. Production should use PostgreSQL and private encrypted object storage.
- The audit chain is tamper-evident, not tamper-proof. Send signed checkpoints to a separate trust boundary before treating it as compliance evidence.
- Revocation blocks subsequent server requests, not downloaded or copied content.
- HTTPS, backups, retention rules, malware scanning, alerting, and production deployment have not been provisioned in this workspace.

- **Administrator role escalation:** The role-management form allows only viewer/owner roles and excludes superusers. `test_administrator_can_promote_viewer_but_not_create_another_administrator` covers this; superusers can still create administrators and require strong credential protection.