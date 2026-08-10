# -*- coding: utf-8 -*-
"""ارسال پیامک واقعی — کاوه‌نگار، ملی‌پیامک، فرازاس‌ام‌اس + حالت دمو
فقط API Key را در پنل مدیریت وارد کنید.
"""
import requests
from validators import http_request
from validators import log_exc as _lexc

PROVIDERS = {
    'demo': dict(name='حالت دمو (بدون ارسال)', fields=['sms_provider']),
    'kavenegar': dict(name='کاوه‌نگار', fields=['sms_kavenegar_key', 'sms_kavenegar_sender']),
    'mellipayamak': dict(name='ملی‌پیامک', fields=['sms_melli_username', 'sms_melli_password', 'sms_melli_sender']),
    'farazsms': dict(name='فراز اس‌ام‌اس (ایپنل)', fields=['sms_faraz_token', 'sms_faraz_sender']),
}


def send_sms(phone, text, settings):
    """ارسال پیامک — خروجی (ok, message)"""
    provider = settings.get('sms_provider') or 'demo'
    if provider == 'demo' or provider not in PROVIDERS:
        # ثبت در لاگ برای حالت دمو
        import logging
        logging.getLogger('academy.sms').info(f'SMS(دمو) به {phone}: {text[:80]}')
        return True, 'SMS_DEMO'
    try:
        if provider == 'kavenegar':
            key = settings.get('sms_kavenegar_key', '').strip()
            sender = settings.get('sms_kavenegar_sender', '').strip() or '20005006600660'
            r = http_request("get", f'https://api.kavenegar.com/v1/{key}/sms/send.json',
                             params={'receptor': phone, 'sender': sender, 'message': text},
                             timeout=15)
            data = r.json()
            if data.get('return', {}).get('status') == 200:
                return True, 'کاوه‌نگار: ارسال شد'
            return False, 'کاوه‌نگار: ' + str(data.get('return', {}).get('message', ''))
        if provider == 'mellipayamak':
            r = http_request("post", 'https://rest.payamak-panel.com/api/SendSMS/SendSMS', json={
                'username': settings.get('sms_melli_username', '').strip(),
                'password': settings.get('sms_melli_password', '').strip(),
                'to': phone,
                'from': settings.get('sms_melli_sender', '').strip() or '5000271001',
                'text': text,
            }, timeout=15)
            data = r.json()
            if str(data.get('RetStatus', '')).startswith('1'):
                return True, 'ملی‌پیامک: ارسال شد'
            return False, 'ملی‌پیامک: ' + str(data.get('StrRetStatus', 'خطا'))
        if provider == 'farazsms':
            r = http_request("post", 'https://ippanel.com/api/', json={
                'op': 'send',
                'uname': settings.get('sms_faraz_token', '').split(':')[0] if ':' in settings.get('sms_faraz_token', '') else '',
                'pass': settings.get('sms_faraz_token', '').split(':')[1] if ':' in settings.get('sms_faraz_token', '') else '',
                'from': settings.get('sms_faraz_sender', '').strip(),
                'message': text,
                'to': [phone],
            }, timeout=15)
            data = r.json()
            if data.get('code') in (0, 200) or data.get('result'):
                return True, 'فراز: ارسال شد'
            return False, 'فراز: ' + str(data)[:100]
    except Exception as e:
        return False, f'خطای SMS: {e}'
    return False, 'ارسال نشد'


def send_otp(phone, code, settings):
    """ارسال کد تایید — با قالب کاوه‌نگار اگر موجود باشد"""
    provider = settings.get('sms_provider') or 'demo'
    text = f'کد ورود شما به آکادمی آنلاین: {code}\nاین کد تا ۱۰ دقیقه معتبر است.'
    if provider == 'kavenegar' and settings.get('sms_kavenegar_key', '').strip():
        try:
            key = settings.get('sms_kavenegar_key', '').strip()
            r = http_request("get", f'https://api.kavenegar.com/v1/{key}/verify/lookup.json',
                             params={'receptor': phone, 'token': code,
                                     'template': settings.get('sms_kavenegar_template', '').strip() or ''},
                             timeout=15)
            data = r.json()
            if data.get('return', {}).get('status') == 200:
                return True, 'کد از طریق کاوه‌نگار ارسال شد'
        except Exception:
            _lexc('sms.py')
    return send_sms(phone, text, settings)


def test_sms(settings):
    """تست اتصال به پنل پیامکی"""
    provider = settings.get('sms_provider') or 'demo'
    if provider == 'demo':
        return True, 'حالت دمو فعال است — پیام‌ها در لاگ ثبت می‌شوند. برای ارسال واقعی، پنل را انتخاب کنید.'
    ok, msg = send_sms(settings.get('sms_test_phone', '') or '09120000000',
                       'تست اتصال پیامک آکادمی آنلاین ✅', settings)
    return ok, msg
