# -*- coding: utf-8 -*-
"""تست گواهینامه — تکمیل دوره → صدور گواهی → استعلام."""
import re
from conftest import login
from models import db, User, Enrollment, Section, Lesson, Course, certificate_code


def _make_course_with_lessons(app):
    """یک دوره با ۳ جلسه می‌سازد و به دانشجوی دمو اختصاص می‌دهد."""
    with app.app_context():
        cat_id = 1
        course = Course(title='دوره گواهی تست', slug='cert-test', price=0,
                        category_id=cat_id, status='published')
        db.session.add(course)
        db.session.flush()
        sec = Section(course_id=course.id, title='بخش', sort=0)
        db.session.add(sec)
        db.session.flush()
        for i in range(3):
            db.session.add(Lesson(section_id=sec.id, title=f'جلسه {i+1}',
                                  video_type='direct', video_url='/static/video/sample.mp4',
                                  sort=i))
        db.session.commit()
        return course.id


def _enroll_demo(app, course_id):
    with app.app_context():
        u = User.query.filter_by(email='demo@test.ir').first()
        db.session.add(Enrollment(user_id=u.id, course_id=course_id))
        db.session.commit()
        return u.id


def test_certificate_requires_completion(app, client):
    """دوره ناتمام → گواهی صادر نمی‌شود (به صفحه یادگیری هدایت می‌شود)."""
    cid = _make_course_with_lessons(app)
    _enroll_demo(app, cid)
    login(client, 'demo@test.ir', 'demo123')
    r = client.get(f'/certificate/{cid}', follow_redirects=False)
    # ناتمام → به صفحه یادگیری برگردانده می‌شود
    assert r.status_code == 302


def test_certificate_issued_when_completed(app, client):
    """تکمیل همه جلسات → گواهی با کد رهگیری صادر می‌شود."""
    cid = _make_course_with_lessons(app)
    uid = _enroll_demo(app, cid)
    # کامل کردن همه جلسات
    with app.app_context():
        en = Enrollment.query.filter_by(user_id=uid, course_id=cid).first()
        lessons = [l.id for l in db.session.get(Course, cid).lessons]
        en.save_progress(lessons)
        assert en.is_completed
        db.session.commit()
    login(client, 'demo@test.ir', 'demo123')
    r = client.get(f'/certificate/{cid}')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'گواهینامه' in body or 'گواهی' in body


def test_certificate_code_deterministic(app):
    """کد رهگیری گواهی باید قطعی باشد (برای استعلام)."""
    with app.app_context():
        u = User.query.filter_by(email='demo@test.ir').first()
        c1 = certificate_code('course-slug', u.email, 42)
        c2 = certificate_code('course-slug', u.email, 42)
        assert c1 == c2
        assert c1.startswith('CRT-')


def test_verify_certificate_page(app, client):
    """صفحه استعلام گواهینامه عمومی است و فرم دارد."""
    r = client.get('/verify-certificate')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'code' in body or 'کد' in body
