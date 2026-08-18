# -*- coding: utf-8 -*-
"""رگرسیون امنیتی — محافظت خودکار از فیکس‌های ۹ دور ممیزی (۱۴۰۵/۰۵/۱۶)

هر تست = یک آسیب‌پذیری که قبلاً کشف و فیکس شد:
  1. Open Redirect در login?next=
  2. cart_add با ورودی غیرعددی → 400 (نه 500)
  3. pay_installment در حالت production → ریدایرکت به درگاه (نه paid مستقیم)
  4. 2FA محدودیت تلاش (۵ بار → لاگین)
  5. OTP محدودیت تلاش (۵ بار → لاگین)
  6. XSS/HTML Injection در قالب ایمیل (_esc)
  7. خرید محصول ناموجود → مسدود در checkout
  8. impersonate_exit بدون حالت impersonation → خانه (نه /admin)
  9. آمار صفحه اصلی واقعی (بدون هاردکد ۵۰,۰۰۰)
"""
import re

from email_service import _esc
from blueprints.auth import _safe_next


# ---------------------------------------------------------------
# ۱) Open Redirect
# ---------------------------------------------------------------
def test_open_redirect_blocked():
    """next خارجی باید None برگرداند؛ فقط مسیرهای نسبی داخلی مجازند"""
    assert _safe_next('https://evil.com') is None
    assert _safe_next('//evil.com') is None
    assert _safe_next('/\\evil.com') is None
    assert _safe_next('javascript:alert(1)') is None
    assert _safe_next('/courses') == '/courses'
    assert _safe_next('/dashboard') == '/dashboard'


def test_login_next_external_redirects_to_dashboard(client):
    """لاگین با next خارجی نباید به سایت خارجی ریدایرکت کند"""
    r = client.get('/auth/login?next=https://evil.com')
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    r = client.post('/auth/login', data={
        '_csrf_token': m.group(1), 'email': 'demo@test.ir', 'password': 'demo123'
    }, follow_redirects=False)
    # ریدایرکت باید داخلی باشد (dashboard) نه evil.com
    loc = r.headers.get('Location', '')
    assert 'evil.com' not in loc


def test_brand_css_settings_cannot_inject_style_or_external_url(app, client):
    from models import Setting, db
    malicious = {
        'brand_color': '#112233;background:url(https://evil.example/x)',
        'brand_color2': 'red;}body{display:none',
        'kit_container': '1200;background:url(https://evil.example/y)',
        'kit_radius': '8;position:fixed',
    }
    with app.app_context():
        for key, value in malicious.items():
            row = db.session.get(Setting, key)
            if row:
                row.value = value
            else:
                db.session.add(Setting(key=key, value=value))
        db.session.commit()
        if hasattr(app, 'clear_cache'):
            app.clear_cache()
    response = client.get('/')
    assert response.status_code == 200
    assert 'evil.example' not in response.text
    assert 'body{display:none' not in response.text


# ---------------------------------------------------------------
# ۲) اعتبارسنجی ورودی API
# ---------------------------------------------------------------
def test_cart_add_rejects_non_numeric(client):
    """cart_add با شناسه غیرعددی → 400 (قبلاً 500 می‌داد)"""
    r = client.post('/api/cart/add', json={'course_id': 'abc'})
    assert r.status_code == 400


def test_cart_add_rejects_unknown_course(client):
    """cart_add با شناسه ناموجود → 404"""
    r = client.post('/api/cart/add', json={'course_id': 99999})
    assert r.status_code == 404


