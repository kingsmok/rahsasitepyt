# -*- coding: utf-8 -*-
"""اجرای مایگریشن با کد تازهٔ checkout شده.

این فایل عمداً یک process جداست و updater بعد از git reset آن را اجرا می‌کند؛
در نتیجه ``models.py`` از نسخهٔ جدید import می‌شود، نه نسخه‌ای که از قبل در
حافظهٔ Worker وب مانده است.

روی ویندوز کنسول پیش‌فرض اغلب cp1252 است و چاپ فارسی/خط تیرهٔ فارسی
``UnicodeEncodeError`` می‌داد — در حالی که خود مایگریشن موفق بود. updater
خروج غیرصفر را شکست می‌دید و کل بروزرسانی را rollback می‌کرد.
"""
import glob
import os
import sqlite3
import sys
import traceback
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def configure_stdio():
    """خروجی را UTF-8 کن تا چاپ فارسی روی ویندوز/هاست هیچ‌وقت مایگریشن را نکشد."""
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    os.environ.setdefault('PYTHONUTF8', '1')
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


def safe_print(msg):
    """چاپ مقاوم: شکست encoding هرگز باعث exit code غیرصفر نمی‌شود."""
    text = str(msg)
    if not text.endswith('\n'):
        text += '\n'
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.write(text)
            stream.flush()
            return True
        except Exception:
            pass
        try:
            buf = getattr(stream, 'buffer', None)
            if buf is not None:
                buf.write(text.encode('utf-8', errors='replace'))
                buf.flush()
                return True
        except Exception:
            pass
    try:
        sys.stdout.write(text.encode('ascii', 'replace').decode('ascii'))
        return True
    except Exception:
        return False


def database_kind(uri):
    """تشخیص موتور دیتابیس از URI فلاسک — sqlite / mysql / other."""
    value = str(uri or '').strip().lower()
    if value.startswith('mysql'):
        return 'mysql'
    if value.startswith('postgres') or value.startswith('postgresql'):
        return 'postgresql'
    if value.startswith('sqlite') or not value:
        return 'sqlite'
    return 'other'


def _sqlite_backup(app):
    """قبل از DDL یک snapshot امن از SQLite/WAL بساز؛ MySQL بکاپ خارجی می‌خواهد."""
    url = str(app.config.get('SQLALCHEMY_DATABASE_URI') or '')
    if not url.startswith('sqlite'):
        return 'بکاپ فایل فقط برای SQLite است؛ MySQL/phpMyAdmin از خود هاست بکاپ بگیرید.'
    try:
        from sqlalchemy.engine import make_url
        db_path = make_url(url).database
    except Exception:
        db_path = None
    if not db_path or db_path == ':memory:':
        return 'SQLite حافظه‌ای است؛ فایل بکاپ لازم نیست.'
    if not os.path.isabs(db_path):
        db_path = os.path.join(ROOT, db_path)
    db_path = os.path.abspath(db_path)
    if not os.path.exists(db_path):
        return 'فایل SQLite هنوز وجود ندارد؛ بکاپ لازم نیست.'

    backup_dir = os.path.join(ROOT, 'instance', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    destination = os.path.join(backup_dir, 'academy-update-{}.db'.format(stamp))
    source = destination_conn = None
    try:
        # sqlite backup API فایل اصلی و WAL را سازگار و اتمیک snapshot می‌کند.
        source = sqlite3.connect(db_path, timeout=30)
        destination_conn = sqlite3.connect(destination)
        source.backup(destination_conn)
        destination_conn.close()
        destination_conn = None
        source.close()
        source = None
    except Exception:
        if destination_conn is not None:
            destination_conn.close()
        if source is not None:
            source.close()
        try:
            os.remove(destination)
        except OSError:
            pass
        raise

    # جلوگیری از رشد نامحدود پوشهٔ backup؛ بکاپ‌های دستی حذف نمی‌شوند.
    files = sorted(glob.glob(os.path.join(backup_dir, 'academy-update-*.db')),
                   key=os.path.getmtime, reverse=True)
    for old in files[5:]:
        try:
            os.remove(old)
        except OSError:
            pass
    return 'بکاپ SQLite ساخته شد: ' + os.path.basename(destination)


def main():
    os.chdir(ROOT)
    # import app تمام مدل‌های ext_models را نیز ثبت می‌کند.
    from app import app
    from updater import _migrate_db
    with app.app_context():
        kind = database_kind(app.config.get('SQLALCHEMY_DATABASE_URI'))
        backup_msg = _sqlite_backup(app)
        migration_msg = _migrate_db()
        safe_print('[{}] {} | {}'.format(kind, backup_msg, migration_msg))


if __name__ == '__main__':
    configure_stdio()
    try:
        main()
    except Exception:
        try:
            traceback.print_exc()
        except Exception:
            pass
        raise SystemExit(1)
