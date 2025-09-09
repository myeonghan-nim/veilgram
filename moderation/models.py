import uuid

from django.db import models


class RuleType(models.TextChoices):
    DENY_KEYWORD = "deny_keyword", "Deny keyword"
    DENY_REGEX = "deny_regex", "Deny regex"
    ALLOW_KEYWORD = "allow_keyword", "Allow keyword"  # 화이트리스트(예외) 확장용


class ModerationRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule_type = models.CharField(max_length=32, choices=RuleType.choices)
    pattern = models.CharField(max_length=255)  # 키워드 또는 정규식 패턴
    lang = models.CharField(max_length=8, default="*")  # 'ko', 'en', '*' 등
    severity = models.PositiveSmallIntegerField(default=1)  # 1~5
    is_active = models.BooleanField(default=True)
    description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "moderation_rules"
        indexes = [models.Index(fields=["rule_type", "lang", "is_active"])]
        constraints = [models.UniqueConstraint(fields=["rule_type", "pattern", "lang"], name="uniq_rule_pattern_per_lang")]


class ModerationReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_type = models.CharField(max_length=32)  # 'post' or 'comment'
    target_id = models.UUIDField()
    verdict = models.CharField(max_length=16)  # 'allow'|'block'|'flag'
    labels = models.JSONField(default=list)  # ['profanity', 'nsfw', ...]
    score = models.FloatField(default=0.0)  # 종합 스코어(간단 가중 합)
    matched = models.JSONField(default=list)  # 매칭된 규칙 목록 [{id, pattern, type, severity}]
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "moderation_reports"
        indexes = [models.Index(fields=["target_type", "target_id"])]
