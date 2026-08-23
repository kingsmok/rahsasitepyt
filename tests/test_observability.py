# -*- coding: utf-8 -*-
"""نظارت‌پذیری سطح تجاری — شناسهٔ درخواست و زمینهٔ خطا.

چرا این لایه برای یک محصول تجاری حیاتی است؟
    وقتی مشتری تماس می‌گیرد و می‌گوید «سایت خطا داد»، تیم پشتیبانی باید
    بتواند دقیقاً همان درخواست را در میان هزاران خط لاگ پیدا کند. بدون
    شناسهٔ همبستگی (Correlation ID) این کار عملاً ناممکن است و پشتیبانی
    به حدس‌زدن تبدیل می‌شود — چیزی که در قرارداد SLA قابل دفاع نیست.

قرارداد این ماژول:
    ۱. هر پاسخ باید هدر X-Request-Id داشته باشد.
    ۲. شناسهٔ ارسالی از پراکسی بالادست حفظ شود (زنجیرهٔ ردیابی نشکند).
    ۳. ورودی بیرونی پاک‌سازی شود (جلوگیری از Log Injection).
    ۴. خطاهای مهارشده با زمینهٔ کامل ثبت شوند، نه به‌صورت خشک.
    ۵. هیچ دادهٔ حساسی (رمز، توکن، کد ملی) وارد لاگ نشود.
"""
import io
import logging

from models import Setting, db


def _capture_academy_log():
    """گرفتن خروجی لاگر 'academy' برای بررسی محتوای ثبت‌شده."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger = logging.getLogger('academy')
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    return buf, handler, logger


def test_every_response_has_request_id(client):
    """هر پاسخ باید شناسهٔ درخواست داشته باشد تا قابل ردیابی باشد."""
    for path in ('/', '/courses', '/auth/register'):
        r = client.get(path)
        rid = r.headers.get('X-Request-Id')
        assert rid, 'مسیر {} هدر X-Request-Id ندارد'.format(path)
        assert 1 <= len(rid) <= 64


def test_upstream_request_id_is_preserved(client):
    """شناسهٔ پراکسی بالادست باید حفظ شود تا ردیابی بین‌سرویسی نشکند."""
    r = client.get('/', headers={'X-Request-Id': 'trace-abc-123'})
    assert r.headers.get('X-Request-Id') == 'trace-abc-123'


def test_malicious_request_id_is_sanitized(client):
    """ورودی مخرب نباید وارد فایل لاگ یا هدر پاسخ شود (Log Injection).

    مهاجم می‌تواند با هدر دستکاری‌شده خطوط جعلی به لاگ تزریق کند یا
    هدر پاسخ را بشکند. فقط کاراکترهای امن پذیرفته می‌شوند.
    """
    r = client.get('/', headers={'X-Request-Id': 'evil;DROP TABLE users--<script>'})
    rid = r.headers.get('X-Request-Id', '')
    assert all(ch.isalnum() or ch in '-_' for ch in rid), \
        'شناسهٔ درخواست پاک‌سازی نشده است: {!r}'.format(rid)
    assert '<' not in rid and ';' not in rid


def test_overlong_request_id_is_truncated(client):
    """شناسهٔ بیش از حد بلند باید کوتاه شود (جلوگیری از تورم لاگ)."""
    r = client.get('/', headers={'X-Request-Id': 'A' * 500})
    assert len(r.headers.get('X-Request-Id', '')) <= 64


def test_swallowed_error_is_logged_with_context(client, app):
    """خطای مهارشده باید با شناسه، مسیر و IP ثبت شود — نه خشک و بی‌زمینه.

    سناریو: مدیر JSON نامعتبر در تنظیمات ذخیره می‌کند. صفحه باید سالم
    بالا بیاید (تاب‌آوری) ولی خطا با زمینهٔ کامل در لاگ ثبت شود.
    """
    with app.app_context():
        db.session.add(Setting(key='talent_questions', value='{invalid json'))
        db.session.commit()

    buf, handler, logger = _capture_academy_log()
    try:
        r = client.get('/talent-test')
    finally:
        logger.removeHandler(handler)

    assert r.status_code == 200, 'تنظیمات خراب نباید صفحه را از کار بیندازد'
    out = buf.getvalue()
    assert 'swallowed error' in out, 'خطای مهارشده اصلاً ثبت نشده است'
    assert 'rid=' in out, 'لاگ شناسهٔ درخواست ندارد — ردیابی ممکن نیست'
    assert '/talent-test' in out, 'لاگ مسیر درخواست را ثبت نکرده است'
    assert 'ip=' in out, 'لاگ نشانی IP را ثبت نکرده است'


def test_log_context_contains_no_sensitive_data(client, app):
    """لاگ نباید به منبع نشت اطلاعات شخصی تبدیل شود (حریم خصوصی).

    فقط شناسهٔ عددی کاربر ثبت می‌شود، نه ایمیل/تلفن/کد ملی — وگرنه خودِ
    فایل لاگ یک بدهی امنیتی و حقوقی می‌شد.
    """
    with app.app_context():
        db.session.add(Setting(key='talent_questions', value='{bad'))
        db.session.commit()

    buf, handler, logger = _capture_academy_log()
    try:
        client.get('/talent-test')
    finally:
        logger.removeHandler(handler)

    out = buf.getvalue()
    for leaked in ('@test.ir', 'password', 'password_hash', 'session_token'):
        assert leaked not in out, 'دادهٔ حساس {!r} در لاگ نشت کرده است'.format(leaked)


def test_log_exc_works_without_request_context(app):
    """log_exc در اسکریپت/کار پس‌زمینه (بدون درخواست) نباید خطا بدهد."""
    from validators import log_exc, request_context
    assert request_context() == '', 'خارج از درخواست باید رشتهٔ خالی برگردد'
    try:
        raise ValueError('خطای آزمایشی')
    except ValueError:
        log_exc('tests.background_job')      # نباید استثنا پرتاب کند


def test_log_exc_supports_error_level(app):
    """سطح error برای خطاهای جدی باید پشتیبانی شود (سازگار با گذشته)."""
    from validators import log_exc
    buf, handler, logger = _capture_academy_log()
    logger.setLevel(logging.WARNING)
    try:
        try:
            raise RuntimeError('خطای بحرانی آزمایشی')
        except RuntimeError:
            log_exc('tests.critical', level='error')
    finally:
        logger.removeHandler(handler)
    assert 'خطای بحرانی آزمایشی' in buf.getvalue()
