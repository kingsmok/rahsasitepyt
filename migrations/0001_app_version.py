# -*- coding: utf-8 -*-
"""0001 — ثبت نسخهٔ برنامه در تنظیمات (برای نمایش در پنل و دیباگ).

بدون تغییر هیچ دادهٔ موجود؛ فقط setting جدید ``app_version`` ساخته می‌شود.
اگر جدول settings هنوز وجود ندارد (نصب بسیار قدیمی)، کاری نمی‌کند —
``_migrate_db`` اول ساختار را با ``create_all`` می‌سازد.
"""
from sqlalchemy import inspect, text


def up(conn):
    inspector = inspect(conn)
    names = set(inspector.get_table_names())
    if 'settings' not in names:
        return
    columns = {c['name'] for c in inspector.get_columns('settings')}
    if 'key' not in columns or 'value' not in columns:
        return
    row = conn.execute(
        text("SELECT 1 FROM settings WHERE key = 'app_version'")).first()
    if not row:
        try:
            conn.execute(text(
                "INSERT INTO settings (key, value) VALUES ('app_version', :v)"),
                {'v': '1.5.0'})
        except Exception:
            # ممکن است جدول ستون value نداشته باشد؛ فقط از گزارش رد می‌شویم
            # تا بروزرسانی ساختار هرگز مسدود نشود.
            pass
