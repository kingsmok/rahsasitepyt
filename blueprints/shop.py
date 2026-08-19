# -*- coding: utf-8 -*-
"""سبد خرید، تسویه حساب و درگاه‌های پرداخت"""
import os
import random
import re
from datetime import datetime
try:
    from datetime import UTC
except ImportError:  # پایتون < 3.11 (هاست‌های اشتراکی)
    from datetime import timezone as _tz_utc
    UTC = _tz_utc.utc
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, session, abort)
from models import (utcnow, db, User, Order, OrderItem, Coupon, Enrollment,
                    PaymentLog, PaymentProof, WalletTransaction)

shop_bp = Blueprint('shop', __name__)

from gateways import (GATEWAYS as _GW, PaymentRedirect, gateway_ready,
                      start_payment, gateway_fa)
from validators import log_exc as _lexc
from jdates import fa

GATEWAYS = _GW


def _sandbox_allowed():
    """آیا شبیه‌ساز پرداخت مجاز است؟

    شبیه‌ساز فقط داخل Flask TESTING/pytest مجاز است. حتی دموی فروش با
    ``ENABLE_DEMO_FEATURES=1`` باید از درگاه واقعی پیکربندی‌شده استفاده کند؛
    production نیز همیشه مسدود است.
    """
    from runtime import automated_test_mode
    return (automated_test_mode() and
            str(g.settings.get('sandbox_mode', '0')) == '1')


def _cart_courses():
    """دوره‌های سبد (برای سازگاری با کدهای قبلی)"""
    return [o for k, o in _cart_items() if k == 'course']


def _cart_items():
    """آیتم‌های سبد: list of (kind, obj) — kind: course | product"""
    from blueprints.products import _cart_items as _pi
    return _pi()


def _cart_total(courses):
    return sum(c.final_price for c in courses)


def _cart_total_all(items):
    from blueprints.products import cart_quantity
    return sum(o.final_price * cart_quantity(k, o) for k, o in items)


@shop_bp.route('/cart')
def cart():
    courses = _cart_courses()
    items = _cart_items()
    total = _cart_total_all(items)
    from blueprints.products import cart_quantity
    quantities = {(kind, obj.id): cart_quantity(kind, obj) for kind, obj in items}
    return render_template('cart.html', courses=courses, items=items, total=total,
                           quantities=quantities)


