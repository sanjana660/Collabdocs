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
    AuditLog.objects.create(
        actor=instance.created_by,
        action=action,
        model_name="Document",
        object_id=str(instance.id),
    )
