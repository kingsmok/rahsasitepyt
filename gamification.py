# -*- coding: utf-8 -*-
"""گیمیفیکیشن: امتیاز، استریک، نشان‌ها — توابع کمکی"""
import json
from datetime import date
from models import db, User, PointLog, WalletTransaction

BADGES = [
    # (حداقل امتیاز، نام، آیکون، توضیح)
    (50, 'شروع‌کننده', '🌱', 'اولین قدم‌های یادگیری'),
    (200, 'یادگیرنده فعال', '📘', '۵۰ امتیاز فعالیت'),
    (500, 'دانشجوی جدی', '🎯', '۲۰۰ امتیاز فعالیت'),
    (1000, 'حرفه‌ای', '🏆', '۵۰۰ امتیاز فعالیت'),
    (2000, 'افسانه آکادمی', '👑', '۱۰۰۰+ امتیاز فعالیت'),
]


def award_points(user, points, reason):
    """افزودن امتیاز + ثبت لاگ + بررسی نشان جدید"""
    if not user:
        return None
    user.points = (user.points or 0) + points
    db.session.add(PointLog(user_id=user.id, points=points, reason=reason))
    # نشان‌ها
    earned = []
    badges = []
    try:
        badges = json.loads(user.badges or '[]')
    except Exception:
        badges = []
    for threshold, name, icon, desc in BADGES:
        if user.points >= threshold and name not in badges:
            badges.append(name)
            earned.append((name, icon))
    if earned:
        user.badges = json.dumps(badges)
    return earned


def record_streak(user):
    """ثبت فعالیت روزانه و محاسبه استریک مطالعه"""
    if not user:
        return 0
    today = date.today().isoformat()
    if user.last_active == today:
        return user.streak or 0
    yesterday = date.fromordinal(date.today().toordinal() - 1).isoformat()
    if user.last_active == yesterday:
        user.streak = (user.streak or 0) + 1
    else:
        user.streak = 1
    user.last_active = today
    return user.streak


def user_badges(user):
    try:
        return json.loads(user.badges or '[]')
    except Exception:
        return []


# ---------------------------------------------------------------------------
# کیف پول — تنها منبع مجاز تغییر موجودی در کل پروژه
# ---------------------------------------------------------------------------
# چرا این توابع بازنویسی شدند؟
#
# پیاده‌سازی قبلی الگوی «خواندن در پایتون → محاسبه → نوشتن» بود:
#
#     user.wallet_balance = (user.wallet_balance or 0) + amount
#
# این یک read-modify-write روی مرز شبکه است و در برابر همزمانی امن نیست:
# دو درخواست هم‌زمان هر دو مقدار قدیمی را می‌خوانند، هر دو همان نتیجه را
# می‌نویسند و یکی از تراکنش‌ها بی‌صدا گم می‌شود (Lost Update).
#
# برای «خرج» وضعیت بدتر بود: گارد موجودی در سطح پایتون انجام می‌شد
# (shop.py مقدار balance را می‌خواند و مقایسه می‌کرد) و تابع با max(0, ...)
# نتیجهٔ منفی را به صفر گرد می‌کرد. یعنی دو خرید هم‌زمان هر دو از گارد رد
# می‌شدند و کاربر بیش از موجودی خود خرید می‌کرد، بدون اینکه موجودی منفی
# شود تا کسی متوجه شود. (این سناریو عملاً بازتولید و اثبات شد.)
#
# راه‌حل: همان الگویی که shop.py::_mark_paid برای شارژ کیف پول به‌کار می‌برد —
# یک دستور UPDATE اتمیک در خود دیتابیس. برای خرج، شرط موجودی داخل همان
# WHERE قرار می‌گیرد تا *دیتابیس* داور باشد، نه پایتون. اگر رقابت رخ دهد
# rowcount صفر برمی‌گردد و تراکنش رد می‌شود.
#
# نکتهٔ سازگاری: پس از UPDATE، مقدار شیء ORM در حافظه کهنه است. چون
# فراخوان‌ها (مثل tests/test_utils.py و پیام‌های flash) بلافاصله
# user.wallet_balance را می‌خوانند، مقدار را از دیتابیس هم‌گام می‌کنیم.

