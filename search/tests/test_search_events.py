import pytest

from search import services
from search.event_dispatcher import dispatch


def _total(resp):
    tot = resp["hits"]["total"]
    return tot["value"] if isinstance(tot, dict) else tot


def _sources(resp):
    return [h["_source"] for h in resp["hits"]["hits"]]


@pytest.mark.django_db
class TestSearchEventDispatch:
    @pytest.fixture(autouse=True)
    def _force_memory_backend(self, settings, monkeypatch):
        # OpenSearch 비활성 → InMemoryBackend 사용
        settings.OPENSEARCH["ENABLED"] = False
        # backend 싱글톤 리셋
        import search.services as srv

        monkeypatch.setattr(srv, "_backend", None)
        # 인덱스 초기화
        services.backend().drop_indices()
        services.backend().ensure_indices()

    class TestPosts:
        def test_post_created_indexes_and_searchable(self):
            evt = {
                "type": "PostCreated",
                "payload": {
                    "post_id": "p1",
                    "author_id": "a1",
                    "author_nickname": "neo",
                    "content": "hello world",
                    "hashtags": ["x", "y"],
                    "created_ms": 1_700_000_000_000,
                    "like_count": 3,
                },
            }
            dispatch(evt)

            resp = services.search_posts(q="hello", page=1, size=10)
            assert _total(resp) == 1

            src = _sources(resp)[0]
            assert src["id"] == "p1"
            assert "hello" in src["content"]
            assert src["hashtags"] == ["x", "y"]

        def test_post_deleted_removes_from_index(self):
            # 사전 색인
            services.index_post("p2", "a1", "neo", "bye now", ["z"], "2025-01-01T00:00:00Z")
            # 삭제 이벤트
            dispatch({"type": "PostDeleted", "payload": {"post_id": "p2"}})

            resp = services.search_posts(q="bye", page=1, size=10)
            assert _total(resp) == 0

    class TestHashtags:
        def test_hashtags_extracted_indexes_tags(self):
            evt = {
                "type": "HashtagsExtracted",
                "payload": {
                    "post_id": "p3",
                    "author_id": "a1",
                    "hashtags": ["golang", "python"],
                    "created_ms": 1_700_000_000_000,
                    # post_count 미지정 → 기본 0
                },
            }
            dispatch(evt)

            resp = services.search_hashtags(q="py", page=1, size=10)
            assert _total(resp) >= 1

            names = [s["name"] for s in _sources(resp)]
            assert "python" in names

    class TestUsers:
        def test_user_created_and_updated(self):
            # 생성
            dispatch(
                {
                    "type": "UserCreated",
                    "payload": {
                        "user_id": "u1",
                        "nickname": "neo",
                        "status_message": "there is no spoon",
                        "created_ms": 1_700_000_000_000,
                    },
                }
            )
            r1 = services.search_users(q="neo", page=1, size=10)
            assert _total(r1) == 1

            # 업데이트(닉네임 변경)
            dispatch({"type": "UserUpdated", "payload": {"user_id": "u1", "nickname": "morpheus"}})
            r2 = services.search_users(q="morpheus", page=1, size=10)
            assert _total(r2) == 1

            r3 = services.search_users(q="neo", page=1, size=10)
            assert _total(r3) == 0  # 동일 ID 재색인으로 교체됨

        def test_user_deleted(self):
            services.index_user(user_id="u2", nickname="trinity", status_message="", created_at="2025-01-01T00:00:00Z")
            dispatch({"type": "UserDeleted", "payload": {"user_id": "u2"}})
            r = services.search_users(q="trinity", page=1, size=10)
            assert _total(r) == 0

    class TestUnknown:
        def test_unknown_event_is_noop(self):
            # Unknown 타입은 예외 없이 무시되어야 함
            dispatch({"type": "SomethingElse", "payload": {"foo": "bar"}})
            # 아무것도 색인되지 않았는지 확인
            assert _total(services.search_posts(q="*", page=1, size=10)) == 0
            assert _total(services.search_users(q="*", page=1, size=10)) == 0
            assert _total(services.search_hashtags(q="*", page=1, size=10)) == 0
