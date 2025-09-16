from typing import Dict

from feed.services import handle_hashtags_extracted, handle_post_created, handle_post_deleted, handle_user_follow_changed

_HANDLERS = {
    "PostCreated": handle_post_created,
    "PostDeleted": handle_post_deleted,
    "HashtagsExtracted": handle_hashtags_extracted,
    "UserFollowed": handle_user_follow_changed,
    "UserUnfollowed": handle_user_follow_changed,
}


def dispatch(evt: Dict):
    t = evt.get("type")
    fn = _HANDLERS.get(t)
    if fn:
        fn(evt)
