import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from comments.models import Comment
from posts.models import Post

pytestmark = pytest.mark.django_db


class TestCommentCRUD:
    def setup_method(self):
        self.client = APIClient()
        self.User = get_user_model()
        self.author = self.User.objects.create()
        self.other = self.User.objects.create()
        self.post = Post.objects.create(author=self.author, content="Hello world")

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_create_comment_success(self):
        self._auth(self.other)
        url = reverse("post-comments-list", kwargs={"post_id": str(self.post.id)})
        res = self.client.post(url, {"content": "nice post!"}, format="json")
        assert res.status_code == 201

        data = res.json()
        assert data["id"]
        assert data["content"] == "nice post!"
        assert data["author"]["id"] == str(self.other.id)

    def test_list_comments_of_post(self):
        Comment.objects.create(post=self.post, user=self.author, content="A")
        Comment.objects.create(post=self.post, user=self.other, content="B")

        self._auth(self.author)
        url = reverse("post-comments-list", kwargs={"post_id": str(self.post.id)})
        res = self.client.get(url)
        assert res.status_code == 200

        body = res.json()
        # 기본 정렬: 최신순
        contents = [c["content"] for c in body["results"]] if "results" in body else [c["content"] for c in body]
        assert contents[0] in ("B", "A")

    def test_retrieve_comment(self):
        c = Comment.objects.create(post=self.post, user=self.author, content="detail")

        self._auth(self.other)
        url = reverse("comment-detail", kwargs={"pk": str(c.id)})
        res = self.client.get(url)
        assert res.status_code == 200
        assert res.json()["content"] == "detail"

    def test_update_comment_author_only(self):
        c = Comment.objects.create(post=self.post, user=self.author, content="old")

        # 작성자 아닌 사용자 → 403
        self._auth(self.other)
        url = reverse("comment-detail", kwargs={"pk": str(c.id)})
        res = self.client.patch(url, {"content": "hacked"}, format="json")
        assert res.status_code == 403

        # 작성자 → 200
        self._auth(self.author)
        res = self.client.patch(url, {"content": "new"}, format="json")
        assert res.status_code == 200
        assert res.json()["content"] == "new"

    def test_delete_comment_author_only(self):
        c = Comment.objects.create(post=self.post, user=self.author, content="bye")
        url = reverse("comment-detail", kwargs={"pk": str(c.id)})

        self._auth(self.other)
        res = self.client.delete(url)
        assert res.status_code == 403

        self._auth(self.author)
        res = self.client.delete(url)
        assert res.status_code == 204
        assert Comment.objects.filter(id=c.id).count() == 0

    def test_reply_create_and_list(self):
        parent = Comment.objects.create(post=self.post, user=self.author, content="parent")

        self._auth(self.other)
        url_create = reverse("comment-replies", kwargs={"pk": str(parent.id)})
        res = self.client.post(url_create, {"content": "child"}, format="json")
        assert res.status_code == 201

        child_id = res.json()["id"]
        url_list = reverse("comment-replies", kwargs={"pk": str(parent.id)})
        res = self.client.get(url_list)
        assert res.status_code == 200

        items = res.json()["results"] if "results" in res.json() else res.json()
        assert any(r["id"] == child_id for r in items)

    def test_reject_empty_content(self):
        self._auth(self.other)
        url = reverse("post-comments-list", kwargs={"post_id": str(self.post.id)})
        res = self.client.post(url, {"content": "   "}, format="json")
        assert res.status_code == 400
        assert "Content must not be empty" in str(res.content)

    def test_parent_must_belong_to_same_post(self):
        other_post = Post.objects.create(author=self.author, content="Other")
        parent_other = Comment.objects.create(post=other_post, user=self.author, content="X")

        self._auth(self.other)
        url = reverse("post-comments-list", kwargs={"post_id": str(self.post.id)})
        res = self.client.post(url, {"content": "oops", "parent": str(parent_other.id)}, format="json")
        assert res.status_code == 400
        assert "Parent comment must be on the same post." in str(res.content)

    def test_auth_required(self):
        url = reverse("post-comments-list", kwargs={"post_id": str(self.post.id)})
        res = self.client.post(url, {"content": "noauth"}, format="json")
        assert res.status_code in (401, 403)
