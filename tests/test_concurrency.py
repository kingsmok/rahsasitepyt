# -*- coding: utf-8 -*-
"""تست‌های همزمانی مسیر پول — کیف پول و کوپن.

این فایل کلاسی از باگ را پوشش می‌دهد که تست‌های واحد معمولی نمی‌بینند:
الگوی «خواندن در پایتون → محاسبه → نوشتن» (read-modify-write) روی فیلدهای
مالی. چنین کدی در تست تک‌نخی همیشه درست کار می‌کند و فقط زیر بار هم‌زمان
شکست می‌خورد.

نکتهٔ صداقت مهندسی: SQLite نوشتن‌ها را سریال می‌کند، بنابراین این تست‌ها
«اثبات ریاضی» نیستند. برای همین در کنار تست‌های رقابتی، تست‌های قطعی هم
داریم که مستقیماً *قرارداد* توابع را بررسی می‌کنند (کسر بیش از موجودی رد
شود، مبلغ نامعتبر رد شود). قرارداد روی MySQL — که مقصد واقعی استقرار این
اپ است — همان است، در حالی که پنجرهٔ رقابت آن‌جا بازتر است.
"""
import threading

from models import Coupon, User, WalletTransaction, db


# ---------------------------------------------------------------------------
# قرارداد قطعی توابع کیف پول (مستقل از زمان‌بندی نخ‌ها)
# ---------------------------------------------------------------------------
def test_wallet_spend_rejects_overdraft(app):
    """کسر بیش از موجودی باید رد شود و موجودی دست‌نخورده بماند."""
    from gamification import wallet_spend
    with app.app_context():
        u = User(name='کاربر موجودی کم', email='ovd@test.ir', phone='09120001101',
                 role='student', is_active=True)
        u.set_password('secret123')
        u.wallet_balance = 10000
        db.session.add(u)
        db.session.commit()

        assert wallet_spend(u, 50000, 'خرید گران') is False
        db.session.commit()
        db.session.refresh(u)
        assert u.wallet_balance == 10000, 'موجودی نباید تغییر کند'
        # هیچ تراکنش خرجی نباید ثبت شده باشد
        assert WalletTransaction.query.filter_by(user_id=u.id, type='spend').count() == 0


def test_wallet_spend_exact_balance_succeeds(app):
    """کسر دقیقاً به اندازهٔ موجودی باید موفق باشد (شرط >= نه >)."""
    from gamification import wallet_spend
    with app.app_context():
        u = User(name='کاربر دقیق', email='exact@test.ir', phone='09120001102',
                 role='student', is_active=True)
        u.set_password('secret123')
        u.wallet_balance = 25000
        db.session.add(u)
        db.session.commit()

        assert wallet_spend(u, 25000, 'خرید کامل') is True
        db.session.commit()
        db.session.refresh(u)
        assert u.wallet_balance == 0


def test_wallet_rejects_invalid_amounts(app):
    """مبلغ صفر/منفی/نامعتبر باید رد شود.

    باگ واقعی: wallet_spend(user, -1000) با منطق قبلی موجودی را *افزایش*
    می‌داد (منهای منفی)، یعنی یک مسیر شارژ رایگان.
    """
    from gamification import wallet_charge, wallet_spend
    with app.app_context():
        u = User(name='کاربر ورودی بد', email='badamt@test.ir', phone='09120001103',
                 role='student', is_active=True)
        u.set_password('secret123')
        u.wallet_balance = 5000
        db.session.add(u)
        db.session.commit()

        for bad in (0, -1000, None, 'abc'):
            assert wallet_spend(u, bad, 'نامعتبر') is False
            assert wallet_charge(u, bad, 'نامعتبر') is False
        db.session.commit()
        db.session.refresh(u)
        assert u.wallet_balance == 5000, 'ورودی نامعتبر نباید موجودی را تغییر دهد'


def test_wallet_spend_handles_null_user(app):
    """کاربر None نباید استثنا بدهد."""
    from gamification import wallet_bonus, wallet_charge, wallet_spend
    with app.app_context():
        assert wallet_spend(None, 1000, 'x') is False
        assert wallet_charge(None, 1000, 'x') is False
        assert wallet_bonus(None, 1000, 'x') is False


