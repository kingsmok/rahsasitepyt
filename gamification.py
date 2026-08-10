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


def wallet_charge(user, amount, detail):
    user.wallet_balance = (user.wallet_balance or 0) + amount
    db.session.add(WalletTransaction(user_id=user.id, amount=amount,
                                     type='charge', detail=detail))


def wallet_spend(user, amount, detail):
    user.wallet_balance = max(0, (user.wallet_balance or 0) - amount)
    db.session.add(WalletTransaction(user_id=user.id, amount=-amount,
                                     type='spend', detail=detail))


def wallet_bonus(user, amount, detail):
    user.wallet_balance = (user.wallet_balance or 0) + amount
    db.session.add(WalletTransaction(user_id=user.id, amount=amount,
                                     type='bonus', detail=detail))


def make_referral_code(user):
    import random
    code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=8))
    from models import User
    while User.query.filter_by(referral_code=code).first():
        code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=8))
    user.referral_code = code
    return code
