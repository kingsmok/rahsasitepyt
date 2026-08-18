# -*- coding: utf-8 -*-
"""رگرسیون‌های عرضه تجاری: انتشار، نقش‌ها، دموهای طراحی و همکار مدرس."""
import json
import re
from pathlib import Path

from conftest import login
from models import db, Course, CourseTeacher, Setting, User
from test_admin_panel import _login_admin_2fa


def _set_many(app, values):
    with app.app_context():
        for key, value in values.items():
            row = db.session.get(Setting, key)
            if row:
                row.value = str(value)
            else:
                db.session.add(Setting(key=key, value=str(value)))
        db.session.commit()
        clear = getattr(app, 'clear_cache', None)
        if callable(clear):
            clear()


def _make_user(app, role, suffix):
    with app.app_context():
        user = User(name=f'کاربر {role}', email=f'{suffix}@test.ir',
                    phone='0912' + str(abs(hash(suffix)) % 10_000_000).zfill(7),
                    role=role, is_active=True)
        user.set_password('StrongPass123!')
        db.session.add(user)
        db.session.commit()
        return user.id, user.email


def _csrf(client, path):
    response = client.get(path)
    match = re.search(r'name="_csrf_token" value="([^"]+)"', response.text)
    assert match, f'CSRF در {path} پیدا نشد (status={response.status_code})'
    return match.group(1)


# ------------------------------------------------------------------
# چرخه نصب غیرفعال → تکمیل → انتشار → غیرفعال‌سازی
# ------------------------------------------------------------------
def test_inactive_site_hides_public_but_admin_can_preview(app, client):
    _set_many(app, {'site_active': '0', 'site_name': 'سامانه آماده‌سازی'})
    guest = app.test_client()
    response = guest.get('/', follow_redirects=False)
    assert response.status_code == 302
    assert '/maintenance' in response.headers['Location']
    maintenance = guest.get('/maintenance')
    assert maintenance.status_code == 503
    assert 'در حال آماده‌سازی' in maintenance.text

    _make_user(app, 'admin', 'preview-admin')
    _login_admin_2fa(client, app, 'preview-admin@test.ir', 'StrongPass123!')
    assert client.get('/').status_code == 200
    assert client.get('/admin/go-live').status_code == 200


def test_paid_site_cannot_activate_without_real_gateway(app, client):
    _set_many(app, {
        'site_active': '0', 'site_name': 'آکادمی واقعی',
        'site_desc': 'آموزش پروژه‌محور', 'email': 'info@example.ir',
    })
    _make_user(app, 'admin', 'paid-admin')
    _login_admin_2fa(client, app, 'paid-admin@test.ir', 'StrongPass123!')
    token = _csrf(client, '/admin/go-live')
    response = client.post('/admin/go-live', data={
        '_csrf_token': token, 'action': 'activate',
    }, follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Setting, 'site_active').value == '0'


def test_free_site_can_activate_and_deactivate(app, client):
    _set_many(app, {
        'site_active': '0', 'site_name': 'آکادمی رایگان',
        'site_desc': 'محتوای آموزشی واقعی', 'email': 'info@example.ir',
    })
    with app.app_context():
        course = Course.query.filter_by(slug='test-course').first()
        course.price = 0
        course.discount_price = 0
        db.session.commit()
    _make_user(app, 'admin', 'launch-admin')
    _login_admin_2fa(client, app, 'launch-admin@test.ir', 'StrongPass123!')

    token = _csrf(client, '/admin/go-live')
    activated = client.post('/admin/go-live', data={
        '_csrf_token': token, 'action': 'activate',
    }, follow_redirects=False)
    assert activated.status_code == 302
    with app.app_context():
        assert db.session.get(Setting, 'site_active').value == '1'
    guest = app.test_client()
    assert guest.get('/').status_code == 200

    token = _csrf(client, '/admin/go-live')
    deactivated = client.post('/admin/go-live', data={
        '_csrf_token': token, 'action': 'deactivate',
    }, follow_redirects=False)
    assert deactivated.status_code == 302
    assert guest.get('/', follow_redirects=False).status_code == 302


