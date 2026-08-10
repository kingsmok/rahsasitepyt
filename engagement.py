# -*- coding: utf-8 -*-
"""امکانات تعامل کاربران ایرانی

- گردونه شانس (مشابه دیجی‌کالا): یک چرخش در روز برای کاربران — جایزه: کد تخفیف/اعتبار کیف پول
- نقشه هوشمند (Map.ir / Neshan): انتخاب استان/شهر برای آدرس پستی + برآورد هزینه پیک اسنپ/تپسی
- افیلیت مارکتینگ: لینک اختصاصی معرفی + پورسانت خودکار (۱۰٪ اولین خرید — متصل به shop)
"""
import random
import uuid

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, jsonify)
from models import db, utcnow, User, Coupon, Setting
from jdates import jdate, fa
from ext_models import SpinResult
from validators import log_exc as _lexc

engage_bp = Blueprint('engage', __name__)

# استان‌ها و شهرهای پرکاربرد برای انتخاب آدرس (ارسال پکیج آموزشی)
IRAN_CITIES = {
    'تهران': ['تهران', 'کرج', 'اسلامشهر', 'ری', 'شهریار'],
    'اصفهان': ['اصفهان', 'کاشان', 'نجف‌آباد', 'خمینی‌شهر'],
    'خراسان رضوی': ['مشهد', 'نیشابور', 'سبزوار', 'تربت حیدریه'],
    'فارس': ['شیراز', 'مرودشت', 'لار', 'جهرم'],
    'آذربایجان شرقی': ['تبریز', 'مراغه', 'مرند'],
    'آذربایجان غربی': ['ارومیه', 'خوی', 'میاندوآب'],
    'خوزستان': ['اهواز', 'آبادان', 'دزفول', 'بندر ماهشهر'],
    'مازندران': ['ساری', 'آمل', 'بابل', 'قائم‌شهر'],
    'گیلان': ['رشت', 'انزلی', 'لاهیجان'],
    'البرز': ['کرج', 'فردیس', 'هشتگرد'],
    'قزوین': ['قزوین', 'تاکستان'],
    'قم': ['قم'],
    'کرمان': ['کرمان', 'رفسنجان', 'سیرجان'],
    'یزد': ['یزد', 'اردکان', 'میبد'],
    'سمنان': ['سمنان', 'شاهرود', 'دامغان'],
    'هرمزگان': ['بندرعباس', 'قشم', 'کیش'],
    'بوشهر': ['بوشهر', 'برازجان'],
    'کردستان': ['سنندج', 'سقز'],
    'همدان': ['همدان', 'ملایر'],
    'مرکزی': ['اراک', 'ساوه'],
    'لرستان': ['خرم‌آباد', 'بروجرد'],
    'زنجان': ['زنجان', 'ابهر'],
    'اردبیل': ['اردبیل', 'پارس‌آباد'],
    'چهارمحال': ['شهرکرد', 'بروجن'],
    'کهگیلویه': ['یاسوج', 'گچساران'],
    'ایلام': ['ایلام', 'مهران'],
    'کرمانشاه': ['کرمانشاه', 'کنگاور'],
    'گلستان': ['گرگان', 'گنبد کاووس'],
    'خراسان شمالی': ['بجنورد', 'شیروان'],
    'خراسان جنوبی': ['بیرجند', 'قائن'],
    'سیستان': ['زاهدان', 'زابل'],
}
PROVINCES = list(IRAN_CITIES.keys())


def _cfg(key, default=''):
    s = db.session.get(Setting, key)
    return (s.value if s and s.value is not None else default)


def _today():
    return jdate(utcnow())


