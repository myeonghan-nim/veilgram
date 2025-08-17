from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services import RelationshipService

User = get_user_model()


class UserRelationViewSet(viewsets.ViewSet):
    """
    /api/v1/users/{pk}/follow   (POST: follow, DELETE: unfollow)
    /api/v1/users/{pk}/block    (POST: block,  DELETE: unblock)
    """

    permission_classes = [IsAuthenticated]
    lookup_field = "pk"  # 기본값. URL의 {pk}가 target user id

    def _get_target(self, pk):
        return get_object_or_404(User, id=pk)

    @action(detail=True, methods=["post"], url_path="follow")
    def follow(self, request, pk=None):
        target = self._get_target(pk)
        RelationshipService.follow(request.user, target)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @follow.mapping.delete
    def unfollow(self, request, pk=None):
        target = self._get_target(pk)
        RelationshipService.unfollow(request.user, target)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="block")
    def block(self, request, pk=None):
        target = self._get_target(pk)
        RelationshipService.block(request.user, target)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @block.mapping.delete
    def unblock(self, request, pk=None):
        target = self._get_target(pk)
        RelationshipService.unblock(request.user, target)
        return Response(status=status.HTTP_204_NO_CONTENT)
