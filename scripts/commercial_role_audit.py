#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""خزش تجاری نقش‌محور روی دیتابیس موقت و داده کامل.

برخلاف smoke test ساده، لینک‌های واقعی HTML و فایل‌های static را با هفت نقش
می‌خواند و هر 404/500 یا لینک قابل‌کلیک منتهی به 403 را خطا می‌گیرد.
هیچ داده‌ای در دیتابیس اصلی تغییر نمی‌کند.

اجرا:
    python scripts/commercial_role_audit.py
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys
import tempfile
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_tmp = tempfile.NamedTemporaryFile(prefix='academy-commercial-', suffix='.db', delete=False)
_tmp.close()
DB_PATH = _tmp.name
os.environ['DATABASE_URL'] = 'sqlite:///' + DB_PATH
os.environ['ENABLE_DEMO_FEATURES'] = '1'
os.environ['FLASK_ENV'] = 'development'
os.environ['APP_ENV'] = 'development'
os.environ.setdefault('SECRET_KEY', 'commercial-audit-only-secret-key')

from app import app  # noqa: E402
from models import Setting, User, db  # noqa: E402
from seed import seed, seed_pages  # noqa: E402

app.config.update(TESTING=True, INSTALL_GUARD=False)

PUBLIC_STARTS = [
    '/', '/courses', '/products', '/teachers', '/blog', '/about', '/contact',
    '/faq', '/learning-paths', '/consultation', '/bundles', '/success-stories',
    '/verify-certificate', '/become-teacher', '/terms', '/privacy',
]
ROLE_STARTS = {
    'guest': PUBLIC_STARTS + ['/auth/login', '/auth/register', '/cart'],
    'student': [
        '/dashboard', '/dashboard/my-courses', '/dashboard/orders',
        '/dashboard/tickets', '/dashboard/profile', '/community/',
        '/community/messages', '/community/live', '/dashboard/notifications',
        '/dashboard/wallet', '/dashboard/study-plan',
    ] + PUBLIC_STARTS,
    'teacher': [
        '/teacher-panel/', '/teacher-panel/courses', '/teacher-panel/students',
        '/teacher-panel/assignments', '/teacher-panel/questions',
        '/teacher-panel/revenue', '/dashboard',
    ] + PUBLIC_STARTS,
    'admin': [
        '/admin/', '/admin/go-live', '/admin/users', '/admin/courses',
        '/admin/orders', '/admin/designs', '/admin/super-settings', '/builder',
        '/admin/seo/',
    ] + PUBLIC_STARTS,
    'secretary': [
        '/admin/', '/admin/users', '/admin/orders', '/admin/consultations',
        '/admin/live-sessions',
    ],
    'support': [
        '/admin/', '/admin/users', '/admin/tickets', '/admin/canned-replies',
        '/admin/chat',
    ],
    'operator': ['/admin/', '/admin/orders', '/admin/proofs', '/admin/sms'],
}

_HREF_RE = re.compile(r'''(?<![\w-])href=["']([^"']+)["']''', re.I)
_SRC_RE = re.compile(r'''(?<![\w-])src=["']([^"']+)["']''', re.I)
_SKIP_PATHS = ('/auth/logout', '/admin/impersonate/exit')


def _prepare_database():
    with app.app_context():
        db.create_all()
        seed()
        seed_pages()
        active = db.session.get(Setting, 'site_active')
        if active:
            active.value = '1'
        else:
            db.session.add(Setting(key='site_active', value='1'))
        for index, role in enumerate(('secretary', 'support', 'operator'), start=1):
            if not User.query.filter_by(role=role).first():
                user = User(
                    name='ممیزی ' + role, email=f'{role}@commercial-audit.local',
                    phone=f'0912999900{index}', role=role, is_active=True,
                )
                user.set_password('AuditOnly123!')
                db.session.add(user)
        db.session.commit()


