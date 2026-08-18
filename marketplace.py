# -*- coding: utf-8 -*-
"""اتصال به مارکت‌پلیس‌ها و موتورهای جستجوی کالا

- فید لحظه‌ای ترب (JSON + XML) و ایمالز (JSON) — قیمت/موجودی/تخفیف دوره‌ها و محصولات
- همگام‌سازی موجودی با دیجی‌کالا Seller Center (کلاینت قابل اتصال + لاگ)
- وب‌هوک باسلام برای دریافت سفارش‌ها در پنل مدیریت
"""
import json
import hmac
import hashlib
from datetime import datetime
try:
    from datetime import UTC
except ImportError:  # پایتون < 3.11 (هاست‌های اشتراکی)
    from datetime import timezone as _tz_utc
    UTC = _tz_utc.utc

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, jsonify, Response, abort)
from models import db, utcnow, Course, Product, Setting, Order
from jdates import jdate_num
from validators import log_exc as _lexc
from ext_models import MarketSyncLog, MarketOrder

market_bp = Blueprint('market', __name__)


def _cfg(key, default=''):
    s = db.session.get(Setting, key)
    return (s.value if s and s.value is not None else default)


def _xml_escape(s):
    """escape کاراکترهای خاص XML — جلوگیری از خراب‌شدن فید با عنوان‌های دارای & < >"""
    return (str(s or '').replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;'))


def _feed_items():
    """آیتم‌های فید: دوره‌های منتشر + محصولات دارای موجودی"""
    items = []
    for c in Course.query.filter_by(status='published').all():
        items.append(dict(
            id=f'course-{c.id}', type='course', title=c.title,
            price=c.price or 0, final_price=c.final_price or 0,
            discount_pct=c.discount_percent or 0,
            stock=1, url=url_for('site.course_detail', slug=c.slug, _external=True),
            image=(c.image_url if c.image_url.startswith('https://') else
                   request.host_url.rstrip('/') + c.image_url),
            category=c.category.name if c.category else 'آموزش',
            in_stock=True,
        ))
    for p in Product.query.filter(Product.stock > 0, Product.is_active == True).all():
        _fp = p.final_price if hasattr(p, 'final_price') else (p.price or 0)
        _dp = 0
        if hasattr(p, 'discount_price') and p.discount_price and p.discount_price < (p.price or 0):
            _dp = round((p.price - p.discount_price) * 100 / p.price)
        product_image = p.image_url
        if not product_image.startswith('https://'):
            product_image = request.host_url.rstrip('/') + product_image
        items.append(dict(
            id=f'product-{p.id}', type='product', title=p.title,
            price=p.price or 0, final_price=_fp or 0,
            discount_pct=_dp,
            stock=p.stock or 0,
            url=url_for('products.product_detail', slug=p.slug, _external=True),
            image=product_image,
            category='محصولات آموزشی',
            in_stock=(p.stock or 0) > 0,
        ))
    return items


def _log(channel, action, status, detail, item_type='', item_id=None):
    try:
        db.session.add(MarketSyncLog(channel=channel, action=action, status=status,
                                     detail=detail[:350], item_type=item_type, item_id=item_id))
        db.session.commit()
    except Exception:
        db.session.rollback()


# ============================================================
# فید ترب — JSON و XML
# ============================================================
@market_bp.route('/api/feed/torob.json')
def torob_json():
    """فید JSON ترب — با هدر no-store برای به‌روزرسانی لحظه‌ای"""
    items = _feed_items()
    out = dict(
        generated_at=datetime.now(UTC).isoformat(),
        merchant=dict(name=_cfg('site_name', 'آکادمی آنلاین'),
                      website=request.host_url.rstrip('/')),
        products=[dict(
            id=i['id'], title=i['title'], price=i['final_price'],
            old_price=i['price'] if i['discount_pct'] else None,
            discount_percent=i['discount_pct'],
            availability='in_stock' if i['in_stock'] else 'out_of_stock',
            stock=i['stock'], category=i['category'],
            url=i['url'], image=i['image'],
        ) for i in items]
    )
    _log('torob', 'feed', 'ok', f'{len(items)} item')
    resp = Response(json.dumps(out, ensure_ascii=False), mimetype='application/json')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@market_bp.route('/api/feed/torob.xml')
def torob_xml():
    """فید XML ترب (Yandex Market Language)"""
    items = _feed_items()
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<yml_catalog date="{}"><shop>'.format(datetime.now(UTC).strftime('%Y-%m-%d %H:%M')),
           f'<name>{_cfg("site_name", "آکادمی آنلاین")}</name>',
           f'<url>{request.host_url.rstrip("/")}</url>',
           '<currencies><currency id="IRR" rate="1"/></currencies>',
           '<categories><category id="1">آموزش</category></categories>',
           '<offers>']
    for i in items:
        price = i['final_price']
        old = f'<oldprice>{i["price"]}</oldprice>' if i['discount_pct'] else ''
        xml.append(
            f'<offer id="{_xml_escape(i["id"])}" available="{"true" if i["in_stock"] else "false"}">'
            f'<url>{_xml_escape(i["url"])}</url><price>{price}</price>{old}'
            f'<currencyId>IRR</currencyId><categoryId>1</categoryId>'
            f'<picture>{_xml_escape(i["image"])}</picture>'
            f'<name>{_xml_escape(i["title"])}</name><stock>{i["stock"]}</stock>'
            f'<description>{_xml_escape(i["category"])}</description></offer>')
    xml += ['</offers></shop></yml_catalog>']
    _log('torob', 'feed_xml', 'ok', f'{len(items)} item')
    resp = Response('\n'.join(xml), mimetype='application/xml')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


