from __future__ import annotations

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import AuditLog, Comment, Document, DocumentVersion, Tag, User, Workspace, WorkspaceMember
from .permissions import get_workspace_membership, require_workspace_role
from .serializers import (
    AuditLogSerializer,
    CommentSerializer,
    DocumentSerializer,
    DocumentVersionSerializer,
    TagSerializer,
    UserSerializer,
    WorkspaceMemberSerializer,
    WorkspaceSummarySerializer,
)
from .utils import resolve_request_user


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("created_at")
    serializer_class = UserSerializer
    lookup_field = "id"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
        except IntegrityError:
            return Response({"detail": "A user with the given email or phone already exists."}, status=status.HTTP_409_CONFLICT)
        headers = self.get_success_headers(serializer.data)
        return Response(self.get_serializer(user).data, status=status.HTTP_201_CREATED, headers=headers)


class WorkspaceViewSet(viewsets.ModelViewSet):
    queryset = Workspace.objects.select_related("owner").all().order_by("created_at")
    serializer_class = WorkspaceSummarySerializer
    lookup_field = "id"

    def get_serializer_class(self):
        if self.action in {"members"}:
            return WorkspaceMemberSerializer
        if self.action in {"summary"}:
            return WorkspaceSummarySerializer
        return WorkspaceSummarySerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                workspace = serializer.save()
                WorkspaceMember.objects.create(workspace=workspace, user=workspace.owner, role=WorkspaceMember.RoleChoices.ADMIN)
        except IntegrityError:
            return Response({"detail": "Unable to create workspace or owner membership."}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(workspace).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        workspace = get_object_or_404(Workspace.objects.select_related("owner"), pk=kwargs[self.lookup_field])
        try:
            get_workspace_membership(request, workspace)
        except (ValidationError, DjangoPermissionDenied) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(self.get_serializer(workspace).data)

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, *args, **kwargs):
        workspace = get_object_or_404(Workspace.objects.select_related("owner"), pk=kwargs[self.lookup_field])
        if request.method.lower() == "get":
            try:
                get_workspace_membership(request, workspace)
            except (ValidationError, DjangoPermissionDenied) as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
            members = (
                workspace.members.select_related("workspace", "user")
                .annotate(document_count=Count("workspace__documents", distinct=True))
                .order_by("joined_at")
            )
            serializer = WorkspaceMemberSerializer(members, many=True)
            return Response(serializer.data)

        try:
            require_workspace_role(request, workspace, (WorkspaceMember.RoleChoices.ADMIN,))
        except (ValidationError, DjangoPermissionDenied) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        payload = request.data.copy()
        payload["workspace_id"] = str(workspace.id)
        serializer = WorkspaceMemberSerializer(data=payload, context={"request": request, "workspace": workspace})
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                member = serializer.save()
        except IntegrityError:
            return Response({"detail": "This user is already a member of the workspace."}, status=status.HTTP_409_CONFLICT)
        return Response(WorkspaceMemberSerializer(member).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request, *args, **kwargs):
        workspace = get_object_or_404(
            Workspace.objects.select_related("owner").annotate(
                member_count=Count("members", distinct=True),
                document_count=Count("documents", distinct=True),
                comment_count=Count("documents__comments", distinct=True),
            ),
            pk=kwargs[self.lookup_field],
        )
        try:
            get_workspace_membership(request, workspace)
        except (ValidationError, DjangoPermissionDenied) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        serializer = WorkspaceSummarySerializer(workspace)
        payload = serializer.data
        payload["comment_count"] = getattr(workspace, "comment_count", 0)
        return Response(payload)


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    lookup_field = "id"

    def get_queryset(self):
        queryset = (
            Document.objects.select_related("workspace", "workspace__owner", "created_by")
            .prefetch_related("tags")
            .annotate(
                version_count=Count("versions", distinct=True),
                comment_count=Count("comments", distinct=True),
                tag_count=Count("tags", distinct=True),
            )
            .order_by("-updated_at")
        )
        params = self.request.query_params
        search = params.get("search")
        workspace_ids = params.get("workspace_ids")
        status_filter = params.get("status_in")
        created_by_ids = params.get("created_by_ids")
        updated_after = params.get("updated_after")
        updated_before = params.get("updated_before")
        title = params.get("title_icontains")
        tag_name = params.get("tag_name")
        tag_ids = params.get("tag_ids")

        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(content__icontains=search))
        if title:
            queryset = queryset.filter(title__icontains=title)
        if tag_name:
            queryset = queryset.filter(tags__name__iexact=tag_name).distinct()
        if tag_ids:
            queryset = queryset.filter(tags__id__in=[item for item in tag_ids.split(",") if item]).distinct()
        if workspace_ids:
            queryset = queryset.filter(workspace_id__in=[item for item in workspace_ids.split(",") if item])
        if status_filter:
            queryset = queryset.filter(status__in=[item for item in status_filter.split(",") if item])
        if created_by_ids:
            queryset = queryset.filter(created_by_id__in=[item for item in created_by_ids.split(",") if item])
        if updated_after:
            queryset = queryset.filter(updated_at__gte=updated_after)
        if updated_before:
            queryset = queryset.filter(updated_at__lte=updated_before)
        return queryset

    def _get_document(self, document_id):
        document = get_object_or_404(Document.objects.select_related("workspace", "workspace__owner", "created_by").prefetch_related("tags"), pk=document_id)
        return document

    def _require_document_access(self, request, document, allowed_roles=(WorkspaceMember.RoleChoices.ADMIN, WorkspaceMember.RoleChoices.EDITOR, WorkspaceMember.RoleChoices.VIEWER)):
        try:
            require_workspace_role(request, document.workspace, allowed_roles)
        except (ValidationError, DjangoPermissionDenied) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return None

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        actor = resolve_request_user(request, required=True)
        try:
            with transaction.atomic():
                document = serializer.save(saved_by=actor)
        except IntegrityError:
            return Response({"detail": "Unable to create the document."}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(document).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        document = self.get_object()
        if (denied := self._require_document_access(request, document, (WorkspaceMember.RoleChoices.ADMIN, WorkspaceMember.RoleChoices.EDITOR))) is not None:
            return denied
        serializer = self.get_serializer(document, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        actor = resolve_request_user(request, required=True)
        try:
            with transaction.atomic():
                document = serializer.save(saved_by=actor)
        except IntegrityError:
            return Response({"detail": "Unable to update the document."}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(document).data)

    def destroy(self, request, *args, **kwargs):
        document = self.get_object()
        if (denied := self._require_document_access(request, document, (WorkspaceMember.RoleChoices.ADMIN,))) is not None:
            return denied
        return super().destroy(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        document = self._get_document(kwargs[self.lookup_field])
        if (denied := self._require_document_access(request, document)) is not None:
            return denied
        return Response(self.get_serializer(document).data)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="versions")
    def versions(self, request, *args, **kwargs):
        document = self._get_document(kwargs[self.lookup_field])
        if (denied := self._require_document_access(request, document)) is not None:
            return denied
        versions = document.versions.select_related("saved_by").order_by("-version_number")
        serializer = DocumentVersionSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="stats")
    def stats(self, request, *args, **kwargs):
        document = self._get_document(kwargs[self.lookup_field])
        if (denied := self._require_document_access(request, document)) is not None:
            return denied
        stats = Document.objects.filter(pk=document.pk).aggregate(
            version_count=Count("versions", distinct=True),
            comment_count=Count("comments", distinct=True),
            tag_count=Count("tags", distinct=True),
        )
        latest_version = document.versions.order_by("-version_number").first()
        return Response(
            {
                "document_id": document.id,
                "version_count": stats["version_count"],
                "comment_count": stats["comment_count"],
                "tag_count": stats["tag_count"],
                "latest_version_number": latest_version.version_number if latest_version else None,
                "updated_at": document.updated_at,
            }
        )

    @action(detail=True, methods=["post"], url_path="tags")
    def tags(self, request, *args, **kwargs):
        document = self._get_document(kwargs[self.lookup_field])
        if (denied := self._require_document_access(request, document)) is not None:
            return denied
        tag_ids = request.data.get("tag_ids")
        if not isinstance(tag_ids, list) or not tag_ids:
            return Response({"detail": "tag_ids must be a non-empty list of UUIDs."}, status=status.HTTP_400_BAD_REQUEST)
        tags = Tag.objects.filter(id__in=tag_ids)
        existing_ids = set(str(tag_id) for tag_id in tags.values_list("id", flat=True))
        missing_ids = [str(tag_id) for tag_id in tag_ids if str(tag_id) not in existing_ids]
        if missing_ids:
            return Response({"detail": f"Unknown tag ids: {', '.join(missing_ids)}"}, status=status.HTTP_400_BAD_REQUEST)
        # only add tags that are not already associated and record audit logs for them
        current_tag_ids = set(str(tid) for tid in document.tags.values_list("id", flat=True))
        to_add = [t for t in tags if str(t.id) not in current_tag_ids]
        if not to_add:
            return Response({"tag_ids": list(document.tags.values_list("id", flat=True))}, status=status.HTTP_200_OK)
        document.tags.add(*to_add)
        # record audit logs for each newly added tag using the acting user
        actor = resolve_request_user(request, required=True)
        for tag in to_add:
            AuditLog.objects.create(actor=actor, action="tag_added", model_name="Document", object_id=str(document.id))
        return Response({"tag_ids": list(document.tags.values_list("id", flat=True))}, status=status.HTTP_200_OK)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    lookup_field = "id"

    def get_queryset(self):
        queryset = Comment.objects.select_related("document", "document__workspace", "author", "parent").order_by("created_at")
        document_id = self.request.query_params.get("document")
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        updated_after = self.request.query_params.get("created_after")
        updated_before = self.request.query_params.get("created_before")
        if updated_after:
            queryset = queryset.filter(created_at__gte=updated_after)
        if updated_before:
            queryset = queryset.filter(created_at__lte=updated_before)
        return queryset

    def _require_document_access(self, request, document, allowed_roles=(WorkspaceMember.RoleChoices.ADMIN, WorkspaceMember.RoleChoices.EDITOR, WorkspaceMember.RoleChoices.VIEWER)):
        try:
            require_workspace_role(request, document.workspace, allowed_roles)
        except (ValidationError, DjangoPermissionDenied) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return None

    def list(self, request, *args, **kwargs):
        if not request.query_params.get("document"):
            return Response({"detail": "document query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
        document = get_object_or_404(Document.objects.select_related("workspace"), pk=request.query_params.get("document"))
        if (denied := self._require_document_access(request, document)) is not None:
            return denied
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor = resolve_request_user(request, required=True)
        document = serializer.validated_data["document"]
        if (denied := self._require_document_access(request, document)) is not None:
            return denied
        try:
            with transaction.atomic():
                comment = serializer.save(author=actor)
        except IntegrityError:
            return Response({"detail": "Unable to create the comment."}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(comment).data, status=status.HTTP_201_CREATED)


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all().annotate(document_count=Count("documents", distinct=True)).order_by("name")
    serializer_class = TagSerializer
    lookup_field = "id"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tag = serializer.save()
        except IntegrityError:
            return Response({"detail": "A tag with this name already exists."}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(tag).data, status=status.HTTP_201_CREATED)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor").order_by("-timestamp")
    serializer_class = AuditLogSerializer
    lookup_field = "id"

    def get_queryset(self):
        queryset = super().get_queryset()
        model_name = self.request.query_params.get("model_name")
        action = self.request.query_params.get("action")
        actor = self.request.query_params.get("actor")
        timestamp_after = self.request.query_params.get("timestamp_after")
        timestamp_before = self.request.query_params.get("timestamp_before")
        if model_name:
            queryset = queryset.filter(model_name__icontains=model_name)
        if action:
            queryset = queryset.filter(action__in=[item for item in action.split(",") if item])
        if actor:
            queryset = queryset.filter(actor_id=actor)
        if timestamp_after:
            queryset = queryset.filter(timestamp__gte=timestamp_after)
        if timestamp_before:
            queryset = queryset.filter(timestamp__lte=timestamp_before)
        return queryset