@shop_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if not g.user:
        flash('برای ادامه خرید ابتدا وارد حساب خود شوید.', 'error')
        return redirect(url_for('auth.login', next=url_for('shop.checkout')))
    courses = _cart_courses()
    items = _cart_items()
    if not courses and not items:
        flash('سبد خرید شما خالی است.', 'info')
        return redirect(url_for('shop.cart'))

    # بررسی موجودی محصولات — جلوگیری از خرید محصول ناموجود یا تعداد بیشتر از موجودی
    from blueprints.products import cart_quantity
    for kind, obj in items:
        requested_quantity = cart_quantity(kind, obj)
        if kind == 'product' and getattr(obj, 'stock', 0) < requested_quantity:
            flash(f'«{obj.title}» موجود نیست — از سبد حذف شد.', 'error')
            cart = session.get('cart', [])
            try:
                cart.remove(f'p:{obj.id}')
            except ValueError:
                pass
            quantities = session.get('cart_qty', {})
            quantities.pop(f'p:{obj.id}', None)
            session['cart'] = cart
            session['cart_qty'] = quantities
            return redirect(url_for('shop.cart'))

    subtotal = _cart_total_all(items) if items else _cart_total(courses)
    has_physical = any(kind == 'product' for kind, _ in items)
    try:
        shipping_cost = max(0, int(g.settings.get('shipping_flat_rate') or 0)) if has_physical else 0
    except (TypeError, ValueError):
        shipping_cost = 0
    coupon = None
    discount = 0
    coupon_code = request.form.get('coupon', '').strip()
    if not coupon_code:
        coupon_code = session.get('coupon_code', '')

    if coupon_code:
        coupon = Coupon.query.filter_by(code=coupon_code.upper()).first()
        if not coupon or not coupon.is_valid:
            flash('کد تخفیف نامعتبر یا منقضی شده است.', 'error')
            coupon = None
            session.pop('coupon_code', None)
        elif subtotal < (coupon.min_amount or 0):
            flash(f'حداقل مبلغ خرید برای این کد تخفیف {coupon.min_amount:,} تومان است.', 'error')
            coupon = None
            session.pop('coupon_code', None)
        else:
            if coupon.type == 'percent':
                discount = round(subtotal * coupon.value / 100)
            else:
                discount = min(coupon.value, subtotal)
            session['coupon_code'] = coupon.code
    elif request.method == 'POST':
        session.pop('coupon_code', None)

    final = max(0, subtotal - discount)

    # پرداخت اقساطی: انتخاب تعداد قسط (۲ تا ۴)
    installment_count = request.form.get('installment_count', 0, type=int)
    if installment_count not in (0, 2, 3, 4):
        installment_count = 0
    try:
        from bnpl import bnpl_enabled, _providers as _bnpl_providers
        bnpl_available = bnpl_enabled() and bool(_bnpl_providers())
    except Exception:
        bnpl_available = False
    # تخفیف وفاداری فقط با درصدی که مدیر صریحاً تنظیم کرده است.
    loyalty_discount = 0
    try:
        loyalty_percent = max(0, min(50, int(g.settings.get('loyalty_discount_percent') or 0)))
    except (TypeError, ValueError):
        loyalty_percent = 0
    has_past_purchase = Enrollment.query.filter_by(user_id=g.user.id).count() > 0
    if has_past_purchase and final > 0 and loyalty_percent:
        loyalty_discount = round(final * loyalty_percent / 100)
        final = max(0, final - loyalty_discount)
    final += shipping_cost
    # POST دست‌ساز هم نباید اقساط غیرفعال یا مبلغ زیر حداقل را دور بزند.
    from runtime import automated_test_mode
    if not bnpl_available or (final < 300000 and not automated_test_mode()):
        installment_count = 0

    if request.method == 'POST' and request.form.get('action') == 'remove_coupon':
        session.pop('coupon_code', None)
        return redirect(url_for('shop.checkout'))

    if request.method == 'POST' and request.form.get('action') == 'create_order':
        shipping = {}
        if has_physical:
            shipping = {
                'name': request.form.get('shipping_name', '').strip(),
                'phone': request.form.get('shipping_phone', '').strip(),
                'province': request.form.get('shipping_province', '').strip(),
                'city': request.form.get('shipping_city', '').strip(),
                'address': request.form.get('shipping_address', '').strip(),
                'postal_code': request.form.get('shipping_postal_code', '').strip(),
            }
            if (len(shipping['name']) < 3 or
                    not re.fullmatch(r'09\d{9}', shipping['phone']) or
                    not shipping['province'] or not shipping['city'] or
                    len(shipping['address']) < 8):
                flash('برای محصولات فیزیکی، نام، موبایل، استان، شهر و آدرس کامل را وارد کنید.', 'error')
                return render_template('checkout.html', courses=courses, items=items,
                                       subtotal=subtotal, discount=discount, final=final,
                                       coupon=coupon, gateways=GATEWAYS,
                                       loyalty_discount=loyalty_discount,
                                       loyalty_percent=loyalty_percent,
                                       has_past_purchase=has_past_purchase,
                                       installment_count=installment_count,
                                       bnpl_available=bnpl_available,
                                       has_physical=has_physical,
                                       shipping_cost=shipping_cost), 400
            if shipping['postal_code'] and not re.fullmatch(r'\d{10}', shipping['postal_code']):
                flash('کد پستی باید ۱۰ رقم باشد.', 'error')
                return redirect(url_for('shop.checkout'))
        code = f"AC-{datetime.now():%y%m%d}-{random.randint(1000, 9999)}"
        while Order.query.filter_by(code=code).first():
            code = f"AC-{datetime.now():%y%m%d}-{random.randint(1000, 9999)}"
        order = Order(code=code, user_id=g.user.id, total=subtotal + shipping_cost,
                      discount=discount + loyalty_discount,
                      final_total=final, coupon=coupon, status='pending',
                      installment_count=installment_count,
                      shipping_name=shipping.get('name', ''),
                      shipping_phone=shipping.get('phone', ''),
                      shipping_province=shipping.get('province', ''),
                      shipping_city=shipping.get('city', ''),
                      shipping_address=shipping.get('address', ''),
                      shipping_postal_code=shipping.get('postal_code', ''),
                      shipping_cost=shipping_cost,
                      fulfillment_status='processing' if has_physical else 'not_required')
        from blueprints.products import _cart_items as _ci
        for kind, obj in _ci():
            quantity = cart_quantity(kind, obj)
            if kind == 'course':
                order.items.append(OrderItem(course_id=obj.id, price=obj.final_price, quantity=1))
            else:
                order.items.append(OrderItem(product_id=obj.id, price=obj.final_price,
                                             quantity=quantity))
                # کاهش موجودی فقط بعد از پرداخت موفق انجام میشود (در _mark_paid)
        db.session.add(order)
        db.session.flush()
        db.session.commit()
        session.pop('cart', None)
        session.pop('cart_qty', None)
        session.pop('coupon_code', None)
        if final == 0 and installment_count == 0:
            _mark_paid(order, 'FREE', 'free_order')
            flash('سفارش رایگان ثبت شد و دسترسی شما فعال است. 🎉', 'success')
            return redirect(url_for('shop.pay_result', code=code, status='success'))
        if installment_count > 1:
            # سفارش اقساطی → پنل اقساطی (انتخاب اسنپ‌پی/ترب/دیجی‌پی + تعداد قسط)
            # خودِ قسط‌ها در bnpl_start ساخته می‌شوند (منبع واحد در bnpl.py)
            flash('سفارش ثبت شد — برای پرداخت اقساطی سرویس و تعداد قسط را انتخاب کنید.', 'info')
            return redirect(url_for('bnpl.bnpl_page', code=code))
        flash('سفارش شما ثبت شد. لطفاً پرداخت را تکمیل کنید.', 'info')
        return redirect(url_for('shop.pay_start', code=code))

    from blueprints.products import _cart_items as _ci2
    items = _ci2()
    return render_template('checkout.html', courses=courses, items=items, subtotal=subtotal,
                           discount=discount, final=final, coupon=coupon, gateways=GATEWAYS,
                           loyalty_discount=loyalty_discount, loyalty_percent=loyalty_percent,
                           has_past_purchase=has_past_purchase, installment_count=installment_count,
                           bnpl_available=bnpl_available, has_physical=has_physical,
                           shipping_cost=shipping_cost)


