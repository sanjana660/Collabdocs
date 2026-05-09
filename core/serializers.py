from __future__ import annotations

from django.db import transaction
from django.db.models import Count
from rest_framework import serializers

from .models import AuditLog, Comment, Document, DocumentVersion, Tag, User, Workspace, WorkspaceMember
from .utils import resolve_request_user


class UserSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "full_name"]

    def get_full_name(self, obj: User) -> str:
        return f"{obj.first_name} {obj.last_name}".strip()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email", "phone", "created_at"]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            "email": {"validators": []},
            "phone": {"validators": []},
        }

    def validate(self, attrs):
        first_name = attrs.get("first_name") or getattr(self.instance, "first_name", "")
        last_name = attrs.get("last_name") or getattr(self.instance, "last_name", "")
        if first_name.strip() == last_name.strip() and first_name:
            raise serializers.ValidationError({"detail": "First and last name must differ."})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class WorkspaceSummarySerializer(serializers.ModelSerializer):
    owner = UserSummarySerializer(read_only=True)
    member_count = serializers.SerializerMethodField()
    document_count = serializers.SerializerMethodField()
    document_ids = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = ["id", "name", "owner", "is_active", "created_at", "member_count", "document_count", "document_ids"]
        read_only_fields = ["id", "created_at", "member_count", "document_count", "document_ids"]

    def get_member_count(self, obj: Workspace) -> int:
        return getattr(obj, "member_count", obj.members.count())

    def get_document_count(self, obj: Workspace) -> int:
        return getattr(obj, "document_count", obj.documents.count())

    def get_document_ids(self, obj: Workspace):
        return list(obj.documents.values_list("id", flat=True)[:10])

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Workspace name cannot be empty.")
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        owner = resolve_request_user(request, required=True)
        if owner is None:
            raise serializers.ValidationError({"detail": "Owner is required."})
        validated_data["owner"] = owner
        return Workspace.objects.create(**validated_data)


class WorkspaceMemberSerializer(serializers.ModelSerializer):
    workspace = WorkspaceSummarySerializer(read_only=True)
    workspace_id = serializers.PrimaryKeyRelatedField(source="workspace", queryset=Workspace.objects.select_related("owner"), write_only=True, required=False)
    user = UserSummarySerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(source="user", queryset=User.objects.all(), write_only=True)

    class Meta:
        model = WorkspaceMember
        fields = ["id", "workspace", "workspace_id", "user", "user_id", "role", "joined_at"]
        read_only_fields = ["id", "joined_at"]

    def validate_role(self, value: str) -> str:
        valid_roles = {choice[0] for choice in WorkspaceMember.RoleChoices.choices}
        if value not in valid_roles:
            raise serializers.ValidationError("Role must be admin, editor, or viewer.")
        return value

    def validate(self, attrs):
        workspace = attrs.get("workspace") or self.context.get("workspace")
        user = attrs.get("user")
        if workspace and not workspace.is_active:
            raise serializers.ValidationError({"workspace_id": "Cannot add members to an inactive workspace."})
        if workspace and user and workspace.owner_id == user.id and attrs.get("role") != WorkspaceMember.RoleChoices.ADMIN:
            raise serializers.ValidationError({"role": "Workspace owner must remain an admin."})
        return attrs


class TagSummarySerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ["id", "name", "document_count"]

    def get_document_count(self, obj: Tag) -> int:
        return getattr(obj, "document_count", obj.documents.count())


class TagSerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Tag
        fields = ["id", "name", "document_count"]
        read_only_fields = ["id", "document_count"]
        extra_kwargs = {
            "name": {"validators": []},
        }

    def validate_name(self, value: str) -> str:
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Tag name must be at least 2 characters long.")
        return value

    def get_document_count(self, obj: Tag) -> int:
        return getattr(obj, "document_count", obj.documents.count())


class DocumentVersionSerializer(serializers.ModelSerializer):
    saved_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = DocumentVersion
        fields = ["id", "document", "content", "version_number", "saved_by", "saved_at"]
        read_only_fields = ["id", "version_number", "saved_at"]


class DocumentSerializer(serializers.ModelSerializer):
    workspace = WorkspaceSummarySerializer(read_only=True)
    workspace_id = serializers.PrimaryKeyRelatedField(source="workspace", queryset=Workspace.objects.select_related("owner"), write_only=True)
    created_by = UserSummarySerializer(read_only=True)
    tags = TagSummarySerializer(many=True, read_only=True)
    version_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    tag_count = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "content",
            "workspace",
            "workspace_id",
            "created_by",
            "status",
            "updated_at",
            "version_count",
            "comment_count",
            "tag_count",
            "tags",
        ]
        read_only_fields = ["id", "updated_at", "version_count", "comment_count", "tag_count", "tags"]

    def validate(self, attrs):
        workspace = attrs.get("workspace") or getattr(self.instance, "workspace", None)
        actor = resolve_request_user(self.context.get("request"), required=True)
        if workspace and not workspace.is_active:
            raise serializers.ValidationError({"workspace_id": "Workspace is inactive."})
        if not actor:
            raise serializers.ValidationError({"created_by_id": "An acting user is required for document changes."})
        membership = WorkspaceMember.objects.filter(workspace=workspace, user=actor).first()
        if not membership:
            raise serializers.ValidationError({"detail": "The acting user is not a member of this workspace."})
        if membership.role not in {WorkspaceMember.RoleChoices.ADMIN, WorkspaceMember.RoleChoices.EDITOR}:
            raise serializers.ValidationError({"detail": "Only admins and editors can create or update documents."})
        return attrs

    def get_version_count(self, obj: Document) -> int:
        return getattr(obj, "version_count", obj.versions.count())

    def get_comment_count(self, obj: Document) -> int:
        return getattr(obj, "comment_count", obj.comments.count())

    def get_tag_count(self, obj: Document) -> int:
        return getattr(obj, "tag_count", obj.tags.count())

    def create(self, validated_data, saved_by=None):
        saved_by = validated_data.pop("saved_by", saved_by)
        document = Document(**validated_data)
        document.save(saved_by=saved_by or validated_data.get("created_by"))
        return document

    def update(self, instance, validated_data, saved_by=None):
        saved_by = validated_data.pop("saved_by", saved_by)
        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)
        instance.save(saved_by=saved_by or validated_data.get("created_by") or instance.created_by)
        return instance


class CommentSerializer(serializers.ModelSerializer):
    document = serializers.PrimaryKeyRelatedField(queryset=Document.objects.select_related("workspace", "created_by"))
    author = UserSummarySerializer(read_only=True)
    parent = serializers.PrimaryKeyRelatedField(queryset=Comment.objects.all(), required=False, allow_null=True)
    reply_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "document", "author", "content", "parent", "reply_count", "created_at"]
        read_only_fields = ["id", "reply_count", "created_at"]

    def validate(self, attrs):
        document = attrs.get("document")
        parent = attrs.get("parent")
        if parent and parent.document_id != document.id:
            raise serializers.ValidationError({"parent": "Parent comment must belong to the same document."})
        return attrs

    def get_reply_count(self, obj: Comment) -> int:
        return obj.replies.count()


class AuditLogSerializer(serializers.ModelSerializer):
    actor = UserSummarySerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "action", "model_name", "object_id", "timestamp"]
        read_only_fields = fields
