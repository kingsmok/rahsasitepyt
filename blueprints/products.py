# -*- coding: utf-8 -*-
"""فروشگاه محصولات فیزیکی — لیست، صفحه محصول، سبد و تسویه یکپارچه"""
import re as _re
import random

from flask import (Blueprint, render_template, request, redirect, url_for, flash,
                   g, session, abort, jsonify)

from models import (utcnow, db, User, Product, Order, OrderItem, Enrollment,
                    PaymentLog, Notification, ActivityLog, Category, Course)
from jdates import fa

products_bp = Blueprint('products', __name__)


def _cart_count(cart=None, quantities=None):
    cart = cart if cart is not None else session.get('cart', [])
    quantities = quantities if quantities is not None else (session.get('cart_qty', {}) or {})
    total = 0
    for item in cart:
        if str(item).startswith('p:'):
            try:
                total += max(1, int(quantities.get(str(item), 1) or 1))
            except (TypeError, ValueError):
                total += 1
        else:
            total += 1
    return total


# ---------------------------------------------------------------- لیست محصولات
@products_bp.route('/products')
def product_list():
    q = request.args.get('q', '').strip()
    cat = request.args.get('cat', '').strip()
    sort = request.args.get('sort', 'newest')
    query = Product.query.filter_by(is_active=True)
    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(Product.title.ilike(like), Product.description.ilike(like),
                                    Product.category.ilike(like)))
    if cat:
        query = query.filter(Product.category == cat)
    order = {'newest': Product.created_at.desc(), 'cheap': Product.price.asc(),
             'expensive': Product.price.desc(), 'popular': Product.views.desc()}.get(sort, Product.created_at.desc())
    items = query.order_by(order).all()
    cats = [r[0] for r in db.session.query(Product.category)
            .filter(Product.is_active == True).distinct().all() if r[0]]
    g.seo['title'] = "فروشگاه محصولات — آکادمی آنلاین"
    g.seo['description'] = f"فهرست {len(items)} محصول فعال؛ قیمت، موجودی و مشخصات هر محصول را پیش از خرید بررسی کنید."
    return render_template('products/list.html', items=items, cats=cats, q=q, cat=cat, sort=sort)


# ---------------------------------------------------------------- صفحه محصول
@products_bp.route('/product/<slug>')
def product_detail(slug):
    value = (slug or '').strip()
    if not value:
        abort(404)
    p = Product.query.filter_by(slug=value, is_active=True).first()
    if p is None and value.isdigit():
        # لینک قدیمی با شناسهٔ عددی → ریدایرکت دائمی به آدرس کانونی
        p = Product.query.filter_by(id=int(value), is_active=True).first()
        if p is not None:
            return redirect(url_for('products.product_detail', slug=p.slug), code=301)
    if p is None:
        abort(404)
    p.views = (p.views or 0) + 1
    db.session.commit()
    related = Product.query.filter(Product.category == p.category, Product.id != p.id,
                                   Product.is_active == True).limit(4).all()
    g.seo['title'] = f"{p.title} — فروشگاه آکادمی آنلاین"
    g.seo['description'] = (p.description or '')[:160]
    return render_template('products/detail.html', p=p, related=related)


# ---------------------------------------------------------------- افزودن به سبد (API)
@products_bp.route('/api/product-cart/add', methods=['POST'])
def product_cart_add():
    raw = (request.get_json(silent=True) or {}).get('product_id') if request.is_json else request.form.get('product_id')
    try:
        pid = int(raw or 0)
    except (TypeError, ValueError):
        return jsonify(ok=False, msg='شناسه محصول نامعتبر است'), 400
    p = db.session.get(Product, pid)
    if not p or not p.is_active:
        return jsonify(ok=False, msg='محصول یافت نشد'), 404
    if p.stock is not None and p.stock <= 0:
        return jsonify(ok=False, msg='این محصول ناموجود است'), 400
    cart = session.get('cart', [])
    quantities = session.get('cart_qty', {})
    key = f'p:{p.id}'
    try:
        current = max(0, int(quantities.get(key, 0) or 0))
    except (TypeError, ValueError):
        current = 0
    if current >= int(p.stock or 0):
        return jsonify(ok=False, msg='بیشتر از موجودی قابل افزودن نیست'), 400
    if key not in cart:
        cart.append(key)
    quantities[key] = current + 1
    session['cart'] = cart
    session['cart_qty'] = quantities
    return jsonify(ok=True, count=_cart_count(cart, quantities), quantity=quantities[key], msg='به سبد خرید اضافه شد')


@products_bp.route('/api/product-cart/remove', methods=['POST'])
def product_cart_remove():
    raw = (request.get_json(silent=True) or {}).get('product_id') if request.is_json else request.form.get('product_id')
    try:
        pid = int(raw or 0)
    except (TypeError, ValueError):
        return jsonify(ok=False, msg='شناسه محصول نامعتبر است'), 400
    cart = session.get('cart', [])
    key = f'p:{pid}'
    if key in cart:
        cart.remove(key)
    quantities = session.get('cart_qty', {})
    quantities.pop(key, None)
    session['cart'] = cart
    session['cart_qty'] = quantities
    return jsonify(ok=True, count=_cart_count(cart, quantities))


@products_bp.route('/api/product-cart/quantity', methods=['POST'])
def product_cart_quantity():
    data = request.get_json(silent=True) or {}
    try:
        pid = int(data.get('product_id') or 0)
        quantity = int(data.get('quantity') or 0)
    except (TypeError, ValueError):
        return jsonify(ok=False, msg='مقدار نامعتبر است'), 400
    product = db.session.get(Product, pid)
    if not product or not product.is_active:
        return jsonify(ok=False, msg='محصول یافت نشد'), 404
    if quantity < 1 or quantity > min(99, int(product.stock or 0)):
        return jsonify(ok=False, msg='تعداد با موجودی محصول سازگار نیست'), 400
    key = f'p:{pid}'
    cart = session.get('cart', [])
    if key not in cart:
        return jsonify(ok=False, msg='محصول در سبد نیست'), 404
    quantities = session.get('cart_qty', {})
    quantities[key] = quantity
    session['cart_qty'] = quantities
    return jsonify(ok=True, quantity=quantity)


def cart_quantity(kind, obj):
    if kind != 'product':
        return 1
    try:
        return max(1, int((session.get('cart_qty', {}) or {}).get(f'p:{obj.id}', 1)))
    except (TypeError, ValueError):
        return 1


# ---------------------------------------------------------------- سبد (مخلوط دوره + محصول)
def _cart_items():
    """آیتم‌های سبد: list of (kind, obj) — kind: course | product"""
    items = []
    for raw in session.get('cart', []):
        if isinstance(raw, int) or str(raw).isdigit():
            c = db.session.get(Course, int(raw))
            if c and c.status == 'published':
                items.append(('course', c))
        elif str(raw).startswith('p:'):
            p = db.session.get(Product, int(str(raw)[2:]))
            if p and p.is_active:
                items.append(('product', p))
    return items


def _cart_total(items):
    return sum(o.final_price * cart_quantity(k, o) for k, o in items)


@products_bp.route('/api/cart/items')
def cart_items_api():
    items = _cart_items()
    return jsonify(ok=True, items=[{
        'kind': k, 'id': o.id, 'title': o.title,
        'price': o.final_price, 'quantity': cart_quantity(k, o),
        'image': o.image if k == 'product' else (o.image or ''),
        'url': (url_for('products.product_detail', slug=o.slug) if k == 'product'
                else url_for('site.course_detail', slug=o.slug)),
    } for k, o in items])
