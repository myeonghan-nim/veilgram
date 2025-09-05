CREATE KEYSPACE IF NOT EXISTS veilgram
  WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

CREATE TABLE IF NOT EXISTS veilgram.feed_posts (
  author_id uuid,
  created_at timeuuid,
  post_id uuid,
  like_count int,
  comment_count int,
  PRIMARY KEY (author_id, created_at)
) WITH CLUSTERING ORDER BY (created_at DESC);

CREATE TABLE IF NOT EXISTS veilgram.feed_hashtag_posts (
  hashtag text,
  created_at timeuuid,
  post_id uuid,
  author_id uuid,
  PRIMARY KEY (hashtag, created_at)
) WITH CLUSTERING ORDER BY (created_at DESC);

CREATE TABLE IF NOT EXISTS veilgram.feed_popular_posts (
  bucket_date date,
  score double,
  created_at timeuuid,
  post_id uuid,
  author_id uuid,
  PRIMARY KEY (bucket_date, score, created_at)
) WITH CLUSTERING ORDER BY (score DESC, created_at DESC);
