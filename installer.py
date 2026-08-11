# -*- coding: utf-8 -*-
"""
نصب‌کننده خودکار آکادمی — شبیه نصب‌کننده وردپرس
- اتصال به دیتابیس (SQLite یا MySQL) و ساخت جدول‌ها
- ساخت حساب مدیر + دانشجوی نمونه
- سید داده‌های اولیه (دسته‌ها، تنظیمات، صفحه اصلی، دوره نمونه، کوپن)
- نوشتن .env و علامت نصب (.installed)
"""
import json
import os
import secrets
import shutil
import time
import urllib.parse
from datetime import datetime
try:
    from datetime import UTC
except ImportError:  # پایتون < 3.11 (هاست‌های اشتراکی)
    from datetime import timezone as _tz_utc
    UTC = _tz_utc.utc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
MARKER = os.path.join(INSTANCE_DIR, '.installed')


def is_installed():
    """آیا نصب انجام شده؟ (فایل نشانگر + رکورد setting)"""
    if os.path.exists(MARKER):
        return True
    try:
        from models import Setting
        st = Setting.query.filter_by(key='site_name').first()
        if st and st.value:
            try:
                os.makedirs(INSTANCE_DIR, exist_ok=True)
                with open(MARKER, 'w', encoding='utf-8') as f:
                    f.write('{"seeded": true}')
            except Exception:
                pass
            return True
    except Exception:
        pass
    return False


def mark_installed(meta):
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    meta['installed_at'] = datetime.now(UTC).isoformat()
    with open(MARKER, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _clean_host(host):
    """پاک‌سازی آدرس میزبان — حذف فاصله و اسلش‌های اضافه"""
    return (host or '').strip().strip('/').strip()


def validate_mysql(host, name, user):
    """اعتبارسنجی فیلدهای MySQL — خروجی: پیام خطا یا رشته خالی"""
    host = _clean_host(host)
    if not host:
        return 'آدرس (Host) خالی است — معمولاً «localhost»'
    if any(ch in host for ch in ' @#:/?\\'):
        return (f'آدرس (Host) نامعتبر است: «{host}» — فقط آدرس میزبان را وارد کنید '
                '(مثل localhost یا sql.example.com) بدون @ و # و فاصله.')
    if not (name or '').strip():
        return 'نام دیتابیس خالی است.'
    if not (user or '').strip():
        return 'نام کاربری خالی است.'
    return ''


def build_db_url(db_type, host='', port='', name='', user='', password=''):
    """ساخت URL اتصال از فرم نصب — SQLite خالی برمی‌گرداند (پیش‌فرض اپ)
    رمز/نام کاربری URL-encode می‌شوند تا کاراکترهای خاص (@ # ! و...) رشته را نشکنند
    """
    if db_type == 'mysql':
        host = _clean_host(host)
        port = (port or '').strip() or '3306'
        user = (user or '').strip()
        name = (name or '').strip().strip('/')
        return (f"mysql+pymysql://{urllib.parse.quote(user, safe='')}:"
                f"{urllib.parse.quote(password, safe='')}@{host}:{port}/{name}"
                "?charset=utf8mb4")
    return ''


def _default_sqlite_url():
    """مسیر پیش‌فرض SQLite — همان مسیری که اپ استفاده می‌کند"""
    return 'sqlite:///' + os.path.join(INSTANCE_DIR, 'academy.db')


def resolve_url(db_url):
    """خالی → SQLite پیش‌فرض"""
    return db_url or _default_sqlite_url()


def _friendly_db_error(e, db_url):
    """تبدیل خطای اتصال به پیام فارسی قابل فهم + بدون لو دادن رمز"""
    msg = str(e)[:500]
    msg = msg.split('(Background on this error')[0].strip()
    # حذف URL کامل از پیام (ممکن است رمز داشته باشد)
    for part in (db_url, db_url.split('?')[0]):
        if part:
            msg = msg.replace(part, '…')
    # استخراج متن اصلی خطای pymysql: (2003, "Can't connect ...")
    import re as _re
    m = _re.search(r'\(\d+, "([^"]+)"\)', msg)
    if m:
        msg = m.group(1)
    low = msg.lower()
    if 'can\'t connect' in low or '2003' in low or 'getaddrinfo' in low or 'name or service not known' in low:
        return ('سرور MySQL پیدا نشد — آدرس (Host) را دقیقاً از پنل هاست بردارید '
                '(اکثر هاست‌ها: localhost). جزئیات: ' + msg[-120:])
    if 'access denied' in low and 'to database' in low:
        return ('دیتابیس با این نام وجود ندارد یا کاربر به آن دسترسی ندارد — اول در پنل هاست '
                '(مثلاً cPanel → MySQL Databases) دیتابیس را بسازید و کاربر را به آن وصل کنید. جزئیات: ' + msg[-120:])
    if 'access denied' in low or '1045' in low:
        return 'نام کاربری یا رمز MySQL اشتباه است. جزئیات: ' + msg[-120:]
    if 'unknown database' in low or '1049' in low or '1044' in low:
        return ('دیتابیس با این نام وجود ندارد — اول در پنل هاست (مثلاً cPanel → MySQL Databases) '
                'آن را بسازید. جزئیات: ' + msg[-120:])
    if 'timed out' in low or 'timeout' in low:
        return 'زمان اتصال به پایان رسید — آدرس یا پورت را بررسی کنید (پورت پیش‌فرض: 3306).'
    return msg[-250:]


def _dns_quick_check(host, timeout=6):
    """چک سریع DNS با تایم‌اوت — بدون hang طولانی (هاست‌های اشتراکی پراکسی کوتاه دارند)
    خروجی: (ok, message)
    """
    import socket as _sock
    import threading as _thr2
    res = {}
    def _resolve():
        try:
            _sock.gethostbyname(host)
            res['ok'] = True
        except Exception as e:
            res['ok'] = False
            res['msg'] = str(e)
    t = _thr2.Thread(target=_resolve, daemon=True)
    t.start()
    t.join(timeout)
    if 'ok' not in res:
        return False, 'پیدا کردن آدرس (Host) بیش از حد طول کشید — آدرس را بررسی کنید'
    if not res.get('ok'):
        return False, res.get('msg', 'خطای DNS')
    return True, ''


def ensure_mysql_db(db_url):
    """تلاش برای ساخت خودکار دیتابیس در زمپ / MySQL در صورتی که دیتابیس وجود نداشته باشد"""
    if not str(db_url).startswith('mysql'):
        return True, ''
    try:
        from sqlalchemy import create_engine, text
        parts = db_url.split('://', 1)[-1].split('/')
        if len(parts) >= 2:
            db_name_part = parts[1].split('?')[0]
            if db_name_part:
                server_url = db_url.split(f'/{db_name_part}', 1)[0] + '/'
                if '?' in db_url:
                    server_url += '?' + db_url.split('?', 1)[1]
                engine = create_engine(server_url, connect_args={'connect_timeout': 5})
                with engine.connect() as conn:
                    conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name_part}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"))
                    conn.commit()
                engine.dispose()
                return True, f'دیتابیس {db_name_part} به صورت خودکار ساخته شد.'
    except Exception as e:
        return False, str(e)
    return True, ''


