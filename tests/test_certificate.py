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


def test_uncomplete_clears_completion_and_locked_post_is_blocked(app, client):
    cid = _make_course_with_lessons(app)
    uid = _enroll_demo(app, cid)
    with app.app_context():
        enrollment = Enrollment.query.filter_by(user_id=uid, course_id=cid).first()
        lessons = db.session.get(Course, cid).lessons
        enrollment.save_progress([lesson.id for lesson in lessons])
        enrollment.completed_at = __import__('models').utcnow()
        lessons[1].release_days = 30
        db.session.commit()
        first_id, locked_id = lessons[0].id, lessons[1].id
    login(client, 'demo@test.ir', 'demo123')
    page = client.get(f'/learn/{cid}?lesson={first_id}')
    token = re.search(r'name="_csrf_token" value="([^\"]+)"', page.text).group(1)
    undone = client.post(f'/learn/{cid}/complete/{first_id}', data={
        '_csrf_token': token, 'action': 'uncomplete'
    })
    assert undone.status_code == 302
    with app.app_context():
        assert Enrollment.query.filter_by(user_id=uid, course_id=cid).first().completed_at is None
    blocked = client.post(f'/learn/{cid}/complete/{locked_id}', data={
        '_csrf_token': token, 'action': 'complete'
    })
    assert blocked.status_code == 403


def test_local_video_uses_protected_range_stream(app, client):
    cid = _make_course_with_lessons(app)
    _enroll_demo(app, cid)
    login(client, 'demo@test.ir', 'demo123')
    page = client.get(f'/learn/{cid}')
    import html
    match = re.search(r'src="([^"]*/stream/lesson/[^"]+)"', page.text)
    assert match, 'ویدیوی محلی باید URL امضاشده داشته باشد'
    stream_url = html.unescape(match.group(1))
    response = client.get(stream_url, headers={'Range': 'bytes=0-99'})
    assert response.status_code in (200, 206)
    assert response.headers.get('Cache-Control', '').startswith('private')


def test_offline_course_can_be_completed_by_teacher(app, client):
    """مدرس بتواند تکمیل دوره حضوری را ثبت کند و گواهی فعال شود."""
    from models import Enrollment, Course, User, db
    with app.app_context():
        course = Course.query.filter_by(slug='test-course').first()
        course.delivery_type = 'offline'
        student = User.query.filter_by(email='demo@test.ir').first()
        enrollment = Enrollment(user_id=student.id, course_id=course.id)
        db.session.add(enrollment)
        db.session.commit()
        eid, cid = enrollment.id, course.id
    login(client, 't@test.ir', 'teacher123')
    response = client.get(f'/teacher-panel/courses/{cid}/students')
    token = re.search(r'name="_csrf_token" value="([^\"]+)"', response.text).group(1)
    done = client.post(f'/teacher-panel/enrollments/{eid}/completion', data={
        '_csrf_token': token, 'action': 'complete'
    }, follow_redirects=False)
    assert done.status_code == 302
    with app.app_context():
        enrollment = db.session.get(Enrollment, eid)
        assert enrollment.completed_at is not None and enrollment.is_completed


def test_teacher_attendance_flow(app, client):
    from models import Enrollment, Course, User, CourseMeeting, AttendanceRecord, db
    with app.app_context():
        course = Course.query.filter_by(slug='test-course').first()
        course.delivery_type = 'offline'
        student = User.query.filter_by(email='demo@test.ir').first()
        enrollment = Enrollment(user_id=student.id, course_id=course.id)
        db.session.add(enrollment)
        db.session.commit()
        cid, eid = course.id, enrollment.id
    login(client, 't@test.ir', 'teacher123')
    token = re.search(r'name="_csrf_token" value="([^\"]+)"',
                      client.get(f'/teacher-panel/courses/{cid}/attendance').text).group(1)
    created = client.post(f'/teacher-panel/courses/{cid}/attendance', data={
        '_csrf_token': token, 'title': 'جلسه حضوری اول',
        'starts_at': '2026-08-15T10:00', 'duration_min': '90'
    }, follow_redirects=False)
    assert created.status_code == 302
    with app.app_context():
        meeting_id = CourseMeeting.query.filter_by(course_id=cid).first().id
    mark_page = client.get(f'/teacher-panel/attendance/{meeting_id}')
    mark_token = re.search(r'name="_csrf_token" value="([^\"]+)"', mark_page.text).group(1)
    saved = client.post(f'/teacher-panel/attendance/{meeting_id}', data={
        '_csrf_token': mark_token, f'status_{eid}': 'present', 'close': '1'
    }, follow_redirects=False)
    assert saved.status_code == 302
    with app.app_context():
        record = AttendanceRecord.query.filter_by(enrollment_id=eid).first()
        assert record and record.status == 'present'
        assert db.session.get(CourseMeeting, meeting_id).is_closed is True


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
