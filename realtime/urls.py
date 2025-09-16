from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RealtimeDocViewSet

router = DefaultRouter()
router.register("realtime", RealtimeDocViewSet, basename="realtime")

urlpatterns = [
    path("api/v1/", include(router.urls)),
]
