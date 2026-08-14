# -*- coding: utf-8 -*-
"""مدل‌های دیتابیس آکادمی آنلاین"""
from datetime import datetime
try:
    from datetime import UTC
except ImportError:  # پایتون < 3.11 (هاست‌های اشتراکی)
    from datetime import timezone as _tz_utc
    UTC = _tz_utc.utc


def utcnow():
    """زمان UTC بدون timezone (سازگار با SQLite و مقایسه‌ها)"""
    return datetime.now(UTC).replace(tzinfo=None)
import json
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# ═══════════════════════════════════════════════════════════════════════════
# خط‌مشی هش‌گذاری رمز عبور (بخش هش‌گذاری)
# ───────────────────────────────────────────────────────────────────────────
# ۱) رمزهای جدید و تغییر رمزها → همیشه با الگوریتم قوی ورک‌زگ ذخیره می‌شوند
#    (scrypt؛ در پایتون‌های قدیمی‌تر pbkdf2:sha256) — غیرقابل شکستن با روش‌های معمول
# ۲) هش‌های قدیمی MD5 خام (۳۲ کاراکتر hex) فقط برای «ورود» پذیرفته می‌شوند و در
#    همان ورود موفق، خودکار به هش قوی «ارتقا» می‌یابند. یعنی اگر در phpMyAdmin
#    رمزی را دستی با MD5() ساختید، کاربر با همان رمز وارد می‌شود و سیستم خودش
#    امنش می‌کند — بدون نیاز به دانستن رمز جدید.
#    مثال phpMyAdmin:
#      UPDATE users SET password_hash = MD5('رمزجدید') WHERE id = 5;
# ۳) برای غیرفعال‌کردن پذیرش MD5 قدیمی، LEGACY_MD5 را False کنید.
# ⚠️ چرا رمزهای جدید را مستقیم MD5 نمی‌کنیم؟ MD5 برای رمز عبور در چند ثانیه
#    با جدول‌های رنگین‌کمانی شکسته می‌شود؛ حتی هش‌های قویِ ورک‌زگ هم روی
#    هاست‌های معمولی فقط چند ده میلی‌ثانیه زمان می‌برند (تأثیری در سرعت ورود ندارد).
# ═══════════════════════════════════════════════════════════════════════════
LEGACY_MD5 = True

import hashlib as _hashlib
import re as _re

_MD5_RE = _re.compile(r'^[0-9a-f]{32}$')


def _md5_hex(text):
    return _hashlib.md5((text or '').encode('utf-8')).hexdigest()


def certificate_code(slug, email, enrollment_id):
    """کد رهگیری گواهینامه — شناسهٔ عمومی و غیرحساس (MD5 طبق درخواست).
    برای اینکه کدهای قبلاً چاپ‌شده (ساخته‌شده با SHA-1) هم معتبر بمانند،
    استعلام‌کننده هر دو حالت را می‌پذیرد — این تابع فقط نسخهٔ جدید (MD5) را می‌سازد."""
    seed = f"{slug}|{email}|{enrollment_id}"
    return 'CRT-' + _md5_hex(seed)[:10].upper()


def certificate_code_legacy_sha1(slug, email, enrollment_id):
    """نسخهٔ قدیمی کد گواهینامه (SHA-1) — فقط برای استعلام کدهای چاپ‌شدهٔ قبل."""
    seed = f"{slug}|{email}|{enrollment_id}"
    return 'CRT-' + _hashlib.sha1(seed.encode('utf-8')).hexdigest()[:10].upper()

db = SQLAlchemy()


def ensure_indexes():
    """ایجاد ایندکس‌های جاافتاده روی دیتابیس موجود (بدون نیاز به مهاجرت).
    روی SQLite و MySQL امن است: فقط ایندکس‌هایی که وجود ندارند ساخته می‌شوند."""
    from sqlalchemy import text as _text
    _tables = {
        'courses': [
            ('idx_courses_status', 'status'),
            ('idx_courses_cat', 'category_id'),
            ('idx_courses_teacher', 'teacher_id'),
            ('idx_courses_views', 'views'),
        ],
        'enrollments': [
            ('idx_enroll_course', 'course_id'),
        ],
        'favorites': [
            ('idx_fav_user', 'user_id'),
        ],
        'live_sessions': [
            ('idx_live_starts', 'starts_at'),
        ],
        'blog_comments': [
            ('idx_bc_post', 'post_id'),
        ],
        'notfound_logs': [
            ('idx_nf_path', 'path'),
        ],
        'price_history': [
            ('idx_price_item', 'item_type, item_id'),
        ],
        'users': [
            ('idx_users_role', 'role'),
        ],
        'orders': [
            ('idx_orders_user_created', 'user_id, created_at'),
        ],
        'reviews': [
            ('idx_reviews_user', 'user_id'),
            ('idx_reviews_created', 'is_approved, created_at'),
        ],
        'tickets': [
            ('idx_tickets_user_status', 'user_id, status'),
        ],
        'notifications': [
            # روی SQLite و MySQL 5.7+/8 کار می‌کند؛
            # MySQL قدیمی‌تر را اسکریپت deploy/mysql-optimize.sql (نسخه پیشوندی) پوشش می‌دهد
            ('idx_notif_title_link', 'title, link'),
        ],
    }
    try:
        from sqlalchemy import inspect as _inspect
        insp = _inspect(db.engine)
        existing = {ix['name'] for ix in insp.get_indexes('courses')}
        for tname, indexes in _tables.items():
            try:
                have = {ix['name'] for ix in insp.get_indexes(tname)}
            except Exception:
                continue
            for name, col in indexes:
                if name in have:
                    continue
                try:
                    with db.engine.begin() as conn:
                        conn.execute(_text(f'CREATE INDEX {name} ON {tname} ({col})'))
                except Exception:
                    pass
    except Exception:
        pass


