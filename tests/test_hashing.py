# -*- coding: utf-8 -*-
"""تست خط‌مشی هش‌گذاری MD5 — قابل ویرایش مستقیم در دیتابیس + سازگاری با هش‌های قدیمی."""
import hashlib
from models import (User, db, certificate_code, certificate_code_legacy_md5,
                    certificate_code_legacy_sha1)


def test_new_password_uses_md5_format(app):
    """رمز جدید با قالب ``md5:<hex>`` ذخیره می‌شود تا مستقیم در DB قابل تغییر باشد."""
    with app.app_context():
        u = User(name='هش تست', email='hash@test.ir', phone='09120000111', role='student')
        u.set_password('Secret-123')
        h = u.password_hash
        assert h.startswith('md5:')
        assert h == 'md5:' + hashlib.md5('Secret-123'.encode()).hexdigest()
        assert u.check_password('Secret-123') is True
        assert u.check_password('wrong') is False


def test_raw_md5_in_db_accepted_and_normalized(app):
    """MD5 خامی که مدیر مستقیم در دیتابیس نوشته پذیرفته و به قالب md5: نرمال می‌شود."""
    with app.app_context():
        u = User(name='قدیمی', email='legacy@test.ir', phone='09120000222', role='student')
        raw = hashlib.md5('old-pass-99'.encode()).hexdigest()
        u.password_hash = raw  # شبیه‌سازی UPDATE مستقیم در phpMyAdmin
        db.session.add(u)
        db.session.commit()
        assert u.check_password('old-pass-99') is True
        db.session.refresh(u)
        assert u.password_hash == 'md5:' + raw  # نرمال‌سازی خودکار
        assert User.query.filter_by(email='legacy@test.ir').first() \
            .check_password('wrong') is False


def test_old_werkzeug_hash_still_accepted_and_converted(app):
    """حساب‌های ساخته‌شده قبل از مهاجرت (هش قوی ورک‌زگ) بدون تغییر رمز وارد می‌شوند."""
    from werkzeug.security import generate_password_hash
    with app.app_context():
        u = User(name='قوی قدیمی', email='oldstrong@test.ir', phone='09120000333',
                 role='student')
        u.password_hash = generate_password_hash('Strong-Old-1')
        db.session.add(u)
        db.session.commit()
        assert u.check_password('Strong-Old-1') is True
        db.session.refresh(u)
        # بعد از ورود موفق به قالب استاندارد MD5 تبدیل شده
        assert u.password_hash.startswith('md5:')


def test_admin_can_change_password_directly_in_db(app):
    """سناریوی اصلی کاربر: مدیر MD5 را دستی در DB می‌نویسد و کاربر وارد می‌شود."""
    with app.app_context():
        u = User(name='کاربر', email='direct@test.ir', phone='09120000444', role='student')
        u.set_password('first-pass')
        db.session.add(u)
        db.session.commit()
        # مدیر در دیتابیس: password_hash = MD5('new-pass-77')
        db.session.query(User).filter_by(email='direct@test.ir').update(
            {'password_hash': hashlib.md5('new-pass-77'.encode()).hexdigest()})
        db.session.commit()
        fresh = User.query.filter_by(email='direct@test.ir').first()
        assert fresh.check_password('new-pass-77') is True
        assert fresh.check_password('first-pass') is False


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