# ============================================================
# گردونه شانس
# ============================================================
# وزندهی: [نوع, مقدار(تومان/درصد), برچسب، احتمال]
SPIN_WHEEL = [
    ('wallet', 50000, '۵۰ هزار تومان کیف پول', 12),
    ('coupon', 20, 'کوپن ۲۰٪ تخفیف', 15),
    ('wallet', 20000, '۲۰ هزار تومان کیف پول', 20),
    ('none', 0, 'شانس دوباره', 18),
    ('coupon', 10, 'کوپن ۱۰٪ تخفیف', 20),
    ('wallet', 100000, '۱۰۰ هزار تومان کیف پول', 8),
    ('coupon', 30, 'کوپن ۳۰٪ تخفیف', 7),
]


def _pick_prize():
    total_w = sum(w[3] for w in SPIN_WHEEL)
    r = random.randint(1, total_w)
    acc = 0
    for ptype, val, label, w in SPIN_WHEEL:
        acc += w
        if r <= acc:
            return ptype, val, label
    return 'none', 0, 'شانس دوباره'


def _make_coupon(percent):
    code = 'SPIN' + str(uuid.uuid4())[:8].upper()
    try:
        db.session.add(Coupon(code=code, type='percent', value=percent,
                              max_uses=1, min_amount=50000, expires_at=None, is_active=True))
        db.session.flush()
    except Exception as e:
        _lexc('engagement.spin')
        return None, str(e)[:60]
    return code, None


@engage_bp.route('/spin')
def spin_page():
    """صفحه گردونه شانس"""
    if not g.user:
        return redirect(url_for('auth.login', next='/spin'))
    today = _today()
    last = (SpinResult.query.filter_by(user_id=g.user.id)
            .order_by(SpinResult.id.desc()).first())
    can = not last or last.spin_date != today
    last_prize = None
    if last and last.spin_date == today:
        last_prize = dict(type=last.prize_type, value=last.prize_value,
                          label=('کیف پول' if last.prize_type == 'wallet' else
                                 f'کوپن {fa(last.prize_value)}٪' if last.prize_type == 'coupon' else
                                 'شانس دوباره'),
                          code=last.coupon_code or '')
    return render_template('engage/spin.html', can=can, last_prize=last_prize,
                           prizes=[w[2] for w in SPIN_WHEEL], fa=fa)


@engage_bp.route('/api/spin', methods=['POST'])
def api_spin():
    """چرخش گردونه — یک بار در روز"""
    if not g.user:
        return jsonify(ok=False, msg='ابتدا وارد شوید'), 401
    today = _today()
    last = (SpinResult.query.filter_by(user_id=g.user.id)
            .order_by(SpinResult.id.desc()).first())
    if last and last.spin_date == today:
        return jsonify(ok=False, msg='امروز قبلاً چرخاندید — فردا دوباره بیایید'), 429
    ptype, val, label = _pick_prize()
    coupon_code = None
    msg = 'شانس خود را فردا دوباره امتحان کنید! 🍀'
    if ptype == 'wallet':
        g.user.wallet_balance = (g.user.wallet_balance or 0) + val
        from models import WalletTransaction
        db.session.add(WalletTransaction(user_id=g.user.id, amount=val, type='bonus',
                                         detail=f'جایزه گردونه شانس ({_today()})'))
        msg = f'🎉 {fa("{:,}".format(val))} تومان به کیف پول شما اضافه شد!'
    elif ptype == 'coupon':
        coupon_code, err = _make_coupon(val)
        if coupon_code:
            msg = f'🎉 کوپن {fa(val)}٪ تخفیف دریافت کردید: {coupon_code}'
        else:
            ptype = 'none'
            msg = 'شانس خود را فردا دوباره امتحان کنید! 🍀'
    db.session.add(SpinResult(user_id=g.user.id, prize_type=ptype, prize_value=val,
                              coupon_code=coupon_code, spin_date=today))
    db.session.commit()
    return jsonify(ok=True, prize_type=ptype, prize_value=val, label=label,
                   coupon_code=coupon_code, msg=msg)


# ============================================================
# نقشه هوشمند — آدرس پستی + برآورد هزینه پیک
# ============================================================
@engage_bp.route('/api/address/provinces')
def api_provinces():
    return jsonify(ok=True, provinces=PROVINCES)


