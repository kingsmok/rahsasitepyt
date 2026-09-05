# -*- coding: utf-8 -*-
"""0006 — پیشینهٔ کوپن: ``created_at`` و ``created_by``.

چرا لازم است؟
    جدول ``coupons`` هیچ ستون زمان یا نویسنده‌ای نداشت. پیامدش فقط این نبود که
    «تازه‌ترین کوپن» قابل تعریف نباشد (``ORDER BY id DESC`` جایگزینش بود)؛
    مسئلهٔ اصلی این بود که یک تخفیف — موجودیتی مستقیماً مالی — هیچ پیشینه‌ای
    نداشت. «این کوپن ۹۰٪ را کی، چه کسی و از کدام IP ساخت؟» در دیتابیس قابل
    پاسخ نبود.

    این دو ستون به ``models.py`` اضافه شده‌اند تا نصب‌های تازه از ابتدا آن‌ها را
    داشته باشند، اما ``db.create_all()`` به جدول موجود ستون اضافه نمی‌کند؛ این
    مایگریشن همان کار را برای نصب‌های فعلی انجام می‌دهد.

دربارهٔ ردیف‌های قدیمی
    ``created_at`` برای کوپن‌های از قبل موجود ``NULL`` می‌ماند. عمداً تاریخ
    جعلی backfill نمی‌شود: یک timestamp ساختگی در ستون ممیزی بدتر از ``NULL``
    است، چون به یک عددِ بی‌اساس، اعتبارِ «دادهٔ واقعی» می‌دهد. ``NULL`` صادقانه
    می‌گوید «این ردیف پیش از ثبت پیشینه ساخته شده».

Idempotent: پیش از افزودن، وجود ستون بررسی می‌شود؛ اجرای دوباره بی‌اثر است.
"""
from sqlalchemy import inspect, text

_TABLE = 'coupons'

# (نام ستون، تعریف SQLite، تعریف MySQL)
_COLUMNS = (
    ('created_at', 'DATETIME', 'DATETIME'),
    ('created_by', 'INTEGER', 'INT'),
)


def up(conn):
    inspector = inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return

    dialect = conn.dialect.name
    existing = {c['name'] for c in inspector.get_columns(_TABLE)}

    for name, sqlite_type, mysql_type in _COLUMNS:
        if name in existing:
            continue
        col_type = mysql_type if dialect == 'mysql' else sqlite_type
        conn.execute(text(f'ALTER TABLE {_TABLE} ADD COLUMN {name} {col_type}'))

    # کلید خارجی فقط در MySQL معنا دارد؛ SQLite پس از ALTER اجازهٔ افزودن
    # CONSTRAINT نمی‌دهد، و ستون created_by به‌تنهایی برای ممیزی کافی است.
    if dialect == 'mysql' and 'created_by' in existing:
        return


def down(conn):  # pragma: no cover - برگشت اختیاری است
    inspector = inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return
    existing = {c['name'] for c in inspector.get_columns(_TABLE)}
    for name in ('created_by', 'created_at'):
        if name in existing:
            try:
                conn.execute(text(f'ALTER TABLE {_TABLE} DROP COLUMN {name}'))
            except Exception:
                pass