class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = (db.Index('idx_users_role', 'role'),)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default='')
    email = db.Column(db.String(160), unique=True, nullable=True, index=True)
    phone = db.Column(db.String(20), unique=True, nullable=True, index=True)
    national_code = db.Column(db.String(10), unique=True, nullable=True, index=True)
    avatar = db.Column(db.String(300))  # فایل آواتار آپلودشده
    password_hash = db.Column(db.String(220), nullable=True)
    role = db.Column(db.String(20), default='student')  # student | teacher | admin
    bio = db.Column(db.Text)
    avatar_color = db.Column(db.String(20), default='#2563eb')
    theme = db.Column(db.String(30), default='theme-01')
    is_active = db.Column(db.Boolean, default=True)
    session_token = db.Column(db.String(64), nullable=True)  # مدیریت سشن — خروج از همه دستگاه‌ها
    # گیمیفیکیشن و کیف پول
    points = db.Column(db.Integer, default=0)
    streak = db.Column(db.Integer, default=0)
    last_active = db.Column(db.String(10))
    badges = db.Column(db.Text, default='[]')
    # ارجاع دوستان
    referral_code = db.Column(db.String(16), unique=True, nullable=True)
    referred_by = db.Column(db.Integer, nullable=True)
    # کیف پول و سطح
    wallet_balance = db.Column(db.Integer, default=0)
    level_pref = db.Column(db.String(20))
    study_daily_minutes = db.Column(db.Integer, default=60)
    last_login_ip = db.Column(db.String(64))
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    # تنظیمات اعلان شخصی کاربر
    notify_email = db.Column(db.Boolean, default=True)   # دریافت ایمیل اطلاع‌رسانی
    notify_sms = db.Column(db.Boolean, default=True)     # دریافت پیامک اطلاع‌رسانی
    # اطلاعات تکمیلی پروفایل (فرم کامل)
    national_id = db.Column(db.String(20), default='')   # شماره شناسنامه
    birth_date = db.Column(db.String(10), default='')    # تاریخ تولد شمسی (۱۴۰۵/۰۵/۱۵)
    education_level = db.Column(db.String(50), default='')  # دیپلم/کارشناسی/کارشناسی ارشد/دکتری/...
    education_major = db.Column(db.String(100), default='') # رشته/مقطع تحصیلی
    marital_status = db.Column(db.String(20), default='')   # مجرد/متاهل
    created_at = db.Column(db.DateTime, default=utcnow)

    def new_session_token(self):
        import uuid
        self.session_token = uuid.uuid4().hex
        return self.session_token

    def set_password(self, p):
        # همیشه هش قوی — هرگز MD5 خام برای رمزهای جدید
        self.password_hash = generate_password_hash(p)

    def check_password(self, p):
        """بررسی رمز عبور:
        ۱) هش قوی استاندارد (scrypt/pbkdf2)
        ۲) هش قدیمی MD5 خام — فقط با اجازهٔ LEGACY_MD5؛ در صورت درستی،
           بلافاصله به هش قوی ارتقا می‌یابد (خودکار و بی‌سروصدا)"""
        if not self.password_hash:
            return False
        # ۱) حالت استاندارد ورک‌زگ (شامل md5$salt$hash و sha1$salt$hash قدیمی فلاسک)
        try:
            if check_password_hash(self.password_hash, p):
                return True
        except ValueError:
            pass  # قالب ناشناخته → بررسی حالت خام MD5 در ادامه
        # ۲) هش خام MD5 (مثل UPDATE ... SET password_hash = MD5('...') در phpMyAdmin)
        if LEGACY_MD5:
            _h = (self.password_hash or '').strip().lower()
            if _MD5_RE.match(_h):
                if _h == _md5_hex(p):
                    self._upgrade_hash(p)
                    return True
        return False

    def _upgrade_hash(self, p):
        """ارتقای خودکار هش قدیمی MD5 به هش قوی — در همان ورود موفق"""
        try:
            self.set_password(p)
            db.session.add(self)
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

    def initials(self):
        parts = (self.name or '؟').split()
        return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else ''))

    @property
    def is_admin(self):
        """دسترسی پنل برای مدیر عادی و سوپر ادمین."""
        return self.role in ('admin', 'super_admin')

    @property
    def is_teacher(self):
        return self.role in ('admin', 'teacher')

    @property
    def avatar_url(self):
        if self.avatar:
            return '/static/img/uploads/avatars/' + self.avatar
        return None

    @property
    def masked_national_code(self):
        nc = (self.national_code or '').strip()
        if len(nc) == 10:
            return nc[:3] + '***' + nc[-4:]
        return '—'

    @property
    def birth_jalali(self):
        """تاریخ تولد شمسی استخراج‌شده از کد ملی — '۱۵ مرداد ۱۳۸۰'"""
        try:
            from validators import birth_jalali_str
            return birth_jalali_str(self.national_code)
        except Exception:
            return None

    def profile_complete(self):
        return bool(self.name and self.email)

    def enrolled_courses(self):
        return [e.course for e in self.enrollments if e.course]


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    icon = db.Column(db.String(10), default='🎓')
    color = db.Column(db.String(20), default='#2563eb')
    description = db.Column(db.Text)
    sort = db.Column(db.Integer, default=0)
    courses = db.relationship('Course', backref='category', lazy=True)


