import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from assets.models import Asset, AssetStatus, AssetType
from comments.models import Comment
from posts.models import Post

pytestmark = pytest.mark.django_db


class TestCommentAssets:
    def setup_method(self):
        self.client = APIClient()
        U = get_user_model()
        self.author = U.objects.create()  # 댓글 작성자 == 첨부 수행자
        self.other = U.objects.create()  # 다른 사용자
        self.post = Post.objects.create(author=self.author, content="P")
        self.comment = Comment.objects.create(post=self.post, user=self.author, content="C")
        self.client.force_authenticate(self.author)

    def _ready_asset(self, owner):
        uid = uuid.uuid4()
        key = f"assets/image/2025/08/30/{owner.id}/{uid}.png"
        return Asset.objects.create(
            owner=owner,
            type=AssetType.IMAGE,
            content_type="image/png",
            size_bytes=1024,
            storage_key=key,
            public_url=f"http://minio/media/{key}",
            status=AssetStatus.READY,
        )

    def test_attach_list_detach_success(self):
        a = self._ready_asset(self.author)

        # attach
        url_attach = reverse("comment-assets", kwargs={"pk": str(self.comment.id)})
        res = self.client.post(url_attach, {"asset_ids": [str(a.id)]}, format="json")
        assert res.status_code == 201, res.content

        a.refresh_from_db()
        assert a.comment_id == self.comment.id

        # list
        res = self.client.get(url_attach)
        assert res.status_code == 200

        body = res.json()
        assert len(body) == 1 and body[0]["id"] == str(a.id)

        # detach
        url_detach = reverse("comment-detach-asset", kwargs={"pk": str(self.comment.id), "asset_id": str(a.id)})
        res = self.client.delete(url_detach)
        assert res.status_code == 204

        a.refresh_from_db()
        assert a.comment_id is None

    def test_attach_reject_not_owned_or_not_ready_or_already_attached(self):
        # 소유권 불일치
        foreign = self._ready_asset(self.other)
        # 상태 미준비
        pending_key = f"assets/image/2025/08/30/{self.author.id}/{uuid.uuid4()}.png"
        pending = Asset.objects.create(
            owner=self.author,
            type=AssetType.IMAGE,
            content_type="image/png",
            size_bytes=100,
            storage_key=pending_key,
            public_url=f"http://minio/media/{pending_key}",
            status=AssetStatus.PENDING,
        )

        # 이미 부착된 자산
        attached = self._ready_asset(self.author)
        attached.comment = self.comment
        attached.save(update_fields=["comment"])

        url = reverse("comment-assets", kwargs={"pk": str(self.comment.id)})
        res = self.client.post(url, {"asset_ids": [str(foreign.id), str(pending.id), str(attached.id)]}, format="json")
        assert res.status_code == 400

        errors = res.json().get("errors", {})
        assert str(foreign.id) in errors and "Not found or not owned" in errors[str(foreign.id)]
        assert str(pending.id) in errors and "READY" in errors[str(pending.id)]
        assert str(attached.id) in errors and "already attached" in errors[str(attached.id)]

    def test_attach_payload_validation(self):
        url = reverse("comment-assets", kwargs={"pk": str(self.comment.id)})
        res = self.client.post(url, {"asset_ids": []}, format="json")
        assert res.status_code == 400
        assert "asset_ids" in res.json()

    def test_detach_wrong_comment(self):
        a = self._ready_asset(self.author)

        # 다른 댓글에 먼저 부착
        other_comment = Comment.objects.create(post=self.post, user=self.author, content="X")
        a.comment = other_comment
        a.save(update_fields=["comment"])

        url = reverse("comment-detach-asset", kwargs={"pk": str(self.comment.id), "asset_id": str(a.id)})
        res = self.client.delete(url)
        assert res.status_code == 400
        assert "not attached to this comment" in res.content.decode().lower()
