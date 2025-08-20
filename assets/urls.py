from rest_framework.routers import DefaultRouter

from .views import AssetUploadViewSet

router = DefaultRouter()
router.register(r"assets/uploads", AssetUploadViewSet, basename="assets-uploads")

urlpatterns = router.urls
