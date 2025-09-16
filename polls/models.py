import uuid

from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint


class Poll(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_polls", db_index=True)
    allow_multiple = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "polls"
        ordering = ("-created_at",)

    def __str__(self):
        return f"Poll<{self.id}> owner={self.owner_id}"


class PollOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options", db_index=True)
    text = models.CharField(max_length=100)
    position = models.PositiveSmallIntegerField()  # 0..4 순서 유지
    vote_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "poll_options"
        ordering = ("position", "id")
        constraints = [
            UniqueConstraint(fields=["poll", "position"], name="uq_poll_option_position"),
            UniqueConstraint(fields=["poll", "text"], name="uq_poll_option_text"),
        ]

    def __str__(self):
        return f"Option<{self.id}> poll={self.poll_id} pos={self.position}"


# single choice일 때 (voter, poll) 유니크로 1표만 허용하며 다중 선택 확장 시 (voter, poll, option) 유니크로 전환하고 allowed_max 등 정책이 필요
class Vote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="votes", db_index=True)
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes", db_index=True)
    option = models.ForeignKey(PollOption, on_delete=models.CASCADE, related_name="votes", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "poll_votes"
        # 데이터 무결성: option은 반드시 같은 poll에 속해야 함(애플리케이션 레벨에서 강제)
        constraints = [
            UniqueConstraint(fields=["voter", "poll"], name="uq_vote_voter_poll"),
        ]
        indexes = [
            models.Index(fields=["poll"], name="idx_vote_poll"),
            models.Index(fields=["option"], name="idx_vote_option"),
        ]

    def __str__(self):
        return f"Vote<{self.id}> voter={self.voter_id} poll={self.poll_id} option={self.option_id}"
