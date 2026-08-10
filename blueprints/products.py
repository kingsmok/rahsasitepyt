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
    cats = [r[0] for r in db.session.query(Product.category).distinct().all() if r[0]]
    g.seo['title'] = "فروشگاه محصولات — آکادمی آنلاین"
    g.seo['description'] = "محصولات و کالاهای آموزشی با ارسال سریع — کیفیت تضمینی."
    return render_template('products/list.html', items=items, cats=cats, q=q, cat=cat, sort=sort)


# ---------------------------------------------------------------- صفحه محصول
@products_bp.route('/product/<slug>')
def product_detail(slug):
    p = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
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
    pid = int(request.json.get('product_id') if request.is_json else request.form.get('product_id') or 0)
    p = db.session.get(Product, pid)
    if not p or not p.is_active:
        return jsonify(ok=False, msg='محصول یافت نشد'), 404
    if p.stock is not None and p.stock <= 0:
        return jsonify(ok=False, msg='این محصول ناموجود است'), 400
    cart = session.get('cart', [])
    key = f'p:{p.id}'
    if key not in cart:
        cart.append(key)
        session['cart'] = cart
    return jsonify(ok=True, count=len(cart), msg='به سبد خرید اضافه شد')


@products_bp.route('/api/product-cart/remove', methods=['POST'])
def product_cart_remove():
    pid = int(request.json.get('product_id') if request.is_json else request.form.get('product_id') or 0)
    cart = session.get('cart', [])
    key = f'p:{pid}'
    if key in cart:
        cart.remove(key)
        session['cart'] = cart
    return jsonify(ok=True, count=len(cart))


# ---------------------------------------------------------------- سبد (مخلوط دوره + محصول)
def _cart_items():
    """آیتم‌های سبد: list of (kind, obj) — kind: course | product"""
    items = []
    for raw in session.get('cart', []):
        if isinstance(raw, int) or str(raw).isdigit():
            c = db.session.get(Course, int(raw))
            if c:
                items.append(('course', c))
        elif str(raw).startswith('p:'):
            p = db.session.get(Product, int(str(raw)[2:]))
            if p and p.is_active:
                items.append(('product', p))
    return items


def _cart_total(items):
    return sum((o.final_price if k == 'course' else o.final_price) for k, o in items)


@products_bp.route('/api/cart/items')
def cart_items_api():
    items = _cart_items()
    return jsonify(ok=True, items=[{
        'kind': k, 'id': o.id, 'title': o.title,
        'price': o.final_price, 'image': o.image if k == 'product' else (o.image or ''),
        'url': (url_for('products.product_detail', slug=o.slug) if k == 'product'
                else url_for('site.course_detail', slug=o.slug)),
    } for k, o in items])
