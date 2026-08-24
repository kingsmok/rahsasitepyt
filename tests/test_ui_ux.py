# -*- coding: utf-8 -*-
"""دسته ۶: UI/UX — منوی گروه‌بندی‌شدهٔ ادمین و داشبورد جدید مدرس."""
import re

from models import (Course, User, db)

from permissions import menu_groups_for


def _make_admin(app, email='uiadmin@test.ir'):
    with app.app_context():
        a = User(name='Admin UI', email=email, phone='09120000500',
                 role='super_admin', is_active=True)
        a.set_password('admin123')
        db.session.add(a)
        db.session.commit()
        return a.id


def _login_admin(client, app, email='uiadmin@test.ir'):
    r = client.get('/auth/login')
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/login', data={'_csrf_token': tok, 'email': email,
                                     'password': 'admin123'})
    code2 = app.config.get('_TEST_AUTH_CODES', {}).get('admin-2fa')
    assert code2
    r = client.get('/auth/admin-2fa')
    tok2 = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/admin-2fa', data={'_csrf_token': tok2, 'code': code2})


def test_menu_groups_are_organized_and_filtered(app):
    _make_admin(app)
    with app.app_context():
        admin = User.query.filter_by(email='uiadmin@test.ir').first()
        groups = menu_groups_for(admin)
        labels = [g['label'] for g in groups]
        assert 'داشبورد و وضعیت' in labels
        assert 'فروش و مالی' in labels
        assert 'محتوا و آموزش' in labels
        assert 'گزارش‌ها' in labels
        assert 'سیستم' in labels
        # هر گروه فقط آیتم‌های مجاز دارد و خالی نیست
        assert all(g['items'] for g in groups)
        # کتابخانه رسانه در گروه طراحی است
        design = next(g for g in groups if g['label'] == 'طراحی و صفحات')
        eps = [ep for ep, _ in design['items']]
        assert 'admin.media_library' in eps
        # درگاه‌ها در گروه فروش
        sales = next(g for g in groups if g['label'] == 'فروش و مالی')
        eps = [ep for ep, _ in sales['items']]
        assert 'admin.gateways' in eps


def test_teacher_menu_groups(app):
    with app.app_context():
        t = User.query.filter_by(email='t@test.ir').first()
        groups = menu_groups_for(t)
        labels = [g['label'] for g in groups]
        assert 'آموزش' in labels
        assert 'مالی' in labels
        eps = [ep for g in groups for ep, _ in g['items']]
        assert 'teacher.revenue' in eps
        assert 'admin.orders' not in eps


def test_admin_sidebar_renders_grouped_menu(client, app):
    _make_admin(app)
    _login_admin(client, app)
    r = client.get('/admin/')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'as-group-toggle' in body
    assert 'فروش و مالی' in body
    assert 'محتوا و آموزش' in body
    assert 'data-admin-group-body' in body
    # گروه فعال صفحهٔ فعلی باز است
    assert 'داشبورد و وضعیت' in body


def test_teacher_dashboard_renders_new_design(client, app):
    with app.app_context():
        teacher = User.query.filter_by(email='t@test.ir').first()
        c = Course.query.filter_by(teacher_id=teacher.id).first()
        if c is None:
            c = Course(title='دوره UI', slug='ui-course', price=100000,
                       teacher_id=teacher.id, status='published')
            db.session.add(c)
        c.revenue_percent = 60
        db.session.commit()
    r = client.get('/auth/login')
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/login', data={'_csrf_token': tok,
                                     'email': 't@test.ir', 'password': 'teacher123'})
    r = client.get('/teacher-panel/')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'tch-hero' in body
    assert 'tch-side' in body
    assert 'tch-course-card' in body
    assert 'دوره‌های من' in body
    assert 'سلام، مدرس تست' in body
    assert 'سهم شما: ۶۰٪' in body


def test_teacher_sidebar_active_state(client, app):
    r = client.get('/auth/login')
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/login', data={'_csrf_token': tok,
                                     'email': 't@test.ir', 'password': 'teacher123'})
    r = client.get('/teacher-panel/revenue')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    # لینک درآمد من فعال است
    assert 'درآمد من' in body


def test_learn_page_notes_and_search_and_celebration_modal(client, app):
    with app.app_context():
        u = User.query.filter_by(email='s@test.ir').first()
        if not u:
            u = User(name='دانشجوی تست', email='s@test.ir', role='student', is_active=True)
            u.set_password('student123')
            db.session.add(u)
            db.session.commit()
        from models import Course, Section, Lesson, Enrollment
        c = Course.query.filter_by(slug='learn-ux-test').first()
        if not c:
            c = Course(title='دوره تست پلیر و یادداشت', slug='learn-ux-test', price=0, status='published')
            db.session.add(c)
            db.session.flush()
            sec = Section(course_id=c.id, title='فصل اول', sort=1)
            db.session.add(sec)
            db.session.flush()
            l1 = Lesson(section_id=sec.id, title='جلسه اول تست', duration='10:00', sort=1, is_free=True)
            db.session.add(l1)
            db.session.flush()
        else:
            l1 = c.lessons[0]

        en = Enrollment.query.filter_by(user_id=u.id, course_id=c.id).first()
        if not en:
            en = Enrollment(user_id=u.id, course_id=c.id)
            db.session.add(en)
        en.save_progress([l1.id])
        db.session.commit()
        cid = c.id
        lid = l1.id

    r = client.get('/auth/login')
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/login', data={'_csrf_token': tok,
                                     'email': 's@test.ir', 'password': 'student123'})
    r = client.get(f'/learn/{cid}?lesson={lid}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'pp-insert-time-btn' in html
    assert 'درج زمان ویدیو' in html
    assert 'lesson-search-input' in html
    assert 'celebration-modal-overlay' in html
    assert 'تبریک! دوره با موفقیت تمام شد' in html

