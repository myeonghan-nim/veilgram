import uuid

from django.conf import settings
from django.db import models


class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts", db_index=True)
    content = models.TextField()
    poll = models.ForeignKey("polls.Poll", on_delete=models.SET_NULL, null=True, blank=True, related_name="posts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "posts"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["author", "-created_at"], name="idx_post_author_created"),
        ]

    def __str__(self):
        return f"Post<{self.id}> by {self.author_id}"


class PostLike(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "post_likes"
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="uniq_post_like_user"),
        ]
        indexes = [
            models.Index(fields=["post", "user"]),
            models.Index(fields=["user", "created_at"]),
        ]


class Bookmark(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE, related_name="bookmarks")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bookmarks"
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="uniq_bookmark_user_post"),
        ]
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]


class Repost(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reposts")
    original_post = models.ForeignKey("posts.Post", on_delete=models.CASCADE, related_name="reposts")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reposts"
        constraints = [
            models.UniqueConstraint(fields=["user", "original_post"], name="uniq_repost_user_original"),
        ]
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]
