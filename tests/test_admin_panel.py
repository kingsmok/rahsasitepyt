# -*- coding: utf-8 -*-
"""تست پنل ادمین، پنل معلم و انجمن — CRUD و کنترل دسترسی."""
import re
from conftest import login
from models import db, User, Enrollment, Ticket, ForumTopic


def _make_admin(app):
    with app.app_context():
        a = User(name='Admin', email='admint@test.ir', phone='09120000111',
                 role='admin', is_active=True)
        a.set_password('admin123')
        db.session.add(a)
        db.session.commit()
        return a.id


def _make_teacher(app):
    with app.app_context():
        t = User.query.filter_by(email='t@test.ir').first()
        if not t:
            t = User(name='مدرس', email='t@test.ir', phone='09120000999',
                     role='teacher', is_active=True)
            t.set_password('teacher123')
            db.session.add(t)
            db.session.commit()
        return t.id


def _make_enrolled_student(app):
    with app.app_context():
        s = User(name='دانشجو', email='st@test.ir', phone='09120000112',
                 role='student', is_active=True)
        s.set_password('student123')
        db.session.add(s)
        db.session.flush()
        db.session.add(Enrollment(user_id=s.id, course_id=1))
        db.session.commit()
        return s.id


def _csrf(client, path):
    r = client.get(path)
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    return m.group(1) if m else 'test-token'


# ---------------------------------------------------------------
# دسترسی: دانشجو نباید به پنل ادمین/معلم برود
# ---------------------------------------------------------------
def test_student_denied_admin_and_teacher(client, app):
    login(client, 'demo@test.ir', 'demo123')
    assert client.get('/admin/').status_code == 302
    assert client.get('/teacher-panel/').status_code in (302, 403)


def test_guest_redirected_from_admin(client, app):
    r = client.get('/admin/')
    assert r.status_code == 302
    assert '/auth/login' in r.headers.get('Location', '') or r.status_code == 302


# ---------------------------------------------------------------
# پنل ادمین: صفحات اصلی رندر می‌شوند
# ---------------------------------------------------------------
def test_admin_pages_render(client, app):
    _make_admin(app)
    _login_admin_2fa(client, app, 'admint@test.ir', 'admin123')
    pages = ['/admin/', '/admin/go-live', '/admin/courses', '/admin/users', '/admin/orders',
             '/admin/blog', '/admin/tickets', '/admin/categories',
             '/admin/coupons', '/admin/quizzes', '/admin/designs',
             '/admin/gateways', '/admin/proofs', '/admin/pages']
    for p in pages:
        r = client.get(p)
        assert r.status_code == 200, f'{p} -> {r.status_code}'


def test_go_live_saves_without_reflecting_secrets(client, app):
    from models import Setting
    _make_admin(app)
    _login_admin_2fa(client, app, 'admint@test.ir', 'admin123')
    token = _csrf(client, '/admin/go-live')
    response = client.post('/admin/go-live', data={
        '_csrf_token': token, 'site_name': 'مجموعه واقعی',
        'site_desc': 'توضیح واقعی', 'email': 'info@example.ir',
        'idpay_api_key': 'VERY-SECRET-KEY', 'currency': 'تومان',
    }, follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Setting, 'idpay_api_key').value == 'VERY-SECRET-KEY'
    page = client.get('/admin/go-live')
    assert 'VERY-SECRET-KEY' not in page.text


def test_admin_can_create_category(client, app):
    _make_admin(app)
    _login_admin_2fa(client, app, 'admint@test.ir', 'admin123')
    tok = _csrf(client, '/admin/categories')
    r = client.post('/admin/categories', data={
        '_csrf_token': tok, 'action': 'add', 'name': 'دسته تست',
        'icon': '📘', 'color': '#123456', 'sort': '9',
    }, follow_redirects=False)
    assert r.status_code in (200, 302)
    with app.app_context():
        from models import Category
        c = Category.query.filter_by(name='دسته تست').first()
        assert c is not None


