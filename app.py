# -*- coding: utf-8 -*-
"""آکادمی آنلاین — اسکریپت LMS آموزشی با Flask
اجرا:  python seed.py  (بار اول)
      python app.py   (شروع سرور)
"""
import os
import time
from datetime import datetime
try:
    from datetime import UTC
except ImportError:  # پایتون < 3.11 (هاست‌های اشتراکی)
    from datetime import timezone as _tz_utc
    UTC = _tz_utc.utc

# بارگذاری .env در صورت وجود (python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import hmac
from flask import Flask, g, request, session, redirect, url_for, abort, render_template
from models import utcnow, db, User, Setting, Category, Order, NewsletterEmail, Course
from jdates import (fa, fa_num, money, MONTHS, slugify, jdate, jdatetime, jdate_num, jtime,
                  jalali_to_gregorian, g2j, j2g)
from validators import log_exc as _lexc


class _CSRFTokenValue(str):
    """رشتهٔ توکن CSRF که «قابل فراخوانی» هم هست.

    قالب‌های خودِ ما توکن را با ``{{ csrf_token }}`` چاپ می‌کنند؛ اما قالب‌های
    Flask-Admin آن را به‌صورت تابع ``csrf_token()`` صدا می‌زنند. قبلاً
    context-processor ما یک str ساده تزریق می‌کرد و همین باعث می‌شد
    Flask-Admin با ``TypeError: 'str' object is not callable`` از کار بیفتد.
    این کلاس هر دو حالت را پوشش می‌دهد: چاپ مثل رشتهٔ معمولی، فراخوانی مثل تابع.
    """
    def __call__(self):
        return str(self)

# ------------------------------------------------------------------
# تم‌های ۲۰‌گانه
# ------------------------------------------------------------------
THEMES = [
    dict(id='theme-01', name='آبی کلاسیک',  desc='تم کلاسیک و حرفه‌ای با رنگ آبی رسمی',  colors=['#2563eb', '#1d4ed8', '#f59e0b'], dark=False),
    dict(id='theme-02', name='بنفش مدرن',   desc='بنفش سلطنتی با حال‌وهوای مدرن',       colors=['#7c3aed', '#6d28d9', '#22d3ee'], dark=False),
    dict(id='theme-03', name='سبز زمردی',   desc='سبز زمردی آرامش‌بخش و الهام‌بخش',     colors=['#059669', '#047857', '#fbbf24'], dark=False),
    dict(id='theme-04', name='سرخ یاقوتی',  desc='قرمز پرانرژی برای برندهای پرشور',     colors=['#dc2626', '#b91c1c', '#fbbf24'], dark=False),
    dict(id='theme-05', name='نارنجی آفتابی', desc='نارنجی گرم و پرانرژی',              colors=['#ea580c', '#c2410c', '#22c55e'], dark=False),
    dict(id='theme-06', name='رز گلد',      desc='صورتی‌طلایی لوکس و جذاب',            colors=['#e11d63', '#be185d', '#f59e0b'], dark=False),
    dict(id='theme-07', name='فیروزه‌ای',   desc='فیروزه‌ای تازه و آرامش‌بخش',          colors=['#0d9488', '#0f766e', '#f59e0b'], dark=False),
    dict(id='theme-08', name='نیمه‌شب',     desc='تم تیره با آبی روشن — مناسب نمایشگر OLED', colors=['#0ea5e9', '#0284c7', '#f59e0b'], dark=True),
    dict(id='theme-09', name='مشکی طلایی',  desc='لوکس و شیک — مشکی با طلایی',          colors=['#f59e0b', '#d97706', '#fbbf24'], dark=True),
    dict(id='theme-10', name='طوسی مینیمال', desc='مینیمال و ساده با طوسی خنثی',        colors=['#475569', '#334155', '#0ea5e9'], dark=False),
    dict(id='theme-11', name='کاربن',       desc='تم تیره مدرن با سبز نئون',            colors=['#34d399', '#10b981', '#a3e635'], dark=True),
    dict(id='theme-12', name='لیمویی',      desc='سبز لیمویی شاد و پرانرژی',            colors=['#65a30d', '#4d7c0f', '#f97316'], dark=False),
    dict(id='theme-13', name='اقیانوس',     desc='آبی اقیانوسی با گرادیان عمیق',        colors=['#0284c7', '#0369a1', '#38bdf8'], dark=False),
    dict(id='theme-14', name='کهکشان',      desc='بنفش کهکشانی تیره با ستاره‌ها',       colors=['#a855f7', '#7e22ce', '#f0abfc'], dark=True),
    dict(id='theme-15', name='فلامینگو',    desc='صورتی شاد و محبوب مخاطبان جوان',      colors=['#ec4899', '#db2777', '#8b5cf6'], dark=False),
    dict(id='theme-16', name='قهوه‌ای گرم',  desc='قهوه‌ای گرم و صمیمی',                colors=['#92400e', '#78350f', '#f59e0b'], dark=False),
    dict(id='theme-17', name='شرابی',       desc='شرابی کلاسیک و رسمی',                colors=['#9f1239', '#881337', '#f59e0b'], dark=False),
    dict(id='theme-18', name='نعنایی روشن', desc='روشن و شاد با سبز نعنایی',            colors=['#10b981', '#059669', '#f472b6'], dark=False),
    dict(id='theme-19', name='سرمه سلطنتی', desc='سرمه‌ای عمیق و باوقار',               colors=['#1e3a8a', '#1e40af', '#f59e0b'], dark=False),
    dict(id='theme-20', name='رنگین‌کمان',   desc='چند‌رنگ شاد با گرادیان‌های رنگی',     colors=['#6366f1', '#ec4899', '#f59e0b'], dark=False),
    dict(id='theme-21', name='ایرانی',       desc='فیروزه‌ای و لاجورد با نقوش اسلیمی و گره‌چینی', colors=['#0e9488', '#d4a017', '#0f3a4e'], dark=False),
    dict(id='theme-22', name='کلاسیک',       desc='سرمه‌ای و نارنجی — منو و فوتر کلاسیک آکادمیک', colors=['#f2640c', '#0f2744', '#ff7a1a'], dark=False),
    dict(id='theme-23', name='فیروزه',       desc='کاشی فیروزه‌ای ایرانی — آرام، آکادمیک و متمایز با زعفران', colors=['#0f766e', '#b45309', '#134e4a'], dark=False),
]

# ============================================================
# ۲۰ طرح اختصاصی ایرانی — از persian_themes.py
# ============================================================
from persian_themes import PERSIAN_THEMES as _PERSIAN_THEMES
# مدل‌های زیرساختی (BNPL/Cashback/مارکت‌پلیس/گردونه/قیمت) — برای ساخت جدول‌ها
import ext_models  # noqa: F401
THEMES.extend(dict(id=t['id'], name=t['name'],
                   desc=f"{t['desc']} — {t['category']}",
                   colors=[t['colors']['primary'], t['colors']['accent'], t['colors']['secondary']],
                   dark=t.get('dark', False), persian=True)
              for t in _PERSIAN_THEMES)
VALID_THEMES = [t['id'] for t in THEMES]

# ------------------------------------------------------------------
# ساخت اپلیکیشن
# ------------------------------------------------------------------
class _SkipBootDDL(Exception):
    """علامت داخلی: از ساخت جدول‌ها هنگام بوت صرف‌نظر شد (MySQL نصب‌شده)."""


