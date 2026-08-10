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
    m = re.search(r'(?:youtube\.com/(?:watch\?v=|embed/|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})', url or '')
    return m.group(1) if m else None


def vimeo_id(url):
    m = re.search(r'vimeo\.com/(?:video/)?(\d+)', url or '')
    return m.group(1) if m else None


def aparat_hash(url):
    m = re.search(r'aparat\.com/v/([A-Za-z0-9_-]+)', url or '')
    return m.group(1) if m else None


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

ALLOWED_IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.avif'}
ALLOWED_FILE_EXT = ALLOWED_IMAGE_EXT | {'.pdf', '.doc', '.docx', '.zip', '.rar',
                                        '.txt', '.csv', '.xlsx', '.pptx', '.mp4', '.mp3'}

def safe_filename(filename, allowed_ext=None):
    """نام امن + پسوند مجاز؛ در غیر این صورت None"""
    if not filename:
        return None
    ext = os.path.splitext(filename)[1].lower()
    allowed = allowed_ext or ALLOWED_FILE_EXT
    if ext not in allowed:
        return None
    # فقط نام پایه (بدون مسیر) و حذف کاراکترهای خطرناک
    base = os.path.basename(filename)
    base = ''.join(c for c in base if c.isalnum() or c in '._-') or 'file'
    return base


def log_exc(context=''):
    """ثبت خطای بلعیده‌شده (جایگزین except: pass) — برای دیباگ واقعی"""
    import logging, sys
    exc = sys.exc_info()[1]
    logging.getLogger('academy').warning(
        'swallowed error [%s]: %s: %s',
        context, type(exc).__name__ if exc else '?', exc or '')


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
