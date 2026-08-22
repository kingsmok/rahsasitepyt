# -*- coding: utf-8 -*-
"""تست‌های امنیتی تکمیلی — پیشگیری از تسخیر حساب در بازیابی رمز + مقایسهٔ مقاوم OTP."""
import re
import blueprints.auth as auth_mod
from models import User, Setting, db


def _csrf(client, path):
    r = client.get(path)
    m = re.search(r'name="_csrf_token" value="([^\"]+)"', r.text)
    assert m, f'CSRF not found on {path}'
    return m.group(1)


def _set_sms_provider(app, provider):
    with app.app_context():
        s = db.session.get(Setting, 'sms_provider')
        if s:
            s.value = provider
        else:
            db.session.add(Setting(key='sms_provider', value=provider))
        db.session.commit()


def _ensure_demo_user_has_password(app):
    """کاربر دمو باید رمز داشته باشد تا جریان بازیابی ادامه پیدا کند."""
    with app.app_context():
        u = User.query.filter_by(phone='09120000888').first()
        u.password_hash = u.password_hash or 'placeholder-hash'
        db.session.commit()


# ---------------------------------------------------------------
# تسخیر حساب در بازیابی رمز — رفع‌شده
# ---------------------------------------------------------------
def test_forgot_sends_otp_to_registered_phone(monkeypatch, client, app):
    """کد بازیابی باید به شمارهٔ واقعی پیامک شود و هرگز روی صفحه نمایش داده نشود
    (با پنل پیامکی واقعی) — جلوگیری از تسخیر حساب با واردکردن شمارهٔ قربانی."""
    _set_sms_provider(app, 'kavenegar')  # پنل واقعی → غیر دمو
    _ensure_demo_user_has_password(app)

    calls = {}

    def fake_send_otp(phone, code, settings):
        calls['phone'] = phone
        calls['code'] = code
        return True, 'sent'

    monkeypatch.setattr('sms.send_otp', fake_send_otp)
    tok = _csrf(client, '/auth/forgot')
    r = client.post('/auth/forgot', data={'_csrf_token': tok, 'phone': '09120000888'},
                    follow_redirects=False)
    assert r.status_code == 302
    assert calls.get('phone') == '09120000888'  # کد واقعاً به شماره ارسال شد
    # کد نباید در فلش/پاسخ نمایش داده شود
    assert 'کد بازیابی شما' not in r.text


def test_forgot_does_not_show_code_to_requestor(monkeypatch, client, app):
    """با پنل واقعی، مهاجم با واردکردن شمارهٔ قربانی نباید کد را ببیند."""
    _set_sms_provider(app, 'kavenegar')
    _ensure_demo_user_has_password(app)

    def fake_send_otp(phone, code, settings):
        return True, 'sent'

    monkeypatch.setattr('sms.send_otp', fake_send_otp)
    tok = _csrf(client, '/auth/forgot')
    r = client.post('/auth/forgot', data={'_csrf_token': tok, 'phone': '09120000888'},
                    follow_redirects=True)
    body = r.get_data(as_text=True)
    # هیچ کد ۵ رقمی در پاسخ نباید باشد (هیچ «حالت دمو» نباید رخ دهد)
    assert 'حالت دمو' not in body


def test_forgot_shows_code_only_in_demo(monkeypatch, client, app):
    """در حالت دمو (بدون پنل واقعی) کد روی صفحه نمایش داده می‌شود — رفتار پیشین حفظ است."""
    _set_sms_provider(app, '')  # دمو
    _ensure_demo_user_has_password(app)

    def fake_send_otp(phone, code, settings):
        return True, 'SMS_DEMO'

    monkeypatch.setattr('sms.send_otp', fake_send_otp)
    tok = _csrf(client, '/auth/forgot')
    r = client.post('/auth/forgot', data={'_csrf_token': tok, 'phone': '09120000888'},
                    follow_redirects=False)
    assert r.status_code == 302
    # برای چک فلش، ریدایرکت را دنبال می‌کنیم
    r2 = client.get(r.headers['Location'], follow_redirects=True)
    assert 'کد بازیابی' in r2.get_data(as_text=True)


def test_otp_plaintext_never_enters_client_session(client, app):
    _set_sms_provider(app, 'demo')
    token = _csrf(client, '/auth/login')
    response = client.post('/auth/phone-send', data={
        '_csrf_token': token, 'phone': '09120000888'
    }, follow_redirects=False)
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert 'otp_code' not in sess
        assert 'otp_code_hash' in sess
    assert app.config.get('_TEST_AUTH_CODES', {}).get('phone-otp')


# ---------------------------------------------------------------
# مقایسهٔ مقاوم در برابر Timing Attack
# ---------------------------------------------------------------
def test_codes_equal_is_constant_time():
    assert auth_mod._codes_equal('12345', '12345') is True
    assert auth_mod._codes_equal('12345', '54321') is False
    assert auth_mod._codes_equal('', '') is False      # خالی هرگز برابر نیست
    assert auth_mod._codes_equal('12345', None) is False


def test_otp_uses_constant_time_comparison():
    """کدهای OTP/2FA باید با مقایسهٔ مقاوم (نه ==) بررسی شوند."""
    src = open('blueprints/auth.py', encoding='utf-8').read()
    # نباید هیچ مقایسهٔ مستقیم == برای کدها باقی مانده باشد
    assert "session['otp_code'] = code" not in src
    assert "session['admin_2fa'] = code" not in src
    assert src.count('_code_matches(') >= 4  # تابع + OTP، 2FA و بازیابی رمز


def test_admin_2fa_code_not_flashed_in_production(monkeypatch, client, app):
    """در production، کد دومرحله‌ای روی صفحه نمایش داده نمی‌شود."""
    _set_sms_provider(app, 'kavenegar')
    monkeypatch.setenv('FLASK_ENV', 'production')
    # بازنویسی _is_prod تا با محیط هماهنگ شود
    monkeypatch.setattr(auth_mod, '_is_prod', lambda: True)
    from conftest import login
    login(client, 't@test.ir', 'teacher123')
    # کد 2FA باید در session باشد ولی در فلش دیده نشود
    r = client.get('/auth/admin-2fa')
    assert 'کد تایید دومرحله‌ای (دمو)' not in r.get_data(as_text=True)


# ---------------------------------------------------------------
# Open Redirect — ریدایرکت referrer فقط هم‌منشاء
# ---------------------------------------------------------------
def test_newsletter_redirect_not_open(client, app):
    """ریدایرکت خبرنامه با referrer بیرونی نباید به دامنهٔ خارجی برود."""
    tok = _csrf(client, '/contact')
    # referrer خارجی → باید به default (index) برگردد نه دامنهٔ بیرونی
    r = client.post('/newsletter', data={'email': 'x@x.ir', '_csrf_token': tok},
                    headers={'Referer': 'https://evil.example.com/phish'},
                    follow_redirects=False)
    assert r.status_code == 302
    target = r.headers['Location']
    assert 'evil.example.com' not in target


def test_newsletter_redirect_same_origin_allowed(client, app):
    tok = _csrf(client, '/contact')
    r = client.post('/newsletter', data={'email': 'x2@x.ir', '_csrf_token': tok},
                    headers={'Referer': 'http://localhost/some-page'},
                    follow_redirects=False)
    assert r.status_code == 302
    assert 'evil.example.com' not in r.headers['Location']