@shop_bp.route('/checkout/wallet', methods=['POST'])
def checkout_wallet():
    """پرداخت کامل سفارش با موجودی کیف پول"""
    if not g.user:
        return redirect(url_for('auth.login'))
    code = request.form.get('code', '')
    order = Order.query.filter_by(code=code, user_id=g.user.id, status='pending').first()
    if not order:
        flash('سفارش یافت نشد.', 'error')
        return redirect(url_for('student.orders'))
    if order.fulfillment_status == 'wallet_topup':
        flash('شارژ کیف پول باید از درگاه پرداخت واقعی انجام شود.', 'error')
        return redirect(url_for('features.wallet'))
    balance = g.user.wallet_balance or 0
    if balance < order.final_total:
        flash('موجودی کیف پول کافی نیست.', 'error')
        return redirect(url_for('shop.pay_start', code=code))
    from gamification import wallet_spend
    wallet_spend(g.user, order.final_total, f'خرید سفارش {order.code}')
    _mark_paid(order, 'WALLET', 'wallet_payment')
    flash('پرداخت با کیف پول انجام شد. دوره فعال شد! 🎉', 'success')
    return redirect(url_for('shop.pay_result', code=code, status='success'))


@shop_bp.route('/pay/installment/<code>/<int:num>', methods=['POST'])
def pay_installment(code, num):
    """پرداخت قسط بعدی یک سفارش اقساطی — فقط در حالت آزمایشی مستقیم؛ در production از درگاه"""
    if not g.user:
        return redirect(url_for('auth.login'))
    from models import Installment
    order = Order.query.filter_by(code=code, user_id=g.user.id).first_or_404()
    inst = Installment.query.filter_by(order_id=order.id, number=num).first_or_404()
    if inst.status == 'paid':
        flash('این قسط قبلاً پرداخت شده.', 'info')
        return redirect(url_for('student.orders'))
    # در سرویس‌های BNPL واقعی، اقساط در پنل همان ارائه‌دهنده وصول می‌شوند؛
    # ارسال دوباره کل مبلغ سفارش به درگاه، برداشت اضافه و نادرست ایجاد می‌کرد.
    if not _sandbox_allowed():
        flash('پرداخت و پیگیری اقساط این سفارش در پنل سرویس اقساطی انجام می‌شود.', 'info')
        return redirect(url_for('student.orders'))
    inst.status = 'paid'
    inst.paid_at = utcnow()
    inst.ref_id = 'INST-' + str(random.randint(100000000, 999999999))
    db.session.add(PaymentLog(order_id=order.id, gateway=order.gateway or 'sandbox',
                              amount=inst.amount, status='paid', ref_id=inst.ref_id,
                              detail=f'قسط {num} از {order.installment_count}'))
    # اگر همه قسط‌ها پرداخت شد → سفارش paid
    remaining = Installment.query.filter_by(order_id=order.id, status='pending').count()
    if remaining == 0:
        order.status = 'paid'
        order.paid_at = utcnow()
        for item in order.items:
            if item.course_id and not Enrollment.query.filter_by(user_id=order.user_id, course_id=item.course_id).first():
                db.session.add(Enrollment(user_id=order.user_id, course_id=item.course_id, order_id=order.id))
            if item.product_id:
                from models import Product as _PP
                quantity = max(1, int(item.quantity or 1))
                updated = _PP.query.filter(_PP.id == item.product_id,
                                           _PP.stock >= quantity).update(
                    {_PP.stock: _PP.stock - quantity}, synchronize_session=False)
                if updated == 0:
                    order.fulfillment_status = 'stock_issue'
        from models import Notification
        Notification.notify(order.user_id, 'تکمیل پرداخت اقساطی 🎉',
                            f'همه قسط‌های سفارش {order.code} پرداخت شد؛ وضعیت سفارش را در حساب ببینید.', '✅',
                            url_for('student.my_courses'))
    db.session.commit()
    flash(f'قسط {fa(num)} پرداخت شد. ✅', 'success')
    return redirect(url_for('student.orders'))


