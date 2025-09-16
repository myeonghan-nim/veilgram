from typing import Any, Dict, Iterable


class SearchBackend:
    # Index lifecycle
    def ensure_indices(self) -> None:
        """Ensure indices exist (stub)."""
        ...

    def drop_indices(self) -> None:
        """Ensure indices exist (stub)."""
        ...

    # Indexing
    def index_user(self, doc: Dict[str, Any]) -> None:
        """Ensure indices exist (stub)."""
        ...

    def index_post(self, doc: Dict[str, Any]) -> None:
        """Ensure indices exist (stub)."""
        ...

    def index_hashtag(self, doc: Dict[str, Any]) -> None:
        """Ensure indices exist (stub)."""
        ...

    def bulk_index(self, kind: str, docs: Iterable[Dict[str, Any]]) -> None:
        """Ensure indices exist (stub)."""
        ...

    # Searching
    def search_users(self, q: str, page: int, size: int) -> Dict[str, Any]:
        """Ensure indices exist (stub)."""
        ...

    def search_posts(self, q: str, page: int, size: int) -> Dict[str, Any]:
        """Ensure indices exist (stub)."""
        ...

    def search_hashtags(self, q: str, page: int, size: int) -> Dict[str, Any]:
        """Ensure indices exist (stub)."""
        ...

    def delete_user(self, user_id: str) -> None:
        """Ensure indices exist (stub)."""
        ...

    def delete_post(self, post_id: str) -> None:
        """Ensure indices exist (stub)."""
        ...

    def delete_hashtag(self, name: str) -> None:
        """Ensure indices exist (stub)."""
        ...
