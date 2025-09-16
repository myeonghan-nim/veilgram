from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ModerationRule
from .services import invalidate_rules_cache


@receiver(post_save, sender=ModerationRule)
def _rule_saved(sender, instance, **kwargs):
    invalidate_rules_cache()


@receiver(post_delete, sender=ModerationRule)
def _rule_deleted(sender, instance, **kwargs):
    invalidate_rules_cache()
