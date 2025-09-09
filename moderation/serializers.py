from rest_framework import serializers

from .models import ModerationRule


class ModerationCheckIn(serializers.Serializer):
    content = serializers.CharField(max_length=10_000, allow_blank=False)


class ModerationCheckOut(serializers.Serializer):
    allowed = serializers.BooleanField()
    verdict = serializers.ChoiceField(choices=["allow", "flag", "block"])
    labels = serializers.ListField(child=serializers.CharField())
    score = serializers.FloatField()
    matches = serializers.ListField(child=serializers.DictField())


class ModerationRuleIn(serializers.ModelSerializer):
    class Meta:
        model = ModerationRule
        fields = ("rule_type", "pattern", "lang", "severity", "description")


class ModerationRuleOut(serializers.ModelSerializer):
    class Meta:
        model = ModerationRule
        fields = ("id", "rule_type", "pattern", "lang", "severity", "is_active", "description", "created_at", "updated_at")
