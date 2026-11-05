from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView


urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    re_path(
        r"^$",
        TemplateView.as_view(template_name="accounts/welcome.html"),
        name="welcome",
    ),
    path("", include("documents.urls")),
]
