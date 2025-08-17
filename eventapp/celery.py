# eventapp_project/celery.py

import os
from celery import Celery
import eventlet # Nhập eventlet

os.environ.setdefault('FORK_MODE', 'spawn')
eventlet.monkey_patch() # Thêm dòng này

# Dat bien moi truong de Django biet su dung settings.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventapp.settings')

# Tao instance Celery
app = Celery('eventapp')

# Lay config tu Django settings, voi prefix "CELERY"
app.config_from_object('django.conf:settings', namespace='CELERY')

# Tu dong tim va load cac task trong cac app Django
app.autodiscover_tasks()
