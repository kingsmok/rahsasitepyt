# -*- coding: utf-8 -*-
"""تست خط‌مشی هش‌گذاری رمز — هش قوی ورک‌زگ + ارتقای خودکار قالب‌های قدیمی MD5."""
import hashlib
from werkzeug.security import check_password_hash
from models import (User, db, certificate_code, certificate_code_legacy_md5,
                    certificate_code_legacy_sha1)


def test_new_password_uses_strong_hash(app):
    """رمز جدید با هش قوی (ورک‌زگ) ذخیره می‌شود — نه MD5."""
    with app.app_context():
        u = User(name='هش تست', email='hash@test.ir', phone='09120000111', role='student')
        u.set_password('Secret-123')
        h = u.password_hash
        # هرگز نباید قالب MD5 تولید شود
        assert not h.startswith('md5:')
        assert not hashlib.md5(b'Secret-123').hexdigest() == h
        # و باید با تابع استاندارد ورک‌زگ قابل تایید باشد
        assert check_password_hash(h, 'Secret-123') is True
        assert u.check_password('Secret-123') is True
        assert u.check_password('wrong') is False


def test_raw_md5_in_db_accepted_and_upgraded(app):
    """MD5 خامی که در دیتابیس قدیمی نوشته شده، پذیرفته و به هش قوی ارتقا می‌یابد."""
    with app.app_context():
        u = User(name='قدیمی', email='legacy@test.ir', phone='09120000222', role='student')
        raw = hashlib.md5('old-pass-99'.encode()).hexdigest()
        u.password_hash = raw  # شبیه‌سازی UPDATE مستقیم قدیمی در phpMyAdmin
        db.session.add(u)
        db.session.commit()
        assert u.check_password('old-pass-99') is True
        db.session.refresh(u)
        # نرمال‌سازی خودکار → هش قوی (نه قالب md5:)
        assert not u.password_hash.startswith('md5:')
        assert check_password_hash(u.password_hash, 'old-pass-99') is True
        assert User.query.filter_by(email='legacy@test.ir').first() \
            .check_password('wrong') is False


def test_md5_prefix_hash_still_accepted_and_upgraded(app):
    """قالب قدیمی ``md5:<hex>`` پذیرفته و در همان ورود به هش قوی ارتقا می‌یابد."""
    with app.app_context():
        u = User(name='قدیمی پیشونددار', email='md5prefix@test.ir',
                 phone='09120000223', role='student')
        u.password_hash = 'md5:' + hashlib.md5('legacy-pass-5'.encode()).hexdigest()
        db.session.add(u)
        db.session.commit()
        assert u.check_password('legacy-pass-5') is True
        db.session.refresh(u)
        assert not u.password_hash.startswith('md5:')
        assert check_password_hash(u.password_hash, 'legacy-pass-5') is True


def test_old_werkzeug_hash_still_accepted(app):
    """حساب‌های قدیمی با هش قوی ورک‌زگ بدون تغییر رمز وارد می‌شوند (بدون تبدیل اضافه)."""
    from werkzeug.security import generate_password_hash
    with app.app_context():
        u = User(name='قوی قدیمی', email='oldstrong@test.ir', phone='09120000333',
                 role='student')
        u.password_hash = generate_password_hash('Strong-Old-1')
        db.session.add(u)
        db.session.commit()
        assert u.check_password('Strong-Old-1') is True
        assert u.check_password('wrong') is False


def test_admin_legacy_md5_in_db_still_logs_in_and_upgrades(app):
    """سناریوی مهاجرت: مدیر در دیتابیس قدیمی MD5 نوشته و کاربر وارد می‌شود."""
    with app.app_context():
        u = User(name='کاربر', email='direct@test.ir', phone='09120000444', role='student')
        u.set_password('first-pass')
        db.session.add(u)
        db.session.commit()
        # مدیر در دیتابیس قدیمی: password_hash = MD5('new-pass-77')
        db.session.query(User).filter_by(email='direct@test.ir').update(
            {'password_hash': hashlib.md5('new-pass-77'.encode()).hexdigest()})
        db.session.commit()
        fresh = User.query.filter_by(email='direct@test.ir').first()
        assert fresh.check_password('new-pass-77') is True
        assert fresh.check_password('first-pass') is False
        # و هش به قالب قوی ارتقا یافته است
        assert not fresh.password_hash.startswith('md5:')


def test_certificate_codes_hmac_and_legacy(app):
    """کد جدید HMAC است و هر دو قالب قدیمی برای استعلام باقی می‌مانند."""
    with app.app_context():
        c = certificate_code('python-course', 'u@example.com', 42)
        old_md5 = certificate_code_legacy_md5('python-course', 'u@example.com', 42)
        old_sha1 = certificate_code_legacy_sha1('python-course', 'u@example.com', 42)
        assert c.startswith('CRT-') and len(c) == 16
        assert c not in (old_md5, old_sha1)
        seed = 'python-course|u@example.com|42'
        assert old_md5 == 'CRT-' + hashlib.md5(seed.encode()).hexdigest()[:10].upper()
        assert old_sha1 == 'CRT-' + hashlib.sha1(seed.encode()).hexdigest()[:10].upper()
