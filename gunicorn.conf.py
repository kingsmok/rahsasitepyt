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

bind = '0.0.0.0:8000'             # اتصال به همه رابط‌ها
workers = int(os.environ.get('GUNICORN_WORKERS', 3))       # ۳ ورکر بهینه برای ۲ هسته CPU
worker_class = 'gthread'          # معماری Threaded برای تحمل ترافیک ۵۰۰ هزارتایی با مصرف رم زیر ۱۵۰ مگابایت
threads = int(os.environ.get('GUNICORN_THREADS', 8))       # ۸ ترد همزمان برای هر ورکر (جمعاً ۲۴ پردازش همزمان)
max_requests = 2000               # بازنشانی ورکر بعد از ۲۰0۰ درخواست (ضد نشت حافظه)
max_requests_jitter = 200
backlog = 2048                    # صف انتظار برای لحظات اوج ترافیک
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
