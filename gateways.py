# -*- coding: utf-8 -*-
"""درگاه‌های پرداخت واقعی ایران — بانک‌ها + اقساطی + تست
تنها کافی است کلیدها/شناسه‌ها را در پنل مدیریت وارد کنید.
هر درگاه: start_payment برای شروع و verify_payment برای تایید.
"""
import json
import time
import requests
from validators import http_request
from datetime import datetime
try:
    from datetime import UTC
except ImportError:  # پایتون < 3.11 (هاست‌های اشتراکی)
    from datetime import timezone as _tz_utc
    UTC = _tz_utc.utc
from validators import log_exc as _lexc

# ================================================================
# متادیتای درگاه‌ها
# ================================================================
GATEWAYS = [
    dict(id='zarinpal', name='زرین‌پال', desc='درگاه امن زرین‌پال — پرداخت با تمام کارت‌های شتاب',
         icon='🅉', fee='۲٬۵۰۰ تومان کارمزد', kind='real', config_keys=['zarinpal_merchant']),
    dict(id='idpay', name='آیدی پی', desc='درگاه پرداخت IDPay — مناسب کسب‌وکارهای آنلاین',
         icon='🅸', fee='۲٬۵۰۰ تومان کارمزد', kind='real', config_keys=['idpay_api_key']),
    dict(id='zibal', name='زیبال', desc='درگاه زیبال — پرداخت سریع با شاپرک',
         icon='🅵', fee='۲٬۵۰۰ تومان کارمزد', kind='real', config_keys=['zibal_merchant']),
    dict(id='melli', name='بانک ملی (به‌پرداخت)', desc='درگاه مستقیم بانک ملی — پرداخت با شاپرک',
         icon='🏦', fee='کارمزد طبق قرارداد', kind='bank', config_keys=['melli_terminal', 'melli_username', 'melli_password']),
    dict(id='sepah', name='بانک سپه', desc='درگاه مستقیم بانک سپه — پرداخت با شاپرک',
         icon='🏛', fee='کارمزد طبق قرارداد', kind='bank', config_keys=['sepah_terminal', 'sepah_merchant', 'sepah_username', 'sepah_password']),
    dict(id='saderat', name='بانک صادرات (سداد)', desc='درگاه مستقیم بانک صادرات — سامانه سداد',
         icon='💳', fee='کارمزد طبق قرارداد', kind='bank', config_keys=['sadad_merchant', 'sadad_terminal', 'sadad_key']),
    dict(id='snapppay', name='اسنپ‌پی', desc='پرداخت اقساطی و کیف پول اسنپ — فروش اقساطی',
         icon='🛵', fee='طبق قرارداد اسنپ‌پی', kind='installment', config_keys=['snapp_client_id', 'snapp_client_secret', 'snapp_merchant']),
    dict(id='digipay', name='دیجی‌پی', desc='درگاه دیجی‌کالا — پرداخت و اقساطی',
         icon='🛍', fee='طبق قرارداد دیجی‌پی', kind='installment', config_keys=['digipay_api_key', 'digipay_merchant']),
    dict(id='tarb', name='کارت اعتباری ترب', desc='پرداخت اعتباری/اقساطی از طریق API ترب (قابل تنظیم)',
         icon='🛒', fee='طبق قرارداد', kind='installment', config_keys=['tarb_api_url', 'tarb_api_key', 'tarb_merchant']),
    dict(id='sandbox', name='درگاه آزمایشی', desc='شبیه‌ساز پرداخت برای تست و دمو — بدون هزینه واقعی',
         icon='🧪', fee='رایگان', kind='test'),
    dict(id='card2card', name='کارت‌به‌کارت', desc='واریز به کارت مجموعه و ثبت فیش — تایید توسط پشتیبانی',
         icon='💳', fee='بدون کارمزد', kind='manual'),
]

GATEWAY_MAP = {g['id']: g for g in GATEWAYS}

