# -*- coding: utf-8 -*-
"""تست درگاه‌های پرداخت واقعی — نگاشت پارامترهای callback در verify_payment."""
import gateways
import pytest


class _FakeResp:
    """پاسخ HTTP ساختگی برای درخواست‌های verify (بدون تماس واقعی با بانک)."""

    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def json(self):
        return self._payload


def _make_order():
    """یک سفارش ساده در حافظه — verify فقط code و final_total را می‌خواند."""
    class O:
        code = 'TEST-1001'
        final_total = 100000
    return O()


def test_zarinpal_verify_maps_callback_params(monkeypatch):
    """پارامترهای Authority/Status از callback باید به zarinpal_verify برسد و پرداخت تایید شود."""
    settings = {'zarinpal_merchant': 'm-123'}

    def fake_http(method, url, **kwargs):
        body = kwargs.get('json') or {}
        assert body.get('authority') == 'AUTH-111'          # پارامتر به‌درستی استخراج شده
        assert body.get('amount') == 100000
        return _FakeResp({'data': {'code': 100, 'ref_id': 'REF-999'}})

    monkeypatch.setattr(gateways, 'http_request', fake_http)
    args = {'Authority': 'AUTH-111', 'Status': 'OK'}
    ok, msg, ref = gateways.verify_payment('zarinpal', settings, _make_order(), args)
    assert ok is True
    assert ref == 'REF-999'


def test_zarinpal_verify_cancelled_by_user(monkeypatch):
    """اگر Status != OK پرداخت لغو شده اعلام می‌شود (بدون تماس با بانک)."""
    args = {'Authority': 'AUTH-111', 'Status': 'NOK'}
    ok, msg, _ = gateways.verify_payment('zarinpal', {'zarinpal_merchant': 'm-123'},
                                         _make_order(), args)
    assert ok is False
    assert 'لغو' in msg


def test_idpay_verify_maps_params(monkeypatch):
    settings = {'idpay_api_key': 'k-1'}

    def fake_http(method, url, **kwargs):
        body = kwargs.get('json') or {}
        assert body.get('id') == 'PID-7'
        assert body.get('order_id') == 'TEST-1001'
        return _FakeResp({'status': 100, 'track_id': 77123456})

    monkeypatch.setattr(gateways, 'http_request', fake_http)
    args = {'id': 'PID-7', 'status': '10'}
    ok, msg, ref = gateways.verify_payment('idpay', settings, _make_order(), args)
    assert ok is True
    assert ref == '77123456'


def test_zibal_verify_maps_params(monkeypatch):
    settings = {'zibal_merchant': 'z-1'}

    def fake_http(method, url, **kwargs):
        body = kwargs.get('json') or {}
        assert body.get('trackId') == 12345
        return _FakeResp({'result': 100, 'amount': 100000})

    monkeypatch.setattr(gateways, 'http_request', fake_http)
    args = {'trackId': '12345', 'success': '1'}
    ok, msg, ref = gateways.verify_payment('zibal', settings, _make_order(), args)
    assert ok is True


