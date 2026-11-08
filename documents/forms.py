from django import forms

from documents.models import Document, DocumentChangeRequest, DocumentGrant
from documents.validators import validate_document_file


class DocumentForm(forms.ModelForm):
    file = forms.FileField(
        validators=[validate_document_file],
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx"}),
    )

    class Meta:
        model = Document
        fields = ("title", "description", "file")


class DocumentEditForm(forms.ModelForm):
    file = forms.FileField(
        required=False,
        validators=[validate_document_file],
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx"}),
    )

    class Meta:
        model = Document
        fields = ("title", "description", "file")


class GrantForm(forms.ModelForm):
    class Meta:
        model = DocumentGrant
        fields = ("user", "permission")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.models import User

        self.fields["user"].queryset = User.objects.filter(
            role=User.Role.VIEWER,
            is_active=True,
            is_approved=True,
        ).order_by("username")


class DocumentChangeRequestForm(forms.ModelForm):
    submitted_file = forms.FileField(
        required=True,
        validators=[validate_document_file],
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx"}),
    )

    class Meta:
        model = DocumentChangeRequest
        fields = ("submitted_file",)
        labels = {"submitted_file": "Modified document"}


class GrantActionForm(forms.Form):
    ACTIONS = (
        (DocumentGrant.Permission.READ, "Read"),
        (DocumentGrant.Permission.EDIT, "Edit"),
        ("revoke", "Revoke"),
    )
    document_id = forms.UUIDField(widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=ACTIONS, widget=forms.HiddenInput)