# ---------------------------------------------------------------
# ۳) پرداخت اقساط — امنیت در production
# ---------------------------------------------------------------
def test_installment_payment_requires_gateway_outside_sandbox(app, client):
    """در حالت غیرآزمایشی، پرداخت قسط باید به درگاه برود نه مستقیم paid"""
    from models import db, Order, OrderItem, Installment, User
    from datetime import datetime, timedelta
    import random
    with app.app_context():
        # غیرفعال کردن sandbox_mode — شبیه production
        from models import Setting
        s = db.session.get(Setting, 'sandbox_mode')
        if s:
            s.value = '0'
        else:
            db.session.add(Setting(key='sandbox_mode', value='0'))
        db.session.commit()
    with app.app_context():
        u = User.query.filter_by(email='demo@test.ir').first()
    # ورود مستقیم به سشن (ساده و بدون وابستگی به لاگین)
    with client.session_transaction() as sess:
        sess['uid'] = u.id
        o = Order(code='TEST-INST-1', user_id=u.id, total=100000, final_total=100000,
                  status='pending', installment_count=2, gateway='sandbox')
        db.session.add(o)
        db.session.flush()
        db.session.add(OrderItem(order_id=o.id, course_id=1, price=100000))
        db.session.add(Installment(order_id=o.id, number=1, amount=30000, status='pending'))
        db.session.add(Installment(order_id=o.id, number=2, amount=70000, status='pending'))
        db.session.commit()
        oid = o.id
    # تلاش برای پرداخت قسط ۲ — با توکن CSRF دستی (مکانیزم سشن)
    r = client.post('/pay/installment/TEST-INST-1/2',
                    data={'_csrf_token': 'test-csrf-token'}, follow_redirects=False)
    with app.app_context():
        inst = db.session.get(Installment, oid * 100)  # placeholder
        from models import Installment as _I
        row = _I.query.filter_by(order_id=oid, number=2).first()
        assert row.status != 'paid', 'قسط نباید بدون درگاه paid شود'
    # پاکسازی
    with app.app_context():
        db.session.query(Installment).filter_by(order_id=oid).delete()
        db.session.query(OrderItem).filter_by(order_id=oid).delete()
        db.session.query(Order).filter_by(id=oid).delete()
        s2 = db.session.get(Setting, 'sandbox_mode')
        if s2:
            s2.value = '1'
        db.session.commit()