def create_app():
    app = Flask(__name__)
    # قابلیت‌های نمایشی به‌صورت پیش‌فرض خاموش‌اند و در production هرگز فعال
    # نمی‌شوند. این پرچم فقط برای تست خودکار/توسعهٔ صریح نگه داشته شده است.
    from runtime import demo_features_enabled as _demo_features_enabled
    app.config['DEMO_FEATURES_ENABLED'] = _demo_features_enabled()
    # ---------- لاگ ساختاریافته: کنسول + فایل چرخشی ----------
    import logging as _logging
    from logging.handlers import RotatingFileHandler as _RFH
    _log_dir = os.environ.get('LOG_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(_log_dir, exist_ok=True)
    _fmt = _logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
    _fh = _RFH(os.path.join(_log_dir, 'academy.log'), maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
    _fh.setFormatter(_fmt)
    _ch = _logging.StreamHandler()
    _ch.setFormatter(_fmt)
    _root = _logging.getLogger()
    _root.setLevel(_logging.INFO)
    if not any(isinstance(h, _RFH) for h in _root.handlers):
        _root.addHandler(_fh)
        _root.addHandler(_ch)
    app.logger.setLevel(_logging.INFO)
    app.logger.info('app initialized (log_dir=%s)', _log_dir)
    # کلید امنیتی: در پروداکشن حتماً باید از محیط تنظیم شود (جلوگیری از جعل session)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    if not app.config['SECRET_KEY']:
        if os.environ.get('FLASK_ENV') == 'production' or os.environ.get('APP_ENV') == 'production':
            raise RuntimeError('SECRET_KEY باید در محیط production تنظیم شود! (متغیر محیطی SECRET_KEY)')
        app.config['SECRET_KEY'] = 'dev-only-key-1403-change-in-production'
    app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 30  # ۳۰ روز
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    # کوکی فقط روی HTTPS — در production اجباری
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '0') == '1' or \
        os.environ.get('FLASK_ENV') == 'production' or os.environ.get('APP_ENV') == 'production'
    # محدودیت حجم بدنه/آپلود: ۵۰ مگابایت
    app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))
    # دیتابیس: SQLite محلی (پیش‌فرض) یا MySQL با DATABASE_URL
    #   DATABASE_URL=mysql+pymysql://USER:PASS@HOST:3306/DBNAME?charset=utf8mb4
    _db_url = os.environ.get('DATABASE_URL') or ''
    if _db_url.startswith('mysql'):
        # اطمینان از utf8mb4 (فارسی + ایموجی) و راننده pymysql
        if 'charset=' not in _db_url:
            _db_url += ('&' if '?' in _db_url else '?') + 'charset=utf8mb4'
        # pool_pre_ping و تنظیمات استخر اتصال برای ترافیک ۵۰۰ هزارتایی (ضد کمبود اتصال)
        # ⚠️ هشدار: ۳ ورکر × (۱۰+۲۰) = ۹۰ اتصال همزمان — در هاست اشتراکی با
        # max_connections پایین (اغلب ۱۰۰–۱۵۰) باعث «Too many connections» و خطای 500 می‌شد!
        # حالا پیش‌فرض امن: ۵+۱۰ = ۱۵ اتصال برای هر ورکر (جمعاً ۴۵) — قابل تنظیم با متغیر محیطی:
        #   MYSQL_POOL_SIZE / MYSQL_MAX_OVERFLOW
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 280,
            'pool_size': int(os.environ.get('MYSQL_POOL_SIZE', 5)),
            'max_overflow': int(os.environ.get('MYSQL_MAX_OVERFLOW', 10)),
            'pool_timeout': 15,
            'connect_args': {
                'charset': 'utf8mb4',
                'use_unicode': True,
                # ⚠️ بدون این تایم‌اوت‌ها، اگر هاست پورت 3306 را فیلتر کرده باشد
                # یا سرور MySQL جواب handshake ندهد، هر درخواست ~۳۰ ثانیه هنگ
                # می‌کرد و بعد با «2013 Lost connection» می‌مرد (ارور ۵۰۰ کند).
                # حالا سریع شکست می‌خورد و پیام واضح در لاگ می‌آید.
                'connect_timeout': int(os.environ.get('MYSQL_CONNECT_TIMEOUT', 10)),
                'read_timeout': int(os.environ.get('MYSQL_READ_TIMEOUT', 60)),
                'write_timeout': int(os.environ.get('MYSQL_WRITE_TIMEOUT', 60)),
            },
        }
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        @event.listens_for(Engine, "connect")
        def set_mysql_session(dbapi_connection, connection_record):
            try:
                cursor = dbapi_connection.cursor()
                cursor.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
                cursor.close()
            except Exception:
                pass
    else:
        # بهینه‌سازی فوق‌العاده SQLite برای همزمانی بالا (حالت WAL + کش در حافظه + ضد قفل دیتابیس)
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            try:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=-10000")
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()
            except Exception:
                pass
    app.config['SQLALCHEMY_DATABASE_URI'] = _db_url or \
        'sqlite:///' + os.path.join(app.instance_path, 'academy.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    # ساخت خودکار جدول‌ها در اولین اجرا (SQLite تازه یا MySQL خالی)
    # — idempotent است: فقط جدول‌های موجود را بررسی و ایجاد می‌کند
    #
    # ⚠️ روی MySQL این کار در هر بوت انجام نمی‌شود: create_all() برای ۶۰ جدول
    # ده‌ها کوئری متادیتا می‌زند و روی هاست اشتراکی کند/ناپایدار است
    # (خطای 2013 Lost connection). چون نصب‌کننده جدول‌ها را می‌سازد، در حالت
    # «نصب‌شده + MySQL» از این مرحله عبور می‌کنیم مگر با SCHEMA_SYNC_ON_BOOT=1.
    _skip_boot_ddl = False
    if str(app.config['SQLALCHEMY_DATABASE_URI']).startswith('mysql') and \
            os.environ.get('SCHEMA_SYNC_ON_BOOT', '0') != '1':
        try:
            from installer import is_installed as _ii
            _skip_boot_ddl = _ii()
        except Exception:
            _skip_boot_ddl = False
    try:
        if _skip_boot_ddl:
            raise _SkipBootDDL()
        with app.app_context():
            db.create_all()
            # ایندکس‌های جاافتاده روی دیتابیس موجود (ضد کندی کوئری‌ها)
            from models import ensure_indexes as _ensure_idx
            _ensure_idx()
    except _SkipBootDDL:
        pass
    except Exception as _db_boot_err:
        # ⚠️ این خطا قبلاً فقط یک خط warning می‌شد و علت واقعی ارور ۵۰۰ با
        # MySQL (دسترسی، انکودینگ، سقف اتصال) پنهان می‌ماند. حالا کل traceback
        # ثبت می‌شود تا در لاگ هاست قابل دیدن باشد.
        import traceback as _tbm
        try:
            app.logger.error(
                'DB init failed on boot (%s): %s\n%s',
                type(_db_boot_err).__name__, _db_boot_err, _tbm.format_exc())
        except Exception:
            pass
        _lexc('app.py')

    # مهاجرت افزایشی کوچک برای نوع برگزاری دوره و اطلاعات ارسال سفارش. ستون‌ها
    # باید پیش از اولین SELECT روی نصب‌های قدیمی اضافه شوند.
    try:
        with app.app_context():
            from sqlalchemy import inspect as _inspect, text as _text
            inspector = _inspect(db.engine)
            table_names = set(inspector.get_table_names())
            quote = '`' if db.engine.dialect.name == 'mysql' else '"'

            def _add_columns(table_name, definitions):
                if table_name not in table_names:
                    return
                columns = {col['name'] for col in inspector.get_columns(table_name)}
                table = f'{quote}{table_name}{quote}'
                for name, ddl in definitions.items():
                    if name not in columns:
                        db.session.execute(_text(
                            f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))

            _add_columns('courses', {
                'delivery_type': "VARCHAR(20) DEFAULT 'online'",
                'allow_download': 'BOOLEAN DEFAULT 0',
                'attendance_required_percent': 'INTEGER DEFAULT 75',
            })
            _add_columns('order_items', {
                'quantity': 'INTEGER DEFAULT 1',
            })
            # جدول‌های جدید حضور و غیاب روی نصب‌های قدیمی نیز ساخته شوند.
            from models import CourseMeeting, AttendanceRecord
            CourseMeeting.__table__.create(db.engine, checkfirst=True)
            AttendanceRecord.__table__.create(db.engine, checkfirst=True)
            _add_columns('orders', {
                'shipping_name': "VARCHAR(120) DEFAULT ''",
                'shipping_phone': "VARCHAR(20) DEFAULT ''",
                'shipping_province': "VARCHAR(80) DEFAULT ''",
                'shipping_city': "VARCHAR(80) DEFAULT ''",
                'shipping_address': "VARCHAR(500) DEFAULT ''",
                'shipping_postal_code': "VARCHAR(20) DEFAULT ''",
                'shipping_cost': 'INTEGER DEFAULT 0',
                'fulfillment_status': "VARCHAR(30) DEFAULT 'not_required'",
            })
            db.session.commit()
    except Exception as _schema_patch_err:
        db.session.rollback()
        app.logger.warning('additive schema patch skipped: %s', _schema_patch_err)

    # ---------- فیلترها ----------
    app.jinja_env.filters['fa'] = fa
    app.jinja_env.filters['money'] = money
    app.jinja_env.filters['jdate'] = jdate
    app.jinja_env.filters['jdatetime'] = jdatetime
    app.jinja_env.filters['jdate_num'] = jdate_num
    app.jinja_env.filters['jtime'] = jtime
    app.jinja_env.filters['slugify'] = slugify

    def _from_json(v):
        import json as _json
        try:
            return _json.loads(v or '{}')
        except Exception:
            return {}
    app.jinja_env.filters['from_json'] = _from_json
    from validators import mask_nc
    app.jinja_env.filters['mask_nc'] = mask_nc
    # ── پاکسازی HTML دلخواه (ضد XSS/فیشینگ) ──
    # هرجا در قالب‌ها HTML خام رندر می‌شود باید از این فیلتر عبور کند، نه |safe.
    # جزئیات دلیل امنیتی در html_sanitizer.py توضیح داده شده است.
    from html_sanitizer import (escape_nl2br as _escape_nl2br,
                                safe_url as _safe_url,
                                sanitize_markup as _sanitize_markup)
    app.jinja_env.filters['clean_html'] = _sanitize_markup
    app.jinja_env.filters['safe_url'] = _safe_url
    app.jinja_env.filters['nl2br'] = _escape_nl2br

    def _safe_css_color(value):
        """رنگ برند فقط hex؛ از بستن style و CSS injection جلوگیری می‌کند."""
        import re as _css_re
        value = str(value or '').strip()
        return value if _css_re.match(r'^#[0-9a-fA-F]{6}$', value) else ''

    def _safe_css_int(value, minimum=0, maximum=2000):
        try:
            return max(int(minimum), min(int(maximum), int(value)))
        except (TypeError, ValueError):
            return ''

    app.jinja_env.filters['css_color'] = _safe_css_color
    app.jinja_env.filters['css_int'] = _safe_css_int

    def _safe_tracking_id(v):
        """شناسه سرویس تحلیلی (GA/Clarity/...) — فقط حروف، عدد، خط‌تیره.

        این مقدار داخل تگ <script> رندر می‌شود؛ بدون این فیلتر یک ادمین
        (یا مهاجمی که به پنل نفوذ کرده) می‌توانست با مقداری مثل
        `G-1';alert(1);//` اسکریپت دلخواه در تمام صفحات سایت اجرا کند.
        """
        import re as _re2
        v = str(v or '').strip()
        return v if _re2.match(r'^[A-Za-z0-9_-]{1,64}$', v) else ''
    app.jinja_env.filters['tracking_id'] = _safe_tracking_id
    # نسخه خودکار assetها — از آخرین زمان تغییر فایل‌های static (برای شکستن کش)
    # ⚠️ قبلاً در هر رندر، کل پوشه static اسکن می‌شد (چند بار در هر صفحه!) — حالا ۶۰ ثانیه کش می‌شود
    def _asset_v():
        def _compute():
            import os as _os
            base = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'static')
            latest = 0.0
            for root, _dirs, files in _os.walk(base):
                for fn in files:
                    try:
                        latest = max(latest, _os.path.getmtime(_os.path.join(root, fn)))
                    except OSError:
                        pass
            return str(int(latest))
        try:
            return _ttl_cache('asset_v', 60, _compute)
        except Exception:
            return '1'
    app.jinja_env.globals['asset_v'] = _asset_v
    app.jinja_env.globals['utcnow'] = utcnow
    app.jinja_env.globals.update(THEMES=THEMES, fa=fa, money=money,
                                 PERSIAN_THEMES=_PERSIAN_THEMES)

    # آمار واقعی سایت — با کش کوتاه (۶۰ ثانیه) برای نمایش در قالب‌ها/ویجت‌ها
    def site_stats():
        def _compute():
            from models import (User as _U, Course as _C, Section as _S, Lesson as _L,
                                Review as _R, Enrollment as _E, BlogPost as _B,
                                SuccessStory as _SS, Order as _O)
            _avg_rating = db.session.query(db.func.avg(_R.rating)) \
                .join(_C, _C.id == _R.course_id) \
                .filter(_R.is_approved == True, _C.status == 'published').scalar() or 0
            # ساعت‌ها با SUM در SQL — قبلاً همه دوره‌ها در پایتون بارگذاری می‌شدند
            _hours = db.session.query(db.func.coalesce(db.func.sum(_C.duration_hours), 0)) \
                .filter(_C.status == 'published').scalar() or 0
            st = dict(
                students=_U.query.filter_by(role='student', is_active=True).count(),
                users=_U.query.filter_by(is_active=True).count(),
                teachers=_U.query.filter(_U.role.in_(['teacher', 'admin']),
                                         _U.is_active == True).count(),
                courses=_C.query.filter_by(status='published').count(),
                lessons=db.session.query(_L.id).join(_S, _S.id == _L.section_id)
                    .join(_C, _C.id == _S.course_id)
                    .filter(_C.status == 'published').count(),
                hours=int(_hours),
                enrollments=db.session.query(_E.id).join(_C, _C.id == _E.course_id)
                    .filter(_C.status == 'published').count(),
                reviews=db.session.query(_R.id).join(_C, _C.id == _R.course_id)
                    .filter(_R.is_approved == True, _C.status == 'published').count(),
                avg_rating=round(float(_avg_rating), 2),
                satisfaction=round(float(_avg_rating) / 5 * 100) if _avg_rating else 0,
                posts=_B.query.filter_by(published=True).count(),
                stories=_SS.query.count(),
                paid_orders=_O.query.filter_by(status='paid').count(),
            )
            return st
        try:
            return _ttl_cache('site_stats', 60, _compute)
        except Exception:
            _lexc('app.py')
            return {}
    app.jinja_env.globals['site_stats'] = site_stats

    # ---------- سیستم آیکون (Tabler — 390 آیکون در static/icons) ----------
    from icons import init_icons
    init_icons(app)

    # ---------- ترمیم خودکار محافظ پوشه‌های آپلود (آپاچی/سی‌پنل) ----------
    # نصب‌های قدیمی که فایل .htaccess محافظ را ندارند، خودکار امن می‌شوند.
    try:
        from uploads_helper import ensure_upload_guards
        ensure_upload_guards()
    except Exception:
        _lexc('app.py')

    @app.template_filter('timestamp_to_jdate')
    def _ts_jdate(ts):
        try:
            from datetime import datetime as _dt
            return jdate(_dt.fromtimestamp(int(ts)))
        except Exception:
            return '—'

    # ---------- سرو فایل‌های خصوصی آپلودی (instance/uploads) ----------
    @app.route('/uploads/<folder>/<path:filename>')
    def serve_private_upload(folder, filename):
        """سرو فایل‌های خصوصی — دسترسی قبلاً در before_request چک شده است

        امنیت: فایل آپلودی هرگز نباید توسط مرورگر «اجرا/رندر» شود. اگر یک فایل
        html/svg آپلودشده به‌صورت inline سرو شود، زیر دامنهٔ خودمان اجرا می‌شود
        (XSS ذخیره‌شده / صفحهٔ فیشینگ) و باعث علامت خوردن دامنه توسط
        Google Safe Browsing («Dangerous site») می‌گردد. بنابراین:
          • فقط تصویر و pdf به‌صورت inline نمایش داده می‌شوند
          • بقیه اجباراً دانلود می‌شوند (Content-Disposition: attachment)
          • در هر حالت nosniff + CSP قفل‌شده روی پاسخ ست می‌شود
        """
        from flask import send_from_directory as _sfd, abort as _abort
        if folder not in ('lessons', 'proofs', 'submissions', 'tickets', 'forms'):
            _abort(404)
        # جلوگیری از path traversal (../) — فقط نام فایل ساده مجاز است
        if '..' in filename or filename.startswith('/') or '\\' in filename:
            _abort(404)
        from uploads_helper import uploads_dir as _udir
        _ext = os.path.splitext(filename)[1].lower()
        _inline_ok = _ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif', '.pdf')
        try:
            _resp = _sfd(_udir(folder), filename, as_attachment=not _inline_ok)
        except FileNotFoundError:
            _abort(404)
        _resp.headers['X-Content-Type-Options'] = 'nosniff'
        # اگر پسوند ناشناخته بود، mimetype اجرایی به آن نچسبد
        if not _inline_ok:
            _resp.headers['Content-Type'] = 'application/octet-stream'
        # سندباکس کامل: حتی اگر چیزی از فیلترها رد شد، اسکریپتی اجرا نمی‌شود
        _resp.headers['Content-Security-Policy'] = "default-src 'none'; sandbox; frame-ancestors 'none'"
        _resp.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        return _resp

    # ---------- ثبت بلوپرینت‌ها ----------
    from blueprints.site import site_bp
    from blueprints.products import products_bp
    app.register_blueprint(products_bp)

    from blueprints.auth import auth_bp
    from blueprints.shop import shop_bp
    from blueprints.student import student_bp
    from blueprints.admin_bp import admin_bp
    from blueprints.api import api_bp
    from blueprints.builder import (builder_bp, builder_courses, builder_categories,
                                    builder_posts, builder_teachers, builder_products,
                                    render_dynamic, render_shortcodes, uniq_cats)
    from models import Course as _CourseModel

    def _courses_by_id(cid):
        try:
            return db.session.get(_CourseModel, int(cid or 0))
        except Exception:
            return None
    app.register_blueprint(site_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(shop_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(builder_bp)
    from blueprints.seo_admin import seo_bp
    app.register_blueprint(seo_bp)
    from blueprints.features import features_bp
    app.register_blueprint(features_bp)
    from blueprints.teacher import teacher_bp
    app.register_blueprint(teacher_bp)
    from blueprints.community import community_bp
    app.register_blueprint(community_bp)
    # ── ماژول‌های زیرساختی: BNPL/Cashback · مارکت‌پلیس · تعامل کاربران ──
    try:
        from bnpl import bnpl_bp
        from marketplace import market_bp
        from engagement import engage_bp
        app.register_blueprint(bnpl_bp)
        app.register_blueprint(market_bp)
        app.register_blueprint(engage_bp)
    except Exception:
        _lexc('app.py')
    # ── سرویس‌های رایگان: Clarity/Crisp/Groq/Bing ──
    try:
        from integrations import services_bp
        app.register_blueprint(services_bp)
    except Exception:
        _lexc('app.py')
    # ── نصب‌کننده وب (شبیه وردپرس — /install) ──
    try:
        from blueprints.install import install_bp
        app.register_blueprint(install_bp)
    except Exception:
        _lexc('app.py')
    # ── فعال‌سازی نسخه تجاری (امضای Ed25519 + اتصال دامنه) ──
    # این جزء امنیتی core است؛ خطای import نباید با اجرای ناقص و بی‌صدا پنهان شود.
    from blueprints.license import license_bp
    app.register_blueprint(license_bp)

    # گارد نصب: اگر نصب انجام نشده، همه مسیرها → /install
    @app.before_request
    def _install_guard():
        if app.config.get('INSTALL_GUARD', True) is False:
            return None
        p = request.path
        if p.startswith('/install') or p.startswith('/static') or p == '/favicon.ico':
            return None
        from installer import is_installed as _is_inst, check_db_health as _cdh
        if not _is_inst():
            return redirect(url_for('install.wizard'))
        # نصب شده — سلامت دیتابیس؟ (جلوگیری از حلقه 500 بعد از نصب ناقص)
        # ⚠️ قبلاً در هر درخواست یک Engine جدید ساخته و کل جدول‌ها inspect می‌شد!
        # حالا نتیجه ۳۰ ثانیه کش می‌شود.
        def _health():
            ok, _msg = _cdh(engine=db.engine)
            return ok
        try:
            ok = _ttl_cache('install_health', 30, _health)
        except Exception:
            ok = True
        if not ok:
            return redirect(url_for('install.wizard') + '?repair=1')
        return None

    @app.before_request
    def _commercial_license_guard():
        """در بسته دارای public key، همه درخواست‌ها به لایسنس معتبر نیاز دارند."""
        from licensing import get_license_manager
        manager = get_license_manager()
        state = manager.status(request.host)
        g.license_state = state
        if not manager.enforced or state.valid:
            return None
        path = request.path or '/'
        allowed = (
            path.startswith(('/static/', '/install', '/license')) or
            path in ('/health', '/favicon.ico') or
            # callback تراکنش شروع‌شده نباید با انقضای ناگهانی لایسنس گم شود.
            path.startswith('/pay/verify/') or path == '/pay/zarinpal-verify'
        )
        if allowed:
            return None
        if path.startswith('/api/') or request.accept_mimetypes.best == 'application/json':
            from flask import jsonify as _jsonify
            return _jsonify(ok=False, code='license_required',
                            msg=state.message, license=state.as_public_dict()), 402
        next_path = request.full_path.rstrip('?')
        return redirect(url_for('license.activate', next=next_path))

    # Flask-Admin (پنل مدیریت کامل مدل‌ها)
    try:
        from admin_panel import init_admin
        init_admin(app)
    except Exception as e:
        app.logger.warning(f'Flask-Admin غیرفعال: {e}')
    # روت پنل Flask-Admin به /admin-extra تا با پنل ما تداخل نکند
    try:
        from flask_admin import Admin as _A
        # مسیر پیش‌فرض /admin/ است — آن را به /admin-extra تغییر می‌دهیم
        # (این کار بعد از ساخت Admin انجام می‌شود؛ در admin_panel تنظیم شده)
    except Exception:
        _lexc('app.py')
    app.jinja_env.globals['builder_courses'] = builder_courses
    app.jinja_env.globals['builder_categories'] = builder_categories
    app.jinja_env.globals['builder_posts'] = builder_posts
    from blueprints.builder import (builder_price_history, builder_amazing_offer,
                                    builder_review_pro)
    app.jinja_env.globals['builder_price_history'] = builder_price_history
    app.jinja_env.globals['builder_amazing_offer'] = builder_amazing_offer
    app.jinja_env.globals['builder_review_pro'] = builder_review_pro
    app.jinja_env.globals['builder_teachers'] = builder_teachers
    app.jinja_env.globals['builder_products'] = builder_products
    app.jinja_env.globals['rd'] = render_dynamic
    app.jinja_env.globals['rshort'] = render_shortcodes
    app.jinja_env.globals['uniq_cats'] = uniq_cats
    # دسترسی ماکروها به داده‌های درخواست (ماکروها context ندارند)
    from blueprints.builder import WIDGETS as _WIDGETS
    from models import Favorite, Ticket

    def _get_all_categories():
        """دسته‌ها + دوره‌های هر دسته — نسخهٔ سبک غیر-ORM (ایمن برای کش بین درخواست‌ها)"""
        try:
            from cache_safe import CatLite, CourseLite
            cat_rows = Category.query.order_by(Category.sort, Category.id).all()
            course_rows = Course.query.filter_by(status='published').all()
            by_cat = {}
            for c in course_rows:
                by_cat.setdefault(c.category_id, []).append(CourseLite(c))
            out = []
            for cat in cat_rows:
                published = by_cat.get(cat.id, [])
                if not published:
                    continue
                out.append(CatLite(cat.name, cat.slug, cat.icon or '🎓',
                                   cat.color or '#2563eb', cid=cat.id,
                                   sort=cat.sort or 0, courses=published))
            return out
        except Exception:
            _lexc('app.py')
            return []

    def _bc_cats():
        try:
            return _ttl_cache('all_categories', 120, _get_all_categories)
        except Exception:
            return []

    def _bc_cur():
        return getattr(g, 'user', None)

    def _bc_site():
        return getattr(g, 'settings', {})

    def _bc_fav_ids():
        u = getattr(g, 'user', None)
        if u:
            try:
                return {(u.id, f.course_id) for f in Favorite.query.filter_by(user_id=u.id).all()}
            except Exception:
                _lexc('app.py')
        return set()

    def _bc_cart():
        return int(getattr(g, 'cart_count', 0) or 0)

    def _bc_enrolled_ids():
        cached = getattr(g, '_enrolled_ids_cache', None)
        if cached is not None:
            return cached
        user = getattr(g, 'user', None)
        if not user:
            return set()
        try:
            from models import Enrollment
            cached = {row.course_id for row in Enrollment.query.filter_by(user_id=user.id).all()}
        except Exception:
            cached = set()
        g._enrolled_ids_cache = cached
        return cached

    def _bc_current_post():
        return getattr(g, 'current_post', None)

    def _bc_cart_total():
        try:
            from blueprints.products import _cart_items as _items, _cart_total as _total
            return _total(_items())
        except Exception:
            return 0

    def _bc_page_settings():
        return getattr(g, 'page_settings', {})

    def _bc_reviews_pending():
        try:
            from models import Review as _R
            return _R.query.filter_by(is_approved=False).count()
        except Exception:
            return 0

    def _bc_tickets():
        u = getattr(g, 'user', None)
        if u:
            try:
                return Ticket.query.filter(Ticket.user_id == u.id,
                                           Ticket.status.in_(['open', 'answered'])).count()
            except Exception:
                _lexc('app.py')
        return 0

    # ---------- کش TTL هوشمند با پاک‌سازی انتخابی (کاهش کوئری‌ها تا ۹۵٪) ----------
    import threading as _cache_thr
    _cache_lock = _cache_thr.Lock()
    _cache_store = {}

    def _ttl_cache(key, ttl, fn):
        now = time.time()
        with _cache_lock:
            hit = _cache_store.get(key)
            if hit and now - hit[0] < ttl:
                return hit[1]
        val = fn()
        with _cache_lock:
            _cache_store[key] = (now, val)
            if len(_cache_store) > 300:
                stale = [k for k, v in _cache_store.items() if now - v[0] > 600]
                for k in stale:
                    _cache_store.pop(k, None)
                if len(_cache_store) > 300:
                    _cache_store.clear()
        return val

    def clear_cache(key=None):
        """پاک‌سازی کش هنگام تغییر تنظیمات یا محتوا از پنل ادمین"""
        with _cache_lock:
            if key and key in _cache_store:
                _cache_store.pop(key, None)
            elif not key:
                _cache_store.clear()
            if not key:
                _html_cache.clear()
    app.jinja_env.globals['clear_cache'] = clear_cache
    app.clear_cache = clear_cache

    def _load_success_stories():
        def _q():
            from models import SuccessStory
            from sqlalchemy.orm import joinedload as _jl
            from cache_safe import story_lite
            rows = SuccessStory.query.options(_jl(SuccessStory.course)) \
                .filter_by(is_active=True) \
                .order_by(SuccessStory.sort, SuccessStory.id.desc()).limit(6).all()
            return [story_lite(s) for s in rows]
        try:
            g._success_stories = _ttl_cache('stories', 60, _q)
            return g._success_stories
        except Exception:
            return []

    def _load_reviews():
        def _q():
            from models import Review
            from sqlalchemy.orm import joinedload as _jl
            from cache_safe import review_lite
            rows = Review.query.options(_jl(Review.user), _jl(Review.course)) \
                .filter_by(is_approved=True) \
                .order_by(Review.created_at.desc()).limit(9).all()
            return [review_lite(r) for r in rows]
        try:
            return _ttl_cache('reviews', 60, _q)
        except Exception:
            return []

    def _load_exam_cats():
        def _q():
            from models import QuestionBank
            return [r[0] for r in db.session.query(QuestionBank.category)
                    .distinct().order_by(QuestionBank.category).all() if r[0]]
        try:
            return _ttl_cache('exam_cats', 300, _q)
        except Exception:
            return []

    app.jinja_env.globals.update(
        WIDGETS=_WIDGETS, bc_categories=_bc_cats, bc_cur_user=_bc_cur,
        bc_site=_bc_site, bc_fav_ids=_bc_fav_ids, bc_cart_count=_bc_cart,
        bc_enrolled_ids=_bc_enrolled_ids,
        bc_tickets_count=_bc_tickets, bc_current_post=_bc_current_post,
        bc_cart_total=_bc_cart_total, courses_by_id=_courses_by_id,
        bc_reviews_pending=_bc_reviews_pending,
        bc_page_settings=_bc_page_settings,
        bc_current_course=lambda: getattr(g, 'current_course', None),
        bc_current_teacher=lambda: getattr(g, 'current_teacher', None),
        bc_success_stories=lambda: getattr(g, '_success_stories', None) or _load_success_stories(),
        bc_reviews=lambda: _load_reviews(),
        bc_exam_cats=lambda: _load_exam_cats())

    # ---------- هدرهای امنیتی + فشرده‌سازی ----------
    @app.after_request
    def security_headers(resp):
        # ── ذخیره صفحه در کش مهمان (قبل از gzip — بدنه خام) ──
        try:
            if (resp.status_code == 200 and request.method == 'GET' and
                    not getattr(g, 'user', None) and
                    resp.content_type and resp.content_type.startswith('text/html')):
                _key = _html_cache_key()
                if _key:
                    _ttl = 300 if request.path == '/' else 120
                    with _cache_lock:
                        if len(_html_cache) > 200:
                            _html_cache.clear()
                        _html_cache[_key] = (time.time(), _ttl, resp.get_data())
        except Exception:
            pass
        # ── پاک‌سازی کش‌ها بعد از هر تغییر محتوا از پنل مدیریت/صفحه‌ساز ──
        try:
            if (request.method == 'POST' and resp.status_code in (200, 302) and
                    (request.path.startswith('/admin') or request.path.startswith('/builder'))):
                clear_cache()
        except Exception:
            pass
        resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
        resp.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        # X-XSS-Protection: 0 چون CSP ما محافظت می‌کند؛ 1 با 'unsafe-inline' تداخل دارد
        resp.headers.setdefault('X-XSS-Protection', '0')
        resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        resp.headers.setdefault('X-Powered-By', 'Academy LMS')
        # محدودسازی APIهای مرورگر (دوربین/میکروفون/موقعیت) — فقط در صورت نیاز باز شوند
        resp.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()')
        # ایزوله‌سازی پنجره‌های کراس‌اورجین
        resp.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        # ⚠️ Cross-Origin-Embedder-Policy: require-corp عمداً ست نمی‌شود.
        # با require-corp هر منبع کراس‌اورجین بدون هدر CORP (تصویر آپلودشده در CDN،
        # ویدیو آپارات/یوتیوب، ویجت گفتگو) بلاک می‌شود و صفحه «شکسته/نیمه‌بارگذاری»
        # نمایش داده می‌شود؛ صفحهٔ شکسته با منابع بلاک‌شده یکی از سیگنال‌های منفی
        # کیفیت/امنیت است و عیب‌یابی «Dangerous site» را هم سخت می‌کند.
        resp.headers.setdefault('Cross-Origin-Resource-Policy', 'same-site')
        # HSTS — فقط روی HTTPS فعال می‌شود. افزودن آن روی HTTP محلی هم بی‌اثر
        # است و هم می‌تواند عیب‌یابی تفاوت HTTP/HTTPS را گمراه‌کننده کند.
        if request.is_secure:
            resp.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        # صفحات پرداخت/حساب هرگز ایندکس نشوند — ایندکس شبیه‌ساز پرداخت
        # توسط Google Safe Browsing به‌عنوان «Dangerous site» فلگ می‌شود.
        _np = request.path or ''
        if (_np.startswith('/pay') or _np.startswith('/checkout') or
                _np.startswith('/cart') or _np.startswith('/dashboard') or
                _np.startswith('/auth') or _np.startswith('/install') or
                _np.startswith('/wallet') or _np.startswith('/admin') or _np.startswith('/license')):
            resp.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        # تصاویر آپلودی ادمین/صفحه‌ساز (/static/img/uploads/...) — inline می‌مانند
        # (لوگو و تصاویر صفحه باید نمایش داده شوند) ولی با sandbox، پس حتی اگر
        # فایل SVG اسکریپت داشته باشد و کاربر مستقیم بازش کند، چیزی اجرا نمی‌شود.
        if request.path.startswith('/static/img/uploads/'):
            resp.headers['X-Content-Type-Options'] = 'nosniff'
            resp.headers['Content-Security-Policy'] = \
                "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox; frame-ancestors 'none'"
            resp.headers['X-Robots-Tag'] = 'noindex, nofollow'
        # ── فایل‌های آپلودشدهٔ عمومی (/static/uploads/...) ──
        # این فایل‌ها را کاربر/ادمین آپلود کرده‌اند؛ اگر مرورگر آن‌ها را به‌عنوان
        # HTML یا SVG اجرا کند، محتوای دلخواه زیر دامنهٔ ما اجرا می‌شود
        # (XSS ذخیره‌شده / صفحهٔ فیشینگ) → علامت «Dangerous site» گوگل.
        if request.path.startswith('/static/uploads/'):
            resp.headers['X-Content-Type-Options'] = 'nosniff'
            resp.headers['Content-Security-Policy'] = \
                "default-src 'none'; img-src 'self' data:; media-src 'self'; sandbox; frame-ancestors 'none'"
            resp.headers['X-Robots-Tag'] = 'noindex, nofollow'
            _uext = os.path.splitext(request.path)[1].lower()
            # svg/html/xml هرگز inline رندر نشوند — اجباراً دانلود
            if _uext in ('.svg', '.svgz', '.html', '.htm', '.xhtml', '.xml',
                         '.js', '.mjs', '.css', '.pdf'):
                resp.headers['Content-Disposition'] = 'attachment'
                if _uext != '.pdf':
                    resp.headers['Content-Type'] = 'application/octet-stream'
        # کش هوشمند: استاتیک ۷ روز، HTML بدون کش
        if request.path.startswith('/static/'):
            resp.headers['Cache-Control'] = 'public, max-age=604800, immutable'
        elif resp.content_type and resp.content_type.startswith('text/html'):
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        # ── Content Security Policy ──
        # این CSP برای جلوگیری از XSS، تزریق اسکریپت، و فیشینگ طراحی شده
        # fetch/XHR به همان origin نیاز به اجازه جداگانه ندارد (self شامل می‌شود)
        csp = (
            "default-src 'self'; "
            # unsafe-inline برای Flask/Jinja2 templates; با nonce/hash می‌توان حذف کرد.
            # 'unsafe-eval' حذف شد — هیچ‌جای پروژه eval/new Function نداریم و وجودش
            # فقط سطح حمله XSS را باز نگه می‌داشت.
            "script-src 'self' 'unsafe-inline' "
            "https://www.googletagmanager.com https://www.google-analytics.com "
            "https://www.clarity.ms https://client.crisp.chat; "
            "style-src 'self' 'unsafe-inline' https://client.crisp.chat; "
            # تصاویر محصول/دوره ممکن است از CDN امنی که مدیر ثبت کرده بیایند.
            "img-src 'self' data: blob: https:; "
            "font-src 'self' data: https://client.crisp.chat; "
            "connect-src 'self' https://www.google-analytics.com https://www.googletagmanager.com "
            "https://*.clarity.ms https://client.crisp.chat wss://client.relay.crisp.chat; "
            "frame-src 'self' https://www.youtube-nocookie.com https://www.youtube.com "
            "https://www.aparat.com https://player.vimeo.com https://w.soundcloud.com "
            "https://maps.google.com https://game.crisp.chat; "
            "worker-src 'self' blob:; "
            "child-src 'self' blob:; "
            "form-action 'self' https://bpm.shaparak.ir https://sep.shaparak.ir; "
            "base-uri 'self'; "
            # frame-ancestors نسخهٔ مدرن X-Frame-Options است — جلوگیری از
            # clickjacking/کپی‌برداری صفحه در iframe سایت فیشینگ
            "frame-ancestors 'self'; "
            "object-src 'none'; "
            "manifest-src 'self'; "
            "media-src 'self' data: blob:;"
        )
        # این directive فقط برای پاسخ HTTPS معتبر است. روی سرور توسعهٔ HTTP،
        # مرورگر در غیر این صورت منابع same-origin را به HTTPS ارتقا می‌دهد و
        # TLS ClientHello را به پورت HTTP سادهٔ Werkzeug می‌فرستد (خطای 400).
        if request.is_secure:
            csp += " upgrade-insecure-requests"
        # ⚠️ مسیرهای آپلود CSP سخت‌گیرانه‌تر (sandbox) خودشان را بالاتر ست کرده‌اند
        # — نباید با CSP عمومی بازنویسی شود.
        _is_upload_path = (request.path.startswith('/static/uploads/') or
                           request.path.startswith('/static/img/uploads/') or
                           request.path.startswith('/uploads/'))
        if resp.status_code != 500 and not _is_upload_path:
            resp.headers['Content-Security-Policy'] = csp
            # انتساب سختگیرانه مرورگر برای فرم‌ها
            if request.path.startswith('/admin'):
                resp.headers['X-Required-Security-Headers'] = 'CSP, X-Frame-Options, X-Content-Type-Options'
        # فشرده‌سازی gzip برای HTML، CSS و JS
        import gzip as _gzip
        _ct = resp.content_type or ''
        _compressible = _ct.startswith('text/html') or _ct.startswith('text/css') or \
                        _ct.startswith('application/javascript') or _ct.startswith('text/javascript') or \
                        _ct.startswith('application/json')
        if (resp.status_code == 200 and _compressible):
            try:
                _data = resp.get_data()
            except RuntimeError:
                # فایل‌های static در حالت passthrough — خروج از حالت برای خواندن داده
                resp.direct_passthrough = False
                _data = resp.get_data()
            if len(_data) > 500:
                accept = request.headers.get('Accept-Encoding', '')
                if 'gzip' in accept:
                    compressed = _gzip.compress(_data, 6)
                    if len(compressed) < len(_data):
                        resp.set_data(compressed)
                        resp.headers['Content-Encoding'] = 'gzip'
                        resp.headers['Content-Length'] = str(len(compressed))
        # کش خصوصی کوتاه‌مدت برای صفحات عمومی مهمان (فقط مرورگر همان کاربر)
        # — سرعت بازدیدهای تکراری بدون خطر لو رفتن سشن/توکن بین کاربران
        if (resp.status_code == 200 and _ct.startswith('text/html') and
                request.method == 'GET' and not getattr(g, 'user', None) and
                request.path.startswith(('/course/', '/courses', '/blog', '/about', '/faq',
                                         '/contact', '/terms', '/privacy', '/teachers', '/',
                                         '/bundles', '/success-stories', '/learning-paths',
                                         '/teachers', '/faq'))):
            # صفحه اصلی و لیست‌ها: کش ۳۰۰ ثانیه (همان کاربر) — سرعت بازدید تکراری
            _age = 300 if request.path == '/' else 120
            resp.headers['Cache-Control'] = f'private, max-age={_age}'
        return resp

    # ---------- Rate limit بر اساس IP — Redis در production، حافظه در dev ----------
    import threading as _thr, time as _time
    _rl_lock = _thr.Lock()
    _rl_hits = {}  # ip -> [window_start, count]  (fallback درون‌حافظه)
    _rl_redis = None
    try:
        if os.environ.get('REDIS_URL'):
            import redis as _redis
            _rl_redis = _redis.Redis.from_url(os.environ['REDIS_URL'], socket_timeout=2, socket_connect_timeout=2)
            _rl_redis.ping()
            app.logger.info('rate limit: Redis فعال شد')
    except Exception:
        _rl_redis = None
        app.logger.info('rate limit: حالت حافظه داخلی (REDIS_URL تنظیم نشده)')

    _TRUST_PROXY = os.environ.get('TRUST_PROXY') == '1'

    def _client_ip():
        """IP واقعی — فقط وقتی TRUST_PROXY=1 به X-Forwarded-For اعتماد کن (nginx آن را overwrite میکند)"""
        if _TRUST_PROXY:
            return request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
        return request.remote_addr or 'unknown'

    def _rate_limit(limit, window):
        ip = _client_ip()
        now = _time.time()
        if _rl_redis is not None:
            try:
                key = f'rl:{ip}:{request.path[:60]}'
                n = _rl_redis.incr(key)
                if n == 1:
                    _rl_redis.expire(key, window)
                return n <= limit
            except Exception:
                pass  # در صورت خطای Redis → fallback به حافظه
        with _rl_lock:
            # همانند کلید Redis، شمارنده هر endpoint جداست؛ در غیر این صورت
            # درخواست عادی API می‌توانست سهمیه login/license همان IP را بسوزاند.
            memory_key = (ip, request.path[:60])
            rec = _rl_hits.get(memory_key)
            if not rec or now - rec[0] > window:
                _rl_hits[memory_key] = [now, 1]
                return True
            rec[1] += 1
            if rec[1] > limit:
                return False
            # پاک‌سازی هوشمند حافظه برای جلوگیری از Memory DoS در ترافیک ۵۰۰ هزارتایی
            if len(_rl_hits) > 5000:
                stale = [k for k, v in _rl_hits.items() if now - v[0] > window]
                for k in stale:
                    _rl_hits.pop(k, None)
                if len(_rl_hits) > 5000:
                    _rl_hits.clear()
            return True

    @app.before_request
    def rate_limit_protect():
        p = request.path
        if p.startswith('/api/') or p.startswith('/builder/api/'):
            if not _rate_limit(120, 60):
                return 'درخواست بیش از حد — کمی صبر کنید.', 429
        elif p == '/auth/login' and request.method == 'POST':
            if not _rate_limit(20, 300):
                return 'تلاش بیش از حد — ۵ دقیقه صبر کنید.', 429
        elif p in ('/auth/register', '/auth/phone-send') and request.method == 'POST':
            if not _rate_limit(10, 300):
                return 'درخواست بیش از حد — کمی صبر کنید.', 429
        elif p == '/newsletter' and request.method == 'POST':
            if not _rate_limit(5, 60):
                return 'درخواست بیش از حد — کمی صبر کنید.', 429
        elif p == '/license' and request.method == 'POST':
            if not _rate_limit(10, 300):
                return 'تلاش فعال‌سازی بیش از حد — ۵ دقیقه صبر کنید.', 429
        elif p == '/install/repair' and request.method == 'POST':
            # نصب تکه‌ای چند درخواست لازم دارد؛ سقف برای کار عادی کافی و برای
            # brute-force رمز/کلید بازیابی محدود است.
            if not _rate_limit(40, 900):
                return 'درخواست تعمیر بیش از حد — ۱۵ دقیقه صبر کنید.', 429
        return None

    # ---------- CSRF محافظت (توکن دستی در سشن) ----------
    @app.before_request
    def csrf_protect():
        import secrets as _secrets
        if '_csrf_token' not in session:
            session['_csrf_token'] = _secrets.token_hex(16)
        g.csrf_token = session['_csrf_token']
        # بررسی POST های حساس (بدون API که JSON دارد؛ نصب‌کننده هم گارد خودش را دارد)
        if request.method == 'POST' and not request.path.startswith('/api') and \
                not request.path.startswith('/builder/api') and \
                not request.path.startswith('/install') and \
                not request.path.startswith('/pay/verify/') and \
                request.path != '/admin/update/webhook':
            # Flask-Admin فرم‌هایش را با نام فیلد `csrf_token` ارسال می‌کند؛
            # پنل اصلی ما از `_csrf_token` استفاده می‌کند. هر دو باید با توکن
            # سشن یکسان مقایسه شوند تا هر دو پنل در برابر CSRF محافظت بمانند.
            token = (request.form.get('_csrf_token') or request.form.get('csrf_token') or
                     request.headers.get('X-CSRF-Token'))
            expected = session.get('_csrf_token') or ''
            if not token:
                abort(400, description='توکن امنیتی (CSRF) ارسال نشده است. لطفاً صفحه را رفرش کنید و دوباره تلاش کنید.')
            if not expected or not hmac.compare_digest(str(token), str(expected)):
                abort(400, description='توکن امنیتی (CSRF) نامعتبر یا منقضی شده است. لطفاً صفحه را رفرش کنید.')

    # ---------- GET روی مسیرهای POST-only → ریدایرکت به جای 405 ----------
    @app.errorhandler(400)
    def bad_request(e):
        return render_error('درخواست نامعتبر', 'فرم یا درخواست ارسال‌شده معتبر نیست — صفحه را رفرش کنید.', 400)

    @app.errorhandler(413)
    def too_large(e):
        return render_error('حجم فایل زیاد است', 'حداکثر حجم مجاز آپلود ۵۰ مگابایت است.', 413)

    @app.errorhandler(405)
    def method_not_allowed(e):
        if request.path.startswith(('/install', '/api/', '/builder/api/')):
            from flask import jsonify as _j
            return _j(ok=False, msg='روش درخواست نامعتبر است', code=405), 405
        p = request.path
        prefix_map = [
            ('/admin/gateways', 'admin.gateways'), ('/admin/messengers', 'admin.messengers'),
            ('/admin/lesson-questions', 'admin.lesson_questions'), ('/admin/submissions', 'admin.submissions'),
            ('/admin/pages', 'admin.pages'), ('/admin/users', 'admin.users'), ('/admin/proofs', 'admin.proofs'),
            ('/admin/payouts', 'admin.payouts'), ('/admin/certificates', 'admin.certificates'),
            ('/admin/bundles', 'admin.bundles'), ('/admin/courses', 'admin.courses'),
            ('/admin/quizzes', 'admin.quizzes'), ('/admin/canned-replies', 'admin.canned_replies'),
            ('/admin/forum', 'admin.forum_moderate'), ('/admin/forms', 'admin.forms'),
            ('/admin/live-sessions', 'admin.live_sessions'), ('/admin/backup', 'admin.backup_list'),
            ('/admin/success-stories', 'admin.success_stories'), ('/admin/assignments', 'admin.assignments'),
            ('/admin/notifications', 'admin.admin_notifications'), ('/admin/newsletters', 'admin.newsletters'),
            ('/admin/menus', 'admin.menus'), ('/admin/tickets', 'admin.tickets'),
            ('/admin/reports', 'admin.overview'), ('/admin/', 'admin.overview'),
            ('/builder', 'builder.index'), ('/lesson/', 'student.my_courses'),
            ('/dashboard/', 'student.dashboard'), ('/talent-test', 'features.talent_test'),
            ('/community', 'community.forum'), ('/teacher-panel', 'teacher.dashboard'),
            ('/exam/', 'features.exam_practice'), ('/wallet/', 'features.wallet'),
            ('/pay/', 'shop.cart'), ('/course/', 'site.courses'), ('/feedback/', 'student.my_courses'),
            ('/api/', 'site.index'), ('/form/', 'site.index'),
        ]
        for prefix, ep in prefix_map:
            if p.startswith(prefix):
                try:
                    return redirect(url_for(ep))
                except Exception:
                    _lexc('app.py')
        ref = request.referrer or ''
        if ref.startswith(request.host_url):
            return redirect(ref)
        return redirect('/')

    # ---------- قبل از هر درخواست ----------
    @app.before_request
    def load_globals():
        # پنل‌های مدیریتی مستقل از سایت — بدون هدر/فوتر فروشگاه
        g.hide_hdr = False
        g.hide_ftr = False
        _p = request.path
        if _p.startswith('/admin') or _p.startswith('/teacher-panel') or _p.startswith('/builder'):
            g.hide_hdr = True
            g.hide_ftr = True
        g.settings = {}
        def _get_all_settings():
            res = {}
            for s in Setting.query.all():
                res[s.key] = s.value
            return res
        try:
            g.settings = _ttl_cache('all_settings', 60, _get_all_settings)
        except Exception:
            _lexc('app.py')
        # URL نرمال‌شدهٔ لوگو — همهٔ حالت‌های تاریخی ذخیره‌شده در تنظیم
        # (uploads/brand/x یا /static/img/...) را به URL سالم تبدیل می‌کند.
        try:
            from models import normalize_logo_url
            g.settings['logo_url'] = normalize_logo_url(
                g.settings.get('custom_logo', ''))
        except Exception:
            _lexc('app.py')
            g.settings['logo_url'] = ''

        # مهاجرت ایمن نصب‌های قدیمی: داده‌های شناخته‌شدهٔ seed حذف نمی‌شوند تا
        # سابقه و روابط دیتابیس آسیب نبیند، اما از دید عموم غیرفعال/پیش‌نویس
        # می‌شوند. مدیر بعداً می‌تواند آن‌ها را بازبینی و حذف کند.
        if not _demo_features_enabled():
            def _disable_legacy_demo_data():
                try:
                    from models import (Coupon as _Coupon, BlogPost as _BlogPost,
                                        Page as _Page, Product as _Product,
                                        Ticket as _Ticket, ContactMessage as _Contact,
                                        NewsletterEmail as _Newsletter, Quiz as _Quiz,
                                        Assignment as _Assignment,
                                        QuestionBank as _QuestionBank)
                    demo_emails = (
                        'demo@academy.ir', 'sara@academy.ir', 'amir@academy.ir',
                        'mehdi@academy.ir', 'negar@academy.ir', 'hossein@academy.ir',
                        'zahra@academy.ir',
                        # ⚠️ ادمینِ seed نیز باید در production غیرفعال شود:
                        # seed.py حساب `admin@academy.ir / admin123` (رمز منتشرشده)
                        # می‌سازد؛ اگر دیتابیس seed‌شده به production بیاید، این
                        # حسابِ با رمز شناخته‌شده قبلاً فعال می‌ماند (backdoor).
                        'admin@academy.ir',
                    )
                    demo_users = User.query.filter(User.email.in_(demo_emails)).all()
                    demo_user_ids = [user.id for user in demo_users]
                    demo_course_ids = [row[0] for row in db.session.query(Course.id)
                                       .filter(db.or_(Course.seeded_students > 0,
                                                      Course.slug == 'course-intro')).all()]
                    legacy_seed_detected = bool(demo_users or demo_course_ids)
                    User.query.filter(User.email.in_(demo_emails)).update(
                        {User.is_active: False}, synchronize_session=False)
                    if demo_user_ids:
                        Order.query.filter(Order.user_id.in_(demo_user_ids)).update(
                            {Order.status: 'canceled'}, synchronize_session=False)
                        _Ticket.query.filter(_Ticket.user_id.in_(demo_user_ids)).update(
                            {_Ticket.status: 'closed'}, synchronize_session=False)
                    if demo_course_ids:
                        _Quiz.query.filter(_Quiz.course_id.in_(demo_course_ids)).update(
                            {_Quiz.is_published: False}, synchronize_session=False)
                        _Assignment.query.filter(_Assignment.course_id.in_(demo_course_ids)).update(
                            {_Assignment.is_published: False}, synchronize_session=False)
                    if demo_course_ids:
                        Course.query.filter(Course.id.in_(demo_course_ids)).update(
                            {Course.status: 'draft', Course.featured: False,
                             Course.seeded_students: 0, Course.views: 0},
                            synchronize_session=False)
                    if legacy_seed_detected:
                        try:
                            from seed import QUESTION_BANK as _SEED_QUESTIONS
                            demo_question_texts = tuple(
                                item[0] for group in _SEED_QUESTIONS.values() for item in group)
                            if demo_question_texts:
                                _QuestionBank.query.filter(_QuestionBank.text.in_(demo_question_texts)).delete(
                                    synchronize_session=False)
                        except Exception:
                            _lexc('app.disable_seed_question_bank')
                        _Coupon.query.filter(_Coupon.code.in_((
                            'WELCOME20', 'NOWROOZ10', 'FIX500'
                        ))).update({_Coupon.is_active: False}, synchronize_session=False)
                    demo_post_titles = (
                        '۱۰ ترفند پایتون که هر برنامه‌نویسی باید بداند',
                        'راهنمای انتخاب اولین زبان برنامه‌نویسی',
                        'چگونه در ۶ ماه توسعه‌دهنده وب شویم؟',
                        '۵ مهارت نرم که هر متخصص فناوری به آن نیاز دارد',
                    )
                    if legacy_seed_detected:
                        _BlogPost.query.filter(_BlogPost.title.in_(demo_post_titles)).update(
                            {_BlogPost.published: False}, synchronize_session=False)
                        _Product.query.filter(_Product.slug.in_((
                            'academy-mug', 'glass-mug', 'dev-notebook', 'coder-tshirt'
                        ))).update({_Product.is_active: False, _Product.featured: False,
                                    _Product.stock: 0}, synchronize_session=False)
                    if legacy_seed_detected:
                        _Newsletter.query.filter(_Newsletter.email.in_((
                            'alireza@gmail.com', 'niloofar@yahoo.com', 'mohsen73@gmail.com'
                        ))).delete(synchronize_session=False)
                        _Contact.query.filter_by(email='reza@mail.com').delete(
                            synchronize_session=False)
                    replacements = {
                        'از صفر تا استخدام — با کد تخفیف WELCOME20 تا ۲۰٪ تخفیف بیشتر بگیرید!':
                            'آموزش گام‌به‌گام همراه با تمرین‌های کاربردی.',
                        'همین حالا ثبت‌نام کن و با کد تخفیف WELCOME20 از ۲۰٪ تخفیف بهره‌مند شو!':
                            'حساب خود را بسازید و دوره‌های منتشرشده را ببینید.',
                    }
                    if legacy_seed_detected:
                        for page in _Page.query.filter(_Page.content.contains('WELCOME20')).all():
                            content = page.content or ''
                            for old, new in replacements.items():
                                content = content.replace(old, new)
                            page.content = content.replace('WELCOME20', '')
                    for key, value in (('sandbox_mode', '0'), ('sms_provider', 'disabled')):
                        row = db.session.get(Setting, key)
                        if row and row.value in ('1', 'demo', ''):
                            row.value = value
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    _lexc('app.disable_legacy_demo_data')
                return True
            _ttl_cache('legacy_demo_disabled_v1', 86400, _disable_legacy_demo_data)

        # بکاپ خودکار دیتابیس: بررسی هر ۱ ساعت برای کاهش ترافیک دیسک
        # ⚠️ کپی فایل دیتابیس در نخ پس‌زمینه انجام می‌شود تا درخواست را قفل نکند
        def _run_backup_check():
            try:
                import os as _os
                bk_dir = _os.path.join(app.instance_path, 'backups')
                _os.makedirs(bk_dir, exist_ok=True)
                import glob as _glob
                _lock_f = None
                try:
                    import fcntl
                    _lock_f = open(_os.path.join(app.instance_path, 'backup.lock'), 'w')
                    fcntl.flock(_lock_f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    return True
                except Exception:
                    pass
                try:
                    # مسیر واقعی SQLite را از engine بگیر؛ DATABASE_URL ممکن است
                    # به فایلی خارج از instance اشاره کند. برای MySQL بکاپ فایل
                    # بی‌معناست و پنل بکاپ دامپ جداگانه می‌سازد.
                    if db.engine.dialect.name != 'sqlite':
                        return True
                    source_db = db.engine.url.database
                    if not source_db or source_db == ':memory:':
                        return True
                    source_db = _os.path.abspath(source_db)
                    if not _os.path.isfile(source_db):
                        app.logger.warning('automatic backup skipped; SQLite file missing: %s', source_db)
                        return True
                    bks = sorted(_glob.glob(_os.path.join(bk_dir, 'academy-*.db')), key=_os.path.getmtime)
                    need = not bks or (time.time() - _os.path.getmtime(bks[-1])) > 86400
                    if need:
                        # sqlite3.backup با WAL سازگار و از copy2 ایمن‌تر است.
                        import sqlite3 as _sqlite3
                        from datetime import datetime as _dt
                        target_db = _os.path.join(
                            bk_dir, f'academy-{_dt.now():%Y%m%d-%H%M}.db')
                        src_conn = _sqlite3.connect(source_db, timeout=15)
                        dst_conn = _sqlite3.connect(target_db)
                        try:
                            src_conn.backup(dst_conn)
                        finally:
                            dst_conn.close()
                            src_conn.close()
                        for old_bk in bks[-7::-1]:
                            try:
                                _os.remove(old_bk)
                            except Exception:
                                _lexc('app.py')
                finally:
                    try:
                        _lock_f and _lock_f.close()
                    except Exception:
                        pass
            except Exception:
                _lexc('app.py')
            return True

        def _start_backup():
            import threading as _thr

            def _runner():
                with app.app_context():
                    _run_backup_check()
            _t = _thr.Thread(target=_runner, daemon=True)
            _t.start()

        _ttl_cache('bk_daily_check', 3600, _start_backup)
        # صفحات صفحه‌ساز (هدر، فوتر، منوی موبایل، خانه...)
        g.pages = {}
        g.page_custom_header = None
        g.page_custom_footer = None
        def _get_all_pages():
            res = {}
            from models import Page
            from cache_safe import page_lite
            try:
                due = Page.query.filter(Page.publish_at.isnot(None),
                                        Page.publish_at <= utcnow()).all()
                for p in due:
                    p.is_published = True
                    p.publish_at = None
                if due:
                    db.session.commit()
            except Exception:
                _lexc('app.py')
            # نسخهٔ سبک و غیر-ORM (ایمن برای کش بین درخواست‌ها)
            for p in Page.query.all():
                res[p.ptype] = page_lite(p)
            return res
        try:
            g.pages = _ttl_cache('all_pages', 60, _get_all_pages)
        except Exception:
            _lexc('app.py')
        g.user = None
        uid = session.get('uid')
        if uid:
            g.user = db.session.get(User, uid)
            if g.user and not g.user.is_active:
                session.clear()
                g.user = None
            elif g.user and session.get('st') and g.user.session_token and session['st'] != g.user.session_token:
                # سشن از دستگاه دیگری باطل شده است (خروج از همه دستگاه‌ها)
                session.clear()
                g.user = None
                from flask import flash as _flash
                _flash('سشن شما در دستگاه دیگری بسته شد. دوباره وارد شوید.', 'info')

        # تا قبل از ورود صحیح کد دوم، uid موجود در سشن نباید امکان دورزدن 2FA
        # با تایپ مستقیم /admin را بدهد.
        if g.user and session.get('admin_2fa_hash'):
            allowed_2fa = (request.path.startswith('/static/') or
                           request.endpoint in ('auth.admin_2fa', 'auth.logout'))
            if not allowed_2fa:
                return redirect(url_for('auth.admin_2fa'))

        # نصب تازه برای عموم غیرفعال است؛ نبودن کلید برای نصب‌های قدیمی به معنی
        # فعال بودن است تا یک به‌روزرسانی، سایت در حال کار را ناگهان نبندد.
        if g.settings.get('site_active', '1') != '1' and not (g.user and g.user.is_admin):
            allowed_inactive = (
                request.path.startswith(('/static/', '/install')) or
                request.endpoint in ('health', 'site.maintenance', 'auth.login',
                                     'auth.admin_2fa', 'auth.logout') or
                (request.endpoint or '').startswith('admin.')
            )
            if not allowed_inactive:
                return redirect(url_for('site.maintenance'))

        daily_reminders()
        # ---------- حفاظت از فایل‌های خصوصی (uploads) ----------
        # مسیرهای جدید /uploads/... و قدیمی /static/uploads/... هر دو چک می‌شوند
        _p = request.path
        _uploads_prefix = '/static/uploads/' if _p.startswith('/static/uploads/') else                           ('/uploads/' if _p.startswith('/uploads/') else None)
        if _uploads_prefix:
            _rel = _p[len(_uploads_prefix):]
            _folder = _rel.split('/')[0] if '/' in _rel else _rel
            if _folder not in ('lessons', 'proofs', 'submissions', 'tickets', 'forms'):
                return None  # media و opt عمومی هستند
            if not g.user:
                return redirect(url_for('auth.login', next=_p))
            try:
                from models import (Lesson as _L, PaymentProof as _Pr, AssignmentSubmission as _As,
                                    Ticket as _T, TicketReply as _Tr, Assignment as _Asg,
                                    Enrollment as _En, Course as _Co, CourseTeacher as _Ct)
                if _folder == 'lessons':
                    _fname = _rel.split('/')[-1]
                    # جستجو با نام فایل — مسیر ذخیره‌شده ممکن است قدیمی/جدید باشد
                    _les_all = _L.query.filter(_L.file_url.like('%/' + _fname)).all()
                    if _les_all and (g.user.is_admin or any(
                            _En.query.filter_by(user_id=g.user.id,
                                                course_id=_l.section.course_id).first()
                            for _l in _les_all)):
                        return None
                elif _folder == 'proofs':
                    _fname = _rel.split('/')[-1]
                    _proof = _Pr.query.filter_by(file=_fname).first()
                    if _proof:
                        _ord = db.session.get(Order, _proof.order_id)
                        if g.user.is_admin or (_ord and _ord.user_id == g.user.id):
                            return None
                elif _folder == 'submissions':
                    _fname = _rel.split('/')[-1]
                    _sub = _As.query.filter_by(file=_fname).first()
                    if _sub:
                        if g.user.id == _sub.user_id or g.user.is_admin:
                            return None
                        _asg = db.session.get(_Asg, _sub.assignment_id)
                        if _asg:
                            _c = db.session.get(_Co, _asg.course_id)
                            if _c and (_c.teacher_id == g.user.id or
                                       _Ct.query.filter_by(course_id=_asg.course_id, teacher_id=g.user.id).first()):
                                return None
                elif _folder == 'tickets':
                    _fname = _rel.split('/')[-1]
                    _t = _T.query.filter_by(attachment=_fname).first()
                    _tr = _Tr.query.filter_by(attachment=_fname).first()
                    if _t and (g.user.is_admin or _t.user_id == g.user.id):
                        return None
                    if _tr and (g.user.is_admin or (_tr.ticket and _tr.ticket.user_id == g.user.id)):
                        return None
                elif _folder == 'forms':
                    if g.user.is_admin:
                        return None
            except Exception:
                _lexc('app.py')
            # پاسخ ساده 403 — بدون قالب (context processor ها هنوز اجرا نشده‌اند)
            from flask import Response as _Resp
            return _Resp('دسترسی غیرمجاز', status=403)
                # ریدایرکت‌های 301 (مدیریت‌شده از پنل سئو) — با کش ۶۰ ثانیه
        # ⚠️ قبلاً در هر درخواست یک کوئری دیتابیس می‌زد
        if not request.path.startswith('/static/') and not request.path.startswith('/builder/api'):
            try:
                def _get_rules():
                    from models import RedirectRule
                    return [(r.source, r.target, r.code or 301) for r in
                            RedirectRule.query.filter_by(is_active=True).all()]
                for _src, _tgt, _code in _ttl_cache('redirect_rules', 60, _get_rules):
                    if _src == request.path:
                        # فقط مسیر نسبی داخلی — ریدایرکت خارجی = فیشینگ/Safe Browsing
                        _tgt = str(_tgt or '').strip()
                        if not _tgt.startswith('/') or _tgt.startswith('//') or '\\' in _tgt:
                            continue
                        if any(ch in _tgt for ch in ('\r', '\n', '\x00')):
                            continue
                        return redirect(_tgt, code=_code)
            except Exception:
                _lexc('app.py')
        # حالت تعمیرات: فقط ادمین می‌تواند وارد شود
        if g.settings.get('maintenance') == '1' and not (g.user and g.user.is_admin):
            allowed = request.path.startswith('/static') or \
                request.endpoint in ('site.maintenance', 'auth.login', 'auth.logout') or \
                (request.endpoint or '').startswith('admin')
            if not allowed:
                return redirect(url_for('site.maintenance'))
        if g.user and not g.user.profile_complete() and request.endpoint and \
                request.endpoint.startswith('student.') and request.endpoint != 'student.profile':
            # کاربرانی که با شماره تماس وارد شده‌اند باید پروفایل را کامل کنند
            return redirect(url_for('auth.complete_profile'))
        # ظاهر سایت فقط از طراحی ذخیره‌شدهٔ مدیر می‌آید. انتخاب شخصی بازدیدکننده
        # و کوکی قدیمی تم عمداً نادیده گرفته می‌شوند تا رنگ/ظاهر در همه صفحات
        # ثابت بماند. پیش‌نمایش URL نیز فقط برای مدیر واردشده مجاز است.
        from designs import SITE_DESIGNS
        _pv = request.args.get('site_design', '') if (g.user and g.user.is_admin) else ''
        _saved_design = g.settings.get('site_design', '')
        sd = _pv if _pv in SITE_DESIGNS else (_saved_design or '1')
        if sd in SITE_DESIGNS:
            theme = SITE_DESIGNS[sd]['theme']
        else:
            theme = g.settings.get('default_theme', 'theme-01')
        if theme not in VALID_THEMES:
            theme = 'theme-01'
        g.theme = theme
        # رنگ مرورگر (theme-color) — برای طرح‌های ایرانی از پالت آن‌ها
        g.theme_color = None
        if theme.startswith('pd-'):
            try:
                from persian_themes import get_theme as _gt
                _t = _gt(theme)
                if _t:
                    g.theme_color = _t['colors']['primary']
            except Exception:
                pass
        # مقادیر مؤثر طراحی (کانتینر و شعاع گوشه)
        g.eff_container = g.settings.get('kit_container') or ''
        g.eff_radius = g.settings.get('kit_radius') or ''
        if not g.eff_container and sd in SITE_DESIGNS:
            g.eff_container = SITE_DESIGNS[sd]['container']
        if not g.eff_radius and sd in SITE_DESIGNS:
            g.eff_radius = SITE_DESIGNS[sd]['radius']
        # سبد خرید
        g.cart = session.get('cart', [])
        quantities = session.get('cart_qty', {}) or {}
        def _cart_item_count(item):
            if not str(item).startswith('p:'):
                return 1
            try:
                return max(1, int(quantities.get(str(item), 1) or 1))
            except (TypeError, ValueError):
                return 1
        g.cart_count = sum(_cart_item_count(item) for item in g.cart)
        # موتور سئو (بعد از بارگذاری تنظیمات)
        from models import SeoMeta
        g.seo = dict(title='', description='', keywords='', canonical='', noindex=False,
                     og_image='', og_type='website', schema=None)
        try:
            path = request.path

            def _get_seo():
                row = SeoMeta.query.filter_by(path=path).first()
                if not row:
                    return None
                # نسخهٔ صرف (غیر-ORM) — ایمن برای کش بین درخواست‌ها
                return dict(title=row.title or '', description=row.description or '',
                            keywords=row.keywords or '', canonical=row.canonical or '',
                            noindex=bool(row.noindex), og_image=row.og_image or '')
            m = _ttl_cache(f'seo:{path[:80]}', 120, _get_seo)
            if m:
                g.seo['title'] = m['title']
                g.seo['description'] = m['description']
                g.seo['keywords'] = m['keywords']
                g.seo['canonical'] = m['canonical']
                g.seo['noindex'] = m['noindex']
                g.seo['og_image'] = m['og_image']
            if not g.seo['title']:
                g.seo['title'] = g.settings.get('seo_title', '')
            if not g.seo['description']:
                g.seo['description'] = g.settings.get('seo_desc', '')
            g.seo['keywords'] = g.seo['keywords'] or g.settings.get('seo_keywords', '')
            if not g.seo['og_image']:
                g.seo['og_image'] = g.settings.get('seo_og_image', 'hero.webp')
            if not g.seo['canonical']:
                g.seo['canonical'] = request.base_url.split('?')[0]
            if request.endpoint and (request.endpoint.startswith('admin') or
                                     request.endpoint.startswith('builder')):
                g.seo['noindex'] = True
            # صفحات پرداخت/سبد/حساب هرگز نباید ایندکس شوند.
            # (ایندکس‌شدن صفحه شبیه‌ساز پرداخت باعث فلگ‌شدن دامنه توسط
            #  Google Safe Browsing با عنوان «Dangerous site» می‌شود)
            _p = request.path or ''
            if (_p.startswith('/pay') or _p.startswith('/checkout') or
                    _p.startswith('/cart') or _p.startswith('/dashboard') or
                    _p.startswith('/auth') or _p.startswith('/install') or
                    _p.startswith('/wallet') or _p.startswith('/uploads') or
                    _p.startswith('/license')):
                g.seo['noindex'] = True
        except Exception:
            _lexc('app.py')

    # ---------- کش صفحه (HTML) برای بازدیدکنندگان مهمان ----------
    # صفحات عمومی (خانه، دوره‌ها، وبلاگ و...) برای کاربران بدون سشن کش می‌شوند.
    # کلید شامل توکن CSRF سشن است تا محتوای شخصی‌سازی‌شده بین کاربران لو نرود.
    # (باید بعد از load_globals ثبت شود تا g.user و سشن آماده باشند)
    _html_cache = {}
    _HTML_PUBLIC = ('/', '/course/', '/courses', '/blog', '/about', '/faq', '/contact',
                    '/terms', '/privacy', '/teachers', '/bundles', '/success-stories',
                    '/learning-paths', '/talent-test', '/products', '/product/',
                    '/search', '/sitemap.xml', '/robots.txt', '/feed')

    def _html_cache_key():
        try:
            if request.method != 'GET':
                return None
            p = request.path
            for _x in ('/admin', '/builder', '/install', '/license', '/api', '/static',
                       '/uploads', '/auth', '/dashboard', '/teacher-panel', '/student',
                       '/community', '/exam', '/wallet', '/pay', '/cart', '/checkout',
                       '/newsletter', '/feedback', '/form/'):
                if p.startswith(_x):
                    return None
            # عضو '/' فقط خود صفحه خانه است؛ startswith('/') تمام مسیرها را
            # cache می‌کرد و می‌توانست صفحه حساس/پویا مثل فعال‌سازی را stale کند.
            is_public = p == '/' or any(
                x != '/' and (p == x or p.startswith(x)) for x in _HTML_PUBLIC)
            if not is_public:
                return None
            if session.get('uid') or session.get('_flashes'):
                return None
            _qs = request.query_string.decode('utf-8', 'replace')
            return f'{p}?{_qs}|c={session.get("_csrf_token", "")}|a={_asset_v()}'
        except Exception:
            return None

    @app.before_request
    def html_cache_serve():
        if getattr(g, 'user', None):
            return None
        _key = _html_cache_key()
        if not _key:
            return None
        _now = time.time()
        with _cache_lock:
            _hit = _html_cache.get(_key)
            if _hit and _now - _hit[0] < _hit[1]:
                from flask import Response as _Resp
                return _Resp(_hit[2], status=200,
                             mimetype='text/html',
                             headers={'Content-Length': str(len(_hit[2]))})
        return None

    def daily_reminders():
        """یادآوری‌های روزانه — در پس‌زمینه اجرا می‌شود تا درخواست را قفل نکند.

        ⚠️ قبلاً روی اولین درخواست هر ۱۵ دقیقه اجرا می‌شد و برای هر دانشجو/سفارش
        یک INSERT می‌زد (در دیتابیس بزرگ = هزاران INSERT در مسیر درخواست → کندی شدید
        و قفل SQLite). حالا: نخ جدا + قفل بین‌پردازه‌ای + بدون اعلان تکراری."""
        import threading as _thr

        def _run_reminders():
            try:
                from datetime import timedelta as _td
                from models import LiveSession, Order, Notification, Enrollment
                _lock_f = None
                # قفل بین‌پردازه‌ای: فقط یک ورکر (از بین چند ورکر gunicorn) اجرا کند
                try:
                    import fcntl
                    _lock_f = open(os.path.join(app.instance_path, 'reminders.lock'), 'w')
                    fcntl.flock(_lock_f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    return True  # ورکر دیگری در حال اجراست
                except Exception:
                    pass
                try:
                    new_notifs = []
                    _title_live = 'کلاس آنلاین به‌زودی 🎥'
                    _title_order = 'خرید شما ناتمام مانده 🛒'
                    # کلاس‌های ۲۴ ساعت آینده
                    soon = LiveSession.query.filter(
                        LiveSession.starts_at >= utcnow(),
                        LiveSession.starts_at <= utcnow() + _td(hours=24)).all()
                    for ls in soon:
                        if not ls.course_id:
                            continue
                        # فقط شناسه دانشجوها — نه بارگذاری همه رکوردها
                        uids = [r[0] for r in db.session.query(Enrollment.user_id)
                                .filter_by(course_id=ls.course_id).distinct().all()]
                        if not uids:
                            continue
                        # در نخ پس‌زمینه request context وجود ندارد → آدرس مستقیم
                        _link = '/community/live'
                        # حذف کسانی که قبلاً اعلان گرفته‌اند (ضد تکرار هر ۱۵ دقیقه)
                        seen = set(r[0] for r in db.session.query(Notification.user_id)
                                   .filter(Notification.user_id.in_(uids),
                                           Notification.title == _title_live).all())
                        for uid in uids:
                            if uid not in seen:
                                new_notifs.append(Notification(
                                    user_id=uid, title=_title_live,
                                    body=f'«{ls.title}» شروع می‌شود — لینک ورود فعال است.',
                                    icon='🎥', link=_link))
                    # سفارش‌های ناقص (۲۴+ ساعت)
                    pending = Order.query.filter(Order.status == 'pending',
                                                 Order.created_at <= utcnow() - _td(hours=24)).all()
                    if pending:
                        # بررسی تکراری‌ها با یک کوئری گروهی (نه یکی‌یکی)
                        _links = [f'/pay/{o.code}' for o in pending]
                        _seen = set()
                        for _row in db.session.query(Notification.link).filter(
                                Notification.link.in_(_links),
                                Notification.title == _title_order).all():
                            _seen.add(_row[0])
                        for o in pending:
                            _link = f'/pay/{o.code}'
                            if _link in _seen:
                                continue
                            new_notifs.append(Notification(
                                user_id=o.user_id, title=_title_order,
                                body=f'سفارش {o.code} هنوز پرداخت نشده — با تخفیف فعلی تکمیلش کن!',
                                icon='🛒', link=_link))
                    # درج یکجا (bulk) — نه یکی‌یکی
                    if new_notifs:
                        for _chunk_start in range(0, len(new_notifs), 500):
                            db.session.add_all(new_notifs[_chunk_start:_chunk_start + 500])
                            db.session.commit()
                finally:
                    try:
                        _lock_f and _lock_f.close()
                    except Exception:
                        pass
            except Exception:
                _lexc('app.py')
            return True

        def _start():
            def _runner():
                # نخ پس‌زمینه سشن/کانتکست خودش را ندارد — باید کانتکست بسازد
                with app.app_context():
                    _run_reminders()
            _t = _thr.Thread(target=_runner, daemon=True)
            _t.start()

        _ttl_cache('reminders_job', 900, _start)
    @app.context_processor
    def inject_helpers():
        def log_activity(action, detail=''):
            """ثبت رویداد در لاگ فعالیت — از قالب‌ها و routeها قابل فراخوانی"""
            try:
                from models import ActivityLog
                db.session.add(ActivityLog(
                    user_id=g.user.id if g.user else None,
                    action=action, detail=detail[:280],
                    ip=request.headers.get('X-Forwarded-For', request.remote_addr or '')[:60]))
                db.session.commit()
            except Exception:
                db.session.rollback()
        return dict(log_activity=log_activity)

    @app.context_processor
    def inject_captcha():
        """کادر کپچای ضداسپم برای فرم‌های عمومی"""
        from captcha import current_captcha
        from markupsafe import Markup, escape
        def captcha_box():
            text = escape(current_captcha())
            return Markup(
                '<div class="form-group">'
                '<label for="cap_inp">🧮 سوال امنیتی: <b>' + text + '</b></label>'
                '<input id="cap_inp" class="form-control" name="captcha" required dir="ltr" '
                'style="max-width:180px" autocomplete="off" placeholder="پاسخ">'
                '<input type="text" name="hp_website" value="" tabindex="-1" autocomplete="off" '
                'aria-hidden="true" style="position:absolute;left:-9999px;opacity:0;height:0">'
                '</div>')
        return dict(captcha_box=captcha_box)

    @app.context_processor
    def inject_globals():
        # اسکریپت‌های سرویس‌های رایگان (Clarity/Crisp) — از .env
        try:
            from integrations import clarity_script, crisp_script
            _clarity = clarity_script()
            _crisp = crisp_script()
        except Exception:
            _clarity, _crisp = '', ''
        cats = []
        fav_ids = set()
        enrolled_ids = set()
        try:
            cats = _ttl_cache('all_categories', 120, _get_all_categories)
            if getattr(g, 'user', None):
                from models import Favorite, Enrollment
                _u0 = g.user
                fav_ids = {(_u0.id, f.course_id) for f in
                           Favorite.query.filter_by(user_id=_u0.id).all()}
                enrolled_ids = {e.course_id for e in
                                Enrollment.query.filter_by(user_id=_u0.id).all()}
        except Exception:
            _lexc('app.py')
        def _real_gateway_configured():
            """آیا حداقل یک درگاه پرداخت بانکیِ واقعی کامل پیکربندی شده است؟"""
            try:
                from gateways import GATEWAYS, gateway_ready
                _st = getattr(g, 'settings', {}) or {}
                return any(gateway_ready(_gw['id'], _st)
                           for _gw in GATEWAYS
                           if _gw.get('kind') in ('real', 'bank'))
            except Exception:
                return False

        def _bnpl_configured():
            try:
                from gateways import GATEWAYS, gateway_ready
                _st = getattr(g, 'settings', {}) or {}
                if _st.get('bnpl_enabled') != '1':
                    return False
                return any(_gw.get('kind') == 'installment' and
                           gateway_ready(_gw['id'], _st) for _gw in GATEWAYS)
            except Exception:
                return False

        from gamification import user_badges
        from permissions import has_permission, can_access_endpoint, ROLES
        from gateways import gateway_fa as _gateway_name
        try:
            from sms import provider_ready as _sms_provider_ready
            _sms_ready = _sms_provider_ready(getattr(g, 'settings', {}) or {})
        except Exception:
            _sms_ready = False
        unread_count = 0
        _u = getattr(g, 'user', None)
        if _u:
            try:
                from models import Notification
                unread_count = Notification.query.filter_by(user_id=_u.id, is_read=False).count()
            except Exception:
                pass
        return dict(site=getattr(g, 'settings', {}), cur_user=_u, site_categories=cats,
                    unread_notifications=unread_count,
                    current_role=(ROLES.get(_u.role, {}).get('fa') if _u else ''),
                    role_name=lambda user: ROLES.get(getattr(user, 'role', ''), {}).get('fa', 'کاربر'),
                    has_perm=has_permission,
                    can_manage_panel=can_access_endpoint(_u, 'admin.overview') if _u else False,
                    my_badges=user_badges(_u) if _u else [],
                    cart_ids=getattr(g, 'cart', []), cart_count=getattr(g, 'cart_count', 0),
                    theme=getattr(g, 'theme', 'theme-01'),
                    fav_ids=fav_ids, now=utcnow(), builder_pages=getattr(g, 'pages', {}),
                    enrolled_ids=enrolled_ids,
                    eff_container=getattr(g, 'eff_container', ''),
                    eff_radius=getattr(g, 'eff_radius', ''),
                    csrf_token=_CSRFTokenValue(getattr(g, 'csrf_token', '')),
                    # آیا درگاه پرداخت بانکی واقعی پیکربندی شده است؟
                    # ادعاهای «پرداخت امن شتاب / درگاه بانکی معتبر» فقط وقتی نمایش
                    # داده می‌شوند که واقعاً درست باشند — ادعای نادرست دربارهٔ
                    # پرداخت بانکی، «محتوای فریب‌دهنده» محسوب می‌شود و یکی از
                    # دلایل علامت خوردن دامنه با «Dangerous site» است.
                    real_gateway_on=_real_gateway_configured(),
                    gateway_name=_gateway_name,
                    bnpl_available=_bnpl_configured(),
                    sms_ready=_sms_ready,
                    # در قالب‌ها نیز بخش‌های آزمایشی فقط در محیط تست صریح قابل مشاهده‌اند.
                    demo_features_enabled=_demo_features_enabled(),
                    license_state=getattr(g, 'license_state', None),
                    clarity_script=_clarity, crisp_script=_crisp,
                    bc_admin_menu=lambda: __import__('permissions', fromlist=['menu_for']).menu_for(_u),
                    bc_admin_groups=lambda: __import__('permissions', fromlist=['menu_groups_for']).menu_groups_for(_u),
                    group_has_active=_group_has_active,
                    seo=getattr(g, 'seo', dict(title='', description='', keywords='',
                                               canonical='', noindex=False, og_image='',
                                               og_type='website', schema=None)))

    def _group_has_active(group, request):
        """آیا دسته‌ای از منوی ادمین شامل صفحهٔ فعلی است؟ (باز بودن خودکار گروه)"""
        current = request.endpoint or ''
        for ep, _label in (group.get('items') or []):
            if current == ep:
                return True
            if ep and '.' in ep:
                prefix = ep.split('.')[0] + '.'
                second = ep.split('.')[1]
                if current.startswith(prefix) and ('.' not in current[len(prefix):] or
                                                   current[len(prefix):].split('.')[0] == second):
                    return True
        return False

    # ---------- سلامت سرویس (برای مانیتورینگ؛ بدون افشای جزئیات) ----------
    @app.route('/health')
    def health():
        from flask import jsonify
        license_status = getattr(g, 'license_state', None)
        if license_status and license_status.enforced and not license_status.valid:
            return jsonify(ok=False, status='license_required',
                           license=license_status.code), 503
        try:
            db.session.execute(db.text('SELECT 1'))
            return jsonify(ok=True, status='healthy',
                           license=license_status.code if license_status else 'unknown'), 200
        except Exception:
            db.session.rollback()
            return jsonify(ok=False, status='unavailable'), 503

    # ---------- خطاها ----------
    _nf_log_throttle = {}
    _nf_log_counts = {}

    @app.errorhandler(404)
    def not_found(e):
        # مسیرهای نصب: همیشه JSON (مرورگر نصب‌کننده هرگز HTML نمی‌گیرد)
        if request.path.startswith('/install'):
            from flask import jsonify as _j
            return _j(ok=False, msg='مسیر نصب یافت نشد', code=404), 404
        # ثبت 404 در مانیتور (ردیابی لینک‌های شکسته)
        # ⚠️ محدود به یک نوشتن در دقیقه برای هر مسیر — ربات‌ها که 404 می‌گیرند
        # قبلاً باعث سیل INSERT/UPDATE و قفل SQLite (خطای 500) می‌شدند
        try:
            if not request.path.startswith('/static/') and not request.path.startswith('/api'):
                _now = time.time()
                _throttled = False
                with _cache_lock:
                    _last = _nf_log_throttle.get(request.path)
                    if _last and _now - _last < 60:
                        _throttled = True
                    else:
                        _nf_log_throttle[request.path] = _now
                        if len(_nf_log_throttle) > 2000:
                            _nf_log_throttle.clear()
                if not _throttled:
                    from models import NotFoundLog
                    log = NotFoundLog.query.filter_by(path=request.path).first()
                    if log:
                        log.count += 1
                        log.referrer = request.referrer or log.referrer
                    else:
                        db.session.add(NotFoundLog(path=request.path[:300],
                                                   referrer=(request.referrer or '')[:400]))
                    db.session.commit()
                else:
                    # حتی بدون نوشتن، بازدید 404 را با یک شمارنده حافظه‌ای ثبت کن
                    _nf_log_counts[request.path] = _nf_log_counts.get(request.path, 0) + 1
        except Exception:
            _lexc('app.py')
        # اگر صفحه ۴۰۴ با صفحه‌ساز ساخته شده باشد
        try:
            from models import Page as _P
            ep = _P.query.filter_by(ptype='404', is_published=True).first()
            if ep and ep.rows():
                from flask import render_template as _rt
                g.page_settings = ep.settings()
                return _rt('builder/public.html', page=ep), 404
        except Exception:
            _lexc('app.py')
        return render_template('errors/standalone_error.html',
                               err_title='صفحه مورد نظر پیدا نشد',
                               err_msg='آدرس وارد شده اشتباه است یا حذف شده است.',
                               err_code=404), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/standalone_error.html',
                               err_title='دسترسی غیرمجاز',
                               err_msg='شما اجازه دسترسی به این بخش را ندارید.',
                               err_code=403), 403

    @app.errorhandler(500)
    def server_error(e):
        # ثبت کامل traceback در فایل لاگ — بدون لو دادن جزئیات به کاربر
        try:
            import traceback as _tb
            app.logger.error('500 Internal Server Error: %s\n%s',
                             e, _tb.format_exc())
        except Exception:
            pass
        # قالب مستقل — چون خطای 500 اغلب از دیتابیس است و base.html به دیتابیس نیاز دارد
        return render_template('errors/standalone_error.html',
                               err_title='خطای سرور',
                               err_msg='مشکلی در سرور رخ داده است. لطفاً کمی بعد تلاش کنید.',
                               err_code=500), 500

    def render_error(title, msg, code):
        from flask import render_template
        return render_template('errors/error.html', err_title=title, err_msg=msg,
                               err_code=code), code

    return app


app = create_app()

if __name__ == '__main__':
    # ساخت جدول‌ها هنگام اجرای مستقیم — اگر دیتابیس در دسترس نبود، به‌جای
    # کرش با تریس‌بک خام، پیام فارسی روشن نشان بده (خطای 2013 روی هاست).
    try:
        with app.app_context():
            db.create_all()
    except Exception as _e:
        print('\n⚠️  اتصال به دیتابیس برقرار نشد — جدول‌ها ساخته نشدند.')
        print('   علت: %s: %s' % (type(_e).__name__, str(_e)[:300]))
        print('   برای عیب‌یابی اجرا کنید:  python scripts/diagnose_db.py\n')
    # debug فقط در محیط توسعه — در production هرگز
    _debug = os.environ.get('FLASK_ENV', 'development') != 'production'
    app.run(host='0.0.0.0', port=5000, debug=_debug)

