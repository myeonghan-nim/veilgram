def user_feed_group(user_id: str) -> str:
    # Channels group name must match ^[A-Za-z0-9._-]+$ and be < 100 chars. Use dot as separator to avoid ':'.
    return f"feed.{user_id}"