@engage_bp.route('/api/address/cities')
def api_cities():
    prov = request.args.get('province', '')
    return jsonify(ok=True, cities=IRAN_CITIES.get(prov, []))


@engage_bp.route('/api/address/shipping-estimate', methods=['POST'])
def api_shipping_estimate():
    """برآورد هزینه ارسال با پیک اسنپ/تپسی بر اساس استان و فاصله تقریبی"""
    data = request.get_json(force=True, silent=True) or {}
    province = data.get('province', '')
    weight = float(data.get('weight', 0.5) or 0.5)  # کیلوگرم
    # فاصله تقریبی از تهران (کیلومتر) — جدول ساده
    distance_km = {
        'تهران': 30, 'البرز': 40, 'قم': 140, 'قزوین': 160, 'سمنان': 220,
        'اصفهان': 440, 'همدان': 330, 'مرکزی': 280, 'زنجان': 290, 'مازندران': 250,
        'گیلان': 320, 'گلستان': 400, 'خراسان رضوی': 900, 'خراسان شمالی': 700,
        'خراسان جنوبی': 1000, 'کرمان': 1000, 'یزد': 630, 'فارس': 900,
        'خوزستان': 850, 'بوشهر': 1000, 'هرمزگان': 1200, 'اردبیل': 600,
        'آذربایجان شرقی': 620, 'آذربایجان غربی': 700, 'کردستان': 460,
        'کرمانشاه': 510, 'ایلام': 690, 'لرستان': 490, 'چهارمحال': 580,
        'کهگیلویه': 900, 'سیستان': 1500,
    }.get(province, 600)
    # هزینه پایه پیک: اسنپ ۸۵ هزار تومان + ۳۵۰۰/کیلومتر؛ تپسی ۸۰ هزار + ۳۰۰۰/کیلومتر
    snap = 85000 + int(distance_km * 3500)
    tapsi = 80000 + int(distance_km * 3000)
    return jsonify(ok=True, distance_km=distance_km, weight=weight,
                   providers=[dict(name='اسنپ', icon='🛵', price=snap,
                                   estimate=f'{fa(distance_km)} کیلومتر — امروز'),
                              dict(name='تپسی', icon='🚙', price=tapsi,
                                   estimate=f'{fa(distance_km)} کیلومتر — امروز')])


@engage_bp.route('/address')
def address_page():
    """صفحه انتخاب آدرس — با نقشه Map.ir (embed) و برآورد هزینه"""
    if not g.user:
        return redirect(url_for('auth.login', next='/address'))
    map_key = _cfg('mapir_api_key', '')
    return render_template('engage/address.html', provinces=PROVINCES,
                           map_key=map_key, fa=fa)


# ============================================================
# افیلیت — لینک اختصاصی (ارتقای سیستم referral موجود)
# ============================================================
@engage_bp.route('/affiliate')
def affiliate_page():
    """داشبورد افیلیت: لینک اختصاصی + آمار معرفی + پورسانت"""
    if not g.user:
        return redirect(url_for('auth.login', next='/affiliate'))
    if not g.user.referral_code:
        g.user.referral_code = 'AF' + str(uuid.uuid4())[:8].upper()
        db.session.commit()
    link = request.host_url.rstrip('/') + url_for('auth.register', ref=g.user.referral_code)
    from models import Order as _O, WalletTransaction as _W
    referred = User.query.filter_by(referred_by=g.user.id).count()
    paid_refs = _O.query.join(User, User.id == _O.user_id) \
        .filter(User.referred_by == g.user.id, _O.status == 'paid').count()
    earnings = db.session.query(db.func.coalesce(db.func.sum(_W.amount), 0)) \
        .filter(_W.user_id == g.user.id, _W.type == 'bonus',
                _W.detail.like('%معرفی%')).scalar() or 0
    return render_template('engage/affiliate.html', link=link,
                           referred=referred, paid_refs=paid_refs,
                           earnings=earnings, fa=fa)


def init_engage(app):
    app.register_blueprint(engage_bp)
