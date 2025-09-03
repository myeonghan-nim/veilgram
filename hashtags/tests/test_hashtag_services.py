import pytest

from hashtags.services import ensure_hashtags


@pytest.mark.django_db
class TestHashtagServices:
    def test_ensure_hashtags_bulk_create_and_dedup(self):
        rows = ensure_hashtags(["Django", "django", "장고"])
        names = sorted([r.name for r in rows])
        assert names == ["django", "장고"]

        again = ensure_hashtags(["django", "장고"])
        assert len(again) == 2  # 이미 존재해도 동일 반환