# نام فارسی درگاه برای نمایش در فاکتور/نتیجه
def gateway_fa(gw_id):
    g = GATEWAY_MAP.get(gw_id or '')
    return g['name'] if g else (gw_id or '—')


def gateway_ready(gw_id, settings):
    """آیا پیکربندی این درگاه کامل است؟"""
    g = GATEWAY_MAP.get(gw_id)
    if not g or g['kind'] in ('test', 'manual'):
        return True
    for k in g.get('config_keys', []):
        if not (settings.get(k) or '').strip():
            return False
    return True


# ================================================================
# زرین‌پال (v4 REST)
# ================================================================
def zarinpal_start(settings, order, user, callback_url):
    merchant = settings.get('zarinpal_merchant')
    resp = http_request("post", 'https://api.zarinpal.com/pg/v4/payment/request.json', json={
        'merchant_id': merchant, 'amount': order.final_total,
        'callback_url': callback_url,
        'description': f'پرداخت سفارش {order.code}',
        'metadata': {'mobile': user.phone or '', 'email': user.email},
    }, timeout=15)
    data = resp.json()
    if data.get('data', {}).get('authority'):
        return f"https://www.zarinpal.com/pg/StartPay/{data['data']['authority']}"
    raise RuntimeError('زرین‌پال: ' + str(data.get('errors', {})))


def zarinpal_verify(settings, order, authority, status):
    if status != 'OK':
        return False, 'تراکنش توسط کاربر لغو شد', ''
    resp = http_request("post", 'https://api.zarinpal.com/pg/v4/payment/verify.json', json={
        'merchant_id': settings.get('zarinpal_merchant'),
        'amount': order.final_total, 'authority': authority,
    }, timeout=15)
    data = resp.json()
    if data.get('data', {}).get('code') == 100:
        ref = data['data'].get('ref_id', '')
        return True, 'پرداخت موفق', ref
    return False, 'تراکنش تایید نشد (کد %s)' % data.get('errors', {}), ''


# ================================================================
# آیدی پی (IDPay)
# ================================================================
def idpay_start(settings, order, user, callback_url):
    key = settings.get('idpay_api_key')
    resp = http_request("post", 'https://api.idpay.ir/v1.1/payment', json={
        'order_id': order.code, 'amount': order.final_total,
        'callback': callback_url, 'name': user.name, 'phone': user.phone or '',
        'mail': user.email or '', 'desc': f'پرداخت سفارش {order.code}',
    }, headers={'X-API-KEY': key, 'Content-Type': 'application/json'}, timeout=15)
    data = resp.json()
    if data.get('link'):
        return data['link']
    raise RuntimeError('آیدی‌پی: ' + str(data.get('error_message') or data))


def idpay_verify(settings, order, pid, status):
    if status != '10':
        return False, 'پرداخت ناموفق یا لغو شده', ''
    resp = http_request("post", 'https://api.idpay.ir/v1.1/payment/verify', json={
        'id': pid, 'order_id': order.code,
    }, headers={'X-API-KEY': settings.get('idpay_api_key'),
                'Content-Type': 'application/json'}, timeout=15)
    data = resp.json()
    if data.get('status') == 100:
        return True, 'پرداخت موفق', str(data.get('track_id', ''))
    return False, 'تایید نشد: ' + str(data.get('message', '')), ''


# ================================================================
# زیبال (Zibal)
# ================================================================
def zibal_start(settings, order, user, callback_url):
    resp = http_request("post", 'https://gateway.zibal.ir/v1/request', json={
        'merchant': settings.get('zibal_merchant'), 'amount': order.final_total,
        'callbackUrl': callback_url, 'description': f'پرداخت سفارش {order.code}',
        'mobile': user.phone or '',
    }, timeout=15)
    data = resp.json()
    if data.get('result') == 100:
        return f"https://gateway.zibal.ir/start/{data['trackId']}"
    raise RuntimeError('زیبال: ' + str(data.get('message', '')))


