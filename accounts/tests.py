from urllib.parse import parse_qs, urlsplit

from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import LoginAccessRequest, User
from documents.models import AuditEvent, Document, DocumentChangeRequest, DocumentGrant
from documents.services import record_event, verify_audit_chain


class LoginApprovalTests(TestCase):
    def setUp(self):
        self.file_field = Document._meta.get_field("file")
        self.original_storage = self.file_field.storage
        self.change_file_field = DocumentChangeRequest._meta.get_field("submitted_file")
        self.original_change_storage = self.change_file_field.storage
        self.storage = InMemoryStorage()
        self.file_field.storage = self.storage
        self.change_file_field.storage = self.storage
        self.admin = User.objects.create_superuser(
            username="root",
            email="root@example.test",
            password="SecurePass123!test",
        )
        self.viewer = User.objects.create_user(
            username="new-viewer",
            email="viewer@example.test",
            first_name="New",
            last_name="Viewer",
            password="SecurePass123!test",
            role=User.Role.VIEWER,
            is_approved=False,
        )

    def tearDown(self):
        for document in Document.objects.all():
            document.file.delete(save=False)
        for change_request in DocumentChangeRequest.objects.all():
            change_request.submitted_file.delete(save=False)
        self.file_field.storage = self.original_storage
        self.change_file_field.storage = self.original_change_storage

    def test_health_check_confirms_database_is_available(self):
        response = self.client.get(reverse("health_check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_valid_unapproved_login_creates_request_and_denies_session(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "new-viewer", "password": "SecurePass123!test"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administrator approval required")
        self.assertNotIn("_auth_user_id", self.client.session)
        request = LoginAccessRequest.objects.get(user=self.viewer)
        self.assertEqual(request.status, LoginAccessRequest.Status.PENDING)
        self.assertEqual(request.name_snapshot, "New Viewer")

    def test_root_url_shows_welcome_page_with_get_started_login_link(self):
        response = self.client.get(reverse("welcome"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome to TrustVault")
        self.assertContains(response, "Get started")
        self.assertContains(response, reverse("accounts:login"))

    def test_successful_login_shows_personalized_welcome_for_every_role(self):
        self.viewer.is_approved = True
        self.viewer.save()
        owner = User.objects.create_user(
            username="welcome-owner",
            email="welcome-owner@example.test",
            password="SecurePass123!test",
            first_name="Welcome",
            last_name="Owner",
            role=User.Role.OWNER,
            is_approved=True,
        )

        for account in (self.admin, owner, self.viewer):
            with self.subTest(role=account.role):
                response = self.client.post(
                    reverse("accounts:login"),
                    {"username": account.username, "password": "SecurePass123!test"},
                )
                for _ in range(3):
                    if response.status_code != 302:
                        break
                    response = self.client.get(response["Location"])
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f"Welcome, {account.display_name}")
                self.client.logout()

    def test_approval_allows_login(self):
        access_request = LoginAccessRequest.objects.create(
            user=self.viewer,
            username_snapshot=self.viewer.username,
            name_snapshot=self.viewer.display_name,
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("accounts:review_request", args=[access_request.pk]),
            {"decision": "approve"},
        )

        self.assertRedirects(response, reverse("accounts:admin_dashboard"))
        self.viewer.refresh_from_db()
        access_request.refresh_from_db()
        self.assertTrue(self.viewer.is_approved)
        self.assertEqual(access_request.status, LoginAccessRequest.Status.APPROVED)

        self.client.logout()
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "new-viewer", "password": "SecurePass123!test"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("accounts:dashboard"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_declined_login_displays_denial_and_submits_new_request(self):
        LoginAccessRequest.objects.create(
            user=self.viewer,
            username_snapshot=self.viewer.username,
            name_snapshot=self.viewer.display_name,
            status=LoginAccessRequest.Status.DECLINED,
        )

        response = self.client.post(
            reverse("accounts:login"),
            {"username": "new-viewer", "password": "SecurePass123!test"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "You do not have access to log in", status_code=403)
        self.assertEqual(
            LoginAccessRequest.objects.filter(
                user=self.viewer,
                status=LoginAccessRequest.Status.PENDING,
            ).count(),
            1,
        )

    def test_public_registration_creates_viewer_and_request(self):
        login_response = self.client.get(reverse("accounts:login"))
        self.assertContains(login_response, "Create an account")
        self.assertNotContains(login_response, "Register a viewer account")

        registration_page = self.client.get(reverse("accounts:register"))
        self.assertContains(registration_page, "Account type")
        self.assertContains(registration_page, "Administrator")
        self.assertContains(registration_page, "Owner")
        self.assertContains(registration_page, "Viewer")

        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "self-registered",
                "first_name": "Self",
                "last_name": "Registered",
                "email": "self@example.test",
                "role": User.Role.VIEWER,
                "password1": "StrongPass987!test",
                "password2": "StrongPass987!test",
            },
        )

        self.assertEqual(response.status_code, 200)
        account = User.objects.get(username="self-registered")
        self.assertEqual(account.role, User.Role.VIEWER)
        self.assertFalse(account.is_approved)
        self.assertTrue(
            LoginAccessRequest.objects.filter(
                user=account,
                status=LoginAccessRequest.Status.PENDING,
            ).exists()
        )

    def test_public_registration_can_request_owner_role(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "self-registered-owner",
                "first_name": "Self",
                "last_name": "Registered",
                "email": "self-registered-owner@example.test",
                "role": User.Role.OWNER,
                "password1": "StrongPass987!test",
                "password2": "StrongPass987!test",
            },
        )

        self.assertEqual(response.status_code, 200)
        account = User.objects.get(username="self-registered-owner")
        self.assertEqual(account.role, User.Role.OWNER)
        self.assertFalse(account.is_approved)
        self.assertTrue(
            LoginAccessRequest.objects.filter(
                user=account,
                status=LoginAccessRequest.Status.PENDING,
            ).exists()
        )

    def test_admin_registration_requires_an_invitation_and_creates_no_access_request(self):
        registration_url = reverse("accounts:register")
        response = self.client.post(
            registration_url,
            {
                "username": "uninvited-admin",
                "first_name": "Uninvited",
                "email": "uninvited@example.test",
                "role": User.Role.ADMIN,
                "password1": "StrongPass987!test",
                "password2": "StrongPass987!test",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "requires a valid invitation")
        self.assertFalse(User.objects.filter(username="uninvited-admin").exists())

        self.client.force_login(self.admin)
        invite_response = self.client.post(reverse("accounts:admin_invitations"))
        self.assertEqual(invite_response.status_code, 200)
        invitation_url = invite_response.context["invitation_url"]
        invitation_token = parse_qs(urlsplit(invitation_url).query)["invite"][0]
        self.client.logout()

        response = self.client.get(invitation_url.replace("http://testserver", ""))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="invitation"')
        response = self.client.post(
            registration_url,
            {
                "username": "invited-admin",
                "first_name": "Invited",
                "email": "invited@example.test",
                "role": User.Role.ADMIN,
                "invitation": invitation_token,
                "password1": "StrongPass987!test",
                "password2": "StrongPass987!test",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administrator account created")
        self.assertNotContains(response, "approval required")

        account = User.objects.get(username="invited-admin")
        self.assertEqual(account.role, User.Role.ADMIN)
        self.assertTrue(account.is_approved)
        self.assertFalse(LoginAccessRequest.objects.filter(user=account).exists())
        login_response = self.client.post(
            reverse("accounts:login"),
            {"username": "invited-admin", "password": "StrongPass987!test"},
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response["Location"], reverse("accounts:dashboard"))
        self.client.logout()

        response = self.client.post(
            registration_url,
            {
                "username": "reused-invitation-admin",
                "first_name": "Reused",
                "email": "reused@example.test",
                "role": User.Role.ADMIN,
                "invitation": invitation_token,
                "password1": "StrongPass987!test",
                "password2": "StrongPass987!test",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "requires a valid invitation")
        self.assertFalse(User.objects.filter(username="reused-invitation-admin").exists())

    def test_non_admin_cannot_open_admin_dashboard(self):
        self.viewer.is_approved = True
        self.viewer.save()
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("accounts:admin_dashboard"))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse("accounts:admin_invitations"))
        self.assertEqual(response.status_code, 403)

    def test_admin_created_owner_still_requires_login_approval(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("accounts:user_create"),
            {
                "username": "managed-owner",
                "first_name": "Managed",
                "last_name": "Owner",
                "email": "managed@example.test",
                "role": User.Role.OWNER,
                "password1": "ExcellentPass321!test",
                "password2": "ExcellentPass321!test",
            },
        )

        self.assertRedirects(response, reverse("accounts:user_list"))
        owner = User.objects.get(username="managed-owner")
        self.assertFalse(owner.is_approved)
        self.assertTrue(
            LoginAccessRequest.objects.filter(
                user=owner,
                status=LoginAccessRequest.Status.PENDING,
            ).exists()
        )

    def test_admin_dashboard_shows_only_selected_section(self):
        access_request = LoginAccessRequest.objects.create(
            user=self.viewer,
            username_snapshot=self.viewer.username,
            name_snapshot=self.viewer.display_name,
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse("accounts:admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Login details")
        self.assertContains(response, self.viewer.username)
        self.assertNotContains(response, "Login approval requests")
        self.assertNotContains(response, "Document sending, receiving, and modification activity")

        response = self.client.get(
            reverse("accounts:admin_dashboard"),
            {"section": "requests"},
        )
        self.assertContains(response, "Login approval requests")
        self.assertContains(response, self.viewer.username)
        self.assertNotContains(response, "Select account type")
        self.assertContains(
            response,
            reverse("accounts:request_detail", args=[access_request.pk]),
        )

        response = self.client.get(
            reverse("accounts:admin_dashboard"),
            {"section": "activity"},
        )
        self.assertContains(response, "Document sending, receiving, and modification activity")
        self.assertContains(response, "IP address")
        self.assertNotContains(response, "Select account type")

    def test_admin_dashboard_role_filter_keeps_login_details_open(self):
        self.client.force_login(self.admin)
        for role, username in (
            (User.Role.ADMIN, self.admin.username),
            (User.Role.VIEWER, self.viewer.username),
        ):
            with self.subTest(role=role):
                response = self.client.get(
                    reverse("accounts:admin_dashboard"),
                    {"role": role},
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="login-details"')
                self.assertContains(response, username)
                self.assertContains(response, 'name="section" value="login-details"')
                self.assertEqual(response.context["role_filter"], role)

    def test_admin_dashboard_paginates_complete_activity_history(self):
        for index in range(55):
            record_event(
                actor=self.admin,
                action="document_received",
                target_label=f"activity-{index}",
            )
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("accounts:admin_dashboard"),
            {"section": "activity", "page": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 2 of 2")
        self.assertContains(response, "activity-0")

    def test_deleting_owner_removes_documents_and_preserves_audit_history(self):
        owner = User.objects.create_user(
            username="delete-owner",
            password="SecurePass123!test",
            role=User.Role.OWNER,
            is_approved=True,
        )
        document = Document.objects.create(
            owner=owner,
            title="Owned report",
            file=SimpleUploadedFile("owned.pdf", b"%PDF-1.4 private report", content_type="application/pdf"),
        )
        shared_owner = User.objects.create_user(
            username="shared-owner",
            password="SecurePass123!test",
            role=User.Role.OWNER,
            is_approved=True,
        )
        shared_document = Document.objects.create(
            owner=shared_owner,
            title="Shared report",
            file=SimpleUploadedFile("shared.pdf", b"%PDF-1.4 shared report", content_type="application/pdf"),
        )
        DocumentGrant.objects.create(document=shared_document, user=owner)
        file_name = document.file.name
        storage = document.file.storage
        self.client.force_login(self.admin)

        response = self.client.post(reverse("accounts:user_delete", args=[owner.pk]))

        self.assertRedirects(response, reverse("accounts:user_list"))
        self.assertFalse(Document.objects.filter(pk=document.pk).exists())
        self.assertFalse(storage.exists(file_name))
        self.assertTrue(
            AuditEvent.objects.filter(
                action="document_deleted",
                target_label="Owned report",
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action="document_access_revoked",
                target_label="Shared report",
            ).exists()
        )
        self.assertTrue(verify_audit_chain())