# ---------------------------------------------------------------
# پنل معلم: دسترسی و صفحات
# ---------------------------------------------------------------
def test_teacher_panel_pages(client, app):
    _make_teacher(app)
    login(client, 't@test.ir', 'teacher123')
    for p in ['/teacher-panel/', '/teacher-panel/courses',
              '/teacher-panel/students', '/teacher-panel/assignments',
              '/teacher-panel/questions', '/teacher-panel/revenue']:
        r = client.get(p)
        assert r.status_code == 200, f'{p} -> {r.status_code}'


def test_teacher_cannot_access_admin(client, app):
    _make_teacher(app)
    login(client, 't@test.ir', 'teacher123')
    assert client.get('/admin/').status_code == 302


# ---------------------------------------------------------------
# انجمن: دسترسی، ساخت تاپیک و ارسال پست
# ---------------------------------------------------------------
def test_community_requires_login(client, app):
    # انجمن (خواندن) عمومی است؛ پیام‌ها و لایو نیازمند لاگین
    r = client.get('/community/messages')
    assert r.status_code == 302


def test_community_pages_for_logged_in(client, app):
    login(client, 'demo@test.ir', 'demo123')
    for p in ['/community/', '/community/messages', '/community/live']:
        r = client.get(p)
        assert r.status_code == 200, f'{p} -> {r.status_code}'


def test_create_forum_topic(client, app):
    login(client, 'demo@test.ir', 'demo123')
    tok = _csrf(client, '/community/')
    r = client.post('/community/topic/new', data={
        '_csrf_token': tok, 'title': 'سوال درباره دوره', 'body': 'بدنه سوال تستی',
        'course_id': '1',
    }, follow_redirects=False)
    assert r.status_code in (200, 302)
    with app.app_context():
        t = ForumTopic.query.first()
        assert t is not None
        assert t.title == 'سوال درباره دوره'


# ---------------------------------------------------------------
# تیکت پشتیبانی: دانشجو می‌سازد، ادمین می‌بیند
# ---------------------------------------------------------------
def test_ticket_creation_and_admin_view(client, app):
    _make_admin(app)
    login(client, 'demo@test.ir', 'demo123')
    tok = _csrf(client, '/dashboard/tickets/new')
    r = client.post('/dashboard/tickets/new', data={
        '_csrf_token': tok, 'subject': 'پشتیبانی تست', 'body': 'متن تیکت',
        'category': 'عمومی', 'priority': 'normal',
    }, follow_redirects=False)
    assert r.status_code in (200, 302)
    with app.app_context():
        t = Ticket.query.filter_by(subject='پشتیبانی تست').first()
        assert t is not None
    # ادمین می‌بیند
    client.get('/auth/logout')
    _login_admin_2fa(client, app, 'admint@test.ir', 'admin123')
    r = client.get('/admin/tickets')
    assert r.status_code == 200


# ---------------------------------------------------------------
# لاگین ادمین با گذر از 2FA (کد از سشن خوانده می‌شود)
# ---------------------------------------------------------------
def _login_admin_2fa(client, app, email, password):
    """لاگین ادمین + رد کد دومرحله‌ای (که در سشن ذخیره شده)."""
    r = client.get('/auth/login')
    tok = _csrf(client, '/auth/login')
    r = client.post('/auth/login', data={'_csrf_token': tok, 'email': email,
                                         'password': password}, follow_redirects=False)
    # کد تست فقط در حافظه سرور است و هرگز داخل cookie session قرار نمی‌گیرد.
    code2 = app.config.get('_TEST_AUTH_CODES', {}).get('admin-2fa')
    assert code2, 'کد تست 2FA در حافظه سرور نیست'
    with client.session_transaction() as sess:
        assert 'admin_2fa' not in sess and 'admin_2fa_hash' in sess
    tok2 = _csrf(client, '/auth/admin-2fa')
    r = client.post('/auth/admin-2fa', data={'_csrf_token': tok2, 'code': code2},
                    follow_redirects=False)
    assert r.status_code == 302
    return r
