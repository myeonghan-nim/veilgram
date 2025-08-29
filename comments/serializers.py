from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField(read_only=True)
    content = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        error_messages={
            "blank": "Content must not be empty.",
            "required": "Content must not be empty.",
        },
    )

    class Meta:
        model = Comment
        fields = ["id", "post", "user", "author", "parent", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "created_at", "updated_at", "post"]

    def _get_post_from_context(self):
        # 1) 명시적으로 주입된 post
        post = self.context.get("post")
        if post is not None:
            return post

        # 2) view.kwargs에서 post_id 추출
        view = self.context.get("view")
        if view:
            kwargs = getattr(view, "kwargs", {}) or {}
            post_id = kwargs.get("post_id")
            if post_id:
                # 지연 임포트(순환 참조 방지)
                from posts.models import Post

                try:
                    return Post.objects.get(id=post_id)
                except Post.DoesNotExist:
                    raise serializers.ValidationError("Post not found.")
        return None

    def get_author(self, obj):
        # 최소한의 작성자 정보 반환(익명성 전제에서 과도한 정보 노출 방지), 필요 시 profiles 연동하여 닉네임 등 추가 가능
        profile = getattr(obj.user, "profile", None) or getattr(obj.user, "profiles", None)
        nickname = getattr(profile, "nickname", None) if profile else None
        return {"id": str(obj.user_id), "nickname": nickname}

    def validate(self, attrs):
        # 업데이트라면 인스턴스의 post, 없으면 컨텍스트/URL에서 복구
        post = self.context.get("post") or (self.instance.post if self.instance else None)
        if post is None:
            post = self._get_post_from_context()
        if post is None:
            # 생성/검증 모두에서 일관적으로 post를 찾지 못한 경우
            raise serializers.ValidationError("Post context missing.")

        # parent 비교(업데이트 시 전달 없으면 기존 parent와 비교)
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if parent and parent.post_id != post.id:
            raise serializers.ValidationError({"parent": "Parent comment must be on the same post."})

        # PATCH에서는 content가 없을 수 있음 → 있을 때만 공백 체크
        if "content" in attrs:
            content = (attrs.get("content") or "").strip()
            if not content:
                raise serializers.ValidationError({"content": "Content must not be empty."})

        # 검증에 사용한 post를 create에서 재사용할 수 있게 저장(옵션)
        self._validated_post = post
        return attrs

    def create(self, validated_data):
        # validate에서 확보한 post 또는 컨텍스트/URL로 복구
        post = getattr(self, "_validated_post", None) or self.context.get("post")
        if post is None:
            post = self._get_post_from_context()
        if post is None:
            raise serializers.ValidationError("Post context missing.")

        user = self.context["request"].user
        validated_data["post"] = post
        validated_data["user"] = user

        try:
            instance = Comment.objects.create(**validated_data)
            instance.full_clean()
            return instance
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)
