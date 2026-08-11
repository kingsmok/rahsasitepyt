# -*- coding: utf-8 -*-
"""تست خط‌مشی هش‌گذاری — هش قوی جدید + پذیرش و ارتقای خودکار MD5 قدیمی"""
import hashlib
from models import User, db, certificate_code, certificate_code_legacy_sha1


def test_new_password_uses_strong_hash(app):
    """رمز جدید باید با الگوریتم قوی ذخیره شود، نه MD5 خام"""
    with app.app_context():
        u = User(name='هش تست', email='hash@test.ir', phone='09120000111', role='student')
        u.set_password('Secret-123')
        h = u.password_hash
        assert '$' in h  # قالب ورک‌زگ: method$salt$hash
        assert len(h) > 40
        # قطعاً MD5 خام نیست
        assert hashlib.md5(b'Secret-123').hexdigest() != h.lower().strip()
        assert u.check_password('Secret-123') is True
        assert u.check_password('wrong') is False


def test_legacy_md5_hash_accepted_and_upgraded(app):
    """هش MD5 خام (مثل UPDATE با MD5() در phpMyAdmin) باید پذیرفته و ارتقا یابد"""
    with app.app_context():
        u = User(name='قدیمی', email='legacy@test.ir', phone='09120000222', role='student')
        u.password_hash = hashlib.md5('old-pass-99'.encode()).hexdigest()  # شبیه‌سازی دیتابیس قدیمی
        db.session.add(u)
        db.session.commit()
        # رمز درست → ورود موفق + ارتقای خودکار
        assert u.check_password('old-pass-99') is True
        db.session.refresh(u)
        upgraded = u.password_hash
        assert '$' in upgraded  # حالا هش قوی شده
        assert upgraded != hashlib.md5('old-pass-99'.encode()).hexdigest()
        # رمز غلط → رد
        assert User.query.filter_by(email='legacy@test.ir').first().check_password('wrong') is False


def test_certificate_codes_md5_and_legacy(app):
    """کد گواهینامه با MD5 ساخته می‌شود و کد قدیمی SHA-1 همچنان قابل استعلام است"""
    with app.app_context():
        c = certificate_code('python-course', 'u@example.com', 42)
        old = certificate_code_legacy_sha1('python-course', 'u@example.com', 42)
        assert c.startswith('CRT-') and len(c) == 14
        # MD5 در پایهٔ کد جدید
        seed = 'python-course|u@example.com|42'
        assert c == 'CRT-' + hashlib.md5(seed.encode()).hexdigest()[:10].upper()
        # کد قدیمی متفاوت است (SHA-1) ولی تابعش سر جایش است
        assert old != c
        assert old == 'CRT-' + hashlib.sha1(seed.encode()).hexdigest()[:10].upper()
