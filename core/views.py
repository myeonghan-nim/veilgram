import uuid, secrets

from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken


from .models import User, DeviceCredential
from .serializers import SignupInputSerializer, SignupOutputSerializer, DeviceLoginSerializer, LogoutSerializer
from .services.session import enforce_single_device_session


class AuthViewSet(viewsets.GenericViewSet):
    queryset = User.objects.all()
    permission_classes = [AllowAny]

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def signup(self, request):
        s = SignupInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        user = User.objects.create_user()
        device_id = s.validated_data.get("device_id") or str(uuid.uuid4())
        device_secret = secrets.token_urlsafe(32)
        cred = DeviceCredential(user=user, device_id=device_id, is_active=True)
        cred.set_secret(device_secret)
        cred.save()

        enforce_single_device_session(user, device_id)

        data = SignupOutputSerializer.build_response(user, device_id, device_secret)
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def login(self, request):
        s = DeviceLoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        user = s.validated_data["user"]
        device_id = s.validated_data["device_id"]

        enforce_single_device_session(user, device_id)
        refresh = RefreshToken.for_user(user)
        data = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user_id": str(user.id),
        }

        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def refresh(self, request):
        s = TokenRefreshSerializer(data=request.data)
        try:
            s.is_valid(raise_exception=True)
        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(s.validated_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def logout(self, request):
        s = LogoutSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        all_logout = s.validated_data.get("all_logout", False)
        if all_logout:
            if not request.user or not request.user.is_authenticated:
                return Response(status=status.HTTP_401_UNAUTHORIZED)

            for t in OutstandingToken.objects.filter(user=request.user):
                try:
                    BlacklistedToken.objects.get_or_create(token=t)
                except Exception:
                    pass
            return Response(status=status.HTTP_204_NO_CONTENT)

        refresh_token = s.validated_data.get("refresh", "")
        try:
            RefreshToken(refresh_token).blacklist()
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)
