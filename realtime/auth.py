import urllib.parse
from typing import Optional

from channels.middleware import BaseMiddleware
from django.conf import settings
from rest_framework_simplejwt.backends import TokenBackend


class JWTAuthMiddleware(BaseMiddleware):
    # QueryString ?token=..., scope["subprotocols"], 또는 Sec-WebSocket-Protocol 헤더에서 JWT를 추출해 검증 후 scope["user_id"]를 세팅한다.

    def _extract_token(self, scope) -> Optional[str]:
        # 1) QueryString
        qs = scope.get("query_string", b"").decode()
        if qs:
            params = urllib.parse.parse_qs(qs)
            if "token" in params and params["token"]:
                return params["token"][0]

        # 2) ASGI scope subprotocols (WebsocketCommunicator/subprotocols, 브라우저도 가능)
        subprotocols = scope.get("subprotocols") or []
        for proto in subprotocols:
            if not proto:
                continue
            p = proto.strip()
            if not p:
                continue
            if p.lower().startswith("bearer "):
                return p[7:].strip()
            # 토큰만 단독으로 실어 보내는 경우
            return p

        # 3) Sec-WebSocket-Protocol 헤더 (ASGI 서버에 따라 들어올 수 있음)
        headers = dict(scope.get("headers", []))
        swp = headers.get(b"sec-websocket-protocol")
        if swp:
            p = swp.decode().split(",")[0].strip()
            if p.lower().startswith("bearer "):
                p = p[7:].strip()
            return p

        return None

    async def __call__(self, scope, receive, send):
        token = self._extract_token(scope)
        if token:
            backend = TokenBackend(
                algorithm=settings.SIMPLE_JWT.get("ALGORITHM", "HS256"),
                signing_key=settings.SIMPLE_JWT.get("SIGNING_KEY", settings.SECRET_KEY),
                verifying_key=settings.SIMPLE_JWT.get("VERIFYING_KEY", None),
            )
            try:
                payload = backend.decode(token, verify=True)
                user_id = payload.get("sub") or payload.get("user_id")
                scope["user_id"] = str(user_id) if user_id else None
            except Exception:
                scope["user_id"] = None
        else:
            scope["user_id"] = None

        return await super().__call__(scope, receive, send)