@shop_bp.route('/pay/<code>', methods=['GET', 'POST'])
def pay_start(code):
    if not g.user:
        return redirect(url_for('auth.login'))
    order = Order.query.filter_by(code=code, user_id=g.user.id).first_or_404()
    if order.status == 'paid':
        if order.fulfillment_status == 'wallet_topup':
            flash('این پرداخت قبلاً تایید و کیف پول شارژ شده است.', 'info')
            return redirect(url_for('features.wallet'))
        flash('این سفارش قبلاً پرداخت شده است. 🎉', 'info')
        return redirect(url_for('student.invoice', code=code))
    if order.status in ('canceled', 'failed'):
        # پرداخت مجدد سفارش لغوشده یا ناموفق باید دوباره pending شود تا callback
        # موفق بتواند آن را به‌صورت اتمیک paid کند.
        order.status = 'pending'
        order.ref_id = None
        db.session.commit()

    if request.method == 'POST':
        gateway = request.form.get('gateway', '').strip()
        _sandbox_on = _sandbox_allowed()
        valid_gateways = {item['id'] for item in GATEWAYS
                          if item['id'] != 'sandbox' or _sandbox_on}
        if not gateway or gateway not in valid_gateways:
            flash('لطفاً یکی از روش‌های پرداخت فعال را انتخاب کنید.', 'error')
            return redirect(url_for('shop.pay_start', code=code))
        # امنیت: درگاه آزمایشی در نسخهٔ نهایی در دسترس نیست.
        if gateway == 'sandbox' and not _sandbox_on:
            flash('پرداخت آزمایشی غیرفعال است؛ یک روش پرداخت واقعی انتخاب کنید.', 'error')
            return redirect(url_for('shop.pay_start', code=code))
        # کارت‌به‌کارت فقط با شماره کارت واقعی ثبت‌شده قابل استفاده است؛
        # ارسال دستی POST نباید این کنترل رابط را دور بزند.
        if gateway == 'card2card' and not gateway_ready(gateway, g.settings):
            flash('روش کارت‌به‌کارت هنوز توسط مدیر تکمیل نشده است.', 'error')
            return redirect(url_for('shop.pay_start', code=code))
        order.gateway = gateway
        db.session.commit()

        # کارت‌به‌کارت — ثبت فیش واریزی
        if gateway == 'card2card':
            return redirect(url_for('shop.card2card', code=code))
        # درگاه آزمایشی — شبیه‌ساز (فقط در حالت sandbox_mode=1)
        if gateway == 'sandbox':
            return redirect(url_for('shop.bank', code=code))
        # درگاه‌های واقعی — شروع پرداخت (اگر پیکربندی ناقص بود → خطا، نه شبیه‌ساز!)
        if not gateway_ready(gateway, g.settings):
            if not _sandbox_on:
                flash('این درگاه هنوز پیکربندی نشده است. لطفاً کمی بعد تلاش کنید.', 'error')
                return redirect(url_for('shop.pay_start', code=code))
            flash('پیکربندی این درگاه کامل نیست — وارد حالت آزمایشی شدید. شناسه‌ها را در پنل مدیریت ثبت کنید.', 'info')
            return redirect(url_for('shop.bank', code=code, gw=gateway))
        try:
            url = start_payment(gateway, g.settings, order, g.user,
                                url_for('shop.pay_verify', gw=gateway, code=order.code,
                                        _external=True))
            if isinstance(url, PaymentRedirect) and url.fields:
                return render_template('pay/forward.html', order=order,
                                       action_url=url.action_url,
                                       fields=url.fields,
                                       gateway_name=gateway_fa(gateway))
            return redirect(url)
        except Exception as e:
            flash(f'خطا در اتصال به درگاه {gateway_fa(gateway)}: {e}', 'error')
            return redirect(url_for('shop.pay_start', code=code))

    # فقط روش‌های واقعاً پیکربندی‌شده نمایش داده می‌شوند؛ کاربر دیگر پس از
    # انتخاب یک درگاه ناقص با خطای مبهم مواجه نمی‌شود.
    _sandbox_on = _sandbox_allowed()
    is_installment = bool(order.installment_count and order.installment_count > 1)
    _gws = []
    for item in GATEWAYS:
        if item['id'] == 'sandbox':
            if _sandbox_on:
                _gws.append(item)
            continue
        if item['id'] == 'card2card':
            if (g.settings.get('c2c_card') or '').strip() and not is_installment:
                _gws.append(item)
            continue
        if not gateway_ready(item['id'], g.settings):
            # فقط تست خودکار می‌تواند درگاه ناقص را برای پوشش رابط نمایش دهد؛
            # دموی فروش و production هر دو فقط درگاه کامل واقعی را می‌بینند.
            from runtime import automated_test_mode
            if not (automated_test_mode() and item['id'] == (order.gateway or '')):
                continue
        if is_installment and item.get('kind') != 'installment':
            continue
        if not is_installment and item.get('kind') == 'installment':
            continue
        _gws.append(item)
    # پیش‌انتخاب درگاه: از پارامتر ?gateway= (مثلاً بازگشت از پنل اقساطی) یا درگاه ثبت‌شده روی سفارش
    preselected = (request.args.get('gateway') or order.gateway or '').strip()
    if preselected and preselected not in [item['id'] for item in _gws]:
        preselected = ''
    return render_template('pay/gateway.html', order=order, gateways=_gws,
                           sandbox_mode=_sandbox_on, preselected=preselected,
                           is_installment=is_installment)


