import uuid
from typing import Dict, Iterable, List

from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement


class CassandraRepo:
    def __init__(self, contact_points: Iterable[str], keyspace: str):
        self.cluster = Cluster(list(contact_points))
        self.session = self.cluster.connect(keyspace)

    @staticmethod
    def _timeuuid_from_ts_ms(ts_ms: int) -> uuid.UUID:
        # 단순 변환(데모용). 운영에선 서버측 timeuuid(now) 삽입 권장.
        return uuid.uuid1(clock_seq=(ts_ms % 16384))

    def insert_post(self, author_id: uuid.UUID, post_id: uuid.UUID, created_ms: int, like_count=0, comment_count=0):
        tuid = self._timeuuid_from_ts_ms(created_ms)
        self.session.execute(
            "INSERT INTO feed_posts (author_id, created_at, post_id, like_count, comment_count) VALUES (%s,%s,%s,%s,%s)",
            (author_id, tuid, post_id, like_count, comment_count),
        )

    def delete_post(self, author_id: uuid.UUID, created_ms: int):
        tuid = self._timeuuid_from_ts_ms(created_ms)
        self.session.execute("DELETE FROM feed_posts WHERE author_id=%s AND created_at=%s", (author_id, tuid))

    def insert_hashtag_post(self, tag: str, post_id: uuid.UUID, author_id: uuid.UUID, created_ms: int):
        tuid = self._timeuuid_from_ts_ms(created_ms)
        self.session.execute("INSERT INTO feed_hashtag_posts (hashtag, created_at, post_id, author_id) VALUES (%s,%s,%s,%s)", (tag, tuid, post_id, author_id))

    def query_following_posts(self, author_ids: List[uuid.UUID], page: int, size: int) -> List[Dict]:
        rows = []
        for aid in author_ids:
            rs = self.session.execute(
                SimpleStatement("SELECT author_id, created_at, post_id, like_count, comment_count FROM feed_posts WHERE author_id=%s LIMIT %s"),
                (aid, size * (page + 1)),
            )
            rows.extend(rs.all())
        rows.sort(key=lambda r: r.created_at, reverse=True)
        start = page * size
        return [{"post_id": str(r.post_id), "author_id": str(r.author_id), "created_at": str(r.created_at)} for r in rows[start : start + size]]

    def query_hashtag_posts(self, tag: str, page: int, size: int) -> List[Dict]:
        rs = self.session.execute(SimpleStatement("SELECT hashtag, created_at, post_id, author_id FROM feed_hashtag_posts WHERE hashtag=%s LIMIT %s"), (tag, size * (page + 1)))
        rows = rs.all()
        rows.sort(key=lambda r: r.created_at, reverse=True)
        start = page * size
        return [{"post_id": str(r.post_id), "author_id": str(r.author_id), "created_at": str(r.created_at)} for r in rows[start : start + size]]
