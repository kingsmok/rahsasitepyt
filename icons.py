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