# ---------------------------------------------------------------
# ۴) 2FA محدودیت تلاش
# ---------------------------------------------------------------
def test_pending_2fa_cannot_open_admin_directly(app, client):
    """وجود uid پیش از تایید کد نباید دسترسی مستقیم به /admin بدهد."""
    from models import db, User
    from blueprints.auth import _code_digest
    with app.app_context():
        admin = User(name='مدیر در انتظار', email='pending2fa@test.ir',
                     phone='09120000661', role='admin', is_active=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id
        digest = _code_digest('123456', 'admin-2fa')
    with client.session_transaction() as sess:
        sess['uid'] = admin_id
        sess['admin_2fa_hash'] = digest
        sess['admin_2fa_ts'] = __import__('time').time()
    response = client.get('/admin/', follow_redirects=False)
    assert response.status_code == 302
    assert '/auth/admin-2fa' in response.headers.get('Location', '')


def test_2fa_brute_force_locked(app, client):
    """۶ تلاش غلط 2FA → سشن باطل و ریدایرکت به لاگین"""
    from models import db, User
    with app.app_context():
        adm = User(name='ادمین تست', email='admin@test.ir', phone='09120000777',
                   role='admin', is_active=True)
        adm.set_password('admin123')
        db.session.add(adm)
        db.session.commit()
        adm_id = adm.id
    # ورود به عنوان ادمین (سشن) + ساخت وضعیت 2FA هش‌شده
    from blueprints.auth import _code_digest
    with app.app_context():
        digest = _code_digest('123456', 'admin-2fa')
    with client.session_transaction() as sess:
        sess['uid'] = adm_id
        sess['admin_2fa_hash'] = digest
        sess['admin_2fa_ts'] = __import__('time').time()
    r = client.get('/auth/admin-2fa')
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    assert m, 'فرم 2FA باز نشد'
    for _ in range(6):
        m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
        r = client.post('/auth/admin-2fa', data={'_csrf_token': m.group(1), 'code': '000000'},
                        follow_redirects=False)
    # تلاش ۶م → لاگین (سشن 2FA باطل شده)
    assert r.status_code == 302
    assert '/auth/login' in r.headers.get('Location', '')
    with client.session_transaction() as sess:
        assert 'uid' not in sess
        assert 'admin_2fa_hash' not in sess


def test_2fa_expired_code(app, client):
    """کد 2FA منقضی (بیشتر از ۵ دقیقه) → لاگین"""
    import time
    from models import db, User
    with app.app_context():
        adm = User(name='ادمین تست۲', email='admin2@test.ir', phone='09120000666',
                   role='admin', is_active=True)
        adm.set_password('admin123')
        db.session.add(adm)
        db.session.commit()
        adm_id = adm.id
    from blueprints.auth import _code_digest
    with app.app_context():
        digest = _code_digest('123456', 'admin-2fa')
    with client.session_transaction() as sess:
        sess['uid'] = adm_id
        sess['admin_2fa_hash'] = digest
        sess['admin_2fa_ts'] = time.time() - 400  # ۶ دقیقه قبل
    r = client.get('/auth/admin-2fa')
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    r = client.post('/auth/admin-2fa', data={'_csrf_token': m.group(1), 'code': '123456'},
                    follow_redirects=False)
    assert r.status_code == 302
    assert '/auth/login' in r.headers.get('Location', '')
    with client.session_transaction() as sess:
        assert 'uid' not in sess
        assert 'admin_2fa_hash' not in sess


# ---------------------------------------------------------------
# ۵) OTP محدودیت تلاش
# ---------------------------------------------------------------
def test_otp_brute_force_locked(client, app):
    """۵ تلاش غلط OTP → سشن باطل و ریدایرکت به لاگین"""
    from blueprints.auth import _code_digest
    with app.app_context():
        digest = _code_digest('12345', 'phone-otp')
    with client.session_transaction() as sess:
        sess['otp_phone'] = '09120000888'
        sess['otp_code_hash'] = digest
        sess['otp_ts'] = __import__('time').time()
    r = client.get('/auth/phone-verify')
    for _ in range(6):
        m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
        r = client.post('/auth/phone-verify', data={'_csrf_token': m.group(1), 'code': '00000'},
                        follow_redirects=False)
    assert r.status_code == 302
    assert '/auth/login' in r.headers.get('Location', '')


# ---------------------------------------------------------------
# ۶) XSS در ایمیل
# ---------------------------------------------------------------
def test_email_xss_escaped():
    """ورودی کاربر در HTML ایمیل باید escape شود"""
    evil = '<script>alert(1)</script><img src=x onerror=alert(2)>'
    out = _esc(evil)
    assert '<script>' not in out
    assert '<img' not in out
    assert '&lt;' in out


# ---------------------------------------------------------------
# ۷) خرید محصول ناموجود
# ---------------------------------------------------------------
def test_checkout_blocks_out_of_stock(app, client):
    """محصول با موجودی ۰ نباید قابل خرید باشد"""
    from models import db, Product, User
    with app.app_context():
        u = User.query.filter_by(email='demo@test.ir').first()
        p = Product(title='محصول تست', slug='test-product', price=10000,
                    stock=0, is_active=True)
        db.session.add(p)
        db.session.commit()
        pid = p.id
    # لاگین + افزودن به سبد
    r = client.get('/auth/login')
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    client.post('/auth/login', data={'_csrf_token': m.group(1),
                                     'email': 'demo@test.ir', 'password': 'demo123'})
    # افزودن محصول به سبد از طریق session
    with client.session_transaction() as sess:
        sess['cart'] = [pid]
    r = client.get('/checkout', follow_redirects=True)
    # باید به سبد برگردد با پیام «موجود نیست»
    assert 'موجود' in r.text or '/cart' in r.text or 'سبد' in r.text


# ---------------------------------------------------------------
# ۸) impersonate_exit بدون impersonation
# ---------------------------------------------------------------
def test_impersonate_exit_without_session_goes_home(client):
    """بدون حالت impersonation، /admin/impersonate/exit → خانه"""
    r = client.get('/admin/impersonate/exit', follow_redirects=False)
    # ریدایرکت به خانه (نه /admin که 403 می‌داد)
    loc = r.headers.get('Location', '')
    assert '/admin' not in loc


# ---------------------------------------------------------------
# ۹) آمار واقعی (placeholder ها)
# ---------------------------------------------------------------
def test_site_stats_real_numbers(app, client):
    """site_stats باید اعداد واقعی دیتابیس را بدهد نه هاردکد"""
    with app.app_context():
        st = app.jinja_env.globals['site_stats']()
        assert 'students' in st
        assert 'courses' in st
        assert 'hours' in st
        assert st['students'] >= 1
        assert st['courses'] >= 1
        # هیچ عدد هاردکد ۵۰,۰۰۰ نیست
        assert st['students'] < 50000


# ---------------------------------------------------------------
# ۱۰) فاز ۱۳ — بازخورد دوره فقط برای ثبت‌نام‌شده‌ها (IDOR)
# ---------------------------------------------------------------
def test_feedback_requires_enrollment(client):
    """کاربر غیرثبت‌نام‌شده نباید بازخورد دوره بدهد"""
    r = client.get('/auth/login')
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    client.post('/auth/login', data={'_csrf_token': m.group(1),
                                     'email': 'demo@test.ir', 'password': 'demo123'})
    # course 1 ساخته‌شده در conftest — دمو ثبت‌نام ندارد
    r = client.get('/feedback/1')
    assert r.status_code == 302
    assert '/course/' in r.headers.get('Location', '')
    # POST هم باید بلاک شود (با توکن CSRF معتبر)
    r = client.get('/course/test-course')
    m2 = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    r = client.post('/feedback/1', data={'_csrf_token': m2.group(1),
                                         'score': 1, 'comment': 'بدون ثبت‌نام'},
                    follow_redirects=False)
    assert r.status_code == 302
    assert '/course/' in r.headers.get('Location', '')


# ---------------------------------------------------------------
# ۱۱) فاز ۱۳ — ضد اسپم پیام خصوصی
# ---------------------------------------------------------------
def test_private_message_rate_limit(client):
    r = client.get('/auth/login')
    m = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    client.post('/auth/login', data={'_csrf_token': m.group(1),
                                     'email': 'demo@test.ir', 'password': 'demo123'})
    # ۳۱ پیام پشت‌سرهم → یکی باید بلاک شود
    r = client.get('/community/messages/1')
    m2 = re.search(r'name="_csrf_token" value="([^"]+)"', r.text)
    blocked = 0
    for _ in range(31):
        r = client.post('/community/api/messages/send',
                        data={'_csrf_token': m2.group(1), 'uid': 1, 'body': 'x'})
        if r.status_code == 429:
            blocked += 1
    assert blocked >= 1, 'محدودیت نرخ پیام اعمال نشد'


# ---------------------------------------------------------------
# ۱۲) فاز ۱۳ — مسیرهای traversal بلاک
# ---------------------------------------------------------------
def test_path_traversal_blocked(client):
    for p in ['/static/../app.py', '/course/%2e%2e%2fapp.py',
              '/admin/../../app.py', '/media/../app.py']:
        r = client.get(p)
        assert r.status_code in (404, 403, 400), f'{p} → {r.status_code}'


# ---------------------------------------------------------------
# ۱۳) فاز ۱۳ — لاگ‌ها نباید رمز/توکن حساس داشته باشند
# ---------------------------------------------------------------
def test_logs_contain_no_secrets(tmp_path):
    import glob, os
    logs = glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  'logs', '*.log'))
    for lp in logs:
        if not os.path.exists(lp):
            continue
        with open(lp, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        assert 'password=' not in text
        assert 'admin123' not in text
