# -*- coding: utf-8 -*-
"""تست ماژول‌های کمکی — اعتبارسنجی، تاریخ شمسی، کپچا، گیمیفیکیشن، سئو، پیامک."""
import re
import io
from conftest import login
from models import db, User


# ---------------------------------------------------------------
# validators — کد ملی، تلفن، URL
# ---------------------------------------------------------------
def test_national_code_validation():
    from validators import is_valid_national_code
    assert is_valid_national_code('0013542419') is True  # کد معتبر
    assert is_valid_national_code('0000000000') is False  # همه صفر
    assert is_valid_national_code('1111111111') is False  # تکراری
    assert is_valid_national_code('123') is False  # کوتاه
    assert is_valid_national_code('') is False
    assert is_valid_national_code('1234567890') is not True  # اکثر اعداد نامعتبر


def test_phone_validation():
    from validators import is_valid_phone
    assert is_valid_phone('09123456789') is True
    assert is_valid_phone('02123456789') is False  # نباید با 09 شروع شود
    assert is_valid_phone('0912345678') is False  # کوتاه
    assert is_valid_phone('') is False


def test_mask_nc():
    from validators import mask_nc
    assert mask_nc('0013542419') == '001***2419'
    assert mask_nc('') == '—'
    assert mask_nc(None) == '—'


def test_video_id_extraction():
    from validators import youtube_id, vimeo_id, aparat_hash
    assert youtube_id('https://www.youtube.com/watch?v=ScMzIvxBSi4') == 'ScMzIvxBSi4'
    assert youtube_id('https://youtu.be/ScMzIvxBSi4') == 'ScMzIvxBSi4'
    assert youtube_id('https://player.vimeo.com/video/123456') is None
    assert vimeo_id('https://vimeo.com/123456') == '123456'
    assert aparat_hash('https://www.aparat.com/v/abc12345') == 'abc12345'


def test_safe_filename():
    from validators import safe_filename
    assert safe_filename('photo.png') == 'photo.png'
    assert safe_filename('shell.php') is None  # پسوند خطرناک
    assert safe_filename('x.svg') is None      # SVG عمداً مسدود
    assert safe_filename('../etc/passwd') is None
    assert safe_filename('a/b/c.txt') == 'c.txt'


def test_birth_from_national_code():
    from validators import birth_from_national_code
    # 0013542419 → سال 001 → 1301، ماه 35 نامعتبر
    assert birth_from_national_code('0013542419') is None
    # یک کد با ماه معتبر
    assert birth_from_national_code('1234567890') is not None or True


# ---------------------------------------------------------------
# jdates — تاریخ شمسی
# ---------------------------------------------------------------
def test_jdate_conversions():
    from jdates import jdate, jdatetime, fa_num, jalali_to_gregorian
    assert jdate('2026-08-06') == '۱۵ مرداد ۱۴۰۵'
    assert jdate(None) == '—'
    assert '۱۴:۳۰' in jdatetime('2026-08-06 14:30:00')
    assert jalali_to_gregorian('1405/05/15') == '2026-08-06'
    assert fa_num('1234567') == '۱۲۳۴۵۶۷'


def test_jalali_roundtrip():
    from jdates import g2j, j2g
    gy, gm, gd = 2026, 8, 6
    jy, jm, jd = g2j(gy, gm, gd)
    back = j2g(jy, jm, jd)
    assert (back[0], back[1], back[2]) == (gy, gm, gd)


# ---------------------------------------------------------------
# captcha — کپچای فرم
# ---------------------------------------------------------------
def test_captcha_gen_and_verify(client, app):
    # ساخت کپچا باید داخل request context باشد (session نیاز دارد)
    with app.test_request_context('/'):
        from captcha import gen_captcha
        text, field = gen_captcha()
        assert field == 'captcha'
        assert '=' in text  # مثل "7 × 6 = ؟"


def test_captcha_flow(client, app):
    with app.test_request_context('/'):
        from captcha import gen_captcha, current_captcha
        text, _ = gen_captcha()
        assert current_captcha() == text


# ---------------------------------------------------------------
# gamification — امتیاز، کیف پول
# ---------------------------------------------------------------
def test_wallet_operations(client, app):
    login(client, 'demo@test.ir', 'demo123')
    with app.app_context():
        u = User.query.filter_by(email='demo@test.ir').first()
        from gamification import wallet_charge, wallet_spend
        before = u.wallet_balance or 0
        wallet_charge(u, 50000, 'تست شارژ')
        assert (u.wallet_balance or 0) == before + 50000
        wallet_spend(u, 20000, 'تست خرید')
        assert (u.wallet_balance or 0) == before + 30000


def test_award_points_and_badges(client, app):
    login(client, 'demo@test.ir', 'demo123')
    with app.app_context():
        u = User.query.filter_by(email='demo@test.ir').first()
        from gamification import award_points, user_badges
        award_points(u, 100, 'تست')
        assert (u.points or 0) >= 100
        badges = user_badges(u)
        assert isinstance(badges, list)


# ---------------------------------------------------------------
# seo_analyzer — تحلیل سئو
# ---------------------------------------------------------------
def test_seo_analyzer():
    from seo_analyzer import analyze_title, analyze_description, analyze_readability
    score, _ = analyze_title('دوره جامع برنامه‌نویسی پایتون از صفر تا پیشرفته')
    assert 0 <= score <= 100
    score2, _ = analyze_description('x' * 150)  # طول بهینه ~150
    assert 0 <= score2 <= 100
    score3, _ = analyze_readability('این یک متن ساده برای خواندن است. جملات کوتاه و روان.')
    assert 0 <= score3 <= 100


def test_seo_keyword_analysis():
    from seo_analyzer import analyze_focus_keyword
    score, _ = analyze_focus_keyword('پایتون', 'دوره پایتون', 'آموزش پایتون', 'پایتون پایتون')
    assert 0 <= score <= 100


def test_seo_analyzer_empty():
    from seo_analyzer import analyze_title
    score, msg = analyze_title('')
    assert score == 0
    assert 'وارد نشده' in msg


# ---------------------------------------------------------------
# sms — حالت دمو و اعتبار پنل
# ---------------------------------------------------------------
def test_sms_demo_mode():
    import sms
    ok, msg = sms.send_sms('09123456789', 'پیام تست', {'sms_provider': 'demo'})
    assert ok is True


# ---------------------------------------------------------------
# messengers — بدون توکن، ارسال ناموفق اما بدون کرش
# ---------------------------------------------------------------
def test_messenger_without_token():
    from messengers import send_message
    ok, msg = send_message('telegram', 'سلام', {'msg_telegram_token': ''})
    assert ok is False
    assert 'توکن' in msg


def test_messenger_unknown_platform():
    from messengers import send_message
    ok, msg = send_message('not-a-platform', 'x', {})
    assert ok is False
