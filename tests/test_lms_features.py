# -*- coding: utf-8 -*-
"""دسته ۴: انواع برگزاری ۴تایی، سهم درآمد مدرس، قفل اقساطی اسنپ‌پی/دیجی‌پی."""
import re

from models import (Course, CourseTeacher, Enrollment, Installment, Lesson,
                    Order, OrderItem, Section, Setting, User, db)

from conftest import login


def _make_admin(app, email='lmsadmin@test.ir'):
    with app.app_context():
        a = User(name='Admin LMS', email=email, phone='09120000300',
                 role='super_admin', is_active=True)
        a.set_password('admin123')
        db.session.add(a)
        db.session.commit()
        return a.id


def _login_admin(client, app, email='lmsadmin@test.ir'):
    r = client.get('/auth/login')
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/login', data={'_csrf_token': tok, 'email': email,
                                     'password': 'admin123'})
    code2 = app.config.get('_TEST_AUTH_CODES', {}).get('admin-2fa')
    assert code2
    r = client.get('/auth/admin-2fa')
    tok2 = re.search(r'name="_csrf_token" value="([^"]+)"', r.text).group(1)
    client.post('/auth/admin-2fa', data={'_csrf_token': tok2, 'code': code2})


def _csrf(client, path):
    r = client.get(path)
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    return m.group(1) if m else ''


# ═══════════════ انواع برگزاری ۴تایی ═══════════════

def test_delivery_labels_four_types(app):
    with app.app_context():
        c = Course.query.first()
        c.delivery_type = 'inperson'
        db.session.commit()
        assert c.delivery_label == 'حضوری'
        assert c.is_attendance_based is True
        c.delivery_type = 'offline'
        assert c.delivery_label == 'آفلاین'
        assert c.is_attendance_based is False
        c.delivery_type = 'online'
        assert c.delivery_label == 'آنلاین'
        assert c.is_attendance_based is False
        c.delivery_type = 'hybrid'
        assert c.delivery_label == 'ترکیبی'
        assert c.is_attendance_based is True