class Course(db.Model):
    __tablename__ = 'courses'
    __table_args__ = (db.Index('idx_courses_status', 'status'),
                       db.Index('idx_courses_cat', 'category_id'),
                       db.Index('idx_courses_teacher', 'teacher_id'),
                       db.Index('idx_courses_views', 'views'),)
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    subtitle = db.Column(db.String(300))
    description = db.Column(db.Text)
    image = db.Column(db.String(300), default='cover-python.png')
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    price = db.Column(db.Integer, default=0)          # تومان
    discount_price = db.Column(db.Integer, default=0) # تومان (0 = بدون تخفیف)
    level = db.Column(db.String(20), default='مقدماتی')  # مقدماتی | متوسط | پیشرفته
    language = db.Column(db.String(20), default='فارسی')
    duration_hours = db.Column(db.Integer, default=10)
    status = db.Column(db.String(20), default='published')  # draft | published
    featured = db.Column(db.Boolean, default=False)
    what_you_learn = db.Column(db.Text)
    requirements = db.Column(db.Text)
    tags = db.Column(db.String(300))
    views = db.Column(db.Integer, default=0)
    seeded_students = db.Column(db.Integer, default=0)  # شمار دانشجویان پایه (برای نمایش دمو)
    intro_video = db.Column(db.String(500), default='')   # ویدئوی معرفی (یوتیوب/آپارات/مستقیم)
    access_days = db.Column(db.Integer, default=0)        # مدت دسترسی به دوره (روز) — 0 = نامحدود
    audience = db.Column(db.String(300), default='')      # مناسب برای چه افرادی
    created_at = db.Column(db.DateTime, default=utcnow)

    teacher = db.relationship('User', backref='courses_taught')
    co_teacher_links = db.relationship('CourseTeacher', backref='course', cascade='all, delete-orphan')
    @property
    def co_teachers(self):
        return [l.teacher for l in self.co_teacher_links if l.teacher]

    @property
    def co_teacher_ids(self):
        return [l.teacher_id for l in self.co_teacher_links]
    sections = db.relationship('Section', backref='course', order_by='Section.sort',
                               cascade='all, delete-orphan', lazy=True)
    reviews = db.relationship('Review', backref='course', cascade='all, delete-orphan', lazy=True)

    @property
    def final_price(self):
        return self.discount_price if self.discount_price and self.discount_price < self.price else self.price

    @property
    def has_discount(self):
        return bool(self.discount_price and self.discount_price < self.price)

    @property
    def discount_percent(self):
        if self.has_discount and self.price:
            return round((self.price - self.discount_price) * 100 / self.price)
        return 0

    @property
    def lessons(self):
        out = []
        for s in self.sections:
            out.extend(s.lessons)
        return out

    @property
    def lesson_count(self):
        return sum(len(s.lessons) for s in self.sections)

    @property
    def rating(self):
        """میانگین امتیاز — با کوئری تجمیعی (نه بارگذاری همه نظرات).
        اگر در لیست‌ها مقدار `_agg_rating` از قبل ست شده باشد، همان استفاده می‌شود."""
        if hasattr(self, '_agg_rating'):
            return self._agg_rating
        try:
            from models import Review as _R
            v = db.session.query(db.func.avg(_R.rating)) \
                .filter(_R.course_id == self.id).scalar()
            return round(float(v or 0), 1)
        except Exception:
            return 0

    @property
    def review_count(self):
        """تعداد نظرات — کوئری تجمیعی سبک به‌جای بارگذاری همه رکوردها."""
        if hasattr(self, '_agg_review_count'):
            return self._agg_review_count
        try:
            from models import Review as _R
            return _R.query.filter_by(course_id=self.id).count()
        except Exception:
            return 0

    @property
    def students_count(self):
        """تعداد دانشجویان — کوئری تجمیعی به‌جای بارگذاری همه ثبت‌نام‌ها."""
        if hasattr(self, '_agg_students'):
            return self._agg_students
        try:
            from models import Enrollment as _E
            return (self.seeded_students or 0) + _E.query.filter_by(course_id=self.id).count()
        except Exception:
            return self.seeded_students or 0

    def is_free(self):
        return self.final_price == 0


class Section(db.Model):
    __tablename__ = 'sections'
    __table_args__ = (db.Index('idx_sections_course', 'course_id'),)
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    title = db.Column(db.String(200), nullable=False)
    sort = db.Column(db.Integer, default=0)
    lessons = db.relationship('Lesson', backref='section', order_by='Lesson.sort',
                              cascade='all, delete-orphan', lazy=True)


class Lesson(db.Model):
    __tablename__ = 'lessons'
    __table_args__ = (db.Index('idx_lessons_section', 'section_id'),)
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'))
    title = db.Column(db.String(220), nullable=False)
    video_type = db.Column(db.String(20), default='direct')  # direct | youtube | aparat | none
    video_url = db.Column(db.String(400))
    file_url = db.Column(db.String(400))    # فایل پروژه / دیتا
    file_name = db.Column(db.String(200))
    file_size = db.Column(db.String(30))
    duration = db.Column(db.String(20), default='00:10:00')
    is_free = db.Column(db.Boolean, default=False)
    release_days = db.Column(db.Integer, default=0)  # دسترسی تدریجی: چند روز بعد از ثبت‌نام باز شود
    captions = db.Column(db.String(400))  # فایل زیرنویس (srt/vtt)
    video_url_hd = db.Column(db.String(400))  # نسخه باکیفیت برای انتخاب کیفیت
    content = db.Column(db.Text)  # توضیحات جلسه
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    sort = db.Column(db.Integer, default=0)

    @property
    def video_src(self):
        u = self.video_url or ''
        if self.video_type == 'direct' and u and not u.startswith(('http', '/')):
            return '/static/video/' + u
        return u


class Review(db.Model):
    __tablename__ = 'reviews'
    __table_args__ = (db.Index('idx_reviews_course', 'course_id', 'is_approved'),
                       db.Index('idx_reviews_user', 'user_id'),
                       db.Index('idx_reviews_created', 'is_approved', 'created_at'),)
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    rating = db.Column(db.Integer, default=5)
    comment = db.Column(db.Text)
    is_approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship('User')
    # نظرات پیشرفته (مشابه دیجی‌کالا) — ستون‌ها با ALTER به دیتابیس موجود اضافه شده‌اند
    pros = db.Column(db.Text, default='')      # نقاط قوت (هر خط یک مورد)
    cons = db.Column(db.Text, default='')      # نقاط ضعف
    buyer_verified = db.Column(db.Boolean, default=False)  # خرید تأییدشده


