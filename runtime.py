# -*- coding: utf-8 -*-
"""پرچم‌های اجرای سراسری و امن برنامه.

دادهٔ نمایشی از شبیه‌سازی عملیاتی جداست: دموی فروش می‌تواند محتوای برچسب‌خورده
داشته باشد، اما OTP، پرداخت، کیف پول و BNPL ساختگی فقط در تست خودکار Flask مجازند.
در production هیچ‌کدام از مسیرهای نمایشی فعال نمی‌شوند.
"""
import os


def env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return bool(default)
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def is_production():
    return (os.environ.get('FLASK_ENV', '').strip().lower() == 'production' or
            os.environ.get('APP_ENV', '').strip().lower() == 'production')


def automated_test_mode():
    """مجوز شبیه‌سازی عملیاتی؛ فقط pytest/Flask TESTING و هرگز دموی فروش."""
    if is_production():
        return False
    if os.environ.get('PYTEST_CURRENT_TEST'):
        return True
    try:
        from flask import current_app, has_app_context
        return bool(has_app_context() and current_app.testing)
    except Exception:
        return False


def demo_content_enabled():
    """اجازه ساخت/نمایش دیتای نمونهٔ برچسب‌خورده در محیط توسعه."""
    if is_production():
        return False
    if automated_test_mode():
        return True
    try:
        from flask import current_app, has_app_context
        if has_app_context():
            return bool(current_app.config.get('DEMO_FEATURES_ENABLED', False))
    except Exception:
        pass
    return env_flag('ENABLE_DEMO_FEATURES', False)


def demo_features_enabled():
    """نام سازگار قدیمی؛ فقط محتوای دمو، نه OTP/پرداخت/اعتبار ساختگی."""
    return demo_content_enabled()
