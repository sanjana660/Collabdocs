import os, sys, pathlib
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from core.models import Document, Tag

if __name__ == '__main__':
    tag = Tag.objects.first()
    print('testing tag:', tag.name if tag else 'no-tags')
    if not tag:
        print('No tags in DB to test against.')
        sys.exit(0)
    docs = Document.objects.filter(tags__name__iexact=tag.name).distinct()
    print('ORM filter count:', docs.count())
    docs_qs = Document.objects.filter(tags__id__in=[tag.id]).distinct()
    print('ORM filter by id count:', docs_qs.count())
    # simulate DRF view filtering via query param
    from rest_framework.test import APIRequestFactory
    from core.views import DocumentViewSet
    factory = APIRequestFactory()
    request = factory.get(f'/api/documents/?tag_name={tag.name}')
    view = DocumentViewSet.as_view({'get': 'list'})
    response = view(request)
    print('view response status:', getattr(response, 'status_code', None))
    print(response.data)
