# -*- coding: utf-8 -*-
"""تست‌های فاز ۱: تصحیح باگ‌های منطقی هسته، Cascade Relationships و گواهی‌های ابطال‌شده"""
import re
from conftest import login
from models import (db, User, Course, Category, Section, Lesson, LessonQuestion,
                    Quiz, QuizQuestion, QuizAttempt, CustomForm, CustomFormEntry,
                    Enrollment, certificate_code)


def _csrf(client, path):
    r = client.get(path)
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    return m.group(1) if m else 'test-token'


def _login_admin(client, app, email, password):
    r = client.get('/auth/login')
    tok = _csrf(client, '/auth/login')
    client.post('/auth/login', data={'_csrf_token': tok, 'email': email,
                                     'password': password}, follow_redirects=False)
    code2 = app.config.get('_TEST_AUTH_CODES', {}).get('admin-2fa')
    if code2:
        tok2 = _csrf(client, '/auth/admin-2fa')
        client.post('/auth/admin-2fa', data={'_csrf_token': tok2, 'code': code2},
                    follow_redirects=False)


def test_user_wallet_insufficient_balance(app, client):
    """کسر از کیف پول در صورت عدم کفایت موجودی باید ناموفق باشد و پیام خطا بدهد."""
    with app.app_context():
        admin = User(name='مدیر سیستم', email='admin_w1@test.ir', role='super_admin', is_active=True)
        admin.set_password('admin123')
        target = User(name='کاربر هدف', email='target_w1@test.ir', role='student', is_active=True, wallet_balance=10000)
        target.set_password('pass123')
        db.session.add_all([admin, target])
        db.session.commit()
        target_id = target.id

    _login_admin(client, app, 'admin_w1@test.ir', 'admin123')
    token = _csrf(client, f'/admin/users/{target_id}/profile')

    # تلاش برای کسر ۵۰ هزار تومان در حالی که موجودی ۱۰ هزار تومان است
    res = client.post(f'/admin/users/{target_id}/wallet', data={
        '_csrf_token': token,
        'action': 'deduct',
        'amount': 50000,
        'note': 'جریمه تست',
    }, follow_redirects=True)

    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert 'کمتر از مبلغ' in body or 'خطا' in body

    with app.app_context():
        u = db.session.get(User, target_id)
        assert u.wallet_balance == 10000


def test_user_wallet_sufficient_balance(app, client):
    """کسر از کیف پول با موجودی کافی باید موفق باشد."""
    with app.app_context():
        admin = User(name='مدیر سیستم', email='admin_w2@test.ir', role='super_admin', is_active=True)
        admin.set_password('admin123')
        target = User(name='کاربر هدف', email='target_w2@test.ir', role='student', is_active=True, wallet_balance=50000)
        target.set_password('pass123')
        db.session.add_all([admin, target])
        db.session.commit()
        target_id = target.id

    _login_admin(client, app, 'admin_w2@test.ir', 'admin123')
    token = _csrf(client, f'/admin/users/{target_id}/profile')

    res = client.post(f'/admin/users/{target_id}/wallet', data={
        '_csrf_token': token,
        'action': 'deduct',
        'amount': 20000,
        'note': 'کسر تست',
    }, follow_redirects=True)

    assert res.status_code == 200
    with app.app_context():
        u = db.session.get(User, target_id)
        assert u.wallet_balance == 30000


def test_cascade_delete_lesson_questions(app):
    """حذف جلسه باید پرسش‌های وابسته را پاک کند بدون ایجاد خطای دیتابیس."""
    with app.app_context():
        cat = Category.query.first()
        course = Course(title='دوره کسکید', slug='cascade-course', category_id=cat.id, price=0, status='published')
        db.session.add(course)
        db.session.flush()
        sec = Section(course_id=course.id, title='سکشن ۱')
        db.session.add(sec)
        db.session.flush()
        lesson = Lesson(section_id=sec.id, title='جلسه ۱')
        db.session.add(lesson)
        db.session.flush()
        user = User.query.filter_by(email='demo@test.ir').first()
        lq = LessonQuestion(lesson_id=lesson.id, user_id=user.id, question='آیا این سوال حذف می‌شود؟')
        db.session.add(lq)
        db.session.commit()

        lid = lesson.id
        db.session.delete(lesson)
        db.session.commit()

        assert LessonQuestion.query.filter_by(lesson_id=lid).count() == 0


