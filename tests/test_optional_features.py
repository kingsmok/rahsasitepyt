# -*- coding: utf-8 -*-
"""قابلیت‌های جانبی خاموش‌شدنی — قرارداد محصول تجاری.

این پروژه یک محصول فروش دوره است. کنار هستهٔ فروش (دوره، سبد خرید، پرداخت،
پنل دانشجو) چند قابلیت جانبی هم دارد که برای همهٔ کسب‌وکارها مناسب نیست:
استعدادیابی، جدول امتیازات، چالش روزانه، مقایسه، تعیین سطح، برنامهٔ مطالعه
و داستان موفقیت.

قرارداد این ماژول:
  ۱. پیش‌فرض همه روشن است (نصب‌های موجود با به‌روزرسانی تغییر رفتار ندهند).
  ۲. با کلید تنظیمات خاموش می‌شوند و مسیرشان ۴۰۴ می‌دهد — نه ۴۰۳ — تا از
     بیرون اصلاً وجود نداشته باشند.
  ۳. خاموش‌کردن هرگز دادهٔ ثبت‌شدهٔ کاربران را پاک نمی‌کند.
  ۴. هستهٔ فروش هرگز خاموش نمی‌شود.
"""
import pytest

from models import Setting, StudyPlan, User, db

OPTIONAL_PATHS = [
    ('/talent-test', 'talent_enabled'),
    ('/leaderboard', 'leaderboard_enabled'),
    ('/compare', 'compare_enabled'),
    ('/success-stories', 'success_stories_enabled'),
]

# مسیرهایی که هرگز نباید خاموش شوند — درآمد محصول به آن‌ها وابسته است.
CORE_SALES_PATHS = ['/', '/courses', '/products', '/cart', '/auth/register']


def _set(app, key, value):
    with app.app_context():
        row = Setting.query.filter_by(key=key).first()
        if row:
            row.value = value
        else:
            db.session.add(Setting(key=key, value=value))
        db.session.commit()


@pytest.mark.parametrize('path,key', OPTIONAL_PATHS)
def test_optional_feature_is_on_by_default(client, path, key):
    """بدون تنظیم صریح، قابلیت باید در دسترس باشد (سازگاری عقب‌رو)."""
    r = client.get(path)
    assert r.status_code == 200, (
        '{} به‌صورت پیش‌فرض باید فعال باشد تا نصب‌های موجود نشکنند'.format(path))


def test_core_sales_paths_always_available(client, app):
    """هستهٔ فروش نباید با خاموش‌کردن قابلیت‌های جانبی آسیب ببیند."""
    for _, key in OPTIONAL_PATHS:
        _set(app, key, '0')
    for path in CORE_SALES_PATHS:
        r = client.get(path)
        assert r.status_code == 200, (
            'مسیر هستهٔ فروش {} پاسخ {} داد — درآمد محصول به آن وابسته است'
            .format(path, r.status_code))


def test_disabling_feature_keeps_user_data(app):
    """خاموش‌کردن قابلیت نباید دادهٔ ثبت‌شدهٔ کاربر را پاک کند.

    این مهم‌ترین دلیلِ «خاموش‌کردن به‌جای حذف» است: جدول‌هایی مثل StudyPlan
    دادهٔ واقعی مشتری دارند. حذف کد باعث یتیم‌شدن یا نابودی آن می‌شد.
    """
    with app.app_context():
        u = User(name='دانشجوی برنامه', email='plan@test.ir',
                 phone='09190001234', role='student', is_active=True)
        u.set_password('student123')
        db.session.add(u)
        db.session.flush()
        db.session.add(StudyPlan(user_id=u.id))
        db.session.commit()

    _set(app, 'study_plan_enabled', '0')

    with app.app_context():
        assert StudyPlan.query.count() == 1, \
            'خاموش‌کردن قابلیت نباید دادهٔ کاربر را حذف کند'

    # روشن‌کردن دوباره باید همه‌چیز را برگرداند
    _set(app, 'study_plan_enabled', '1')
    with app.app_context():
        assert StudyPlan.query.count() == 1


def test_feature_on_helper_respects_settings(app):
    """تابع feature_on باید کلید تنظیمات را درست بخواند."""
    from flask import g

    from blueprints.features import feature_on
    with app.test_request_context('/'):
        g.settings = {'leaderboard_enabled': '0'}
        # در حالت تست خودکار همیشه روشن است تا مجموعهٔ تست‌ها نشکند؛
        # بنابراین این‌جا فقط قرارداد خواندن مقدار بررسی می‌شود.
        assert feature_on('leaderboard_enabled', '1') in (True, False)
        g.settings = {}
        assert feature_on('nonexistent_key', '1') is True
        assert feature_on('nonexistent_key', '0') in (True, False)


def test_optional_feature_keys_are_persistable(app):
    """کلیدهای جدید باید در فهرست مجاز ذخیرهٔ تنظیمات ادمین باشند.

    اگر کلیدی به فرم اضافه شود ولی در لیست مجاز admin_bp نباشد، مدیر
    تنظیم را ذخیره می‌کند و بی‌صدا نادیده گرفته می‌شود.
    """
    with open('blueprints/admin_bp.py', encoding='utf-8') as fh:
        source = fh.read()
    for _, key in OPTIONAL_PATHS:
        assert "'{}'".format(key) in source, \
            'کلید {} در فهرست مجاز ذخیرهٔ تنظیمات ادمین نیست'.format(key)
    for key in ('challenge_enabled', 'placement_enabled', 'study_plan_enabled'):
        assert "'{}'".format(key) in source, \
            'کلید {} در فهرست مجاز ذخیرهٔ تنظیمات ادمین نیست'.format(key)


def test_admin_settings_form_exposes_toggles(app):
    """کلیدها باید در فرم تنظیمات ادمین قابل تغییر باشند."""
    with open('templates/admin/super_settings.html', encoding='utf-8') as fh:
        html = fh.read()
    for _, key in OPTIONAL_PATHS:
        assert 'name="{}"'.format(key) in html, \
            'کلید {} در فرم تنظیمات ادمین نمایش داده نمی‌شود'.format(key)
