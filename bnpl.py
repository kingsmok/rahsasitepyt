# -*- coding: utf-8 -*-
"""سیستم پرداخت اقساطی و BNPL — پنل اقساطی اسنپ‌پی / ترب / دیجی‌پی + Cashback

همهٔ منطق اقساط در همین ماژول «یک‌جا» نگه داشته شده است:
  - محاسبهٔ برنامهٔ اقساط (installment_schedule)
  - ساخت/بازسازی قسط‌های سفارش (build_installments)
  - پنل اقساطی (bnpl_page) که سرویس‌های اقساطی را به‌همراه طرح و کارمزدشان نشان می‌دهد
  - شروع پرداخت قسط اول از طریق درگاه همان سرویس (bnpl_start → shop.pay_start)

درگاه‌های اقساطی: snapppay (اسنپ‌پی) / tarb (ترب) / digipay (دیجی‌پی).
"""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, jsonify)
from datetime import datetime, timedelta

from models import (db, utcnow, Order, User, Setting, Installment)
from jdates import jdate, fa, jdatetime
from validators import safe_int

bnpl_bp = Blueprint('bnpl', __name__)


# ------------------------------------------------------------------
# تنظیمات BNPL
# ------------------------------------------------------------------
def _cfg(key, default):
    s = db.session.get(Setting, key)
    return (s.value if s and s.value else default)


def max_installments():
    """حداکثر تعداد قسط سراسری — از تنظیمات (پیش‌فرض ۴)."""
    try:
        return int(_cfg('bnpl_max_installments', '4'))
    except Exception:
        return 4


def cashback_percent():
    """درصد Cashback فقط با تنظیم صریح مدیر؛ پیش‌فرض صفر."""
    try:
        return max(0, min(50, int(_cfg('cashback_percent', '0'))))
    except Exception:
        return 0


def bnpl_enabled():
    """اقساط فقط پس از فعال‌سازی مدیر؛ تست داخلی از این قاعده مستثناست."""
    from runtime import automated_test_mode
    return automated_test_mode() or _cfg('bnpl_enabled', '0') == '1'


def _providers():
    """فقط سرویس‌های اقساطی واقعاً پیکربندی‌شده را برگردان."""
    from gateways import gateway_plan, gateway_ready, INSTALLMENT_PROVIDERS
    from runtime import automated_test_mode
    settings = getattr(g, 'settings', {}) or {}
    out = []
    for pid in INSTALLMENT_PROVIDERS:
        if not gateway_ready(pid, settings) and not automated_test_mode():
            continue
        plan = gateway_plan(pid)
        if plan:
            plan['max_installments'] = min(plan['max_installments'], max_installments())
            out.append(plan)
    return out


# ------------------------------------------------------------------
# محاسبهٔ برنامهٔ اقساط و ساخت قسط‌ها — «منبع واحد» (یک‌جا)
# ------------------------------------------------------------------
def installment_schedule(total, n, fee_pct=0):
    """برنامهٔ پرداخت اقساطی: قسط اول (پیش‌پرداخت) بزرگ‌تر، مابقی مساوی.

    خروجی: [dict(num, amount, date_fa?, date_en?)] — بدون تاریخ، فقط مبالغ.
    """
    n = max(1, int(n or 1))
    total = int(total or 0)
    with_fee = total + round(total * int(fee_pct or 0) / 100)
    base = with_fee // n
    out = []
    for i in range(1, n + 1):
        amt = (with_fee - base * (n - 1)) if i == 1 else base
        out.append(dict(num=i, amount=amt))
    return out


def _schedule_with_dates(total, n, fee_pct=0):
    """برنامهٔ اقساط + تاریخ سررسید شمسی (برای نمایش در پنل)."""
    sched = installment_schedule(total, n, fee_pct)
    first_due = datetime.now() + timedelta(days=1)
    for p in sched:
        due = first_due + timedelta(days=30 * (p['num'] - 1))
        p['date_fa'] = jdate(due)
        p['date_en'] = due.strftime('%Y-%m-%d')
    return sched


def build_installments(order, n, fee_pct=0):
    """بازسازی قسط‌های یک سفارش بر اساس تعداد قسط انتخاب‌شده.

    یک‌جا هم قسط‌ها را می‌سازد هم تعداد قسط سفارش را ثبت می‌کند.
    """
    from models import Installment
    Installment.query.filter_by(order_id=order.id).delete()
    sched = installment_schedule(order.final_total, n, fee_pct)
    for p in sched:
        due = utcnow() + timedelta(days=30 * (p['num'] - 1))
        db.session.add(Installment(order_id=order.id, number=p['num'],
                                   amount=p['amount'], due_date=due))
    order.installment_count = n
    db.session.commit()
    return sched


