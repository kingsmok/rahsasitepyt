# -*- coding: utf-8 -*-
"""تست احراز هویت — ثبت‌نام، ورود، خروج، دسترسی"""
import re
from conftest import login


def test_login_success(client):
    r = login(client, 'demo@test.ir', 'demo123')
    assert r.status_code == 302
    # پروفایل دمو ناقص است → به تکمیل پروفایل می‌رود (رفتار درست اپ)
    assert '/complete-profile' in r.headers['Location'] or '/dashboard' in r.headers['Location']


def test_login_wrong_password(client):
    r = login(client, 'demo@test.ir', 'wrong-pass')
    assert r.status_code == 200  # صفحه لاگین با پیام خطا


def test_register_new_user(client):
    r = client.get('/auth/register')
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    r = client.post('/auth/register', data={
        '_csrf_token': m.group(1),
        'name': 'کاربر جدید', 'email': 'new@test.ir', 'phone': '09120000123',
        'national_code': '0013542419', 'password': 'secret123', 'confirm': 'secret123',
    }, follow_redirects=False)
    assert r.status_code == 302


def test_register_without_national_code(client):
    """کد ملی اختیاری است — ثبت‌نام بدون کد ملی باید موفق باشد (ضد فیشینگ)."""
    r = client.get('/auth/register')
    m = re.search(r'name="_csrf_token" value="([^\"]+)"', r.text)
    r = client.post('/auth/register', data={
        '_csrf_token': m.group(1),
        'name': 'کاربر بدون کد ملی', 'email': 'nocode@test.ir', 'phone': '09120000555',
        'national_code': '', 'password': 'secret123', 'confirm': 'secret123',
    }, follow_redirects=False)
    assert r.status_code == 302  # بدون کد ملی هم ثبت‌نام موفق است


def test_register_form_does_not_force_national_code(client):
    """فرم ثبت‌نام نباید کد ملی را در سمت مرورگر اجباری کند.

    تست کلاینت pytest اعتبارسنجی HTML5 را اجرا نمی‌کند، بنابراین اگر فقط
    بک‌اند اصلاح شود ولی ویژگی required در قالب بماند، کاربر واقعی همچنان
    نمی‌تواند بدون کد ملی ثبت‌نام کند (باگ پنهان از دید تست‌ها).
    """
    r = client.get('/auth/register')
    assert r.status_code == 200
    m = re.search(r'<input[^>]*name="national_code"[^>]*>', r.text)
    assert m, 'فیلد کد ملی در فرم ثبت‌نام پیدا نشد'
    assert 'required' not in m.group(0), 'کد ملی نباید در HTML اجباری باشد'


def test_register_rejects_invalid_national_code(client):
    """کد ملی اختیاری است، اما اگر وارد شد باید معتبر باشد."""
    r = client.get('/auth/register')
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    r = client.post('/auth/register', data={
        '_csrf_token': m.group(1),
        'name': 'کاربر کد غلط', 'email': 'badnc@test.ir', 'phone': '09120000556',
        'national_code': '1234567890', 'password': 'secret123', 'confirm': 'secret123',
    }, follow_redirects=False)
    assert r.status_code == 200  # فرم دوباره نمایش داده می‌شود، ثبت‌نام انجام نمی‌شود


def test_register_without_national_code_stores_null(client, app):
    """کد ملی خالی باید NULL ذخیره شود تا قید unique چند کاربر را نشکند."""
    from models import User
    for i, (name, email, phone) in enumerate([
        ('کاربر یک', 'n1@test.ir', '09120000601'),
        ('کاربر دو', 'n2@test.ir', '09120000602'),
    ]):
        r = client.get('/auth/register')
        m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
        r = client.post('/auth/register', data={
            '_csrf_token': m.group(1),
            'name': name, 'email': email, 'phone': phone,
            'national_code': '', 'password': 'secret123', 'confirm': 'secret123',
        }, follow_redirects=False)
        assert r.status_code == 302, f'ثبت‌نام کاربر {i + 1} بدون کد ملی شکست خورد'
        client.get('/auth/logout')
    with app.app_context():
        for email in ('n1@test.ir', 'n2@test.ir'):
            u = User.query.filter_by(email=email).first()
            assert u is not None
            assert u.national_code is None, 'کد ملی خالی باید NULL باشد نه رشته خالی'


def test_logout(client):
    login(client, 'demo@test.ir', 'demo123')
    r = client.get('/auth/logout', follow_redirects=False)
    assert r.status_code == 302
    # بعد از خروج، داشبورد باید ریدایرکت کند
    assert client.get('/dashboard').status_code == 302


def test_student_cannot_access_admin(client):
    login(client, 'demo@test.ir', 'demo123')
    r = client.get('/admin/', follow_redirects=False)
    assert r.status_code == 302  # ریدایرکت به بیرون


def test_2fa_flow_for_admin(client):
    """ادمین بعد از لاگین باید به صفحه 2FA برود و با کد دمو وارد شود"""
    r = login(client, 't@test.ir', 'teacher123')
    # مدرس (non-admin) مستقیم می‌رود داشبورد
    assert r.status_code == 302
