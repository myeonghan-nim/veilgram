from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from .events import publish_event
from .models import CommentReport, PostReport, UserReport

User = get_user_model()


def _join_reasons(reasons_list):
    # ERD가 text 필드이므로 간단히 줄바꿈 문자열로 직렬화
    return "\n".join(r.strip() for r in reasons_list if r and r.strip())


@transaction.atomic
def create_user_report(*, reporter, target_user_id: str, reasons: list[str], block: bool):
    if str(reporter.id) == str(target_user_id):
        raise ValidationError({"detail": "You cannot report yourself."})

    try:
        target = User.objects.get(id=target_user_id)
    except ObjectDoesNotExist:
        raise NotFound({"detail": "Target user not found."})

    # 즉시 중복 방지(유연성을 위해 애플리케이션 레벨로)
    if UserReport.objects.filter(reporter=reporter, target_user=target).exists():
        raise ValidationError({"detail": "Already reported."})

    report = UserReport.objects.create(reporter=reporter, target_user=target, reasons=_join_reasons(reasons))

    # block 요청이면 즉시 차단(관계 도메인)
    if block:
        from relations.models import Block  # 기존 도메인 재사용

        Block.objects.get_or_create(user_id=reporter.id, blocked_user_id=target.id)

    publish_event("UserReported", {"report_id": str(report.id), "reporter_id": str(reporter.id), "target_user_id": str(target.id), "block": block})
    return report


@transaction.atomic
def create_post_report(*, reporter, post_id: str, reasons: list[str], block: bool):
    from posts.models import Post

    try:
        post = Post.objects.select_related("author").get(id=post_id)
    except Post.DoesNotExist:
        raise NotFound({"detail": "Post not found."})

    if post.author_id == reporter.id:
        raise ValidationError({"detail": "You cannot report your own post."})

    if PostReport.objects.filter(reporter=reporter, post=post).exists():
        raise ValidationError({"detail": "Already reported."})

    report = PostReport.objects.create(reporter=reporter, post=post, reasons=_join_reasons(reasons), block=block)

    if block:
        from relations.models import Block

        Block.objects.get_or_create(user_id=reporter.id, blocked_user_id=post.author_id)

    publish_event("PostReported", {"report_id": str(report.id), "reporter_id": str(reporter.id), "post_id": str(post.id), "author_id": str(post.author_id), "block": block})
    return report


@transaction.atomic
def create_comment_report(*, reporter, comment_id: str, reasons: list[str], block: bool):
    from comments.models import Comment

    try:
        comment = Comment.objects.select_related("user", "post").get(id=comment_id)
    except Comment.DoesNotExist:
        raise NotFound({"detail": "Comment not found."})

    if comment.user_id == reporter.id:
        raise ValidationError({"detail": "You cannot report your own comment."})

    if CommentReport.objects.filter(reporter=reporter, comment=comment).exists():
        raise ValidationError({"detail": "Already reported."})

    report = CommentReport.objects.create(reporter=reporter, comment=comment, reasons=_join_reasons(reasons), block=block)

    if block:
        from relations.models import Block

        Block.objects.get_or_create(user_id=reporter.id, blocked_user_id=comment.user_id)

    publish_event(
        "CommentReported",
        {
            "report_id": str(report.id),
            "reporter_id": str(reporter.id),
            "comment_id": str(comment.id),
            "author_id": str(comment.user_id),
            "post_id": str(comment.post_id),
            "block": block,
        },
    )
    return report
