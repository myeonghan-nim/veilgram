from rest_framework.routers import DefaultRouter

from .views import SignupViewSet

router = DefaultRouter()
router.register(r"auth", SignupViewSet, basename="auth")

urlpatterns = router.urls
