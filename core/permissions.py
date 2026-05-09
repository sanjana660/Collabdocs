from __future__ import annotations

from django.core.exceptions import PermissionDenied

from .models import WorkspaceMember
from .utils import resolve_request_user


def get_workspace_membership(request, workspace):
    user = resolve_request_user(request, required=True)
    membership = WorkspaceMember.objects.select_related("workspace", "user").filter(workspace=workspace, user=user).first()
    if not membership:
        raise PermissionDenied("You are not a member of this workspace.")
    return user, membership


def require_workspace_role(request, workspace, allowed_roles: tuple[str, ...]):
    user, membership = get_workspace_membership(request, workspace)
    if membership.role not in allowed_roles:
        raise PermissionDenied("You do not have permission to perform this action.")
    return user, membership
