from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import AuditLog, Document


@receiver(pre_save, sender=Document)
def store_document_state(sender, instance: Document, **kwargs):
    instance._was_adding = instance._state.adding


@receiver(post_save, sender=Document)
def write_document_audit_log(sender, instance: Document, **kwargs):
    action = "created" if getattr(instance, "_was_adding", False) else "updated"
    # Use the saved_by actor if available (from update), otherwise use created_by (from create)
    actor = getattr(instance, '_audit_actor', None) or instance.created_by
    AuditLog.objects.create(
        actor=actor,
        action=action,
        model_name="Document",
        object_id=str(instance.id),
    )
