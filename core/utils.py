from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError

from .models import User


def resolve_request_user(request, required: bool = False) -> User | None:
    if request is None:
        if required:
            raise ValidationError({"detail": "X-User-ID header is required."})
        return None
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        if required:
            raise ValidationError({"detail": "X-User-ID header is required."})
        return None
    try:
        uuid.UUID(str(user_id))
    except ValueError as exc:
        raise ValidationError({"detail": "X-User-ID must be a valid UUID."}) from exc

    user = User.objects.filter(id=user_id).first()
    if not user and required:
        raise ValidationError({"detail": "The acting user does not exist."})
    return user