# ============================================================
# فید ایمالز
# ============================================================
@market_bp.route('/api/feed/emalls.json')
def emalls_json():
    items = _feed_items()
    out = dict(
        seller=dict(name=_cfg('site_name', 'آکادمی آنلاین'),
                    id=_cfg('emalls_seller_id', '')),
        generated_at=datetime.now(UTC).isoformat(),
        products=[dict(
            product_id=i['id'], title=i['title'], price=i['final_price'],
            previous_price=i['price'], discount=i['discount_pct'],
            stock=i['stock'], in_stock=i['in_stock'], category=i['category'],
            deep_link=i['url'], image=i['image'],
        ) for i in items]
    )
    _log('emalls', 'feed', 'ok', f'{len(items)} item')
    resp = Response(json.dumps(out, ensure_ascii=False), mimetype='application/json')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


# ============================================================
# دیجی‌کالا Seller Center — همگام‌سازی موجودی
# ============================================================
def _dk_headers():
    return {'Authorization': 'Bearer ' + _cfg('dk_access_token', ''),
            'Content-Type': 'application/json'}


def sync_digikala_inventory(only_ids=None):
    """ارسال موجودی محصولات به دیجی‌کالا — در production با Celery اجرا می‌شود"""
    base = _cfg('dk_api_base', 'https://seller.digikala.com/api/v1')
    token = _cfg('dk_access_token', '')
    if not token:
        return 0, 'توکن دیجی‌کالا تنظیم نشده است'
    import requests as _rq
    prods = Product.query.filter(Product.stock > 0).all()
    if only_ids:
        prods = [p for p in prods if p.id in only_ids]
    ok_n = 0
    for p in prods:
        dk_id = str(getattr(p, 'dk_product_id', '') or '').strip()
        if not dk_id:
            _log('digikala', 'sync_inventory', 'skipped',
                 f'{p.title}: شناسه دیجی‌کالا تنظیم نشده', 'product', p.id)
            continue
        try:
            payload = {'inventory': [{'product_id': dk_id,
                                      'quantity': max(0, p.stock or 0)}]}
            r = _rq.post(f'{base}/inventory', json=payload, headers=_dk_headers(),
                         timeout=(5, 15))
            st = 'ok' if r.status_code in (200, 201) else 'error'
            _log('digikala', 'sync_inventory', st,
                 f'{p.title}: HTTP {r.status_code}', 'product', p.id)
            if st == 'ok':
                ok_n += 1
        except Exception as e:
            _log('digikala', 'sync_inventory', 'error', str(e)[:200], 'product', p.id)
    return ok_n, f'{ok_n} محصول همگام شد'


