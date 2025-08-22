from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Post
from .serializers import PostCreateIn, PostOut
from .services import create_post


class PostViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Post.objects.all()

    def create(self, request):
        """
        POST /api/v1/posts/
        {
            "content": "text ...",
            "asset_ids": ["uuid", ...],                               # optional
            "poll_id": "uuid",                                        # optional
            "poll": {"options": ["A","B"], "allow_multiple": false}   # optional (poll_id와 동시 금지)
        }
        -> { "id": "...", "author": "...", "created_at": "..." }
        """
        ser = PostCreateIn(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        try:
            post = create_post(
                author=request.user,
                content=v["content"],
                asset_ids=v.get("asset_ids") or [],
                poll_id=str(v["poll_id"]) if v.get("poll_id") else None,
                poll_options=(v["poll"]["options"] if v.get("poll") else None),
                allow_multiple=(v["poll"].get("allow_multiple", False) if v.get("poll") else False),
            )
        except DjangoValidationError as e:
            detail = getattr(e, "message_dict", None) or getattr(e, "messages", None) or str(e)
            raise DRFValidationError(detail)
        return Response(PostOut(post).data, status=status.HTTP_201_CREATED)
