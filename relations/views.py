from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiTypes, OpenApiExample
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services import RelationshipService
from common.schema import ErrorOut

User = get_user_model()


class UserRelationViewSet(viewsets.ViewSet):
    """
    /api/v1/users/{pk}/follow   (POST: follow, DELETE: unfollow)
    /api/v1/users/{pk}/block    (POST: block,  DELETE: unblock)
    """

    permission_classes = [IsAuthenticated]
    lookup_field = "pk"  # 기본값. URL의 {pk}가 target user id
    serializer_class = serializers.Serializer

    def _get_target(self, pk):
        return get_object_or_404(User, id=pk)

    @extend_schema(
        tags=["Relations"],
        summary="사용자 팔로우",
        operation_id="users_follow",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="대상 사용자 ID (UUID)")],
        request=None,
        responses={
            204: OpenApiResponse(description="팔로우 성공"),
            400: OpenApiResponse(response=ErrorOut, description="자기 자신 팔로우 등 정책 위반"),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut, description="대상 사용자가 없거나 접근 불가"),
        },
        examples=[OpenApiExample("예시", value=None, request_only=True, description="POST /api/v1/users/{id}/follow")],
    )
    @action(detail=True, methods=["post"], url_path="follow")
    def follow(self, request, pk=None):
        target = self._get_target(pk)
        RelationshipService.follow(request.user, target)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Relations"],
        summary="사용자 언팔로우",
        operation_id="users_unfollow",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="대상 사용자 ID (UUID)")],
        request=None,
        responses={
            204: OpenApiResponse(description="언팔로우 성공"),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut, description="팔로우 관계 없음 또는 대상 없음"),
        },
        examples=[OpenApiExample("예시", value=None, request_only=True, description="DELETE /api/v1/users/{id}/follow")],
    )
    @follow.mapping.delete
    def unfollow(self, request, pk=None):
        target = self._get_target(pk)
        RelationshipService.unfollow(request.user, target)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Relations"],
        summary="사용자 차단",
        operation_id="users_block",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="대상 사용자 ID (UUID)")],
        request=None,
        responses={
            204: OpenApiResponse(description="차단 성공"),
            400: OpenApiResponse(response=ErrorOut, description="자기 자신 차단 등 정책 위반"),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut, description="대상 사용자가 없거나 접근 불가"),
        },
        examples=[OpenApiExample("예시", value=None, request_only=True, description="POST /api/v1/users/{id}/block")],
    )
    @action(detail=True, methods=["post"], url_path="block")
    def block(self, request, pk=None):
        target = self._get_target(pk)
        RelationshipService.block(request.user, target)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Relations"],
        summary="사용자 차단 해제",
        operation_id="users_unblock",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="대상 사용자 ID (UUID)")],
        request=None,
        responses={
            204: OpenApiResponse(description="차단 해제 성공"),
            401: OpenApiResponse(response=ErrorOut),
            404: OpenApiResponse(response=ErrorOut, description="차단 관계 없음 또는 대상 없음"),
        },
        examples=[OpenApiExample("예시", value=None, request_only=True, description="DELETE /api/v1/users/{id}/block")],
    )
    @block.mapping.delete
    def unblock(self, request, pk=None):
        target = self._get_target(pk)
        RelationshipService.unblock(request.user, target)
        return Response(status=status.HTTP_204_NO_CONTENT)