class Favorite(db.Model):
    __tablename__ = 'favorites'
    __table_args__ = (db.Index('idx_fav_user', 'user_id'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    course = db.relationship('Course')


class Order(db.Model):
    __tablename__ = 'orders'
    __table_args__ = (db.Index('idx_orders_user_status', 'user_id', 'status'),
                       db.Index('idx_orders_status_created', 'status', 'created_at'),
                       db.Index('idx_orders_user_created', 'user_id', 'created_at'),)
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total = db.Column(db.Integer, default=0)
    discount = db.Column(db.Integer, default=0)
    final_total = db.Column(db.Integer, default=0)
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupons.id'))
    status = db.Column(db.String(20), default='pending')  # pending | paid | failed | canceled
    gateway = db.Column(db.String(40))
    ref_id = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=utcnow)
    paid_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    user = db.relationship('User', backref=db.backref('orders', lazy='dynamic'))
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan', lazy=True)
    installments = db.relationship('Installment', cascade='all, delete-orphan', lazy=True)
    coupon = db.relationship('Coupon')
    bundle_id = db.Column(db.Integer, nullable=True)  # اگر سفارش از باندل باشد
    installment_count = db.Column(db.Integer, default=0)  # تعداد اقساط (0 = یکجا)

    @property
    def status_fa(self):
        return {'pending': 'در انتظار پرداخت', 'paid': 'پرداخت‌شده',
                'failed': 'ناموفق', 'canceled': 'لغو شده',
                'pending_verify': 'در انتظار تایید فیش'}.get(self.status, self.status)


class PaymentProof(db.Model):
    """فیش واریزی کارت‌به‌کارت — ثبت و تایید توسط ادمین"""
    __tablename__ = 'payment_proofs'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    payer_name = db.Column(db.String(120), nullable=False)
    ref_number = db.Column(db.String(120))
    amount = db.Column(db.Integer, default=0)
    file = db.Column(db.String(300))
    note = db.Column(db.String(300))
    status = db.Column(db.String(20), default='pending')  # pending | approved | rejected
    admin_note = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=utcnow)
    verified_at = db.Column(db.DateTime)
    order = db.relationship('Order')


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    __table_args__ = (db.Index('idx_orderitems_order', 'order_id'),
                       db.Index('idx_orderitems_course', 'course_id'),)
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    price = db.Column(db.Integer, default=0)
    course = db.relationship('Course')
    product = db.relationship('Product')


class Coupon(db.Model):
    __tablename__ = 'coupons'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    type = db.Column(db.String(10), default='percent')  # percent | fixed
    value = db.Column(db.Integer, default=10)
    max_uses = db.Column(db.Integer, default=100)
    used_count = db.Column(db.Integer, default=0)
    min_amount = db.Column(db.Integer, default=0)
    expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    @property
    def is_valid(self):
        if not self.is_active:
            return False
        if self.max_uses and self.used_count >= self.max_uses:
            return False
        if self.expires_at:
            exp = self.expires_at
            if hasattr(exp, 'tzinfo') and exp.tzinfo is not None:
                exp = exp.replace(tzinfo=None)
            if exp < utcnow():
                return False
        return True


class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    __table_args__ = (db.Index('idx_enroll_user_course', 'user_id', 'course_id'),
                       db.Index('idx_enroll_course', 'course_id'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    progress = db.Column(db.Text, default='[]')  # لیست شناسه جلسات تکمیل‌شده
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)  # آخرین فعالیت (یادآور ادامه یادگیری)
    user = db.relationship('User', backref='enrollments')
    course = db.relationship('Course', backref='enrollments')

    def progress_list(self):
        try:
            v = json.loads(self.progress or '[]')
            return v if isinstance(v, list) else []
        except Exception:
            return []

    def save_progress(self, lst):
        self.progress = json.dumps(lst)
        self.updated_at = utcnow()  # آخرین فعالیت — مبنای یادآور ادامه یادگیری

    @property
    def percent(self):
        total = self.course.lesson_count
        if not total:
            return 0
        return round(len(self.progress_list()) * 100 / total)

    @property
    def is_completed(self):
        return self.percent >= 100


class Ticket(db.Model):
    __tablename__ = 'tickets'
    __table_args__ = (db.Index('idx_tickets_user_status', 'user_id', 'status'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text)
    status = db.Column(db.String(20), default='open')  # open | answered | closed
    admin_reply = db.Column(db.Text)
    category = db.Column(db.String(60), default='عمومی')  # دسته‌بندی
    priority = db.Column(db.String(20), default='normal')  # low | normal | high | urgent
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # ارجاع به پشتیبان
    attachment = db.Column(db.String(300))  # فایل پیوست
    created_at = db.Column(db.DateTime, default=utcnow)
    first_response_at = db.Column(db.DateTime)  # برای میانگین زمان پاسخ
    answered_at = db.Column(db.DateTime)
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('tickets', lazy='dynamic'))
    assignee = db.relationship('User', foreign_keys=[assigned_to])


class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    __table_args__ = (db.Index('idx_blog_published', 'published', 'created_at'),)
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    excerpt = db.Column(db.String(400))
    body = db.Column(db.Text)
    image = db.Column(db.String(300))
    category = db.Column(db.String(80), default='آموزش')
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    views = db.Column(db.Integer, default=0)
    published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    author = db.relationship('User')

    @property
    def read_time(self):
        words = len((self.body or '').split())
        return max(1, round(words / 220))


class SeoMeta(db.Model):
    """تنظیمات سئو اختصاصی برای هر آدرس (شبیه Rank Math)"""
    __tablename__ = 'seo_metas'
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(300), unique=True, nullable=False, index=True)  # مثل /course/xxx
    title = db.Column(db.String(200))
    description = db.Column(db.String(400))
    keywords = db.Column(db.String(300))
    focus_keyword = db.Column(db.String(100))   # کلمه کلیدی اصلی
    canonical = db.Column(db.String(300))
    noindex = db.Column(db.Boolean, default=False)
    nofollow = db.Column(db.Boolean, default=False)
    og_image = db.Column(db.String(300))
    og_title = db.Column(db.String(200))
    og_desc = db.Column(db.String(400))
    # امتیاز سئو (محاسبه‌شده)
    score = db.Column(db.Integer, default=0)           # 0-100
    score_grade = db.Column(db.String(10), default='') # great|good|bad
    readability = db.Column(db.Integer, default=0)     # 0-100
    last_analyzed = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)


