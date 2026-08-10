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
    # حذف ابعاد ثابت و کلاس‌های تبلر
    svg = re.sub(r'\s(width|height)="\d+"', '', svg, count=2)
    svg = re.sub(r'\sclass="[^"]*"', '', svg, count=1)
    svg = svg.replace('<svg ', f'<svg width="{size}" height="{size}" ', 1)
    if cls:
        svg = svg.replace('<svg ', f'<svg class="{cls}" ', 1)
    if title:
        svg = svg.replace('<svg ', f'<svg role="img" aria-label="{title}" ', 1)
    else:
        svg = svg.replace('<svg ', '<svg aria-hidden="true" ', 1)
    return Markup(svg)


def icon_names():
    """لیست نام آیکون‌ها برای مرورگر آیکون"""
    return sorted(_ICONS.keys())


_load_icons()


def init_icons(app):
    app.jinja_env.globals['icon'] = icon
    app.jinja_env.globals['icon_names'] = icon_names