def test_admin_course_form_saves_four_types_and_revenue(client, app):
    _make_admin(app)
    _login_admin(client, app)
    tok = _csrf(client, '/admin/courses/new')
    r = client.post('/admin/courses/new', data={
        '_csrf_token': tok, 'title': 'دوره حضوری جدید', 'price': '100000',
        'discount_price': '', 'level': 'مقدماتی', 'duration_hours': '10',
        'delivery_type': 'inperson', 'revenue_percent': '70',
        'unlock_per_installment': '3',
        'attendance_required_percent': '80',
        'category_id': '', 'teacher_id': '', 'image': 'course-placeholder.webp',
        'status': 'draft',
    }, follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        c = Course.query.filter_by(title='دوره حضوری جدید').first()
        assert c is not None
        assert c.delivery_type == 'inperson'
        assert c.revenue_percent == 70
        assert c.unlock_per_installment == 3
        assert c.delivery_label == 'حضوری'
        assert c.teacher_percent() == 70


def test_admin_course_form_saves_co_teachers_with_shares(client, app):
    _make_admin(app)
    _login_admin(client, app)
    with app.app_context():
        t1 = User.query.filter_by(email='t@test.ir').first()
        t2 = User(name='مدرس کمکی', email='co@test.ir', phone='09120000301',
                  role='teacher', is_active=True)
        t2.set_password('teacher123')
        db.session.add(t2)
        db.session.commit()
        t1_id, t2_id = t1.id, t2.id
    tok = _csrf(client, '/admin/courses/new')
    r = client.post('/admin/courses/new', data={
        '_csrf_token': tok, 'title': 'دوره با مدرس کمکی', 'price': '100000',
        'discount_price': '', 'level': 'مقدماتی', 'duration_hours': '10',
        'delivery_type': 'online', 'revenue_percent': '60',
        'unlock_per_installment': '0',
        'teacher_id': str(t1_id),
        'co_teacher_ids': [str(t2_id)],
        'co_share_' + str(t2_id): '25',
        'category_id': '', 'image': 'course-placeholder.webp',
        'status': 'draft',
    }, follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        c = Course.query.filter_by(title='دوره با مدرس کمکی').first()
        assert c is not None
        link = CourseTeacher.query.filter_by(course_id=c.id, teacher_id=t2_id).first()
        assert link is not None
        assert link.share_percent == 25
        # سهم مدرس اصلی = ۶۰٪ استخر منهای ۲۵٪ کمکی
        sold = 100000
        main_share = c.teacher_share_amount(t1_id, sold)
        co_share = c.teacher_share_amount(t2_id, sold)
        assert co_share == round(100000 * 0.60 * 0.25)
        assert main_share == round(100000 * 0.60) - co_share
        # مدرس غیرمرتبط سهم ندارد
        assert c.teacher_share_amount(99999, sold) == 0


def test_teacher_default_share_setting_fallback(app):
    with app.app_context():
        c = Course.query.first()
        c.revenue_percent = None
        db.session.commit()
        st = db.session.get(Setting, 'teacher_default_share')
        if st:
            st.value = '40'
        else:
            db.session.add(Setting(key='teacher_default_share', value='40'))
        db.session.commit()
        assert c.teacher_percent() == 40
        # بدون تنظیم → ۵۰
        db.session.delete(st or db.session.get(Setting, 'teacher_default_share'))
        db.session.commit()
        assert c.teacher_percent() == 50


# ═══════════════ قفل اقساطی — باز شدن جلسات با پرداخت هر قسط ═══════════════

def _installment_fixture(app, per=2):
    """دوره ۶ جلسه‌ای با قفل اقساطی + ثبت‌نام + سفارش ۳ قسطی."""
    with app.app_context():
        student = User.query.filter_by(email='demo@test.ir').first()
        teacher = User.query.filter_by(email='t@test.ir').first()
        c = Course(title='دوره اقساطی', slug='installment-course', price=300000,
                   teacher_id=teacher.id, status='published',
                   unlock_per_installment=per)
        db.session.add(c)
        db.session.flush()
        s1 = Section(course_id=c.id, title='بخش ۱', sort=1)
        s2 = Section(course_id=c.id, title='بخش ۲', sort=2)
        db.session.add_all([s1, s2])
        db.session.flush()
        for i in range(6):
            db.session.add(Lesson(section_id=s1.id if i < 3 else s2.id,
                                  title='جلسه {}'.format(i + 1),
                                  video_type='none', sort=i + 1))
        order = Order(code='INST-ORDER-1', user_id=student.id, total=300000,
                      final_total=300000, status='paid', gateway='snapppay',
                      installment_count=3)
        db.session.add(order)
        db.session.flush()
        for num in range(1, 4):
            db.session.add(Installment(order_id=order.id, number=num,
                                       amount=100000))
        db.session.add(OrderItem(order_id=order.id, course_id=c.id,
                                 price=300000, quantity=1))
        db.session.add(Enrollment(user_id=student.id, course_id=c.id,
                                  order_id=order.id))
        db.session.commit()
        return c.id, order.id


def test_installment_unlock_limit_grows_with_paid_installments(app):
    cid, oid = _installment_fixture(app, per=2)
    with app.app_context():
        e = Enrollment.query.filter_by(course_id=cid).first()
        # هیچ قسطی جدا ثبت نشده → قسط اول (تسویه) = ۱ قسط پرداخت‌شده
        assert e.unlocked_lesson_limit() == 2
        # ثبت پرداخت قسط ۲ → ۴ جلسه باز
        inst2 = Installment.query.filter_by(order_id=oid, number=2).first()
        inst2.status = 'paid'
        db.session.commit()
        db.session.refresh(e)
        assert e.unlocked_lesson_limit() == 4
        # قسط ۳ هم پرداخت → همه باز
        inst3 = Installment.query.filter_by(order_id=oid, number=3).first()
        inst3.status = 'paid'
        db.session.commit()
        db.session.refresh(e)
        assert e.unlocked_lesson_limit() == 0


def test_learn_page_locks_lessons_beyond_installment_limit(client, app):
    cid, oid = _installment_fixture(app, per=2)
    login(client, 'demo@test.ir', 'demo123')
    # جلسه ۱ و ۲ باید قابل مشاهده باشند؛ جلسه ۳ قفل
    r = client.get('/learn/{}'.format(cid))
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'قسط بعدی' in body  # نشانگر قفل اقساطی
    with app.app_context():
        e = Enrollment.query.filter_by(course_id=cid).first()
        lessons = e.course.lessons
        lesson3_id = lessons[2].id
    # تلاش مستقیم برای درس قفل‌شده → برگشت به صفحه یادگیری
    r = client.get('/learn/{}?lesson={}'.format(cid, lesson3_id),
                   follow_redirects=False)
    assert r.status_code == 302
    # درس داخل سقف → ۲۰۰
    lesson1_id = lessons[0].id
    r = client.get('/learn/{}?lesson={}'.format(cid, lesson1_id))
    assert r.status_code == 200


def test_complete_lesson_blocked_for_locked_installment_lesson(client, app):
    cid, oid = _installment_fixture(app, per=2)
    login(client, 'demo@test.ir', 'demo123')
    with app.app_context():
        lessons = db.session.get(Course, cid).lessons
        locked_id = lessons[4].id  # جلسه ۵ — خارج از سقف
    page = client.get('/learn/{}'.format(cid))
    tok = re.search(r'name="_csrf_token" value="([^"]+)"', page.text).group(1)
    r = client.post('/learn/{}/complete/{}'.format(cid, locked_id), data={
        '_csrf_token': tok,
    })
    assert r.status_code == 403


def test_admin_marks_installment_paid_and_unlocks(client, app):
    cid, oid = _installment_fixture(app, per=2)
    _make_admin(app)
    _login_admin(client, app)
    with app.app_context():
        inst2 = Installment.query.filter_by(order_id=oid, number=2).first()
        iid = inst2.id
        order = db.session.get(Order, oid)
        assert order.status == 'paid'
    tok = _csrf(client, '/admin/installments')
    r = client.post('/admin/installments/{}/mark-paid'.format(iid), data={
        '_csrf_token': tok,
    }, follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        inst2 = db.session.get(Installment, iid)
        assert inst2.status == 'paid'
        e = Enrollment.query.filter_by(course_id=cid).first()
        # قسط ۲ ثبت شد → ۲×۲=۴ جلسه باز
        assert e.unlocked_lesson_limit() == 4
    # صفحه اقساط ادمین دکمه را نشان می‌دهد
    r = client.get('/admin/installments')
    assert 'ثبت پرداخت' in r.get_data(as_text=True)


def test_unlock_notice_in_order_for_bnpl_page(app):
    cid, oid = _installment_fixture(app, per=3)
    with app.app_context():
        order = db.session.get(Order, oid)
        notice = order.unlock_notice()
        assert '۳' in notice and 'جلسه' in notice


# ═══════════════ درگاه‌های اقساطی اسنپ‌پی/دیجی‌پی ═══════════════

def test_snapppay_and_digipay_registered_as_installment_providers():
    from gateways import GATEWAY_MAP, INSTALLMENT_PROVIDERS, gateway_plan
    assert 'snapppay' in GATEWAY_MAP
    assert 'digipay' in GATEWAY_MAP
    assert 'snapppay' in INSTALLMENT_PROVIDERS
    assert 'digipay' in INSTALLMENT_PROVIDERS
    assert GATEWAY_MAP['snapppay']['kind'] == 'installment'
    assert GATEWAY_MAP['digipay']['kind'] == 'installment'
    snapp = gateway_plan('snapppay')
    digi = gateway_plan('digipay')
    assert snapp['name'] == 'اسنپ‌پی'
    assert digi['name'] == 'دیجی‌پی'
    assert snapp['max_installments'] >= 2
    assert digi['max_installments'] >= 2
