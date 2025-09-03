from django.core.management.base import BaseCommand
from django.db.models import Count

from search import services


class Command(BaseCommand):
    help = "Rebuild search indices from database"

    def handle(self, *args, **opts):
        b = services.backend()
        b.drop_indices()
        b.ensure_indices()

        # Users/Profiles
        from profiles.models import Profile

        pqs = Profile.objects.select_related("user").all()
        b.bulk_index("user", ({"id": str(p.user_id), "nickname": p.nickname, "status_message": p.status_message or "", "created_at": p.created_at} for p in pqs))

        # Posts (+ Hashtags 매핑)
        from posts.models import Post

        try:
            from hashtags.models import PostHashtag

            tag_map = {}
            for row in PostHashtag.objects.values("post_id", "hashtag__name"):
                tag_map.setdefault(row["post_id"], []).append(row["hashtag__name"])
        except Exception:
            tag_map = {}

        b.bulk_index(
            "post",
            (
                {
                    "id": str(p.id),
                    "author_id": str(p.author_id),
                    "author_nickname": getattr(getattr(p, "author", None), "nickname", "") or "",
                    "content": p.content or "",
                    "hashtags": tag_map.get(p.id, []),
                    "created_at": p.created_at,
                    "like_count": getattr(p, "like_count", 0),
                }
                for p in Post.objects.all()
            ),
        )

        # Hashtags (있으면)
        try:
            from hashtags.models import Hashtag

            hqs = Hashtag.objects.annotate(post_count=Count("post_hashtags")).values("name", "post_count")
            b.bulk_index("hashtag", ({"name": h["name"], "post_count": h["post_count"]} for h in hqs))
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS("Search indices rebuilt"))
