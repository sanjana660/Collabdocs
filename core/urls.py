from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuditLogViewSet, CommentViewSet, DocumentViewSet, TagViewSet, UserViewSet, WorkspaceViewSet

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"workspaces", WorkspaceViewSet, basename="workspace")
router.register(r"documents", DocumentViewSet, basename="document")
router.register(r"comments", CommentViewSet, basename="comment")
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"audit-logs", AuditLogViewSet, basename="audit-log")

urlpatterns = [path("", include(router.urls))]
