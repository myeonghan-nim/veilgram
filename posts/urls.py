from rest_framework.routers import DefaultRouter

from .views import BookmarkViewSet, PostViewSet

router = DefaultRouter()
router.register(r"posts", PostViewSet, basename="posts")
router.register(r"bookmarks", BookmarkViewSet, basename="bookmarks")

urlpatterns = router.urls
