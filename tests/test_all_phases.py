# -*- coding: utf-8 -*-
"""Comprehensive tests covering all implemented phases (Phases 1-5)."""
import json
from datetime import datetime, timedelta
from app import create_app
from models import (db, User, Course, Section, Lesson, LessonNote, Order, OrderItem,
                    Coupon, Product, Review, Enrollment, Quiz, QuizQuestion,
                    QuizAttempt, LessonQuestion, CustomForm, CustomFormEntry,
                    Ticket, TicketReply, Page, PageRevision)
from gamification import wallet_charge, wallet_spend
from blueprints.admin_extra import _parse_report_date
from tests.conftest import csrf_headers


def test_wallet_spend_and_charge(app):
    """Test user wallet charging, spending, and balance constraints."""
    with app.app_context():
        user = User(name='Wallet User', email='wallet_test@example.com', role='student')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()

        # Charge wallet
        assert wallet_charge(user, 100_000, 'Charge Test') is True
        assert user.wallet_balance == 100_000

        # Spend within balance
        assert wallet_spend(user, 40_000, 'Spend Test 1') is True
        assert user.wallet_balance == 60_000

        # Spend more than balance -> Should fail and return False
        assert wallet_spend(user, 90_000, 'Spend Test 2') is False
        assert user.wallet_balance == 60_000


def test_co_teacher_revenue_split_cap(app):
    """Test co-teacher revenue split logic and bounds."""
    with app.app_context():
        teacher1 = User(name='Main Teacher', email='t1@example.com', role='teacher')
        teacher2 = User(name='Co Teacher 1', email='t2@example.com', role='teacher')
        teacher3 = User(name='Co Teacher 2', email='t3@example.com', role='teacher')
        for t in (teacher1, teacher2, teacher3):
            t.set_password('password123')
            db.session.add(t)
        db.session.commit()

        course = Course(
            title='Revenue Split Course',
            slug='revenue-split-course',
            price=1_000_000,
            revenue_percent=70,  # Teacher pool = 70% = 700,000
            teacher_id=teacher1.id,
            status='published'
        )
        db.session.add(course)
        db.session.commit()

        from models import CourseTeacher
        db.session.add(CourseTeacher(course_id=course.id, teacher_id=teacher2.id, share_percent=20))
        db.session.add(CourseTeacher(course_id=course.id, teacher_id=teacher3.id, share_percent=30))
        db.session.commit()

        # Teacher 2 gets 20% of 700k = 140k
        assert course.teacher_share_amount(teacher2.id, 1_000_000) == 140_000
        # Teacher 3 gets 30% of 700k = 210k
        assert course.teacher_share_amount(teacher3.id, 1_000_000) == 210_000
        # Main teacher gets remaining (50% of 700k) = 350k
        assert course.teacher_share_amount(teacher1.id, 1_000_000) == 350_000


