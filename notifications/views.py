from django.utils import timezone
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Device, NotificationSetting, Notification
from .serializers import DeviceIn, DeviceOut, NotificationSettingIn, NotificationSettingOut, NotificationOut, MarkReadIn


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

    @action(detail=False, methods=["POST"])
    def mark_read(self, request):
        ser = MarkReadIn(data=request.data)
        ser.is_valid(raise_exception=True)
        ids = ser.validated_data["ids"]
        updated = Notification.objects.filter(user=request.user, id__in=ids).update(is_read=True)
        return Response({"updated": updated})
