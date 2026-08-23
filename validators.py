# -*- coding: utf-8 -*-
"""اعتبارسنجی کد ملی، شماره تماس و ابزارهای لینک ویدیو"""
import re
import random

PHONE_RE = re.compile(r'^09\d{9}$')
NC_RE = re.compile(r'^\d{10}$')


def is_valid_phone(p):
    """شماره موبایل ایرانی: 09xxxxxxxxx"""
    return bool(PHONE_RE.fullmatch(str(p or '').strip()))


def is_valid_national_code(code):
    """اعتبارسنجی الگوریتمی کد ملی ۱۰ رقمی ایرانی"""
    code = str(code or '').strip()
    if not NC_RE.fullmatch(code):
        return False
    if len(set(code)) == 1:
        return False
    check = int(code[9])
    s = sum(int(code[i]) * (10 - i) for i in range(9))
    r = s % 11
    return (r < 2 and check == r) or (r >= 2 and check == 11 - r)


def gen_national_code():
    """تولید کد ملی معتبر (برای داده‌های دمو)"""
    for _ in range(1000):
        d = [random.randint(0, 9) for _ in range(9)]
        d[0] = random.randint(1, 9)
        if len(set(d)) == 1:
            continue
        s = sum(d[i] * (10 - i) for i in range(9))
        r = s % 11
        c = r if r < 2 else 11 - r
        return ''.join(map(str, d)) + str(c)
    return '0000000000'


def mask_nc(code):
    """نمایش کد ملی ماسک‌شده: 045***8904"""
    code = str(code or '').strip()
    if len(code) == 10:
        return code[:3] + '***' + code[-4:]
    return '—'


def youtube_id(url):
    m = re.search(
        r'(?:youtube(?:-nocookie)?\.com/(?:watch\?v=|embed/|shorts/|live/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})',
        url or '')
    if m:
        return m.group(1)
    m = re.search(r'[?&]v=([A-Za-z0-9_-]{11})', url or '')
    return m.group(1) if m else None


def vimeo_id(url):
    m = re.search(r'(?:player\.)?vimeo\.com/(?:video/)?(\d+)', url or '')
    return m.group(1) if m else None


def aparat_hash(url):
    m = re.search(
        r'aparat\.com/(?:video/video/embed/videohash/|v/|video/)([A-Za-z0-9_-]+)',
        url or '')
    return m.group(1) if m else None


def detect_video(url):
    """تشخیص نوع پخش از URL — یوتیوب / آپارات / مستقیم."""
    url = (url or '').strip()
    yt = youtube_id(url)
    if yt:
        return 'youtube', yt
    ap = aparat_hash(url)
    if ap:
        return 'aparat', ap
    vm = vimeo_id(url)
    if vm:
        return 'vimeo', vm
    if url:
        return 'direct', url
    return 'none', ''


