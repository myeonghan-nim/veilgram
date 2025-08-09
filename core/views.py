import uuid, secrets

from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer


from .models import User, DeviceCredential
from .serializers import SignupInputSerializer, SignupOutputSerializer, DeviceLoginSerializer


class AuthViewSet(viewsets.GenericViewSet):
    queryset = User.objects.all()
    permission_classes = [AllowAny]

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def signup(self, request):
        serializer = SignupInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.create_user()
        device_id = serializer.validated_data.get("device_id") or str(uuid.uuid4())
        device_secret = secrets.token_urlsafe(32)
        cred = DeviceCredential(user=user, device_id=device_id, is_active=True)
        cred.set_secret(device_secret)
        cred.save()

        data = SignupOutputSerializer.build_response(user, device_id, device_secret)
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def login(self, request):
        serializer = DeviceLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def refresh(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)
