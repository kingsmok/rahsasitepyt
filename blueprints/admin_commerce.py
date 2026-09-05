# -*- coding: utf-8 -*-
"""دامنهٔ تجارت — سفارش، فیش پرداخت، کوپن، اقساط، تسویه و درگاه‌ها.

Route های این دامنه روی Blueprint مشترک ``admin_bp`` (از ``admin_core``)
ثبت می‌شوند؛ ``blueprints/admin_bp.py`` در انتهای خود این ماژول را
import می‌کند تا ثبت انجام شود. هیچ منطقی اینجا نباید مستقیماً
``db.session.commit()`` صدا بزند یا ورودی خام فرم را کست کند — هر دو
از ``admin_core`` می‌آیند.
"""
from __future__ import annotations

import os
import uuid

from datetime import datetime, timedelta
from flask import (
    g,render_template, request, redirect, url_for, flash, abort)
from admin_queries import coupon_list
from admin_core import (
    audit,
    commit,
    go_referrer,
    admin_bp, admin_required, commit
)
from models import (
    Coupon, Notification, Order, PaymentProof, PayoutRequest, Product, Setting, db,
    slug_matches_title, unique_slug_for, utcnow
)
from validators import (safe_int, safe_referrer, log_exc as _lexc)
from admin_core import SECRET_SETTING_KEYS as _SECRET_SETTING_KEYS
from jdates import (fa_num)


@admin_bp.route('/orders')
@admin_required
def orders():
    status = request.args.get('status', '')
    query = Order.query
    if status:
        query = query.filter(Order.status == status)
    # صفحه‌بندی — قبلاً همه سفارش‌ها (هزاران ردیف) یکجا بارگذاری و رندر می‌شد
    try:
        page = max(1, request.args.get('page', 1, type=int))
    except Exception:
        page = 1
    per_page = 50
    total = query.count()
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    all_orders = query.order_by(Order.created_at.desc()) \
        .offset((page - 1) * per_page).limit(per_page).all()
    return render_template('admin/orders.html', orders=all_orders, status=status,
                           page=page, pages=pages, total=total)


@admin_bp.route('/orders/<int:oid>')
@admin_required
def order_detail(oid):
    order = db.get_or_404(Order, oid)
    proofs = PaymentProof.query.filter_by(order_id=oid).order_by(PaymentProof.created_at.desc()).all()
    return render_template('admin/order_detail.html', order=order, proofs=proofs)


@admin_bp.route('/orders/<int:oid>/fulfillment', methods=['POST'])
@admin_required
def order_fulfillment(oid):
    order = db.get_or_404(Order, oid)
    if order.fulfillment_status == 'not_required':
        abort(400)
    status = request.form.get('status', '')
    if status not in ('stock_issue', 'processing', 'shipped', 'delivered'):
        abort(400)
    order.fulfillment_status = status
    commit(success='وضعیت ارسال سفارش ذخیره شد.')
    return redirect(url_for('admin.order_detail', oid=oid))


