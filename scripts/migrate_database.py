# -*- coding: utf-8 -*-
"""اجرای مایگریشن با کد تازهٔ checkout شده.

این فایل عمداً یک process جداست و updater بعد از git reset آن را اجرا می‌کند؛
در نتیجه ``models.py`` از نسخهٔ جدید import می‌شود، نه نسخه‌ای که از قبل در
حافظهٔ Worker وب مانده است.
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
os.chdir(ROOT)


def _sqlite_backup(app):
    """قبل از DDL یک snapshot امن از SQLite/WAL بساز؛ MySQL بکاپ خارجی می‌خواهد."""
    url = str(app.config.get('SQLALCHEMY_DATABASE_URI') or '')
    if not url.startswith('sqlite'):
        return 'بکاپ خودکار فایل فقط برای SQLite انجام می‌شود.'
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
    # import app تمام مدل‌های ext_models را نیز ثبت می‌کند.
    from app import app
    from updater import _migrate_db
    with app.app_context():
        backup_msg = _sqlite_backup(app)
        migration_msg = _migrate_db()
        print(backup_msg + ' — ' + migration_msg)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
