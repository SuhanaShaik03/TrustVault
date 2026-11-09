# TrustVault: Prompts, Decisions, and Follow-up

This is a working record of how TrustVault was built with coding assistance. The prompt descriptions below are fair summaries, not word-for-word transcripts. The dates follow the requested project timeline; they are not all independently confirmed by the Git history. Commit links point to changes that can be inspected, but a commit may represent the implementation or later correction rather than the exact date a prompt was sent.

## 1 November 2026 — Define the three roles

- **Prompt, summarized:** Build the application around Admin, Owner, and Viewer roles. Admins should manage accounts and access requests; Owners should manage documents and sharing; Viewers should access documents assigned to them.
- **What it produced:** The initial project structure and the first pass at role-aware account and document workflows.
- **What needed scrutiny:** A role-based interface is not an authorization boundary by itself. A hidden button or dashboard tab does not stop someone from requesting a protected URL directly.
- **What I checked or changed:** Reviewed the server-side account and document views and the tests for non-admin dashboard access and document access by unshared users. The project tests the authorization decisions at the request level rather than relying only on what the interface displays. See the [initial project commit](https://github.com/SuhanaShaik03/TrustVault/commit/36e519a), [administrator workflow commit](https://github.com/SuhanaShaik03/TrustVault/commit/634ae2e), and [security-controls commit](https://github.com/SuhanaShaik03/TrustVault/commit/081c82f).

## 2 November 2026 — Admin dashboard and account approval

- **Prompt, summarized:** Give Admins separate Login Details, Access Requests, and Audit Logs sections. Let them manage accounts, create users, and approve or decline Owner and Viewer access requests.
- **What it produced:** Account-management and approval workflows, with role-specific administrator pages and tests.
- **What needed a security decision:** The first requirements did not specify how a new Admin should be authorized. Allowing anyone to select Admin during public registration would create a privilege-escalation path.
- **What I did instead:** Restricted public Admin registration to a valid, one-time invitation. Owner and Viewer registration continues through the approval workflow; an Admin invitation does not create an approval request for another Admin to process. Reviewed the invitation and administrator controls in the [administrator workflow commit](https://github.com/SuhanaShaik03/TrustVault/commit/634ae2e) and [security-controls commit](https://github.com/SuhanaShaik03/TrustVault/commit/081c82f). The invitation requirement is covered by `test_admin_registration_requires_an_invitation_and_creates_no_access_request`.

## 5 November 2026 — Owner and Viewer document workflows

- **Prompt, summarized:** Let Owners upload and manage documents, grant Viewers read or edit access, and review replacement files submitted by Viewers. Show Viewers their assigned documents and the status of their submissions.
- **What it produced:** Document grants, private document views, the change-request workflow, and corresponding tests.
- **What needed careful interpretation:** “Edit access” must not let a Viewer silently overwrite the Owner's original. The intended behavior is to submit a proposed replacement for Owner approval.
- **What I checked or changed:** Checked that authorization is enforced in the document views, that a read grant cannot edit, that an edit grant cannot directly modify the original, and that declining a submission leaves the original unchanged. See the [Owner and Viewer access commit](https://github.com/SuhanaShaik03/TrustVault/commit/2545bb0) and the later [Viewer access correction and upload-guidance commit](https://github.com/SuhanaShaik03/TrustVault/commit/e7b016a). These boundaries are exercised by `test_read_grant_allows_download_but_not_edit`, `test_edit_grant_cannot_change_original_document_directly`, and the change-approval tests.

## 6 November 2026 — Database and deployment configuration

- **Prompt, summarized from the deployment work:** Prepare the application for hosted use, including PostgreSQL configuration and the correct allowed hosts for the deployment.
- **What it produced:** PostgreSQL configuration and deployment-host settings.
- **What was wrong:** The initial host configuration did not cover all deployment preview hosts, so valid hosted requests could be rejected. The repeated host-configuration updates in the commit history show that the deployment hostname handling needed follow-up.
- **What I did instead:** Updated the allowed-host configuration for preview hosts and continued validating the deployment setup. See the [PostgreSQL migration commit](https://github.com/SuhanaShaik03/TrustVault/commit/4829c8a) and [preview-host correction](https://github.com/SuhanaShaik03/TrustVault/commit/7f82970).

## 7 November 2026 — No prompt or fix independently confirmed

- **Prompt:** I could not verify a distinct prompt for this date from the available prompt images or repository history.
- **What it produced:** No separate implementation is attributed to 7 November in this log.
- **What was wrong:** The evidence available here is incomplete; assigning the following day's work to this date would make the record misleading.
- **What I did instead:** Left this entry explicit rather than inventing a prompt, defect, or commit. The next verified implementation changes are dated 8 November.

## 8 November 2026 — Deployment uploads and Viewer access corrections

- **Prompt, summarized from the fixes:** Resolve document-upload problems in the hosted environment, correct the supported-file guidance, and address a Viewer document-access problem.
- **What it produced:** Deployment upload fixes, updated file-format handling and guidance, and additional Viewer-access tests.
- **What was wrong:** Hosted uploads were not working reliably, and the Viewer access and upload guidance needed correction. The commit subjects and their changed tests/files document these issues.
- **What I did instead:** Fixed the upload and Viewer access behavior and added or updated regression coverage. See [Fix document uploads on Render](https://github.com/SuhanaShaik03/TrustVault/commit/965144a), [Fix Vercel document uploads](https://github.com/SuhanaShaik03/TrustVault/commit/843bfe0), and [Fix viewer document access and upload guidance](https://github.com/SuhanaShaik03/TrustVault/commit/e7b016a).

## Follow-up work — 9 November 2026

- **Prompt:** “Check the IP address; it has been messed up and is not working properly. Modify and fix the error.”
- **What it produced:** Tracing the audit-event code showed it used `REMOTE_ADDR` alone. Behind a hosting proxy, this can record the proxy address rather than the visitor's address.
- **What I changed and verified:** Added configurable trusted-proxy handling, configured Render for one trusted proxy, documented the setting, and added tests for forwarded addresses and ignored untrusted headers. The focused audit tests and the full 47-test suite passed. These edits are in the current worktree and do not yet have a commit link: [IP capture implementation](./documents/services.py), [proxy setting](./trustvault/settings.py), [IP tests](./documents/tests.py), and [Render configuration](./render.yaml).
- **Documentation prompts:** I also asked for a human-friendly overview of the roles and workflows, then asked for `THREATS.md` to distinguish manual checks, automated security tests, and future security work. Those documents now exist as [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) and [THREATS.md](./THREATS.md). These are working-tree documentation changes, not committed changes.

## Reusable project context

- **`README.md`** — project purpose, local setup, and deployment notes.
- **`API.md`** — route behavior and caller authorization expectations.
- **`THREATS.md`** — documented manual checks, test coverage, and remaining risks.
- **`accounts/tests.py` and `documents/tests.py`** — existing behavior and regression tests to consult before changing access rules.
- **User-provided prompt screenshots and feature descriptions** — the original role, dashboard, registration, and document-workflow requirements.

I have not found a separate reusable AI instruction or prompt-template file in the repository. This log does not claim that manual checks are automated, that the audit log is tamper-proof, or that uncommitted changes have a commit link.
