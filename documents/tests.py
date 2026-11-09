import tempfile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import InMemoryStorage
from datetime import datetime, timezone
from pathlib import Path
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from unittest.mock import patch
from accounts.models import User
from documents.models import AuditEvent, Document, DocumentChangeRequest, DocumentGrant
from documents.storage import PrivateDocumentStorage
from documents.services import record_event, verify_audit_chain
from documents.validators import validate_document_file


class PrivateDocumentStorageTests(TestCase):
    def test_render_storage_saves_and_reopens_a_file_on_the_mounted_disk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            media_root = Path(temp_dir) / "media_private"
            with (
                patch("documents.storage.settings.IS_RENDER", True),
                patch("documents.storage.settings.PRIVATE_MEDIA_ROOT", media_root),
            ):
                storage = PrivateDocumentStorage()
                saved_name = storage.save(
                    "documents/report.pdf",
                    SimpleUploadedFile("report.pdf", b"%PDF-1.7 report"),
                )

                with storage.open(saved_name, "rb") as saved_file:
                    self.assertEqual(saved_file.read(), b"%PDF-1.7 report")

                storage.delete(saved_name)

    def test_render_storage_defers_disk_check_until_a_file_is_saved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            invalid_root = base_dir / "not-a-directory"
            invalid_root.write_text("blocker", encoding="utf-8")

            with (
                patch("documents.storage.settings.IS_RENDER", True),
                patch("documents.storage.settings.PRIVATE_MEDIA_ROOT", invalid_root / "media"),
            ):
                storage = PrivateDocumentStorage()
                self.assertEqual(Path(storage.location), invalid_root / "media")

                with self.assertRaisesRegex(RuntimeError, "persistent disk"):
                    storage.save("document.pdf", SimpleUploadedFile("document.pdf", b"%PDF-1.7"))

            self.assertFalse((base_dir / "media_private").exists())


