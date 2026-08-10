# -*- coding: utf-8 -*-
"""سیستم پرداخت اقساطی و BNPL — مشابه اسنپ‌پی/دیجی‌پی + Cashback یکپارچه

- لندینگ اختصاصی خرید اقساطی ۴ ماهه (شبیه اسنپ‌پی) برای سفارش‌های گران‌قیمت
- اتصال به درگاه‌های اقساطی موجود: snapppay / digipay / tarb (از gateways.py)
- Cashback خودکار پس از هر خرید موفق (درصد قابل تنظیم در تنظیمات)
"""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, jsonify, session)
from datetime import datetime, timedelta

from models import (db, utcnow, Order, User, WalletTransaction, Setting,
                    Installment, Course, Product)
from jdates import jdate, fa, jdatetime

bnpl_bp = Blueprint('bnpl', __name__)


# ------------------------------------------------------------------
# تنظیمات BNPL
# ------------------------------------------------------------------
def _cfg(key, default):
    s = db.session.get(Setting, key)
    return (s.value if s and s.value else default)


def max_installments():
    """حداکثر تعداد قسط — از تنظیمات (پیش‌فرض ۴)"""
    try:
        return int(_cfg('bnpl_max_installments', '4'))
    except Exception:
        return 4


def cashback_percent():
    """درصد Cashback پس از خرید موفق — پیش‌فرض ۲٪"""
    try:
        return int(_cfg('cashback_percent', '2'))
    except Exception:
        return 2


def bnpl_enabled():
    return _cfg('bnpl_enabled', '1') == '1'


# ------------------------------------------------------------------
# لندینگ اقساطی (شبیه اسنپ‌پی)
# ------------------------------------------------------------------
@bnpl_bp.route('/bnpl/<code>')
def bnpl_page(code):
    """صفحه اختصاصی خرید اقساطی — ۴ قسط ماهانه با کارمزد شفاف"""
    if not g.user:
        return redirect(url_for('auth.login', next=request.path))
    order = Order.query.filter_by(code=code, user_id=g.user.id).first_or_404()
    if order.status == 'paid':
        flash('این سفارش قبلاً پرداخت شده است.', 'info')
        return redirect(url_for('shop.invoice', code=code))
    n = max_installments()
    total = order.final_total
    fee = 0  # کارمزد اقساط (در نسخه واقعی از قرارداد درگاه)
    each = (total + fee) // n
    remainder = (total + fee) - each * (n - 1)
    first_due = datetime.now() + timedelta(days=1)
    schedule = []
    for i in range(1, n + 1):
        amt = remainder if i == n else each
        due = first_due + timedelta(days=30 * (i - 1))
        schedule.append(dict(num=i, amount=amt,
                             date_fa=jdate(due),
                             date_en=due.strftime('%Y-%m-%d')))
    providers = []
    from gateways import GATEWAY_MAP
    for pid in ('snapppay', 'digipay', 'tarb'):
        prov = GATEWAY_MAP.get(pid)
        if prov and prov['kind'] == 'installment':
            providers.append(prov)
    return render_template('bnpl/landing.html', order=order, n=n, fee=fee,
                           each=each, remainder=remainder, schedule=schedule,
                           providers=providers, fa=fa, bnpl_enabled=bnpl_enabled(),
                           cashback_percent=cashback_percent)


@bnpl_bp.route('/bnpl/<code>/start', methods=['POST'])
def bnpl_start(code):
    """شروع خرید اقساطی — ذخیره تعداد قسط و ریدایرکت به درگاه"""
    if not g.user:
        return redirect(url_for('auth.login'))
    order = Order.query.filter_by(code=code, user_id=g.user.id).first_or_404()
    gateway = request.form.get('gateway', 'snapppay')
    num = request.form.get('num', 4, type=int)
    num = max(2, min(num, max_installments()))
    order.installment_count = num
    db.session.commit()
    return redirect(url_for('shop.pay_start', code=code, gateway=gateway))


# ------------------------------------------------------------------
# Cashback — برگشت وجه به کیف پول پس از پرداخت موفق
# ------------------------------------------------------------------
def grant_cashback(order, base_amount=None):
    """بعد از پرداخت موفق: درصدی از مبلغ به کیف پول برمی‌گردد (CashbackLog + اعلان)
    از shop.py بعد از تأیید پرداخت صدا زده می‌شود."""
    from ext_models import CashbackLog
    pct = cashback_percent()
    if pct <= 0:
        return None
    base = base_amount or order.final_total
    amount = int(base * pct / 100)
    if amount <= 0:
        return None
    u = db.session.get(User, order.user_id)
    if not u:
        return None
    u.wallet_balance = (u.wallet_balance or 0) + amount
    db.session.add(WalletTransaction(
        user_id=u.id, amount=amount, type='bonus',
        detail=f'Cashback خرید {fa("{:,}".format(base))} تومان ({pct}٪) — سفارش {order.code}'))
    db.session.add(CashbackLog(user_id=u.id, order_id=order.id, amount=amount,
                               percent=pct, base_amount=base,
                               note=f'بازگشت {pct}٪ پس از پرداخت موفق'))
    from models import Notification
    try:
        db.session.add(Notification(user_id=u.id,
                                    title='🎁 Cashback به کیف پول شما واریز شد',
                                    body=f'{fa("{:,}".format(amount))} تومان بابت خرید اخیر به کیف پول اضافه شد.'))
    except Exception:
        pass
    db.session.commit()
    return amount


# ------------------------------------------------------------------
# API — وضعیت اقساط و پرداخت قسط
# ------------------------------------------------------------------
@bnpl_bp.route('/api/bnpl/status/<code>')
def bnpl_status(code):
    """وضعیت اقساط یک سفارش (JSON) — برای ویجت/داشبورد"""
    if not g.user:
        return jsonify(ok=False, msg='ابتدا وارد شوید'), 401
    order = Order.query.filter_by(code=code, user_id=g.user.id).first_or_404()
    insts = Installment.query.filter_by(order_id=order.id).order_by(Installment.number).all()
    return jsonify(ok=True, code=code,
                   total=order.final_total,
                   count=order.installment_count,
                   items=[dict(number=i.number, amount=i.amount,
                               status=i.status,
                               due_fa=jdate(i.due_date) if i.due_date else '',
                               paid_fa=jdatetime(i.paid_at) if i.paid_at else '')
                          for i in insts])


def init_bnpl(app):
    app.register_blueprint(bnpl_bp)
