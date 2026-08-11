#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تغییر مطمئن رمز عبور کاربر — مستقیم روی همان دیتابیسی که سایت استفاده می‌کند.

چرا این اسکریپت؟
    اگر در phpMyAdmin ستون password_hash را دستی عوض کنید و باز هم رمز قدیمی
    کار کند (یا رمز جدید کار نکند)، معمولاً یکی از این‌هاست:
      ۱) سایت اصلاً به آن دیتابیس وصل نیست (DATABASE_URL خالی → SQLite محلی)
      ۲) رمز را متن ساده نوشته‌اید (بدون هش و بدون پیشوند plain:)
      ۳) ری‌استارت نکرده‌اید / کش مرورگر یا سشن قدیمی هنوز باز است
    این اسکریپت هر سه را دور می‌زند: با همان تنظیمات اپ وصل می‌شود، هش قوی
    می‌سازد و سشن‌های قبلی کاربر را هم باطل می‌کند.

اجرا (در پوشه پروژه روی هاست):
    python3 scripts/set_password.py --email admin@site.ir --password 'رمزجدید'
    python3 scripts/set_password.py --id 5 --password 'MyNewPass123'
    python3 scripts/set_password.py --phone 09120000000 --password 'MyNewPass123'
    python3 scripts/set_password.py --list            # نمایش کاربران و نوع هش
    python3 scripts/set_password.py --email a@b.ir --check 'رمز'   # تست رمز

روی هاست اشتراکی معمولاً باید پایتون venv را صدا بزنید:
    ./venv/bin/python scripts/set_password.py ...
