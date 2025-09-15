import uuid, secrets

from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiTypes
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
from common.schema import ErrorOut, SignupOut, LoginOut


class AuthViewSet(viewsets.GenericViewSet):
    queryset = User.objects.all()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == "signup":
            return SignupInputSerializer
        if self.action == "login":
            return DeviceLoginSerializer
        if self.action == "refresh":
            return TokenRefreshSerializer
        if self.action == "logout":
            return LogoutSerializer
        return SignupInputSerializer

    @extend_schema(
        tags=["Auth"],
        summary="회원가입(디바이스 최초 등록)",
        description=(
            "새 사용자 계정을 생성하고, 초기 디바이스 자격증명(`device_id`, `device_secret`)을 발급합니다. " "이후 `login` 엔드포인트에서 해당 자격으로 JWT를 발급받을 수 있습니다."
        ),
        operation_id="auth_signup",
        request=SignupInputSerializer,
        responses={201: OpenApiResponse(response=SignupOut, description="생성된 사용자와 디바이스 자격증명"), 400: OpenApiResponse(response=ErrorOut)},
        examples=[
            OpenApiExample("요청 예시(기기 ID 지정)", value={"device_id": "ios-iphone15pro-max-1234"}, request_only=True),
            OpenApiExample(
                "응답 예시", value={"user_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "device_id": "ios-iphone15pro-max-1234", "device_secret": "k9tJx..._WX"}, response_only=True
            ),
        ],
    )
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

    @extend_schema(
        tags=["Auth"],
        summary="디바이스 로그인(JWT 발급)",
        description="디바이스 자격증명으로 로그인하여 `access` / `refresh` 토큰을 발급받습니다.",
        operation_id="auth_login",
        request=DeviceLoginSerializer,
        responses={200: OpenApiResponse(response=LoginOut, description="JWT와 사용자 ID"), 400: OpenApiResponse(response=ErrorOut)},
        examples=[
            OpenApiExample("요청 예시", value={"device_id": "ios-iphone15pro-max-1234", "device_secret": "k9tJx..._WX"}, request_only=True),
            OpenApiExample(
                "응답 예시",
                value={
                    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "user_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                },
                response_only=True,
            ),
        ],
    )
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

    @extend_schema(
        tags=["Auth"],
        summary="액세스 토큰 재발급",
        description="`refresh` 토큰으로 새로운 `access` 토큰을 재발급합니다.",
        operation_id="auth_refresh",
        request=TokenRefreshSerializer,
        responses={200: OpenApiResponse(response=TokenRefreshSerializer, description="새 access 토큰"), 401: OpenApiResponse(response=ErrorOut)},
        examples=[OpenApiExample("요청 예시", value={"refresh": "eyJhbGciOi..."}), OpenApiExample("응답 예시", value={"access": "eyJhbGciOi..."}, response_only=True)],
    )
    @action(detail=False, methods=["post"])
    def refresh(self, request):
        s = TokenRefreshSerializer(data=request.data)
        try:
            s.is_valid(raise_exception=True)
        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(s.validated_data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Auth"],
        summary="로그아웃(토큰 블랙리스트)",
        description=(
            "- `all_logout=true`이면 **현재 인증 사용자**의 모든 토큰을 블랙리스트 처리합니다(헤더에 `Authorization` 필요).\n"
            "- 그렇지 않으면 body의 `refresh` 토큰만 블랙리스트 처리합니다."
        ),
        operation_id="auth_logout",
        request=LogoutSerializer,
        responses={
            204: OpenApiResponse(description="로그아웃 성공"),
            400: OpenApiResponse(response=ErrorOut),
            401: OpenApiResponse(response=ErrorOut, description="all_logout=true 인데 인증 헤더 누락 등"),
        },
        examples=[
            OpenApiExample("모든 기기에서 로그아웃", value={"all_logout": True}, request_only=True),
            OpenApiExample("해당 refresh만 무효화", value={"refresh": "eyJhbGciOi..."}, request_only=True),
        ],
    )
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