# ------------------------------------------------------------------
# پنل اقساطی — انتخاب سرویس اقساط (اسنپ‌پی / ترب / دیجی‌پی) و تعداد قسط
# ------------------------------------------------------------------
@bnpl_bp.route('/bnpl/<code>')
def bnpl_page(code):
    """پنل اقساطی: انتخاب سرویس اقساطی + تعداد قسط + مشاهدهٔ برنامهٔ پرداخت."""
    if not g.user:
        return redirect(url_for('auth.login', next=request.path))
    order = Order.query.filter_by(code=code, user_id=g.user.id).first_or_404()
    if order.status == 'paid':
        flash('این سفارش قبلاً پرداخت شده است.', 'info')
        return redirect(url_for('student.invoice', code=code))
    if not bnpl_enabled():
        flash('پرداخت اقساطی برای این فروشگاه فعال نیست.', 'info')
        return redirect(url_for('shop.pay_start', code=code))
    providers = _providers()
    if not providers:
        flash('سرویس اقساطی فعالی در دسترس نیست. لطفاً بعداً تلاش کنید یا پرداخت یکجا را انتخاب کنید.', 'warning')
        return redirect(url_for('shop.pay_start', code=code))
    # تعداد قسط: از query (پیش‌انتخاب) یا تعداد قسط فعلی سفارش یا حداکثر
    try:
        n = safe_int(request.args.get('n'), order.installment_count or max_installments(), 2, 4)
    except Exception:
        n = max_installments()
    max_n = min(max_installments(), max(p['max_installments'] for p in providers))
    n = max(2, min(n, max_n))
    schedule = _schedule_with_dates(order.final_total, n)
    return render_template('bnpl/landing.html', order=order, n=n, max_n=max_n,
                           schedule=schedule, providers=providers, fa=fa,
                           bnpl_enabled=bnpl_enabled(),
                           cashback_percent=cashback_percent)


@bnpl_bp.route('/bnpl/<code>/start', methods=['POST'])
def bnpl_start(code):
    """شروع خرید اقساطی — ساخت قسط‌ها و هدایت به درگاه همان سرویس اقساطی."""
    if not g.user:
        return redirect(url_for('auth.login'))
    order = Order.query.filter_by(code=code, user_id=g.user.id).first_or_404()
    if not bnpl_enabled():
        flash('پرداخت اقساطی فعال نیست.', 'error')
        return redirect(url_for('shop.pay_start', code=code))
    gateway = request.form.get('gateway', '').strip()
    plans = {p['id']: p for p in _providers()}
    if gateway not in plans:
        flash('سرویس اقساطی انتخاب‌شده معتبر نیست.', 'error')
        return redirect(url_for('bnpl.bnpl_page', code=code))
    num = request.form.get('num', 0, type=int)
    num = max(2, min(num, plans[gateway]['max_installments']))
    # ساخت/بازسازی قسط‌ها و ثبت تعداد قسط — یک‌جا
    build_installments(order, num, fee_pct=plans[gateway]['fee_pct'])
    # انتخاب درگاه اقساطی برای پرداخت
    order.gateway = gateway
    db.session.commit()
    flash(f'خرید اقساطی با {plans[gateway]["name"]} در {fa(num)} قسط ثبت شد — قسط اول (پیش‌پرداخت) اکنون پرداخت می‌شود.', 'info')
    # هدایت به صفحهٔ درگاه با درگاه اقساطیِ از پیش انتخاب‌شده
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
    # از منبع واحد کیف پول استفاده می‌شود (قبلاً منطق افزایش موجودی و ثبت
    # WalletTransaction این‌جا کپی شده بود — نقض DRY و ناامن در برابر
    # همزمانی: cashback و پاداش معرفی می‌توانند هم‌زمان اجرا شوند).
    from gamification import wallet_bonus
    wallet_bonus(u, amount,
                 f'Cashback خرید {fa("{:,}".format(base))} تومان ({pct}٪) — سفارش {order.code}')
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
    """وضعیت اقساط یک سفارش (JSON) — برای ویجت/داشبورد."""
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
