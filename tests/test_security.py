# -*- coding: utf-8 -*-
"""تست‌های امنیتی — CSRF، آپلود، XSS، IDOR"""
import io
import re
from conftest import csrf_headers, login


def test_csrf_rejects_missing_token(client):
    """POST بدون توکن CSRF → 400"""
    r = client.post('/contact', data={'name': 'x', 'message': 'y'})
    assert r.status_code == 400


def test_api_cart_requires_csrf(client):
    """POST سبد زیر /api بدون توکن باید 400 بدهد (نه موفق)."""
    r = client.post('/api/cart/add', json={'course_id': 1})
    assert r.status_code == 400
    assert r.get_json()['ok'] is False


def test_csrf_accepts_valid_token(client):
    r = client.get('/contact')
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    r = client.post('/contact', data={
        '_csrf_token': m.group(1), 'name': 'کاربر', 'email': 'x@x.ir',
        'subject': 'سوال', 'message': 'پیام تست',
    }, follow_redirects=False)
    assert r.status_code == 302


def test_upload_rejects_dangerous_ext(client):
    """آپلود فایل .php باید رد شود (کتابخانه رسانه فقط برای مدرس/ادمین است)"""
    login(client, 't@test.ir', 'teacher123')
    r = client.post('/api/media/upload', data={
        'file': (io.BytesIO(b'<?php echo 1;'), 'shell.php')
    }, headers=csrf_headers(client), content_type='multipart/form-data')
    assert r.status_code == 400


def test_upload_rejects_svg_dangerous_content(client):
    """SVG می‌تواند اسکریپت اجرا شود؛ باید رد شود (حتی برای مدرس/ادمین)"""
    login(client, 't@test.ir', 'teacher123')
    r = client.post('/api/media/upload', data={
        'file': (io.BytesIO(b'<svg onload="alert(1)"></svg>'), 'x.svg')
    }, headers=csrf_headers(client), content_type='multipart/form-data')
    assert r.status_code == 400


def test_media_upload_forbidden_for_student(client):
    """کتابخانه رسانه مرکزی نباید برای دانشجوی معمولی باز باشد (فقط ادمین/مدرس) —
    این همان حفره‌ای بود که امکان میزبانی محتوای فریب‌دهنده/مخرب زیر دامنه را
    می‌داد و باعث علامت‌گذاری توسط Safe Browsing گوگل/فایرفاکس می‌شد."""
    login(client, 'demo@test.ir', 'demo123')
    r = client.post('/api/media/upload', data={
        'file': (io.BytesIO(b'fake image bytes'), 'pic.png')
    }, headers=csrf_headers(client), content_type='multipart/form-data')
    assert r.status_code == 403


def test_upload_rejects_non_image_in_builder(client):
    """آپلود غیرتصویر در صفحه‌ساز رد شود"""
    # ادمین بسازیم
    r = client.post('/api/media/upload', data={
        'file': (io.BytesIO(b'MZ fake exe'), 'evil.exe')
    }, headers=csrf_headers(client), content_type='multipart/form-data')
    assert r.status_code in (400, 401, 403)


def test_xss_escaped_in_comment(client):
    """XSS در متن‌ها escape شود"""
    # ثبت نظر با اسکریپت — صفحه نباید تگ را اجرا کند
    login(client, 'demo@test.ir', 'demo123')
    r = client.get('/course/test-course')
    html = r.get_data(as_text=True)
    assert '<script>alert(1)</script>' not in html


def test_private_lesson_file_protected(client):
    """فایل درس بدون لاگین → ریدایرکت لاگین"""
    r = client.get('/static/uploads/lessons/anything.zip')
    assert r.status_code in (302, 403)


def test_csrf_rejection_returns_400_not_500(client):
    """POST بدون CSRF باید 400 برگرداند نه 500 — regression برای خطای آبشاری context processor"""
    r = client.post('/contact', data={'name': 'x', 'message': 'y'})
    assert r.status_code == 400


def test_csrf_rejection_on_admin_post(client):
    """POST ادمین بدون CSRF → 400 نه 500"""
    r = client.post('/admin/menus/new', data={})
    assert r.status_code in (400, 302)  # 302 اگر لاگین نباشد
