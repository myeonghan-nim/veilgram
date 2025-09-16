from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import tasks
from .models import Comment


@receiver(post_save, sender=Comment)
def on_comment_created_or_updated(sender, instance: Comment, created: bool, **kwargs):
    if created:
        tasks.on_comment_created.delay(
            comment_id=str(instance.id),
            post_id=str(instance.post_id),
            author_id=str(instance.user_id),  # 댓글 작성자
            parent_id=str(instance.parent_id) if instance.parent_id else "",
            post_author_id=str(instance.post.author_id),
            parent_author_id=str(instance.parent.user_id) if instance.parent_id else "",
        )
    else:
        tasks.on_comment_updated.delay(comment_id=str(instance.id), post_id=str(instance.post_id), author_id=str(instance.user_id))


@receiver(post_delete, sender=Comment)
def on_comment_deleted(sender, instance: Comment, **kwargs):
    tasks.on_comment_deleted.delay(comment_id=str(instance.id), post_id=str(instance.post_id), author_id=str(instance.user_id))
