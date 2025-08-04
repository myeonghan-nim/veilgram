from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import SignupSerializer


class SignupViewSet(viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = SignupSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=["post"])
    def signup(self, request):
        user = User.objects.create_user()
        refresh = RefreshToken.for_user(user)

        serializer = self.get_serializer(instance=user)

        data = serializer.data
        data["access"] = str(refresh.access_token)
        data["refresh"] = str(refresh)
        return Response(data, status=status.HTTP_201_CREATED)
