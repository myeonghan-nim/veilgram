import re
from dataclasses import dataclass
from typing import Dict, List

from django.core.cache import cache
from django.db import transaction

from .models import ModerationRule, RuleType

RULES_CACHE_KEY = "moderation:rules:v1"
RULES_CACHE_TTL_SECONDS = 300


@dataclass
class CheckResult:
    allowed: bool
    verdict: str  # 'allow'|'block'|'flag'
    labels: List[str]
    score: float
    matches: List[dict]


def _compile_regexes(patterns: List[str]) -> List[re.Pattern]:
    compiled = []
    for p in patterns:
        try:
            compiled.append(re.compile(p, re.IGNORECASE | re.UNICODE))
        except re.error:
            # 잘못된 정규식은 안전하게 skip (운영자가 수정)
            continue
    return compiled


def _to_snapshot(rows: List[ModerationRule]) -> Dict:
    deny_kw = [r.pattern for r in rows if r.rule_type == RuleType.DENY_KEYWORD and r.is_active]
    deny_rx = [r.pattern for r in rows if r.rule_type == RuleType.DENY_REGEX and r.is_active]
    allow_kw = [r.pattern for r in rows if r.rule_type == RuleType.ALLOW_KEYWORD and r.is_active]
    compiled = {"deny_keywords": deny_kw, "deny_regexes": deny_rx, "allow_keywords": allow_kw}
    return compiled


def load_rules_snapshot(force_reload: bool = False) -> Dict:
    # Redis에서 규칙 스냅샷을 가져오고, 없으면 DB에서 적재하여 캐시
    if not force_reload:
        cached = cache.get(RULES_CACHE_KEY)
        if cached:
            return cached

    rows = list(ModerationRule.objects.filter(is_active=True).order_by("severity"))
    snapshot = _to_snapshot(rows)
    cache.set(RULES_CACHE_KEY, snapshot, RULES_CACHE_TTL_SECONDS)
    return snapshot


def invalidate_rules_cache():
    cache.delete(RULES_CACHE_KEY)


def _keyword_hit(content: str, words: List[str]) -> List[str]:
    content_lc = content.lower()
    hits = []
    for w in words:
        if w.lower() in content_lc:
            hits.append(w)
    return hits


def _regex_hit(content: str, regexes: List[re.Pattern]) -> List[str]:
    hits = []
    for rx in regexes:
        if rx.search(content):
            hits.append(rx.pattern)
    return hits


def _simple_nsfw_score(text: str) -> float:
    # 외부 ML API 연동 지점, 실제 서비스에선 여기서 HTTP 호출(HF Inference, 내부 모델 등)을 수행하나 현재는 간단한 휴리스틱(금칙어 가중치)로 대체해 인터페이스만 동일하게 유지.
    snapshot = load_rules_snapshot()
    deny_kw = snapshot.get("deny_keywords", [])
    kw_hits = _keyword_hit(text, deny_kw)
    base = min(len(kw_hits) * 0.2, 1.0)
    return base


def check_text(content: str) -> CheckResult:
    # 텍스트 기반 모더레이션: 키워드/정규식 + (대체)NSFW 스코어링
    snapshot = load_rules_snapshot()
    deny_kw = snapshot.get("deny_keywords", [])
    deny_rx = _compile_regexes(snapshot.get("deny_regexes", []))

    kw_hits = _keyword_hit(content, deny_kw)
    rx_hits = _regex_hit(content, deny_rx)

    labels = []
    matches = []
    score = 0.0

    if kw_hits:
        labels.append("profanity")
        matches += [{"type": "keyword", "pattern": p, "severity": 1} for p in kw_hits]
        score += min(len(kw_hits) * 0.3, 1.0)

    if rx_hits:
        labels.append("pattern")
        matches += [{"type": "regex", "pattern": p, "severity": 2} for p in rx_hits]
        score += min(len(rx_hits) * 0.4, 1.0)

    nsfw = _simple_nsfw_score(content)
    if nsfw >= 0.5:
        labels.append("nsfw")
    score = min(score + nsfw, 1.0)

    # 정책: score >= 0.5 → block, 0.2~0.5 → flag, <0.2 → allow
    if score >= 0.5:
        verdict = "block"
        allowed = False
    elif score >= 0.2:
        verdict = "flag"
        allowed = True
    else:
        verdict = "allow"
        allowed = True

    return CheckResult(allowed=allowed, verdict=verdict, labels=sorted(set(labels)), score=score, matches=matches)


@transaction.atomic
def upsert_rule(rule_type: str, pattern: str, lang: str = "*", severity: int = 1, description: str = "") -> ModerationRule:
    obj, _ = ModerationRule.objects.update_or_create(
        rule_type=rule_type,
        pattern=pattern,
        lang=lang,
        defaults={
            "severity": severity,
            "is_active": True,
            "description": description,
        },
    )
    invalidate_rules_cache()
    return obj