def test_connection(db_url):
    """تست اتصال دیتابیس — سریع و ضد-hang — خروجی (ok, message)"""
    try:
        if str(db_url).startswith('mysql'):
            # ۱) چک سریع DNS (قبل از اتصال — هاست‌های خراب را فوری رد می‌کند)
            host = db_url.split('@')[-1].split(':')[0]
            ok_dns, msg_dns = _dns_quick_check(host)
            if not ok_dns:
                return False, ('سرور MySQL پیدا نشد — آدرس (Host) را دقیقاً از پنل هاست بردارید '
                               '(اکثر هاست‌ها: localhost). جزئیات: ' + msg_dns[-100:])
        from sqlalchemy import create_engine
        if str(db_url).startswith('mysql'):
            try:
                eng = _get_engine(db_url)   # TCP → fallback سوکت محلی
                with eng.connect():
                    pass
                eng.dispose()
            except Exception as e:
                err_str = str(e).lower()
                if '1049' in err_str or 'unknown database' in err_str:
                    ok_mk, mk_msg = ensure_mysql_db(db_url)
                    if ok_mk:
                        eng = _get_engine(db_url)
                        with eng.connect():
                            pass
                        eng.dispose()
                        return True, 'اتصال به MySQL برقرار شد و دیتابیس به صورت خودکار ساخته شد ✅'
                raise e
        else:
            eng = create_engine(resolve_url(db_url))
            with eng.connect():
                pass
            eng.dispose()
        mode = _best_conn_cache.get(db_url)
        extra = ' (از طریق سوکت محلی)' if isinstance(mode, tuple) else ''
        return True, 'اتصال برقرار شد ✅' + extra
    except Exception as e:
        return False, 'خطای اتصال: ' + _friendly_db_error(e, db_url)