class RedirectRule(db.Model):
    """ریدایرکت 301 — مدیریت شده از پنل سئو"""
    __tablename__ = 'redirect_rules'
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(300), unique=True, nullable=False, index=True)  # /old-path
    target = db.Column(db.String(300), nullable=False)  # /new-path
    code = db.Column(db.Integer, default=301)  # 301 | 302
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)


class NotFoundLog(db.Model):
    """مانیتور خطاهای 404 — برای پیدا کردن لینک‌های شکسته"""
    __tablename__ = 'notfound_logs'
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(300), index=True)
    referrer = db.Column(db.String(400))
    count = db.Column(db.Integer, default=1)
    first_seen = db.Column(db.DateTime, default=utcnow)
    last_seen = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)


class BlogComment(db.Model):
    __tablename__ = 'blog_comments'
    __table_args__ = (db.Index('idx_bc_post', 'post_id'),)
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    is_approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    post = db.relationship('BlogPost', backref='comments')


class NewsletterEmail(db.Model):
    __tablename__ = 'newsletter_emails'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160))
    subject = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)


class PaymentLog(db.Model):
    __tablename__ = 'payment_logs'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer)
    gateway = db.Column(db.String(40))
    amount = db.Column(db.Integer)
    status = db.Column(db.String(20))
    ref_id = db.Column(db.String(160))
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)


class Setting(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text)


class Page(db.Model):
    """صفحات ساخته‌شده با صفحه‌ساز (شبیه Elementor)"""
    __tablename__ = 'pages'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    ptype = db.Column(db.String(20), default='page')  # home | header | footer | mobile_menu | page
    content = db.Column(db.Text, default='{"rows":[]}')  # JSON بلوک‌ها
    is_published = db.Column(db.Boolean, default=True)
    publish_at = db.Column(db.DateTime, nullable=True)  # زمان‌بندی انتشار
    custom_header = db.Column(db.Integer, nullable=True)  # هدر اختصاصی (آیدی صفحه هدر)
    custom_footer = db.Column(db.Integer, nullable=True)  # فوتر اختصاصی
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    def parsed(self):
        try:
            return json.loads(self.content or '{"rows":[]}')
        except Exception:
            return {'settings': {}, 'rows': []}

    def rows(self):
        """ردیف‌های صفحه — با پاکسازی کامل (ضد داده خراب: settings/data/style رشته‌ای)"""
        rows = self.parsed().get('rows', [])
        try:
            from blueprints.builder import _sanitize_rows
            return _sanitize_rows(rows)
        except Exception:
            return rows

    def settings(self):
        return self.parsed().get('settings', {})


class ActivityLog(db.Model):
    """لاگ فعالیت کاربران — ورود، خرید، تیکت و رویدادهای مهم"""
    __tablename__ = 'activity_logs'
    __table_args__ = (db.Index('idx_activity_user', 'user_id', 'created_at'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(60), nullable=False)   # login | order | payment | ticket | profile
    detail = db.Column(db.String(300))
    ip = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship('User')


# ================================================================
# سیستم آزمون و تمرین (ارزیابی و تعامل)
# ================================================================
class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    passing_score = db.Column(db.Integer, default=50)      # درصد قبولی
    time_limit = db.Column(db.Integer, default=0)           # دقیقه (0 = بدون محدودیت)
    is_placement = db.Column(db.Boolean, default=False)     # آزمون تعیین سطح سراسری
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    course = db.relationship('Course', backref='quizzes')
    questions = db.relationship('QuizQuestion', backref='quiz',
                                cascade='all, delete-orphan', order_by='QuizQuestion.sort')


class QuizQuestion(db.Model):
    __tablename__ = 'quiz_questions'
    __table_args__ = (db.Index('idx_quiz_q_quiz', 'quiz_id'),)
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    text = db.Column(db.String(400), nullable=False)
    choices = db.Column(db.Text, default='[]')   # JSON لیست گزینه‌ها
    correct_index = db.Column(db.Integer, default=0)
    explanation = db.Column(db.String(400))
    sort = db.Column(db.Integer, default=0)

    def choices_list(self):
        import json
        try:
            return json.loads(self.choices or '[]')
        except Exception:
            return []


class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score = db.Column(db.Float, default=0)          # درصد
    passed = db.Column(db.Boolean, default=False)
    answers = db.Column(db.Text, default='[]')      # JSON
    started_at = db.Column(db.DateTime, default=utcnow)
    finished_at = db.Column(db.DateTime)
    quiz = db.relationship('Quiz')
    user = db.relationship('User')


class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    max_score = db.Column(db.Integer, default=100)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    course = db.relationship('Course', backref='assignments')
    submissions = db.relationship('AssignmentSubmission', backref='assignment',
                                  cascade='all, delete-orphan')


class AssignmentSubmission(db.Model):
    __tablename__ = 'assignment_submissions'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text)
    file = db.Column(db.String(300))
    score = db.Column(db.Integer)
    feedback = db.Column(db.Text)
    status = db.Column(db.String(20), default='submitted')  # submitted | graded
    created_at = db.Column(db.DateTime, default=utcnow)
    graded_at = db.Column(db.DateTime)
    user = db.relationship('User')


class LessonQuestion(db.Model):
    """پرسش و پاسخ زیر هر درس"""
    __tablename__ = 'lesson_questions'
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)
    answered_at = db.Column(db.DateTime)
    user = db.relationship('User')
    lesson = db.relationship('Lesson')


# ================================================================
# گیمیفیکیشن، کیف پول و ارجاع
# ================================================================
class PointLog(db.Model):
    __tablename__ = 'point_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    points = db.Column(db.Integer, default=0)
    reason = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship('User')


class WalletTransaction(db.Model):
    __tablename__ = 'wallet_transactions'
    __table_args__ = (db.Index('idx_wallet_user', 'user_id'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, default=0)       # + شارژ / − خرید
    type = db.Column(db.String(20), default='charge')  # charge | spend | bonus | refund
    detail = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship('User')


class Bundle(db.Model):
    __tablename__ = 'bundles'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(300), default='cover-python.webp')
    price = db.Column(db.Integer, default=0)
    discount_price = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    courses = db.relationship('Course', secondary='bundle_courses',
                              backref='bundles', lazy='joined')