# ------------------------------------------------------------------
# نقش‌های عملیاتی و اعمال واقعی role_permissions
# ------------------------------------------------------------------
def test_staff_roles_get_only_their_real_sections(app):
    cases = [
        ('secretary', 'secretary-role',
         {'/admin/': 200, '/admin/users': 200, '/admin/orders': 200,
          '/admin/consultations': 200, '/admin/tickets': 403}),
        ('support', 'support-role',
         {'/admin/': 200, '/admin/users': 200, '/admin/tickets': 200,
          '/admin/orders': 403, '/admin/roles': 403}),
        ('operator', 'operator-role',
         {'/admin/': 200, '/admin/orders': 200, '/admin/proofs': 200,
          '/admin/tickets': 403, '/admin/roles': 403}),
    ]
    for role, suffix, expectations in cases:
        role_client = app.test_client()
        _make_user(app, role, suffix)
        result = login(role_client, f'{suffix}@test.ir', 'StrongPass123!')
        assert result.status_code == 302
        for path, status in expectations.items():
            assert role_client.get(path).status_code == status, f'{role}: {path}'
        dashboard = role_client.get('/admin/').text
        assert 'مجموع درآمد' not in dashboard


def test_custom_role_permission_changes_guard_and_menu(app, client):
    permissions = {
        'support': ['dashboard', 'view_users', 'reply_tickets',
                    'view_user_courses', 'use_canned_replies', 'view_orders'],
    }
    _set_many(app, {'role_permissions': json.dumps(permissions)})
    _make_user(app, 'support', 'custom-support')
    login(client, 'custom-support@test.ir', 'StrongPass123!')
    response = client.get('/admin/orders')
    assert response.status_code == 200
    panel = client.get('/admin/')
    assert '/admin/orders' in panel.text
    assert '/admin/roles' not in panel.text


def test_secretary_can_register_only_student(app, client):
    _make_user(app, 'secretary', 'register-secretary')
    login(client, 'register-secretary@test.ir', 'StrongPass123!')
    page = client.get('/admin/users/add')
    assert page.status_code == 200
    assert 'value="teacher"' not in page.text
    token = _csrf(client, '/admin/users/add')
    blocked = client.post('/admin/users/add', data={
        '_csrf_token': token, 'name': 'مدرس غیرمجاز', 'email': 'bad-role@test.ir',
        'phone': '09121112223', 'password': 'StrongPass123!', 'role': 'teacher',
    })
    assert blocked.status_code == 403

    token = _csrf(client, '/admin/users/add')
    created = client.post('/admin/users/add', data={
        '_csrf_token': token, 'name': 'دانشجوی ثبت شده', 'email': 'new-student@test.ir',
        'phone': '09121112224', 'password': 'StrongPass123!', 'role': 'student',
    }, follow_redirects=False)
    assert created.status_code == 302
    with app.app_context():
        assert User.query.filter_by(email='new-student@test.ir', role='student').first()


# ------------------------------------------------------------------
# تمام حالت‌های طراحی قابل انتخاب باید واقعاً رندر شوند.
# ------------------------------------------------------------------
def test_all_public_design_modes_render_for_admin(app, client):
    from designs import HOME_DESIGNS, SITE_DESIGNS
    from design_variants import all_variants

    _make_user(app, 'admin', 'design-matrix')
    _login_admin_2fa(client, app, 'design-matrix@test.ir', 'StrongPass123!')

    for design_id in HOME_DESIGNS:
        response = client.get('/?design=' + design_id)
        assert response.status_code == 200, f'home design {design_id}'
        assert '<main' in response.text
    for path in ('/about', '/contact'):
        for design_id in ('1', '2', '3', '4', '5'):
            response = client.get(f'{path}?design={design_id}')
            assert response.status_code == 200, f'{path} design {design_id}'
            assert '<main' in response.text
    for design_id, design in SITE_DESIGNS.items():
        response = client.get('/?site_design=' + design_id + '&preview=1')
        assert response.status_code == 200, f'site design {design_id}'
        assert f'themes/{design["theme"]}.css' in response.text
    for variant in all_variants():
        response = client.get('/admin/design-preview/' + variant['design_id'])
        assert response.status_code == 200, f'variant {variant["design_id"]}'
        assert variant['theme_name'] in response.text