@admin_bp.route('/proofs/<int:pid>/verify', methods=['POST'])
@admin_required
def proof_verify(pid):
    """تایید فیش کارت‌به‌کارت → فعال‌سازی سفارش و ثبت‌نام خودکار"""
    proof = db.get_or_404(PaymentProof, pid)
    action = request.form.get('action', '')
    if action == 'approve':
        order = proof.order
        if int(proof.amount or 0) != int(order.final_total or 0):
            flash('مبلغ فیش با مبلغ نهایی سفارش یکسان نیست؛ فیش تایید نشد.', 'error')
            return redirect(url_for('admin.order_detail', oid=order.id))
        from blueprints.shop import _mark_paid
        if not _mark_paid(order, 'C2C-' + proof.ref_number, 'card2card_verified'):
            flash('وضعیت سفارش تغییر نکرد؛ احتمالاً قبلاً پردازش شده است.', 'error')
            return redirect(url_for('admin.order_detail', oid=order.id))
        proof.status = 'approved'
        proof.verified_at = utcnow()
        proof.admin_note = request.form.get('note', '')
        db.session.add(proof)
        commit(success=f'فیش سفارش {order.code} تایید و سفارش فعال شد. ✅')
        # اطلاع‌رسانی به کاربر: فیش تایید و دسترسی فعال شد
        # ⚠️ Notification.notify فقط add می‌کند — commit جدا لازم است وگرنه
        # در پایان درخواست rollback می‌شود و کاربر هرگز اعلان نمی‌بیند.
        try:
            from models import Notification
            if order.user_id:
                Notification.notify(order.user_id, 'فیش واریزی تایید شد ✅',
                                    f'سفارش {order.code} فعال شد و دوره‌های آن در حساب شما باز شد.',
                                    '✅', url_for('student.orders'))
                db.session.commit()
        except Exception:
            _lexc('blueprints/admin_bp.py')
    elif action == 'reject':
        proof.status = 'rejected'
        proof.admin_note = request.form.get('note', '')
        order = proof.order
        order.status = 'pending'
        commit(success='فیش رد شد و سفارش به حالت در انتظار بازگشت.', category='info')
        try:
            from models import Notification
            if order.user_id:
                _note = (request.form.get('note') or '').strip()
                Notification.notify(order.user_id, 'فیش واریزی رد شد ❌',
                                    f'سفارش {order.code} قابل تایید نبود. لطفاً فیش جدید ثبت کنید یا با پشتیبانی تماس بگیرید.'
                                    + (f' دلیل: {_note[:150]}' if _note else ''),
                                    '❌', url_for('student.orders'))
                db.session.commit()
        except Exception:
            _lexc('blueprints/admin_bp.py')
    return go_referrer('admin.orders')


@admin_bp.route('/proofs')
@admin_required
def proofs():
    """فهرست فیش‌های واریزی"""
    status = request.args.get('status', '')
    query = PaymentProof.query
    if status:
        query = query.filter(PaymentProof.status == status)
    items = query.order_by(PaymentProof.created_at.desc()).all()
    return render_template('admin/proofs.html', proofs=items, status=status)


# ---------------------------------------------------------------- کوپن‌ها


def _coupon_expiry(raw: str):
    """تبدیل تاریخ انقضای شمسی به datetime — یا ``None``.

    نسخهٔ قبلی یک lambda تودرتو با ``__import__('app', ...)`` بود: هم خوانا نبود،
    هم یک ورودی بد در ``strptime`` صفحه را ۵۰۰ می‌کرد.
    """
    raw = (raw or '').strip()
    if not raw:
        return None
    from app import jalali_to_gregorian
    iso = jalali_to_gregorian(raw)
    if not iso:
        return None
    try:
        return datetime.strptime(iso, '%Y-%m-%d')
    except (TypeError, ValueError):
        return None


@admin_bp.route('/coupons', methods=['GET', 'POST'])
@admin_required
def coupons():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            code = request.form.get('code', '').strip().upper()
            if code and not Coupon.query.filter_by(code=code).first():
                exp = request.form.get('expires_at', '').strip()
                db.session.add(Coupon(
                    code=code, type=request.form.get('type', 'percent'),
                    value=safe_int(request.form.get('value')),
                    max_uses=safe_int(request.form.get('max_uses')),
                    min_amount=safe_int(request.form.get('min_amount')),
                    expires_at=_coupon_expiry(exp),
                    created_by=g.user.id))
                audit('coupon_create', code)
                commit(success='کوپن ساخته شد.')
        elif action == 'delete':
            c = db.session.get(Coupon, safe_int(request.form.get('cid')))
            if c:
                db.session.delete(c)
                commit(success='کوپن حذف شد.', category='info')
        return redirect(url_for('admin.coupons'))
    return render_template('admin/coupons.html', coupons=coupon_list())