class BundleCourse(db.Model):
    __tablename__ = 'bundle_courses'
    id = db.Column(db.Integer, primary_key=True)
    bundle_id = db.Column(db.Integer, db.ForeignKey('bundles.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)


class StudyPlan(db.Model):
    __tablename__ = 'study_plans'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    daily_minutes = db.Column(db.Integer, default=60)
    goal = db.Column(db.String(300))
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    user = db.relationship('User')


# ================================================================
# نسخه‌بندی صفحات (تاریخچه تغییرات)
# ================================================================
class PageRevision(db.Model):
    __tablename__ = 'page_revisions'
    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer, db.ForeignKey('pages.id'), nullable=False)
    content = db.Column(db.Text, default='{"rows":[]}')
    note = db.Column(db.String(200))
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    page = db.relationship('Page')
    author = db.relationship('User')


# ================================================================
# اعلان‌های داخلی
# ================================================================
class Notification(db.Model):
    __tablename__ = 'notifications'
    __table_args__ = (db.Index('idx_notif_user_read', 'user_id', 'is_read'),
                       db.Index('idx_notif_title_link', 'title', 'link'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.String(400))
    icon = db.Column(db.String(10), default='🔔')
    link = db.Column(db.String(300))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship('User')

    @staticmethod
    def notify(user_id, title, body='', icon='🔔', link=''):
        db.session.add(Notification(user_id=user_id, title=title, body=body,
                                    icon=icon, link=link))


# ================================================================
# نقش‌ها و دسترسی‌ها (Permission-Based)
# ================================================================
ROLES = {
    'super_admin': dict(name='سوپر ادمین', fa='سوپر ادمین',
        permissions=['*']),
    'admin': dict(name='مدیر', fa='ادمین',
        permissions=['dashboard', 'view_users', 'edit_users', 'manage_courses',
                     'manage_builder', 'manage_pages', 'manage_bundles', 'view_orders',
                     'approve_payments', 'manage_coupons', 'manage_blog', 'reply_tickets',
                     'view_reports', 'manage_settings', 'manage_gateways', 'manage_sms',
                     'manage_messengers', 'manage_seo', 'view_all_revenue', 'manage_roles']),
    'teacher': dict(name='مدرس', fa='استاد',
        permissions=['dashboard', 'edit_own_courses', 'view_own_students',
                     'reply_questions', 'grade_assignments', 'manage_own_quizzes',
                     'view_own_revenue', 'request_payout']),
    'student': dict(name='دانشجو', fa='دانشجو',
        permissions=['dashboard']),
    'secretary': dict(name='منشی', fa='منشی',
        permissions=['dashboard', 'view_users', 'register_students', 'view_consultations',
                     'view_orders', 'send_sms', 'view_daily_classes', 'track_leads']),
    'support': dict(name='پشتیبان', fa='پشتیبان',
        permissions=['dashboard', 'view_users', 'reply_tickets', 'view_user_courses',
                     'use_canned_replies']),
    'operator': dict(name='اپراتور', fa='اپراتور',
        permissions=['dashboard', 'view_orders', 'approve_payments', 'contact_users',
                     'view_daily_tasks', 'send_sms']),
}

# معادل فارسی برای نمایش
ROLE_FA = {k: v['fa'] for k, v in ROLES.items()}

PERMISSION_FA = {
    'dashboard': 'داشبورد', 'view_users': 'مشاهده کاربران', 'edit_users': 'ویرایش کاربران',
    'manage_courses': 'مدیریت دوره‌ها', 'edit_own_courses': 'مدیریت دوره‌های خود',
    'view_own_students': 'مشاهده دانشجویان خود', 'manage_builder': 'مدیریت صفحه‌ساز',
    'manage_pages': 'مدیریت صفحات', 'view_orders': 'مشاهده سفارش‌ها',
    'approve_payments': 'تایید پرداخت‌ها', 'manage_coupons': 'مدیریت تخفیف‌ها',
    'manage_blog': 'مدیریت وبلاگ', 'reply_tickets': 'پاسخ تیکت‌ها',
    'view_reports': 'مشاهده گزارش‌ها', 'manage_settings': 'تنظیمات سایت',
    'manage_gateways': 'درگاه‌ها', 'manage_sms': 'پیامک', 'manage_messengers': 'پیام‌رسان‌ها',
    'manage_seo': 'مدیریت سئو', 'view_all_revenue': 'مشاهده درآمد کل',
    'view_own_revenue': 'مشاهده درآمد خود', 'manage_roles': 'مدیریت نقش‌ها',
    'reply_questions': 'پاسخ به پرسش‌ها', 'grade_assignments': 'نمره‌دهی تکالیف',
    'manage_own_quizzes': 'مدیریت آزمون‌های خود', 'request_payout': 'درخواست تسویه',
    'register_students': 'ثبت‌نام دانشجو', 'view_consultations': 'مشاوره‌ها',
    'send_sms': 'ارسال پیامک', 'view_daily_classes': 'کلاس‌های روزانه',
    'track_leads': 'پیگیری لیدها', 'view_user_courses': 'دوره‌های کاربر',
    'use_canned_replies': 'پاسخ‌های آماده', 'contact_users': 'تماس با کاربران',
    'view_daily_tasks': 'وظایف روزانه',
}


# ================================================================
# فرم‌ساز حرفه‌ای
# ================================================================
class CustomForm(db.Model):
    __tablename__ = 'custom_forms'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    description = db.Column(db.Text)
    fields = db.Column(db.Text, default='[]')   # JSON: [{label,type,required,options}]
    notify_sms = db.Column(db.Boolean, default=False)
    notify_messenger = db.Column(db.String(20))  # telegram/bale/eitaa/...
    success_msg = db.Column(db.String(300), default='ثبت شد ✅')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    def fields_list(self):
        try:
            return json.loads(self.fields or '[]')
        except Exception:
            return []


class CustomFormEntry(db.Model):
    __tablename__ = 'custom_form_entries'
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey('custom_forms.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    data = db.Column(db.Text, default='{}')     # JSON: {label: value}
    created_at = db.Column(db.DateTime, default=utcnow)
    form = db.relationship('CustomForm')


# ================================================================
# پاسخ‌های آماده تیکت
# ================================================================
class CannedReply(db.Model):
    __tablename__ = 'canned_replies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)


# ================================================================
# منوساز حرفه‌ای — چند منو + زیرمنو + نمایش بر اساس نقش
# ================================================================
class Menu(db.Model):
    __tablename__ = 'menus'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    location = db.Column(db.String(30), default='main')  # main | footer | mobile | user
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    items = db.relationship('MenuItem', backref='menu', cascade='all, delete-orphan',
                            order_by='MenuItem.sort')


class MenuItem(db.Model):
    __tablename__ = 'menu_items'
    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('menus.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('menu_items.id'), nullable=True)
    label = db.Column(db.String(120), nullable=False)
    url = db.Column(db.String(300), default='#')
    icon = db.Column(db.String(10), default='')
    roles = db.Column(db.String(120), default='')  # '' = همه | comma list: student,teacher
    target_blank = db.Column(db.Boolean, default=False)
    sort = db.Column(db.Integer, default=0)
    children = db.relationship('MenuItem', backref=db.backref('parent', remote_side=[id]),
                               cascade='all, delete-orphan', order_by='MenuItem.sort')


# ================================================================
# چت آنلاین پشتیبانی
# ================================================================
class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship('User')


# ================================================================
# درخواست تسویه مدرس
# ================================================================
class PayoutRequest(db.Model):
    __tablename__ = 'payout_requests'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, default=0)
    account = db.Column(db.String(300))  # شماره شبا/کارت
    status = db.Column(db.String(20), default='pending')  # pending | paid | rejected
    admin_note = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=utcnow)
    paid_at = db.Column(db.DateTime)
    teacher = db.relationship('User')


# ================================================================
# چالش هفتگی و تقویم مطالعه
# ================================================================
class StudyDay(db.Model):
    __tablename__ = 'study_days'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    day = db.Column(db.String(10), nullable=False)      # YYYY-MM-DD
    lessons_done = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)


# ================================================================
# انجمن گفتگو
# ================================================================
class ForumTopic(db.Model):
    __tablename__ = 'forum_topics'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text)
    is_pinned = db.Column(db.Boolean, default=False)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship('User')
    course = db.relationship('Course')
    posts = db.relationship('ForumPost', backref='topic', cascade='all, delete-orphan')


