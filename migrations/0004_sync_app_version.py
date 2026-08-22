# -*- coding: utf-8 -*-
"""0004 — همگام‌سازی ``settings.app_version`` با ``version.txt``.

نسخهٔ نمایشی پنل را با فایل انتشار یکی می‌کند. اگر جدول/ستون موجود نباشد
کاری نمی‌کند. Idempotent: اجرای دوباره فقط همان مقدار را می‌نویسد.
"""
import os

from sqlalchemy import inspect, text


def _version_from_file():
    here = os.path.abspath(globals().get('__file__') or os.getcwd())
    root = os.path.dirname(os.path.dirname(here))
    path = os.path.join(root, 'version.txt')
    try:
        with open(path, encoding='utf-8') as handle:
            lines = (handle.read() or '').strip().splitlines()
        value = lines[0].strip() if lines else ''
    except OSError:
        value = ''
    return value[:64] if value else '1.5.1'


def up(conn):
    inspector = inspect(conn)
    names = set(inspector.get_table_names())
    if 'settings' not in names:
        return
    columns = {c['name'] for c in inspector.get_columns('settings')}
    if 'key' not in columns or 'value' not in columns:
        return
    version = _version_from_file()
    row = conn.execute(
        text("SELECT 1 FROM settings WHERE key = 'app_version'")).first()
    if row:
        conn.execute(
            text("UPDATE settings SET value = :v WHERE key = 'app_version'"),
            {'v': version})
    else:
        try:
            conn.execute(text(
                "INSERT INTO settings (key, value) VALUES ('app_version', :v)"),
                {'v': version})
        except Exception:
            pass