"""
import argparse
import getpass
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, '.env'), override=True)
except Exception:
    pass


def _mask(url):
    """پنهان‌کردن رمز دیتابیس در خروجی"""
    url = str(url or '')
    if '@' not in url:
        return url
    head, tail = url.split('@', 1)
    if ':' in head:
        scheme_user, _pw = head.rsplit(':', 1)
        return scheme_user + ':****@' + tail
    return url


def _hash_kind(h):
    """تشخیص نوع هش ذخیره‌شده — برای عیب‌یابی"""
    import re
    h = (h or '').strip()
    if not h:
        return 'خالی (بدون رمز — کاربر نمی‌تواند با رمز وارد شود)'
    if h.startswith('scrypt:') or h.startswith('pbkdf2:'):
        return 'هش قوی ✅ (' + h.split(':')[0] + ')'
    if re.match(r'^(plain[:$]|\{plain\})', h):
        return 'متن ساده با پیشوند plain: (موقتاً کار می‌کند، در اولین ورود ارتقا می‌یابد)'
    if re.match(r'^[0-9a-f]{32}$', h, re.I):
        return 'MD5 خام (قدیمی — پذیرفته و در اولین ورود ارتقا می‌یابد)'
    if re.match(r'^[0-9a-f]{40}$', h, re.I):
        return 'SHA1 خام (قدیمی — پذیرفته و در اولین ورود ارتقا می‌یابد)'
    if re.match(r'^[0-9a-f]{64}$', h, re.I):
        return 'SHA256 خام (قدیمی — پذیرفته و در اولین ورود ارتقا می‌یابد)'
    if '$' in h:
        return 'قالب ورک‌زگ قدیمی'
    return '⚠️ متن ساده بدون پیشوند — سایت آن را قبول نمی‌کند! این اسکریپت را اجرا کنید'


def main():
    ap = argparse.ArgumentParser(description='تغییر مطمئن رمز عبور کاربر')
    who = ap.add_mutually_exclusive_group()
    who.add_argument('--email', help='ایمیل کاربر')
    who.add_argument('--phone', help='شماره موبایل کاربر')
    who.add_argument('--id', type=int, help='شناسه (id) کاربر')
    ap.add_argument('--password', help='رمز جدید (اگر ندهید، پرسیده می‌شود)')
    ap.add_argument('--check', help='فقط تست کن این رمز درست است یا نه (تغییری نمی‌دهد)')
    ap.add_argument('--list', action='store_true', help='فهرست کاربران و نوع هش رمزشان')
    ap.add_argument('--keep-sessions', action='store_true',
                    help='سشن‌های فعال کاربر باطل نشوند (پیش‌فرض: باطل می‌شوند)')
    args = ap.parse_args()

    from app import create_app
    from models import db, User

    app = create_app()
    print('=' * 62)
    print(' تغییر رمز عبور — آکادمی')
    print('=' * 62)
    print('دیتابیسی که سایت استفاده می‌کند:')
    print('   ' + _mask(app.config.get('SQLALCHEMY_DATABASE_URI')))
    if not os.environ.get('DATABASE_URL'):
        print('   ⚠️ DATABASE_URL در .env خالی است → SQLite محلی.')
        print('      اگر رمز را در phpMyAdmin (MySQL) عوض می‌کنید، سایت اصلاً آن‌جا را نمی‌خواند!')
    print()

    with app.app_context():
        if args.list:
            users = User.query.order_by(User.id).limit(200).all()
            if not users:
                print('هیچ کاربری در این دیتابیس نیست — یعنی به دیتابیس اشتباه وصل‌اید.')
                return 1
            print(f'{"id":>4}  {"ایمیل":<32} {"نقش":<12} وضعیت رمز')
            print('-' * 100)
            for u in users:
                print(f'{u.id:>4}  {(u.email or "-"):<32} {(u.role or ""):<12} {_hash_kind(u.password_hash)}')
            return 0

        q = None
        if args.email:
            q = User.query.filter(db.func.lower(User.email) == args.email.strip().lower())
        elif args.phone:
            q = User.query.filter_by(phone=args.phone.strip())
        elif args.id:
            q = User.query.filter_by(id=args.id)
        else:
            ap.error('یکی از --email یا --phone یا --id را بدهید (یا --list).')

        user = q.first()
        if not user:
            print('❌ کاربری با این مشخصات در این دیتابیس پیدا نشد.')
            print('   با --list ببینید اصلاً چه کاربرانی این‌جا هستند.')
            return 1

        print(f'کاربر: #{user.id} — {user.name} <{user.email}>  نقش: {user.role}')
        print(f'وضعیت فعلی رمز: {_hash_kind(user.password_hash)}')
        print()

        if args.check:
            ok = user.check_password(args.check)
            print(('✅ رمز درست است.' if ok else '❌ رمز اشتباه است.'))
            return 0 if ok else 2

        pw = args.password
        if not pw:
            pw = getpass.getpass('رمز جدید: ')
            if pw != getpass.getpass('تکرار رمز جدید: '):
                print('❌ تکرار رمز مطابقت ندارد.')
                return 1
        if len(pw) < 6:
            print('❌ رمز باید حداقل ۶ کاراکتر باشد.')
            return 1

        user.set_password(pw)
        if not args.keep_sessions:
            user.new_session_token()  # خروج اجباری از همه دستگاه‌ها
        if not user.is_active:
            user.is_active = True
            print('ℹ️ حساب غیرفعال بود — فعال شد.')
        db.session.commit()

        # تایید نهایی: از دیتابیس دوباره بخوان و تست کن
        db.session.expire_all()
        fresh = db.session.get(User, user.id)
        ok = fresh.check_password(pw)
        print('✅ رمز ذخیره شد.' if ok else '❌ ذخیره شد ولی تست ناموفق بود!')
        print(f'   نوع هش جدید: {_hash_kind(fresh.password_hash)}')
        if not args.keep_sessions:
            print('   همهٔ سشن‌های قبلی این کاربر باطل شد.')
        print()
        print('اگر روی هاست هستید، برای اطمینان یک بار ری‌استارت کنید:')
        print('   touch passenger_wsgi.py     (cPanel / Passenger)')
        return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
