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


def test_cart_items(client, app):
    _make_products(app)
    login(client, 'demo@test.ir', 'demo123')
    with app.app_context():
        p = Product.query.filter_by(slug='mug-test').first()
    client.post('/api/product-cart/add', json={'product_id': p.id})
    r = client.get('/api/cart/items')
    assert r.status_code == 200