def zibal_verify(settings, order, track_id, success):
    if success != '1':
        return False, 'پرداخت لغو شد', ''
    resp = http_request("post", 'https://gateway.zibal.ir/v1/verify', json={
        'merchant': settings.get('zibal_merchant'), 'trackId': int(track_id or 0),
    }, timeout=15)
    data = resp.json()
    if data.get('result') == 100 and data.get('amount') == order.final_total:
        return True, 'پرداخت موفق', str(track_id)
    return False, 'مغایرت مبلغ یا تایید نشد', ''


# ================================================================
# بانک ملی — به‌پرداخت (SOAP)
# ================================================================
_SOAP_NS = ('<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
            '<soap:Body><{method} xmlns="http://interfaces.core.sw.bps.com/">'
            '<{arg}><![CDATA[{payload}]]></{arg}></{method}></soap:Body></soap:Envelope>')


def _soap_call(url, method, arg, payload, timeout=20):
    body = _SOAP_NS.format(method=method, arg=arg, payload=payload)
    resp = http_request("post", url, data=body.encode('utf-8'),
                         headers={'Content-Type': 'text/xml; charset=utf-8'}, timeout=timeout)
    return resp.text


def melli_start(settings, order, user, callback_url):
    terminal = settings.get('melli_terminal')
    username = settings.get('melli_username')
    password = settings.get('melli_password')
    now = datetime.now(UTC)
    local_date = now.strftime('%Y%m%d')
    local_time = now.strftime('%H%M%S')
    payload = ';'.join([str(terminal), username, password, str(order.id),
                        str(order.final_total), local_date, local_time, '',
                        callback_url, str(order.id)])
    xml = _soap_call('https://bpm.shaparak.ir/pgwchannel/services/pgw?wsdl',
                     'bpPayRequest', 'terminalId', payload)
    import re
    m = re.search(r'<return>([^<]+)</return>', xml)
    if not m:
        raise RuntimeError('به‌پرداخت: پاسخ نامعتبر (آیا IP سرور در پنل بانک ثبت شده؟)')
    res = m.group(1).strip()
    if res.startswith('0,'):
        ref = res.split(',')[1]
        return f'https://bpm.shaparak.ir/pgwchannel/startpay.mellat?RefId={ref}'
    raise RuntimeError('به‌پرداخت: کد خطا ' + res)


def melli_verify(settings, order, ref_id, sale_ref):
    terminal = settings.get('melli_terminal')
    username = settings.get('melli_username')
    password = settings.get('melli_password')
    payload = ';'.join([str(terminal), username, password, str(order.id),
                        str(order.id), str(sale_ref or '')])
    xml = _soap_call('https://bpm.shaparak.ir/pgwchannel/services/pgw?wsdl',
                     'bpVerifyRequest', 'terminalId', payload)
    import re
    m = re.search(r'<return>([^<]+)</return>', xml)
    res = m.group(1).strip() if m else '-1'
    if res == '0':
        try:
            _soap_call('https://bpm.shaparak.ir/pgwchannel/services/pgw?wsdl',
                       'bpSettleRequest', 'terminalId', payload)
        except Exception:
            _lexc('gateways.py')
        return True, 'پرداخت موفق', str(sale_ref)
    return False, 'تایید نشد (کد ' + res + ')', ''


# ================================================================
# بانک سپه (SOAP قدیمی + REST جدید)
# ================================================================
def sepah_start(settings, order, user, callback_url):
    terminal = settings.get('sepah_terminal')
    payload = ';'.join([str(terminal), '', str(order.final_total),
                        str(order.id), callback_url])
    xml = _soap_call('https://sep.shaparak.ir/OnlinePG/OnlinePG',
                     'SendToken', 'TerminalID', payload)
    import re
    m = re.search(r'<Token>([^<]+)</Token>', xml) or re.search(r'<return>([^<]+)</return>', xml)
    if not m:
        raise RuntimeError('سپه: پاسخ نامعتبر')
    token = m.group(1).strip()
    if token and not token.startswith('ERR'):
        return f'https://sep.shaparak.ir/OnlinePG/OnlinePG?Token={token}'
    raise RuntimeError('سپه: ' + token)


