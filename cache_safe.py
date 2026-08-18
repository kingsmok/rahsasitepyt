# -*- coding: utf-8 -*-
"""پروکسی‌های داده‌ای امن برای کش بین‌درخواستی.

اشیای ORM (SQLAlchemy) نباید در کش ذخیره شوند:
 - بعد از بسته‌شدن سشن → DetachedInstanceError → خطای 500
 - اگر به سشن جدید add شوند → اشیای کهنه وارد identity map می‌شوند →
   کوئری‌های بعدی همان درخواست دادهٔ قدیمی برمی‌گردانند (باعث باگ شد!)

این ماژول «نسخهٔ سبک» اشیا را با دادهٔ صرف (بدون اتصال به دیتابیس) می‌سازد
تا قالب‌ها دقیقاً همان خروجی قبلی را ببینند.
"""


class UserLite:
    __slots__ = ('name', 'avatar_color', 'bio')

    def __init__(self, name, avatar_color=None, bio=''):
        self.name = name or ''
        self.avatar_color = avatar_color or '#2563eb'
        self.bio = bio or ''

    def initials(self):
        parts = (self.name or '؟').split()
        return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else ''))


class TeacherLite(UserLite):
    __slots__ = ('id',)

    def __init__(self, uid, name, avatar_color=None, bio=''):
        super().__init__(name, avatar_color, bio)
        self.id = uid


class CourseLite:
    """کارت دوره — همه چیزهایی که course_card و ویجت‌ها نیاز دارند."""
    __slots__ = ('id', 'title', 'slug', 'image', 'image_url', 'featured', 'price',
                 'discount_price', 'duration_hours', 'delivery_type',
                 'rating', 'review_count', 'students_count', 'category', 'teacher')

    def __init__(self, c=None, rating=0, review_count=0, students_count=0,
                 category=None, teacher=None, **fields):
        if c is None:
            for k in ('id', 'title', 'slug', 'image', 'featured', 'price',
                      'discount_price', 'duration_hours', 'delivery_type'):
                setattr(self, k, fields.get(k))
            image = str(self.image or '').strip()
            self.image_url = (image if image.startswith('https://') else
                              '/static/img/' + image if image else
                              '/static/img/course-placeholder.webp')
            self.rating = rating
            self.review_count = review_count
            self.students_count = students_count
            self.category = category
            self.teacher = teacher
            return
        self.id = c.id
        self.title = c.title
        self.slug = c.slug
        self.image = c.image
        self.image_url = c.image_url
        self.featured = bool(c.featured)
        self.price = c.price or 0
        self.discount_price = c.discount_price or 0
        self.duration_hours = c.duration_hours
        self.delivery_type = getattr(c, 'delivery_type', 'online') or 'online'
        # آمار تجمیعی — از مقادیر از‌پیش‌محاسبه‌شده یا محاسبهٔ سبک
        self.rating = rating
        self.review_count = review_count
        self.students_count = students_count
        # دسته و مدرس — نسخهٔ سبک
        self.category = category
        self.teacher = teacher

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

    def is_free(self):
        return self.final_price == 0


class CatLite:
    __slots__ = ('id', 'name', 'slug', 'icon', 'color', 'sort', 'courses')

    def __init__(self, name, slug, icon='🎓', color='#2563eb', cid=0, sort=0, courses=None):
        self.id = cid
        self.name = name
        self.slug = slug
        self.icon = icon
        self.color = color
        self.sort = sort
        self.courses = courses or []


class PageLite:
    """نسخهٔ سبک Page صفحه‌ساز — بدون اتصال به دیتابیس."""
    __slots__ = ('id', 'title', 'ptype', 'is_published', 'custom_header',
                 'custom_footer', '_parsed', '_rows')

    def __init__(self, ptype, title='', is_published=True, content='{}',
                 custom_header=None, custom_footer=None, pid=0):
        self.id = pid
        self.title = title
        self.ptype = ptype
        self.is_published = bool(is_published)
        self.custom_header = custom_header
        self.custom_footer = custom_footer
        try:
            self._parsed = __import__('json').loads(content or '{}')
        except Exception:
            self._parsed = {}
        self._rows = None

    def rows(self):
        if self._rows is None:
            rows = self._parsed.get('rows', [])
            try:
                from blueprints.builder import _sanitize_rows
                self._rows = _sanitize_rows(rows)
            except Exception:
                self._rows = rows
        return self._rows

    def settings(self):
        return self._parsed.get('settings', {}) or {}


class ReviewLite:
    __slots__ = ('rating', 'comment', 'pros', 'cons', 'buyer_verified',
                 'user', 'course', 'created_at')

    def __init__(self, rating, comment='', pros='', cons='', buyer_verified=False,
                 user=None, course=None, created_at=None):
        self.rating = rating or 0
        self.comment = comment or ''
        self.pros = pros or ''
        self.cons = cons or ''
        self.buyer_verified = bool(buyer_verified)
        self.user = user
        self.course = course
        self.created_at = created_at


class StoryLite:
    __slots__ = ('name', 'color', 'role', 'result', 'story', 'course')

    def __init__(self, name, color='#2563eb', role='', result='', story='', course=None):
        self.name = name or ''
        self.color = color or '#2563eb'
        self.role = role or ''
        self.result = result or ''
        self.story = story or ''
        self.course = course


class PostLite:
    __slots__ = ('slug', 'image', 'category', 'created_at', 'title', 'id')

    def __init__(self, slug, image='', category='', created_at=None, title='', pid=0):
        self.slug = slug
        self.image = image
        self.category = category or ''
        self.created_at = created_at
        self.title = title
        self.id = pid


# ---------------------------------------------------------------- سازنده‌ها

def user_lite(u):
    if u is None:
        return None
    return UserLite(u.name, u.avatar_color, u.bio or '')


def course_lite(c, rating=0, review_count=0, students_count=0):
    """ساخت CourseLite از شیء ORM + آمار تجمیعی (اختیاری).
    اگر آمار داده نشود، از _agg_* خود شیء (که مسیرهای لیست ست کرده‌اند) خوانده می‌شود."""
    if rating == 0 and hasattr(c, '_agg_rating'):
        rating = c._agg_rating
    if review_count == 0 and hasattr(c, '_agg_review_count'):
        review_count = c._agg_review_count
    if students_count == 0 and hasattr(c, '_agg_students'):
        students_count = c._agg_students
    cat = None
    if c.category is not None:
        cat = CatLite(c.category.name, c.category.slug, c.category.icon or '🎓',
                      c.category.color or '#2563eb', cid=c.category.id)
    return CourseLite(c, rating=rating, review_count=review_count,
                      students_count=students_count, category=cat,
                      teacher=user_lite(c.teacher))


def category_lite(c, courses=None):
    return CatLite(c.name, c.slug, c.icon or '🎓', c.color or '#2563eb',
                   cid=c.id, sort=c.sort or 0, courses=courses or [])


def page_lite(p):
    return PageLite(p.ptype, p.title or '', p.is_published, p.content or '{}',
                    p.custom_header, p.custom_footer, pid=p.id)


def review_lite(r):
    return ReviewLite(r.rating, r.comment or '', r.pros or '', r.cons or '',
                      r.buyer_verified, user_lite(r.user),
                      course_lite(r.course) if r.course else None, r.created_at)


def story_lite(s):
    return StoryLite(s.name, s.color or '#2563eb', s.role or '', s.result or '',
                     s.story or '', course_lite(s.course) if s.course else None)


def post_lite(p):
    return PostLite(p.slug, p.image or '', p.category or '', p.created_at,
                    p.title, pid=p.id)
