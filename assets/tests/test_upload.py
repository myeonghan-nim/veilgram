import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from assets.models import Asset, AssetStatus

pytestmark = pytest.mark.django_db

# ----- Stub and fixtures -----


# MinIO/S3를 직접 호출하지 않도록 presign/head_object만 흉내내어 테스트마다 content_length를 바꿔 업로드 사이즈 불일치 경로를 검증
class _StubS3Client:
    def __init__(self):
        self.content_length = 1234

    def generate_presigned_url(self, op, Params, ExpiresIn, HttpMethod):
        key = Params["Key"]
        return f"http://minio:9000/presign/{key}?expires={ExpiresIn}"

    def head_object(self, Bucket, Key):
        return {"ContentLength": self.content_length, "ETag": '"stub-etag"'}


@pytest.fixture(autouse=True)
def s3_stub(monkeypatch):
    # assets.s3 모듈이 내부적으로 사용하는 boto3.client()를 스텁으로 대체하여 각 테스트에서 s3_stub.content_length를 변경
    import assets.s3 as s3

    stub = _StubS3Client()

    class _StubBoto3:
        def client(self, *_args, **_kwargs):
            return stub

    monkeypatch.setattr(s3, "boto3", _StubBoto3())
    return stub


@pytest.fixture
def user():
    U = get_user_model()
    return U.objects.create(id=uuid.uuid4())


@pytest.fixture
def auth_client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def anon_client():
    return APIClient()


# ----- Tests: /prepare -----


class TestAssetUploadPrepare:
    def test_image_ok(self, auth_client):
        url = reverse("assets-uploads-prepare")
        payload = {"type": "image", "content_type": "image/jpeg", "size_bytes": 1234, "ext": "jpg"}
        res = auth_client.post(url, data=payload, format="json")
        assert res.status_code == 201

        body = res.json()
        assert body["asset_id"]
        assert body["upload_url"].startswith("http://minio:9000/presign/")
        assert body["method"] == "PUT"
        assert body["headers"]["Content-Type"] == "image/jpeg"
        assert body["public_url"].endswith(".jpg")

        a = Asset.objects.get(id=body["asset_id"])
        assert a.status == AssetStatus.PENDING
        assert a.storage_key.startswith("assets/image/")

    def test_reject_large_video(self, auth_client, settings):
        url = reverse("assets-uploads-prepare")
        payload = {"type": "video", "content_type": "video/mp4", "size_bytes": 500 * 1024 * 1024, "ext": "mp4"}
        res = auth_client.post(url, data=payload, format="json")
        assert res.status_code == 400
        assert b"Video too large" in res.content

    def test_reject_unsupported_mime(self, auth_client):
        url = reverse("assets-uploads-prepare")
        payload = {"type": "image", "content_type": "image/gif", "size_bytes": 1000, "ext": "gif"}
        res = auth_client.post(url, data=payload, format="json")
        assert res.status_code == 400
        assert b"Unsupported image content_type" in res.content

    def test_requires_authentication(self, anon_client):
        url = reverse("assets-uploads-prepare")
        payload = {"type": "image", "content_type": "image/jpeg", "size_bytes": 100, "ext": "jpg"}
        res = anon_client.post(url, data=payload, format="json")
        assert res.status_code in (401, 403)


# ---------- Test: /complete ----------


class TestAssetUploadComplete:
    def _prepare_asset(self, auth_client, *, size=1234, ext="png", content_type="image/png"):
        prep = auth_client.post(reverse("assets-uploads-prepare"), data={"type": "image", "content_type": content_type, "size_bytes": size, "ext": ext}, format="json").json()
        return prep["asset_id"]

    def test_marks_ready_on_success(self, auth_client):
        asset_id = self._prepare_asset(auth_client, size=1234, ext="png", content_type="image/png")
        res = auth_client.post(reverse("assets-uploads-complete"), data={"asset_id": asset_id}, format="json")
        assert res.status_code == 200

        body = res.json()
        assert body["status"] == "READY"
        assert body["public_url"].endswith(".png")

        a = Asset.objects.get(id=asset_id)
        assert a.status == AssetStatus.READY

    def test_size_mismatch_sets_failed(self, auth_client, s3_stub):
        # 준비 단계에서 5555 바이트라고 저장해두고
        asset_id = self._prepare_asset(auth_client, size=5555, ext="jpg", content_type="image/jpeg")

        # S3 HEAD는 다른 사이즈(1234)로 응답하도록 스텁 설정 (기본값 1234 유지)
        # s3_stub.content_length = 1234 # (기본값 그대로)
        res = auth_client.post(reverse("assets-uploads-complete"), data={"asset_id": asset_id}, format="json")
        assert res.status_code == 400
        assert b"size mismatch" in res.content

        a = Asset.objects.get(id=asset_id)
        assert a.status == AssetStatus.FAILED