def _wallet_delta(user, amount, tx_type, detail, require_balance=False):
    """هستهٔ مشترک تغییر موجودی کیف پول — اتمیک و امن در برابر همزمانی.

    این تنها نقطه‌ای است که مجاز است ``User.wallet_balance`` را تغییر دهد.
    (اصل DRY / Single Source of Truth؛ قبلاً سه پیاده‌سازی موازی از این
    منطق در gamification.py، bnpl.py و engagement.py وجود داشت.)

    پارامترها:
        user: شیء کاربر (اگر None باشد امن رد می‌شود).
        amount: مبلغ مثبت به تومان. مقدار صفر یا منفی پذیرفته نمی‌شود.
        tx_type: 'charge' | 'spend' | 'bonus' | 'refund'
        require_balance: اگر True باشد، تنها در صورت کفایت موجودی اعمال می‌شود.

    خروجی: True در صورت اعمال موفق، False در غیر این صورت.
    """
    # ── گارد ورودی: دفاع در عمق ──────────────────────────────────────────
    # مسیر ادمین (admin_bp.user_wallet) خودش amount <= 0 را رد می‌کند، اما
    # تابع نباید به گارد فراخوان تکیه کند: یک مبلغ منفی در wallet_spend
    # عملاً به «شارژ رایگان» تبدیل می‌شد (منهای منفی = مثبت).
    if user is None or getattr(user, 'id', None) is None:
        return False
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return False
    if amount <= 0:
        return False

    if require_balance:
        # کسر اتمیک و مشروط: شرط کفایت موجودی داخل WHERE است، بنابراین
        # حتی اگر دو درخواست هم‌زمان به این‌جا برسند تنها یکی از آن‌ها
        # سطر را تغییر می‌دهد و دیگری rowcount=0 می‌گیرد.
        updated = User.query.filter(
            User.id == user.id,
            db.func.coalesce(User.wallet_balance, 0) >= amount,
        ).update(
            {User.wallet_balance: db.func.coalesce(User.wallet_balance, 0) - amount},
            synchronize_session=False,
        )
        if not updated:
            return False           # موجودی ناکافی یا رقابت هم‌زمان → رد
        signed = -amount
    else:
        # افزایش موجودی: بدون شرط، اما همچنان اتمیک تا شارژهای هم‌زمان
        # (مثلاً cashback و پاداش معرفی در یک لحظه) روی هم گم نشوند.
        User.query.filter(User.id == user.id).update(
            {User.wallet_balance: db.func.coalesce(User.wallet_balance, 0) + amount},
            synchronize_session=False,
        )
        signed = amount

    db.session.add(WalletTransaction(user_id=user.id, amount=signed,
                                     type=tx_type, detail=detail))

    # هم‌گام‌سازی شیء در حافظه: UPDATE مستقیم روی دیتابیس، نسخهٔ ORM را
    # به‌روز نمی‌کند. بدون این کار، کدی که بلافاصله بعد از فراخوانی
    # user.wallet_balance را می‌خواند (تست‌ها، پیام‌های flash، قالب‌ها)
    # مقدار کهنه می‌دید.
    try:
        db.session.refresh(user, ['wallet_balance'])
    except Exception:
        # اگر شیء به سشن متصل نباشد یا هنوز flush نشده باشد، تخمین محلی
        # می‌زنیم؛ منبع حقیقت همچنان دیتابیس است.
        user.wallet_balance = max(0, (user.wallet_balance or 0) + signed)
    return True


def wallet_charge(user, amount, detail):
    """افزایش موجودی (شارژ). خروجی True/False برای بررسی توسط فراخوان."""
    return _wallet_delta(user, amount, 'charge', detail)


def wallet_spend(user, amount, detail):
    """کسر موجودی — تنها در صورت کفایت موجودی.

    خروجی False یعنی «کسر انجام نشد» (موجودی ناکافی، مبلغ نامعتبر یا
    رقابت هم‌زمان). فراخوان **باید** خروجی را بررسی کند و نباید فرض کند
    که کسر همیشه موفق است.
    """
    return _wallet_delta(user, amount, 'spend', detail, require_balance=True)


def wallet_bonus(user, amount, detail):
    """افزایش موجودی بابت جایزه/پاداش (cashback، معرفی دوستان، گردونه)."""
    return _wallet_delta(user, amount, 'bonus', detail)


def make_referral_code(user):
    import random
    code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=8))
    from models import User
    while User.query.filter_by(referral_code=code).first():
        code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=8))
    user.referral_code = code
    return code
