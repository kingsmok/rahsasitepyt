# -*- coding: utf-8 -*-
"""تست فاز ۱۱ — فیدهای مارکت‌پلیس و وبهوک باسلام"""
import hashlib
import hmac
import json
import re
from xml.dom.minidom import parseString

import pytest
from models import db, Product, Setting, Course
from ext_models import MarketOrder


_TEST_WEBHOOK_SECRET = 'marketplace-test-secret'


@pytest.fixture(autouse=True)
def _configured_webhook_secret(app):
    with app.app_context():
        row = db.session.get(Setting, 'basalam_webhook_secret')
        if row:
            row.value = _TEST_WEBHOOK_SECRET
        else:
            db.session.add(Setting(key='basalam_webhook_secret',
                                   value=_TEST_WEBHOOK_SECRET))
        db.session.commit()


def _post_json(client, url, payload, headers=None):
    raw = json.dumps(payload, ensure_ascii=False)
    h = {
        'Content-Type': 'application/json',
        'X-Basalam-Signature': hmac.new(
            _TEST_WEBHOOK_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest(),
    }
    if headers:
        h.update(headers)
    return client.post(url, data=raw, headers=h)


def test_torob_json_feed_valid(client, app):
    r = client.get('/api/feed/torob.json')
    assert r.status_code == 200
    assert r.headers.get('Cache-Control') == 'no-store'
    d = r.get_json()
    assert d['merchant']['name']
    assert len(d['products']) >= 1
    p = d['products'][0]
    for k in ('id', 'title', 'price', 'availability', 'url', 'image'):
        assert k in p
    # فید نباید تصویر SVG داشته باشد (ترب قبول نمی‌کند)
    assert not any('.svg' in x['image'] for x in d['products'])


def test_torob_xml_well_formed_and_escaped(client, app):
    # عنوان با کاراکتر خاص XML — باید escape شود نه اینکه فید را بشکند
    with app.app_context():
        c = Course.query.filter_by(status='published').first()
        c.title = 'دوره & <تست> "قیمت"'
        db.session.commit()
    r = client.get('/api/feed/torob.xml')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert '&lt;' in body and '&amp;' in body  # escape شده
    parseString(body)  # اگر XML خراب باشد خطا می‌دهد


def test_emalls_json_valid(client):
    r = client.get('/api/feed/emalls.json')
    assert r.status_code == 200
    d = r.get_json()
    assert 'seller' in d and 'products' in d
    assert len(d['products']) >= 1


def test_webhook_refuses_requests_until_secret_is_configured(client, app):
    with app.app_context():
        db.session.get(Setting, 'basalam_webhook_secret').value = ''
        db.session.commit()
    response = client.post('/api/marketplace/basalam/webhook',
                           json={'id': 'NO-SECRET'})
    assert response.status_code == 503


def test_webhook_requires_phone(client):
    r = _post_json(client, '/api/marketplace/basalam/webhook',
                   {'id': 'X-1', 'total': 1000})
    assert r.status_code == 422
    assert r.get_json()['ok'] is False


def test_webhook_rejects_oversized(client):
    big = '{"id":"X-2","total":1,"customer":{"phone":"09120000000"},"items":[' + '[1],' * 80000 + ']}'
    r = client.post('/api/marketplace/basalam/webhook', data=big,
                    headers={'Content-Type': 'application/json'})
    assert r.status_code == 413


def test_webhook_creates_and_updates_order(client, app):
    r = _post_json(client, '/api/marketplace/basalam/webhook',
                   {'id': 'BS-T1', 'total': 350000,
                    'customer': {'name': 'زهرا محمدی', 'phone': '09121112233'},
                    'items': [{'name': 'فنجان', 'qty': 1}], 'status': 'new'})
    assert r.status_code == 200
    assert r.get_json()['ok'] is True
    with app.app_context():
        mo = MarketOrder.query.filter_by(external_id='BS-T1').first()
        assert mo and mo.total == 350000 and mo.customer_phone == '09121112233'
        # به‌روزرسانی همان سفارش — بدون رکورد تکراری
        _post_json(client, '/api/marketplace/basalam/webhook',
                   {'id': 'BS-T1', 'total': 350000,
                    'customer': {'name': 'زهرا محمدی', 'phone': '09121112233'},
                    'status': 'shipped'})
        assert MarketOrder.query.filter_by(external_id='BS-T1').count() == 1
        assert MarketOrder.query.filter_by(external_id='BS-T1').first().status == 'shipped'


def test_webhook_hmac_signature(client, app):
    with app.app_context():
        st = db.session.get(Setting, 'basalam_webhook_secret')
        if st:
            st.value = 'topsecret'
        else:
            db.session.add(Setting(key='basalam_webhook_secret', value='topsecret'))
        db.session.commit()
    import hmac as _hmac, hashlib as _hl
    payload = json.dumps({'id': 'BS-H1', 'total': 1,
                          'customer': {'name': 'ت', 'phone': '09121112233'}},
                         ensure_ascii=False)
    # بدون امضا → 403
    r = client.post('/api/marketplace/basalam/webhook', data=payload,
                    headers={'Content-Type': 'application/json'})
    assert r.status_code == 403
    # امضای درست → 200
    sig = _hmac.new(b'topsecret', payload.encode(), _hl.sha256).hexdigest()
    r = client.post('/api/marketplace/basalam/webhook', data=payload,
                    headers={'Content-Type': 'application/json',
                             'X-Basalam-Signature': sig})
    assert r.status_code == 200


def test_sitemap_xml_valid(client, app):
    """sitemap.xml باید XML معتبر باشد — قبلاً تگ image:loc اشتباه بسته می‌شد"""
    with app.app_context():
        from models import BlogPost
        if not BlogPost.query.first():
            db.session.add(BlogPost(title='مطلب تست', slug='post-1',
                                    excerpt='م', body='م', published=True,
                                    image='cover-test.webp'))
            db.session.commit()
    from xml.parsers import expat
    r = client.get('/sitemap.xml')
    assert r.status_code == 200
    assert r.headers.get('Cache-Control') == 'public, max-age=3600'
    p = expat.ParserCreate()
    p.Parse(r.get_data(as_text=True), True)  # خطا = شکست تست
    assert '<url>' in r.get_data(as_text=True)
