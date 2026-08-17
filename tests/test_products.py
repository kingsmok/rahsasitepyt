# -*- coding: utf-8 -*-
"""تست فروشگاه محصولات — فهرست، جزئیات، سبد، سفارش."""
import re
from conftest import login
from models import db, Product, Order


def _make_products(app):
    with app.app_context():
        if Product.query.count() == 0:
            db.session.add(Product(title='ماگ تست', slug='mug-test', price=100000,
                                   discount_price=80000, is_active=True, stock=5, featured=True))
            db.session.add(Product(title='لیوان تست', slug='glass-test', price=50000,
                                   discount_price=0, is_active=True, stock=10))
            db.session.commit()
        return [p.id for p in Product.query.all()]


def _csrf(client, path):
    response = client.get(path)
    match = re.search(r'name="_csrf_token" value="([^"]+)"', response.text)
    assert match
    return match.group(1)


def test_products_list_page(client, app):
    _make_products(app)
    r = client.get('/products')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'ماگ تست' in body


def test_product_detail_page(client, app):
    _make_products(app)
    with app.app_context():
        p = Product.query.filter_by(slug='mug-test').first()
    r = client.get(f'/product/{p.slug}')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert p.title in body


def test_product_final_price_with_discount(app):
    _make_products(app)
    with app.app_context():
        p = Product.query.filter_by(slug='mug-test').first()
        assert p.final_price == 80000  # تخفیف اعمال شده
        assert p.has_discount is True
        p2 = Product.query.filter_by(slug='glass-test').first()
        assert p2.final_price == 50000  # بدون تخفیف


def test_add_product_to_cart(client, app):
    _make_products(app)
    login(client, 'demo@test.ir', 'demo123')
    with app.app_context():
        p = Product.query.filter_by(slug='mug-test').first()
    r = client.post('/api/product-cart/add', json={'product_id': p.id})
    assert r.status_code == 200
    assert r.get_json().get('ok') is True


def test_add_product_cart_invalid(client, app):
    _make_products(app)
    login(client, 'demo@test.ir', 'demo123')
    r = client.post('/api/product-cart/add', json={'product_id': 99999})
    assert r.status_code in (400, 404)
    assert client.post('/api/product-cart/add', json={'product_id': 'bad'}).status_code == 400


def test_cart_items(client, app):
    _make_products(app)
    login(client, 'demo@test.ir', 'demo123')
    with app.app_context():
        p = Product.query.filter_by(slug='mug-test').first()
    client.post('/api/product-cart/add', json={'product_id': p.id})
    r = client.get('/api/cart/items')
    assert r.status_code == 200
    assert r.get_json()['items'][0]['quantity'] == 1
    update = client.post('/api/product-cart/quantity', json={'product_id': p.id, 'quantity': 3})
    assert update.status_code == 200
    assert client.get('/api/cart/items').get_json()['items'][0]['quantity'] == 3


def test_physical_order_requires_and_stores_shipping_address(client, app):
    _make_products(app)
    login(client, 'demo@test.ir', 'demo123')
    with app.app_context():
        product = Product.query.filter_by(slug='mug-test').first()
    client.post('/api/product-cart/add', json={'product_id': product.id})
    client.post('/api/product-cart/quantity', json={'product_id': product.id, 'quantity': 2})
    token = _csrf(client, '/checkout')
    missing = client.post('/checkout', data={
        '_csrf_token': token, 'action': 'create_order'
    })
    assert missing.status_code == 400

    token = _csrf(client, '/checkout')
    response = client.post('/checkout', data={
        '_csrf_token': token, 'action': 'create_order',
        'shipping_name': 'تحویل گیرنده', 'shipping_phone': '09120000888',
        'shipping_province': 'تهران', 'shipping_city': 'تهران',
        'shipping_address': 'خیابان آزمایش، پلاک ۱۲',
        'shipping_postal_code': '1234567890',
    }, follow_redirects=False)
    assert response.status_code == 302
    with app.app_context():
        order = Order.query.filter_by(shipping_phone='09120000888').first()
        assert order and order.shipping_city == 'تهران'
        assert order.fulfillment_status == 'processing'
        assert order.items[0].quantity == 2
        assert order.total == 160000
        code = order.code
    assert client.get(f'/invoice/{code}').status_code == 200
    pdf = client.get(f'/invoice/{code}/pdf')
    assert pdf.status_code == 200
    assert pdf.content_type == 'application/pdf'
    assert pdf.data.startswith(b'%PDF-')
    assert len(pdf.data) > 10_000


def test_missing_product_image_uses_real_fallback(client, app):
    _make_products(app)
    with app.app_context():
        product = Product.query.filter_by(slug='mug-test').first()
        product.image = 'deleted-file.jpg'
        db.session.commit()
        assert product.image_url == '/static/img/cover-product-mug.webp'
    response = client.get('/product/mug-test')
    assert response.status_code == 200
    assert '/static/img/cover-product-mug.webp' in response.text
