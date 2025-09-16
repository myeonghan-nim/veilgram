from typing import Any, Dict, Iterable

from django.conf import settings


class OpenSearchBackend:
    def __init__(self):
        from opensearchpy import OpenSearch, helpers  # import 지연

        self._helpers = helpers

        conf = settings.OPENSEARCH
        auth = (conf["USER"], conf["PASSWORD"]) if conf["USER"] else None
        self.client = OpenSearch(hosts=conf["HOSTS"], http_auth=auth, timeout=conf["TIMEOUT"], retries=2)
        self.prefix = conf["INDEX_PREFIX"]
        self.use_nori = conf["USE_NORI"]

    # index names
    @property
    def idx_users(self):
        return f"{self.prefix}-users"

    @property
    def idx_posts(self):
        return f"{self.prefix}-posts"

    @property
    def idx_tags(self):
        return f"{self.prefix}-hashtags"

    def _analyzers(self) -> Dict[str, Any]:
        # nori 사용 시 토글 (운영 클러스터 플러그인 상태와 일치시켜야 함)
        if self.use_nori:
            return {
                "analysis": {
                    "analyzer": {
                        "kr": {"type": "custom", "tokenizer": "nori_tokenizer"},
                        "edge": {"type": "custom", "tokenizer": "standard", "filter": ["lowercase", "edge_ngram"]},
                    },
                    "filter": {"edge_ngram": {"type": "edge_ngram", "min_gram": 1, "max_gram": 20}},
                }
            }
        return {
            "analysis": {
                "analyzer": {"edge": {"type": "custom", "tokenizer": "standard", "filter": ["lowercase", "edge_ngram"]}},
                "filter": {"edge_ngram": {"type": "edge_ngram", "min_gram": 1, "max_gram": 20}},
            }
        }

    def _create_index(self, name: str, body: Dict[str, Any]):
        if not self.client.indices.exists(index=name):
            self.client.indices.create(index=name, body=body)

    def ensure_indices(self):
        self._create_index(
            self.idx_users,
            {
                "settings": self._analyzers(),
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "nickname": {"type": "text", "analyzer": "edge"},
                        "status_message": {"type": "text", "analyzer": "edge"},
                        "created_at": {"type": "date"},
                    }
                },
            },
        )
        self._create_index(
            self.idx_posts,
            {
                "settings": self._analyzers(),
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "author_id": {"type": "keyword"},
                        "author_nickname": {"type": "text", "analyzer": "edge"},
                        "content": {"type": "text", "analyzer": "edge"},
                        "hashtags": {"type": "keyword"},
                        "created_at": {"type": "date"},
                        "like_count": {"type": "integer"},
                    }
                },
            },
        )
        self._create_index(
            self.idx_tags, {"settings": self._analyzers(), "mappings": {"properties": {"name": {"type": "text", "analyzer": "edge"}, "post_count": {"type": "integer"}}}}
        )

    def drop_indices(self):
        for idx in [self.idx_users, self.idx_posts, self.idx_tags]:
            if self.client.indices.exists(index=idx):
                self.client.indices.delete(index=idx)

    # Indexing
    def index_user(self, doc: Dict[str, Any]) -> None:
        self.client.index(index=self.idx_users, id=doc["id"], body=doc, refresh="wait_for")

    def index_post(self, doc: Dict[str, Any]) -> None:
        self.client.index(index=self.idx_posts, id=doc["id"], body=doc, refresh="wait_for")

    def index_hashtag(self, doc: Dict[str, Any]) -> None:
        self.client.index(index=self.idx_tags, id=doc["name"], body=doc, refresh="wait_for")

    def bulk_index(self, kind: str, docs: Iterable[Dict[str, Any]]) -> None:
        idx = {"user": self.idx_users, "post": self.idx_posts, "hashtag": self.idx_tags}[kind]
        actions = ({"_op_type": "index", "_index": idx, "_id": d.get("id") or d.get("name"), "_source": d} for d in docs)
        self._helpers.bulk(self.client, actions, refresh="wait_for")

    # Searching
    def _search(self, index: str, q: str, page: int, size: int, fields: list, boosts=None):
        boosts = boosts or {}
        body = {
            "query": {"bool": {"should": [{"match": {f: {"query": q, "boost": boosts.get(f, 1.0)}}} for f in fields], "minimum_should_match": 1}},
            "from": (page - 1) * size,
            "size": size,
        }
        return self.client.search(index=index, body=body)

    def search_users(self, q, page, size):
        return self._search(self.idx_users, q, page, size, ["nickname", "status_message"], {"nickname": 2.0})

    def search_posts(self, q, page, size):
        return self._search(self.idx_posts, q, page, size, ["content", "author_nickname"], {"content": 2.5})

    def search_hashtags(self, q, page, size):
        return self._search(self.idx_tags, q, page, size, ["name"], {"name": 3.0})

    def delete_user(self, user_id: str) -> None:
        self.client.delete(index=self.idx_users, id=user_id, ignore=[404], refresh="wait_for")

    def delete_post(self, post_id: str) -> None:
        self.client.delete(index=self.idx_posts, id=post_id, ignore=[404], refresh="wait_for")

    def delete_hashtag(self, name: str) -> None:
        self.client.delete(index=self.idx_tags, id=name, ignore=[404], refresh="wait_for")