def test_co_teacher_percent_cap(app):
    """مجموع سهم مدرسین همکار نباید از ۱۰۰٪ استخر درآمد تجاوز کند."""
    with app.app_context():
        from models import CourseTeacher
        cat = Category.query.first()
        main_t = User(name='مدرس اصلی', email='main_t@test.ir', role='teacher', is_active=True)
        co_t1 = User(name='مدرس کمکی ۱', email='co1@test.ir', role='teacher', is_active=True)
        co_t2 = User(name='مدرس کمکی ۲', email='co2@test.ir', role='teacher', is_active=True)
        db.session.add_all([main_t, co_t1, co_t2])
        db.session.commit()

        course = Course(title='دوره مشترک', slug='co-course', category_id=cat.id, price=1000000,
                        teacher_id=main_t.id, revenue_percent=50, status='published')
        db.session.add(course)
        db.session.flush()

        # مدرسین کمکی هر کدام ۶۰٪ سهم خواسته‌اند (جمعاً ۱۲۰٪)
        db.session.add(CourseTeacher(course_id=course.id, teacher_id=co_t1.id, share_percent=60))
        db.session.add(CourseTeacher(course_id=course.id, teacher_id=co_t2.id, share_percent=60))
        db.session.commit()

        sold = 1000000
        # استخر ۵۰٪ = ۵۰۰,۰۰۰ تومان
        # با نرمال‌سازی به ۱۰۰٪، هر کدام ۵۰٪ استخر (۲۵۰,۰۰۰ تومان) می‌گیرند
        share_co1 = course.teacher_share_amount(co_t1.id, sold)
        share_co2 = course.teacher_share_amount(co_t2.id, sold)
        share_main = course.teacher_share_amount(main_t.id, sold)

        assert share_co1 + share_co2 <= 500000
        assert share_main == 0
        assert share_co1 == 250000
        assert share_co2 == 250000


def test_revoked_certificate_verification(app, client):
    """استعلام گواهی باطل‌شده باید وضعیت ابطال را صریحاً نشان دهد."""
    with app.app_context():
        admin = User(name='مدیر سیستم', email='admin_cert@test.ir', role='super_admin', is_active=True)
        admin.set_password('admin123')
        student = User.query.filter_by(email='demo@test.ir').first()
        cat = Category.query.first()
        course = Course(title='دوره گواهی ابطالی', slug='revoked-cert-course', category_id=cat.id, price=0, status='published')
        db.session.add_all([admin, course])
        db.session.flush()
        en = Enrollment(user_id=student.id, course_id=course.id, completed_at=__import__('models').utcnow())
        db.session.add(en)
        db.session.commit()
        eid = en.id
        code = certificate_code(course.slug, student.email, en.id)

    token = _csrf(client, '/verify-certificate')

    # قبل از ابطال: استعلام معتبر است
    res = client.post('/verify-certificate', data={'code': code, '_csrf_token': token})
    assert 'تایید شد' in res.get_data(as_text=True)

    # ابطال توسط مدیر
    _login_admin(client, app, 'admin_cert@test.ir', 'admin123')
    admin_token = _csrf(client, '/admin/certificates')
    r_revoke = client.post(f'/admin/certificates/{eid}/revoke', data={'_csrf_token': admin_token}, follow_redirects=True)
    assert r_revoke.status_code == 200

    # خروج یا استعلام به عنوان مهمان
    client.get('/auth/logout')
    verify_token = _csrf(client, '/verify-certificate')
    res_after = client.post('/verify-certificate', data={'code': code, '_csrf_token': verify_token})
    body = res_after.get_data(as_text=True)
    assert 'باطل' in body or 'لغو' in body
