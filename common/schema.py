from drf_spectacular.utils import inline_serializer
from rest_framework import serializers

# Common
ErrorOut = inline_serializer(
    name="ErrorOut",
    fields={"detail": serializers.CharField(help_text="Human readable error message.")},
)

# JWT
JWTOut = inline_serializer(
    name="JWTOut",
    fields={
        "access": serializers.CharField(),
        "refresh": serializers.CharField(),
        "token_type": serializers.CharField(default="bearer"),
        "expires_in": serializers.IntegerField(help_text="Access token TTL in seconds"),
    },
)

# Authors
AuthorOut = inline_serializer(
    name="AuthorOut",
    fields={
        "id": serializers.UUIDField(),
        "nickname": serializers.CharField(required=False),
        "avatar_url": serializers.URLField(required=False, allow_null=True),
    },
)

# Assets
AssetIdsIn = inline_serializer(
    name="AssetIdsIn",
    fields={"asset_ids": serializers.ListField(child=serializers.UUIDField(), min_length=1, help_text="Attach 대상 Asset ID 목록(1개 이상)")},
)

AttachErrorsOut = inline_serializer(
    name="AttachErrorsOut",
    fields={"errors": serializers.DictField(child=serializers.CharField(), help_text="key=asset_id, value=오류 사유")},
)

# Availability
AvailabilityOut = inline_serializer(
    name="AvailabilityOut",
    fields={
        "nickname": serializers.CharField(),
        "available": serializers.BooleanField(),
        "reasons": serializers.ListField(child=serializers.CharField()),
    },
)

# Moderation
OkOut = inline_serializer(
    name="OkOut",
    fields={"ok": serializers.BooleanField()},
)

# Realtime (WebSocket)
RealtimeCapabilitiesOut = inline_serializer(
    name="RealtimeCapabilitiesOut",
    fields={
        "websocket_url": serializers.CharField(help_text="WS endpoint (absolute or relative)"),
        "auth": inline_serializer(
            name="RealtimeAuthHints",
            fields={
                "subprotocol": serializers.CharField(required=False, help_text="예: JWT 를 Sec-WebSocket-Protocol 로 전달"),
                "authorization_header": serializers.CharField(required=False, help_text="예: Authorization: Bearer <token>"),
                "requires_user_id_scope": serializers.BooleanField(required=False, help_text="ASGI scope['user_id'] 필수 여부"),
            },
        ),
        "events": serializers.ListField(
            child=inline_serializer(
                name="RealtimeEventMeta",
                fields={
                    "type": serializers.CharField(),
                    "direction": serializers.ChoiceField(choices=["server->client", "client->server"]),
                    "desc": serializers.CharField(required=False),
                    "example": serializers.DictField(child=serializers.CharField(), required=False),
                },
            ),
            help_text="지원 이벤트/메시지 요약",
        ),
        "close_codes": serializers.DictField(child=serializers.CharField(), required=False, help_text="서버가 사용할 수 있는 Close code 사전"),
        "heartbeat_sec": serializers.IntegerField(required=False, help_text="권장 ping 주기(클라이언트에서 전송)"),
        "notes": serializers.ListField(child=serializers.CharField(), required=False),
    },
)

# Searches
SearchOut = inline_serializer(
    name="SearchOut",
    fields={
        "total": serializers.IntegerField(help_text="검색 결과 총 개수"),
        "results": serializers.ListField(child=serializers.DictField(), help_text="결과 항목 리스트(리소스 유형에 따라 필드가 달라질 수 있음)"),
    },
)

# Users
SignupOut = inline_serializer(
    name="SignupOut",
    fields={
        "user_id": serializers.UUIDField(),
        "device_id": serializers.CharField(),
        "device_secret": serializers.CharField(),
    },
)

LoginOut = inline_serializer(
    name="LoginOut",
    fields={
        "access": serializers.CharField(),
        "refresh": serializers.CharField(),
        "user_id": serializers.UUIDField(),
    },
)
