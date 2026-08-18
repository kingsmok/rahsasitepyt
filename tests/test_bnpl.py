# -*- coding: utf-8 -*-
"""تست پنل اقساطی (BNPL) — اسنپ‌پی / ترب / دیجی‌پی."""
import re
from conftest import login


def _csrf(client, path):
    r = client.get(path)
    m = re.search(r'name="_csrf_token" value="([^\"]+)"', r.text)
    assert m, f'CSRF not found on {path}'
    return m.group(1)


# ---------------------------------------------------------------
# محاسبهٔ برنامهٔ اقساط
# ---------------------------------------------------------------
def test_installment_schedule_sums_to_total():
    import bnpl
    for n in (2, 3, 4):
        sched = bnpl.installment_schedule(1000000, n)
        assert sum(p['amount'] for p in sched) == 1000000
        assert len(sched) == n
        # قسط اول (پیش‌پرداخت) بزرگ‌تر یا مساوی بقیه است
        assert sched[0]['amount'] >= sched[1]['amount']


def test_installment_schedule_with_fee():
    import bnpl
    sched = bnpl.installment_schedule(100000, 4, fee_pct=10)
    assert sum(p['amount'] for p in sched) == 110000  # 10٪ کارمزد


def test_build_installments_persists(monkeypatch, app):
    import bnpl
    from models import Order, OrderItem, Installment, db
    with app.app_context():
        o = Order(code='INST-TEST-1', user_id=1, total=400000, final_total=400000,
                  status='pending')
        db.session.add(o)
        db.session.flush()
        db.session.add(OrderItem(order_id=o.id, course_id=1, price=400000))
        db.session.commit()
        oid = o.id
        sched = bnpl.build_installments(o, 4)
        rows = Installment.query.filter_by(order_id=o.id).order_by(Installment.number).all()
        assert len(rows) == 4
        assert sum(i.amount for i in rows) == 400000
        assert o.installment_count == 4
        db.session.query(Installment).filter_by(order_id=o.id).delete()
        db.session.query(OrderItem).filter_by(order_id=o.id).delete()
        db.session.query(Order).filter_by(id=o.id).delete()
        db.session.commit()


