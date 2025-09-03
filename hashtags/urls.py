from rest_framework.routers import DefaultRouter

from .views import HashtagViewSet

router = DefaultRouter()
router.register(r"hashtags", HashtagViewSet, basename="hashtags")

urlpatterns = router.urls
