from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from .models import Poll, PollOption, Vote

MIN_OPTIONS = 2
MAX_OPTIONS = 5


@dataclass(frozen=True)
class CreatedPoll:
    poll: Poll
    options: list[PollOption]


def create_poll(*, owner, option_texts: Sequence[str], allow_multiple: bool = False) -> CreatedPoll:
    texts = [t.strip() for t in option_texts if t and t.strip()]
    # 옵션 2..5개, 텍스트 중복 금지, 트랜잭션으로 일관성 보장
    if len(texts) < MIN_OPTIONS:
        raise ValidationError("Poll must have at least 2 options")
    if len(texts) > MAX_OPTIONS:
        raise ValidationError("Poll can have at most 5 options")
    if len(set(map(str.lower, texts))) != len(texts):
        raise ValidationError("Duplicate option text")

    with transaction.atomic():
        poll = Poll.objects.create(owner=owner, allow_multiple=allow_multiple)
        options = []
        for i, text in enumerate(texts):
            options.append(PollOption.objects.create(poll=poll, text=text, position=i))
        return CreatedPoll(poll=poll, options=options)


@dataclass(frozen=True)
class VoteResult:
    poll: Poll
    options: list[PollOption]
    my_option_id: str | None


def _ensure_option_in_poll(poll: Poll, option: PollOption):
    if option.poll_id != poll.id:
        raise ValidationError("Option does not belong to poll")


@transaction.atomic
def cast_vote(*, poll: Poll, voter, option: PollOption) -> VoteResult:
    _ensure_option_in_poll(poll, option)

    # 단일 선택을 가정하며 기존 표가 있으면 다른 옵션으로 '이동' 처리(이전 옵션 -1, 새 옵션 +1)
    existing = Vote.objects.select_for_update().filter(voter=voter, poll=poll).first()
    if existing is None:
        # 신규 투표
        Vote.objects.create(voter=voter, poll=poll, option=option)
        PollOption.objects.filter(id=option.id).update(vote_count=F("vote_count") + 1)
        my_option_id = str(option.id)
    elif existing.option_id == option.id:
        # 동일 옵션 재투표: idempotent
        my_option_id = str(option.id)
    else:
        # 옵션 이동
        old_option_id = existing.option_id
        Vote.objects.filter(pk=existing.pk).update(option_id=option.id)
        PollOption.objects.filter(id=old_option_id).update(vote_count=F("vote_count") - 1)
        PollOption.objects.filter(id=option.id).update(vote_count=F("vote_count") + 1)
        my_option_id = str(option.id)

    options = list(PollOption.objects.filter(poll=poll).order_by("position"))
    return VoteResult(poll=poll, options=options, my_option_id=my_option_id)


@transaction.atomic
def retract_vote(*, poll: Poll, voter) -> VoteResult:
    # 사용자의 표를 철회하며 존재하지 않으면 idempotent.
    existing = Vote.objects.select_for_update().filter(voter=voter, poll=poll).first()
    if existing:
        PollOption.objects.filter(id=existing.option_id).update(vote_count=F("vote_count") - 1)
        existing.delete()
    options = list(PollOption.objects.filter(poll=poll).order_by("position"))
    return VoteResult(poll=poll, options=options, my_option_id=None)
