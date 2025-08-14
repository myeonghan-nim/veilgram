from rest_framework.routers import SimpleRouter

from .views import ProfileViewSet

router = SimpleRouter(trailing_slash=False)
router.register(prefix=r"profile", viewset=ProfileViewSet, basename="profile")

urlpatterns = router.urls