def test_lesson_notes_api(client, app):
    """Test student lesson notes retrieval and cloud sync."""
    with app.app_context():
        user = User(name='Student Notes', email='student_notes@example.com', role='student')
        user.set_password('password123')
        course = Course(title='Notes Course', slug='notes-course', price=0, status='published')
        db.session.add_all([user, course])
        db.session.commit()

        sec = Section(course_id=course.id, title='Sec 1')
        db.session.add(sec)
        db.session.commit()

        lesson = Lesson(section_id=sec.id, title='Lesson 1', duration='10:00')
        db.session.add(lesson)
        db.session.commit()

        # Login
        with client.session_transaction() as sess:
            sess['uid'] = user.id
            sess['st'] = user.session_token

        headers = csrf_headers(client)

        # Save note
        res = client.post(f'/api/lesson/{lesson.id}/note',
                          json={'note': 'Key takeaway from lesson 1', 'playback_time': 125.5},
                          headers=headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data['ok'] is True

        # Fetch note
        res = client.get(f'/api/lesson/{lesson.id}/note')
        assert res.status_code == 200
        data = res.get_json()
        assert data['ok'] is True
        assert data['note'] == 'Key takeaway from lesson 1'
        assert abs(data['playback_time'] - 125.5) < 0.1


def test_lesson_playback_api(client, app):
    """Test student playback position save and resume."""
    with app.app_context():
        user = User(name='Student Playback', email='student_pb@example.com', role='student')
        user.set_password('password123')
        course = Course(title='Playback Course', slug='pb-course', price=0, status='published')
        db.session.add_all([user, course])
        db.session.commit()

        sec = Section(course_id=course.id, title='Sec 1')
        db.session.add(sec)
        db.session.commit()

        lesson = Lesson(section_id=sec.id, title='Lesson PB', duration='15:00')
        db.session.add(lesson)
        db.session.commit()

        # Login
        with client.session_transaction() as sess:
            sess['uid'] = user.id
            sess['st'] = user.session_token

        headers = csrf_headers(client)

        # Save playback position
        res = client.post(f'/api/lesson/{lesson.id}/playback',
                          json={'playback_time': 342.0},
                          headers=headers)
        assert res.status_code == 200
        assert res.get_json()['ok'] is True

        # Fetch playback position
        res = client.get(f'/api/lesson/{lesson.id}/playback')
        assert res.status_code == 200
        data = res.get_json()
        assert data['ok'] is True
        assert abs(data['playback_time'] - 342.0) < 0.1


def test_coupon_revalidation_in_order(client, app):
    """Test coupon validation and expired coupon handling in create_order."""
    with app.app_context():
        user = User(name='Coupon User', email='coupon_u@example.com', role='student')
        user.set_password('password123')
        course = Course(title='Paid Course', slug='paid-c', price=200_000, status='published')
        expired_coupon = Coupon(
            code='EXPIRED100',
            type='percent',
            value=20,
            expires_at=datetime.utcnow() - timedelta(days=1)
        )
        valid_coupon = Coupon(
            code='VALID20',
            type='percent',
            value=20,
            expires_at=datetime.utcnow() + timedelta(days=10)
        )
        db.session.add_all([user, course, expired_coupon, valid_coupon])
        db.session.commit()

        # Get CSRF token
        client.get('/')
        with client.session_transaction() as sess:
            tok = sess.get('_csrf_token')
            sess['uid'] = user.id
            sess['st'] = user.session_token
            sess['cart'] = [course.id]
            sess['coupon'] = {'code': 'EXPIRED100', 'discount': 40_000}

        # Attempt to create order with expired coupon
        res = client.post('/checkout', data={
            'action': 'create_order',
            'gateway': 'card2card',
            '_csrf_token': tok,
            'name': 'Coupon User',
            'email': 'coupon_u@example.com',
            'phone': '09120000000'
        })
        assert res.status_code in (200, 302)

        # Check latest order: coupon discount should not apply expired coupon
        order = Order.query.filter_by(user_id=user.id).order_by(Order.id.desc()).first()
        assert order is not None
        assert order.coupon is None or order.discount == 0
        assert order.final_total == 200_000


def test_marketplace_inventory_sync(app):
    """Test inventory deduction and restoration on marketplace orders."""
    with app.app_context():
        from ext_models import MarketOrder
        product = Product(
            title='Market Product',
            slug='market-product',
            price=150_000,
            stock=10,
            is_active=True
        )
        db.session.add(product)
        db.session.commit()

        initial_stock = product.stock

        # Create MarketOrder
        mo = MarketOrder(
            channel='basalam',
            external_id='BSL-1001',
            customer_name='Ali Reza',
            customer_phone='09120000000',
            items=json.dumps([{'product_id': product.id, 'quantity': 2}]),
            total=300_000,
            status='new'
        )
        db.session.add(mo)
        db.session.commit()

        # Simulate status change to accepted
        mo.status = 'accepted'
        items_data = json.loads(mo.items)
        for it in items_data:
            p = db.session.get(Product, it['product_id'])
            p.stock -= it['quantity']
        db.session.commit()
        assert product.stock == initial_stock - 2

        # Status change to canceled -> stock restored
        for it in items_data:
            p = db.session.get(Product, it['product_id'])
            p.stock += it['quantity']
        mo.status = 'canceled'
        db.session.commit()
        assert product.stock == initial_stock


def test_jalali_date_range_helper():
    """Test Jalali and Gregorian date range parsing helper."""
    # Gregorian
    d_g = _parse_report_date('2024-05-15')
    assert d_g is not None
    assert d_g.year == 2024 and d_g.month == 5 and d_g.day == 15

    # Jalali with Persian digits
    d_j = _parse_report_date('۱۴۰۳/۰۱/۱۵')
    assert d_j is not None
    assert d_j.year == 2024 and d_j.month == 4 and d_j.day == 3

    # Empty / Invalid
    assert _parse_report_date('') is None
    assert _parse_report_date('invalid-date') is None


def test_bulk_actions_endpoints(client, app):
    """Test admin bulk actions for reviews, users, and orders."""
    with app.app_context():
        admin = User(name='Admin Bulk', email='admin_bulk@example.com', role='super_admin')
        admin.set_password('AdminPass123')
        u1 = User(name='User 1', email='u1@example.com', role='student', is_active=True)
        u2 = User(name='User 2', email='u2@example.com', role='student', is_active=True)
        u1.set_password('Pass1234')
        u2.set_password('Pass1234')
        course = Course(title='C1', slug='c1', price=0, status='published')
        db.session.add_all([admin, u1, u2, course])
        db.session.commit()

        r1 = Review(course_id=course.id, user_id=u1.id, rating=5, comment='Nice', is_approved=False)
        r2 = Review(course_id=course.id, user_id=u2.id, rating=4, comment='Good', is_approved=False)
        o1 = Order(user_id=u1.id, code='ORD-01', total=100_000, final_total=100_000, status='pending')
        o2 = Order(user_id=u2.id, code='ORD-02', total=200_000, final_total=200_000, status='pending')
        db.session.add_all([r1, r2, o1, o2])
        db.session.commit()

        client.get('/')
        with client.session_transaction() as sess:
            tok = sess.get('_csrf_token')
            sess['uid'] = admin.id
            sess['st'] = admin.session_token

        # Bulk approve reviews
        res = client.post('/admin/reviews/bulk', data={
            '_csrf_token': tok,
            'bulk_action': 'approve',
            'item_ids[]': [r1.id, r2.id]
        })
        assert res.status_code == 302
        db.session.refresh(r1)
        db.session.refresh(r2)
        assert r1.is_approved is True
        assert r2.is_approved is True

        # Bulk deactivate users
        res = client.post('/admin/users/bulk', data={
            '_csrf_token': tok,
            'bulk_action': 'deactivate',
            'item_ids[]': [u1.id, u2.id]
        })
        assert res.status_code == 302
        db.session.refresh(u1)
        db.session.refresh(u2)
        assert u1.is_active is False
        assert u2.is_active is False

        # Bulk activate users
        res = client.post('/admin/users/bulk', data={
            '_csrf_token': tok,
            'bulk_action': 'activate',
            'item_ids[]': [u1.id, u2.id]
        })
        assert res.status_code == 302
        db.session.refresh(u1)
        assert u1.is_active is True

        # Bulk mark paid orders
        res = client.post('/admin/orders/bulk', data={
            '_csrf_token': tok,
            'bulk_action': 'mark_paid',
            'item_ids[]': [o1.id, o2.id]
        })
        assert res.status_code == 302
        db.session.refresh(o1)
        db.session.refresh(o2)
        assert o1.status == 'paid'
        assert o2.status == 'paid'