def test_design_demos_do_not_publish_fake_contact_details():
    from design_variants import all_variants
    payload = json.dumps(all_variants(), ensure_ascii=False)
    for fake in ('۰۲۱-۱۲۳۴۵۶۷۸', 'info@academy.ir',
                 'تهران، خیابان آزادی، پلاک ۱۲۳', '@academy_ir'):
        assert fake not in payload


def test_every_registered_theme_has_stylesheet():
    from app import THEMES
    root = Path(__file__).resolve().parents[1]
    missing = [theme['id'] for theme in THEMES
               if not (root / 'static' / 'css' / 'themes' /
                       f'{theme["id"]}.css').is_file()]
    assert not missing


def test_literal_static_references_resolve_to_real_files():
    """منابع literal در CSS/Jinja نباید بعد از تحویل ZIP به 404 برسند."""
    root = Path(__file__).resolve().parents[1]
    static = root / 'static'
    missing = []
    for stylesheet in static.rglob('*.css'):
        source = stylesheet.read_text(encoding='utf-8')
        for value in re.findall(r"url\(\s*['\"]?([^'\")]+)", source, re.I):
            value = value.strip()
            if not value or value.startswith(('data:', 'http:', 'https:', '#', 'var(')):
                continue
            target = ((static / value[len('/static/'):])
                      if value.startswith('/static/') else
                      (stylesheet.parent / value).resolve())
            if not target.is_file():
                missing.append('%s -> %s' % (stylesheet.relative_to(root), value))
    for template in (root / 'templates').rglob('*.html'):
        source = template.read_text(encoding='utf-8')
        for value in re.findall(
                r"url_for\(\s*['\"]static['\"]\s*,\s*filename\s*=\s*['\"]([^'\"]+)",
                source):
            if not (static / value).is_file():
                missing.append('%s -> %s' % (template.relative_to(root), value))
    assert not missing, '\n'.join(missing)


def test_public_empty_states_do_not_claim_unfinished_demo_features():
    root = Path(__file__).resolve().parents[1] / 'templates'
    for relative in ('community/live.html', 'features/success_stories.html',
                     'learning_paths.html'):
        source = (root / relative).read_text(encoding='utf-8')
        assert 'به‌زودی' not in source and 'در حال توسعه' not in source, relative


def test_demo_data_is_labeled_and_cannot_be_enabled_in_production(
        client, monkeypatch):
    page = client.get('/')
    assert 'نسخه نمایشی توسعه' in page.text
    from runtime import demo_features_enabled
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('ENABLE_DEMO_FEATURES', '1')
    assert demo_features_enabled() is False


# ------------------------------------------------------------------
# همکار مدرس باید در همه صفحات پنل همان دوره را ببیند.
# ------------------------------------------------------------------
def test_co_teacher_course_is_consistent_across_panel(app, client):
    teacher_id, email = _make_user(app, 'teacher', 'co-teacher')
    with app.app_context():
        course = Course.query.filter_by(slug='test-course').first()
        db.session.add(CourseTeacher(course_id=course.id, teacher_id=teacher_id))
        db.session.commit()
        course_id = course.id
    login(client, email, 'StrongPass123!')
    for path in ('/teacher-panel/', '/teacher-panel/courses',
                 '/teacher-panel/students', '/teacher-panel/assignments',
                 '/teacher-panel/questions', '/teacher-panel/revenue'):
        response = client.get(path)
        assert response.status_code == 200, path
    assert 'دوره تست' in client.get('/teacher-panel/courses').text
    assert client.get(f'/teacher-panel/courses/{course_id}/students').status_code == 200