def write_env_file(db_url, secret_key):
    """به‌روزرسانی .env — حفظ کلیدهای موجود + افزودن دیتابیس/کلید"""
    env_path = os.path.join(BASE_DIR, '.env')
    lines = {}
    if os.path.exists(env_path):
        for ln in open(env_path, encoding='utf-8'):
            ln = ln.strip()
            if ln and not ln.startswith('#') and '=' in ln:
                k, v = ln.split('=', 1)
                lines[k.strip()] = v.strip()
    lines['SECRET_KEY'] = secret_key
    lines['FLASK_ENV'] = 'production'
    lines['APP_ENV'] = 'production'
    if db_url:
        lines['DATABASE_URL'] = db_url
    else:
        lines.pop('DATABASE_URL', None)  # خالی = SQLite پیش‌فرض
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write('# ⚙️ تنظیمات محیطی — ساخته‌شده توسط نصب‌کننده آکادمی\n')
        for k in ('SECRET_KEY', 'FLASK_ENV', 'APP_ENV', 'DATABASE_URL',
                  'LOG_DIR', 'REDIS_URL', 'CLARITY_ID', 'CRISP_WEBSITE_ID',
                  'GROQ_API_KEY', 'BING_API_KEY', 'BING_KEY_LOCATION'):
            if k in lines and lines[k]:
                f.write(f'{k}={lines[k]}\n')
        f.write('\n# تنظیمات دیگر (پرداخت/پیامک/ایمیل) از پنل ادمین ← تنظیمات سوپر\n')
    return env_path


# ============================================================
# داده‌های اولیه (سید)
# ============================================================
HOME_PAGE_JSON = {
    "rows": [
        {"cols": [[{"id": "inst-h1", "type": "slider", "data": {
            "arrows": True, "autoplay": True, "dots": True, "height": "420",
            "interval": "5", "overlay": "60", "radius": "0",
            "slides": [
                {"align": "right", "btn_text": "🚀 مشاهده همه دوره‌ها", "btn_url": "/courses",
                 "img": "hero.webp",
                 "sub": "دوره‌های پروژه‌محور با برترین مدرسان — همین امروز شروع کن!",
                 "title": "آینده‌ات را با مهارت‌های دیجیتال قدرتمندتر بساز"},
                {"align": "center", "btn_text": "شروع یادگیری", "btn_url": "/courses",
                 "img": "cover-flask.webp",
                 "sub": "آموزش عملی ویدیویی به همراه تمرین و آزمون.",
                 "title": "آموزش پروژه‌محور؛ از صفر تا یک محصول واقعی"}
            ]}}]]},
        {"cols": [[{"id": "inst-h2", "type": "stats", "data": {
            "columns": "4",
            "items": [
                {"icon": "🎓", "label": "دانشجوی فعال", "value": "{students}"},
                {"icon": "📚", "label": "دوره تخصصی", "value": "{courses}"},
                {"icon": "⏱", "label": "ساعت آموزش", "value": "{hours}"},
                {"icon": "⭐", "label": "رضایت دانشجویان", "value": "{satisfaction}"}
            ]}}]]},
        {"cols": [[{"id": "inst-h3", "type": "courses", "data": {
            "columns": "3", "limit": "6", "sort": "latest",
            "title": "دوره‌های محبوب",
            "subtitle": "محبوب‌ترین دوره‌های آموزشی آکادمی"}}]]}
    ]
}

DEFAULT_SETTINGS = {
    'site_name': 'آکادمی آنلاین',
    'site_desc': 'مرجع آموزش آنلاین فارسی — دوره‌های پروژه‌محور با مدرسان برتر',
    'email': 'info@academy.ir',
    'phone': '021-91001234',
    'address': 'تهران، خیابان ولیعصر',
    'support_hours': 'شنبه تا پنجشنبه — ۹ تا ۲۱',
    'home_design': 'builder',
    'sandbox_mode': '0',
    'sms_provider': '',
    'allow_register': '1',
    'allow_phone_login': '1',
    'maintenance': '0',
    'bnpl_enabled': '1',
    'cashback_percent': '5',
    'certificate_text': 'این گواهینامه به‌پاس تکمیل موفق دوره صادر شده است.',
    'invoice_prefix': 'AC',
}

CATEGORIES = [
    ('برنامه‌نویسی', 'برنامه-نویسی', '💻', '#2563eb'),
    ('وب', 'وب', '🌐', '#059669'),
    ('هوش مصنوعی', 'هوش-مصنوعی', '🤖', '#7c3aed'),
    ('طراحی', 'طراحی', '🎨', '#db2777'),
    ('کسب‌وکار', 'کسب-وکار', '📈', '#ea580c'),
    ('آفیس', 'آفیس', '📊', '#16a34a'),
    ('زبان', 'زبان', '🗣️', '#0ea5e9'),
    ('امنیت', 'امنیت', '🛡️', '#dc2626'),
]


