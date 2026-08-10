# -*- coding: utf-8 -*-
"""تست فروشگاه (سبد → سفارش → پرداخت sandbox → ثبت‌نام) و تاریخ شمسی"""
import re
import sqlite3

from conftest import login
from models import db, Order, Enrollment
from jdates import jdate, jalali_to_gregorian, jdatetime


def _csrf(client, path):
    r = client.get(path)
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    assert m
    return m.group(1)


def test_cart_add(client):
    login(client, 'demo@test.ir', 'demo123')
    r = client.post('/api/cart/add', json={'course_id': 1})
    assert r.get_json()['ok'] is True


def test_full_purchase_flow(client):
    """جریان کامل خرید: سبد → سفارش → درگاه sandbox → پرداخت → ثبت‌نام"""
    login(client, 'demo@test.ir', 'demo123')
    # سبد
    client.post('/api/cart/add', json={'course_id': 1})
    # سفارش
    tok = _csrf(client, '/checkout')
    r = client.post('/checkout', data={
        '_csrf_token': tok, 'action': 'create_order', 'installment_count': '0'
    }, follow_redirects=False)
    assert r.status_code == 302
    code = r.headers['Location'].split('/pay/')[-1]
    # درگاه sandbox
    tok = _csrf(client, f'/pay/{code}')
    r = client.post(f'/pay/{code}', data={'_csrf_token': tok, 'gateway': 'sandbox'},
                    follow_redirects=False)
    assert r.status_code == 302 and '/pay/bank/' in r.headers['Location']
    # شبیه‌سازی پرداخت موفق
    bank_url = r.headers['Location']
    tok = _csrf(client, bank_url)
    r = client.post(bank_url, data={'_csrf_token': tok, 'decision': 'ok'},
                    follow_redirects=False)
    assert r.status_code == 302 and 'success' in r.headers['Location']
    # بررسی: سفارش paid و ثبت‌نام ساخته شده
    order = Order.query.filter_by(code=code).first()
    assert order and order.status == 'paid'
    enr = Enrollment.query.filter_by(order_id=order.id).first()
    assert enr is not None


def test_double_payment_no_duplicate(client):
    """پرداخت تکراری نباید لاگ/کوپن دوباره بسازد"""
    test_full_purchase_flow(client)  # یک پرداخت کامل
    # تلاش دوباره روی سفارش paid → ریدایرکت به نتیجه بدون لاگ جدید
    from models import PaymentLog
    before = PaymentLog.query.count()
    order = Order.query.filter_by(status='paid').first()
    r = client.get(f'/pay/bank/{order.code}', follow_redirects=False)
    assert r.status_code == 302
    assert PaymentLog.query.count() == before


# ---------- تاریخ شمسی ----------
def test_jdate_conversion():
    assert jdate('2026-08-06') == '۱۵ مرداد ۱۴۰۵'


def test_jdatetime_conversion():
    assert '۱۴:۳۰' in jdatetime('2026-08-06 14:30:00')


def test_jalali_to_gregorian():
    assert jalali_to_gregorian('1405/05/15') == '2026-08-06'
    assert jalali_to_gregorian('bad-input') is None


def test_jdate_none():
    assert jdate(None) == '—'


def test_student_e2e_register_learn_cert_review_ticket(client, app):
    """فلوی کامل دانشجو: ثبت‌نام → ورود خودکار → یادگیری → گواهی → نظر → تیکت"""
    import re as _re
    from models import User, Enrollment, Review, Ticket, Section, Lesson

    def _csrf(url):
        r = client.get(url)
        m = _re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
        return m.group(1) if m else None

    # ثبت‌نام (با کد ملی معتبر)
    import random as _rnd
    nc = None
    for _ in range(200):
        d = [_rnd.randint(0, 9) for _ in range(10)]
        if d[0] == 0:
            continue
        s = sum((10 - i) * d[i] for i in range(9))
        r = s % 11
        c = (0 if r < 2 else 11 - r)
        if c == d[9]:
            nc = ''.join(map(str, d))
            break
    if not nc:
        nc = '0013542429'  # کد معتبر ثابت
    tok = _csrf('/auth/register')
    r = client.post('/auth/register', data={
        '_csrf_token': tok, 'name': 'کاربر E2E تست', 'email': 'e2e@test.ir',
        'password': 'Test1234!', 'confirm': 'Test1234!',
        'phone': '09120988776', 'national_code': nc,
    }, follow_redirects=False)
    assert r.status_code == 302, f'ثبت‌نام: {r.status_code}'
    with app.app_context():
        u = User.query.filter_by(email='e2e@test.ir').first()
        assert u is not None

    # ثبت‌نام در دوره (مستقیم — چون پرداخت در تست دیگر پوشش داده شده)
    with app.app_context():
        en = Enrollment(user_id=u.id, course_id=1)
        db.session.add(en)
        db.session.flush()
        # درس و سکشن برای دوره تست بساز (گواهی نیاز به ۱۰۰٪ دارد)
        sec = Section.query.filter_by(course_id=1).first()
        if not sec:
            sec = Section(course_id=1, title='سکشن تست', sort=1)
            db.session.add(sec)
            db.session.flush()
        lessons = []
        for i, t in enumerate(['درس ۱', 'درس ۲']):
            lsn = Lesson(section_id=sec.id, title=t, video_type='none',
                         content='متن درس', sort=i + 1, is_free=True)
            db.session.add(lsn)
            lessons.append(lsn)
        db.session.commit()
        lessons = (Lesson.query.join(Section, Lesson.section_id == Section.id)
                   .filter(Section.course_id == 1)
                   .order_by(Section.sort, Lesson.sort).all())

    # یادگیری + تکمیل همه دروس (گواهی نیاز به ۱۰۰٪ دارد)
    for lsn in lessons:
        tok = _csrf(f'/learn/1?lesson={lsn.id}')
        r = client.post(f'/learn/1/complete/{lsn.id}', data={'_csrf_token': tok},
                        follow_redirects=False)
        assert r.status_code in (302, 200)
    # گواهی
    r = client.get('/certificate/1')
    assert r.status_code == 200
    # نظر
    tok = _csrf('/course/test-course')
    r = client.post('/course/test-course/review', data={'_csrf_token': tok, 'rating': 5,
                                                       'comment': 'عالی بود'}, follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        assert Review.query.filter_by(user_id=u.id).count() >= 1
    # تیکت
    tok = _csrf('/dashboard/tickets/new')
    r = client.post('/dashboard/tickets/new', data={'_csrf_token': tok,
                    'subject': 'سوال تستی', 'body': 'بدنه سوال'}, follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        assert Ticket.query.filter_by(user_id=u.id).count() >= 1
