#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بررسی سلامت سایت بدون وابستگی به حساب یا دادهٔ نمایشی.

استفاده:
    HEALTH_BASE_URL=https://example.com python scripts/health_check.py

برای بررسی اختیاری یک حساب واقعیِ مخصوص مانیتورینگ، متغیرهای HEALTH_EMAIL و
HEALTH_PASSWORD را فقط در محیط سرور تنظیم کنید. هیچ رمز پیش‌فرضی در کد نیست.
"""
import os
import re
import sys

import requests

BASE = os.environ.get('HEALTH_BASE_URL', 'http://localhost:5000').rstrip('/')
EMAIL = os.environ.get('HEALTH_EMAIL', '').strip()
PASSWORD = os.environ.get('HEALTH_PASSWORD', '')
TIMEOUT = int(os.environ.get('HEALTH_TIMEOUT', '20'))

session = requests.Session()
results = {}


def get(path):
    return session.get(BASE + path, allow_redirects=False, timeout=TIMEOUT)


def csrf_from(response):
    match = re.search(r'name="_csrf_token" value="([^"]+)"', response.text)
    return match.group(1) if match else ''


def check(path, allowed=(200, 301, 302, 308)):
    try:
        response = get(path)
        results[path] = response.status_code
        if response.status_code not in allowed:
            print(f'FAIL {response.status_code:>3}  {path}')
        else:
            print(f' OK  {response.status_code:>3}  {path}')
        return response
    except Exception as exc:
        results[path] = f'ERR {exc}'
        print(f'FAIL ERR  {path}: {exc}')
        return None


# مسیرهای عمومی باید بدون هیچ دادهٔ اولیه‌ای سالم باشند.
public_routes = [
    '/', '/courses', '/products', '/about', '/contact', '/faq', '/terms',
    '/privacy', '/blog', '/teachers', '/verify-certificate', '/consultation',
    '/learning-paths', '/sitemap.xml', '/robots.txt', '/become-teacher',
    '/bundles', '/placement-test', '/health',
]
for route in public_routes:
    check(route)

# ورود اختیاری فقط با حساب واقعیِ داده‌شده از محیط. OTP هرگز از HTML خوانده نمی‌شود.
if EMAIL and PASSWORD:
    login_page = get('/auth/login')
    token = csrf_from(login_page)
    if not token:
        results['AUTH'] = 'ERR CSRF not found'
        print('FAIL AUTH: توکن فرم ورود پیدا نشد')
    else:
        response = session.post(
            BASE + '/auth/login',
            data={'_csrf_token': token, 'email': EMAIL, 'password': PASSWORD},
            allow_redirects=False, timeout=TIMEOUT,
        )
        location = response.headers.get('Location', '')
        if response.status_code not in (301, 302):
            results['AUTH'] = response.status_code
            print(f'FAIL AUTH: {response.status_code}')
        elif '/admin-2fa' in location:
            # رفتار درست و امن: ادامه فقط با پیامک واقعی کاربر انجام می‌شود.
            results['AUTH'] = '2FA_REQUIRED'
            print(' OK  AUTH: ورود اولیه صحیح است؛ تایید دومرحله‌ای واقعی لازم است')
        else:
            results['AUTH'] = 'OK'
            print(' OK  AUTH: حساب مانیتورینگ وارد شد')
            for route in ('/dashboard', '/dashboard/profile', '/dashboard/orders',
                          '/dashboard/tickets', '/dashboard/my-courses'):
                check(route)
else:
    print('INFO بررسی ورود اجرا نشد؛ HEALTH_EMAIL/HEALTH_PASSWORD تنظیم نشده است.')

bad = {path: code for path, code in results.items()
       if isinstance(code, str) and code.startswith('ERR') or
       isinstance(code, int) and code not in (200, 301, 302, 308)}
print(f'\n=== {len(results)} بررسی، {len(bad)} خطا ===')
for path, code in bad.items():
    print(f'  {code}  {path}')
sys.exit(1 if bad else 0)
