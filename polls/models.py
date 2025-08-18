import uuid

from django.db import models


class Poll(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "polls"
        ordering = ("-created_at",)

    def __str__(self):
        return f"Poll<{self.id}>"
