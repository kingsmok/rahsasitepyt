# -*- coding: utf-8 -*-
"""صفحه اصلی صفحه‌ساز: ساخت، ذخیره، نمایش روی / و بازنشانی طرح."""
import json
import re

from models import Page, Setting, User, db

from tests.conftest import csrf_headers


def _make_admin(app, email='homeadmin@test.ir'):
    with app.app_context():
        a = User(name='Admin Home', email=email, phone='09120000501',
                 role='super_admin', is_active=True)
        a.set_password('admin123')
        db.session.add(a)
        db.session.commit()
        return a.id


def _login_admin(client, app, email='homeadmin@test.ir'):
    r = client.get('/auth/login')
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/login', data={'_csrf_token': tok, 'email': email,
                                     'password': 'admin123'})
    code2 = app.config.get('_TEST_AUTH_CODES', {}).get('admin-2fa')
    assert code2
    r = client.get('/auth/admin-2fa')
    tok2 = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/admin-2fa', data={'_csrf_token': tok2, 'code': code2})


def _csrf_form(client, path):
    r = client.get(path)
    assert r.status_code == 200, path
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.get_data(as_text=True))
    assert m, 'توکن CSRF در %s نیست' % path
    return m.group(1)


def _heading_rows(text):
    return [{
        'id': 'r_home_test',
        'settings': {'gap': 0, 'py': 24},
        'cols': [[{
            'id': 'w_home_test',
            'type': 'heading',
            'data': {'text': text, 'tag': 'h1', 'align': 'center', 'mb': '16'},
        }]],
    }]


def test_open_home_requires_login(client):
    r = client.get('/builder/open-home', follow_redirects=False)
    assert r.status_code in (302, 303)
    loc = r.headers.get('Location', '')
    assert '/auth/login' in loc


def test_open_home_creates_and_redirects(client, app):
    _make_admin(app)
    _login_admin(client, app)
    r = client.get('/builder/open-home', follow_redirects=False)
    assert r.status_code in (302, 303)
    loc = r.headers.get('Location', '')
    assert '/builder/' in loc
    assert '/builder/open-home' not in loc
    with app.app_context():
        page = Page.query.filter_by(ptype='home').first()
        assert page is not None
        assert page.is_published
        assert page.rows()
        design = db.session.get(Setting, 'home_design')
        assert design and design.value == 'builder'
    ed = client.get(loc)
    assert ed.status_code == 200
    body = ed.get_data(as_text=True)
    assert 'pb-editor-body' in body
    assert 'pb-home-banner' in body


def test_builder_home_slug_is_editor_not_loop(client, app):
    _make_admin(app)
    _login_admin(client, app)
    client.get('/builder/open-home', follow_redirects=True)
    with app.app_context():
        page = Page.query.filter_by(ptype='home').first()
        assert page is not None
        slug = page.slug
    r = client.get('/builder/' + slug, follow_redirects=False)
    assert r.status_code == 200
    assert 'pb-editor-body' in r.get_data(as_text=True)
    if slug == 'home':
        r2 = client.get('/builder/home', follow_redirects=False)
        assert r2.status_code == 200
        assert 'pb-editor-body' in r2.get_data(as_text=True)


def test_home_design_builder_creates_page(client, app):
    _make_admin(app)
    _login_admin(client, app)
    tok = _csrf_form(client, '/admin/designs')
    r = client.post('/admin/designs', data={
        '_csrf_token': tok,
        'field': 'home_design',
        'value': 'builder',
    }, follow_redirects=False)
    assert r.status_code in (302, 303)
    with app.app_context():
        page = Page.query.filter_by(ptype='home').first()
        assert page is not None
        assert page.rows()
        design = db.session.get(Setting, 'home_design')
        assert design and design.value == 'builder'


def test_homepage_renders_saved_heading(client, app):
    marker = 'خانه بیلدر تست یکتا'
    _make_admin(app)
    _login_admin(client, app)
    with app.app_context():
        page = Page(
            title='صفحه اصلی', slug='main-home', ptype='home',
            is_published=True,
            content=json.dumps({'settings': {}, 'rows': _heading_rows(marker)},
                               ensure_ascii=False),
        )
        db.session.add(page)
        row = db.session.get(Setting, 'home_design')
        if row:
            row.value = 'builder'
        else:
            db.session.add(Setting(key='home_design', value='builder'))
        db.session.commit()
        app.clear_cache()
    r = client.get('/')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert marker in body
    assert 'pb-heading' in body


def test_api_save_activates_builder_home(client, app):
    marker = 'تیتر ذخیره‌شده صفحه‌ساز'
    _make_admin(app)
    _login_admin(client, app)
    with app.app_context():
        page = Page(
            title='صفحه اصلی', slug='home', ptype='home',
            is_published=True,
            content=json.dumps({'settings': {}, 'rows': []}, ensure_ascii=False),
        )
        db.session.add(page)
        db.session.commit()
    payload = {
        'slug': 'home',
        'settings': {},
        'published': True,
        'rows': _heading_rows(marker),
    }
    r = client.post('/builder/api/save', json=payload, headers=csrf_headers(client))
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data and data.get('ok')
    with app.app_context():
        design = db.session.get(Setting, 'home_design')
        assert design and design.value == 'builder'
        page = Page.query.filter_by(ptype='home').first()
        assert page.rows()
    home = client.get('/')
    assert home.status_code == 200
    assert marker in home.get_data(as_text=True)


def test_home_reset_finds_ptype_not_just_slug(client, app):
    _make_admin(app)
    _login_admin(client, app)
    with app.app_context():
        page = Page(
            title='خانه', slug='main-home', ptype='home',
            is_published=True,
            content=json.dumps({'settings': {}, 'rows': []}, ensure_ascii=False),
        )
        db.session.add(page)
        db.session.commit()
        pid = page.id
    tok = _csrf_form(client, '/admin/designs')
    r = client.post('/admin/designs', data={
        '_csrf_token': tok,
        'field': 'home_reset',
        'value': 'pd-01',
    }, follow_redirects=True)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'فیروزه‌ای اصفهان' in body
    with app.app_context():
        page = db.session.get(Page, pid)
        assert page.ptype == 'home'
        assert page.slug == 'main-home'
        assert page.rows()
        design = db.session.get(Setting, 'home_design')
        assert design and design.value == 'builder'
    live = client.get('/')
    assert live.status_code == 200
    assert 'آکادمی دانش — پنجره‌ای به دانایی بی‌پایان' in live.get_data(as_text=True)
