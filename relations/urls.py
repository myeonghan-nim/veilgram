from rest_framework.routers import SimpleRouter

from .views import UserRelationViewSet

router = SimpleRouter(trailing_slash=False)
router.register(r"users", UserRelationViewSet, basename="user-relations")

urlpatterns = router.urls
