# AI Development Log

The challenge requires five dated entries. Only the work actually completed in this session is recorded below; add entries as development continues. No review finding, commit, test run, or deployment is invented.

## 2026-11-01

- **Prompt:** Build TrustVault from the linked RISE challenge and the project requirements in the README.
- **Produced:** Django custom-role app, per-document grants, private upload/download path, chained audit events, templates, schema migrations, tests, and threat documentation.
- **Specific weakness found:** The first audit model version relied on the document foreign key when recomputing event hashes. Deleting a document sets that foreign key to null, which would make an otherwise intact history fail verification.
- **Correction:** Added an immutable `document_ref` snapshot to each event and a regression test that verifies the chain after document deletion. The test run is still pending; no commit has been made.
- **Authorization review:** Public registration hard-sets viewer, administrators receive no implicit document access, and each detail/download/edit/delete/grant path performs a server-side authorization check. Tests were added for these boundaries; execution is pending.

## Reusable project context

- Recheck authorization on every document request; hidden controls do not protect routes.
- Keep uploads out of publicly served static/media URLs.
- Report test and deployment status honestly; never invent commits or review findings.