@shop_bp.route('/pay/verify/<gw>', methods=['GET', 'POST'])
def pay_verify(gw):
    """بازگشت از درگاه — تایید تراکنش برای همه درگاه‌های واقعی"""
    from gateways import verify_payment as _verify
    values = request.values
    code = values.get('code') or values.get('order_id') or values.get('ResNum') or ''
    order = Order.query.filter_by(code=code).first_or_404()
    if order.gateway and order.gateway != gw:
        abort(400)
    if order.status == 'paid':
        return redirect(url_for('shop.pay_result', code=code, status='success'))
    try:
        ok, msg, ref = _verify(gw, g.settings, order, values)
        if ok:
            _mark_paid(order, ref or f'{gw.upper()}-' + str(random.randint(100000, 999999)), f'{gw}_verify')
            return redirect(url_for('shop.pay_result', code=code, status='success'))
        order.status = 'failed'
        db.session.add(PaymentLog(order_id=order.id, gateway=gw, amount=order.final_total,
                                  status='failed', detail=msg))
        try:
            from models import Notification
            Notification.notify(order.user_id, 'پرداخت ناموفق بود ⚠️',
                                f'سفارش {order.code} پرداخت نشد — دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.',
                                '⚠️', url_for('shop.pay_start', code=code))
        except Exception:
            _lexc('blueprints/shop.py')
        db.session.commit()
        return redirect(url_for('shop.pay_result', code=code, status='failed'))
    except Exception as e:
        order.status = 'failed'
        db.session.add(PaymentLog(order_id=order.id, gateway=gw, amount=order.final_total,
                                  status='failed', detail=str(e)[:200]))
        db.session.commit()
        return redirect(url_for('shop.pay_result', code=code, status='unknown'))


@shop_bp.route('/pay/card2card/<code>', methods=['GET', 'POST'])
def card2card(code):
    """کارت‌به‌کارت — نمایش شماره کارت و ثبت فیش واریزی"""
    if not g.user:
        return redirect(url_for('auth.login'))
    order = Order.query.filter_by(code=code, user_id=g.user.id).first_or_404()
    if order.status == 'paid':
        return redirect(url_for('shop.pay_result', code=code, status='success'))
    existing = PaymentProof.query.filter_by(order_id=order.id, status='pending').first()

    if request.method == 'POST':
        payer_name = request.form.get('payer_name', '').strip()
        ref_number = request.form.get('ref_number', '').strip()
        amount = request.form.get('amount', '').strip()
        note = request.form.get('note', '').strip()
        paid_amount = int(amount) if amount.isdigit() else 0
        if not payer_name or not ref_number:
            flash('نام واریزکننده و شماره پیگیری الزامی است.', 'error')
        elif paid_amount != int(order.final_total or 0):
            flash('مبلغ واریزی باید دقیقاً برابر مبلغ نهایی سفارش باشد.', 'error')
        else:
            order.status = 'pending_verify'
            order.gateway = 'card2card'
            fname = None
            f = request.files.get('receipt')
            if f and f.filename:
                ext = os.path.splitext(f.filename)[1].lower()
                if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.pdf'):
                    flash('فرمت فیش مجاز نیست (jpg/png/pdf).', 'error')
                    return redirect(url_for('shop.card2card', code=code))
                from uploads_helper import file_content_is_safe
                if not file_content_is_safe(f.stream, ext):
                    flash('محتوای فایل ارسالی نامعتبر یا ناامن است.', 'error')
                    return redirect(url_for('shop.card2card', code=code))
                fname = f'proof-{order.code}{ext}'
                from uploads_helper import uploads_dir
                f.save(os.path.join(uploads_dir('proofs'), fname))
            if existing:
                existing.payer_name = payer_name
                existing.ref_number = ref_number
                existing.amount = paid_amount
                existing.note = note
                existing.file = fname or existing.file
                existing.status = 'pending'
            else:
                db.session.add(PaymentProof(order_id=order.id, payer_name=payer_name,
                                            ref_number=ref_number,
                                            amount=paid_amount,
                                            file=fname, note=note))
            db.session.add(PaymentLog(order_id=order.id, gateway='card2card',
                                      amount=order.final_total, status='pending_verify',
                                      detail=f'فیش ثبت شد — {payer_name} ({ref_number})'))
            db.session.commit()
            flash('فیش واریزی شما ثبت شد! پس از تایید توسط پشتیبانی، سفارش پردازش می‌شود. ⏳', 'success')
            return redirect(url_for('student.orders'))

    card_no = (g.settings.get('c2c_card') or '').strip()
    card_name = (g.settings.get('c2c_name') or g.settings.get('site_name') or '').strip()
    return render_template('pay/card2card.html', order=order, card_no=card_no,
                           card_name=card_name, existing=existing)