_SESSION_TUNE_SQL = (
    'SET SESSION wait_timeout=600',
    'SET SESSION net_read_timeout=120',
    'SET SESSION net_write_timeout=120',
    'SET SESSION max_statement_time=0',
    'SET SESSION max_execution_time=0',
    'SET SESSION max_allowed_packet=67108864',
)


def _apply_session_tune(dbapi_con):
    """اعمال تنظیمات سشن روی هر اتصال جدید (pool_connect event)
    مهم: SET SESSION فقط همان connection را تنظیم می‌کند؛ با این event همه
    اتصال‌های pool تنظیم می‌شوند — بدون آن، کوئری‌های سنگین (CREATE TABLE)
    روی اتصال‌های دیگر سقف زمان هاست را دارند و kill می‌شوند (خطای 2013).
    dbapi_con: اتصال خام (cursor دارد)
    """
    try:
        cur = dbapi_con.cursor()
        for stmt in _SESSION_TUNE_SQL:
            try:
                cur.execute(stmt)
            except Exception:
                pass
        cur.close()
    except Exception:
        pass


def _fast_engine(db_url, unix_socket=None):
    """engine فوق‌سریع برای نصب — بدون pool (NullPool) و تایم‌اوت کوتاه
    - یک اتصال تازه هر بار (سبک — برای نصب که چند کوئری دارد)
    - pool_connect event: تنظیم سشن (ضد max_statement_time هاست)
    - unix_socket: برای هاست‌هایی که MySQL فقط سوکت محلی دارد
    """
    from sqlalchemy import create_engine, event as _event
    from sqlalchemy.pool import NullPool
    c_args = {'connect_timeout': 5, 'read_timeout': 60, 'write_timeout': 60}
    if unix_socket:
        c_args = {'unix_socket': unix_socket, 'connect_timeout': 5}
    eng = create_engine(
        resolve_url(db_url),
        poolclass=NullPool,
        connect_args=c_args)
    try:
        _event.listen(eng, 'connect', lambda dbapi_con, rec: _apply_session_tune(dbapi_con))
    except Exception:
        pass
    return eng


# سوکت‌های محلی رایج MySQL/MariaDB روی هاست‌های اشتراکی
_LOCAL_SOCKETS = (
    '/var/run/mysqld/mysqld.sock',
    '/run/mysqld/mysqld.sock',
    '/var/lib/mysql/mysql.sock',
    '/tmp/mysql.sock',
    '/tmp/mariadb.sock',
)

# کش بهترین روش اتصال — بین تست و نصب یکسان می‌ماند
_best_conn_cache = {}


def _get_engine(db_url):
    """بهترین اتصال ممکن: اول TCP (سریع)، اگر نشد و host محلی بود → سوکت محلی
    نتیجه در کش ذخیره می‌شود تا تست اتصال و نصب از یک روش استفاده کنند.
    """
    key = db_url
    if key in _best_conn_cache:
        mode = _best_conn_cache[key]
        if isinstance(mode, tuple):
            return _fast_engine(db_url, unix_socket=mode[1])
        return _fast_engine(db_url)
    # تلاش TCP
    try:
        eng = _fast_engine(db_url)
        with eng.connect():
            pass
        _best_conn_cache[key] = 'tcp'
        return eng
    except Exception:
        pass
    # تلاش سوکت محلی (فقط host محلی)
    host = db_url.split('@')[-1].split(':')[0] if '@' in db_url else ''
    if host in ('localhost', '127.0.0.1', ''):
        for sock in _LOCAL_SOCKETS:
            if os.path.exists(sock):
                try:
                    eng = _fast_engine(db_url, unix_socket=sock)
                    with eng.connect():
                        pass
                    _best_conn_cache[key] = ('socket', sock)
                    return eng
                except Exception:
                    continue
    # برگرد به TCP — خطای اصلی در run_install نمایش داده می‌شود
    return _fast_engine(db_url)


