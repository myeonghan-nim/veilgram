from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse, OpenApiTypes, OpenApiExample, inline_serializer
from rest_framework import viewsets, mixins, status, serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Device, NotificationSetting, Notification
from .serializers import DeviceIn, DeviceOut, NotificationSettingIn, NotificationSettingOut, NotificationOut, MarkReadIn
from common.schema import ErrorOut


@extend_schema_view(
    list=extend_schema(
        tags=["Notifications/Devices"],
        summary="내 디바이스 토큰 목록",
        description="현재 사용자에 활성화된(Device.is_active=True) 디바이스 토큰 목록을 반환합니다.",
        operation_id="devices_list",
        responses={200: OpenApiResponse(response=DeviceOut(many=True)), 401: OpenApiResponse(response=ErrorOut)},
    ),
    create=extend_schema(
        tags=["Notifications/Devices"],
        summary="디바이스 토큰 등록(Upsert with deactivation)",
        description=("해당 `device_token`이 다른 사용자에 등록돼 있으면 그 레코드를 **비활성화**(is_active=False)한 뒤, " "현재 사용자 소유로 활성 등록합니다."),
        operation_id="devices_create",
        request=DeviceIn,
        responses={201: OpenApiResponse(response=DeviceOut, description="등록된 디바이스"), 400: OpenApiResponse(response=ErrorOut), 401: OpenApiResponse(response=ErrorOut)},
        examples=[OpenApiExample("요청 예시", value={"device_token": "fcm-xxx"})],
    ),
    destroy=extend_schema(
        tags=["Notifications/Devices"],
        summary="디바이스 토큰 비활성화",
        description="해당 디바이스 레코드를 **삭제 대신 비활성화**(is_active=False)합니다.",
        operation_id="devices_destroy",
        parameters=[OpenApiParameter(name="pk", location=OpenApiParameter.PATH, type=OpenApiTypes.UUID, description="디바이스 ID (UUID)")],
        responses={204: OpenApiResponse(description="비활성화 완료"), 401: OpenApiResponse(response=ErrorOut), 404: OpenApiResponse(response=ErrorOut)},
    ),
)
class DeviceViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Device.objects.filter(user=self.request.user, is_active=True).order_by("-created_at")

    def get_serializer_class(self):
        return DeviceOut if self.action in ("list",) else DeviceIn

    def perform_create(self, serializer):
        # 같은 token이 다른 유저에 등록되어 있다면 소유권 이전 or 비활성화 정책 선택 가능
        token = serializer.validated_data["device_token"]
        Device.objects.filter(device_token=token).exclude(user=self.request.user).update(is_active=False)
        serializer.save(user=self.request.user, is_active=True)

    def create(self, request, *args, **kwargs):
        ser_in = self.get_serializer(data=request.data)  # DeviceIn
        ser_in.is_valid(raise_exception=True)
        self.perform_create(ser_in)
        out = DeviceOut(ser_in.instance)  # id, created_at 포함
        return Response(out.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.is_active = False
        obj.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(
        tags=["Notifications/Settings"],
        summary="알림 설정 조회",
        description="현재 사용자의 알림 설정을 조회합니다. 없으면 기본값으로 생성해 반환합니다.",
        operation_id="notification_settings_get",
        responses={200: OpenApiResponse(response=NotificationSettingOut), 401: OpenApiResponse(response=ErrorOut)},
    ),
    update=extend_schema(
        tags=["Notifications/Settings"],
        summary="알림 설정 업데이트",
        description="현재 사용자의 알림 설정을 업데이트합니다.",
        operation_id="notification_settings_update",
        request=NotificationSettingIn,
        responses={
            200: OpenApiResponse(response=NotificationSettingOut, description="갱신된 설정"),
            400: OpenApiResponse(response=ErrorOut),
            401: OpenApiResponse(response=ErrorOut),
        },
        examples=[OpenApiExample("요청 예시", value={"push_enabled": True, "marketing_enabled": False}, request_only=True)],
    ),
)
class NotificationSettingViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _get_or_create(self, user):
        obj, _ = NotificationSetting.objects.get_or_create(user=user)
        return obj

    def list(self, request):
        obj = self._get_or_create(request.user)
        return Response(NotificationSettingOut(obj).data)

    def update(self, request):
        obj = self._get_or_create(request.user)
        ser = NotificationSettingIn(data=request.data)
        ser.is_valid(raise_exception=True)
        for k, v in ser.validated_data.items():
            setattr(obj, k, v)
        obj.updated_at = timezone.now()
        obj.save()
        return Response(NotificationSettingOut(obj).data)


@extend_schema_view(
    list=extend_schema(
        tags=["Notifications"],
        summary="내 알림 목록",
        description=("현재 사용자에게 발송된 알림을 최신순으로 반환합니다.\n" "- `read` 쿼리: `true` → 읽은 것만, `false` → 읽지 않은 것만, 생략 시 전체"),
        operation_id="notifications_list",
        parameters=[
            OpenApiParameter(name="read", location=OpenApiParameter.QUERY, required=False, type=OpenApiTypes.STR, description="읽음 필터: `true` | `false`", enum=["true", "false"])
        ],
        responses={200: OpenApiResponse(response=NotificationOut(many=True)), 401: OpenApiResponse(response=ErrorOut)},
    ),
)
class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationOut

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user).order_by("-created_at")
        read = self.request.query_params.get("read")
        if read == "true":
            qs = qs.filter(is_read=True)
        elif read == "false":
            qs = qs.filter(is_read=False)
        return qs

    @extend_schema(
        tags=["Notifications"],
        summary="알림 읽음 처리",
        description="요청한 알림 ID 목록을 읽음 처리합니다. 사용자 본인 소유의 알림만 처리됩니다.",
        operation_id="notifications_mark_read",
        request=MarkReadIn,
        responses={
            200: OpenApiResponse(response=inline_serializer(name="MarkReadOut", fields={"updated": serializers.IntegerField(help_text="읽음 처리된 개수")})),
            400: OpenApiResponse(response=ErrorOut),
            401: OpenApiResponse(response=ErrorOut),
        },
        examples=[
            OpenApiExample("요청 예시", value={"ids": ["11111111-1111-1111-1111-111111111111"]}, request_only=True),
            OpenApiExample("응답 예시", value={"updated": 1}, response_only=True),
        ],
    )
    @action(detail=False, methods=["POST"])
    def mark_read(self, request):
        ser = MarkReadIn(data=request.data)
        ser.is_valid(raise_exception=True)
        ids = ser.validated_data["ids"]
        updated = Notification.objects.filter(user=request.user, id__in=ids).update(is_read=True)
        return Response({"updated": updated})
