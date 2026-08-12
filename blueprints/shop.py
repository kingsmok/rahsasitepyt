# -*- coding: utf-8 -*-
"""سبد خرید، تسویه حساب و درگاه‌های پرداخت"""
import os
import random
import requests
from datetime import datetime
try:
    from datetime import UTC
except ImportError:  # پایتون < 3.11 (هاست‌های اشتراکی)
    from datetime import timezone as _tz_utc
    UTC = _tz_utc.utc
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, session, abort)
from werkzeug.utils import secure_filename
from models import (utcnow, db, User, Course, Order, OrderItem, Coupon, Enrollment,
                    PaymentLog, PaymentProof)

shop_bp = Blueprint('shop', __name__)

from gateways import GATEWAYS as _GW, gateway_ready, start_payment, verify_payment, gateway_fa
from validators import log_exc as _lexc
from jdates import fa

GATEWAYS = _GW


def _sandbox_allowed():
    """آیا شبیه‌ساز پرداخت مجاز است؟

    شرط ۱: حالت آزمایشی در تنظیمات روشن باشد (sandbox_mode=1)
    شرط ۲: اپ در حالت production نباشد، مگر اینکه مدیر صریحاً
            ALLOW_SANDBOX_IN_PRODUCTION=1 را ست کرده باشد.

    دلیل شرط ۲: صفحه شبیه‌ساز روی یک سایت واقعیِ در دسترس عموم،
    توسط Google Safe Browsing به‌عنوان صفحه فیشینگ بانکی شناسایی
    می‌شود و کل دامنه با پیام «Dangerous site» در کروم مسدود می‌گردد.
    """
    if str(g.settings.get('sandbox_mode', '0')) != '1':
        return False
    _prod = (os.environ.get('FLASK_ENV') == 'production' or
             os.environ.get('APP_ENV') == 'production')
    if _prod and os.environ.get('ALLOW_SANDBOX_IN_PRODUCTION', '0') != '1':
        return False
    return True


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
    return sum(o.final_price for k, o in items)


