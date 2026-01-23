from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from django.conf.urls.static import static
from django.conf import settings


router = DefaultRouter()
router.register(r"departments", views.DepartmentViewSet)
router.register(r"staff", views.StaffViewSet)
router.register(r"visits", views.VisitViewSet)
router.register(r"settings", views.SystemSettingViewSet)
# router.register(r"notificationlogs", views.NotificationLogViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("departments/hierarchy/", views.DepartmentViewSet.as_view({"get": "hierarchy"}), name="department-hierarchy"),
    path("staff/search/", views.StaffViewSet.as_view({"get": "search"}), name="staff-search"),
    path("staff/import_csv/", views.StaffViewSet.as_view({"post": "import_csv"}), name="staff-import-csv"),
    path("staff/export_csv/", views.StaffViewSet.as_view({"get": "export_csv"}), name="staff-export-csv"),
    path("visits/<int:pk>/respond/", views.VisitViewSet.as_view({"post": "respond"}), name="visit-respond"),
    path("visits/<int:pk>/escalate/", views.VisitViewSet.as_view({"post": "escalate"}), name="visit-escalate"),
    path("visits/statistics/", views.VisitViewSet.as_view({"get": "statistics"}), name="visit-statistics"),
    path("settings/get_setting/", views.SystemSettingViewSet.as_view({"get": "get_setting"}), name="systemsetting-get-setting"),
    path("settings/set_setting/", views.SystemSettingViewSet.as_view({"post": "set_setting"}), name="systemsetting-set-setting"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)