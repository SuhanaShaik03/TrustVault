from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),
    path("admin/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/storage-health/", views.storage_health, name="storage_health"),
    path("admin/invitations/", views.admin_invitations, name="admin_invitations"),
    path("admin/users/", views.user_list, name="user_list"),
    path("admin/users/create/", views.user_create, name="user_create"),
    path("admin/users/<int:user_id>/delete/", views.user_delete, name="user_delete"),
    path("admin/requests/<int:request_id>/", views.request_detail, name="request_detail"),
    path(
        "admin/requests/<int:request_id>/review/",
        views.review_request,
        name="review_request",
    ),
]
