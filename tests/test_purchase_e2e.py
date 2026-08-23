# -*- coding: utf-8 -*-
"""سناریوی سرتاسری خرید — حیاتی‌ترین جریان درآمدی محصول.

چرا این فایل لازم است؟
    تست‌های موجود هر جزء را جدا بررسی می‌کنند (سبد، سفارش، کیف پول،
    ثبت‌نام)، اما هیچ‌کدام کل زنجیره را از ابتدا تا انتها طی نمی‌کنند.
    شکستن این زنجیره یعنی مشتری پول می‌دهد و دوره فعال نمی‌شود — بدترین
    باگ ممکن برای یک نرم‌افزار فروش دوره، چون مستقیماً به اعتبار و
    درآمد صاحب محصول ضربه می‌زند.

قرارداد تضمین‌شده:
    ثبت‌نام → سبد → ثبت سفارش → پرداخت → وضعیت paid → ثبت‌نام خودکار در
    دوره → کسر دقیق موجودی. هر حلقه از این زنجیره جداگانه بررسی می‌شود.
"""
import re

from models import Category, Course, Enrollment, Order, User, db


def _csrf(client, path='/'):
    r = client.get(path)
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    assert m, 'توکن CSRF در صفحهٔ {} پیدا نشد'.format(path)
    return m.group(1)


def _make_course(app, price=200000, slug='e2e-course'):
    with app.app_context():
        cat = Category(name='دستهٔ آزمون', slug='e2e-cat', sort=1)
        db.session.add(cat)
        db.session.flush()
        teacher = User(name='مدرس آزمون', email='teacher@e2e.ir',
                       phone='09120001111', role='teacher', is_active=True)
        teacher.set_password('teacher123')
        db.session.add(teacher)
        db.session.flush()
        course = Course(title='دورهٔ آزمون سرتاسری', slug=slug, price=price,
                        category_id=cat.id, teacher_id=teacher.id,
                        status='published')
        db.session.add(course)
        db.session.commit()
        return course.id


def _register_buyer(client, email='buyer@e2e.ir', phone='09121112233'):
    return client.post('/auth/register', data={
        '_csrf_token': _csrf(client, '/auth/register'),
        'name': 'خریدار آزمون', 'email': email, 'phone': phone,
        'national_code': '', 'password': 'secret123', 'confirm': 'secret123',
    }, follow_redirects=False)


def test_full_purchase_flow_with_wallet(client, app):
    """کل زنجیرهٔ خرید با کیف پول باید بدون شکست کار کند."""
    course_id = _make_course(app)

    r = _register_buyer(client)
    assert r.status_code == 302, 'ثبت‌نام خریدار موفق نبود'

    with client.session_transaction() as sess:
        sess['cart'] = [course_id]

    with app.app_context():
        buyer = User.query.filter_by(email='buyer@e2e.ir').first()
        buyer_id = buyer.id
        from gamification import wallet_charge
        wallet_charge(buyer, 500000, 'شارژ آزمون')
        db.session.commit()

    # ۱) ثبت سفارش
    r = client.post('/checkout', data={
        '_csrf_token': _csrf(client, '/checkout'),
        'action': 'create_order', 'installment_count': '0',
    }, follow_redirects=False)
    assert r.status_code == 302, 'ثبت سفارش باید ریدایرکت به صفحهٔ پرداخت بدهد'

    with app.app_context():
        order = (Order.query.filter_by(user_id=buyer_id)
                 .order_by(Order.id.desc()).first())
        assert order is not None, 'سفارش ساخته نشد'
        assert order.status == 'pending'
        assert order.final_total == 200000, 'مبلغ نهایی سفارش نادرست است'
        code = order.code

    # ۲) پرداخت با کیف پول
    r = client.post('/checkout/wallet', data={
        '_csrf_token': _csrf(client, '/cart'), 'code': code,
    }, follow_redirects=False)
    assert r.status_code == 302

    # ۳) بررسی نتیجهٔ نهایی: سفارش پرداخت‌شده، دوره فعال، موجودی درست
    with app.app_context():
        order = Order.query.filter_by(code=code).first()
        assert order.status == 'paid', 'وضعیت سفارش پس از پرداخت paid نشد'
        assert order.paid_at is not None, 'زمان پرداخت ثبت نشد'

        enrollment = Enrollment.query.filter_by(
            user_id=buyer_id, course_id=course_id).first()
        assert enrollment is not None, \
            'مشتری پول داد ولی در دوره ثبت‌نام نشد — بحرانی‌ترین باگ ممکن'

        buyer = db.session.get(User, buyer_id)
        assert buyer.wallet_balance == 300000, \
            'کسر موجودی نادرست: {} (انتظار ۳۰۰۰۰۰)'.format(buyer.wallet_balance)


