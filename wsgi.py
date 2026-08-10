# -*- coding: utf-8 -*-
"""WSGI entry point — برای Gunicorn/uWSGI:
    gunicorn -c gunicorn.conf.py wsgi:app
"""
import os
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی از .env (در production هم امن است)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

from app import app  # noqa: E402

if __name__ == '__main__':
    app.run()
