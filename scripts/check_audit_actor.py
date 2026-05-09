import os, sys, pathlib
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
from datetime import datetime
django.setup()
from core.models import AuditLog

ACTOR_ID = '6da6ee88-b6ac-4dcf-8d9a-fcbe7a6bc8ce'
TS_AFTER = '2026-05-01T00:00:00Z'
TS_BEFORE = '2026-05-09T23:59:59Z'

def parse_ts(s):
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        return None

if __name__ == '__main__':
    ts_after = parse_ts(TS_AFTER)
    ts_before = parse_ts(TS_BEFORE)
    qs = AuditLog.objects.filter(actor_id=ACTOR_ID)
    print('total for actor:', qs.count())
    if ts_after:
        qs = qs.filter(timestamp__gte=ts_after)
    if ts_before:
        qs = qs.filter(timestamp__lte=ts_before)
    print('for actor in range:', qs.count())
    for a in qs.order_by('-timestamp')[:5]:
        print(a.id, a.actor_id, a.action, a.model_name, a.timestamp)
