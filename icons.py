# -*- coding: utf-8 -*-
"""سیستم آیکون — Tabler Icons (MIT)
- فایل‌های SVG در static/icons/ (390 آیکون)
- استفاده در قالب‌ها:  {{ icon('heart', 20, 'text-danger') }}
- نام‌ها را می‌توانید در /admin/icons ببینید و کپی کنید
"""
import os
import re

from markupsafe import Markup

_ICONS = {}
_ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'icons')


def _load_icons():
    """بارگذاری یک‌باره همه آیکون‌ها در حافظه"""
    for f in sorted(os.listdir(_ICON_DIR)):
        if f.endswith('.svg'):
            try:
                with open(os.path.join(_ICON_DIR, f), encoding='utf-8') as fh:
                    _ICONS[f[:-4]] = fh.read()
            except Exception:
                pass


def icon(name, size=20, cls='', title=''):
    """رندر آیکون SVG inline — همرنگ متن (currentColor)
    size:  ابعاد پیکسل | cls: کلاس‌های CSS | title: tooltip
    """
    svg = _ICONS.get(name, _ICONS.get('circle-check', ''))
    if not svg:
        return Markup('')
    # حذف ابعاد، کلاس‌ها و ویژگی‌های تکراری
    svg = re.sub(r'\s+(width|height)="[^"]*"', '', svg)
    svg = re.sub(r'\s+class="[^"]*"', '', svg)
    svg = re.sub(r'\s+(role|aria-label|aria-hidden)="[^"]*"', '', svg)
    # تزریق ابعاد و کلاس و ویژگی‌های دسترس‌پذیری به تگ <svg> (مستقل از فاصله‌ها و شکست خط)
    attrs = f' width="{size}" height="{size}"'
    if cls:
        attrs += f' class="{cls}"'
    if title:
        attrs += f' role="img" aria-label="{title}"'
    else:
        attrs += ' aria-hidden="true"'
    svg = re.sub(r'<svg\b', f'<svg{attrs}', svg, count=1)
    return Markup(svg)


def icon_names():
    """لیست نام آیکون‌ها برای مرورگر آیکون"""
    return sorted(_ICONS.keys())


_load_icons()


def init_icons(app):
    app.jinja_env.globals['icon'] = icon
    app.jinja_env.globals['icon_names'] = icon_names
    app.jinja_env.globals['social_icon'] = social_icon
    app.jinja_env.globals['bank_icon'] = bank_icon
    app.jinja_env.globals['bank_names'] = bank_names
    app.jinja_env.globals['messenger_names'] = messenger_names
    app.jinja_env.globals['IR_MESSENGERS'] = IR_MESSENGERS
    app.jinja_env.globals['IR_BANKS'] = IR_BANKS


# ═══════════════════════════════════════════════════════════════════════════
# آیکون‌های ایرانی — پیام‌رسان‌ها و بانک‌ها / درگاه‌های پرداخت
# ═══════════════════════════════════════════════════════════════════════════
_SOCIAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'static', 'img', 'social')
_BANK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'static', 'img', 'banks')

# پیام‌رسان‌های ایرانی + جهانی — نام، رنگ، الگوی لینک پروفایل
IR_MESSENGERS = {
    'eitaa':    dict(fa='ایتا',    color='#28a745', url='https://eitaa.com/{}'),
    'bale':     dict(fa='بله',     color='#1e9e6a', url='https://ble.ir/{}'),
    'rubika':   dict(fa='روبیکا',  color='#2563eb', url='https://rubika.ir/{}'),
    'soroush':  dict(fa='سروش',    color='#7c3aed', url='https://splus.ir/{}'),
    'shad':     dict(fa='شاد',     color='#e11d48', url='https://shad.ir/{}'),
    'telegram': dict(fa='تلگرام',  color='#229ed9', url='https://t.me/{}'),
    'whatsapp': dict(fa='واتساپ',  color='#25d366', url='https://wa.me/{}'),
    'instagram': dict(fa='اینستاگرام', color='#dc2743', url='https://instagram.com/{}'),
    'aparat':   dict(fa='آپارات',  color='#ed145b', url='https://aparat.com/{}'),
}

# بانک‌ها و درگاه‌های پرداخت ایرانی
IR_BANKS = {
    'mellat': 'بانک ملت', 'melli': 'بانک ملی ایران', 'saderat': 'بانک صادرات',
    'saman': 'بانک سامان', 'parsian': 'بانک پارسیان', 'pasargad': 'بانک پاسارگاد',
    'sepah': 'بانک سپه', 'tejarat': 'بانک تجارت', 'refah': 'بانک رفاه کارگران',
    'keshavarzi': 'بانک کشاورزی', 'maskan': 'بانک مسکن', 'ayandeh': 'بانک آینده',
    'shahr': 'بانک شهر', 'eghtesad': 'بانک اقتصاد نوین', 'day': 'بانک دی',
    'sina': 'بانک سینا', 'postbank': 'پست بانک', 'blubank': 'بلو بانک',
    'zarinpal': 'زرین‌پال', 'idpay': 'آیدی‌پی', 'zibal': 'زیبال', 'sadad': 'سداد',
    'behpardakht': 'به‌پرداخت ملت', 'snapppay': 'اسنپ‌پی', 'digipay': 'دیجی‌پی',
    'shaparak': 'شاپرک',
}


def social_icon(name, size=24, cls=''):
    """آیکون پیام‌رسان به‌صورت تگ <img> (فایل SVG رنگی در static/img/social)."""
    path = os.path.join(_SOCIAL_DIR, '{}.svg'.format(name))
    if not os.path.exists(path):
        return Markup('')
    meta = IR_MESSENGERS.get(name, {})
    label = meta.get('fa', name)
    return Markup(
        '<img src="/static/img/social/{n}.svg" alt="{l}" title="{l}" '
        'width="{s}" height="{s}" loading="lazy" decoding="async"'
        '{c}>'.format(n=name, l=label, s=size,
                      c=' class="{}"'.format(cls) if cls else '')
    )


def bank_icon(name, size=40, cls=''):
    """آیکون بانک/درگاه پرداخت ایرانی به‌صورت تگ <img>."""
    path = os.path.join(_BANK_DIR, '{}.svg'.format(name))
    if not os.path.exists(path):
        return Markup('')
    label = IR_BANKS.get(name, name)
    return Markup(
        '<img src="/static/img/banks/{n}.svg" alt="{l}" title="{l}" '
        'width="{s}" height="{s}" loading="lazy" decoding="async"'
        '{c}>'.format(n=name, l=label, s=size,
                      c=' class="{}"'.format(cls) if cls else '')
    )


def bank_names():
    """لیست (شناسه، نام فارسی) بانک‌ها و درگاه‌ها — برای مرورگر آیکون."""
    return sorted(IR_BANKS.items())


def messenger_names():
    """لیست (شناسه، اطلاعات) پیام‌رسان‌ها — برای فرم‌ها و فوتر."""
    return sorted(IR_MESSENGERS.items())
