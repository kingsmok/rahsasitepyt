# -*- coding: utf-8 -*-
"""صفحه‌ساز برای همه بخش‌های عمومی: ساخت یک‌کلیکی، نمایش زنده، فیلتر فهرست."""
import json
import re

from models import Bundle, Page, Product, User, db

from tests.conftest import csrf_headers


def _make_admin(app, email='secadmin@test.ir'):
    with app.app_context():
        a = User(name='Admin Sections', email=email, phone='09120000511',
                 role='super_admin', is_active=True)
        a.set_password('admin123')
        db.session.add(a)
        db.session.commit()
        return a.id


def _login_admin(client, app, email='secadmin@test.ir'):
    r = client.get('/auth/login')
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/login', data={'_csrf_token': tok, 'email': email,
                                     'password': 'admin123'})
    code2 = app.config.get('_TEST_AUTH_CODES', {}).get('admin-2fa')
    assert code2
    r = client.get('/auth/admin-2fa')
    tok2 = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/admin-2fa', data={'_csrf_token': tok2, 'code': code2})


def _heading_rows(text, wtype='heading'):
    return [{
        'id': 'r_sec_test',
        'settings': {'gap': 0, 'py': 24},
        'cols': [[{
            'id': 'w_sec_test',
            'type': wtype,
            'data': {'text': text, 'tag': 'h1', 'align': 'center', 'mb': '16',
                     'title': text},
        }]],
    }]


def _publish_page(app, slug, marker, widget='heading'):
    with app.app_context():
        page = Page.query.filter_by(slug=slug).first()
        assert page is not None
        page.is_published = True
        page.content = json.dumps(
            {'settings': {}, 'rows': _heading_rows(marker, widget)},
            ensure_ascii=False)
        db.session.commit()
        app.clear_cache()
        return page.id


def test_open_section_requires_login(client):
    r = client.get('/builder/open/courses', follow_redirects=False)
    assert r.status_code in (302, 303)
    assert '/auth/login' in r.headers.get('Location', '')


def test_open_section_unknown_404(client, app):
    _make_admin(app)
    _login_admin(client, app)
    r = client.get('/builder/open/not-a-section', follow_redirects=False)
    assert r.status_code == 404


def test_open_section_courses_creates_draft(client, app):
    _make_admin(app)
    _login_admin(client, app)
    r = client.get('/builder/open/courses', follow_redirects=False)
    assert r.status_code in (302, 303)
    loc = r.headers.get('Location', '')
    assert '/builder/' in loc
    assert '/builder/open/' not in loc
    with app.app_context():
        page = Page.query.filter_by(slug='courses', ptype='page').first()
        assert page is not None
        assert not page.is_published
        assert page.rows()
    ed = client.get(loc)
    assert ed.status_code == 200
    body = ed.get_data(as_text=True)
    assert 'pb-editor-body' in body
    assert 'pb-home-banner' in body


def test_builder_index_lists_new_sections(client, app):
    _make_admin(app)
    _login_admin(client, app)
    r = client.get('/builder')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert '/courses' in body
    assert '/products' in body
    assert '/bundles' in body
    assert '/success-stories' in body
    assert '/verify-certificate' in body
    assert 'قالب‌های تک‌صفحه' in body
    assert 'builder.open_section' not in body
    assert '/builder/open/courses' in body


def test_courses_builder_live_without_filters(client, app):
    marker = 'تیتر فهرست دوره‌ها یکتا'
    _make_admin(app)
    _login_admin(client, app)
    client.get('/builder/open/courses', follow_redirects=True)
    _publish_page(app, 'courses', marker)
    r = client.get('/courses')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert marker in body
    assert 'pb-heading' in body


def test_courses_filters_keep_static(client, app):
    marker = 'تیتر فیلترنشده دوره‌ها'
    _make_admin(app)
    _login_admin(client, app)
    client.get('/builder/open/courses', follow_redirects=True)
    _publish_page(app, 'courses', marker)
    r = client.get('/courses?q=پایتون')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert marker not in body


