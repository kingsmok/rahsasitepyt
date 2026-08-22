# -*- coding: utf-8 -*-
"""تست رگرسیون: حذف ایمن دوره، گارد enrollment یتیم، و رزولوشن URL تصاویر."""
import os
import re
import uuid
from conftest import csrf_headers, login
from models import db, User, Course, Enrollment, Bundle, BlogPost


def _make_media_file(name):
    """ساخت فایل واقعی در کتابخانه رسانه تا resolve_image_url آن را بپذیرد."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(root, 'static', 'uploads', 'media')
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + b'0' * 32)
    return path


def _cleanup_media_file(name):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, 'static', 'uploads', 'media', name)
    try:
        os.remove(path)
    except OSError:
        pass


def _csrf(client, path):
    r = client.get(path)
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    return m.group(1) if m else 'test-token'


def test_course_delete_blocked_when_enrolled(client, app):
    """حذف دورهٔ دارای ثبت‌نام باید مسدود شود (ضد دادهٔ یتیم)."""
    with app.app_context():
        course = Course.query.filter_by(slug='test-course').first()
        s = User.query.filter_by(email='demo@test.ir').first()
        if not Enrollment.query.filter_by(course_id=course.id, user_id=s.id).first():
            db.session.add(Enrollment(course_id=course.id, user_id=s.id))
            db.session.commit()
        cid = course.id
    a = User(name='Admin', email='admdel@test.ir', phone='09120000121',
             role='admin', is_active=True)
    with app.app_context():
        a.set_password('admin123')
        db.session.add(a)
        db.session.commit()
    login(client, 'admdel@test.ir', 'admin123')
    # رد 2FA
    from tests.test_admin_panel import _login_admin_2fa
    _login_admin_2fa(client, app, 'admdel@test.ir', 'admin123')
    tok = _csrf(client, '/admin/courses')
    r = client.post(f'/admin/courses/{cid}/delete', data={'_csrf_token': tok},
                    follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert db.session.get(Course, cid) is not None  # هنوز وجود دارد


def test_orphaned_enrollment_percent_does_not_crash(app):
    """Enrollment یتیم (دوره حذف‌شدهٔ نصب قدیمی) نباید 500 بدهد."""
    with app.app_context():
        u = User(name='x', email='orphan@test.ir', phone='09120000122', role='student')
        db.session.add(u)
        db.session.flush()
        e = Enrollment(user_id=u.id, course_id=999999)  # دوره ناموجود
        db.session.add(e)
        db.session.commit()
        assert e.course is None
        assert e.percent == 0
        assert e.is_completed is False
        assert e.unlocked_lesson_limit() == 0


def test_bundle_image_url_resolves_media_library(app):
    """تصویر باندل از کتابخانه رسانه باید به /static/uploads/media/... حل شود."""
    name = 'm_' + uuid.uuid4().hex[:8] + '.png'
    _make_media_file(name)
    try:
        with app.app_context():
            b = Bundle(title='باندل', slug='bundle-x', image='uploads/media/' + name,
                       price=1000)
            db.session.add(b)
            db.session.commit()
            assert b.image_url == '/static/uploads/media/' + name
    finally:
        _cleanup_media_file(name)


def test_post_lite_image_url_resolves_media_library(app):
    """PostLite باید تصویر کتابخانه رسانه را درست حل کند (نه پیشوند /static/img/)."""
    from cache_safe import post_lite
    name = 'm_' + uuid.uuid4().hex[:8] + '.png'
    _make_media_file(name)
    try:
        with app.app_context():
            p = BlogPost(title='پست', slug='post-x', image='uploads/media/' + name)
            db.session.add(p)
            db.session.commit()
            lite = post_lite(p)
            assert lite.image_url == '/static/uploads/media/' + name
    finally:
        _cleanup_media_file(name)


def test_cart_renders_media_library_course_cover(client, app):
    """کاور دورهٔ انتخاب‌شده از کتابخانه رسانه در سبد باید درست رندر شود."""
    name = 'm_' + uuid.uuid4().hex[:8] + '.png'
    _make_media_file(name)
    try:
        with app.app_context():
            course = Course.query.filter_by(slug='test-course').first()
            course.image = 'uploads/media/' + name
            db.session.commit()
        client.get('/auth/logout')
        # افزودن دوره به سبد (API)
        r = client.post('/api/cart/add', json={'course_id': 1},
                        headers=csrf_headers(client))
        assert r.status_code == 200
        html = client.get('/cart').get_data(as_text=True)
        assert '/static/uploads/media/' + name in html
        assert '/static/img/uploads/media/' + name not in html
    finally:
        _cleanup_media_file(name)
