from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ReportsViewSet

router = DefaultRouter()
router.register(r"reports", ReportsViewSet, basename="reports")

urlpatterns = [
    path("", include(router.urls)),
]
