# -*- coding: utf-8 -*-
"""ارسال پیامک واقعی — بدون fallback نمایشی در نسخهٔ نهایی.

تا زمانی که یک سرویس واقعی کامل پیکربندی نشده باشد، ارسال با پیام روشن ناموفق
می‌شود و هیچ OTP در صفحه یا لاگ ثبت نمی‌شود.
"""
import logging

from validators import http_request
from validators import log_exc as _lexc

log = logging.getLogger('academy.sms')

PROVIDERS = {
    'disabled': dict(name='غیرفعال (بدون ارسال)', fields=[]),
    'kavenegar': dict(name='کاوه‌نگار', fields=['sms_kavenegar_key']),
    'mellipayamak': dict(name='ملی‌پیامک', fields=['sms_melli_username', 'sms_melli_password']),
    'farazsms': dict(name='فراز اس‌ام‌اس (ایپنل)', fields=['sms_faraz_token', 'sms_faraz_sender']),
}


def provider_ready(settings):
    """کامل بودن حداقل تنظیمات سرویس پیامک انتخاب‌شده."""
    provider = (settings.get('sms_provider') or 'disabled').strip()
    meta = PROVIDERS.get(provider)
    if not meta or provider == 'disabled':
        return False
    return all((settings.get(key) or '').strip() for key in meta.get('fields', []))


def _demo_send_allowed(provider):
    """سازگاری محدود با تست‌های خودکار؛ هرگز در production فعال نیست."""
    if provider not in ('', 'demo', 'disabled'):
        return False
    from runtime import demo_features_enabled
    return demo_features_enabled()


def send_sms(phone, text, settings):
    """ارسال پیامک — خروجی ``(موفق، پیام)``."""
    provider = (settings.get('sms_provider') or 'disabled').strip()
    if _demo_send_allowed(provider):
        # فقط محیط تست صریح؛ در سایت نهایی نه متن و نه OTP در لاگ نوشته نمی‌شود.
        return True, 'SMS_TEST'
    if provider not in PROVIDERS or not provider_ready(settings):
        log.warning('SMS skipped: provider is disabled or incomplete')
        return False, 'سامانه پیامک فعال یا کامل پیکربندی نشده است.'
    if not phone:
        return False, 'شماره گیرنده ثبت نشده است.'

    try:
        if provider == 'kavenegar':
            key = settings.get('sms_kavenegar_key', '').strip()
            sender = settings.get('sms_kavenegar_sender', '').strip() or '20005006600660'
            r = http_request('get', f'https://api.kavenegar.com/v1/{key}/sms/send.json',
                             params={'receptor': phone, 'sender': sender, 'message': text},
                             timeout=15)
            data = r.json()
            if data.get('return', {}).get('status') == 200:
                return True, 'کاوه‌نگار: ارسال شد'
            return False, 'کاوه‌نگار: ' + str(data.get('return', {}).get('message', 'خطای ارسال'))

        if provider == 'mellipayamak':
            r = http_request('post', 'https://rest.payamak-panel.com/api/SendSMS/SendSMS', json={
                'username': settings.get('sms_melli_username', '').strip(),
                'password': settings.get('sms_melli_password', '').strip(),
                'to': phone,
                'from': settings.get('sms_melli_sender', '').strip() or '5000271001',
                'text': text,
            }, timeout=15)
            data = r.json()
            if str(data.get('RetStatus', '')).startswith('1'):
                return True, 'ملی‌پیامک: ارسال شد'
            return False, 'ملی‌پیامک: ' + str(data.get('StrRetStatus', 'خطای ارسال'))

        if provider == 'farazsms':
            token = settings.get('sms_faraz_token', '').strip()
            username, password = (token.split(':', 1) + [''])[:2] if ':' in token else ('', '')
            r = http_request('post', 'https://ippanel.com/api/', json={
                'op': 'send', 'uname': username, 'pass': password,
                'from': settings.get('sms_faraz_sender', '').strip(),
                'message': text, 'to': [phone],
            }, timeout=15)
            data = r.json()
            if data.get('code') in (0, 200) or data.get('result'):
                return True, 'فراز: ارسال شد'
            return False, 'فراز: ' + str(data)[:100]
    except Exception as exc:
        log.error('SMS provider error: %s', exc)
        return False, 'ارتباط با سامانه پیامک برقرار نشد. کمی بعد دوباره تلاش کنید.'
    return False, 'پیامک ارسال نشد.'


def send_otp(phone, code, settings):
    """ارسال کد تایید؛ در هیچ مسیر عمومی کد را نمایش یا لاگ نمی‌کند."""
    provider = (settings.get('sms_provider') or 'disabled').strip()
    text = f'کد ورود شما به آکادمی آنلاین: {code}\nاین کد تا ۱۰ دقیقه معتبر است.'
    if provider == 'kavenegar' and provider_ready(settings):
        template = settings.get('sms_kavenegar_template', '').strip()
        if template:
            try:
                key = settings.get('sms_kavenegar_key', '').strip()
                r = http_request('get', f'https://api.kavenegar.com/v1/{key}/verify/lookup.json',
                                 params={'receptor': phone, 'token': code, 'template': template},
                                 timeout=15)
                data = r.json()
                if data.get('return', {}).get('status') == 200:
                    return True, 'کد از طریق کاوه‌نگار ارسال شد'
            except Exception:
                _lexc('sms.py')
    return send_sms(phone, text, settings)


def test_sms(settings):
    """تست اتصال به پنل پیامکی واقعی."""
    if not provider_ready(settings):
        return False, 'ابتدا یک سرویس واقعی را انتخاب و اطلاعات الزامی آن را کامل کنید.'
    phone = (settings.get('sms_test_phone') or '').strip()
    if not phone:
        return False, 'شماره دریافت‌کنندهٔ تست را وارد کنید.'
    return send_sms(phone, 'تست اتصال پیامک آکادمی آنلاین ✅', settings)
