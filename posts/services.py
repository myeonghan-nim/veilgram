from __future__ import annotations
from typing import Sequence

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Post
from assets.models import Asset, AssetStatus
from hashtags.services import attach_hashtags_to_post
from moderation.services import check_text
from polls.models import Poll
from polls.services import create_poll as _create_poll
from search.services import index_post


def _max_attachments() -> int:
    return int(getattr(settings, "POST_LIMITS", {}).get("MAX_ATTACHMENTS", 10))


@transaction.atomic
def create_post(*, author, content: str, asset_ids: Sequence, poll_id: str | None, poll_options: Sequence[str] | None, allow_multiple: bool = False) -> Post:
    # 1) 본문 검증(Serializer에서도 검증하지만 도메인 계약으로 한 번 더)
    content = (content or "").strip()
    if not content:
        raise ValidationError("Content must not be empty")

    # 1.5) 모더레이션 사전 검증
    result = check_text(content)
    if not result.allowed and result.verdict == "block":
        # 테스트/일관성을 위해 기존 스타일대로 문자열 메시지 사용
        # (필드 지정이 필요하면 {"content": ["Content violates policies"]} 로도 변경 가능)
        raise ValidationError("Content violates policies")

    # 2) Poll 결정(둘 다 주면 오류)
    if poll_id and poll_options:
        raise ValidationError("Provide either poll_id or poll(options), not both")

    poll_obj = None
    if poll_id:
        poll_obj = Poll.objects.select_for_update().filter(id=poll_id, owner=author).first()
        if poll_obj is None:
            raise ValidationError("Invalid poll_id")
        # 이미 다른 포스트에 연결된 Poll 금지
        if Post.objects.filter(poll=poll_obj).exists():
            raise ValidationError("Poll is already attached to a post")
    elif poll_options:
        # 옵션으로 즉석 생성
        created = _create_poll(owner=author, option_texts=poll_options, allow_multiple=allow_multiple)
        poll_obj = created.poll

    # 3) Asset 확보
    asset_ids = list(dict.fromkeys(asset_ids or []))  # unique 유지 + 순서 보존
    if len(asset_ids) > _max_attachments():
        raise ValidationError(f"Too many attachments (>{_max_attachments()})")

    # 잠금 + 조건 일치하는 것만
    locked_assets = Asset.objects.select_for_update().filter(id__in=asset_ids, owner=author, status=AssetStatus.READY, post__isnull=True)

    if len(asset_ids) != locked_assets.count():
        # 어떤 자산은 소유자 불일치/미완료/이미 연결됨
        raise ValidationError("Invalid attachments detected")

    # 4) Post 생성
    post = Post.objects.create(author=author, content=content, poll=poll_obj)

    # 5) Hashtag 자동 추출 및 연결
    tags = attach_hashtags_to_post(post.id, content)

    # 6) 검색 색인
    index_post(
        post_id=post.id,
        author_id=post.author_id,
        author_nickname=getattr(getattr(post, "author", None), "nickname", "") or "",
        content=post.content,
        hashtags=tags,
        created_at=post.created_at,
        like_count=getattr(post, "like_count", 0),
    )

    # 7) 첨부 연결
    if asset_ids:
        Asset.objects.filter(id__in=asset_ids).update(post=post)

    return post
