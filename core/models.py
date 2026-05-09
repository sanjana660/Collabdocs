from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email: str, first_name: str, last_name: str, phone: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        if not phone:
            raise ValueError("Phone is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, first_name=first_name, last_name=last_name, phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, first_name: str = "Admin", last_name: str = "User", phone: str = "0000000000", password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, first_name, last_name, phone, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.CharField(max_length=254, unique=True)
    phone = models.CharField(max_length=15, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "phone"]

    def __str__(self) -> str:
        return self.email


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_workspaces")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class WorkspaceMember(models.Model):
    class RoleChoices(models.TextChoices):
        ADMIN = "admin", "Admin"
        EDITOR = "editor", "Editor"
        VIEWER = "viewer", "Viewer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="workspace_memberships")
    role = models.CharField(max_length=20, choices=RoleChoices.choices)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "user"], name="unique_workspace_member")]

    def __str__(self) -> str:
        return f"{self.user} in {self.workspace}"


class Document(models.Model):
    class StatusChoices(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    content = models.TextField()
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="documents")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_documents")
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.DRAFT)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, saved_by: User | None = None, **kwargs):
        super().save(*args, **kwargs)
        version_number = self.versions.count() + 1
        DocumentVersion.objects.create(
            document=self,
            content=self.content,
            version_number=version_number,
            saved_by=saved_by,
        )

    def __str__(self) -> str:
        return self.title


class DocumentVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    content = models.TextField()
    version_number = models.PositiveIntegerField()
    saved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="saved_versions")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        constraints = [models.UniqueConstraint(fields=["document", "version_number"], name="unique_document_version")]

    def __str__(self) -> str:
        return f"{self.document} v{self.version_number}"


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="comments")
    content = models.TextField()
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replies")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.content[:32]


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    documents = models.ManyToManyField(Document, related_name="tags", blank=True)

    def __str__(self) -> str:
        return self.name


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.model_name}:{self.action}"
