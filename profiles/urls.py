from rest_framework.routers import SimpleRouter

from .views import ProfileViewSet

router = SimpleRouter(trailing_slash=False)
router.register(prefix=r"profiles", viewset=ProfileViewSet, basename="profiles")

urlpatterns = router.urls
