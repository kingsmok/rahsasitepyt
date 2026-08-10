# -*- coding: utf-8 -*-
"""پیکربندی Gunicorn — production-ready
اجرا:  gunicorn -c gunicorn.conf.py wsgi:app
"""
import os

# مسیر پروژه
BASE = os.path.dirname(os.path.abspath(__file__))

# لاگ‌ها: ابتدا /var/log/academy (روی سرور)، fallback به logs/ محلی
LOG_DIR = '/var/log/academy'
if not os.path.isdir(LOG_DIR) or not os.access(LOG_DIR, os.W_OK):
    LOG_DIR = os.path.join(BASE, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

bind = '127.0.0.1:8000'          # پشت Nginx — در معرض مستقیم نیست
workers = 3                       # = (هسته‌های CPU × 2) + 1
worker_class = 'sync'
timeout = 60
graceful_timeout = 30
keepalive = 5

# لاگ‌ها
accesslog = os.path.join(LOG_DIR, 'access.log')
errorlog = os.path.join(LOG_DIR, 'error.log')
capture_output = True
loglevel = 'info'

# نام سرویس برای systemd (Type=notify)
proc_name = 'academy'
