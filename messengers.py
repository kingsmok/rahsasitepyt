# -*- coding: utf-8 -*-
"""اتصال به ربات‌های پیام‌رسان ایرانی و خارجی — تلگرام، بله، ایتا، سروش، روبیکا
فقط توکن ربات و آیدی کانال/چت را در پنل مدیریت وارد کنید.
"""
import requests
from validators import http_request

MESSENGERS = [
    dict(id='telegram', name='تلگرام', fa='تلگرام', icon='/static/img/social/telegram.svg',
         color='#229ed9', token_key='msg_telegram_token', chat_key='msg_telegram_chat',
         base='https://api.telegram.org'),
    dict(id='bale', name='بله', fa='بله', icon='/static/img/social/bale.svg',
         color='#1e9e6a', token_key='msg_bale_token', chat_key='msg_bale_chat',
         base='https://api.bale.ai'),
    dict(id='eitaa', name='ایتا', fa='ایتا', icon='/static/img/social/eitaa.svg',
         color='#28a745', token_key='msg_eitaa_token', chat_key='msg_eitaa_chat',
         base='https://eitaayar.ir/api'),
    dict(id='soroush', name='سروش', fa='سروش', icon='/static/img/social/soroush.svg',
         color='#7c3aed', token_key='msg_soroush_token', chat_key='msg_soroush_chat',
         base='https://api.soroush.app'),
    dict(id='rubika', name='روبیکا', fa='روبیکا', icon='/static/img/social/rubika.svg',
         color='#2563eb', token_key='msg_rubika_token', chat_key='msg_rubika_chat',
         base='https://messapi.rubika.ir'),
]

MSG_MAP = {m['id']: m for m in MESSENGERS}


def sanitize_bot_token(raw):
    """استخراج توکن از متن پیست‌شدهٔ BotFather."""
    import re
    raw = (raw or '').strip()
    if not raw:
        return ''
    m = re.search(r'(\d{5,}:[A-Za-z0-9_-]{20,})', raw)
    if m:
        return m.group(1)
    return raw.split()[0][:200]


def sanitize_chat_id(raw):
    """استخراج @channel یا شناسه عددی از متن پیست‌شده."""
    import re
    raw = (raw or '').strip()
    if not raw:
        return ''
    m = re.search(r'(@[A-Za-z0-9_]{4,}|-?\d{5,})', raw)
    if m:
        return m.group(1)
    return raw.split()[0][:80]


def _settings_of(settings):
    """برگرداندن دیکشنری plain از Setting ها"""
    return dict(settings) if isinstance(settings, dict) else {s.key: s.value for s in settings}


def send_message(platform, text, settings, link=None):
    """ارسال پیام به یک پیام‌رسان — خروجی (ok, message)"""
    m = MSG_MAP.get(platform)
    if not m:
        return False, 'پیام‌رسان ناشناخته'
    cfg = _settings_of(settings)
    token = (cfg.get(m['token_key']) or '').strip()
    chat = (cfg.get(m['chat_key']) or '').strip()
    if not token:
        return False, f'توکن ربات {m["fa"]} ثبت نشده'
    full = text + (f'\n🔗 {link}' if link else '')
    try:
        if platform in ('telegram', 'bale', 'eitaa', 'soroush'):
            base = m['base']
            url = f'{base}/bot{token}/sendMessage'
            if platform == 'eitaa':
                url = f'{base}/{token}/sendMessage'
            r = http_request("post", url, json={'chat_id': chat, 'text': full,
                                         'disable_web_page_preview': False},
                              timeout=15)
            data = r.json()
            if data.get('ok'):
                return True, f'{m["fa"]}: ارسال شد'
            return False, f'{m["fa"]}: ' + str(data.get('description', 'خطا'))
        if platform == 'rubika':
            # API روبیکا — روش call با auth
            r = http_request("post", f"{m['base']}/", json={
                'api_version': '6', 'auth': token,
                'method': 'send_message',
                'data': {'chat_id': chat, 'text': full, 'message_type': 0},
            }, timeout=15)
            data = r.json()
            if data.get('status') == 'OK':
                return True, 'روبیکا: ارسال شد'
            return False, 'روبیکا: ' + str(data.get('status_det') or data)[:120]
    except Exception as e:
        return False, f'{m["fa"]}: خطای اتصال — {e}'
    return False, 'ارسال نشد'


def send_to_all(text, settings, link=None):
    """ارسال به همه پیام‌رسان‌های فعال — خروجی نتایج هر کدام"""
    results = {}
    for m in MESSENGERS:
        cfg = _settings_of(settings)
        token = (cfg.get(m['token_key']) or '').strip()
        if not token:
            continue
        ok, msg = send_message(m['id'], text, settings, link)
        results[m['id']] = (ok, msg)
    return results


def test_platform(platform, settings):
    """تست اتصال ربات — فراخوانی getMe"""
    m = MSG_MAP.get(platform)
    if not m:
        return False, 'ناشناخته'
    cfg = _settings_of(settings)
    token = (cfg.get(m['token_key']) or '').strip()
    if not token:
        return False, 'توکن ثبت نشده'
    try:
        if platform in ('telegram', 'bale', 'soroush'):
            r = http_request("get", f"{m['base']}/bot{token}/getMe", timeout=12)
            data = r.json()
            if data.get('ok'):
                bot = data['result'].get('username', '')
                return True, f'✅ ربات @{bot} متصل است'
            return False, str(data.get('description', 'توکن نامعتبر'))
        if platform == 'eitaa':
            r = http_request("get", f"{m['base']}/{token}/getMe", timeout=12)
            data = r.json()
            if data.get('ok'):
                return True, f"✅ ربات {data['result'].get('username','')} متصل است"
            return False, str(data.get('description', 'توکن نامعتبر'))
        if platform == 'rubika':
            r = http_request("post", f"{m['base']}/", json={'api_version': '6', 'auth': token,
                                                     'method': 'get_me'}, timeout=12)
            data = r.json()
            if data.get('status') == 'OK':
                return True, '✅ ربات روبیکا متصل است'
            return False, str(data.get('status_det') or data)[:120]
    except Exception as e:
        return False, f'خطای اتصال: {e}'
    return False, 'نامشخص'
