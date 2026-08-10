# -*- coding: utf-8 -*-
"""ماژول مستقل تاریخ شمسی — g2j / j2g / jdate / jdatetime / jtime / jdate_num / jalali_to_gregorian
جدا از app.py تا هیچ circular import رخ ندهد"""
from datetime import datetime as _dt, date as _date

FA_DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
          'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']


def fa(value):
    """تبدیل عدد/متن به ارقام فارسی — None/خالی → رشته خالی (ضد نمایش 'None')"""
    if value is None or value == '':
        return ''
    return str(value).translate(FA_DIGITS)


def g2j(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def j2g(jy, jm, jd):
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += 186 + ((jm - 7) * 30)
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    if gy % 4 == 0 and (gy % 100 != 0 or gy % 400 == 0):
        g_d_m = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    else:
        g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gm = 0
    for i in range(12):
        if gd <= g_d_m[i + 1]:
            gm = i + 1
            break
    gd -= g_d_m[gm - 1]
    return gy, gm, gd


def _to_dt(dt):
    """تبدیل هر نوع ورودی (datetime/date/str/timestamp) به datetime"""
    if dt is None:
        return None
    if isinstance(dt, _dt):
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    if isinstance(dt, _date):
        return _dt(dt.year, dt.month, dt.day)
    if isinstance(dt, (int, float)):
        try:
            return _dt.fromtimestamp(dt)
        except Exception:
            return None
    if isinstance(dt, str):
        s = dt.strip()
        for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y/%m/%d %H:%M', '%Y/%m/%d'):
            try:
                return _dt.strptime(s[:26], fmt)
            except Exception:
                continue
    return None


def jdate(dt):
    dt = _to_dt(dt)
    if dt is None:
        return '—'
    jy, jm, jd = g2j(dt.year, dt.month, dt.day)
    return fa(f'{jd} {MONTHS[jm - 1]} {jy}')


def jdatetime(dt):
    dt = _to_dt(dt)
    if dt is None:
        return '—'
    return jdate(dt) + ' - ' + fa(f'{dt.hour:02d}:{dt.minute:02d}')


def jdate_num(dt):
    """تاریخ شمسی عددی: ۱۴۰۵/۰۵/۱۵"""
    dt = _to_dt(dt)
    if dt is None:
        return '—'
    jy, jm, jd = g2j(dt.year, dt.month, dt.day)
    return fa(f'{jy}/{jm:02d}/{jd:02d}')


def jtime(dt):
    """فقط ساعت شمسی: ۱۰:۳۰"""
    dt = _to_dt(dt)
    if dt is None:
        return '—'
    return fa(f'{dt.hour:02d}:{dt.minute:02d}')


def jalali_to_gregorian(s):
    """ورودی: '1405/05/25' یا '1405-05-25' → خروجی: 'YYYY-MM-DD' یا None"""
    s = (s or '').strip().replace('-', '/')
    import re as _re
    m = _re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})$', s)
    if not m:
        return None
    jy, jm, jd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= jm <= 12 and 1 <= jd <= 31):
        return None
    gy, gm, gd = j2g(jy, jm, jd)
    return f'{gy:04d}-{gm:02d}-{gd:02d}'


def fa_num(value):
    return str(value).translate(FA_DIGITS)


def money(value):
    try:
        v = int(value or 0)
    except (TypeError, ValueError):
        v = 0
    return fa(f'{v:,}') + ' تومان'


def slugify(text):
    import re as _re
    text = str(text or '').strip().replace(' ', '-')
    return _re.sub(r'[^\w\u0600-\u06FF\-]', '', text)
