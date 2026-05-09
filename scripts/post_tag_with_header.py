import os, sys, pathlib
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from rest_framework.test import APIRequestFactory
from core.views import DocumentViewSet
from core.models import Document, Tag, WorkspaceMember

DOC_ID = '6d3732d2-ed47-42db-ab9b-d341f79c1043'
TAG_ID = '8ec9caa1-36ea-4153-b729-148c299fef1e'

if __name__ == '__main__':
    doc = Document.objects.filter(id=DOC_ID).first()
    if not doc:
        print('Document not found:', DOC_ID)
        sys.exit(1)
    # find a workspace admin
    member = WorkspaceMember.objects.filter(workspace=doc.workspace, role=WorkspaceMember.RoleChoices.ADMIN).select_related('user').first()
    if not member:
        print('No admin member found for workspace', doc.workspace.id)
        sys.exit(1)
    user = member.user
    print('Using user:', user.id, user.email, 'role', member.role)
    factory = APIRequestFactory()
    data = {'tag_ids': [TAG_ID]}
    # include header X-User-ID
    request = factory.post(f'/api/documents/{DOC_ID}/tags', data, format='json', HTTP_X_USER_ID=str(user.id))
    view = DocumentViewSet.as_view({'post': 'tags'})
    response = view(request, id=DOC_ID)
    print('status:', getattr(response, 'status_code', None))
    print(response.data)
