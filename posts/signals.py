from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import tasks
from .models import Post, PostLike, Repost

User = get_user_model()


def _spawn(task, *args, **kwargs):
    # 테스트/로컬에서 CELERY_TASK_ALWAYS_EAGER=True 라면 즉시 동기 실행(.apply), 그 외 환경에서는 .delay 로 비동기 실행.
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return task.apply(args=args, kwargs=kwargs)
    return task.delay(*args, **kwargs)


# --- Post ---
@receiver(post_save, sender=Post)
def on_post_created_or_updated(sender, instance, created: bool, **kwargs):
    if created:
        _spawn(tasks.on_post_created, str(instance.id), str(instance.author_id))
    else:
        _spawn(tasks.on_post_updated, str(instance.id), str(instance.author_id))


@receiver(post_delete, sender=Post)
def on_post_deleted(sender, instance, **kwargs):
    _spawn(tasks.on_post_deleted, str(instance.id), str(instance.author_id))


# --- Like ---
@receiver(post_save, sender=PostLike)
def on_post_liked_created(sender, instance, created: bool, **kwargs):
    if not created:
        return
    _spawn(tasks.on_post_liked, str(instance.post_id), str(instance.user_id), str(instance.post.author_id))


@receiver(post_delete, sender=PostLike)
def on_post_unliked_deleted(sender, instance, **kwargs):
    _spawn(tasks.on_post_unliked, str(instance.post_id), str(instance.user_id), str(instance.post.author_id))


# --- Repost ---
@receiver(post_save, sender=Repost)
def on_post_reposted_created(sender, instance, created: bool, **kwargs):
    if not created:
        return
    _spawn(tasks.on_post_reposted, str(instance.original_post_id), str(instance.user_id), str(instance.original_post.author_id), str(instance.id))


@receiver(post_delete, sender=Repost)
def on_post_unreposted_deleted(sender, instance, **kwargs):
    _spawn(tasks.on_post_unreposted, str(instance.original_post_id), str(instance.user_id), str(instance.original_post.author_id), str(instance.id))
