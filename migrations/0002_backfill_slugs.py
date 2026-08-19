# -*- coding: utf-8 -*-
"""0002 — تعمیر اسلاگ‌های خالی/تکراری دوره، محصول و وبلاگ (ضد لینک 404).

در دیتابیس‌های قدیمی که ستون slug بعداً اضافه شده، رکوردهای قدیمی ممکن است
اسلاگ خالی یا NULL داشته باشند و لینک «/course/» یا «/product/» به 404 برسد.
این مایگریشن برای هر رکورد بدون اسلاگ، از عنوان اسلاگ یکتا می‌سازد و
اسلاگ‌های تکراری را با پسوند عددی اصلاح می‌کند — بدون حذف یا تغییر هیچ
دادهٔ دیگری. Idempotent: اجرای دوباره تغییری ایجاد نمی‌کند.
"""
import re

from sqlalchemy import inspect, text


def _slugify(title, fallback):
    text = str(title or '').strip()
    if not text:
        return fallback
    slug = re.sub(r'[^\w\u0600-\u06FF\-]+', '-', text.replace(' ', '-'))
    slug = re.sub(r'-{2,}', '-', slug).strip('-')
    if not slug or set(slug) == {'-'}:
        return fallback
    return slug[:220] or fallback


def _fix_table(conn, table, title_col='title', fallback='item'):
    inspector = inspect(conn)
    names = set(inspector.get_table_names())
    if table not in names:
        return 0
    columns = {c['name'] for c in inspector.get_columns(table)}
    if 'slug' not in columns or 'id' not in columns or title_col not in columns:
        return 0
    rows = conn.execute(text(
        'SELECT id, {} FROM {} WHERE slug IS NULL OR slug = \'\' '
        'ORDER BY id'.format(title_col, table))).fetchall()
    if not rows:
        return 0
    # اسلاگ‌های موجود برای یکتاسازی
    taken = set()
    try:
        for (slug,) in conn.execute(text('SELECT slug FROM {} WHERE slug IS NOT NULL AND slug != \'\''.format(table))):
            taken.add(slug)
    except Exception:
        pass
    fixed = 0
    for row_id, title in rows:
        base = _slugify(title, fallback)
        candidate = base
        n = 2
        while candidate in taken:
            candidate = '{}-{}'.format(base[:216], n)
            n += 1
        taken.add(candidate)
        conn.execute(text('UPDATE {} SET slug = :slug WHERE id = :rid'.format(table)),
                     {'slug': candidate, 'rid': row_id})
        fixed += 1
    return fixed


def _dedupe_table(conn, table):
    """اصلاح اسلاگ‌های تکراری (هر اسلاگ فقط یک رکورد؛ بقیه پسوند می‌گیرند)."""
    inspector = inspect(conn)
    names = set(inspector.get_table_names())
    if table not in names:
        return 0
    columns = {c['name'] for c in inspector.get_columns(table)}
    if 'slug' not in columns or 'id' not in columns:
        return 0
    rows = conn.execute(text(
        'SELECT id, slug FROM {} WHERE slug IS NOT NULL AND slug != \'\' '
        'ORDER BY id'.format(table))).fetchall()
    seen = {}
    fixed = 0
    for row_id, slug in rows:
        if slug in seen:
            base = slug[:216]
            n = 2
            while '{}-{}'.format(base, n) in seen:
                n += 1
            new_slug = '{}-{}'.format(base, n)
            seen[new_slug] = row_id
            conn.execute(text('UPDATE {} SET slug = :slug WHERE id = :rid'.format(table)),
                         {'slug': new_slug, 'rid': row_id})
            fixed += 1
        else:
            seen[slug] = row_id
    return fixed


def up(conn):
    total = 0
    total += _fix_table(conn, 'courses', 'title', 'course')
    total += _fix_table(conn, 'products', 'title', 'product')
    total += _fix_table(conn, 'blog_posts', 'title', 'post')
    total += _dedupe_table(conn, 'courses')
    total += _dedupe_table(conn, 'products')
    total += _dedupe_table(conn, 'blog_posts')