# ⚠️ مسیر عمداً «bank» نیست: آدرسی مثل /pay/bank/... روی یک صفحهٔ شبیه‌ساز
# پرداخت، برای خزندهٔ Google Safe Browsing شبیه صفحهٔ جعلی بانک دیده می‌شود.
# نام مسیر «sandbox» صریحاً می‌گوید این یک محیط آزمایشی است.
@shop_bp.route('/pay/sandbox/<code>', methods=['GET', 'POST'])
def bank(code):
    """شبیه‌ساز پرداخت برای تست — فقط در حالت sandbox_mode=1 قابل استفاده است.

    نام تابع (endpoint) برای سازگاری با url_for('shop.bank', ...) در قالب‌ها
    و کدهای موجود دست‌نخورده مانده؛ فقط URL عمومی به /pay/sandbox تغییر کرده.
    """
    from gateways import GATEWAY_MAP
    if not g.user:
        return redirect(url_for('auth.login'))
    order = Order.query.filter_by(code=code, user_id=g.user.id).first_or_404()
    gw = request.args.get('gw') or order.gateway or 'sandbox'
    if order.status == 'paid':
        return redirect(url_for('shop.pay_result', code=code, status='success'))
    # امنیت: در حالت غیرآزمایشی، هیچ مسیری به شبیه‌ساز پرداخت باز نیست
    if not _sandbox_allowed():
        flash('درگاه آزمایشی غیرفعال است.', 'error')
        return redirect(url_for('shop.pay_start', code=code))
    if request.method == 'POST':
        decision = request.form.get('decision', 'ok')
        # شبیه‌سازی پاسخ درگاه
        if decision == 'ok':
            ref = 'SANDBOX-' + str(random.randint(100000000, 999999999))
            _mark_paid(order, ref, 'sandbox_success')
            return redirect(url_for('shop.pay_result', code=code, status='success'))
        if decision == 'cancel':
            order.status = 'canceled'
            db.session.add(PaymentLog(order_id=order.id, gateway=order.gateway or 'sandbox',
                                      amount=order.final_total, status='canceled',
                                      detail='انصراف کاربر از پرداخت'))
            db.session.commit()
            return redirect(url_for('shop.pay_result', code=code, status='canceled'))
        order.status = 'failed'
        db.session.add(PaymentLog(order_id=order.id, gateway=order.gateway or 'sandbox',
                                  amount=order.final_total, status='failed', detail='خطای درگاه'))
        db.session.commit()
        return redirect(url_for('shop.pay_result', code=code, status='failed'))
    return render_template('pay/bank.html', order=order, gw=gw,
                           gw_meta=GATEWAY_MAP.get(gw, {}))


@shop_bp.route('/pay/zarinpal-verify')
def zarinpal_verify():
    authority = request.args.get('Authority', '')
    status = request.args.get('Status', '')
    order = Order.query.filter_by(ref_id=authority).first()
    if not order:
        order = Order.query.filter_by(code=request.args.get('code', '')).first()
    if not order:
        abort(404)
    if status == 'OK' and authority:
        try:
            merchant = g.settings.get('zarinpal_merchant')
            from validators import http_request
            resp = http_request('post', 'https://api.zarinpal.com/pg/v4/payment/verify.json', json={
                'merchant_id': merchant, 'amount': order.final_total, 'authority': authority,
            }, timeout=10)
            data = resp.json()
            if data.get('data', {}).get('code') == 100:
                ref = data['data'].get('ref_id', authority)
                _mark_paid(order, ref, 'zarinpal')
                return redirect(url_for('shop.pay_result', code=order.code, status='success'))
        except Exception:
            _lexc('blueprints/shop.py')
        order.status = 'failed'
        db.session.commit()
        return redirect(url_for('shop.pay_result', code=order.code, status='failed'))
    return redirect(url_for('shop.pay_result', code=order.code, status='canceled'))


