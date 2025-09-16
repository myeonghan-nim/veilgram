import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def make_user():
    U = get_user_model()
    return U.objects.create()


class TestUserReportAPI:
    def setup_method(self):
        self.client = APIClient()
        self.reporter = make_user()
        self.target = make_user()
        self.url = f"/api/v1/reports/users/{self.target.id}/"

    def test_requires_auth(self):
        res = self.client.post(self.url, data={"reasons": ["spam"]}, format="json")
        assert res.status_code in (401, 403)

    def test_report_user_success_and_block(self):
        self.client.force_authenticate(self.reporter)
        res = self.client.post(self.url, data={"reasons": ["abuse", "spam"], "block": True}, format="json")
        assert res.status_code == 201

        body = res.json()
        assert "report_id" in body and "created_at" in body

        # 차단이 생성되었는지 점검
        from relations.models import Block

        assert Block.objects.filter(user_id=self.reporter.id, blocked_user_id=self.target.id).exists()

    def test_report_user_duplicate_rejected(self):
        self.client.force_authenticate(self.reporter)
        first = self.client.post(self.url, data={"reasons": ["spam"]}, format="json")
        assert first.status_code == 201

        dup = self.client.post(self.url, data={"reasons": ["spam"]}, format="json")
        assert dup.status_code == 400

    def test_cannot_report_self(self):
        self.client.force_authenticate(self.reporter)
        url = f"/api/v1/reports/users/{self.reporter.id}/"
        res = self.client.post(url, data={"reasons": ["weird"]}, format="json")
        assert res.status_code == 400


class TestPostReportAPI:
    def setup_method(self):
        self.client = APIClient()
        self.reporter = make_user()
        self.author = make_user()
        # 최소 Post 생성 (이미 8~12일차 구현 가정)
        from posts.models import Post

        self.post = Post.objects.create(author_id=self.author.id, content="hello")
        self.url = f"/api/v1/reports/posts/{self.post.id}/"

    def test_report_post_success(self):
        self.client.force_authenticate(self.reporter)
        res = self.client.post(self.url, data={"reasons": ["nsfw"], "block": True}, format="json")
        assert res.status_code == 201

        from relations.models import Block

        assert Block.objects.filter(user_id=self.reporter.id, blocked_user_id=self.author.id).exists()

    def test_cannot_report_own_post(self):
        self.client.force_authenticate(self.author)
        res = self.client.post(self.url, data={"reasons": ["spam"]}, format="json")
        assert res.status_code == 400

    def test_duplicate_rejected(self):
        self.client.force_authenticate(self.reporter)
        a = self.client.post(self.url, data={"reasons": ["spam"]}, format="json")
        b = self.client.post(self.url, data={"reasons": ["spam"]}, format="json")
        assert a.status_code == 201
        assert b.status_code == 400


class TestCommentReportAPI:
    def setup_method(self):
        self.client = APIClient()
        self.reporter = make_user()
        self.author = make_user()
        from comments.models import Comment
        from posts.models import Post

        self.post = Post.objects.create(author_id=self.author.id, content="post")
        self.comment = Comment.objects.create(post_id=self.post.id, user_id=self.author.id, content="c1")
        self.url = f"/api/v1/reports/comments/{self.comment.id}/"

    def test_report_comment_success(self):
        self.client.force_authenticate(self.reporter)
        res = self.client.post(self.url, data={"reasons": ["harassment"], "block": True}, format="json")
        assert res.status_code == 201

        from relations.models import Block

        assert Block.objects.filter(user_id=self.reporter.id, blocked_user_id=self.author.id).exists()

    def test_cannot_report_own_comment(self):
        self.client.force_authenticate(self.author)
        res = self.client.post(self.url, data={"reasons": ["spam"]}, format="json")
        assert res.status_code == 400

    def test_comment_not_found(self):
        self.client.force_authenticate(self.reporter)
        bad_url = f"/api/v1/reports/comments/{uuid.uuid4()}/"
        res = self.client.post(bad_url, data={"reasons": ["x"]}, format="json")
        # services 레벨에서 400(ValidationError)로 일관 처리
        assert res.status_code in (400, 404)