def test_wallet_transaction_log_matches_balance(app):
    """جمع تراکنش‌ها باید همیشه با موجودی برابر باشد (Invariant حسابداری)."""
    from gamification import wallet_bonus, wallet_charge, wallet_spend
    with app.app_context():
        u = User(name='کاربر دفتر', email='ledger@test.ir', phone='09120001104',
                 role='student', is_active=True)
        u.set_password('secret123')
        u.wallet_balance = 0
        db.session.add(u)
        db.session.commit()

        wallet_charge(u, 100000, 'شارژ')
        wallet_bonus(u, 20000, 'جایزه')
        wallet_spend(u, 30000, 'خرید')
        wallet_spend(u, 999999, 'رد شود')   # نباید ثبت شود
        db.session.commit()
        db.session.refresh(u)

        total = sum(t.amount for t in
                    WalletTransaction.query.filter_by(user_id=u.id).all())
        assert total == u.wallet_balance == 90000


# ---------------------------------------------------------------------------
# تست‌های رقابتی واقعی (چند نخ هم‌زمان)
# ---------------------------------------------------------------------------
def test_concurrent_wallet_spend_no_double_spend(app):
    """دو خرید هم‌زمان با موجودی کافی برای یکی → فقط یکی باید موفق شود.

    این دقیقاً سناریویی است که با کد قبلی بازتولید شد: کاربر با موجودی
    ۱۰۰٬۰۰۰ تومان، دو سفارش ۱۰۰٬۰۰۰ تومانی را هم‌زمان پرداخت می‌کرد و
    max(0, ...) موجودی را صفر نگه می‌داشت تا ضرر پنهان بماند.
    """
    with app.app_context():
        u = User(name='خریدار هم‌زمان', email='conc@test.ir', phone='09120001105',
                 role='student', is_active=True)
        u.set_password('secret123')
        u.wallet_balance = 100000
        db.session.add(u)
        db.session.commit()
        uid = u.id

    n = 2
    barrier = threading.Barrier(n)
    results = []

    def buy():
        with app.app_context():
            from gamification import wallet_spend
            user = db.session.get(User, uid)
            barrier.wait()          # همگام‌سازی برای بیشینه‌کردن احتمال رقابت
            ok = wallet_spend(user, 100000, 'خرید هم‌زمان')
            if ok:
                db.session.commit()
            else:
                db.session.rollback()
            results.append(ok)

    threads = [threading.Thread(target=buy) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with app.app_context():
        user = db.session.get(User, uid)
        spends = WalletTransaction.query.filter_by(user_id=uid, type='spend').count()
        assert sum(1 for r in results if r) == 1, 'فقط یک خرید باید موفق شود'
        assert spends == 1, 'فقط یک تراکنش خرج باید ثبت شود'
        assert user.wallet_balance == 0
        assert user.wallet_balance >= 0, 'موجودی هرگز نباید منفی شود'


def test_concurrent_wallet_charge_no_lost_update(app):
    """۱۰ شارژ هم‌زمان → هیچ‌کدام نباید گم شود."""
    with app.app_context():
        u = User(name='کاربر شارژ', email='chg@test.ir', phone='09120001106',
                 role='student', is_active=True)
        u.set_password('secret123')
        u.wallet_balance = 0
        db.session.add(u)
        db.session.commit()
        uid = u.id

    n = 10
    barrier = threading.Barrier(n)

    def charge():
        with app.app_context():
            from gamification import wallet_charge
            user = db.session.get(User, uid)
            barrier.wait()
            wallet_charge(user, 1000, 'شارژ هم‌زمان')
            db.session.commit()

    threads = [threading.Thread(target=charge) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with app.app_context():
        user = db.session.get(User, uid)
        assert user.wallet_balance == n * 1000, \
            f'انتظار {n * 1000} بود، {user.wallet_balance} شد — شارژ گم شده است'


def test_concurrent_coupon_increment_no_lost_update(app):
    """افزایش هم‌زمان شمارندهٔ کوپن نباید گم شود.

    گم‌شدن افزایش یعنی عبور از سقف max_uses و ضرر مالی روی کوپن محدود.
    """
    with app.app_context():
        c = Coupon(code='CONCUR', type='fixed', value=50000,
                   max_uses=100, used_count=0, is_active=True)
        db.session.add(c)
        db.session.commit()
        cid = c.id

    n = 10
    barrier = threading.Barrier(n)

    def redeem():
        with app.app_context():
            barrier.wait()
            Coupon.query.filter(Coupon.id == cid).update(
                {Coupon.used_count: db.func.coalesce(Coupon.used_count, 0) + 1},
                synchronize_session=False)
            db.session.commit()

    threads = [threading.Thread(target=redeem) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with app.app_context():
        c = db.session.get(Coupon, cid)
        assert c.used_count == n, \
            f'انتظار {n} بود، {c.used_count} شد — افزایش کوپن گم شده است'
