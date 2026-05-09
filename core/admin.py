from django.contrib import admin

from .models import AuditLog, Comment, Document, DocumentVersion, Tag, User, Workspace, WorkspaceMember

admin.site.register(User)
admin.site.register(Workspace)
admin.site.register(WorkspaceMember)
admin.site.register(Document)
admin.site.register(DocumentVersion)
admin.site.register(Comment)
admin.site.register(Tag)
admin.site.register(AuditLog)
