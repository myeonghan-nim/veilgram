from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeviceViewSet, NotificationSettingViewSet, NotificationViewSet

router = DefaultRouter()
router.register(r"notifications/devices", DeviceViewSet, basename="notification-device")
router.register(r"notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("", include(router.urls)),
    path("notifications/settings", NotificationSettingViewSet.as_view({"get": "list", "put": "update"})),
]
