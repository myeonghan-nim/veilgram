from rest_framework import serializers

from .models import Poll, PollOption


class PollOptionOut(serializers.ModelSerializer):
    class Meta:
        model = PollOption
        fields = ["id", "text", "position", "vote_count"]


class PollOut(serializers.ModelSerializer):
    options = PollOptionOut(many=True, read_only=True)
    owner = serializers.UUIDField(source="owner_id", read_only=True)

    class Meta:
        model = Poll
        fields = ["id", "owner", "allow_multiple", "created_at", "options"]


class PollCreateIn(serializers.Serializer):
    options = serializers.ListField(child=serializers.CharField(max_length=100), min_length=2, max_length=5, allow_empty=False)
    allow_multiple = serializers.BooleanField(required=False, default=False)

    def validate_options(self, options):
        # 공백 트리밍 후 빈 문자열 제거
        cleaned = [o.strip() for o in options if o and o.strip()]
        # 개수 제한은 필드 정의(min/max_length)로 이미 1차 검증됨
        lower = [o.lower() for o in cleaned]
        if len(set(lower)) != len(lower):
            # 테스트가 기대하는 정확한 문구로 고정
            raise serializers.ValidationError("Duplicate option text")
        return cleaned


class VoteIn(serializers.Serializer):
    option_id = serializers.UUIDField()


class VoteOut(serializers.Serializer):
    poll = PollOut()
    my_option_id = serializers.UUIDField(allow_null=True)
