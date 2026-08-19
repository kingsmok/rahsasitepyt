# -*- coding: utf-8 -*-
"""تست امنیتی: غیرفعال‌سازی خودکار حساب ادمینِ seed در حالت غیر دمو.

seed.py حسابی با رمز منتشرشدهٔ `admin@academy.ir / admin123` می‌سازد. اگر
دیتابیس seed‌شده به production بیاید، این حساب باید به‌صورت خودکار غیرفعال
شود (مانند بقیهٔ حساب‌های نمایشی) تا backdoor باقی نماند.
"""
import runtime
from models import db, User


def test_seeded_admin_deactivated_in_non_demo_mode(app, monkeypatch):
    with app.app_context():
        u = User(name='مدیر سیستم', email='admin@academy.ir', phone='09120000000',
                 role='admin', is_active=True)
        u.set_password('admin123')
        db.session.add(u)
        db.session.commit()
        uid = u.id

    # شبیه‌سازی محیط غیر دمو (production/تست خودکار خاموش) تا مسیر پاک‌سازی
    # دادهٔ نمایشی در load_globals واقعاً اجرا شود.
    monkeypatch.setattr(runtime, 'is_production', lambda: False)
    monkeypatch.setattr(runtime, 'automated_test_mode', lambda: False)
    # مقدار در هنگام ساخت اپ (با تست خودکار فعال) True ست شده؛ برای شبیه‌سازی
    # دقیق production آن را خاموش می‌کنیم.
    app.config['DEMO_FEATURES_ENABLED'] = False

    client = app.test_client()
    r = client.get('/')
    assert r.status_code == 200

    with app.app_context():
        u2 = db.session.get(User, uid)
        assert u2 is not None
        assert u2.is_active is False


def test_demo_mode_keeps_seeded_admin_active(app):
    """در حالت دمو (تست خودکار) حساب ادمین seed نباید غیرفعال شود."""
    with app.app_context():
        u = User(name='مدیر سیستم', email='admin@academy.ir', phone='09120000001',
                 role='admin', is_active=True)
        u.set_password('admin123')
        db.session.add(u)
        db.session.commit()
        uid = u.id

    client = app.test_client()
    r = client.get('/')
    assert r.status_code == 200

    with app.app_context():
        u2 = db.session.get(User, uid)
        assert u2.is_active is True