class ForumPost(db.Model):
    __tablename__ = 'forum_posts'
    __table_args__ = (db.Index('idx_forumposts_topic', 'topic_id'),)
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('forum_topics.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship('User')


# ================================================================
# کلاس آنلاین (لایو) — لینک اسکایروم/گپ/وبینار
# ================================================================
class LiveSession(db.Model):
    __tablename__ = 'live_sessions'
    __table_args__ = (db.Index('idx_live_starts', 'starts_at'),)
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    link = db.Column(db.String(400))
    starts_at = db.Column(db.DateTime, nullable=False)
    duration_min = db.Column(db.Integer, default=90)
    is_recorded = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    course = db.relationship('Course')


# ================================================================
# پرداخت اقساطی — قسط‌های یک سفارش
# ================================================================
class Installment(db.Model):
    __tablename__ = 'installments'
    __table_args__ = (db.Index('idx_installments_order', 'order_id'),)
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    number = db.Column(db.Integer, default=1)       # قسط چندم
    amount = db.Column(db.Integer, default=0)
    due_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')  # pending | paid | overdue
    paid_at = db.Column(db.DateTime)
    ref_id = db.Column(db.String(120))
    order = db.relationship('Order', overlaps='installments')


# ================================================================
# بانک سوال — سوالات مشترک قابل استفاده در آزمون‌ها
# ================================================================
class QuestionBank(db.Model):
    __tablename__ = 'question_bank'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), default='عمومی')
    text = db.Column(db.String(400), nullable=False)
    choices = db.Column(db.Text, default='[]')
    correct_index = db.Column(db.Integer, default=0)
    explanation = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=utcnow)

    def choices_list(self):
        try:
            return json.loads(self.choices or '[]')
        except Exception:
            return []


# ================================================================
# چند مدرس برای یک دوره
# ================================================================
class CourseTeacher(db.Model):
    __tablename__ = 'course_teachers'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role_name = db.Column(db.String(100), default='مدرس')


class TicketReply(db.Model):
    """پاسخ‌های تیکت — تاریخچه مکالمه"""
    __tablename__ = 'ticket_replies'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    body = db.Column(db.Text, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    attachment = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=utcnow)
    ticket = db.relationship('Ticket', backref='replies')
    user = db.relationship('User')


# ================================================================
# پیام خصوصی (DM)
# ================================================================
class PrivateMessage(db.Model):
    __tablename__ = 'private_messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')


# ================================================================
# نظرسنجی انجمن (Poll)
# ================================================================
class ForumPoll(db.Model):
    __tablename__ = 'forum_polls'
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('forum_topics.id'), nullable=False)
    question = db.Column(db.String(300), nullable=False)
    options = db.Column(db.Text, default='[]')   # JSON list
    created_at = db.Column(db.DateTime, default=utcnow)
    topic = db.relationship('ForumTopic', backref='polls')
    votes = db.relationship('ForumPollVote', backref='poll', cascade='all, delete-orphan')

    def options_list(self):
        try:
            return json.loads(self.options or '[]')
        except Exception:
            return []