# ---------------------------------------------------------------- وبلاگ


@admin_bp.route('/orders/bulk', methods=['POST'])
@admin_required
def orders_bulk():
    """عملیات گروهی روی سفارش‌ها"""
    action = request.form.get('action') or request.form.get('bulk_action')
    ids = request.form.getlist('ids') or request.form.getlist('item_ids[]')
    id_list = [safe_int(x) for x in ids if safe_int(x)]
    if not id_list:
        flash('هیچ سفارشی انتخاب نشده است.', 'error')
        return redirect(url_for('admin.orders'))

    orders = Order.query.filter(Order.id.in_(id_list)).all()
    if action in ('shipped', 'delivered', 'processing', 'canceled'):
        for o in orders:
            if o.fulfillment_status != 'not_required':
                o.fulfillment_status = action
            if action == 'canceled':
                o.status = 'canceled'
        commit(success=f'وضعیت {len(orders)} سفارش به\u200cروزرسانی شد.')
    elif action == 'mark_paid':
        from blueprints.shop import _mark_paid
        for o in orders:
            if o.status != 'paid':
                _mark_paid(o, 'BULK-ADMIN-' + o.code, 'admin_bulk')
        commit(success=f'{len(orders)} سفارش با موفقیت تایید و پرداخت شدند. ✅')

    return redirect(url_for('admin.orders'))


# ---------------------------------------------------------------- گالری طراحی‌ها (پیش‌نمایش + انتخاب اصلی)


@admin_bp.route('/gateways', methods=['GET', 'POST'])
@admin_required
def gateways():
    """مدیریت درگاه‌های پرداخت — فقط کدها را وارد کنید"""
    if request.method == 'POST':
        keys = ['c2c_card', 'c2c_name',
                'zarinpal_merchant', 'idpay_api_key', 'zibal_merchant',
                'parsian_login_account',
                'melli_terminal', 'melli_username', 'melli_password',
                'sepah_terminal',
                'sadad_merchant', 'sadad_terminal', 'sadad_key',
                'snapp_client_id', 'snapp_client_secret', 'snapp_merchant',
                'digipay_api_key', 'digipay_merchant',
                'tarb_api_url', 'tarb_api_key', 'tarb_merchant']
        for k in keys:
            v = request.form.get(k, '').strip()
            if k in _SECRET_SETTING_KEYS and not v:
                continue
            st = db.session.get(Setting, k)
            if st:
                st.value = v
            else:
                db.session.add(Setting(key=k, value=v))
        commit(success='تنظیمات درگاه\u200cها ذخیره شد. ✅')
        return redirect(url_for('admin.gateways'))
    return render_template('admin/gateways.html')


@admin_bp.route('/gateways/test/<gw>', methods=['POST'])
@admin_required
def gateway_test(gw):
    """تست اتصال درگاه — بدون تراکنش واقعی"""
    from gateways import test_gateway
    # اول ذخیره فیلدهای همین فرم
    keys = ['c2c_card', 'c2c_name',
            'zarinpal_merchant', 'idpay_api_key', 'zibal_merchant',
            'parsian_login_account',
            'melli_terminal', 'melli_username', 'melli_password',
            'sepah_terminal',
            'sadad_merchant', 'sadad_terminal', 'sadad_key',
            'snapp_client_id', 'snapp_client_secret', 'snapp_merchant',
            'digipay_api_key', 'digipay_merchant',
            'tarb_api_url', 'tarb_api_key', 'tarb_merchant']
    for k in keys:
        v = request.form.get(k, '').strip()
        if k in _SECRET_SETTING_KEYS and not v:
            continue
        st = db.session.get(Setting, k)
        if st:
            st.value = v
        elif v:
            db.session.add(Setting(key=k, value=v))
    commit(context='admin.gateway_test')
    # خواندن تنظیمات تازه
    settings = {s.key: s.value for s in Setting.query.all()}
    ok, msg = test_gateway(gw, settings)
    flash(('✅ ' if ok else '❌ ') + msg, 'success' if ok else 'error')
    return redirect(url_for('admin.gateways'))


