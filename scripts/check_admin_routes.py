# -*- coding: utf-8 -*-
"""بررسی تطابق جدول routeهای پنل مدیریت با نسخهٔ مرجع.

چرا این اسکریپت وجود دارد؟ وقتی ``blueprints/admin_bp.py`` به چند ماژول دامنه
تقسیم شد، دو خطر واقعی وجود داشت: route ای که جابه‌جا نمی‌شود (و بی‌صدا غیب
می‌شود) و decorator ای که حین جابه‌جایی پاک می‌شود. هیچ‌کدام با ۴۳۵ تست گرفتنی
نبودند، چون تست‌ها فقط routeهایی را می‌زنند که می‌شناسند.

این اسکریپت جدول route زندهٔ اپ را با تجزیهٔ ایستای یک فایل مرجع مقایسه می‌کند:

    python scripts/check_admin_routes.py                 # مرجع: HEAD در git
    python scripts/check_admin_routes.py path/to/old.py  # مرجع: یک فایل دلخواه

کد خروج ۰ یعنی هیچ route ای گم نشده. برای CI مناسب است.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

ROUTE_RE = re.compile(
    r"@admin_bp\.route\('([^']+)'(?:, methods=\[([^\]]*)\])?\)\s*\n"
    r"(?:@[^\n]+\n)*def (\w+)\(", re.M)


def live_routes() -> set[tuple[str, str, str]]:
    """جدول route واقعی، از خود Flask."""
    os.environ.setdefault('APP_ENV', 'testing')
    os.environ.setdefault('FLASK_ENV', 'testing')
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:  # ایزوله‌سازی از .env سرور — همان کاری که conftest می‌کند
        import dotenv
        dotenv.load_dotenv = lambda *a, **k: False
    except Exception:
        pass
    from app import create_app
    app = create_app()
    out = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith('admin.'):
            methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
            out.add((rule.endpoint, rule.rule, methods))
    return out


def static_routes(source: str) -> set[tuple[str, str, str]]:
    """جدول route از روی متن منبع — بدون اجرای آن."""
    out = set()
    for path, methods, fn in ROUTE_RE.findall(source):
        ms = sorted(x.strip().strip("'\"") for x in (methods or '').split(',')
                    if x.strip()) or ['GET']
        out.add(('admin.' + fn, path, ','.join(ms)))
    return out


def reference_source(argv: list[str]) -> str:
    if len(argv) > 1:
        with open(argv[1], encoding='utf-8') as fh:
            return fh.read()
    return subprocess.run(['git', 'show', 'HEAD:blueprints/admin_bp.py'],
                          capture_output=True, text=True, check=True).stdout


def main(argv: list[str]) -> int:
    live = live_routes()
    ref = static_routes(reference_source(argv))
    live_endpoints = {e for e, _r, _m in live}
    missing = sorted((e, r, m) for e, r, m in ref if e not in live_endpoints)

    print(f'live admin routes : {len(live)}')
    print(f'reference routes  : {len(ref)}')
    if missing:
        print('\nMISSING — این routeها در مرجع هستند ولی ثبت نشده‌اند:')
        for endpoint, rule, methods in missing:
            print(f'  {endpoint}  {rule}  [{methods}]')
        return 1
    print('\nOK — هیچ route ای گم نشده.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