def safe_int(value, default=0, min_value=None, max_value=None):
    """تبدیل عدد فرم/JSON بدون ValueError و با محدوده اختیاری."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError, OverflowError):
        number = int(default)
    if min_value is not None:
        number = max(int(min_value), number)
    if max_value is not None:
        number = min(int(max_value), number)
    return number


def human_size(n):
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return '—'
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024:
            return f'{int(n)} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'

# -*- coding: utf-8 -*-

import os

# توجه امنیتی: «.svg» عمداً از مجموعهٔ پیش‌فرض حذف شده — فایل SVG می‌تواند
# جاوااسکریپت داخلش داشته باشد (<script>) و وقتی مستقیم در مرورگر باز شود
# اجرا می‌شود (XSS ذخیره‌شده). دقیقاً همین حفره باعث می‌شود گوگل سیف‌براوزینگ
# / فایرفاکس دامنه را «فریب بازدیدکننده برای دانلود نرم‌افزار» علامت بزند،
# چون هرکسی که فقط عضو سایت شده (نه لزوماً ادمین) می‌تواند چنین فایلی را
# در دامنهٔ خودمان میزبانی و به‌عنوان لینک فیشینگ/مخرب پخش کند.
# SVG فقط برای مسیرهای کاملاً ادمین (لوگو، آپلود صفحه‌ساز) با
# ALLOWED_IMAGE_EXT_TRUSTED مجاز است، نه برای آپلودهای کاربر عادی/دانشجو.
ALLOWED_IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif'}
ALLOWED_IMAGE_EXT_TRUSTED = ALLOWED_IMAGE_EXT | {'.svg'}
ALLOWED_FILE_EXT = ALLOWED_IMAGE_EXT | {'.pdf', '.doc', '.docx', '.zip', '.rar',
                                        '.txt', '.csv', '.xlsx', '.pptx', '.mp4', '.mp3'}
# کتابخانه رسانه (فایل‌هایی که مستقیماً زیر دامنه عمومی سرو می‌شوند):
# فقط تصویر/ویدیو/صوت + pdf. هیچ zip/سند اجرایی/svg — چون لینک آن‌ها قابل
# پخش عمومی است و میزبانی محتوای اجرایی زیر دامنه، سیگنال «سایت خطرناک» است.
ALLOWED_MEDIA_EXT = ALLOWED_IMAGE_EXT | {'.mp4', '.webm', '.mov', '.mp3', '.wav',
                                         '.ogg', '.pdf'}

def safe_filename(filename, allowed_ext=None):
    """نام امن + پسوند مجاز؛ در غیر این صورت None"""
    if not filename or '\x00' in filename:
        return None
    filename = os.path.basename(filename.replace('\\', '/'))
    ext = os.path.splitext(filename)[1].lower()
    allowed = allowed_ext or ALLOWED_FILE_EXT
    if ext not in allowed:
        return None
    base = ''.join(c for c in filename if c.isalnum() or c in '._-') or 'file'
    while '..' in base:
        base = base.replace('..', '.')
    # پسوند دوگانه (shell.php.jpg / x.html.png) — پسوند میانی هم نباید اجرایی باشد
    _parts = base.lower().split('.')
    _dangerous = {'php', 'php3', 'php4', 'php5', 'php7', 'phtml', 'phar', 'cgi',
                  'pl', 'py', 'rb', 'sh', 'bash', 'exe', 'bat', 'cmd', 'com',
                  'scr', 'msi', 'dll', 'jar', 'apk', 'js', 'mjs', 'html', 'htm',
                  'xhtml', 'shtml', 'asp', 'aspx', 'jsp', 'htaccess'}
    if any(p in _dangerous for p in _parts[:-1]):
        return None
    return base


# ── امضاهای محتوای اجرایی که نباید داخل فایل «تصویر» باشند ──
_EXEC_MARKERS = (b'<script', b'javascript:', b'<iframe', b'<embed', b'<object',
                 b'onload=', b'onerror=', b'onclick=', b'<!entity', b'<?php',
                 b'<handler', b'<set ', b'<animate')


def file_content_is_safe(stream, ext):
    """آیا محتوای فایل آپلودشده با پسوندش می‌خواند و کد اجرایی ندارد؟

    چک کردن فقط پسوند کافی نیست: یک فایل با نام `logo.svg` (یا حتی `x.png`)
    می‌تواند حاوی `<script>` باشد و وقتی مرورگر بازش می‌کند، کد زیر دامنهٔ ما
    اجرا می‌شود — یعنی XSS ذخیره‌شده و صفحهٔ فیشینگ روی دامنهٔ خودمان.
    این همان الگویی است که Google Safe Browsing کل دامنه را برایش با پیام
    «Dangerous site» مسدود می‌کند.

    ورودی: شیء فایل (werkzeug FileStorage.stream یا هر stream قابل seek)
    خروجی: True اگر امن باشد.
    """
    ext = (ext or '').lower()
    try:
        pos = stream.tell()
    except Exception:
        pos = None
    try:
        head = stream.read(8192) or b''
    except Exception:
        return False
    finally:
        try:
            stream.seek(pos if pos is not None else 0)
        except Exception:
            pass
    if isinstance(head, str):
        head = head.encode('utf-8', 'ignore')
    low = head.lower()
    if ext in ('.svg', '.svgz'):
        # SVG یک سند XML است — هیچ تگ اجرایی نباید داشته باشد
        return not any(m in low for m in _EXEC_MARKERS)
    if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif'):
        # تصویر باینری واقعی: نباید با متن/HTML شروع شود و نباید تگ اسکریپت داشته باشد
        if low.lstrip()[:1] == b'<':
            return False
        return not any(m in low for m in (b'<script', b'<?php', b'<iframe'))
    return True


def request_context():
    """زمینهٔ درخواست جاری برای لاگ — شناسهٔ درخواست، کاربر، مسیر و IP.

    چرا لازم است (نظارت‌پذیری سطح تجاری):
        بدون این اطلاعات، یک خطای ثبت‌شده در لاگ عملاً بی‌فایده است: معلوم
        نیست کدام کاربر، از کدام IP و روی کدام مسیر آن را ایجاد کرده. وقتی
        مشتری تماس می‌گیرد و می‌گوید «صفحه خطا داد»، تیم پشتیبانی باید
        بتواند با یک شناسه دقیقاً همان درخواست را پیدا کند.

    ⚠️ نکتهٔ امنیتی (Zero-Trust):
        عمداً هیچ دادهٔ حساسی ثبت نمی‌شود — نه توکن نشست، نه رمز عبور، نه
        کد ملی. فقط شناسهٔ عددی کاربر ثبت می‌شود، نه ایمیل یا شماره تماس،
        تا فایل لاگ خودش به یک منبع نشت اطلاعات شخصی تبدیل نشود.

    خروجی: رشتهٔ کوتاه و قابل جستجو، یا رشتهٔ خالی در صورت نبودِ کانتکست
    (مثلاً هنگام اجرای اسکریپت‌های CLI یا کارهای پس‌زمینه).
    """
    try:
        from flask import g, has_request_context, request
    except Exception:          # pragma: no cover - فقط اگر Flask نصب نباشد
        return ''
    if not has_request_context():
        return ''
    parts = []
    try:
        rid = getattr(g, 'request_id', None)
        if rid:
            parts.append('rid={}'.format(rid))
        user = getattr(g, 'user', None)
        # فقط شناسهٔ عددی — نه ایمیل/تلفن (جلوگیری از نشت PII در لاگ)
        parts.append('uid={}'.format(getattr(user, 'id', None) or '-'))
        parts.append('{} {}'.format(request.method, request.path[:120]))
        # اولین مقدار X-Forwarded-For پشت پراکسی، وگرنه remote_addr
        client_ip = (request.headers.get('X-Forwarded-For', '')
                     .split(',')[0].strip() or request.remote_addr or '-')
        parts.append('ip={}'.format(client_ip[:45]))
    except Exception:
        # ساخت زمینهٔ لاگ هرگز نباید خودش باعث خطا شود.
        return ' '.join(parts)
    return ' '.join(parts)


def log_exc(context='', level='warning'):
    """ثبت خطای مهارشده (جایگزین ``except: pass``) همراه با زمینهٔ کامل.

    این تابع در بیش از ۹۰ نقطهٔ پروژه صدا زده می‌شود، بنابراین امضای آن
    عمداً سازگار با گذشته نگه داشته شده: ``log_exc('ماژول')`` دقیقاً مثل
    قبل کار می‌کند و به‌صورت خودکار زمینهٔ درخواست را هم اضافه می‌کند.

    پارامترها:
        context: نام ماژول/عملیات برای ردیابی (مثلاً 'shop.mark_paid').
        level:   'warning' (پیش‌فرض) یا 'error' برای خطاهای جدی‌تر که باید
                 در سامانهٔ هشدار دیده شوند.

    چرا traceback فقط در سطح debug ثبت می‌شود:
        ثبت کامل traceback برای هر خطای مهارشده، فایل لاگ را در ترافیک بالا
        پر می‌کند. متن کامل با ``LOG_LEVEL=DEBUG`` در دسترس است، اما در حالت
        عادی فقط یک خط فشرده و قابل جستجو ثبت می‌شود.
    """
    import logging
    import sys

    exc = sys.exc_info()[1]
    logger = logging.getLogger('academy')
    ctx = request_context()
    log_fn = logger.error if str(level).lower() == 'error' else logger.warning
    log_fn('swallowed error [%s]%s: %s: %s',
           context,
           ' ({})'.format(ctx) if ctx else '',
           type(exc).__name__ if exc else '?',
           exc or '')
    # traceback کامل فقط وقتی سطح لاگ DEBUG باشد (جلوگیری از پرشدن لاگ)
    if exc is not None and logger.isEnabledFor(logging.DEBUG):
        logger.debug('traceback [%s]', context, exc_info=True)


def birth_from_national_code(nc):
    """استخراج تاریخ تولد شمسی از کد ملی (۳ رقم اول = سال، ۲ رقم = ماه، ۲ رقم = روز)
    خروجی: (سال_شمسی, ماه, روز) یا None"""
    nc = str(nc or '').strip()
    if len(nc) != 10 or not nc.isdigit():
        return None
    try:
        y3 = int(nc[0:3])
        month = int(nc[3:5])
        day = int(nc[5:7])
    except Exception:
        return None
    if not (1 <= month <= 12) or not (1 <= day <= 31):
        return None
    if y3 <= 9:
        year = 1300 + y3
    elif y3 <= 99:
        year = 1300 + y3
    elif y3 <= 199:
        year = 1400 + (y3 - 100)
    else:
        year = 1500 + (y3 - 200)
    return (year, month, day)


def birth_jalali_str(nc):
    """تاریخ تولد شمسی متنی از کد ملی — '۱۵ مرداد ۱۳۸۰' یا None"""
    b = birth_from_national_code(nc)
    if not b:
        return None
    from jdates import MONTHS, fa
    try:
        return fa(f'{b[2]} {MONTHS[b[1] - 1]} {b[0]}')
    except Exception:
        return None


# ================================================================
# محدودیت طول ورودی‌ها — ضد DoS و پر شدن دیتابیس
# ================================================================
MAX_LEN = {
    'name': 120, 'email': 160, 'phone': 20, 'subject': 200, 'message': 5000,
    'comment': 2000, 'question': 1000, 'bio': 2000, 'goal': 300, 'text': 10000,
    'title': 200, 'body': 10000, 'url': 500, 'code': 64, 'default': 2000,
}


def clamp_field(value, kind='default'):
    """برش مقدار به حداکثر طول مجاز — همیشه رشته برمی‌گرداند"""
    v = str(value or '').strip()
    return v[:MAX_LEN.get(kind, MAX_LEN['default'])]


def is_short(value, kind='default', min_len=1):
    """آیا مقدار کوتاه‌تر از حداقل است؟"""
    return len(str(value or '').strip()) < min_len


def http_request(method, url, **kwargs):
    """درخواست HTTP خارجی با timeout اجباری — جلوگیری از hang بی‌نهایت"""
    import requests as _req
    kwargs.setdefault('timeout', (5, 15))  # اتصال ۵ ثانیه، پاسخ ۱۵ ثانیه
    return _req.request(method, url, **kwargs)


def safe_next(url, default=None):
    """اعتبارسنجی پارامتر `next` — فقط مسیر نسبی داخلی.

    Open Redirect یعنی لینکی مثل `https://دامنه-ما/auth/login?next=https://evil`
    که کاربر به آن اعتماد می‌کند ولی سر از سایت مهاجم درمی‌آورد. این دقیقاً
    الگوی «Social Engineering» است که Google Safe Browsing دامنهٔ *ما* را
    (نه مهاجم را) برایش «Dangerous site» علامت می‌زند.
    """
    if not url:
        return default
    url = str(url).strip()
    if any(c in url for c in ('\n', '\r', '\x00', '\t')):
        return default
    # // و /\ هر دو پروتکل-نسبی هستند و به دامنهٔ بیرونی می‌روند
    if not url.startswith('/') or url.startswith('//') or url[:2] == '/\\':
        return default
    return url[:500]


def safe_referrer(default=None):
    """برگرداندن referrer فقط در صورت هم-منشاء بودن (جلوگیری از Open Redirect).

    `request.referrer` قابل‌کنترل توسط کلاینت است؛ ریدایرکت مستقیم به آن می‌تواند
    کاربر را به یک دامنهٔ بیرونی (فیشینگ) بفرستد. این تابع فقط آدرس‌های داخلی
    (هم‌منشاء) را برمی‌گرداند و در غیر این صورت `default` را برمی‌گرداند.
    """
    from flask import request
    ref = (request.referrer or '').strip()
    host = (request.host_url or '').rstrip('/')
    if host and ref.startswith(host + '/'):
        # جلوگیری از نویسه‌های خطرناک در URL
        if any(c in ref for c in ('\n', '\r', '\x00')):
            return default
        return ref
    return default


# ================================================================
# ضد تزریق فرمول در CSV/Excel (CSV/Formula Injection — OWASP)
# ================================================================
_CSV_RISKY_RE = re.compile(r'^[=+\-@\t\r]')


def csv_cell(value):
    """ایمن‌سازی یک سلول CSV در برابر تزریق فرمول.

    دادهٔ کاربر (نام، ایمیل، پاسخ فرم و...) که مستقیماً در خروجی اکسل نوشته
    می‌شود، اگر با ``=`` ، ``+`` ، ``-`` ، ``@`` ، tab یا CR شروع شود، توسط
    اکسل/شیتز به‌عنوان فرمول/فرمان اجرا می‌شود (CSV Injection). این تابع با
    پیشوند ``'`` آن را به متن خنثی تبدیل می‌کند.
    """
    if value is None:
        return ''
    s = str(value)
    if _CSV_RISKY_RE.match(s):
        return "'" + s
    return s
