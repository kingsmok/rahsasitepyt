# -*- coding: utf-8 -*-
"""تست رگرسیون: ضد CSV Injection و برش طول فیلدهای سئو."""
from validators import csv_cell
from blueprints.seo_admin import _clip


def test_csv_cell_neutralizes_formula_prefixes():
    """سلول‌هایی که با = + - @ tab/CR شروع می‌شوند باید با ' پیشوند بگیرند."""
    assert csv_cell('=HYPERLINK("http://evil","x")') == "'=HYPERLINK(\"http://evil\",\"x\")"
    assert csv_cell('+cmd|calc') == "'+cmd|calc"
    assert csv_cell('-2+3') == "'-2+3"
    assert csv_cell('@SUM(A1:A2)') == "'@SUM(A1:A2)"
    # متن عادی و شماره موبایل دست‌نخورده بمانند
    assert csv_cell('نام عادی') == 'نام عادی'
    assert csv_cell('09211234567') == '09211234567'
    assert csv_cell(None) == ''
    assert csv_cell('') == ''


def test_seo_clip_truncates_to_column_limit():
    """مقادیر سئو باید به طول ستون‌های دیتابیس برش بخورند (ضد Data too long)."""
    assert len(_clip('x' * 500, 'title')) == 200
    assert len(_clip('x' * 500, 'description')) == 400
    assert len(_clip('x' * 500, 'focus_keyword')) == 100
    assert _clip('  hello  ', 'title') == 'hello'
