import uuid

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


# Local/Test Only
class FeedEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    post_id = models.UUIDField(db_index=True)
    author_id = models.UUIDField(db_index=True)
    created_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "feed_entries"
        unique_together = ("user", "post_id")
        indexes = [models.Index(fields=["user", "-created_at"])]