@admin_bp.route('/installments')
@admin_required
def installments():
    """مدیریت پرداخت اقساطی — همه قسط‌ها"""
    from models import Installment
    status = request.args.get('status', '')
    q = Installment.query
    if status:
        q = q.filter(Installment.status == status)
    items = q.order_by(Installment.due_date.asc()).all()
    return render_template('admin/installments.html', items=items, status=status)


@admin_bp.route('/installments/<int:iid>/mark-paid', methods=['POST'])
@admin_required
def installment_mark_paid(iid):
    """ثبت دستی پرداخت یک قسط — برای همگام‌سازی وصولی‌های اسنپ‌پی/دیجی‌پی
    (که در پنل خود ارائه‌دهنده انجام می‌شود) و باز شدن جلسات بعدی دوره."""
    from models import Installment as _I, Notification as _N
    inst = db.get_or_404(_I, iid)
    if inst.status == 'paid':
        flash('این قسط قبلاً پرداخت شده است.', 'info')
        return redirect(url_for('admin.installments'))
    order = inst.order
    inst.status = 'paid'
    inst.paid_at = utcnow()
    inst.ref_id = (inst.ref_id or '') + ' | ADMIN-MANUAL'
    remaining = _I.query.filter_by(order_id=order.id).filter(
        _I.status != 'paid').count()
    _N.notify(order.user_id, 'قسط شما ثبت شد ✅',
              'قسط {} از {} سفارش {} ثبت شد. جلسات بیشتری از دوره باز شد.'.format(
                  fa_num(inst.number), fa_num(order.installment_count or 1), order.code),
              '💳', url_for('student.my_courses'))
    if remaining == 0:
        order.status = 'paid'
        order.paid_at = utcnow()
        _N.notify(order.user_id, 'تکمیل پرداخت اقساطی 🎉',
                  'همه قسط‌های سفارش {} پرداخت شد؛ همه جلسات دوره باز شد.'.format(order.code),
                  '✅', url_for('student.my_courses'))
    commit(success='قسط {}/{} به\u200cعنوان پرداخت\u200cشده ثبت شد؛ جلسات دوره طبق قفل اقساطی باز شد.'.format(fa_num(inst.number), fa_num(order.installment_count or 1)))
    return redirect(url_for('admin.installments'))


@admin_bp.route('/payouts')
@admin_required
def payouts():
    items = PayoutRequest.query.order_by(PayoutRequest.created_at.desc()).all()
    return render_template('admin/payouts.html', items=items)


@admin_bp.route('/payouts/<int:pid>/action', methods=['POST'])
@admin_required
def payout_action(pid):
    p = db.get_or_404(PayoutRequest, pid)
    action = request.form.get('action', '')
    if action == 'paid':
        p.status = 'paid'
        p.paid_at = utcnow()
        p.admin_note = request.form.get('note', '')
        from models import Notification
        Notification.notify(p.teacher_id, 'تسویه حساب انجام شد 💰',
                            f'مبلغ {p.amount:,} تومان به حساب شما واریز شد.', '💰')
    elif action == 'rejected':
        p.status = 'rejected'
        p.admin_note = request.form.get('note', '')
        from models import Notification
        Notification.notify(p.teacher_id, 'درخواست تسویه رد شد',
                            request.form.get('note', '') or 'لطفاً اطلاعات حساب را بررسی کنید.', '⚠️')
    commit(success='وضعیت تسویه به\u200cروزرسانی شد.')
    return redirect(url_for('admin.payouts'))


# ================================================================
# چت آنلاین پشتیبانی (سمت ادمین)
# ================================================================