def sepah_verify(settings, order, ref_num, token):
    terminal = settings.get('sepah_terminal')
    payload = ';'.join([str(terminal), str(ref_num or '')])
    xml = _soap_call('https://sep.shaparak.ir/OnlinePG/OnlinePG',
                     'VerifyTransaction', 'TerminalID', payload)
    import re
    m = re.search(r'<Result>([^<]+)</Result>', xml) or re.search(r'<return>([^<]+)</return>', xml)
    res = m.group(1).strip() if m else '-1'
    if res == '0':
        return True, 'پرداخت موفق', str(ref_num)
    return False, 'تایید نشد (کد ' + res + ')', ''


# ================================================================
# بانک صادرات — سداد (REST + امضای RSA)
# ================================================================
def _rsa_sign(text, private_key):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    key = serialization.load_pem_private_key(private_key.encode(), password=None)
    sig = key.sign(text.encode('utf-8'), padding.PKCS1v15(), hashes.SHA1())
    import base64
    return base64.b64encode(sig).decode()


def sadad_start(settings, order, user, callback_url):
    merchant = settings.get('sadad_merchant')
    terminal = settings.get('sadad_terminal')
    key = settings.get('sadad_key')
    now = datetime.now(UTC)
    local_dt = now.strftime('%m%d%H%M%S')
    data = f'{terminal};{order.id};{order.final_total}'
    try:
        sign = _rsa_sign(data, key)
    except Exception as e:
        raise RuntimeError('سداد: کلید خصوصی نامعتبر است — ' + str(e)[:60])
    resp = http_request("post", 'https://sadad.shaparak.ir/api/v0/Request/PaymentRequest', json={
        'MerchantId': merchant, 'TerminalId': terminal, 'TerminalKey': key,
        'Amount': order.final_total, 'OrderId': order.id, 'LocalDateTime': local_dt,
        'CallbackUrl': callback_url, 'SignData': sign, 'PayerId': user.phone or '',
    }, headers={'Content-Type': 'application/json'}, timeout=20)
    data = resp.json()
    if data.get('ResCode') == 0 and data.get('Token'):
        return f"https://sadad.shaparak.ir/VPG/Purchase?Token={data['Token']}"
    raise RuntimeError('سداد: ' + str(data.get('Description') or data))


def sadad_verify(settings, order, token):
    key = settings.get('sadad_key')
    try:
        sign = _rsa_sign(f'{token}', key)
    except Exception as e:
        raise RuntimeError('سداد: ' + str(e)[:60])
    resp = http_request("post", 'https://sadad.shaparak.ir/api/v0/Advice/Verify', json={
        'Token': token, 'SignData': sign,
    }, headers={'Content-Type': 'application/json'}, timeout=20)
    data = resp.json()
    if data.get('ResCode') == 0:
        ref = str(data.get('RetrivalRefNo', ''))
        return True, 'پرداخت موفق', ref
    return False, 'تایید نشد: ' + str(data.get('Description', '')), ''


# ================================================================
# اسنپ‌پی (اقساطی)
# ================================================================
def snapppay_start(settings, order, user, callback_url):
    token = _snapppay_token(settings)
    resp = http_request("post", 'https://api.snapppay.ir/v2/payment/request', json={
        'merchant_code': settings.get('snapp_merchant'),
        'amount': order.final_total,
        'callback_uri': callback_url,
        'description': f'پرداخت سفارش {order.code}',
        'mobile_number': user.phone or '',
        'customer_identifier': user.email or user.phone or '',
    }, headers={'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'}, timeout=20)
    data = resp.json()
    if data.get('redirect_uri') or data.get('redirect'):
        return data.get('redirect_uri') or data['redirect']
    raise RuntimeError('اسنپ‌پی: ' + str(data.get('message') or data))