def _mark_paid(order, ref, detail):
    # محافظ race اتمیک: فقط سفارش pending/pending_verify را paid کن — اگر قبلاً پرداخت شده
    # (callback تکراری درگاه یا verify دوباره) هیچ تغییری رخ نمی‌دهد
    _upd = Order.query.filter(Order.id == order.id,
                              Order.status.in_(['pending', 'pending_verify'])) \
        .update({'status': 'paid', 'paid_at': utcnow(), 'ref_id': ref},
                synchronize_session=False)
    if _upd == 0:
        return False
    db.session.refresh(order)
    order.ref_id = ref
    order.paid_at = utcnow()
    if order.coupon:
        order.coupon.used_count += 1
    db.session.add(PaymentLog(order_id=order.id, gateway=order.gateway, amount=order.final_total,
                              status='paid', ref_id=ref, detail=detail))
    if order.fulfillment_status == 'wallet_topup':
        # افزایش موجودی داخل همان transaction تایید پرداخت و به‌شکل SQL اتمیک؛
        # callback تکراری به‌دلیل گارد status بالا دوباره شارژ نمی‌کند.
        User.query.filter(User.id == order.user_id).update(
            {User.wallet_balance: db.func.coalesce(User.wallet_balance, 0) + order.final_total},
            synchronize_session=False)
        db.session.add(WalletTransaction(
            user_id=order.user_id, amount=order.final_total, type='charge',
            detail=f'شارژ آنلاین کیف پول — پرداخت {order.code}'))
        try:
            from models import Notification
            Notification.notify(
                order.user_id, 'کیف پول شارژ شد ✅',
                f'{order.final_total:,} تومان پس از تایید پرداخت به کیف پول شما اضافه شد.',
                '💰', url_for('features.wallet'))
        except Exception:
            _lexc('shop.mark_paid.wallet_notification')
        try:
            from models import ActivityLog
            db.session.add(ActivityLog(
                user_id=order.user_id, action='wallet_topup',
                detail=f'شارژ آنلاین {order.final_total:,} تومان ({order.gateway})',
                ip=request.headers.get('X-Forwarded-For', request.remote_addr or '')[:60]))
        except Exception:
            _lexc('shop.mark_paid.wallet_activity')
        db.session.commit()
        return True
    if order.installment_count and order.installment_count > 1:
        from gateways import GATEWAY_MAP
        if (GATEWAY_MAP.get(order.gateway) or {}).get('kind') == 'installment':
            from models import Installment
            Installment.query.filter_by(order_id=order.id).update(
                {'status': 'provider_managed'}, synchronize_session=False)
    for item in order.items:
        if item.course_id and not Enrollment.query.filter_by(user_id=order.user_id,
                                                             course_id=item.course_id).first():
            db.session.add(Enrollment(user_id=order.user_id, course_id=item.course_id, order_id=order.id))
        if item.product_id:
            # کاهش قطعی موجودی + اعلان
            try:
                from models import Product as _P
                quantity = max(1, int(item.quantity or 1))
                updated = _P.query.filter(_P.id == item.product_id,
                                          _P.stock >= quantity).update(
                    {_P.stock: _P.stock - quantity}, synchronize_session=False)
                if updated == 0:
                    # پرداخت انجام شده اما موجودی هم‌زمان توسط سفارش دیگری مصرف شده است.
                    # وضعیت ویژه مانع می‌شود کسری موجودی بی‌صدا پنهان بماند.
                    order.fulfillment_status = 'stock_issue'
            except Exception as _e:
                _lexc(f'shop.mark_paid.stock: {_e}')
    if order.fulfillment_status == 'stock_issue':
        try:
            from models import Notification
            admin_ids = [row[0] for row in db.session.query(User.id)
                         .filter(User.role.in_(['admin', 'super_admin']), User.is_active == True).all()]
            for admin_id in admin_ids:
                Notification.notify(admin_id, 'کسری موجودی سفارش ⚠️',
                                    f'سفارش {order.code} پرداخت شده اما موجودی یکی از محصولات کافی نیست.',
                                    '⚠️', url_for('admin.order_detail', oid=order.id))
        except Exception:
            _lexc('shop.mark_paid.stock_notification')
    # اعلان داخلی پرداخت موفق با متن متناسب با نوع اقلام
    try:
        from models import Notification
        has_course = any(item.course_id for item in order.items)
        has_product = any(item.product_id for item in order.items)
        if has_course and has_product:
            notice_body = f'سفارش {order.code} پرداخت شد؛ دوره فعال و محصول برای پردازش ارسال ثبت شد.'
            notice_url = url_for('student.orders')
        elif has_course:
            notice_body = f'سفارش {order.code} پرداخت شد و دوره در حساب شما فعال است.'
            notice_url = url_for('student.my_courses')
        else:
            notice_body = f'سفارش {order.code} پرداخت شد و محصول برای پردازش ارسال ثبت شد.'
            notice_url = url_for('student.orders')
        Notification.notify(order.user_id, 'پرداخت شما موفق بود 🎉',
                            notice_body, '✅', notice_url)
        from email_service import send_payment_notice
        buyer = db.session.get(User, order.user_id)
        if buyer and buyer.email:
            send_payment_notice(buyer, order, g.settings)
    except Exception:
        _lexc('blueprints/shop.py')
    # لاگ فعالیت
    try:
        from models import ActivityLog
        db.session.add(ActivityLog(user_id=order.user_id, action='payment',
                                   detail=f'پرداخت سفارش {order.code} ({order.gateway})',
                                   ip=request.headers.get('X-Forwarded-For', request.remote_addr or '')[:60]))
    except Exception:
        _lexc('blueprints/shop.py')
    # اعلان خودکار: پیامک خرید + پیام در پیام‌رسان‌های متصل
    try:
        buyer = db.session.get(User, order.user_id)
        from sms import send_sms
        if buyer and buyer.phone and getattr(buyer, 'notify_sms', True) is not False:
            send_sms(buyer.phone, f'پرداخت سفارش {order.code} به مبلغ {order.final_total:,} تومان تایید شد. وضعیت سفارش را در حساب خود ببینید. — {g.settings.get("site_name", "آکادمی")}', g.settings)
        from messengers import send_to_all
        send_to_all(f'🎉 پرداخت جدید: سفارش {order.code} به مبلغ {order.final_total:,} تومان توسط {buyer.name if buyer else ""}',
                    g.settings, url_for('admin.orders', _external=True))
    except Exception:
        _lexc('blueprints/shop.py')
    # پاداش معرفی فقط با درصد صریح مدیر و فقط روی اولین خرید.
    try:
        buyer = db.session.get(User, order.user_id)
        from models import Order as _O
        try:
            referral_percent = max(0, min(50, int(g.settings.get('referral_bonus_percent') or 0)))
        except (TypeError, ValueError):
            referral_percent = 0
        first_paid = _O.query.filter(_O.user_id == order.user_id,
                                     _O.status == 'paid', _O.id != order.id).count() == 0
        if buyer and buyer.referred_by and first_paid and referral_percent:
            referrer = db.session.get(User, buyer.referred_by)
            if referrer:
                bonus = round(order.final_total * referral_percent / 100)
                from gamification import wallet_bonus
                wallet_bonus(referrer, bonus, f'پاداش معرفی {buyer.name}')
    except Exception:
        _lexc('blueprints/shop.py')
    # ── Cashback یکپارچه: درصدی از مبلغ خرید به کیف پول خود خریدار برمی‌گردد ──
    try:
        from bnpl import grant_cashback
        grant_cashback(order)
    except Exception:
        _lexc('blueprints/shop.py')
    # ثبت نقطه قیمت برای نمودار قیمت (PriceHistory)
    try:
        from blueprints.builder import record_price
        for it in order.items:
            if it.course_id:
                record_price('course', it.course_id, it.course.price or 0, it.course.final_price or 0)
            if it.product_id:
                from models import Product as _P
                pr = db.session.get(_P, it.product_id)
                if pr:
                    record_price('product', pr.id, pr.price or 0, pr.final_price or 0)
    except Exception:
        _lexc('blueprints/shop.py')
    db.session.commit()


@shop_bp.route('/pay/result/<code>')
def pay_result(code):
    if not g.user:
        return redirect(url_for('auth.login'))
    order = Order.query.filter_by(code=code).first_or_404()
    if order.user_id != g.user.id and not getattr(g.user, 'is_admin', False):
        abort(403)
    status = request.args.get('status', '')
    # استعلام خودکار: اگر وضعیت «نامشخص» است ولی پرداخت واقعاً انجام شده
    if status in ('', 'unknown') and order.status == 'paid':
        status = 'success'
    elif status in ('', 'unknown') and order.status == 'canceled':
        status = 'canceled'
    return render_template('pay/result.html', order=order, status=status)