class ForumPollVote(db.Model):
    __tablename__ = 'forum_poll_votes'
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('forum_polls.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    option_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)


# ================================================================
# رضایت سنجی پس از دوره
# ================================================================
class CourseFeedback(db.Model):
    __tablename__ = 'course_feedback'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    score = db.Column(db.Integer, default=5)          # 1-5
    recommend = db.Column(db.Boolean, default=True)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship('User')
    course = db.relationship('Course')


# ================================================================
# شبیه‌ساز آزمون (کنکور) — آزمون تصادفی از بانک سوال
# ================================================================
class ExamAttempt(db.Model):
    __tablename__ = 'exam_attempts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    category = db.Column(db.String(100), default='عمومی')
    question_ids = db.Column(db.Text, default='[]')   # شناسه سوالات (json)
    answers = db.Column(db.Text, default='{}')        # پاسخ‌های کاربر (json)
    score = db.Column(db.Integer, default=0)
    total = db.Column(db.Integer, default=0)
    duration_sec = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    user = db.relationship('User')

    def qids(self):
        try:
            return json.loads(self.question_ids or '[]')
        except Exception:
            return []

    def answers_map(self):
        try:
            return json.loads(self.answers or '{}')
        except Exception:
            return {}


# ================================================================
# داستان‌های موفقیت دانشجویان (مطالعات موردی)
# ================================================================
class SuccessStory(db.Model):
    __tablename__ = 'success_stories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120), default='')      # شغل/موقعیت فعلی
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    story = db.Column(db.Text, default='')            # داستان موفقیت
    result = db.Column(db.String(200), default='')    # نتیجه (مثلاً «استخدام در شرکت X»)
    color = db.Column(db.String(20), default='#7c3aed')
    is_active = db.Column(db.Boolean, default=True)
    sort = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    course = db.relationship('Course')


# ================================================================
# کتابخانه رسانه مرکزی — مدیریت یکپارچه فایل‌های آپلودی
# ================================================================
class Media(db.Model):
    __tablename__ = 'media'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)      # نام اصلی فایل
    path = db.Column(db.String(400), nullable=False)          # مسیر نسبی در static (مثل uploads/media/ab12.jpg)
    mime = db.Column(db.String(80), default='')
    size = db.Column(db.Integer, default=0)                   # بایت
    width = db.Column(db.Integer, nullable=True)              # برای تصاویر
    height = db.Column(db.Integer, nullable=True)
    kind = db.Column(db.String(20), default='file')           # image | video | audio | file
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    uploader = db.relationship('User')

    @property
    def url(self):
        return '/static/' + self.path.lstrip('/')

    @property
    def human_size(self):
        try:
            from validators import human_size
            return human_size(self.size)
        except Exception:
            return f'{self.size} B'


# ================================================================
# محصولات فیزیکی (فروشگاه) — جدا از دوره‌های آموزشی
# ================================================================
class Product(db.Model):
    __tablename__ = 'products'
    __table_args__ = (db.Index('idx_products_active', 'is_active', 'featured'),)
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    description = db.Column(db.Text, default='')
    price = db.Column(db.Integer, default=0)            # تومان
    discount_price = db.Column(db.Integer, default=0)   # 0 = بدون تخفیف
    image = db.Column(db.String(300), default='')       # تصویر اصلی
    category = db.Column(db.String(100), default='')    # دسته (لیوان و فنجان، ...)
    sku = db.Column(db.String(60), default='')          # شناسه محصول
    dk_product_id = db.Column(db.String(60), default='')  # شناسه محصول در دیجی‌کالا (Seller Center)
    dimensions = db.Column(db.String(100), default='')  # ابعاد (۷×۷ سانتی‌متر)
    weight = db.Column(db.String(50), default='')       # وزن (۲۸۰ گرم)
    material = db.Column(db.String(100), default='')    # جنس (شیشه)
    features = db.Column(db.Text, default='')           # ویژگی‌ها (هر خط یک مورد)
    stock = db.Column(db.Integer, default=0)            # موجودی
    featured = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    @property
    def final_price(self):
        return self.discount_price if self.discount_price and self.discount_price < self.price else self.price

    @property
    def has_discount(self):
        return bool(self.discount_price and self.discount_price < self.price)

    def features_list(self):
        try:
            import json as _json
            return _json.loads(self.features or '[]')
        except Exception:
            return [f for f in (self.features or '').split('\n') if f.strip()]


# ================================================================
# تنظیم خودکار انکودینگ utf8mb4 و موتور InnoDB برای MySQL/MariaDB
# ================================================================
def _apply_mysql_table_options(metadata):
    """تنظیم مشخصات MySQL برای تمام جدول‌ها جهت پیشگیری از خطای Duplicate entry در اسلاگ‌های فارسی"""
    for _tbl in metadata.tables.values():
        _tbl.kwargs.setdefault('mysql_charset', 'utf8mb4')
        _tbl.kwargs.setdefault('mysql_collate', 'utf8mb4_unicode_ci')
        _tbl.kwargs.setdefault('mysql_engine', 'InnoDB')

_apply_mysql_table_options(db.metadata)


def annotate_course_stats(courses):
    """محاسبهٔ یکجا (bulk) آمار دوره‌ها — حذف N+1 برای rating/review_count/students_count.

    برای هر دوره در `courses` مقادیر `_agg_rating`, `_agg_review_count`, `_agg_students`
    را ست می‌کند تا propertyهای `rating`/`review_count`/`students_count` کوئری جدا نزنند.
    """
    courses = [c for c in courses if c is not None]
    if not courses:
        return courses
    ids = [c.id for c in courses]
    # میانگین امتیاز + تعداد نظرات به‌ازای دوره (یک کوئری تجمیعی)
    try:
        rows = db.session.query(Review.course_id,
                                db.func.avg(Review.rating),
                                db.func.count(Review.id)) \
            .filter(Review.course_id.in_(ids), Review.is_approved == True) \
            .group_by(Review.course_id).all()
        stat = {r[0]: (round(float(r[1] or 0), 1), int(r[2] or 0)) for r in rows}
    except Exception:
        stat = {}
    # تعداد ثبت‌نام به‌ازای دوره (یک کوئری تجمیعی)
    try:
        erows = db.session.query(Enrollment.course_id, db.func.count(Enrollment.id)) \
            .filter(Enrollment.course_id.in_(ids)) \
            .group_by(Enrollment.course_id).all()
        encount = {r[0]: int(r[1] or 0) for r in erows}
    except Exception:
        encount = {}
    for c in courses:
        if c.id in stat:
            c._agg_rating, c._agg_review_count = stat[c.id]
        c._agg_students = (c.seeded_students or 0) + encount.get(c.id, 0)
    return courses

