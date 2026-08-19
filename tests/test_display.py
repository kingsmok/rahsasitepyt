# -*- coding: utf-8 -*-
"""تست ظاهر سایت — اعمال طراحی مدیر و نبود انتخاب‌گر رنگ عمومی."""
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
# حذف انتخاب‌گر رنگ/تم عمومی
# ---------------------------------------------------------------
def test_public_theme_picker_is_removed_from_all_base_pages(client, app):
    """حتی تنظیم قدیمی نباید دکمه یا پنل شناور رنگ را دوباره نمایش دهد."""
    _set(app, 'allow_theme_switcher', '1')
    for path in ('/', '/courses', '/auth/login'):
        response = client.get(path)
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert 'id="theme-fab"' not in body
        assert 'id="theme-panel"' not in body
        assert 'data-close-theme' not in body
        assert "fetch('/api/theme'" not in body


def test_public_theme_api_is_removed(client):
    """مسیر قدیمی نباید امکان ذخیره تم شخصی یا کوکی رنگ ایجاد کند."""
    response = client.post('/api/theme', json={'theme': 'theme-08'})
    assert response.status_code == 404
    assert 'lms_theme=' not in response.headers.get('Set-Cookie', '')


def test_legacy_theme_cookie_cannot_override_admin_design(client, app):
    """رنگ سایت برای همه بازدیدکنندگان از طراحی مدیر می‌آید، نه کوکی قدیمی."""
    _set(app, 'site_design', '1')
    client.set_cookie('lms_theme', 'theme-08')
    body = client.get('/').get_data(as_text=True)
    assert 'themes/theme-22.css' in body
    assert 'themes/theme-08.css' not in body


def test_missing_course_image_uses_neutral_placeholder(client, app):
    from models import Course
    with app.app_context():
        course = Course.query.filter_by(slug='test-course').first()
        course.image = 'missing-course-cover.jpg'
        db.session.commit()
        assert course.image_url == '/static/img/course-placeholder.webp'
    page = client.get('/course/test-course')
    assert page.status_code == 200
    assert '/static/img/course-placeholder.webp' in page.text
    assert 'cover-python' not in page.text


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
