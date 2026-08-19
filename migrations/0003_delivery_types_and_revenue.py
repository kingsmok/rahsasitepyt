# -*- coding: utf-8 -*-
"""0003 — نوع برگزاری ۴تایی + سهم درآمد مدرس (دسته ۴: LMS).

تغییرات داده‌ای (ساختار ستون‌ها خودکار توسط _migrate_db اضافه می‌شود):
  1. تبدیل delivery_type قدیمی: مقدار 'offline' در نسخه‌های قبلی در رابط
     کاربری «حضوری» نمایش داده می‌شد؛ حالا به 'inperson' تبدیل می‌شود تا
     ۴ نوع مجزا (حضوری/آنلاین/آفلاین/ترکیبی) معنای درست داشته باشند.
  2. پر کردن revenue_percent دوره‌ها از پیش‌فرض سایت (teacher_default_share)
     تا فیلد سهم مدرس در فرم دوره مقدار مشخص داشته باشد.
Idempotent: اجرای دوباره تغییری ایجاد نمی‌کند.
"""
from sqlalchemy import inspect, text


def _setting(conn, key, default):
    try:
        row = conn.execute(text('SELECT value FROM settings WHERE key = :k'),
                           {'k': key}).first()
        if row and str(row[0] or '').isdigit():
            return int(row[0])
    except Exception:
        pass
    return default


def up(conn):
    inspector = inspect(conn)
    names = set(inspector.get_table_names())
    if 'courses' in names:
        columns = {c['name'] for c in inspector.get_columns('courses')}
        if 'delivery_type' in columns:
            conn.execute(text(
                "UPDATE courses SET delivery_type = 'inperson' "
                "WHERE delivery_type = 'offline'"))
        if 'revenue_percent' in columns:
            default_share = max(0, min(100, _setting(conn, 'teacher_default_share', 50)))
            conn.execute(text(
                "UPDATE courses SET revenue_percent = :s WHERE revenue_percent IS NULL"),
                {'s': default_share})
