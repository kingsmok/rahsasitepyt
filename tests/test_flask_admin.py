# -*- coding: utf-8 -*-
"""تست رگرسیون: یکپارچگی Flask-Admin در /admin-extra.

پیش از این، پوستهٔ ``templates/admin/base.html`` قالب پایهٔ Flask-Admin را سایه
می‌انداخت و توکن CSRF ما (رشتهٔ ساده) قالب‌های Flask-Admin را با
``'str' object is not callable`` می‌شکست. این تست‌ها صحت رندر شدن پنل و
تفکیک سطح دسترسی را تضمین می‌کنند.
"""
import re
from conftest import login
from models import db, User
from tests.test_admin_panel import _login_admin_2fa


def test_flask_admin_renders_own_ui_for_admin(client, app):
    """ادمین باید UI واقعی Flask-Admin را ببیند (نه سایدبار پنل اصلی)."""
    a = User(name='Admin', email='faadmin@test.ir', phone='09120000121',
             role='admin', is_active=True)
    with app.app_context():
        a.set_password('admin123')
        db.session.add(a)
        db.session.commit()
    _login_admin_2fa(client, app, 'faadmin@test.ir', 'admin123')
    r = client.get('/admin-extra/')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    # نباید سایدبار پنل مدیریت اصلی ما رندر شود
    assert 'as-sidebar' not in body
    # نوار Flask-Admin باید حاضر باشد
    assert 'navbar' in body


def test_flask_admin_model_views_render_for_admin(client, app):
    """لیست مدل‌ها (دوره/سفارش/تیکت) برای ادمین باید 200 بدهد + توکن CSRF واقعی."""
    a = User(name='Admin', email='faadmin2@test.ir', phone='09120000122',
             role='admin', is_active=True)
    with app.app_context():
        a.set_password('admin123')
        db.session.add(a)
        db.session.commit()
    _login_admin_2fa(client, app, 'faadmin2@test.ir', 'admin123')
    body = client.get('/admin-extra/course/').get_data(as_text=True)
    # توکن CSRF فرم اکشن‌ها باید مقدار واقعی (۳۲ کاراکتر هگز) داشته باشد
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body)
    assert m is not None and len(m.group(1)) == 32
    for path in ['/admin-extra/course/', '/admin-extra/order/', '/admin-extra/ticket/']:
        r = client.get(path)
        assert r.status_code == 200, f'{path} -> {r.status_code}'


def test_flask_admin_user_view_restricted_to_super_admin(client, app):
    """کاربر-ویوی Flask-Admin (شامل فیلد role) فقط برای سوپرادمین باز است."""
    a = User(name='Admin', email='faadmin3@test.ir', phone='09120000123',
             role='admin', is_active=True)
    with app.app_context():
        a.set_password('admin123')
        db.session.add(a)
        db.session.commit()
    _login_admin_2fa(client, app, 'faadmin3@test.ir', 'admin123')
    r = client.get('/admin-extra/user/')
    # مدیر عادی نباید به ویرایش نقش از Flask-Admin دسترسی داشته باشد
    assert r.status_code in (302, 403)