@shop_bp.route('/cart')
def cart():
    courses = _cart_courses()
    items = _cart_items()
    total = _cart_total_all(items)
    return render_template('cart.html', courses=courses, items=items, total=total)


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

    # بررسی موجودی محصولات — جلوگیری از خرید محصول ناموجود
    for kind, obj in items:
        if kind == 'product' and getattr(obj, 'stock', 1) <= 0:
            flash(f'«{obj.title}» موجود نیست — از سبد حذف شد.', 'error')
            cart = session.get('cart', [])
            try:
                cart.remove(obj.id)
            except ValueError:
                pass
            session['cart'] = cart
            return redirect(url_for('shop.cart'))

    subtotal = _cart_total_all(items) if items else _cart_total(courses)
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

    # تخفیف وفاداری: ۵٪ برای دانشجویانی که قبلاً دوره خریده‌اند (جدا از کوپن)
    loyalty_discount = 0
    has_past_purchase = Enrollment.query.filter_by(user_id=g.user.id).count() > 0
    if has_past_purchase and final > 0:
        loyalty_discount = round(final * 5 / 100)
        final = max(0, final - loyalty_discount)

    if request.method == 'POST' and request.form.get('action') == 'remove_coupon':
        session.pop('coupon_code', None)
        return redirect(url_for('shop.checkout'))

    if request.method == 'POST' and request.form.get('action') == 'create_order':
        code = f"AC-{datetime.now():%y%m%d}-{random.randint(1000, 9999)}"
        while Order.query.filter_by(code=code).first():
            code = f"AC-{datetime.now():%y%m%d}-{random.randint(1000, 9999)}"
        order = Order(code=code, user_id=g.user.id, total=subtotal,
                      discount=discount + loyalty_discount,
                      final_total=final, coupon=coupon, status='pending',
                      installment_count=installment_count)
        from blueprints.products import _cart_items as _ci
        for kind, obj in _ci():
            if kind == 'course':
                order.items.append(OrderItem(course_id=obj.id, price=obj.final_price))
            else:
                order.items.append(OrderItem(product_id=obj.id, price=obj.final_price))
                # کاهش موجودی فقط بعد از پرداخت موفق انجام میشود (در _mark_paid)
        db.session.add(order)
        db.session.flush()
        # ساخت قسط‌ها (هر قسط ۳۰٪ — اولین قسط با پرداخت اول)
        if installment_count > 1:
            from models import Installment
            from datetime import timedelta as _td
            each = round(final * 30 / 100)
            remainder = final - each * (installment_count - 1)
            for n in range(1, installment_count + 1):
                amt = remainder if n == 1 else each
                due = utcnow() + _td(days=30 * (n - 1))
                db.session.add(Installment(order_id=order.id, number=n,
                                           amount=amt, due_date=due))
        db.session.commit()
        session.pop('cart', None)
        session.pop('coupon_code', None)
        if installment_count > 1:
            flash(f'سفارش ثبت شد — پرداخت در {installment_count} قسط. قسط اول اکنون پرداخت می‌شود.', 'info')
        else:
            flash('سفارش شما ثبت شد. لطفاً پرداخت را تکمیل کنید.', 'info')
        return redirect(url_for('shop.pay_start', code=code))

    from blueprints.products import _cart_items as _ci2
    items = _ci2()
    return render_template('checkout.html', courses=courses, items=items, subtotal=subtotal,
                           discount=discount, final=final, coupon=coupon, gateways=GATEWAYS,
                           loyalty_discount=loyalty_discount, has_past_purchase=has_past_purchase,
                           installment_count=installment_count)


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
    # امنیت: در حالت غیرآزمایشی، پرداخت فقط از طریق درگاه انجام می‌شود (نه POST ساده)
    if not _sandbox_allowed():
        flash('پرداخت قسط از طریق درگاه انجام می‌شود — در حال انتقال...', 'info')
        return redirect(url_for('shop.pay_start', code=code))
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
                _pr = db.session.get(_PP, item.product_id)
                if _pr:
                    _pr.stock = max(0, (_pr.stock or 0) - 1)
        from models import Notification
        Notification.notify(order.user_id, 'تکمیل پرداخت اقساطی 🎉',
                            f'همه قسط‌های سفارش {order.code} پرداخت شد — دوره فعال است!', '✅',
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
        flash('این سفارش قبلاً پرداخت شده و دوره فعال است. 🎉', 'info')
        return redirect(url_for('student.invoice', code=code))
    if order.status == 'canceled':
        # اجازه پرداخت مجدد سفارش لغوشده
        order.status = 'pending'
        db.session.commit()

    if request.method == 'POST':
        gateway = request.form.get('gateway', 'sandbox')
        # امنیت: درگاه آزمایشی فقط وقتی sandbox_mode=1 باشد در دسترس است
        # (جلوگیری از «خرید رایگان» در سایت واقعی)
        _sandbox_on = _sandbox_allowed()
        if gateway == 'sandbox' and not _sandbox_on:
            flash('درگاه آزمایشی غیرفعال است — یک درگاه پرداخت واقعی انتخاب کنید.', 'error')
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
            return redirect(url)
        except Exception as e:
            flash(f'خطا در اتصال به درگاه {gateway_fa(gateway)}: {e}', 'error')
            return redirect(url_for('shop.pay_start', code=code))

    # درگاه آزمایشی فقط در حالت sandbox_mode=1 به کاربر نمایش داده می‌شود
    _sandbox_on = _sandbox_allowed()
    _gws = [g for g in GATEWAYS if g['id'] != 'sandbox' or _sandbox_on]
    return render_template('pay/gateway.html', order=order, gateways=_gws,
                           sandbox_mode=_sandbox_on)


@shop_bp.route('/pay/verify/<gw>')
def pay_verify(gw):
    """بازگشت از درگاه — تایید تراکنش برای همه درگاه‌های واقعی"""
    from gateways import verify_payment as _verify
    code = request.args.get('code') or request.args.get('order_id') or ''
    order = Order.query.filter_by(code=code).first_or_404()
    try:
        ok, msg, ref = _verify(gw, g.settings, order, request.args)
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
        if not payer_name or not ref_number:
            flash('نام واریزکننده و شماره پیگیری الزامی است.', 'error')
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
                fname = f'proof-{order.code}{ext}'
                from uploads_helper import uploads_dir
                f.save(os.path.join(uploads_dir('proofs'), fname))
            if existing:
                existing.payer_name = payer_name
                existing.ref_number = ref_number
                existing.amount = int(amount) if amount.isdigit() else 0
                existing.note = note
                existing.file = fname or existing.file
                existing.status = 'pending'
            else:
                db.session.add(PaymentProof(order_id=order.id, payer_name=payer_name,
                                            ref_number=ref_number,
                                            amount=int(amount) if amount.isdigit() else 0,
                                            file=fname, note=note))
            db.session.add(PaymentLog(order_id=order.id, gateway='card2card',
                                      amount=order.final_total, status='pending_verify',
                                      detail=f'فیش ثبت شد — {payer_name} ({ref_number})'))
            db.session.commit()
            flash('فیش واریزی شما ثبت شد! پس از تایید توسط پشتیبانی، دوره فعال می‌شود. ⏳', 'success')
            return redirect(url_for('student.orders'))

    card_no = (g.settings.get('c2c_card') or '').strip()
    card_name = (g.settings.get('c2c_name') or g.settings.get('site_name') or '').strip()
    return render_template('pay/card2card.html', order=order, card_no=card_no,
                           card_name=card_name, existing=existing)


@shop_bp.route('/pay/bank/<code>', methods=['GET', 'POST'])
def bank(code):
    """شبیه‌ساز درگاه بانکی برای تست — فقط در حالت sandbox_mode=1 قابل استفاده است"""
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
    # محافظ race اتمیک: فقط سفارش pending را paid کن — اگر قبلاً پرداخت شده
    # (callback تکراری درگاه یا verify دوباره) هیچ تغییری رخ نمی‌دهد
    _upd = Order.query.filter_by(id=order.id, status='pending') \
        .update({'status': 'paid', 'paid_at': utcnow(), 'ref_id': ref})
    if _upd == 0:
        return False
    db.session.refresh(order)
    order.ref_id = ref
    order.paid_at = utcnow()
    if order.coupon:
        order.coupon.used_count += 1
    db.session.add(PaymentLog(order_id=order.id, gateway=order.gateway, amount=order.final_total,
                              status='paid', ref_id=ref, detail=detail))
    for item in order.items:
        if item.course_id and not Enrollment.query.filter_by(user_id=order.user_id,
                                                             course_id=item.course_id).first():
            db.session.add(Enrollment(user_id=order.user_id, course_id=item.course_id, order_id=order.id))
        if item.product_id:
            # کاهش قطعی موجودی + اعلان
            prod = db.session.get(Product, item.product_id) if 'Product' in dir() else None
            try:
                from models import Product as _P
                prod = db.session.get(_P, item.product_id)
                if prod:
                    prod.stock = max(0, (prod.stock or 0) - 1)
            except Exception as _e:
                _lexc(f'shop.mark_paid.stock: {_e}')
    # اعلان داخلی پرداخت موفق
    try:
        from models import Notification
        Notification.notify(order.user_id, 'پرداخت شما موفق بود 🎉',
                            f'سفارش {order.code} پرداخت شد — دوره فعال است.',
                            '✅', url_for('student.my_courses'))
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
            send_sms(buyer.phone, f'✅ پرداخت سفارش {order.code} به مبلغ {order.final_total:,} تومان انجام شد. دوره فعال شد! — {g.settings.get("site_name", "آکادمی")}', g.settings)
        from messengers import send_to_all
        send_to_all(f'🎉 پرداخت جدید: سفارش {order.code} به مبلغ {order.final_total:,} تومان توسط {buyer.name if buyer else ""}',
                    g.settings, url_for('admin.orders', _external=True))
    except Exception:
        _lexc('blueprints/shop.py')
    # پاداش ارجاع: ۱۰٪ اولین خرید به کیف پول معرف
    try:
        buyer = db.session.get(User, order.user_id)
        from models import Order as _O
        first_paid = _O.query.filter(_O.user_id == order.user_id,
                                     _O.status == 'paid', _O.id != order.id).count() == 0
        if buyer and buyer.referred_by and first_paid:
            referrer = db.session.get(User, buyer.referred_by)
            if referrer:
                bonus = round(order.final_total * 10 / 100)
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
