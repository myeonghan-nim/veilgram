from drf_spectacular.utils import inline_serializer
from rest_framework import serializers

ErrorOut = inline_serializer(
    name="ErrorOut",
    fields={"detail": serializers.CharField(help_text="Human readable error message.")},
)

JWTOut = inline_serializer(
    name="JWTOut",
    fields={
        "access": serializers.CharField(),
        "refresh": serializers.CharField(),
        "token_type": serializers.CharField(default="bearer"),
        "expires_in": serializers.IntegerField(help_text="Access token TTL in seconds"),
    },
)

AuthorOut = inline_serializer(
    name="AuthorOut",
    fields={
        "id": serializers.UUIDField(),
        "nickname": serializers.CharField(required=False),
        "avatar_url": serializers.URLField(required=False, allow_null=True),
    },
)