def _product_int(value, maximum=2_000_000_000):
    try:
        return max(0, min(maximum, int(value or 0)))
    except (TypeError, ValueError):
        return 0


def _save_product_image(file_storage, uploader_id=None):
    """ذخیره امن تصویر محصول + ثبت در کتابخانه رسانه مرکزی.

    برگرداندن مسیر نسبی (مثل uploads/products/product-xxx.jpg)؛
    اگر آپلود نامعتبر باشد None و خطا flash می‌شود.
    """
    if not file_storage or not file_storage.filename:
        return None
    from validators import (ALLOWED_IMAGE_EXT, file_content_is_safe,
                            safe_filename as _safe_filename)
    safe = _safe_filename(file_storage.filename, ALLOWED_IMAGE_EXT)
    ext = os.path.splitext(safe or '')[1].lower()
    if not safe or not file_content_is_safe(file_storage.stream, ext):
        flash('تصویر محصول معتبر نیست؛ فقط JPG، PNG، WebP، GIF یا AVIF امن مجاز است.', 'error')
        return None
    directory = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'static', 'img', 'uploads', 'products')
    os.makedirs(directory, exist_ok=True)
    filename = f'product-{uuid.uuid4().hex[:12]}{ext}'
    fpath = os.path.join(directory, filename)
    file_storage.save(fpath)
    try:
        from uploads_helper import compress_image_file
        compressed = compress_image_file(fpath)
        if compressed:
            width, height, size = compressed
    except Exception:
        _lexc('blueprints/admin_bp.py')
    # ثبت در کتابخانه رسانه مرکزی — تصویر آپلودشده اینجا هم قابل استفاده است
    try:
        from models import Media
        size = os.path.getsize(fpath)
        width = height = None
        try:
            from PIL import Image as _Img
            with _Img.open(fpath) as im:
                width, height = im.size
        except Exception:
            pass
        db.session.add(Media(filename=safe, path='uploads/products/' + filename,
                             mime=file_storage.mimetype or '', size=size,
                             width=width, height=height, kind='image',
                             uploaded_by=uploader_id or (getattr(g, 'user', None) and g.user.id)))
        db.session.flush()
    except Exception:
        _lexc('blueprints/admin_bp.py')
    return 'uploads/products/' + filename


@admin_bp.route('/products', methods=['GET', 'POST'])
@admin_required
def products_admin():
    """لیست محصولات + ساخت محصول جدید"""
    from models import Product as _P
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('عنوان محصول الزامی است.', 'error')
        else:
            from models import unique_slug_for
            _slug_req = (request.form.get('slug') or '').strip()
            slug = unique_slug_for(_P, _slug_req or title, fallback='product')
            from validators import clamp_field
            image_file = request.files.get('image_file')
            uploaded_image = _save_product_image(image_file)
            if image_file and image_file.filename and not uploaded_image:
                return redirect(url_for('admin.products_admin'))
            image = (uploaded_image or request.form.get('image', '').strip() or
                     'cover-product-mug.webp')
            _p = _P(
                title=title, slug=slug,
                description=clamp_field(request.form.get('description'), 'default'),
                price=_product_int(request.form.get('price')),
                discount_price=_product_int(request.form.get('discount_price')),
                image=image,
                category=clamp_field(request.form.get('category'), 'default'),
                sku=clamp_field(request.form.get('sku'), 'default'),
                dimensions=clamp_field(request.form.get('dimensions'), 'default'),
                weight=clamp_field(request.form.get('weight'), 'default'),
                material=clamp_field(request.form.get('material'), 'default'),
                features=request.form.get('features', '').strip(),
                stock=_product_int(request.form.get('stock'), maximum=10_000_000),
                featured=bool(request.form.get('featured')),
                is_active=True,
            )
            db.session.add(_p)
            commit(context='admin.products_admin')
            try:
                from seo_service import ensure_meta
                ensure_meta('/product/' + _p.slug)
                db.session.commit()
                from seo_service import save_seo_from_form as _ssf
                _ssf('/product/' + _p.slug, request.form)
                db.session.commit()
            except Exception:
                _lexc('blueprints/admin_bp.py')
            flash('محصول ساخته شد. آدرس عمومی: /product/' + slug +
                  '  —  اگر ۴۰۴ دیدید از /p/' + str(_p.id) + ' استفاده کنید.', 'success')
        return redirect(url_for('admin.products_admin'))
    items = _P.query.order_by(_P.created_at.desc()).all()
    return render_template('admin/products.html', items=items)


