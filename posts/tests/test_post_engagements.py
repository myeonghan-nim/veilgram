import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from posts.models import Post, PostLike, Repost

User = get_user_model()


@pytest.mark.django_db
class TestPostLikes:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create()
        self.post = Post.objects.create(author=self.user, content="hello")
        self.base = f"/api/v1/posts/{self.post.id}"

    def test_like_success(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(f"{self.base}/like/")
        assert res.status_code == 204
        assert PostLike.objects.filter(user=self.user, post=self.post).count() == 1

    def test_like_duplicate(self):
        self.client.force_authenticate(self.user)
        self.client.post(f"{self.base}/like/")
        res = self.client.post(f"{self.base}/like/")
        assert res.status_code == 400
        assert res.json()["detail"] == "Already liked"

    def test_unlike_success(self):
        self.client.force_authenticate(self.user)
        self.client.post(f"{self.base}/like/")
        res = self.client.delete(f"{self.base}/like/")
        assert res.status_code == 204
        assert PostLike.objects.filter(user=self.user, post=self.post).count() == 0

    def test_unlike_not_liked(self):
        self.client.force_authenticate(self.user)
        res = self.client.delete(f"{self.base}/like/")
        assert res.status_code == 404
        assert res.json()["detail"] == "Not liked"

    def test_like_requires_auth(self):
        res = self.client.post(f"{self.base}/like/")
        assert res.status_code == 401


@pytest.mark.django_db
class TestBookmarks:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create()
        self.post = Post.objects.create(author=self.user, content="hello")
        self.base = f"/api/v1/posts/{self.post.id}"

    def test_bookmark_success_and_list(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(f"{self.base}/bookmark/")
        assert res.status_code == 204
        res = self.client.get("/api/v1/bookmarks/")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list) and len(data) == 1
        assert data[0]["post_id"] == str(self.post.id)

    def test_bookmark_duplicate(self):
        self.client.force_authenticate(self.user)
        self.client.post(f"{self.base}/bookmark/")
        res = self.client.post(f"{self.base}/bookmark/")
        assert res.status_code == 400
        assert res.json()["detail"] == "Already bookmarked"

    def test_unbookmark_success(self):
        self.client.force_authenticate(self.user)
        self.client.post(f"{self.base}/bookmark/")
        res = self.client.delete(f"{self.base}/bookmark/")
        assert res.status_code == 204

    def test_unbookmark_not_bookmarked(self):
        self.client.force_authenticate(self.user)
        res = self.client.delete(f"{self.base}/bookmark/")
        assert res.status_code == 404
        assert res.json()["detail"] == "Not bookmarked"

    def test_bookmark_requires_auth(self):
        res = self.client.post(f"{self.base}/bookmark/")
        assert res.status_code == 401


@pytest.mark.django_db
class TestRepost:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create()
        self.other = User.objects.create()
        self.post = Post.objects.create(author=self.other, content="original")
        self.base = f"/api/v1/posts/{self.post.id}"

    def test_repost_success(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(f"{self.base}/share/")
        assert res.status_code == 201
        body = res.json()
        assert set(body.keys()) == {"id", "original_post_id", "sharer_id", "created_at"}
        assert body["original_post_id"] == str(self.post.id)
        assert body["sharer_id"] == str(self.user.id)
        assert Repost.objects.filter(user=self.user, original_post=self.post).count() == 1

    def test_repost_duplicate(self):
        self.client.force_authenticate(self.user)
        self.client.post(f"{self.base}/share/")
        res = self.client.post(f"{self.base}/share/")
        assert res.status_code == 400
        assert res.json()["detail"] == "Already reposted"

    def test_repost_requires_auth(self):
        res = self.client.post(f"{self.base}/share/")
        assert res.status_code == 401