def _tune_session(eng):
    """به‌روزرسانی متغیرهای سشن MySQL — مقاوم‌سازی در برابر قطعی
    نکته کلیدی: هاست‌های اشتراکی گاهی سقف زمان اجرای کوئری می‌گذارند
    (max_statement_time در MariaDB / max_execution_time در MySQL) که کوئری‌های
    سنگین مثل CREATE TABLE با ایندکس را می‌کشد → «Lost connection during query».
    اینجا سقف را برای سشن صفر می‌کنیم.
    """
    from models import db as _db
    try:
        with eng.connect() as conn:
            for stmt in (
                'SET SESSION wait_timeout=600',
                'SET SESSION net_read_timeout=120',
                'SET SESSION net_write_timeout=120',
                # سقف زمان اجرای کوئری را بردار (علت رایج 2013 در هاست‌های اشتراکی)
                'SET SESSION max_statement_time=0',
                'SET SESSION max_execution_time=0',
            ):
                try:
                    conn.execute(_db.text(stmt))
                except Exception:
                    pass
            try:
                conn.execute(_db.text('SET SESSION max_allowed_packet=67108864'))
            except Exception:
                pass
    except Exception:
        pass


def check_db_health():
    """سلامت دیتابیس فعلی (از .env یا پیش‌فرض) — خروجی (ok, message)
    برای گارد نصب: اگر مارکر هست ولی جدول‌ها نیستند → not ok → حالت تعمیر
    """
    try:
        from sqlalchemy import create_engine, inspect
        from models import Setting
        url = env_db_url()
        if str(url).startswith('mysql'):
            eng = _get_engine(url)
        else:
            eng = create_engine(resolve_url(url))
        with eng.connect():
            pass
        # جدول‌های اصلی موجودند؟
        names = set(inspect(eng).get_table_names())
        missing = [t for t in ('settings', 'users', 'courses', 'pages') if t not in names]
        eng.dispose()
        if missing:
            return False, 'جدول‌های اصلی ناقص‌اند: ' + ', '.join(missing)
        return True, 'دیتابیس سالم است ✅'
    except Exception as e:
        return False, 'دیتابیس در دسترس نیست: ' + str(e)[:150]


