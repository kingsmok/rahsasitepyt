# -*- coding: utf-8 -*-
"""تست مسیرهای عمومی و مدیریت خطا"""
from conftest import login


def test_home(client):
    r = client.get('/')
    assert r.status_code == 200
    assert 'آکادمی' in r.get_data(as_text=True)


def test_public_pages(client):
    for p in ['/courses', '/about', '/faq', '/contact', '/terms', '/privacy',
              '/teachers', '/blog', '/bundles', '/success-stories',
              '/verify-certificate', '/products']:
        r = client.get(p)
        assert r.status_code == 200, f'{p} → {r.status_code}'


def test_course_detail(client):
    r = client.get('/course/test-course')
    assert r.status_code == 200
    assert 'دوره تست' in r.get_data(as_text=True)


def test_404_page(client):
    r = client.get('/no-such-page-xyz')
    assert r.status_code == 404
    assert '۴۰۴' in r.get_data(as_text=True) or 'پیدا نشد' in r.get_data(as_text=True)


def test_invalid_ids_404(client):
    assert client.get('/course/99999').status_code == 404
    assert client.get('/teacher/999').status_code == 404
    assert client.get('/quiz/999').status_code == 404


def test_dashboard_requires_login(client):
    r = client.get('/dashboard')
    assert r.status_code == 302
    assert '/auth/login' in r.headers['Location']