class DocumentPermissionTests(TestCase):
    def setUp(self):
        self.file_field = Document._meta.get_field("file")
        self.original_storage = self.file_field.storage
        self.change_file_field = DocumentChangeRequest._meta.get_field("submitted_file")
        self.original_change_storage = self.change_file_field.storage
        self.storage = InMemoryStorage()
        self.file_field.storage = self.storage
        self.change_file_field.storage = self.storage
        self.owner = User.objects.create_user(
            username="owner",
            password="SecurePass123!test",
            role=User.Role.OWNER,
            is_approved=True,
        )
        self.viewer = User.objects.create_user(
            username="viewer",
            password="SecurePass123!test",
            role=User.Role.VIEWER,
            is_approved=True,
        )
        self.document = Document.objects.create(
            owner=self.owner,
            title="Quarterly report",
            description="Internal",
            file=SimpleUploadedFile("report.pdf", b"%PDF-1.4 confidential text", content_type="application/pdf"),
        )

    def tearDown(self):
        for document in Document.objects.all():
            document.file.delete(save=False)
        for change_request in DocumentChangeRequest.objects.all():
            change_request.submitted_file.delete(save=False)
        self.file_field.storage = self.original_storage
        self.change_file_field.storage = self.original_change_storage

    def test_unshared_user_cannot_open_document(self):
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse("documents:document_detail", args=[self.document.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_read_grant_allows_download_but_not_edit(self):
        DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            permission=DocumentGrant.Permission.READ,
        )
        self.client.force_login(self.viewer)

        download = self.client.get(
            reverse("documents:document_download", args=[self.document.pk])
        )
        opened = self.client.get(
            reverse("documents:document_open", args=[self.document.pk])
        )
        edit = self.client.get(reverse("documents:document_edit", args=[self.document.pk]))
        submit_change = self.client.get(
            reverse("documents:document_change_submit", args=[self.document.pk])
        )

        self.assertEqual(download.status_code, 200)
        download.close()
        self.assertEqual(opened.status_code, 200)
        self.assertTrue(opened["Content-Disposition"].startswith("inline"))
        opened.close()
        self.assertEqual(edit.status_code, 404)
        self.assertEqual(submit_change.status_code, 404)

    def test_viewer_open_missing_document_file_returns_not_found_not_server_error(self):
        DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            permission=DocumentGrant.Permission.READ,
        )
        self.storage.delete(self.document.file.name)
        self.client.force_login(self.viewer)

        with self.assertLogs("documents.views", level="ERROR"):
            response = self.client.get(
                reverse("documents:document_open", args=[self.document.pk])
            )

        self.assertEqual(response.status_code, 404)
        self.assertContains(
            response,
            "contact the document owner",
            status_code=404,
        )
        self.assertFalse(AuditEvent.objects.filter(action="document_opened").exists())

    def test_owner_open_missing_file_shows_replace_action(self):
        self.storage.delete(self.document.file.name)
        self.client.force_login(self.owner)

        with self.assertLogs("documents.views", level="ERROR"):
            response = self.client.get(
                reverse("documents:document_open", args=[self.document.pk])
            )

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Document file unavailable", status_code=404)
        self.assertContains(response, "Replace document file", status_code=404)


    def test_owner_preview_missing_submitted_file_returns_not_found_not_server_error(self):
        change_request = DocumentChangeRequest.objects.create(
            document=self.document,
            viewer=self.viewer,
            submitted_file=SimpleUploadedFile("revision.pdf", b"%PDF-1.7 revision"),
            uploaded_filename="revision.pdf",
        )
        self.storage.delete(change_request.submitted_file.name)
        self.client.force_login(self.owner)

        with self.assertLogs("documents.views", level="ERROR"):
            response = self.client.get(
                reverse("documents:document_change_preview", args=[change_request.pk])
            )

        self.assertEqual(response.status_code, 404)

    def test_edit_grant_cannot_change_original_document_directly(self):
        DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            permission=DocumentGrant.Permission.EDIT,
        )
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse("documents:document_edit", args=[self.document.pk]),
            {"title": "Updated report", "description": "Revised"},
        )

        self.assertEqual(response.status_code, 404)
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, "Quarterly report")
        self.assertFalse(AuditEvent.objects.filter(action="document_modified").exists())

    def test_owner_can_replace_document_file_and_old_copy_is_removed(self):
        old_name = self.document.file.name
        storage = self.document.file.storage
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("documents:document_edit", args=[self.document.pk]),
            {
                "title": self.document.title,
                "description": self.document.description,
                "file": SimpleUploadedFile(
                    "replacement.doc",
                    b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1updated document",
                ),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.document.refresh_from_db()
        self.assertNotEqual(self.document.file.name, old_name)
        self.assertFalse(storage.exists(old_name))
        event = AuditEvent.objects.get(action="document_modified")
        self.assertTrue(event.details["file_replaced"])

    def test_owner_can_share_and_revoke_access(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("documents:document_share", args=[self.document.pk]),
            {"user": self.viewer.pk, "permission": DocumentGrant.Permission.READ},
        )
        self.assertRedirects(
            response,
            reverse("documents:document_detail", args=[self.document.pk]),
        )
        grant = DocumentGrant.objects.get(document=self.document, user=self.viewer)
        response = self.client.post(
            reverse(
                "documents:document_revoke",
                args=[self.document.pk, grant.pk],
            )
        )
        self.assertRedirects(
            response,
            reverse("documents:document_detail", args=[self.document.pk]),
        )
        self.assertFalse(DocumentGrant.objects.filter(pk=grant.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(action="document_access_revoked").exists())

    def test_revoking_a_grant_immediately_denies_document_access(self):
        grant = DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            permission=DocumentGrant.Permission.READ,
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(
                "documents:document_revoke",
                args=[self.document.pk, grant.pk],
            )
        )
        self.assertRedirects(
            response,
            reverse("documents:document_detail", args=[self.document.pk]),
        )

        self.client.force_login(self.viewer)
        for route_name in (
            "document_detail",
            "document_open",
            "document_download",
        ):
            with self.subTest(route=route_name):
                response = self.client.get(
                    reverse(f"documents:{route_name}", args=[self.document.pk])
                )
                self.assertEqual(response.status_code, 404)

    def test_owner_can_open_download_and_delete_document(self):
        file_name = self.document.file.name
        self.client.force_login(self.owner)

        opened = self.client.get(
            reverse("documents:document_open", args=[self.document.pk])
        )
        self.assertEqual(opened.status_code, 200)
        self.assertEqual(b"".join(opened.streaming_content), b"%PDF-1.4 confidential text")

        downloaded = self.client.get(
            reverse("documents:document_download", args=[self.document.pk])
        )
        self.assertEqual(downloaded.status_code, 200)
        self.assertTrue(downloaded["Content-Disposition"].startswith("attachment"))
        self.assertEqual(
            b"".join(downloaded.streaming_content),
            b"%PDF-1.4 confidential text",
        )

        response = self.client.post(
            reverse("documents:document_delete", args=[self.document.pk])
        )
        self.assertRedirects(response, reverse("documents:document_list"))
        self.assertFalse(Document.objects.filter(pk=self.document.pk).exists())
        self.assertFalse(self.storage.exists(file_name))
        self.assertTrue(
            AuditEvent.objects.filter(
                action="document_deleted",
                target_label="Quarterly report",
            ).exists()
        )
        self.assertTrue(verify_audit_chain())

    def test_owner_cannot_access_another_owners_document_by_id(self):
        other_owner = User.objects.create_user(
            username="other-owner",
            password="SecurePass123!test",
            role=User.Role.OWNER,
            is_approved=True,
        )
        other_document = Document.objects.create(
            owner=other_owner,
            title="Private report",
            file=SimpleUploadedFile("private.pdf", b"%PDF-1.4 private"),
        )
        self.client.force_login(self.owner)

        for route_name in (
            "document_detail",
            "document_open",
            "document_download",
            "document_edit",
            "document_share",
            "document_delete",
        ):
            with self.subTest(route=route_name):
                method = (
                    self.client.post
                    if route_name == "document_delete"
                    else self.client.get
                )
                response = method(
                    reverse(f"documents:{route_name}", args=[other_document.pk])
                )
                self.assertEqual(response.status_code, 404)

        self.assertTrue(Document.objects.filter(pk=other_document.pk).exists())

    def test_administrator_role_does_not_grant_document_access(self):
        administrator = User.objects.create_user(
            username="administrator",
            password="SecurePass123!test",
            role=User.Role.ADMIN,
            is_approved=True,
        )
        self.client.force_login(administrator)

        for route_name in ("document_detail", "document_open", "document_download"):
            with self.subTest(route=route_name):
                response = self.client.get(
                    reverse(f"documents:{route_name}", args=[self.document.pk])
                )
                self.assertEqual(response.status_code, 404)

    def test_document_delete_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)

        response = client.post(
            reverse("documents:document_delete", args=[self.document.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Document.objects.filter(pk=self.document.pk).exists())

    def test_upload_validator_rejects_mismatched_pdf_signature(self):
        upload = SimpleUploadedFile("fake.pdf", b"not a pdf")
        with self.assertRaisesMessage(Exception, "valid PDF signature"):
            validate_document_file(upload)

    def test_upload_validator_rejects_files_over_ten_mib(self):
        upload = SimpleUploadedFile(
            "large.pdf",
            b"%PDF-1.7" + b"x" * (10 * 1024 * 1024),
        )

        with self.assertRaisesMessage(Exception, "10 MiB or smaller"):
            validate_document_file(upload)

    def test_upload_validator_accepts_only_supported_document_types(self):
        validate_document_file(SimpleUploadedFile("report.pdf", b"%PDF-1.7 content"))
        validate_document_file(
            SimpleUploadedFile("report.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1content")
        )
        with self.assertRaisesMessage(Exception, "Unsupported file type. Upload a PDF or DOC document only."):
            validate_document_file(SimpleUploadedFile("report.docx", b"PK\x03\x04content"))
        with self.assertRaisesMessage(Exception, "Unsupported file type. Upload a PDF or DOC document only."):
            validate_document_file(SimpleUploadedFile("report.txt", b"plain text"))

    def test_docx_upload_shows_form_error_and_does_not_save_document(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("documents:document_upload"),
            {
                "title": "Unsupported DOCX",
                "description": "",
                "file": SimpleUploadedFile("report.docx", b"PK\x03\x04content"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Unsupported file type. Upload a PDF or DOC document only.",
        )
        self.assertFalse(Document.objects.filter(title="Unsupported DOCX").exists())

    def test_owner_can_upload_document_and_return_to_document_list(self):
        self.client.force_login(self.owner)
        upload_url = reverse("documents:document_upload")
        document_list_url = reverse("documents:document_list")

        response = self.client.get(upload_url)
        self.assertContains(response, "Back to documents")
        self.assertContains(response, document_list_url)
        self.assertContains(
            response,
            "Supported formats: PDF and DOC only. Maximum upload size: 10 MiB.",
        )

        response = self.client.post(
            upload_url,
            {
                "title": "New report",
                "description": "For review",
                "file": SimpleUploadedFile("new-report.pdf", b"%PDF-1.7 test"),
            },
        )

        self.assertEqual(response.status_code, 302)
        document = Document.objects.get(owner=self.owner, title="New report")
        self.assertEqual(
            response["Location"],
            reverse("documents:document_detail", args=[document.pk]),
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action="document_uploaded",
                document=document,
            ).exists()
        )

    def test_owner_upload_reports_storage_failure_without_creating_document(self):
        self.client.force_login(self.owner)
        with (
            patch.object(
                Document,
                "save",
                side_effect=RuntimeError("Private media storage is unavailable."),
            ),
            self.assertLogs("documents.views", level="ERROR"),
        ):
            response = self.client.post(
                reverse("documents:document_upload"),
                {
                    "title": "Storage failure report",
                    "description": "",
                    "file": SimpleUploadedFile("report.pdf", b"%PDF-1.7 report"),
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertContains(
            response,
            "The document could not be saved.",
            status_code=503,
        )

    def test_owner_dashboard_has_required_tabs_and_login_details(self):
        other_owner = User.objects.create_user(
            username="other-owner",
            password="SecurePass123!test",
            role=User.Role.OWNER,
            is_approved=True,
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("documents:document_list"))
        self.assertContains(response, "Documents")
        self.assertContains(response, "Login details")
        self.assertContains(response, "Approval requests")

        response = self.client.get(
            reverse("documents:document_list"),
            {"section": "login-details"},
        )
        self.assertContains(response, self.viewer.username)
        self.assertContains(response, "Viewers list")
        self.assertContains(response, "Owner list")
        self.assertNotContains(response, other_owner.username)
        self.assertContains(response, "Manage access")

        response = self.client.get(
            reverse("documents:document_list"),
            {"section": "login-details", "list": "owners"},
        )
        self.assertContains(response, other_owner.username)
        self.assertNotContains(response, f"<td>{self.viewer.username}</td>")

    def test_owner_document_table_shows_upload_timestamp_in_ist_and_actions(self):
        Document.objects.filter(pk=self.document.pk).update(
            created_at=datetime(2025, 12, 31, 18, 30, tzinfo=timezone.utc)
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("documents:document_list"))

        self.assertContains(response, "Document name")
        self.assertContains(response, "Date uploaded (IST)")
        self.assertContains(response, "Time uploaded (IST)")
        self.assertContains(response, "01 Jan 2026")
        self.assertContains(response, "12:00 AM")
        self.assertContains(response, "Open")
        self.assertContains(response, "Edit details")
        self.assertContains(response, "Delete")
        self.assertNotContains(response, "Maximum upload size:")

    def test_viewer_has_assigned_and_uploaded_document_tabs(self):
        read_document = Document.objects.create(
            owner=self.owner,
            title="Read-only file",
            file=SimpleUploadedFile("read.pdf", b"%PDF-1.4 read"),
        )
        read_grant = DocumentGrant.objects.create(
            document=read_document,
            user=self.viewer,
            permission=DocumentGrant.Permission.READ,
        )
        edit_grant = DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            permission=DocumentGrant.Permission.EDIT,
        )
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse("documents:document_change_submit", args=[edit_grant.document_id])
        )
        self.assertContains(response, "Submitted file")
        self.assertContains(
            response,
            "Supported formats: PDF and DOC only. Maximum upload size: 10 MiB.",
        )
        field_heading = response.content.index(b">Submitted file</label>")
        upload_guidance = response.content.index(
            b"Supported formats: PDF and DOC only. Maximum upload size: 10 MiB."
        )
        file_input = response.content.index(b'type="file"')
        self.assertLess(field_heading, upload_guidance)
        self.assertLess(upload_guidance, file_input)

        DocumentChangeRequest.objects.create(
            document=self.document,
            viewer=self.viewer,
            submitted_file=SimpleUploadedFile(
                "revision.doc",
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1revision",
            ),
            uploaded_filename="revision.doc",
            status=DocumentChangeRequest.Status.PENDING,
        )
        DocumentChangeRequest.objects.create(
            document=read_document,
            viewer=self.viewer,
            submitted_file=SimpleUploadedFile("accepted.pdf", b"%PDF-1.4 accepted"),
            uploaded_filename="accepted.pdf",
            status=DocumentChangeRequest.Status.APPROVED,
        )
        response = self.client.get(reverse("documents:document_list"))
        self.assertContains(response, "Assigned documents")
        self.assertContains(response, "Uploaded documents")
        self.assertContains(response, self.owner.username)
        self.assertContains(
            response,
            reverse("documents:document_change_submit", args=[edit_grant.document_id]),
            count=1,
        )

        self.assertNotContains(
            response,
            reverse("documents:document_change_submit", args=[read_grant.document_id]),
        )
        self.assertContains(
            response,
            reverse("documents:document_open", args=[edit_grant.document_id]),
        )

        response = self.client.get(reverse("documents:document_list"), {"tab": "uploaded"})
        self.assertContains(response, "revision.doc")
        self.assertContains(response, "Pending approval")
        self.assertContains(response, "accepted.pdf")
        self.assertContains(response, "Approved")
        self.assertContains(response, "Date uploaded")
        self.assertContains(response, "Time uploaded")
        self.assertNotContains(response, "Open document")

    def test_owner_can_assign_read_edit_and_revoke_for_selected_viewer(self):
        self.client.force_login(self.owner)
        access_url = reverse("documents:owner_viewer_access", args=[self.viewer.pk])

        for action in ("read", "edit"):
            response = self.client.post(
                access_url,
                {"document_id": self.document.pk, "action": action},
            )
            self.assertRedirects(response, access_url)
            self.assertEqual(
                DocumentGrant.objects.get(document=self.document, user=self.viewer).permission,
                action,
            )

        self.client.post(
            access_url,
            {"document_id": self.document.pk, "action": "revoke"},
        )
        self.assertFalse(DocumentGrant.objects.filter(document=self.document, user=self.viewer).exists())

    def test_viewer_change_is_pending_until_owner_approves(self):
        DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            permission=DocumentGrant.Permission.EDIT,
        )
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse("documents:document_change_submit", args=[self.document.pk]),
            {"submitted_file": SimpleUploadedFile("changed.pdf", b"%PDF-1.7 changed content")},
        )

        self.assertRedirects(
            response,
            reverse("documents:document_detail", args=[self.document.pk]),
        )
        change_request = DocumentChangeRequest.objects.get(document=self.document)
        self.assertEqual(change_request.status, DocumentChangeRequest.Status.PENDING)
        self.assertEqual(self.document.file.read(), b"%PDF-1.4 confidential text")

        self.client.force_login(self.owner)
        detail_url = reverse("documents:document_change_detail", args=[change_request.pk])
        preview = self.client.get(
            reverse("documents:document_change_preview", args=[change_request.pk])
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(b"".join(preview.streaming_content), b"%PDF-1.7 changed content")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(detail_url, {"decision": "approve"})

        self.assertRedirects(response, f"{reverse('documents:document_list')}?section=approval-requests")
        self.document.refresh_from_db()
        change_request.refresh_from_db()
        self.assertEqual(change_request.status, DocumentChangeRequest.Status.APPROVED)
        self.assertEqual(self.document.file.read(), b"%PDF-1.7 changed content")

    def test_declined_viewer_change_leaves_document_unchanged_and_notifies_viewer(self):
        DocumentGrant.objects.create(
            document=self.document,
            user=self.viewer,
            permission=DocumentGrant.Permission.EDIT,
        )
        self.client.force_login(self.viewer)
        self.client.post(
            reverse("documents:document_change_submit", args=[self.document.pk]),
            {"submitted_file": SimpleUploadedFile("changed.pdf", b"%PDF-1.7 declined content")},
        )
        change_request = DocumentChangeRequest.objects.get(document=self.document)

        self.client.force_login(self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("documents:document_change_detail", args=[change_request.pk]),
                {"decision": "decline"},
            )

        self.document.refresh_from_db()
        self.assertEqual(self.document.file.read(), b"%PDF-1.4 confidential text")
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse("documents:document_list"),
            {"tab": "uploaded"},
        )
        self.assertContains(response, "Your request has been declined by the owner.")


class AuditChainTests(TestCase):
    def setUp(self):
        self.file_field = Document._meta.get_field("file")
        self.original_storage = self.file_field.storage
        self.change_file_field = DocumentChangeRequest._meta.get_field("submitted_file")
        self.original_change_storage = self.change_file_field.storage
        self.storage = InMemoryStorage()
        self.file_field.storage = self.storage
        self.change_file_field.storage = self.storage
        self.actor = User.objects.create_user(
            username="auditor",
            password="SecurePass123!test",
            role=User.Role.OWNER,
            is_approved=True,
        )

    def tearDown(self):
        for document in Document.objects.all():
            document.file.delete(save=False)
        for change_request in DocumentChangeRequest.objects.all():
            change_request.submitted_file.delete(save=False)
        self.file_field.storage = self.original_storage
        self.change_file_field.storage = self.original_change_storage

    def test_events_form_verifiable_chain_and_tampering_is_detected(self):
        record_event(actor=self.actor, action="document_shared", target_label="report")
        record_event(actor=self.actor, action="document_received", target_label="report")
        self.assertTrue(verify_audit_chain())

        event = AuditEvent.objects.first()
        AuditEvent.objects.filter(pk=event.pk).update(target_label="changed")
        self.assertFalse(verify_audit_chain())

    def test_request_ip_is_recorded_and_protected_by_the_audit_hash(self):
        request = RequestFactory().get("/", REMOTE_ADDR="203.0.113.8")
        event = record_event(
            actor=self.actor,
            action="document_received",
            target_label="report",
            request=request,
        )

        self.assertEqual(event.ip_address, "203.0.113.8")
        self.assertTrue(verify_audit_chain())
        AuditEvent.objects.filter(pk=event.pk).update(ip_address="203.0.113.9")
        self.assertFalse(verify_audit_chain())

    def test_trusted_forwarded_ip_is_recorded_instead_of_proxy_ip(self):
        request = RequestFactory().get(
            "/",
            REMOTE_ADDR="10.0.0.2",
            HTTP_X_FORWARDED_FOR="203.0.113.8",
        )
        with patch("documents.services.settings.TRUSTED_PROXY_COUNT", 1):
            event = record_event(
                actor=self.actor,
                action="document_received",
                target_label="report",
                request=request,
            )

        self.assertEqual(event.ip_address, "203.0.113.8")
        self.assertTrue(verify_audit_chain())

    def test_forwarded_ip_uses_proxy_count_and_ignores_untrusted_header(self):
        forwarded_request = RequestFactory().get(
            "/",
            REMOTE_ADDR="10.0.0.3",
            HTTP_X_FORWARDED_FOR="203.0.113.8, 198.51.100.7",
        )
        with patch("documents.services.settings.TRUSTED_PROXY_COUNT", 2):
            forwarded_event = record_event(
                actor=self.actor,
                action="document_received",
                target_label="trusted report",
                request=forwarded_request,
            )

        untrusted_request = RequestFactory().get(
            "/",
            REMOTE_ADDR="203.0.113.9",
            HTTP_X_FORWARDED_FOR="192.0.2.55",
        )
        with patch("documents.services.settings.TRUSTED_PROXY_COUNT", 0):
            untrusted_event = record_event(
                actor=self.actor,
                action="document_received",
                target_label="direct report",
                request=untrusted_request,
            )

        self.assertEqual(forwarded_event.ip_address, "203.0.113.8")
        self.assertEqual(untrusted_event.ip_address, "203.0.113.9")
        self.assertTrue(verify_audit_chain())

    def test_deleting_referenced_user_does_not_break_audit_chain(self):
        record_event(actor=self.actor, action="account_deleted", target_label=self.actor.username)
        self.actor.delete()
        self.assertTrue(verify_audit_chain())

    def test_deleting_referenced_document_does_not_break_audit_chain(self):
        document = Document.objects.create(
            owner=self.actor,
            title="Audit target",
            file=SimpleUploadedFile("target.pdf", b"%PDF-1.4 sample", content_type="application/pdf"),
        )
        record_event(
            actor=self.actor,
            action="document_received",
            target_label=document.title,
            document=document,
        )
        document.delete()
        self.assertTrue(verify_audit_chain())
