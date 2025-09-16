from typing import Dict, Iterable, Protocol, Tuple


class PushProvider(Protocol):
    def send_multicast(self, platform: str, tokens: Iterable[str], title: str, body: str, data: Dict) -> Tuple[int, int]:
        """returns (success_count, failure_count)"""


def get_provider() -> PushProvider:
    # settings 또는 환경변수로 선택 (default: Dummy)
    from django.conf import settings

    name = getattr(settings, "PUSH_PROVIDER", "dummy")

    if name == "fcm":
        return FcmProvider()
    elif name == "apns":
        return ApnsProvider()
    else:
        return DummyProvider()


class DummyProvider:
    def send_multicast(self, platform, tokens, title, body, data):
        # 테스트/개발용: 아무것도 보내지 않고 성공 카운트만 반환
        tokens = list(tokens)
        return len(tokens), 0


class FcmProvider:
    def __init__(self):
        try:
            from firebase_admin import initialize_app, messaging  # type: ignore

            self.messaging = messaging
            try:
                initialize_app()
            except ValueError:
                # 이미 초기화된 경우
                pass
        except Exception as e:
            raise RuntimeError("FCM provider requires firebase_admin") from e

    def send_multicast(self, platform, tokens, title, body, data):
        tokens = list(tokens)
        if not tokens:
            return 0, 0
        message = self.messaging.MulticastMessage(notification=self.messaging.Notification(title=title, body=body), data={k: str(v) for k, v in data.items()}, tokens=tokens)
        resp = self.messaging.send_multicast(message, dry_run=False)
        return resp.success_count, resp.failure_count


class ApnsProvider:
    def __init__(self):
        try:
            from apns2.client import APNsClient  # type: ignore
            from apns2.payload import Payload  # type: ignore

            self.APNsClient = APNsClient
            self.Payload = Payload
        except Exception as e:
            raise RuntimeError("APNs provider requires apns2") from e

    def send_multicast(self, platform, tokens, title, body, data):
        # 실제 APNs 멀티캐스트는 반복 전송로 구현 (간소화)
        tokens = list(tokens)
        if not tokens:
            return 0, 0
        client = self.APNsClient(credentials="path/to/cert_or_token", use_sandbox=False)
        payload = self.Payload(alert={"title": title, "body": body}, custom=data)
        ok, fail = 0, 0
        for t in tokens:
            try:
                client.send_notification(t, payload, topic="com.example.app")
                ok += 1
            except Exception:
                fail += 1
        return ok, fail
