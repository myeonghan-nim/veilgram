from django.urls import include, re_path
from rest_framework.routers import SimpleRouter

from .views import CommentViewSet, PostCommentViewSet

router = SimpleRouter()
router.register(r"comments", CommentViewSet, basename="comment")
router.register(r"posts/(?P<post_id>[0-9a-f-]{36})/comments", PostCommentViewSet, basename="post-comments")

urlpatterns = [
    re_path(r"", include(router.urls)),
]
