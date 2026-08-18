# -*- coding: utf-8 -*-
"""تست سرتاسری پرداخت با درگاه واقعی (زرین‌پال) از طریق مسیر واقعی shop.

باعث اطمینان می‌شود که مسیر «شروع پرداخت → بازگشت از درگاه → تایید → paid»
برای درگاه‌های واقعی (نه فقط sandbox) کار می‌کند. تماس‌های HTTP بانک با پاسخ
جعلی جایگزین می‌شوند تا هیچ تراکنش واقعی‌ای انجام نشود.
"""
import re
import gateways
import pytest


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _csrf(client, path):
    r = client.get(path)
    m = re.search(r'name="_csrf_token" value="([^\"]+)"', r.text)
    assert m, f'CSRF not found on {path}'
    return m.group(1)


@pytest.fixture()
def real_gateway_settings(app):
    """روشن کردن زرین‌پال واقعی و خاموش کردن sandbox_mode."""
    from models import Setting, db
    with app.app_context():
        for k, v in [('sandbox_mode', '0'), ('zarinpal_merchant', 'MOCK-MERCHANT')]:
            s = db.session.get(Setting, k)
            if s:
                s.value = v
            else:
                db.session.add(Setting(key=k, value=v))
        db.session.commit()


def test_real_zarinpal_full_flow(client, app, real_gateway_settings, monkeypatch):
    """جریان کامل: سبد → سفارش → انتخاب زرین‌پال → درگاه → بازگشت → تایید → paid."""
    from models import Order, Enrollment, db

    login = __import__('conftest', fromlist=['login']).login
    login(client, 'demo@test.ir', 'demo123')

    # سبد + سفارش
    client.post('/api/cart/add', json={'course_id': 1})
    tok = _csrf(client, '/checkout')
    r = client.post('/checkout', data={'_csrf_token': tok, 'action': 'create_order',
                                       'installment_count': '0'}, follow_redirects=False)
    assert r.status_code == 302
    code = r.headers['Location'].split('/pay/')[-1]

    # شبیه‌سازی پاسخ درگاه زرین‌پال:
    #   start → درگاه URL با authority
    #   verify → code=100 موفق
    def fake_http(method, url, **kwargs):
        if 'payment/request' in url:
            return _FakeResp({'data': {'authority': 'AUTH-E2E-1', 'fee': 2500},
                              'errors': None})
        if 'payment/verify' in url:
            body = kwargs.get('json') or {}
            assert body.get('authority') == 'AUTH-E2E-1', 'authority باید به verify برسد'
            return _FakeResp({'data': {'code': 100, 'ref_id': 'REF-E2E-1'}, 'errors': None})
        raise AssertionError('unexpected url: ' + url)

    monkeypatch.setattr(gateways, 'http_request', fake_http)

    # انتخاب زرین‌پال در صفحه پرداخت → باید به درگاه واقعی ریدایرکت شود (نه شبیه‌ساز)
    tok = _csrf(client, f'/pay/{code}')
    r = client.post(f'/pay/{code}', data={'_csrf_token': tok, 'gateway': 'zarinpal'},
                    follow_redirects=False)
    assert r.status_code == 302
    target = r.headers['Location']
    assert 'zarinpal.com/pg/StartPay/AUTH-E2E-1' in target
    assert '/pay/sandbox/' not in target  # نباید به شبیه‌ساز برود

    # بازگشت از درگاه (callback) → pay_verify
    r = client.get(f'/pay/verify/zarinpal?Authority=AUTH-E2E-1&Status=OK&code={code}',
                   follow_redirects=False)
    assert r.status_code == 302
    assert 'success' in r.headers['Location']

    # سفارش باید paid شود و ثبت‌نام ساخته شود
    with app.app_context():
        order = Order.query.filter_by(code=code).first()
        assert order and order.status == 'paid'
        assert order.gateway == 'zarinpal'
        enr = Enrollment.query.filter_by(order_id=order.id).first()
        assert enr is not None


def test_wallet_topup_uses_real_gateway_and_callback_once(
        client, app, real_gateway_settings, monkeypatch):
    """شارژ کیف پول از سفارش واقعی عبور می‌کند و callback تکراری دوباره شارژ نمی‌کند."""
    from conftest import login
    from models import Order, User, WalletTransaction

    login(client, 'demo@test.ir', 'demo123')
    page = client.get('/dashboard/wallet')
    token = re.search(r'name="_csrf_token" value="([^\"]+)"', page.text).group(1)
    response = client.post('/dashboard/wallet', data={
        '_csrf_token': token, 'amount': '250000',
    }, follow_redirects=False)
    assert response.status_code == 302
    assert '/pay/WAL-' in response.headers['Location']
    code = response.headers['Location'].split('/pay/')[-1]

    def fake_http(method, url, **kwargs):
        if 'payment/request' in url:
            return _FakeResp({'data': {'authority': 'AUTH-WALLET-1'}, 'errors': None})
        if 'payment/verify' in url:
            return _FakeResp({'data': {'code': 100, 'ref_id': 'REF-WALLET-1'},
                              'errors': None})
        raise AssertionError('unexpected url: ' + url)

    monkeypatch.setattr(gateways, 'http_request', fake_http)
    token = _csrf(client, f'/pay/{code}')
    started = client.post(f'/pay/{code}', data={
        '_csrf_token': token, 'gateway': 'zarinpal',
    }, follow_redirects=False)
    assert 'zarinpal.com/pg/StartPay/AUTH-WALLET-1' in started.headers['Location']

    callback = f'/pay/verify/zarinpal?Authority=AUTH-WALLET-1&Status=OK&code={code}'
    verified = client.get(callback, follow_redirects=False)
    assert verified.status_code == 302 and 'success' in verified.headers['Location']
    with app.app_context():
        order = Order.query.filter_by(code=code).one()
        user = User.query.filter_by(email='demo@test.ir').one()
        assert order.status == 'paid'
        assert order.fulfillment_status == 'wallet_topup'
        assert user.wallet_balance == 250000
        assert WalletTransaction.query.filter_by(
            user_id=user.id, type='charge').count() == 1

    repeated = client.get(callback, follow_redirects=False)
    assert repeated.status_code == 302
    with app.app_context():
        user = User.query.filter_by(email='demo@test.ir').one()
        assert user.wallet_balance == 250000
        assert WalletTransaction.query.filter_by(
            user_id=user.id, type='charge').count() == 1


def test_real_gateway_not_offered_when_sandbox_off(client, app, real_gateway_settings):
    """با sandbox خاموش، درگاه آزمایشی نباید در لیست نمایش داده شود و انتخابش رد شود."""
    login = __import__('conftest', fromlist=['login']).login
    login(client, 'demo@test.ir', 'demo123')
    client.post('/api/cart/add', json={'course_id': 1})
    tok = _csrf(client, '/checkout')
    r = client.post('/checkout', data={'_csrf_token': tok, 'action': 'create_order',
                                       'installment_count': '0'}, follow_redirects=False)
    code = r.headers['Location'].split('/pay/')[-1]
    # انتخاب sandbox در حالت غیرآزمایشی → باید رد شود
    tok = _csrf(client, f'/pay/{code}')
    r = client.post(f'/pay/{code}', data={'_csrf_token': tok, 'gateway': 'sandbox'},
                    follow_redirects=False)
    assert r.status_code == 302
    assert '/pay/sandbox/' not in r.headers['Location']
    from models import db
    with app.app_context():
        db.session.query(__import__('models', fromlist=['OrderItem']).OrderItem).delete()
        db.session.query(__import__('models', fromlist=['Order']).Order).delete()
        db.session.commit()
