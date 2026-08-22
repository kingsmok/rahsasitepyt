# -*- coding: utf-8 -*-
"""0005 — ایندکس‌های کارایی روی کلیدهای خارجی پرترافیک.

چرا لازم است؟
    چند جدول که با رشد سایت بزرگ می‌شوند (لاگ امتیاز، پیام پشتیبانی، پیام
    خصوصی، روزهای مطالعه) روی ستون user_id/recipient_id فیلتر می‌شدند بدون
    اینکه ایندکسی وجود داشته باشد. در SQLite و MySQL نتیجه یک full-table
    scan در هر بارگذاری داشبورد و هدر بود؛ روی دیتابیس چندهزارردیفی این
    هزینه به‌سرعت محسوس می‌شود.

    تعریف ایندکس‌ها به models.py اضافه شده تا نصب‌های تازه از ابتدا آن‌ها را
    داشته باشند، اما db.create_all() روی جدول‌هایی که از قبل وجود دارند
    ایندکس جدید نمی‌سازد. این مایگریشن همان کار را برای نصب‌های موجود
    انجام می‌دهد.

Idempotent: از CREATE INDEX IF NOT EXISTS استفاده می‌شود و پیش از آن وجود
جدول و ستون‌ها بررسی می‌شود؛ اجرای دوباره بی‌اثر است.
"""
from sqlalchemy import inspect, text


# (نام ایندکس، نام جدول، ستون‌ها)
_INDEXES = (
    ('idx_pointlog_user', 'point_logs', ('user_id',)),
    ('idx_chat_user_created', 'chat_messages', ('user_id', 'created_at')),
    ('idx_studyday_user_day', 'study_days', ('user_id', 'day')),
    ('idx_pm_recipient', 'private_messages', ('recipient_id', 'is_read')),
    ('idx_pm_sender', 'private_messages', ('sender_id',)),
)


def up(conn):
    inspector = inspect(conn)
    table_names = set(inspector.get_table_names())

    for index_name, table, columns in _INDEXES:
        # جدول ممکن است در نسخه‌های قدیمی‌تر هنوز ساخته نشده باشد.
        if table not in table_names:
            continue

        # اگر ستونی وجود نداشته باشد (نصب قدیمی با اسکیمای متفاوت)، از این
        # ایندکس صرف‌نظر می‌کنیم تا کل بروزرسانی به‌خاطر آن متوقف نشود.
        existing_columns = {c['name'] for c in inspector.get_columns(table)}
        if not set(columns).issubset(existing_columns):
            continue

        # اگر ایندکسی با همین نام از قبل باشد، دوباره ساخته نمی‌شود.
        existing_indexes = {i['name'] for i in inspector.get_indexes(table)}
        if index_name in existing_indexes:
            continue

        column_list = ', '.join(columns)
        try:
            # IF NOT EXISTS در SQLite و MySQL 8+ پشتیبانی می‌شود؛ برای
            # نسخه‌های قدیمی‌تر MySQL، بررسی existing_indexes بالا نقش
            # همان گارد را ایفا می‌کند.
            conn.execute(text(
                f'CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column_list})'))
        except Exception:
            # ساخت ایندکس یک بهینه‌سازی است، نه یک تغییر دادهٔ حیاتی.
            # اگر موتور دیتابیس گرامر IF NOT EXISTS را نپذیرد، بدون آن
            # تلاش می‌کنیم و در نهایت بی‌صدا رد می‌شویم تا بروزرسانی سایت
            # به‌خاطر یک ایندکس شکست نخورد.
            try:
                conn.execute(text(
                    f'CREATE INDEX {index_name} ON {table} ({column_list})'))
            except Exception:
                pass