# ============================================================
# وب‌هوک باسلام — دریافت سفارش
# ============================================================
@market_bp.route('/api/marketplace/basalam/webhook', methods=['POST'])
def basalam_webhook():
    """دریافت سفارش از باسلام — تأیید امضا با secret (HMAC-SHA256)"""
    raw = request.get_data(as_text=True)
    if len(raw) > 65536:
        _log('basalam', 'webhook', 'error', 'payload بیش از حد مجاز (64KB)')
        return jsonify(ok=False, msg='payload بیش از حد مجاز'), 413
    secret = _cfg('basalam_webhook_secret', '')
    if not secret:
        _log('basalam', 'webhook', 'error', 'webhook secret پیکربندی نشده است')
        return jsonify(ok=False, msg='وب‌هوک باسلام هنوز امن پیکربندی نشده است.'), 503
    sig = request.headers.get('X-Basalam-Signature', '')
    expect = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expect):
        _log('basalam', 'webhook', 'error', 'امضای نامعتبر')
        return jsonify(ok=False, msg='امضای نامعتبر'), 403
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        return jsonify(ok=False, msg='payload باید JSON باشد'), 400
    ext_id = str(data.get('id') or data.get('order_id') or '').strip()
    if not ext_id:
        return jsonify(ok=False, msg='شناسه سفارش الزامی است'), 400
    phone = str(data.get('customer', {}).get('phone') or data.get('phone') or '').strip()
    items = data.get('items') if isinstance(data.get('items'), list) else []
    exists = MarketOrder.query.filter_by(channel='basalam', external_id=ext_id).first()
    if exists:
        exists.status = data.get('status', exists.status)
        db.session.commit()
        return jsonify(ok=True, msg='به‌روزرسانی شد')
    if not phone:
        _log('basalam', 'webhook', 'error', f'سفارش {ext_id}: شماره تماس الزامی است')
        return jsonify(ok=False, msg='شماره تماس الزامی است'), 422
    try:
        total = int(data.get('total') or data.get('price') or 0)
    except Exception:
        total = 0
    mo = MarketOrder(
        channel='basalam', external_id=ext_id,
        customer_name=str(data.get('customer', {}).get('name') or data.get('name') or ''),
        customer_phone=phone,
        address=str(data.get('shipping_address') or data.get('address') or ''),
        items=json.dumps(items, ensure_ascii=False),
        total=total, status=str(data.get('status') or 'new'),
        raw=raw[:4000])
    db.session.add(mo)
    db.session.commit()
    _log('basalam', 'webhook', 'ok', f'سفارش {ext_id} دریافت شد')
    return jsonify(ok=True, msg='سفارش دریافت شد', order_id=mo.id)


# ============================================================
# پنل مدیریت مارکت‌پلیس
# ============================================================
@market_bp.route('/admin/marketplace')
def admin_marketplace():
    if not g.user or g.user.role not in ('admin', 'super_admin'):
        abort(403)
    logs = MarketSyncLog.query.order_by(MarketSyncLog.id.desc()).limit(30).all()
    mo = MarketOrder.query.order_by(MarketOrder.id.desc()).limit(20).all()
    counts = dict(
        courses=Course.query.filter_by(status='published').count(),
        products=Product.query.filter(Product.stock > 0).count(),
        basalam=MarketOrder.query.count(),
        feed_ok=MarketSyncLog.query.filter_by(channel='torob', status='ok').count(),
    )
    return render_template('admin/marketplace.html', logs=logs, orders=mo,
                           counts=counts, fa=fa_helper)


@market_bp.route('/admin/marketplace/sync', methods=['POST'])
def admin_sync():
    if not g.user or g.user.role not in ('admin', 'super_admin'):
        abort(403)
    channel = request.form.get('channel', 'digikala')
    if channel == 'digikala':
        n, msg = sync_digikala_inventory()
        flash(f'دیجی‌کالا: {msg}', 'success' if n else 'error')
    elif channel == 'torob':
        # لمس فید = لاگ
        _log('torob', 'manual', 'ok', 'درخواست دستی فید')
        flash('فید ترب به‌روزرسانی شد (آدرس فید ثابت است و ترب خودش می‌خواند).', 'success')
    return redirect(url_for('market.admin_marketplace'))


@market_bp.route('/admin/marketplace/order/<int:oid>/status', methods=['POST'])
def admin_order_status(oid):
    if not g.user or g.user.role not in ('admin', 'super_admin'):
        abort(403)
    mo = db.session.get(MarketOrder, oid)
    if not mo:
        flash('سفارش پیدا نشد', 'error')
        return redirect(url_for('market.admin_marketplace'))
    st = request.form.get('status', '')
    if st in ('accepted', 'shipped', 'done', 'canceled', 'new'):
        mo.status = st
        db.session.commit()
        flash(f'وضعیت سفارش به «{st}» تغییر کرد', 'success')
    return redirect(url_for('market.admin_marketplace'))


def fa_helper(v):
    return jdate_num(v) if hasattr(v, 'year') else str(v)


def init_market(app):
    app.register_blueprint(market_bp)
