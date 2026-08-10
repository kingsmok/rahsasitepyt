# -*- coding: utf-8 -*-
"""مدل‌های ماژول‌های زیرساختی — BNPL، Cashback، مارکت‌پلیس، گردونه شانس، تاریخچه قیمت
(این فایل در app.py ایمپورت می‌شود تا create_all جدول‌های جدید را بسازد)
"""
from models import db, utcnow


# ============================================================
# کیف پول — Cashback (برگشت وجه پس از خرید موفق)
# ============================================================
class CashbackLog(db.Model):
    __tablename__ = 'cashback_logs'
    __table_args__ = (db.Index('idx_cashback_user', 'user_id'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    amount = db.Column(db.Integer, default=0)            # مبلغ برگشتی (تومان)
    percent = db.Column(db.Integer, default=2)           # درصد بازگشت
    base_amount = db.Column(db.Integer, default=0)       # مبلغ مبنای محاسبه
    note = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship('User')
    order = db.relationship('Order')


# ============================================================
# مارکت‌پلیس‌ها — لاگ همگام‌سازی و سفارش‌های خارجی
# ============================================================
class MarketSyncLog(db.Model):
    __tablename__ = 'market_sync_logs'
    __table_args__ = (db.Index('idx_mkt_channel', 'channel'),)
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(30))        # torob | emalls | digikala | basalam
    action = db.Column(db.String(50))         # feed | sync_inventory | webhook
    status = db.Column(db.String(20), default='ok')   # ok | error
    item_type = db.Column(db.String(20))      # course | product
    item_id = db.Column(db.Integer)
    detail = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=utcnow)


class MarketOrder(db.Model):
    """سفارش دریافتی از پلتفرم‌های خارجی (باسلام و...)"""
    __tablename__ = 'market_orders'
    __table_args__ = (db.Index('idx_mkt_ext', 'channel', 'external_id'),)
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(30), default='basalam')
    external_id = db.Column(db.String(100))
    customer_name = db.Column(db.String(120))
    customer_phone = db.Column(db.String(20))
    address = db.Column(db.String(400))
    items = db.Column(db.Text)                # JSON — اقلام سفارش
    total = db.Column(db.Integer, default=0)
    status = db.Column(db.String(30), default='new')  # new | accepted | shipped | done | canceled
    raw = db.Column(db.Text)                  # payload خام وب‌هوک
    created_at = db.Column(db.DateTime, default=utcnow)


# ============================================================
# تاریخچه قیمت — نمودار قیمت (مشابه دیجی‌کالا)
# ============================================================
class PriceHistory(db.Model):
    __tablename__ = 'price_history'
    __table_args__ = (db.Index('idx_price_item', 'item_type', 'item_id'),)
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(20))      # course | product
    item_id = db.Column(db.Integer)
    price = db.Column(db.Integer, default=0)          # قیمت اصلی
    final_price = db.Column(db.Integer, default=0)    # قیمت نهایی (با تخفیف)
    recorded_at = db.Column(db.DateTime, default=utcnow)


# ============================================================
# گردونه شانس — گیمیفیکیشن
# ============================================================
class SpinResult(db.Model):
    __tablename__ = 'spin_results'
    __table_args__ = (db.Index('idx_spin_user', 'user_id'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    prize_type = db.Column(db.String(20), default='none')  # coupon | wallet | none
    prize_value = db.Column(db.Integer, default=0)         # مبلغ کوپن/کیف پول (تومان) یا درصد
    coupon_code = db.Column(db.String(40))                 # کد تخفیف تولیدشده
    spin_date = db.Column(db.String(20))                   # تاریخ شمسی
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship('User')
