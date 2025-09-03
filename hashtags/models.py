import uuid

from django.db import models
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower


class Hashtag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # 저장 시 소문자(NFKC 정규화 후)만 넣는 것을 권장
    name = models.CharField(max_length=64, unique=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hashtags"
        constraints = [
            # name 대소문자 무시 유니크 (PostgreSQL)
            UniqueConstraint(Lower("name"), name="uniq_hashtag_name_lower"),
        ]

    def __str__(self):
        return f"#{self.name}"


class PostHashtag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE, related_name="post_hashtags", db_index=True)
    hashtag = models.ForeignKey(Hashtag, on_delete=models.CASCADE, related_name="post_hashtags", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "post_hashtags"
        constraints = [
            UniqueConstraint(fields=["post", "hashtag"], name="uniq_post_hashtag"),
        ]
        indexes = [
            models.Index(fields=["hashtag", "created_at"], name="idx_hashtag_created"),
        ]
