from rest_framework import serializers

from polls.serializers import PollCreateIn


class PostCreateIn(serializers.Serializer):
    # allow_blank=True 로 필드 단계의 기본 블랭크 에러를 우회하고, 아래 validate_content에서 통일된 문구로 검증
    content = serializers.CharField(max_length=5000, allow_blank=True, trim_whitespace=True)
    asset_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)
    poll_id = serializers.UUIDField(required=False, allow_null=True)
    poll = PollCreateIn(required=False)  # {"options":[...], "allow_multiple": false}

    def validate_content(self, value: str):
        if not value or not value.strip():
            raise serializers.ValidationError("Content must not be empty")
        return value.strip()

    def validate(self, data):
        poll_id = data.get("poll_id")
        poll = data.get("poll")
        if poll_id and poll:
            raise serializers.ValidationError("Provide either poll_id or poll, not both")

        ids = data.get("asset_ids") or []
        # 중복 제거는 서비스에서 하지만 입력도 사전 방어
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Duplicate asset_ids")
        return data


class PostOut(serializers.Serializer):
    id = serializers.UUIDField()
    author = serializers.UUIDField(source="author_id")
    created_at = serializers.DateTimeField()
