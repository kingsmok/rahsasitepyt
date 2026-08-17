# -*- coding: utf-8 -*-
"""تست حالت‌های نمایش — اعمال طراحی سایت (container/radius)، پنل تم، API تم."""
from models import db, Setting


def _set(app, key, value):
    with app.app_context():
        s = db.session.get(Setting, key)
        if s:
            s.value = value
        else:
            db.session.add(Setting(key=key, value=value))
        db.session.commit()


# ---------------------------------------------------------------
# اعمال طراحی سایت (site_design) — container و radius
# ---------------------------------------------------------------
def test_site_design_container_applied(client, app):
    """انتخاب طرح ۵ (مینیمال: container=1280, radius=8) باید روی رندر اعمال شود."""
    _set(app, 'site_design', '5')
    _set(app, 'kit_container', '')
    _set(app, 'kit_radius', '')
    body = client.get('/').get_data(as_text=True)
    assert '--container:1280px' in body
    assert '--radius-sm:8px' in body


def test_kit_override_beats_design(client, app):
    """اگر kit_container در تنظیمات ست شده باشد باید برنده باشد."""
    _set(app, 'site_design', '5')
    _set(app, 'kit_container', '1400')
    _set(app, 'kit_radius', '20')
    body = client.get('/').get_data(as_text=True)
    assert '--container:1400px' in body
    assert '--radius-sm:20px' in body


def test_pd_design_uses_persian_theme(client, app):
    """طرح ایرانی باید تم pd را لینک کند و container آن را اعمال کند."""
    _set(app, 'site_design', 'pd-01')  # فیروزه‌ای اصفهان
    _set(app, 'kit_container', '')
    _set(app, 'kit_radius', '')
    body = client.get('/').get_data(as_text=True)
    assert 'themes/pd-01.css' in body
    # pd-01 باید container داشته باشد
    import re
    m = re.search(r'--container:(\d+)px', body)
    assert m, 'container باید اعمال شود'


# ---------------------------------------------------------------
# پنل انتخاب تم
# ---------------------------------------------------------------
def test_theme_panel_present(client, app):
    """پنل تم باید در صفحه موجود باشد و تم‌ها را نمایش دهد."""
    body = client.get('/').get_data(as_text=True)
    assert 'theme-fab' in body
    assert 'theme-panel' in body
    assert 'آبی کلاسیک' in body      # تم ۰۱
    assert 'فیروزه‌ای اصفهان' in body  # تم ایرانی pd-01


def test_theme_panel_can_be_hidden_for_commercial_brand(client, app):
    _set(app, 'allow_theme_switcher', '0')
    body = client.get('/').get_data(as_text=True)
    assert 'id="theme-fab"' not in body
    assert 'id="theme-panel"' not in body


def test_theme_panel_shows_all_themes(client, app):
    """هر ۴۳ تم باید در پنل حضور داشته باشد."""
    from app import THEMES
    body = client.get('/').get_data(as_text=True)
    for t in THEMES:
        assert f'data-theme="{t["id"]}"' in body, f'missing {t["id"]}'


def test_set_theme_api_works(client, app):
    """API تغییر تم باید کوکی را ست کند و تم را اعمال کند."""
    r = client.post('/api/theme', json={'theme': 'theme-08'})
    assert r.status_code == 200
    assert r.get_json().get('ok') is True
    assert 'lms_theme=theme-08' in r.headers.get('Set-Cookie', '')
    # رندر بعدی باید تم جدید را لینک کند
    body = client.get('/').get_data(as_text=True)
    assert 'themes/theme-08.css' in body


def test_set_theme_api_rejects_invalid(client, app):
    """تم نامعتبر نباید پذیرفته شود."""
    r = client.post('/api/theme', json={'theme': 'theme-999'})
    assert r.status_code == 400


# ---------------------------------------------------------------
# انتخاب طرح از پنل ادمین
# ---------------------------------------------------------------
def _make_admin(app):
    from models import User
    with app.app_context():
        a = User(name='Admin', email='admind@test.ir', phone='09120000002',
                 role='admin', is_active=True)
        a.set_password('admin123')
        db.session.add(a)
        db.session.commit()
        return a.id


def test_admin_selects_site_design(client, app):
    """انتخاب طرح از پنل ادمین باید site_design را ذخیره و در رندر اعمال کند."""
    import re
    from test_admin_panel import _login_admin_2fa
    _make_admin(app)
    _login_admin_2fa(client, app, 'admind@test.ir', 'admin123')
    tok = _csrf_admin(client)
    r = client.post('/admin/designs', data={'_csrf_token': tok,
                                            'field': 'site_design', 'value': 'pd-03'},
                    follow_redirects=False)
    assert r.status_code == 302
    # رندر بعدی باید تم pd-03 را اعمال کند
    body = client.get('/').get_data(as_text=True)
    assert 'themes/pd-03.css' in body


def _csrf_admin(client):
    import re
    r = client.get('/admin/designs')
    m = re.search(r'name="_csrf_token" value="([^\"]+)"', r.text)
    return m.group(1) if m else 'test-token'
