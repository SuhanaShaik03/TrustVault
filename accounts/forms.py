from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from accounts.models import User
from accounts.services import has_valid_admin_invitation


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    role = forms.ChoiceField(
        choices=User.Role.choices,
        initial=User.Role.VIEWER,
        label="Account type",
    )
    invitation = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "role")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("role") == User.Role.ADMIN and not has_valid_admin_invitation(
            cleaned_data.get("invitation", "")
        ):
            self.add_error(
                None,
                "Administrator registration requires a valid invitation link.",
            )
        return cleaned_data


class UserCreateForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    role = forms.ChoiceField(
        choices=((User.Role.OWNER, "Owner"), (User.Role.VIEWER, "Viewer"))
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "role")

    def __init__(self, *args, allow_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        if allow_admin:
            self.fields["role"].choices = User.Role.choices

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data["role"]
        user.is_approved = user.role == User.Role.ADMIN
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="User ID")
