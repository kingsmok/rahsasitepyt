#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""خزش مسیرهای واقعی سایت بدون حساب یا دادهٔ نمایشی.

این فایل با الگوی نام قدیمی ``*_test.py`` حفظ شده، اما هنگام import/pytest هیچ
درخواستی اجرا نمی‌کند. اجرا فقط با دستور مستقیم انجام می‌شود:

    HEALTH_BASE_URL=https://example.com python scripts/full_route_test.py
"""
import os
import re
import sys
from urllib.parse import urlparse

import requests


BASE = os.environ.get('HEALTH_BASE_URL', 'http://localhost:5000').rstrip('/')
TIMEOUT = int(os.environ.get('HEALTH_TIMEOUT', '20'))
ALLOWED = (200, 301, 302, 308)


def _same_site_path(url):
    parsed = urlparse(url)
    base = urlparse(BASE)
    if parsed.netloc and parsed.netloc != base.netloc:
        return None
    path = parsed.path or '/'
    return path + (('?' + parsed.query) if parsed.query else '')


def main():
    session = requests.Session()
    paths = {
        '/', '/health', '/courses', '/products', '/about', '/contact', '/faq',
        '/terms', '/privacy', '/blog', '/teachers', '/verify-certificate',
        '/consultation', '/learning-paths', '/bundles', '/become-teacher',
        '/sitemap.xml', '/robots.txt', '/auth/login', '/auth/register', '/cart',
    }

    # URLهای واقعی منتشرشده را از sitemap بخوان؛ هیچ slug یا شناسه ساختگی نداریم.
    try:
        sitemap = session.get(BASE + '/sitemap.xml', timeout=TIMEOUT)
        if sitemap.status_code == 200:
            for loc in re.findall(r'<loc>(.*?)</loc>', sitemap.text):
                path = _same_site_path(loc)
                if path:
                    paths.add(path)
    except Exception as exc:
        print('WARN sitemap:', exc)

    failures = []
    for path in sorted(paths):
        try:
            response = session.get(BASE + path, allow_redirects=False, timeout=TIMEOUT)
            state = 'OK' if response.status_code in ALLOWED else 'FAIL'
            print(f'{state:4} {response.status_code:>3} {path}')
            if response.status_code not in ALLOWED:
                failures.append((response.status_code, path))
        except Exception as exc:
            print(f'FAIL ERR {path}: {exc}')
            failures.append(('ERR', path))

    print(f'\n{len(paths)} مسیر بررسی شد؛ {len(failures)} خطا.')
    for code, path in failures:
        print(f'  {code}  {path}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
