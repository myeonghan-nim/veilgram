from rest_framework.routers import DefaultRouter

from .views import ModerationCheckViewSet, ModerationRuleViewSet

router = DefaultRouter()
router.register("moderation", ModerationCheckViewSet, basename="moderation-check")
router.register("moderation/rules", ModerationRuleViewSet, basename="moderation-rules")

urlpatterns = router.urls
