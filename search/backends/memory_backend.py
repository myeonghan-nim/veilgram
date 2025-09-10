from typing import Iterable, Dict, Any


class InMemoryBackend:
    def __init__(self):
        self.users, self.posts, self.tags = {}, {}, {}

    def ensure_indices(self): ...
    def drop_indices(self):
        self.users.clear()
        self.posts.clear()
        self.tags.clear()

    # Indexing
    def index_user(self, doc: Dict[str, Any]) -> None:
        self.users[doc["id"]] = doc

    def index_post(self, doc: Dict[str, Any]) -> None:
        self.posts[doc["id"]] = doc

    def index_hashtag(self, doc: Dict[str, Any]) -> None:
        self.tags[doc["name"]] = doc

    def bulk_index(self, kind: str, docs: Iterable[Dict[str, Any]]) -> None:
        for d in docs:
            if kind == "user":
                self.index_user(d)
            elif kind == "post":
                self.index_post(d)
            else:
                self.index_hashtag(d)

    # Searching
    def _find(self, store, q, page, size, keys):
        ql = (q or "").lower()
        rows = [v for v in store.values() if any(ql in str(v.get(k, "")).lower() for k in keys)]
        total = len(rows)
        start = (page - 1) * size
        end = start + size
        return {"hits": {"total": {"value": total}, "hits": [{"_source": s} for s in rows[start:end]]}}

    def search_users(self, q, page, size):
        return self._find(self.users, q, page, size, ["nickname", "status_message"])

    def search_posts(self, q, page, size):
        return self._find(self.posts, q, page, size, ["content", "author_nickname", "hashtags"])

    def search_hashtags(self, q, page, size):
        return self._find(self.tags, q, page, size, ["name"])

    def delete_user(self, user_id: str) -> None:
        self.users.pop(user_id, None)

    def delete_post(self, post_id: str) -> None:
        self.posts.pop(post_id, None)

    def delete_hashtag(self, name: str) -> None:
        self.tags.pop(name, None)
