# -*- coding: utf-8 -*-
"""آزمون‌های امکانات اسکریپت آموزینو و کلیدهای لایسنس اسپات پلیر"""
import pytest
from conftest import login
from test_admin_panel import _login_admin_2fa, _make_admin
from models import db, User, Course, Category, Enrollment

def test_amoozino_homepage_design(client, app):
    with app.app_context():
        _make_admin(app)
        _login_admin_2fa(client, app, 'admint@test.ir', 'admin123')
        
        r = client.get('/?design=amoozino')
        assert r.status_code == 200
        assert 'آموزینو' in r.get_data(as_text=True)
        assert 'خدمات و دسته‌بندی‌های تخصصی' in r.get_data(as_text=True)

def test_student_license_keys_page(client, app):
    with app.app_context():
        cat = Category(name='برنامه‌نویسی', slug='programming-amz')
        db.session.add(cat)
        db.session.commit()

        course = Course(title='دوره تخصصی پایتون آموزینو', slug='amz-python-course',
                        price=500000, category_id=cat.id, status='published')
        student = User(name='Ali Rezaei', email='ali_amz@test.ir', role='student', national_code='0013542419')
        student.set_password('pass123')
        db.session.add_all([course, student])
        db.session.commit()

        enr = Enrollment(user_id=student.id, course_id=course.id)
        db.session.add(enr)
        db.session.commit()

        login(client, 'ali_amz@test.ir', 'pass123')

def test_course_prerequisite_display(client, app):
    with app.app_context():
        cat = Category(name='وب', slug='web-prereq')
        db.session.add(cat)
        db.session.commit()

        c1 = Course(title='پایتون مقدماتی', slug='python-basic', price=0, category_id=cat.id, status='published')
        db.session.add(c1)
        db.session.commit()

        c2 = Course(title='جنگو پیشرفته', slug='django-advanced', price=800000,
                    category_id=cat.id, prerequisite_id=c1.id, status='published')
        db.session.add(c2)
        db.session.commit()

        r = client.get('/course/django-advanced')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'پیش‌نیاز پیشنهادی این دوره' in html
        assert 'پایتون مقدماتی' in html

def test_meeting_booking_flow(client, app):
    with app.app_context():
        from models import MeetingBooking
        teacher = User(name='استاد حسینی', email='teacher_mb@test.ir', role='teacher', national_code='0013542419')
        teacher.set_password('pass123')
        student = User(name='دانشجو کریمی', email='student_mb@test.ir', role='student', national_code='0013542427')
        student.set_password('pass123')
        db.session.add_all([teacher, student])
        db.session.commit()

        mb = MeetingBooking(teacher_id=teacher.id, title='جلسه رفع اشکال هوش مصنوعی',
                            meeting_date='1405/06/20', start_time='17:00', duration_min=60,
                            price=0, status='available')
        db.session.add(mb)
        db.session.commit()

        # دانشجو وارد شده و جلسه را رزرو می‌کند
        login(client, 'student_mb@test.ir', 'pass123')
        # دریافت توکن CSRF
        r_page = client.get('/dashboard/meetings')
        import re
        m = re.search(r'name="_csrf_token" value="([^"]+)"', r_page.get_data(as_text=True))
        token = m.group(1) if m else ''

        r = client.post(f'/meeting/book/{mb.id}', data={'_csrf_token': token, 'notes': 'سوال درباره ماتریس‌ها'}, follow_redirects=True)
        assert r.status_code == 200
        assert 'جلسه مشاوره با موفقیت برای شما رزرو شد' in r.get_data(as_text=True)

        # بررسی رزرو شدن
        updated_mb = db.session.get(MeetingBooking, mb.id)
        assert updated_mb.status == 'booked'
        assert updated_mb.student_id == student.id


def test_live_sessions_and_status(client, app):
    with app.app_context():
        from models import LiveSession, utcnow
        from datetime import timedelta
        _now = utcnow()
        ls1 = LiveSession(title='وبینار زنده نقشه راه هوش مصنوعی',
                          starts_at=_now - timedelta(minutes=10),
                          duration_min=60, link='https://skyroom.online/ch/ai')
        ls2 = LiveSession(title='کارگاه آینده شغلی پایتون',
                          starts_at=_now + timedelta(days=2),
                          duration_min=90, link='https://skyroom.online/ch/py')
        db.session.add_all([ls1, ls2])
        db.session.commit()

        r = client.get('/community/live')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'وبینار زنده نقشه راه هوش مصنوعی' in html
        assert 'کارگاه آینده شغلی پایتون' in html
        assert '🔴 زنده' in html or 'live-pulse-badge' in html


def test_leaderboard_podium_rendering(client, app):
    with app.app_context():
        u1 = User(name='نفر اول طلا', email='gold@test.ir', points=1500, streak=12, is_active=True)
        u1.set_password('pass123')
        u2 = User(name='نفر دوم نقره', email='silver@test.ir', points=1100, streak=7, is_active=True)
        u2.set_password('pass123')
        u3 = User(name='نفر سوم برنز', email='bronze@test.ir', points=800, streak=4, is_active=True)
        u3.set_password('pass123')
        db.session.add_all([u1, u2, u3])
        db.session.commit()

        login(client, 'silver@test.ir', 'pass123')
        r = client.get('/leaderboard')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'جدول برترین‌های یادگیری' in html
        assert 'نفر اول طلا' in html
        assert 'نفر دوم نقره' in html
        assert 'نفر سوم برنز' in html
        assert 'قهرمان دوره' in html
        assert 'my-rank-banner' in html

