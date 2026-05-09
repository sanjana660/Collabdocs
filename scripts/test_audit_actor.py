import os, sys, pathlib
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from core.models import AuditLog, User
from rest_framework.test import APIRequestFactory
from core.views import AuditLogViewSet

if __name__ == '__main__':
    user = User.objects.first()
    if not user:
        user = User.objects.create_user(
            email='actor-test@example.com',
            first_name='Actor',
            last_name='Test',
            phone='+15559990000',
            password='Test1234!'
        )
    log = AuditLog.objects.create(actor=user, action='test', model_name='Document', object_id='test')
    factory = APIRequestFactory()
    request = factory.get(f'/api/audit-logs/?actor={user.id}')
    view = AuditLogViewSet.as_view({'get': 'list'})
    response = view(request)
    print('status:', getattr(response, 'status_code', None))
    print(response.data)