def test_products_builder_live(client, app):
    marker = 'تیتر فروشگاه صفحه‌ساز'
    _make_admin(app)
    _login_admin(client, app)
    client.get('/builder/open/products', follow_redirects=True)
    _publish_page(app, 'products', marker)
    r = client.get('/products')
    assert r.status_code == 200
    assert marker in r.get_data(as_text=True)
    filtered = client.get('/products?q=لیوان')
    assert filtered.status_code == 200
    assert marker not in filtered.get_data(as_text=True)


def test_verify_certificate_builder_post_result(client, app):
    _make_admin(app)
    _login_admin(client, app)
    client.get('/builder/open/verify-certificate', follow_redirects=True)
    with app.app_context():
        page = Page.query.filter_by(slug='verify-certificate').first()
        page.is_published = True
        page.content = json.dumps({
            'settings': {},
            'rows': [{
                'id': 'r_vrf',
                'settings': {'gap': 0, 'py': 24},
                'cols': [[{
                    'id': 'w_vrf',
                    'type': 'cert_verify',
                    'data': {'title': 'استعلام گواهی بیلدر',
                             'text': 'کد را وارد کنید.'},
                }]],
            }],
        }, ensure_ascii=False)
        db.session.commit()
        app.clear_cache()
    live = client.get('/verify-certificate')
    assert live.status_code == 200
    body = live.get_data(as_text=True)
    assert 'استعلام گواهی بیلدر' in body
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', body).group(1)
    posted = client.post('/verify-certificate', data={
        '_csrf_token': tok,
        'code': 'CRT-NO-SUCH',
    })
    assert posted.status_code == 200
    out = posted.get_data(as_text=True)
    assert 'استعلام گواهی بیلدر' in out
    assert 'یافت نشد' in out


def test_shop_products_widget_renders(client, app):
    _make_admin(app)
    _login_admin(client, app)
    with app.app_context():
        db.session.add(Product(
            title='لیوان تست صفحه‌ساز', slug='mug-builder', price=45000,
            discount_price=30000, is_active=True, stock=4, category='لیوان'))
        db.session.commit()
    from blueprints.builder import builder_shop_products
    with app.test_request_context('/'):
        with app.app_context():
            rows = builder_shop_products({'limit': '8', 'sort': 'newest'})
            assert any(p.slug == 'mug-builder' for p in rows)
            mug = next(p for p in rows if p.slug == 'mug-builder')
            assert mug.final_price == 30000
            assert mug.has_discount
    payload = {
        'edit': False,
        'rows': [{
            'id': 'r_shop',
            'settings': {'gap': 16, 'py': 16},
            'cols': [[{
                'id': 'w_shop',
                'type': 'shop_products',
                'data': {'title': 'فروشگاه ویجت', 'limit': '8',
                         'columns': '4', 'show_price': True},
            }]],
        }],
    }
    r = client.post('/builder/api/render', json=payload,
                    headers=csrf_headers(client))
    assert r.status_code == 200
    data = r.get_json()
    assert data and data.get('ok')
    html = data.get('html') or ''
    assert 'لیوان تست صفحه‌ساز' in html
    assert '/product/mug-builder' in html


def test_bundles_widget_renders(client, app):
    _make_admin(app)
    _login_admin(client, app)
    with app.app_context():
        db.session.add(Bundle(
            title='بسته تست صفحه‌ساز', slug='bundle-builder',
            description='سه دوره با هم', price=900000, discount_price=600000,
            is_active=True))
        db.session.commit()
    from blueprints.builder import builder_bundles
    with app.test_request_context('/'):
        with app.app_context():
            rows = builder_bundles({'limit': '6'})
            assert any(b.slug == 'bundle-builder' for b in rows)
    payload = {
        'edit': False,
        'rows': [{
            'id': 'r_bnd',
            'settings': {'gap': 16, 'py': 16},
            'cols': [[{
                'id': 'w_bnd',
                'type': 'bundles',
                'data': {'title': 'بسته‌های ویجت', 'limit': '6',
                         'columns': '3', 'show_price': True},
            }]],
        }],
    }
    r = client.post('/builder/api/render', json=payload,
                    headers=csrf_headers(client))
    assert r.status_code == 200
    data = r.get_json()
    assert data and data.get('ok')
    html = data.get('html') or ''
    assert 'بسته تست صفحه‌ساز' in html
    assert '/bundle/bundle-builder' in html
