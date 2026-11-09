# TrustVault Project Overview

TrustVault is a web application for storing and sharing documents with controlled access. It has three user roles: Administrator, Owner, and Viewer. Each role has different responsibilities and permissions.

## User roles

### Administrator

Administrators manage accounts and access approvals.

- View and manage user accounts, including creating accounts and deleting accounts when appropriate.
- Invite another administrator with a unique, one-time registration link.
- Review access requests from people registering as Owners or Viewers, then approve or decline them.
- Review the audit log, which displays recorded account and document activity with timestamps and IP addresses when available.

### Owner

Owners manage their documents and decide who can access them.

- Upload, view, edit, and delete their documents.
- Browse the Viewer list and see other Owners' login names.
- Give a Viewer read-only or edit access to a document, or revoke access.
- Review document changes submitted by Viewers with edit access. An approved change replaces the current document; a declined change does not.

### Viewer

Viewers can access documents that have been shared with them.

- Browse documents assigned to them.
- Download documents when they have read-only access.
- Submit a changed version for Owner review when they have edit access.
- Check the status of submitted changes, including whether they were approved or declined.

## Typical workflows

### Account approval

1. A person registers as an Owner or Viewer.
2. TrustVault creates an access request for an Administrator to review.
3. The Administrator approves or declines the request.
4. An Administrator can also create accounts directly. New administrator accounts can be registered using a unique invitation link.

### Sharing a document

1. An Owner uploads a document.
2. The Owner grants a Viewer read-only or edit access.
3. The Viewer can use the document according to the permission granted. The Owner can revoke access later.

### Submitting a document change

1. A Viewer with edit access submits a modified version.
2. The Owner reviews the submission in the approval requests section.
3. If approved, the submitted version replaces the current document. If declined, the current document remains unchanged.

## Security checks performed

The following checks have been performed during development:

- Authentication and password validation were checked.
- SQL injection was checked at the login page.
- Unauthenticated users and users without access were checked for unauthorized page and document access, including path traversal attempts.
- Role boundaries were checked to ensure Owners and Viewers cannot access administrator-only areas.
- Checks were made to ensure one user cannot access another user's data.
- File upload validation was checked; unsupported file types are rejected.

These checks describe testing performed; they should not be taken as a guarantee that the application is free of vulnerabilities. The audit log shows events recorded by the application, with timestamps and IP addresses when available. It is not a substitute for a complete intrusion-detection or security-monitoring system.

## Current limitations and future work

- Search is not currently available and is planned as a future enhancement.
- The codebase includes unit tests, but a dedicated end-to-end automation suite has not been implemented.
- Email notifications are planned for document uploads and sharing.
- Official security email notifications for rejected or failed login attempts are also planned.

## Document and file restrictions

The current application accepts PDF and DOC files up to 10 MiB. DOCX and other unsupported formats are rejected. Documents are private and are served only after authorization checks.