def test_purchase_blocked_when_wallet_insufficient(client, app):
    """موجودی ناکافی نباید سفارش را paid کند و نباید دوره را فعال کند."""
    course_id = _make_course(app, price=900000, slug='e2e-expensive')
    _register_buyer(client, 'poor@e2e.ir', '09121114444')

    with client.session_transaction() as sess:
        sess['cart'] = [course_id]

    with app.app_context():
        buyer = User.query.filter_by(email='poor@e2e.ir').first()
        buyer_id = buyer.id
        from gamification import wallet_charge
        wallet_charge(buyer, 10000, 'شارژ ناکافی')   # خیلی کمتر از قیمت
        db.session.commit()

    client.post('/checkout', data={
        '_csrf_token': _csrf(client, '/checkout'),
        'action': 'create_order', 'installment_count': '0',
    }, follow_redirects=False)

    with app.app_context():
        order = (Order.query.filter_by(user_id=buyer_id)
                 .order_by(Order.id.desc()).first())
        assert order is not None
        code = order.code

    client.post('/checkout/wallet', data={
        '_csrf_token': _csrf(client, '/cart'), 'code': code,
    }, follow_redirects=False)

    with app.app_context():
        order = Order.query.filter_by(code=code).first()
        assert order.status != 'paid', \
            'سفارش با موجودی ناکافی نباید پرداخت‌شده علامت بخورد'
        assert Enrollment.query.filter_by(
            user_id=buyer_id, course_id=course_id).first() is None, \
            'بدون پرداخت موفق نباید دسترسی دوره داده شود'
        buyer = db.session.get(User, buyer_id)
        assert buyer.wallet_balance == 10000, 'موجودی نباید تغییر کند'


def test_empty_cart_cannot_create_order(client, app):
    """سبد خالی نباید سفارش بسازد."""
    _register_buyer(client, 'empty@e2e.ir', '09121115555')
    with client.session_transaction() as sess:
        sess['cart'] = []
    r = client.post('/checkout', data={
        '_csrf_token': _csrf(client, '/cart'),
        'action': 'create_order', 'installment_count': '0',
    }, follow_redirects=False)
    assert r.status_code in (302, 200)
    with app.app_context():
        buyer = User.query.filter_by(email='empty@e2e.ir').first()
        assert Order.query.filter_by(user_id=buyer.id).count() == 0, \
            'سبد خالی نباید سفارش ایجاد کند'


def test_guest_cannot_checkout(client, app):
    """کاربر مهمان نباید بتواند سفارش ثبت کند."""
    course_id = _make_course(app, slug='e2e-guest')
    with client.session_transaction() as sess:
        sess['cart'] = [course_id]
    r = client.post('/checkout', data={
        '_csrf_token': _csrf(client, '/cart'),
        'action': 'create_order', 'installment_count': '0',
    }, follow_redirects=False)
    assert r.status_code == 302, 'مهمان باید به صفحهٔ ورود هدایت شود'
    with app.app_context():
        assert Order.query.count() == 0, 'مهمان نباید سفارش بسازد'


def test_atomic_wallet_guard_blocks_overdraft_directly(app):
    """گارد اتمیک کسر کیف پول باید مستقیماً برداشت بیش از موجودی را رد کند.

    چرا این تست در سطح تابع نوشته شده و نه از طریق HTTP؟
        در مسیر /checkout/wallet دو لایهٔ محافظت وجود دارد:
          ۱) یک چک سادهٔ موجودی (فقط برای نمایش پیام کاربرپسند)
          ۲) کسر اتمیک با شرط کفایت موجودی داخل خود دستور SQL
        لایهٔ اول همیشه زودتر عمل می‌کند، بنابراین از طریق HTTP هرگز
        نمی‌توان لایهٔ دوم را آزمود. اما لایهٔ دوم همان چیزی است که در
        شرایط همزمانی واقعی (دو خرید هم‌زمان) از دو-بار-خرج‌شدن جلوگیری
        می‌کند، پس باید جداگانه و مستقیم تضمین شود.
    """
    from gamification import wallet_spend
    with app.app_context():
        u = User(name='کاربر گارد', email='guard@e2e.ir', phone='09121117777',
                 role='student', is_active=True)
        u.set_password('secret123')
        u.wallet_balance = 50000
        db.session.add(u)
        db.session.commit()

        # برداشت بیش از موجودی باید رد شود و موجودی دست‌نخورده بماند
        assert wallet_spend(u, 200000, 'خرید گران') is False
        db.session.commit()
        db.session.refresh(u)
        assert u.wallet_balance == 50000, 'موجودی نباید تغییر کند'

        # برداشت دقیقاً به اندازهٔ موجودی باید موفق باشد
        assert wallet_spend(u, 50000, 'خرید کامل') is True
        db.session.commit()
        db.session.refresh(u)
        assert u.wallet_balance == 0
        assert u.wallet_balance >= 0, 'موجودی هرگز نباید منفی شود'
