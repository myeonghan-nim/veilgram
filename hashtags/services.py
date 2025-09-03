import re
import unicodedata
from typing import Iterable, List

from django.db import transaction

from .models import Hashtag, PostHashtag

MAX_HASHTAG_LEN = 64
_HASHTAG_RE = re.compile(r"(?<!\w)#([0-9A-Za-z_가-힣]+)", re.UNICODE)


def normalize_tag(raw: str) -> str:
    # 유니코드 정규화 + 소문자 + 길이 제한
    s = unicodedata.normalize("NFKC", raw).strip()
    return s.lower()[:MAX_HASHTAG_LEN]


def extract_hashtags(text: str) -> List[str]:
    # 본문에서 해시태그 토큰 추출 (중복/길이/정규화 처리, 순서 보존)
    if not text:
        return []
    toks = [_HASHTAG_RE.findall(text or "")][0]
    norm = [normalize_tag(t) for t in toks if t]
    # 빈/너무 짧은 토큰 제거
    norm = [t for t in norm if t and len(t) > 0]
    # 순서 보존 중복 제거
    seen = {}
    return [seen.setdefault(t, t) for t in norm if t not in seen]


@transaction.atomic
def ensure_hashtags(names: Iterable[str]) -> List[Hashtag]:
    # 정규화된 이름 리스트를 받아 DB 보장(get or create, bulk)
    names = list({normalize_tag(n) for n in names if n})
    if not names:
        return []
    existing = list(Hashtag.objects.filter(name__in=names))
    exist_set = {h.name for h in existing}
    missing = [Hashtag(name=n) for n in names if n not in exist_set]
    if missing:
        # 경합 시 Conflict 무시 (동시 생성) 후 재조회
        Hashtag.objects.bulk_create(missing, ignore_conflicts=True)
    return list(Hashtag.objects.filter(name__in=names))


@transaction.atomic
def attach_hashtags_to_post(post_id, content: str) -> List[str]:
    # 본문에서 해시태그를 추출해 PostHashtag를 연결하고 최종 태그 이름 리스트를 반환
    tags = extract_hashtags(content)
    if not tags:
        return []
    tag_rows = ensure_hashtags(tags)
    # 이미 연결된 것 제외하고 bulk_create
    existing = set(PostHashtag.objects.filter(post_id=post_id, hashtag__in=tag_rows).values_list("hashtag__name", flat=True))
    to_link = [PostHashtag(post_id=post_id, hashtag=h) for h in tag_rows if h.name not in existing]
    if to_link:
        PostHashtag.objects.bulk_create(to_link, ignore_conflicts=True)
    return [h.name for h in tag_rows]
