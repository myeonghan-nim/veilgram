from django.conf import settings

_backend = None


def get_backend():
    # env 기반 토글: ENABLED=false면 In-Memory
    if not settings.OPENSEARCH.get("ENABLED", False):
        from .backends.memory_backend import InMemoryBackend

        return InMemoryBackend()
    try:
        from .backends.opensearch_backend import OpenSearchBackend

        return OpenSearchBackend()
    except Exception:
        # 운영 장애 시에도 검색 완전 중단을 피하기 위한 안전망(선택)
        from .backends.memory_backend import InMemoryBackend

        return InMemoryBackend()


def backend():
    global _backend
    if _backend is None:
        _backend = get_backend()
        _backend.ensure_indices()
    return _backend


# Convenience wrappers
def index_user(user_id, nickname, status_message, created_at):
    backend().index_user({"id": str(user_id), "nickname": nickname, "status_message": status_message or "", "created_at": created_at})


def index_post(post_id, author_id, author_nickname, content, hashtags, created_at, like_count=0):
    backend().index_post(
        {
            "id": str(post_id),
            "author_id": str(author_id),
            "author_nickname": author_nickname or "",
            "content": content or "",
            "hashtags": hashtags or [],
            "created_at": created_at,
            "like_count": like_count,
        }
    )


def index_hashtag(name, post_count=0):
    backend().index_hashtag({"name": name, "post_count": post_count})


def search_users(q, page, size):
    return backend().search_users(q, page, size)


def search_posts(q, page, size):
    return backend().search_posts(q, page, size)


def search_hashtags(q, page, size):
    return backend().search_hashtags(q, page, size)