# ---------------------------------------------------------------
# پنل اقساطی — از checkout تا انتخاب سرویس و شروع پرداخت
# ---------------------------------------------------------------
def test_checkout_with_installment_goes_to_bnpl(client, app):
    login(client, 'demo@test.ir', 'demo123')
    client.post('/api/cart/add', json={'course_id': 1})
    tok = _csrf(client, '/checkout')
    r = client.post('/checkout', data={'_csrf_token': tok, 'action': 'create_order',
                                       'installment_count': '4'}, follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers['Location']
    assert '/bnpl/' in loc  # سفارش اقساطی باید به پنل اقساطی برود


def test_bnpl_page_shows_three_providers(client, app):
    login(client, 'demo@test.ir', 'demo123')
    client.post('/api/cart/add', json={'course_id': 1})
    tok = _csrf(client, '/checkout')
    r = client.post('/checkout', data={'_csrf_token': tok, 'action': 'create_order',
                                       'installment_count': '3'}, follow_redirects=False)
    code = r.headers['Location'].split('/bnpl/')[-1]
    r = client.get(f'/bnpl/{code}')
    assert r.status_code == 200
    for name in ['اسنپ‌پی', 'کارت اعتباری ترب', 'دیجی‌پی']:
        assert name in r.text, name
    assert 'پنل خرید اقساطی' in r.text


def test_bnpl_start_sets_gateway_and_installments(client, app):
    login(client, 'demo@test.ir', 'demo123')
    client.post('/api/cart/add', json={'course_id': 1})
    tok = _csrf(client, '/checkout')
    r = client.post('/checkout', data={'_csrf_token': tok, 'action': 'create_order',
                                       'installment_count': '3'}, follow_redirects=False)
    code = r.headers['Location'].split('/bnpl/')[-1]
    # انتخاب دیجی‌پی + ۴ قسط
    tok = _csrf(client, f'/bnpl/{code}')
    r = client.post(f'/bnpl/{code}/start', data={'_csrf_token': tok,
                                                 'gateway': 'digipay', 'num': '4'},
                    follow_redirects=False)
    assert r.status_code == 302
    # باید به pay_start با درگاه از پیش انتخاب‌شده هدایت شود
    assert '/pay/' in r.headers['Location']
    from models import Order, Installment, db
    with app.app_context():
        o = Order.query.filter_by(code=code).first()
        assert o is not None
        assert o.gateway == 'digipay'
        assert o.installment_count == 4
        rows = Installment.query.filter_by(order_id=o.id).count()
        assert rows == 4
        db.session.query(Installment).filter_by(order_id=o.id).delete()
        db.session.query(Order).filter_by(id=o.id).delete()
        db.session.commit()


def test_bnpl_start_rejects_invalid_gateway(client, app):
    login(client, 'demo@test.ir', 'demo123')
    client.post('/api/cart/add', json={'course_id': 1})
    tok = _csrf(client, '/checkout')
    r = client.post('/checkout', data={'_csrf_token': tok, 'action': 'create_order',
                                       'installment_count': '2'}, follow_redirects=False)
    code = r.headers['Location'].split('/bnpl/')[-1]
    tok = _csrf(client, f'/bnpl/{code}')
    r = client.post(f'/bnpl/{code}/start', data={'_csrf_token': tok,
                                                 'gateway': 'zarinpal', 'num': '4'},
                    follow_redirects=False)
    assert r.status_code == 302
    assert f'/bnpl/{code}' in r.headers['Location']  # برگشت به پنل
    from models import Order, db
    with app.app_context():
        o = Order.query.filter_by(code=code).first()
        assert o.gateway != 'zarinpal'
        db.session.query(Order).filter_by(id=o.id).delete()
        db.session.commit()


def test_gateway_page_preselects_installment_provider(client, app, monkeypatch):
    """پس از شروع از پنل اقساطی، درگاه اقساطی در صفحهٔ پرداخت از پیش انتخاب شده باشد."""
    login(client, 'demo@test.ir', 'demo123')
    client.post('/api/cart/add', json={'course_id': 1})
    tok = _csrf(client, '/checkout')
    r = client.post('/checkout', data={'_csrf_token': tok, 'action': 'create_order',
                                       'installment_count': '4'}, follow_redirects=False)
    code = r.headers['Location'].split('/bnpl/')[-1]
    tok = _csrf(client, f'/bnpl/{code}')
    client.post(f'/bnpl/{code}/start', data={'_csrf_token': tok,
                                             'gateway': 'snapppay', 'num': '4'},
                follow_redirects=False)
    # صفحهٔ انتخاب درگاه باید snapppay را انتخاب‌شده نشان دهد
    r = client.get(f'/pay/{code}')
    assert 'name="gateway" value="snapppay" class="hide" checked' in r.text
    from models import Order, Installment, db
    with app.app_context():
        db.session.query(Installment).filter_by(order_id=Order.query.filter_by(code=code).first().id).delete()
        db.session.query(Order).filter_by(code=code).delete()
        db.session.commit()


# ---------------------------------------------------------------
# تست سرتاسری: پنل اقساطی → درگاه اسنپ‌پی → تأیید → سفارش paid
# ---------------------------------------------------------------
def test_bnpl_full_snapppay_flow(client, app, monkeypatch):
    """انتخاب اسنپ‌پی در پنل اقساطی → شروع پرداخت از درگاه اسنپ‌پی → تأیید → paid."""
    import gateways
    from models import Order, OrderItem, Installment, Enrollment, db

    class _FakeResp:
        def __init__(self, payload):
            self.payload = payload
            self.status_code = 200

        def json(self):
            return self.payload

    def fake_http(method, url, **kwargs):
        if 'oauth/token' in url:
            return _FakeResp({'access_token': 'TOK-1'})
        if 'v2/payment/request' in url:
            return _FakeResp({'redirect_uri': 'https://snapp.link/BNPL-1'})
        if 'v2/payment/status/' in url:
            return _FakeResp({'status': 'success'})
        raise AssertionError('unexpected url: ' + url)

    monkeypatch.setattr(gateways, 'http_request', fake_http)
    # پیکربندی اسنپ‌پی
    from models import Setting
    with app.app_context():
        for k, v in [('sandbox_mode', '0'), ('snapp_client_id', 'cid'),
                     ('snapp_client_secret', 'csec'), ('snapp_merchant', 'm')]:
            s = db.session.get(Setting, k)
            if s:
                s.value = v
            else:
                db.session.add(Setting(key=k, value=v))
        db.session.commit()

    login(client, 'demo@test.ir', 'demo123')
    client.post('/api/cart/add', json={'course_id': 1})
    tok = _csrf(client, '/checkout')
    r = client.post('/checkout', data={'_csrf_token': tok, 'action': 'create_order',
                                       'installment_count': '4'}, follow_redirects=False)
    assert '/bnpl/' in r.headers['Location']
    code = r.headers['Location'].split('/bnpl/')[-1]

    # انتخاب اسنپ‌پی در پنل اقساطی
    tok = _csrf(client, f'/bnpl/{code}')
    r = client.post(f'/bnpl/{code}/start', data={'_csrf_token': tok,
                                                 'gateway': 'snapppay', 'num': '4'},
                    follow_redirects=False)
    assert r.status_code == 302
    # صفحهٔ درگاه → اسنپ‌پی از پیش انتخاب شده → submit
    tok = _csrf(client, f'/pay/{code}')
    r = client.post(f'/pay/{code}', data={'_csrf_token': tok, 'gateway': 'snapppay'},
                    follow_redirects=False)
    assert r.status_code == 302
    assert 'snapp.link/BNPL-1' in r.headers['Location']

    # بازگشت از درگاه
    r = client.get(f'/pay/verify/snapppay?track_id=TX-99&status=success&code={code}',
                   follow_redirects=False)
    assert r.status_code == 302
    assert 'success' in r.headers['Location']

    with app.app_context():
        o = Order.query.filter_by(code=code).first()
        assert o and o.status == 'paid'
        assert o.gateway == 'snapppay'
        assert {row.status for row in Installment.query.filter_by(order_id=o.id)} == {
            'provider_managed'}
        enr = Enrollment.query.filter_by(order_id=o.id).first()
        assert enr is not None
        db.session.query(OrderItem).filter_by(order_id=o.id).delete()
        db.session.query(Installment).filter_by(order_id=o.id).delete()
        db.session.query(Order).filter_by(id=o.id).delete()
        db.session.commit()
