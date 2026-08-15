# -*- coding: utf-8 -*-
"""پرچم‌های اجرای سراسری و امن برنامه.

رفتارهای نمایشی (نمایش OTP، پرداخت ساختگی و دادهٔ نمونه) به‌صورت پیش‌فرض خاموش
هستند و در محیط production تحت هیچ شرایطی فعال نمی‌شوند. تست‌های خودکار Flask
می‌توانند از ``TESTING`` استفاده کنند، بدون آن‌که این رفتار به سایت واقعی نشت کند.
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


def demo_features_enabled():
    """آیا قابلیت‌های نمایشی واقعاً مجازند؟

    - production: همیشه False
    - تست خودکار Flask: True (برای تست مسیرهای قدیمی بدون انتشار عمومی)
    - توسعه: فقط با ENABLE_DEMO_FEATURES=1
    """
    if is_production():
        return False
    # pytest فقط یک محیط داخلی و غیرقابل دسترس برای کاربر است.
    if os.environ.get('PYTEST_CURRENT_TEST'):
        return True
    try:
        from flask import current_app, has_app_context
        if has_app_context():
            if current_app.testing:
                return True
            return bool(current_app.config.get('DEMO_FEATURES_ENABLED', False))
    except Exception:
        pass
    return env_flag('ENABLE_DEMO_FEATURES', False)
