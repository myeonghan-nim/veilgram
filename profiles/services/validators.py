import re
import unicodedata
from typing import Iterable, Set

from django.core.cache import cache
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

FORBIDDEN_NICKNAMES_CACHE_KEY = "filter:forbidden_nicknames"
FORBIDDEN_NICKNAMES_TTL = 300

NICKNAME_MIN = 2
NICKNAME_MAX = 20
NICKNAME_REGEX = re.compile(r"^[A-Za-z0-9가-힣._]{2,20}$")


def _cache_key():
    ver = getattr(settings, "FORBIDDEN_NICKNAMES_VERSION", "v1")
    return f"{FORBIDDEN_NICKNAMES_CACHE_KEY}:{ver}"


def normalize_nickname(nick: str) -> str:
    n = unicodedata.normalize("NFKC", nick).strip()
    return n


class NicknamePolicyValidator:
    message = _("Nickname must be between 2 and 20 characters long and can only contain Korean, English letters, numbers, dots, and underscores.")

    def __call__(self, value: str):
        v = normalize_nickname(value)
        if not (NICKNAME_MIN <= len(v) <= NICKNAME_MAX):
            raise serializers.ValidationError(self.message)
        if not NICKNAME_REGEX.match(v):
            raise serializers.ValidationError(self.message)
        return v


class ForbiddenNicknameService:
    @staticmethod
    def load() -> set[str]:
        words = cache.get(_cache_key())
        if words is None:
            words = getattr(settings, "FORBIDDEN_NICKNAMES", ["admin", "operator", "moderator"])
            cache.set(_cache_key(), list(words), FORBIDDEN_NICKNAMES_TTL)
        return {w.strip().lower() for w in words}


class ForbiddenNicknameValidator:
    message = _("This nickname is not allowed.")

    def __call__(self, value: str):
        v = normalize_nickname(value).lower()
        words = ForbiddenNicknameService.load()
        if v in words or any(w in v for w in words):
            raise serializers.ValidationError(self.message)
        return v