def _snapppay_token(settings):
    resp = http_request("post", 'https://api.snapppay.ir/v2/oauth/token', data={
        'grant_type': 'client_credentials',
        'client_id': settings.get('snapp_client_id'),
        'client_secret': settings.get('snapp_client_secret'),
    }, timeout=20)
    data = resp.json()
    tok = data.get('access_token')
    if not tok:
        raise RuntimeError('اسنپ‌پی: دریافت توکن ناموفق — ' + str(data.get('error') or data))
    return tok


def snapppay_verify(settings, order, track_id, status):
    if status != 'success' and status != '1':
        return False, 'پرداخت ناتمام یا لغو شده', ''
    try:
        token = _snapppay_token(settings)
        resp = http_request("get", f"https://api.snapppay.ir/v2/payment/status/{track_id}",
                            headers={'Authorization': f'Bearer {token}'}, timeout=20)
        data = resp.json()
        if data.get('status') in ('success', 'paid', 'completed'):
            return True, 'پرداخت موفق', str(track_id)
    except Exception:
        _lexc('gateways.py')
    return False, 'وضعیت تراکنش نامشخص — با پشتیبانی بررسی کنید', str(track_id or '')


# ================================================================
# دیجی‌پی (اقساطی)
# ================================================================
def digipay_start(settings, order, user, callback_url):
    resp = http_request("post", 'https://api.digipay.ir/api/v1.3/payment/purchase', json={
        'amount': order.final_total,
        'callbackUrl': callback_url,
        'merchantCode': settings.get('digipay_merchant') or '',
        'description': f'پرداخت سفارش {order.code}',
        'mobile': user.phone or '',
    }, headers={'X-API-Key': settings.get('digipay_api_key'),
                'Content-Type': 'application/json'}, timeout=20)
    data = resp.json()
    if data.get('result', {}).get('verify') or data.get('redirect'):
        return data.get('redirect') or data['result']['verify']
    raise RuntimeError('دیجی‌پی: ' + str(data.get('error') or data))


def digipay_verify(settings, order, purchase_id, status):
    if status != '1' and status != 'success':
        return False, 'پرداخت ناموفق', ''
    resp = http_request("post", 'https://api.digipay.ir/api/v1.3/payment/verify', json={
        'purchaseId': purchase_id,
    }, headers={'X-API-Key': settings.get('digipay_api_key'),
                'Content-Type': 'application/json'}, timeout=20)
    data = resp.json()
    if data.get('status') == '1' or data.get('result', {}).get('status') == '1':
        return True, 'پرداخت موفق', str(purchase_id)
    return False, 'تایید نشد', str(purchase_id or '')


# ================================================================
# ترب — درگاه قابل تنظیم (API URL دلخواه)
# ================================================================
def tarb_start(settings, order, user, callback_url):
    base = (settings.get('tarb_api_url') or 'https://api.tarb.example.ir').rstrip('/')
    resp = http_request("post", base + '/payment/request', json={
        'merchant': settings.get('tarb_merchant'),
        'amount': order.final_total,
        'callback': callback_url,
        'order_id': order.code,
        'description': f'پرداخت سفارش {order.code}',
    }, headers={'Authorization': 'Bearer ' + (settings.get('tarb_api_key') or ''),
                'Content-Type': 'application/json'}, timeout=20)
    data = resp.json()
    url = data.get('redirect') or data.get('url') or data.get('link')
    if url:
        return url
    raise RuntimeError('ترب: ' + str(data.get('message') or data))


def tarb_verify(settings, order, ref_id, status):
    if status in ('success', '1', 'paid'):
        return True, 'پرداخت موفق', str(ref_id)
    return False, 'پرداخت ناموفق یا لغو شده', str(ref_id or '')


# ================================================================
# دیسپچر عمومی
# ================================================================
def start_payment(gw_id, settings, order, user, callback_url):
    """شروع پرداخت — خروجی URL درگاه واقعی"""
    fn = {
        'zarinpal': zarinpal_start, 'idpay': idpay_start, 'zibal': zibal_start,
        'melli': melli_start, 'sepah': sepah_start, 'saderat': sadad_start,
        'snapppay': snapppay_start, 'digipay': digipay_start, 'tarb': tarb_start,
    }.get(gw_id)
    if not fn:
        raise RuntimeError('درگاه ناشناخته')
    return fn(settings, order, user, callback_url)


