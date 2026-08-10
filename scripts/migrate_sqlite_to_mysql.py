#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مهاجرت داده از SQLite به MySQL — انتقال کامل همه جدول‌ها

استفاده:
    # ۱) ابتدا دیتابیس MySQL را در هاست بسازید (utf8mb4)
    # ۲) فایل .env را با DATABASE_URL مای‌اسکیول ست کنید:
    #    DATABASE_URL=mysql+pymysql://USER:PASS@HOST:3306/DBNAME?charset=utf8mb4
    # ۳) این اسکریپت را اجرا کنید (دیتابیس MySQL را کامل می‌سازد):
    python3 scripts/migrate_sqlite_to_mysql.py
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE, '.env'))

# ── مبدا: SQLite فعلی (داده‌های واقعی) ──
SQLITE_PATH = os.path.join(BASE, 'instance', 'academy.db')
if not os.path.exists(SQLITE_PATH):
    sys.exit(f'دیتابیس SQLite پیدا نشد: {SQLITE_PATH}')

MYSQL_URL = os.environ.get('DATABASE_URL', '')
if not MYSQL_URL.startswith('mysql'):
    sys.exit('DATABASE_URL در .env باید mysql+pymysql://... باشد — ابتدا تنظیم کنید.')

import sqlite3
from sqlalchemy import create_engine, text, insert

src = sqlite3.connect(SQLITE_PATH)
dst = create_engine(MYSQL_URL, pool_pre_ping=True)

# ── ۱) حذف جدول‌های قبلی (اگر مهاجرت قبلی ناقص مانده) + ساخت از مدل‌ها ──
from app import app
from models import db
import sqlalchemy as _sa

def drop_all_mysql(engine):
    """حذف همه جدول‌های موجود در MySQL — شروع تمیز"""
    insp = _sa.inspect(engine)
    for t in insp.get_table_names():
        try:
            with engine.begin() as conn:
                conn.execute(text(f'SET FOREIGN_KEY_CHECKS=0'))
                conn.execute(text(f'DROP TABLE IF EXISTS `{t}`'))
                conn.execute(text(f'SET FOREIGN_KEY_CHECKS=1'))
        except Exception:
            pass

drop_all_mysql(dst)
with app.app_context():
    db.create_all()

# ── ۲) کپی داده‌ها با ترتیب وابستگی FK (جدول‌های بدون ارجاع اول) ──
def table_order(engine):
    """مرتب‌سازی توپولوژیک جدول‌ها بر اساس FK"""
    import sqlalchemy
    insp = sqlalchemy.inspect(engine)
    names = set(insp.get_table_names())
    fk_map = {}
    for t in names:
        fks = set()
        for fk in insp.get_foreign_keys(t):
            fks.add(fk['referred_table'])
        fk_map[t] = fks & names
    ordered, seen = [], set()
    def visit(t, stack):
        if t in seen:
            return
        if t in stack:
            return  # حلقه — نادیده
        stack.add(t)
        for dep in sorted(fk_map.get(t, ())):
            visit(dep, stack)
        stack.discard(t)
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    for t in sorted(names):
        visit(t, set())
    return ordered

import sqlalchemy as _sa
insp = _sa.inspect(dst)
mysql_tables = set(insp.get_table_names())
tables = table_order(dst)
metadata = db.metadata

SKIP = {'alembic_version', 'sqlite_sequence'}
total = 0
with dst.begin() as conn:
    # پاکسازی کامل اگر قبلاً داده هست (اجرای مجدد امن)
    try:
        conn.execute(text('SET FOREIGN_KEY_CHECKS=0'))
    except Exception:
        pass
    for t in reversed(tables):
        if t in SKIP:
            continue
        conn.execute(text(f'DELETE FROM `{t}`'))
    for t in tables:
        if t in SKIP or t not in metadata.tables:
            continue
        tbl = metadata.tables[t]
        cols = [r[1] for r in src.execute(f'PRAGMA table_info("{t}")')]
        if not cols:
            continue
        rows = src.execute(f'SELECT * FROM "{t}"').fetchall()
        if not rows:
            continue
        # حذف ستون‌هایی که در MySQL نیستند
        mcols = {c['name'] for c in insp.get_columns(t)}
        cols = [c for c in cols if c in mcols]
        if not cols:
            continue
        sql = insert(tbl)
        batch = []
        for r in rows:
            vals = {}
            for i, c in enumerate(cols):
                v = r[i] if i < len(r) else None
                if isinstance(v, bytes):
                    v = v.decode('utf-8', errors='replace')
                vals[c] = v
            batch.append(vals)
            if len(batch) >= 500:
                conn.execute(sql, batch)
                total += len(batch)
                batch = []
        if batch:
            conn.execute(sql, batch)
            total += len(batch)
        print(f'  ✅ {t}: {len(rows)} ردیف')
    try:
        conn.execute(text('SET FOREIGN_KEY_CHECKS=1'))
    except Exception:
        pass

print(f'\n🎉 مهاجرت کامل شد — {total} ردیف به MySQL منتقل شد.')
print(f'   حالا با DATABASE_URL ست‌شده، اپ روی MySQL اجرا می‌شود.')
