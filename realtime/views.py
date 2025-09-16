from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.schema import RealtimeCapabilitiesOut


class RealtimeDocViewSet(viewsets.ViewSet):
    """
    WebSocket 핸드셰이크/계약을 Swagger/Redoc에서 '발견'할 수 있게 해주는 문서 전용 뷰.
    런타임 비즈니스 로직은 없고, 정적 가이드를 반환한다.
    """

    permission_classes = [IsAuthenticated]
    # 스키마 인트로스펙션 안정화
    serializer_class = serializers.Serializer

    @extend_schema(
        tags=["Realtime"],
        summary="Feed WebSocket 연결 가이드/능력치",
        description=(
            "실시간 Feed(WebSocket) 연결 정보를 제공합니다.\n\n"
            "핵심 규약은 `feed/consumers.py`에 근거합니다:\n"
            "- 연결 성공 조건: ASGI `scope['user_id']`가 있어야 합니다. 없으면 서버가 4401 코드로 바로 종료합니다.\n"
            "- 서버→클라이언트 이벤트: `feed_update` (payload는 `data` 필드에 그대로 전달)\n"
            '- 클라이언트→서버 메시지: `{"type":"ping"}` 전송 시 `{"event":"pong"}` 응답\n'
        ),
        operation_id="realtime_feed_capabilities",
        responses={200: OpenApiResponse(response=RealtimeCapabilitiesOut)},
        examples=[
            OpenApiExample(
                "응답 예시",
                value={
                    "websocket_url": "/ws/feed/",
                    "auth": {"subprotocol": "<JWT_ACCESS_TOKEN>", "authorization_header": "Bearer <JWT_ACCESS_TOKEN>", "requires_user_id_scope": True},
                    "events": [
                        {
                            "type": "feed_update",
                            "direction": "server->client",
                            "desc": "팔로잉 사용자/관심 리소스의 새 피드 항목",
                            "example": {"event": "feed_update", "data": {"post_id": "uuid", "author_id": "uuid"}},
                        },
                        {"type": "ping", "direction": "client->server", "desc": "헬스 체크용 ping", "example": {"type": "ping"}},
                        {"type": "pong", "direction": "server->client", "desc": "ping에 대한 응답", "example": {"event": "pong"}},
                    ],
                    "close_codes": {"4401": "Unauthorized (scope['user_id'] 없음)"},
                    "heartbeat_sec": 25,
                    "notes": [
                        "인증 미들웨어에서 JWT 검증 후 scope['user_id']를 설정해야 합니다.",
                        "인증 전달은 Subprotocol 또는 Authorization 헤더 중 한 가지를 권장합니다.",
                        "메시지 페이로드 스키마는 기능별로 확장될 수 있습니다.",
                    ],
                },
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="capabilities")
    def capabilities(self, request):
        data = {
            "websocket_url": "/ws/feed/",
            "auth": {"subprotocol": "<JWT_ACCESS_TOKEN>", "authorization_header": "Bearer <JWT_ACCESS_TOKEN>", "requires_user_id_scope": True},
            "events": [
                {
                    "type": "feed_update",
                    "direction": "server->client",
                    "desc": "새 피드 항목 브로드캐스트",
                    "example": {"event": "feed_update", "data": {"post_id": "uuid", "author_id": "uuid"}},
                },
                {"type": "ping", "direction": "client->server", "example": {"type": "ping"}},
                {"type": "pong", "direction": "server->client", "example": {"event": "pong"}},
            ],
            "close_codes": {"4401": "Unauthorized (scope['user_id'] missing)"},
            "heartbeat_sec": 25,
            "notes": ["클라이언트는 주기적으로 ping을 보내고, 서버는 pong으로 응답합니다.", "인증 미들웨어는 JWT를 검증하고 scope['user_id']를 설정해야 합니다."],
        }
        return Response(RealtimeCapabilitiesOut(data).data)