@admin_bp.route('/products/<int:pid>/edit', methods=['GET', 'POST'])
@admin_required
def product_admin_edit(pid):
    from models import Product as _P
    p = db.get_or_404(_P, pid)
    if request.method == 'POST':
        from validators import clamp_field
        image_file = request.files.get('image_file')
        uploaded_image = _save_product_image(image_file)
        if image_file and image_file.filename and not uploaded_image:
            return redirect(url_for('admin.product_admin_edit', pid=p.id))
        _old_title = p.title
        _old_path_p = '/product/' + p.slug if p.slug else None
        p.title = clamp_field(request.form.get('title'), 'title') or p.title
        # اسلاگ: اگر خالی است بساز؛ اگر مدیر دستی واردش کرده همان را یکتا کن؛
        # اگر عنوان عوض شده ولی اسلاگ هنوز از عنوان قبلی است، همگام کن.
        from models import unique_slug_for as _usf, slug_matches_title as _smt
        _slug_in = (request.form.get('slug') or '').strip()
        if _slug_in:
            p.slug = _usf(_P, _slug_in, exclude_id=p.id, fallback='product')
        elif not p.slug:
            p.slug = _usf(_P, p.title, exclude_id=p.id, fallback='product')
        elif _old_title != p.title and _smt(p.slug, _old_title, 'product'):
            p.slug = _usf(_P, p.title, exclude_id=p.id, fallback='product')
        p.description = clamp_field(request.form.get('description'), 'default')
        p.price = _product_int(request.form.get('price'))
        p.discount_price = _product_int(request.form.get('discount_price'))
        p.image = uploaded_image or request.form.get('image', '').strip() or p.image
        p.category = clamp_field(request.form.get('category'), 'default')
        p.sku = clamp_field(request.form.get('sku'), 'default')
        p.dimensions = clamp_field(request.form.get('dimensions'), 'default')
        p.weight = clamp_field(request.form.get('weight'), 'default')
        p.material = clamp_field(request.form.get('material'), 'default')
        p.features = request.form.get('features', '').strip()
        p.stock = _product_int(request.form.get('stock'), maximum=10_000_000)
        p.featured = bool(request.form.get('featured'))
        p.is_active = bool(request.form.get('is_active'))
        commit(context='admin.product_admin_edit')
        try:
            from seo_service import ensure_meta, save_seo_from_form
            ensure_meta('/product/' + p.slug)
            db.session.commit()
            save_seo_from_form('/product/' + p.slug, request.form,
                               old_path=_old_path_p)
        except Exception:
            _lexc('blueprints/admin_bp.py')
        flash('محصول به‌روزرسانی شد. ✏️', 'success')
        return redirect(url_for('admin.products_admin'))
    _seo_p = None
    if p and p.slug:
        from seo_service import get_seo_for
        _seo_p = get_seo_for('/product/' + p.slug)
    return render_template('admin/product_form.html', p=p, seo=_seo_p)


@admin_bp.route('/products/<int:pid>/delete', methods=['POST'])
@admin_required
def product_admin_delete(pid):
    from models import Product as _P
    p = db.get_or_404(_P, pid)
    db.session.delete(p)
    commit(success='محصول حذف شد.', category='info')
    return redirect(url_for('admin.products_admin'))