def env_db_url():
    """خواندن تازه DATABASE_URL از .env — برای تعمیر و سلامت
    (مقدار محیطی قبلی را نادیده می‌گیرد چون ممکن است از boot قدیمی مانده باشد)
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(BASE_DIR, '.env'), override=True)
    except Exception:
        pass
    return os.environ.get('DATABASE_URL', '')


def _is_conn_lost(exc):
    """آیا خطا از نوع قطعی اتصال است؟ (2013 / 2006 / server has gone away)"""
    s = str(exc)
    return any(k in s for k in ('2013', '2006', 'Lost connection',
                                'server has gone away', 'closed connection',
                                'Connection refused'))


def _create_tables_resilient(eng, max_tries=4):
    """ساخت جدول‌ها جدول‌به‌جدول با retry جدول‌به‌جدول — ضد قطعی اتصال
    - هر جدول در تلاش خودش؛ اگر یک جدول قطعی خورد فقط همان دوباره تلاش می‌شود
    - بین تلاش‌ها اتصال تازه (dispose) + sleep کوتاه
    """
    from models import db as _db
    db = _db
    from sqlalchemy import inspect as _insp
    import time as _time
    for table in db.metadata.sorted_tables:
        for attempt in range(1, max_tries + 1):
            try:
                if table.name in set(_insp(eng).get_table_names()):
                    break
                table.create(eng, checkfirst=True)
                break
            except Exception as e:
                if not _is_conn_lost(e):
                    raise
                eng.dispose()
                _time.sleep(1.5 * attempt)
                if attempt >= max_tries:
                    # تلاش آخر: اگر جدول با این‌حال ساخته شد (اتصال فقط قطع شده) ادامه بده
                    try:
                        if table.name in set(_insp(eng).get_table_names()):
                            break
                    except Exception:
                        pass
                    raise
    return True


# ════════════════════════════════════════════════════════════
# نصب در پس‌زمینه — ضد «Request Timeout» هاست‌های اشتراکی
# نصب کامل ممکن است >۳۰ ثانیه طول بکشد؛ پراکسی هاست درخواست طولانی را
# قطع می‌کند. پس نصب در یک thread جدا اجرا و پیشرفت آن با /install/status
# (polling هر ۲ ثانیه) خوانده می‌شود — هر درخواست HTTP کوتاه می‌ماند.
# ════════════════════════════════════════════════════════════
import threading as _bg_thr

_install_state = {
    'status': 'idle',      # idle | running | done | error
    'step': 0,             # 0..5
    'steps': 5,
    'msg': '',
    'ok': False,
}
_install_lock = _bg_thr.Lock()

# ── state روی دیسک (چند-worker گونی/Passenger) ──
# بدون این، thread نصب در worker A اجرا می‌شود ولی poll به worker B می‌رود
# و همیشه idle می‌بیند → صفحه برای همیشه «در حال نصب...» می‌ماند.
_INSTALL_STATE_FILE = os.path.join(INSTANCE_DIR, '.install_progress.json')
_INSTALL_STALE_SECONDS = 120  # ۲ دقیقه بدون پیشرفت = thread مرده


def _save_state():
    global _install_state
    _install_state['_updated'] = time.time()
    try:
        os.makedirs(INSTANCE_DIR, exist_ok=True)
        with open(_INSTALL_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_install_state, f, ensure_ascii=False)
    except Exception:
        pass


def _load_state_file():
    try:
        with open(_INSTALL_STATE_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def install_progress():
    """وضعیت فعلی نصب — از فایل (چند-worker) + تشخیص وقفه thread"""
    global _install_state
    fstate = _load_state_file()
    if fstate is not None:
        with _install_lock:
            _install_state.update(fstate)
    st = dict(_install_state)
    st.pop('_updated', None)
    st['stale'] = False
    if st.get('status') == 'running':
        upd = _install_state.get('_updated', 0)
        if time.time() - upd > _INSTALL_STALE_SECONDS:
            st['status'] = 'error'
            st['stale'] = True
            st['msg'] = ('نصب قطع شد (سرور/هاست درخواست پس‌زمینه را متوقف کرد). '
                         'روی «شروع نصب» دوباره بزنید — از همان‌جا ادامه می‌دهد.')
            with _install_lock:
                _install_state['status'] = 'error'
                _install_state['msg'] = st['msg']
            _save_state()
    return st


# لاگین خودکار مدیر بعد از اتمام نصب (یک بار)
_bg_auto_login_done = False
_bg_auto_login_lock = _bg_thr.Lock()


def _bg_logged_in():
    global _bg_auto_login_done
    with _bg_auto_login_lock:
        return _bg_auto_login_done


def _mark_bg_logged_in():
    global _bg_auto_login_done
    with _bg_auto_login_lock:
        _bg_auto_login_done = True


def start_background_install(db_url, admin, site, create_demo_student=False):
    """شروع نصب در پس‌زمینه — بدون مسدود کردن درخواست HTTP
    خروجی: (started, message)
    """
    global _install_state
    # چک running از فایل (چند-worker)
    fstate = _load_state_file()
    if fstate and fstate.get('status') == 'running' and \
            time.time() - fstate.get('_updated', 0) < _INSTALL_STALE_SECONDS:
        return False, 'نصب دیگری در حال اجراست — کمی صبر کنید.'
    with _install_lock:
        _install_state = {
            'status': 'running', 'step': 0, 'steps': 5,
            'msg': 'شروع نصب...', 'ok': False,
        }
    _save_state()

    def _work():
        try:
            def _prog(step, msg):
                with _install_lock:
                    _install_state['step'] = step
                    _install_state['msg'] = msg
                _save_state()   # هر پیشرفت → فایل (پول در worker دیگر هم ببیند)
            ok, msg = run_install(db_url, admin, site, create_demo_student,
                                  progress_cb=_prog)
            with _install_lock:
                _install_state['status'] = 'done' if ok else 'error'
                _install_state['ok'] = ok
                _install_state['msg'] = msg
                if ok:
                    _install_state['step'] = 5
            _save_state()
        except Exception as e:
            with _install_lock:
                _install_state['status'] = 'error'
                _install_state['ok'] = False
                _install_state['msg'] = 'خطای غیرمنتظره: ' + str(e)[:250]
            _save_state()

    _bg_thr.Thread(target=_work, daemon=True).start()
    return True, 'نصب در پس‌زمینه شروع شد'


def run_install(db_url, admin, site, create_demo_student=False, progress_cb=None):
    """
    اجرای کامل نصب — نسخه فوق‌سریع (برای هاست‌های اشتراکی با سقف زمانی):
    - یک اتصال واحد برای کل نصب (بدون pool، بدون reconnect بین مراحل)
    - batch insert (executemany) به‌جای ORM تکی — داده‌ها در چند کوئری
    - FOREIGN_KEY_CHECKS=0 هنگام درج (چند برابر سریع‌تر)
    - جدول‌ها جدول‌به‌جدول با تلاش مجدد
    admin: dict(name, email, password)
    site:  dict(name, desc, phone, email, base_url)
    progress_cb: تابع اختیاری (step, msg)
    خروجی: (ok, message)
    """
    def _prog(step, msg):
        if progress_cb:
            try:
                progress_cb(step, msg)
            except Exception:
                pass
    try:
        from models import db, User, Setting, Category, Course, Section, Lesson, Coupon
        from models import Page
        from sqlalchemy import insert as _ins, select as _sel
        import time as _t

        # ── ۰) چک پیش‌نیاز MySQL ──
        is_mysql = str(db_url).startswith('mysql')
        if is_mysql:
            try:
                import pymysql  # noqa: F401
            except ImportError:
                return False, ('ماژول PyMySQL نصب نیست! در ترمینال هاست اجرا کنید: '
                               './venv/bin/pip install PyMySQL  (یا: pip install -r requirements.txt)')
            ensure_mysql_db(db_url)

        # ── ۱) اتصال سریع (TCP یا سوکت محلی) + ساخت جدول‌ها ──
        t0 = _t.time()
        if is_mysql:
            eng = _get_engine(db_url)
            _create_tables_resilient(eng)
        else:
            from sqlalchemy import create_engine
            eng = create_engine(resolve_url(db_url))
            db.metadata.create_all(eng)
        _prog(1, f'جدول‌ها ساخته شدند ({_t.time()-t0:.1f}ث)')

        # ── ۲) کپی فوق‌سریع داده‌ها — یک اتصال + batch + FK off ──
        t1 = _t.time()
        settings = dict(DEFAULT_SETTINGS)
        for k, v in (('site_name', site.get('name')), ('site_desc', site.get('desc')),
                     ('phone', site.get('phone')), ('email', site.get('email')),
                     ('base_url', (site.get('base_url') or '').strip())):
            if v:
                settings[k] = v
        settings['installed_at'] = datetime.now(UTC).isoformat()

        with eng.begin() as conn:
            try:
                conn.execute(db.text('SET FOREIGN_KEY_CHECKS=0'))
            except Exception:
                pass

            # تنظیمات — batch
            existing = {r[0] for r in conn.execute(_sel(Setting.key))}
            rows = [{'key': k, 'value': v} for k, v in settings.items() if k not in existing]
            if rows:
                conn.execute(_ins(Setting), rows)

            # دسته‌بندی‌ها — batch
            existing = {r[0] for r in conn.execute(_sel(Category.slug))}
            rows = [{'name': n, 'slug': sl, 'icon': ic, 'color': co, 'sort': 0}
                    for n, sl, ic, co in CATEGORIES if sl not in existing]
            if rows:
                conn.execute(_ins(Category), rows)

            # کاربران (مدیر + دمو)
            existing = {r[0] for r in conn.execute(_sel(User.email))}
            if admin['email'].lower() not in existing:
                u = User(name=admin['name'], email=admin['email'].lower(),
                         role='super_admin', is_active=True)
                u.set_password(admin['password'])
                conn.execute(_ins(User).values(
                    name=u.name, email=u.email, role='super_admin',
                    is_active=True, password_hash=u.password_hash))
            if create_demo_student and 'demo@academy.ir' not in existing:
                u = User(name='دانشجوی نمونه', email='demo@academy.ir',
                         phone='09120000001', role='student', is_active=True)
                u.set_password('demo123')
                conn.execute(_ins(User).values(
                    name=u.name, email=u.email, phone=u.phone, role='student',
                    is_active=True, password_hash=u.password_hash))

            # صفحه اصلی
            if not conn.execute(_sel(Page.id).where(
                    Page.slug == 'home', Page.ptype == 'page')).first():
                conn.execute(_ins(Page).values(
                    title='خانه', slug='home', ptype='page',
                    content=json.dumps(HOME_PAGE_JSON, ensure_ascii=False),
                    is_published=True))

            # دوره نمونه + سکشن‌ها + درس‌ها (batch)
            if not conn.execute(_sel(Course.id).where(
                    Course.slug == 'course-intro')).first():
                cat_id = conn.execute(_sel(Category.id).where(
                    Category.slug == 'برنامه-نویسی')).scalar()
                t_id = conn.execute(_sel(User.id).where(
                    User.role == 'super_admin').limit(1)).scalar()
                res = conn.execute(_ins(Course).values(
                    title='آشنایی با پلتفرم آموزشی آکادمی',
                    slug='course-intro',
                    subtitle='یک دوره رایگان برای آشنایی با امکانات پلتفرم',
                    description='این دوره نمونه به‌صورت خودکار هنگام نصب ساخته شده است. '
                                'می‌توانید آن را از پنل مدیریت ویرایش یا حذف کنید.',
                    image='cover-python.webp', category_id=cat_id,
                    teacher_id=t_id, price=0, discount_price=0, level='مقدماتی',
                    language='fa', status='published', featured=True,
                    what_you_learn='آشنایی با پلتفرم\nنحوه یادگیری\nدریافت گواهی',
                    requirements='هیچ پیش‌نیازی لازم نیست', duration_hours=1,
                    tags='رایگان,آشنایی,مقدماتی', views=0))
                course_id = res.lastrowid
                r1 = conn.execute(_ins(Section).values(
                    course_id=course_id, title='شروع کار', sort=1))
                r2 = conn.execute(_ins(Section).values(
                    course_id=course_id, title='امکانات پیشرفته', sort=2))
                conn.execute(_ins(Lesson), [
                    {'section_id': r1.lastrowid, 'title': 'خوش آمدید', 'video_type': 'none',
                     'content': 'به آکادمی خوش آمدید! این جلسه شما را با پلتفرم آشنا می‌کند.',
                     'sort': 1, 'is_free': True, 'duration': '00:03:00'},
                    {'section_id': r1.lastrowid, 'title': 'چگونه یاد بگیریم؟', 'video_type': 'none',
                     'content': 'با برنامه مطالعاتی شخصی و پیگیری پیشرفت، مسیر یادگیری خود را مدیریت کنید.',
                     'sort': 2, 'is_free': True, 'duration': '00:04:00'},
                    {'section_id': r2.lastrowid, 'title': 'گواهینامه پایان دوره', 'video_type': 'none',
                     'content': 'پس از تکمیل همه جلسات، گواهینامه معتبر با کد رهگیری دریافت می‌کنید.',
                     'sort': 1, 'is_free': True, 'duration': '00:03:00'},
                ])

            # کوپن
            if not conn.execute(_sel(Coupon.id).where(
                    Coupon.code == 'WELCOME20')).first():
                conn.execute(_ins(Coupon).values(
                    code='WELCOME20', type='percent', value=20,
                    min_amount=0, max_uses=0, used_count=0, is_active=True))

            try:
                conn.execute(db.text('SET FOREIGN_KEY_CHECKS=1'))
            except Exception:
                pass
        _prog(3, f'داده‌ها کپی شدند ({_t.time()-t1:.1f}ث)')

        eng.dispose()

        # ── ۳) سوئیچ اپ به دیتابیس جدید (بدون ری‌استارت) — ضد-خطا ──
        try:
            from flask import current_app
            app = current_app._get_current_object()
            app.config['SQLALCHEMY_DATABASE_URI'] = resolve_url(db_url)
            try:
                from sqlalchemy import create_engine as _ce
                _opts = dict(app.config.get('SQLALCHEMY_ENGINE_OPTIONS') or {})
                _opts.setdefault('pool_pre_ping', True)
                if str(db_url).startswith('mysql'):
                    _opts.setdefault('pool_recycle', 280)
                _engines = db._app_engines.get(app)
                if _engines:
                    for _e in _engines.values():
                        _e.dispose()
                    _engines.clear()
                    _engines[None] = _ce(resolve_url(db_url), **_opts)
            except Exception:
                pass
        except Exception:
            pass

        # ── ۴) نوشتن .env + علامت نصب ──
        secret_key = secrets.token_hex(32)
        write_env_file(db_url, secret_key)
        mark_installed({
            'db': 'mysql' if db_url.startswith('mysql') else 'sqlite',
            'admin': admin['email'].lower(),
            'site': site.get('name') or 'آکادمی آنلاین',
        })
        _prog(5, 'ذخیره تنظیمات و .env')
        return True, f'نصب با موفقیت کامل شد ✅ (در {_t.time()-t0:.1f} ثانیه)'
    except Exception as e:
        msg = str(e)[:400]
        msg = msg.split('(Background on this error')[0].strip()
        import re as _re
        m = _re.search(r'\(\d+, "([^"]+)"\)', msg)
        if m:
            msg = m.group(1)
        if _is_conn_lost(e):
            # جدول‌هایی که ساخته شده‌اند می‌مانند — اجرای دوباره از همان‌جا ادامه می‌دهد
            return False, ('خطا در نصب: هاست هنگام ساخت داده‌ها اتصال MySQL را قطع کرد (کد 2013). '
                           'محدودیت پکت (max_allowed_packet) معمولاً علت نیست — '
                           'بیشتر هاست‌ها سقف زمان اجرای کوئری دارند. '
                           'راه‌حل‌ها: ۱) همین‌جا روی «شروع نصب» دوباره بزنید — جدول‌های ساخته‌شده '
                           'می‌مانند و از همان‌جا ادامه می‌دهد. ۲) اگر دوباره قطع شد، در گام اول '
                           '«SQLite» را انتخاب کنید (ساده‌ترین و مطمئن‌ترین روی هر هاست). '
                           '۳) یا از پشتیبانی هاست بخواهید max_statement_time را روی 0 بگذارد. '
                           'جزئیات: ' + msg[-120:])
        return False, 'خطا در نصب: ' + msg[-300:]
