from django.contrib import admin
from django.urls import include, path, re_path
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.db import DatabaseError, connection
from django.http import JsonResponse


@require_GET
def health_check(_request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("healthz/", health_check, name="health_check"),
    re_path(
        r"^$",
        TemplateView.as_view(template_name="accounts/welcome.html"),
        name="welcome",
    ),
    path("", include("documents.urls")),
]