def test_sadad_verify_maps_token(monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    pem = key.private_bytes(serialization.Encoding.PEM,
                            serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    settings = {'sadad_key': pem}

    def fake_http(method, url, **kwargs):
        body = kwargs.get('json') or {}
        assert 'Token' in body
        return _FakeResp({'ResCode': 0, 'RetrivalRefNo': '987654'})

    monkeypatch.setattr(gateways, 'http_request', fake_http)
    args = {'Token': 'TOK-555'}
    ok, msg, ref = gateways.verify_payment('saderat', settings, _make_order(), args)
    assert ok is True
    assert ref == '987654'


def test_unknown_gateway_returns_failure():
    ok, msg, ref = gateways.verify_payment('not-a-gateway', {}, _make_order(), {})
    assert ok is False


@pytest.mark.parametrize('gw_id', [
    'zarinpal', 'idpay', 'zibal', 'melli', 'sepah',
    'saderat', 'snapppay', 'digipay', 'tarb',
])
def test_verify_no_typeerror_on_empty_args(gw_id, monkeypatch):
    """با args خالی نباید TypeError بدهد — یعنی نگاشت پارامتر درست است."""
    monkeypatch.setattr(gateways, 'http_request',
                        lambda *a, **k: _FakeResp({'data': {}, 'status': -1, 'result': -1,
                                                   'ResCode': -1, 'message': ''}))
    ok, msg, _ = gateways.verify_payment(gw_id, {}, _make_order(), {})
    assert ok in (True, False)


# ================================================================
# شروع پرداخت (start_payment) برای همه درگاه‌های واقعی
# ================================================================

class _O:
    code = 'TST-900'
    id = 42
    final_total = 250000


class _U:
    phone = '09120000000'
    email = 'u@test.ir'
    name = 'کاربر تست'


_USER = _U()


def test_start_all_real_gateways_return_url(monkeypatch):
    """start_payment برای هر درگاه واقعی باید یک URL (درگاه) برگرداند، نه خطا."""
    def fake_http(method, url, **kwargs):
        if 'zarinpal.com/pg/v4/payment/request' in url:
            return _FakeResp({'data': {'authority': 'A9'}, 'errors': None})
        if 'idpay.ir' in url and '/payment' in url and 'verify' not in url:
            return _FakeResp({'link': 'https://idpay.ir/link-1'})
        if 'gateway.zibal.ir/v1/request' in url:
            return _FakeResp({'result': 100, 'trackId': '555'})
        if 'sadad.shaparak.ir/api/v0/Request/PaymentRequest' in url:
            return _FakeResp({'ResCode': 0, 'Token': 'TKN-1'})
        if 'api.snapppay.ir/v2/payment/request' in url:
            return _FakeResp({'redirect_uri': 'https://snapp.link/x'})
        if 'api.digipay.ir/api/v1.3/payment/purchase' in url:
            return _FakeResp({'redirect': 'https://digipay.link/y', 'result': {'verify': ''}})
        if '/payment/request' in url and 'tarb' in url:
            return _FakeResp({'redirect': 'https://tarb.link/z'})
        if 'api.snapppay.ir/v2/oauth/token' in url:
            return _FakeResp({'access_token': 'TOK'})
        raise AssertionError('unexpected url: ' + url)

    def fake_soap(url, method, arg, payload, timeout=20):
        if method == 'bpPayRequest':
            return '<return>0,REF-11</return>'
        if method == 'SendToken':
            return '<Token>SEP-TOKEN</Token>'
        raise AssertionError('unexpected soap method ' + method)

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    pem = key.private_bytes(serialization.Encoding.PEM,
                            serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()

    settings = {
        'zarinpal_merchant': 'm', 'idpay_api_key': 'k', 'zibal_merchant': 'z',
        'melli_terminal': '1', 'melli_username': 'u', 'melli_password': 'p',
        'sepah_terminal': '2', 'sadad_merchant': 'm2', 'sadad_terminal': '3', 'sadad_key': pem,
        'snapp_client_id': 'c', 'snapp_client_secret': 's', 'snapp_merchant': 'm3',
        'digipay_api_key': 'k2', 'digipay_merchant': 'm4',
        'tarb_api_url': 'https://api.tarb.example.ir', 'tarb_api_key': 'k3', 'tarb_merchant': 'm5',
    }
    monkeypatch.setattr(gateways, 'http_request', fake_http)
    monkeypatch.setattr(gateways, '_soap_call', fake_soap)

    expected = {
        'zarinpal': 'zarinpal.com/pg/StartPay/A9',
        'idpay': 'https://idpay.ir/link-1',
        'zibal': 'gateway.zibal.ir/start/555',
        'melli': 'bpm.shaparak.ir/pgwchannel/startpay.mellat?RefId=REF-11',
        'sepah': 'sep.shaparak.ir/OnlinePG/OnlinePG?Token=SEP-TOKEN',
        'saderat': 'sadad.shaparak.ir/VPG/Purchase?Token=TKN-1',
        'snapppay': 'https://snapp.link/x',
        'digipay': 'https://digipay.link/y',
        'tarb': 'https://tarb.link/z',
    }
    for gw, fragment in expected.items():
        url = gateways.start_payment(gw, settings, _O(), _USER, 'https://cb.ir/verify')
        assert fragment in url, f'{gw}: got {url}'