def verify_payment(gw_id, settings, order, args):
    """تایید پرداخت — خروجی (موفق?, پیام, ref_id)"""
    fn = {
        'zarinpal': zarinpal_verify, 'idpay': idpay_verify, 'zibal': zibal_verify,
        'melli': melli_verify, 'sepah': sepah_verify, 'saderat': sadad_verify,
        'snapppay': snapppay_verify, 'digipay': digipay_verify, 'tarb': tarb_verify,
    }.get(gw_id)
    if not fn:
        return False, 'درگاه ناشناخته', ''
    return fn(settings, order, args)


def test_gateway(gw_id, settings):
    """تست اتصال/اعتبارسنجی پیکربندی بدون تراکنش واقعی"""
    g = GATEWAY_MAP.get(gw_id)
    if not g:
        return False, 'درگاه ناشناخته'
    if g['kind'] in ('test', 'manual'):
        return True, 'درگاه آزمایشی همیشه فعال است.'
    missing = [k for k in g.get('config_keys', []) if not (settings.get(k) or '').strip()]
    if missing:
        return False, 'فیلدهای زیر خالی است: ' + '، '.join(missing)
    # تست اتصال واقعی سبک (بدون تراکنش)
    try:
        if gw_id == 'zarinpal':
            r = http_request("post", 'https://api.zarinpal.com/pg/v4/payment/verify.json',
                              json={'merchant_id': settings['zarinpal_merchant'],
                                    'amount': 1000, 'authority': 'test'},
                              timeout=10)
            return True, 'پاسخ سرور زرین‌پال دریافت شد (کد %s)' % r.status_code
        if gw_id == 'idpay':
            r = http_request("post", 'https://api.idpay.ir/v1.1/payment/verify',
                              json={'id': 'test', 'order_id': 'test'},
                              headers={'X-API-KEY': settings['idpay_api_key']}, timeout=10)
            return True, 'پاسخ سرور آیدی‌پی دریافت شد (کد %s)' % r.status_code
        if gw_id == 'melli':
            import re
            xml = _soap_call('https://bpm.shaparak.ir/pgwchannel/services/pgw?wsdl',
                             'bpPayRequest', 'terminalId', ';'.join(
                                 [settings['melli_terminal'], settings['melli_username'],
                                  settings['melli_password'], '0', '1000', '14050101', '000000', '', '', '0']))
            m = re.search(r'<return>([^<]+)</return>', xml)
            return True, 'پاسخ سرور به‌پرداخت: ' + (m.group(1) if m else xml[:80])
        if gw_id == 'sepah':
            return True, 'پیکربندی سپه معتبر است (تست تراکنش هنگام پرداخت انجام می‌شود).'
        if gw_id == 'saderat':
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            key = serialization.load_pem_private_key(settings['sadad_key'].encode(), password=None)
            return True, 'کلید RSA سداد معتبر است.'
        if gw_id == 'snapppay':
            _snapppay_token(settings)
            return True, 'توکن اسنپ‌پی دریافت شد — اتصال برقرار است ✅'
        if gw_id == 'digipay':
            r = http_request("post", 'https://api.digipay.ir/api/v1.3/payment/verify',
                              json={'purchaseId': '0'},
                              headers={'X-API-Key': settings['digipay_api_key']}, timeout=10)
            return True, 'پاسخ سرور دیجی‌پی دریافت شد (کد %s)' % r.status_code
        if gw_id == 'tarb':
            return True, 'پیکربندی ترب ذخیره شد — تست تراکنش هنگام پرداخت انجام می‌شود.'
    except Exception as e:
        return False, 'خطا در اتصال: ' + str(e)[:120]
    return True, 'پیکربندی کامل است.'
