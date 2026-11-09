# TrustVault Security Checks and Threats

This document summarizes the security checks performed for TrustVault, the related automated tests in the codebase, and areas that need further security work. Manual checks are development-time observations; they are not a guarantee that the application is free of vulnerabilities.

## 1. Manual checks performed

The following checks were performed manually:

1. **Authentication and password handling:** Checked username and password validation during sign-in.
2. **SQL injection at login:** Tried SQL injection input in the login flow; the attempted input did not bypass authentication.
3. **Path traversal and unauthorized access:** Checked that unauthenticated users and users without permission cannot access protected pages or documents through path traversal attempts.
4. **Role boundary and privilege escalation:** Checked that Owners and Viewers cannot access administrator accounts or administrator-only functionality.
5. **User data isolation:** Checked that one user cannot access another user's data.
6. **File upload validation:** Checked that unsupported file types are rejected with an error.

## 2. Security tests added in the codebase

Automated tests in `accounts/tests.py` and `documents/tests.py` cover the following security-related behavior:

- **Authentication and account approval:** Tests check that unapproved accounts cannot establish an authenticated session, approved accounts can log in, and approval requests are created or handled as expected.
- **Administrator registration:** `test_admin_registration_requires_an_invitation_and_creates_no_access_request` checks that administrator registration requires a valid invitation.
- **Administrator-only access:** `test_non_admin_cannot_open_admin_dashboard` checks that a non-administrator cannot open the administrator dashboard.
- **Document access controls:** Tests check that unshared users and other Owners cannot access a document by guessing its ID, that a Viewer’s read grant does not permit editing, and that an administrator role does not by itself grant access to a document.
- **Grant revocation and change approval:** Tests check that revoking a grant blocks subsequent access, and that a Viewer-submitted change does not replace the original document unless the Owner approves it.
- **Upload validation:** Tests check unsupported file types, the 10 MiB size limit, mismatched PDF signatures, and that a rejected DOCX upload is not saved. The validator accepts PDF and DOC files with the expected signatures.
- **CSRF protection:** Tests check that logout requires POST with a valid CSRF token and that document deletion rejects requests without valid CSRF protection.
- **Audit integrity and IP capture:** Tests check that audit-chain tampering is detected, that event IP addresses are included in the hash, and that configured trusted-proxy settings select the forwarded client IP without trusting that header when no proxy is configured.
- **Private storage behavior:** A test checks that Render storage fails explicitly when the configured persistent media directory is not writable instead of silently falling back to ephemeral storage.

These tests verify specific application behavior; they do not replace manual penetration testing, deployment review, or a dedicated security automation suite.

## 3. Future enhancements / areas needing more focus

1. **Broader security test coverage:** Add a dedicated automated security suite for path traversal, cross-user access across all relevant endpoints, role escalation, injection handling, and security-sensitive regression cases. Include browser-level or end-to-end coverage where appropriate.
2. **Abuse detection and alerting:** Consider rate limiting and monitoring for repeated failed logins, suspicious access attempts, and other unusual activity. Email notifications for failed or rejected logins and document sharing or uploads are not currently implemented.
3. **File threat protection:** Current validation checks file extension, size, and selected file signatures; it is not malware scanning. Add a scanning pipeline and review handling of potentially unsafe document content before production use.
4. **Production audit and data protection:** The audit chain is tamper-evident, not tamper-proof; an operator with database access could alter it. Consider sending signed audit checkpoints to a separate trust boundary. Review encryption at rest, backups, retention, HTTPS, and private storage/reverse-proxy configuration as part of deployment operations.

## Current threat limitations

- Revoking access blocks future authorized requests but cannot recall copies already downloaded.
- The application does not currently provide document search.
- There is no dedicated end-to-end security automation suite.
- The application's audit log is not a substitute for centralized security monitoring or intrusion detection.
