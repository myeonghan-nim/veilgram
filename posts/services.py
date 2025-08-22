from __future__ import annotations
from typing import Sequence

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from .models import Post
from assets.models import Asset, AssetStatus
from polls.models import Poll
from polls.services import create_poll as _create_poll


def _max_attachments() -> int:
    return int(getattr(settings, "POST_LIMITS", {}).get("MAX_ATTACHMENTS", 10))


@transaction.atomic
def create_post(*, author, content: str, asset_ids: Sequence, poll_id: str | None, poll_options: Sequence[str] | None, allow_multiple: bool = False) -> Post:
    # 1) 본문 검증(Serializer에서도 검증하지만 도메인 계약으로 한 번 더)
    content = (content or "").strip()
    if not content:
        raise ValidationError("Content must not be empty")

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

    # 5) 첨부 연결
    if asset_ids:
        Asset.objects.filter(id__in=asset_ids).update(post=post)

    return post