def _role_sessions():
    users = {}
    with app.app_context():
        for role in ('admin', 'teacher', 'student', 'secretary', 'support', 'operator'):
            condition = (User.role.in_(['admin', 'super_admin'])
                         if role == 'admin' else User.role == role)
            user = User.query.filter(condition).first()
            if not user:
                raise RuntimeError(f'حساب نقش {role} ساخته نشد')
            users[role] = (user.id, user.session_token)
    return users


def _same_site_url(current_path, value):
    value = (value or '').strip()
    if not value or value.startswith(('#', 'mailto:', 'tel:', 'javascript:', 'data:')):
        return None
    parsed = urllib.parse.urlsplit(
        urllib.parse.urljoin('http://audit.local' + current_path, value))
    if parsed.netloc != 'audit.local':
        return None
    return parsed.path + (('?' + parsed.query) if parsed.query else '')


def crawl_role(role, starts, users):
    client = app.test_client()
    if role != 'guest':
        uid, token = users[role]
        with client.session_transaction() as session:
            session['uid'] = uid
            if token:
                session['st'] = token

    queue = collections.deque((path, 'START') for path in starts)
    seen = set()
    assets = set()
    issues = []
    statuses = collections.Counter()

    while queue and len(seen) < 900:
        path, source = queue.popleft()
        parsed = urllib.parse.urlsplit(path)
        path = parsed.path + (('?' + parsed.query) if parsed.query else '')
        if path in seen or any(parsed.path.startswith(item) for item in _SKIP_PATHS):
            continue
        seen.add(path)
        try:
            response = client.get(path, follow_redirects=False)
        except Exception as exc:  # TESTING=True exceptions bubble up
            issues.append(dict(status='EXCEPTION', path=path, source=source,
                               detail=f'{type(exc).__name__}: {exc}'))
            continue
        statuses[response.status_code] += 1
        if (response.status_code >= 500 or response.status_code == 404 or
                (response.status_code == 403 and source != 'START')):
            issues.append(dict(status=response.status_code, path=path, source=source))

        if response.status_code != 200 or 'text/html' not in response.content_type:
            continue
        html = response.get_data(as_text=True)
        for href in _HREF_RE.findall(html):
            target = _same_site_url(parsed.path, href)
            if target and target not in seen:
                queue.append((target, path))
        for src in _SRC_RE.findall(html):
            target = _same_site_url(parsed.path, src)
            if target and target.startswith('/static/'):
                assets.add((target, path))

    for asset, source in sorted(assets):
        response = client.get(asset)
        if response.status_code != 200:
            issues.append(dict(status=response.status_code, path=asset,
                               source=source, kind='asset'))
    return dict(visited=len(seen), assets=len(assets), statuses=dict(statuses),
                issues=issues)


def main():
    try:
        _prepare_database()
        users = _role_sessions()
        results = {}
        failures = 0
        for role, starts in ROLE_STARTS.items():
            result = crawl_role(role, starts, users)
            results[role] = result
            failures += len(result['issues'])
            print(
                f"{role:10} pages={result['visited']:>3} assets={result['assets']:>3} "
                f"statuses={result['statuses']} issues={len(result['issues'])}"
            )
            for issue in result['issues'][:20]:
                print(f"  {issue['status']} {issue['path']}  ← {issue['source']}")
        total_pages = sum(row['visited'] for row in results.values())
        total_assets = sum(row['assets'] for row in results.values())
        print(f'\nTOTAL pages={total_pages} assets={total_assets} issues={failures}')
        report_path = os.environ.get('COMMERCIAL_AUDIT_REPORT')
        if report_path:
            Path(report_path).write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        return 1 if failures else 0
    finally:
        try:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        except Exception:
            pass
        for suffix in ('', '-wal', '-shm'):
            try:
                os.remove(DB_PATH + suffix)
            except OSError:
                pass


if __name__ == '__main__':
    raise SystemExit(main())
