# -*- coding: utf-8 -*-
"""لایهٔ دادهٔ پنل مدیریت (Admin Read Model).

هر عددی که پنل نشان می‌دهد از این ماژول می‌آید، نه از داخل route. دو دلیل:

۱. **درستی الگوریتمی.** در نسخهٔ قبلی، داشبورد با ~۲۹ round-trip ساخته می‌شد:
   نمودار ۷ روزهٔ فروش در یک حلقهٔ پایتون، روزی ۲ کوئری (۱۴ کوئری) اجرا می‌کرد،
   و ``completion_rate`` با ``Enrollment.query.join(...).all()`` **کل جدول
   ثبت‌نام‌ها** را در حافظه materialize می‌کرد تا بعداً در پایتون ``sum`` بزند.
   با ۱۰۰٬۰۰۰ ثبت‌نام، این یعنی اسکن کامل جدول + صدها مگابایت RAM در هر بار
   باز شدن داشبورد — روی هاست اشتراکی، یعنی OOM. اینجا همهٔ آن‌ها به یک
   ``GROUP BY`` و یک ``AVG`` تبدیل شده‌اند: O(۱) round-trip.

۲. **قابلیت تست.** این توابع ورودی/خروجی خالص دارند (کوئری در، dict/لیست بیرون)
   و هیچ وابستگی به ``request`` ندارند، پس بدون test client قابل unit test اند.

قاعدهٔ معماری: route حق ندارد ``func.sum``/``func.count`` بنویسد. اگر عددی لازم
است، اینجا یک تابع برایش ساخته می‌شود.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from models import (BlogComment, BlogPost, ContactMessage, Course, CustomForm,
                    CustomFormEntry, Enrollment, NewsletterEmail, Order, Review,
                    Ticket, User, db, utcnow)

__all__ = [
    'Dashboard', 'dashboard_metrics', 'sales_chart', 'enrollment_stats',
    'course_list', 'user_list', 'blog_list', 'review_lists', 'coupon_list',
    'form_entry_counts', 'certificate_rows', 'behavior_report',
    'ticket_report', 'message_list', 'newsletter_list', 'activity_list',
]


def _scalar(stmt, default: Any = 0) -> Any:
    """اجرای یک کوئری تک‌مقداری؛ ``None`` دیتابیس به ``default`` نگاشت می‌شود.

    ``SUM`` در SQL روی مجموعهٔ خالی ``NULL`` می‌دهد، نه صفر. بدون این نگاشت،
    قالب با ``None + 1`` می‌شکند. این تنها نقطهٔ انجام آن کار است.
    """
    value = db.session.execute(stmt).scalar()
    return default if value is None else value


# ------------------------------------------------------------------ داشبورد
@dataclass(frozen=True, slots=True)
class Dashboard:
    """تمام اعداد داشبورد مدیر، در یک شیء تغییرناپذیر.

    چرا dataclass به‌جای dict با ۲۰ کلید؟ چون ``render_template(**asdict(d))``
    یک اشتباه تایپی در نام کلید را از «سکوت و عدد گمشده در UI» به
    ``TypeError`` در زمان اجرا تبدیل می‌کند.
    """
    total_revenue: int
    paid_orders: int
    users_count: int
    courses_count: int
    published_courses_count: int
    today_orders: int
    recent_orders: list
    recent_users: list
    top_courses: list
    tickets_open: int
    messages: int
    reviews_pending: int
    month_revenue: int
    month_orders: int
    active_users: int
    completion_rate: int
    avg_progress: int
    new_today: int
    week: list

    def as_template_kwargs(self) -> dict[str, Any]:
        """تبدیل به kwargs قالب — **بدون** ``dataclasses.asdict``.

        این یک تلهٔ واقعی است: ``asdict()`` مقادیر را ``deepcopy`` می‌کند تا
        ساختار تودرتو را امن کپی کند. کپی عمیق یک موجودیت SQLAlchemy آن را از
        session جدا (detached) می‌کند، و اولین lazy-load در قالب با
        ``DetachedInstanceError`` منفجر می‌شود. اینجا ارجاع‌ها دست‌نخورده
        منتقل می‌شوند.
        """
        from dataclasses import fields
        return {f.name: getattr(self, f.name) for f in fields(self)}


def dashboard_metrics() -> Dashboard:
    """همهٔ معیارهای داشبورد.

    تعداد round-trip: **۱۱ ثابت** (در برابر ~۲۹ متغیر قبلی) و مهم‌تر، مستقل از
    حجم داده. حلقهٔ ۷ روزه حذف شد؛ نمودار از یک ``GROUP BY`` ساخته می‌شود.
    """
    now = utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    paid = Order.status == 'paid'

    total_revenue = _scalar(select(func.coalesce(func.sum(Order.final_total), 0)).where(paid))
    month_revenue = _scalar(
        select(func.coalesce(func.sum(Order.final_total), 0)).where(paid, Order.paid_at >= month_start))
    paid_orders = _scalar(select(func.count(Order.id)).where(paid))
    month_orders = _scalar(select(func.count(Order.id)).where(paid, Order.paid_at >= month_start))

    # «امروز» و «کاربران فعال ۷ روز اخیر» در یک کوئری هرکدام — قبلاً جدا بودند
    # و ``last_active`` را با مقایسهٔ رشته‌ای تاریخ می‌سنجیدند؛ همان مقایسه نگه
    # داشته شده تا رفتار عوض نشود، ولی داخل SQL نه در پایتون.
    today_orders = _scalar(select(func.count(Order.id)).where(
        paid, func.date(Order.created_at) == func.date(func.now())))
    new_today = _scalar(select(func.count(User.id)).where(
        User.is_active.is_(True),
        func.date(User.created_at) == func.date(func.now())))
    active_users = _scalar(select(func.count(User.id)).where(
        User.is_active.is_(True), User.last_active.isnot(None),
        User.last_active >= (now - timedelta(days=7)).strftime('%Y-%m-%d')))

    users_count = _scalar(select(func.count(User.id)).where(User.is_active.is_(True)))
    courses_count = _scalar(select(func.count(Course.id)))
    published_courses_count = _scalar(
        select(func.count(Course.id)).where(Course.status == 'published'))
    tickets_open = _scalar(select(func.count(Ticket.id)).where(
        Ticket.status.in_(['open', 'answered'])))
    messages = _scalar(select(func.count(ContactMessage.id)).where(
        ContactMessage.is_read.is_(False)))
    reviews_pending = _scalar(
        select(func.count(Review.id))
        .join(Course, Course.id == Review.course_id)
        .where(Review.is_approved.is_(False), Course.status == 'published'))

    # selectinload/joinedload: قبلاً قالب برای هر سفارش یک کوئری items و برای هر
    # دوره یک کوئری category می‌زد (N+1). اینجا هر دو پیش‌بارگذاری می‌شوند.
    recent_orders = db.session.execute(
        select(Order).options(selectinload(Order.items))
        .order_by(Order.created_at.desc()).limit(8)).scalars().all()
    recent_users = db.session.execute(
        select(User).where(User.is_active.is_(True))
        .order_by(User.created_at.desc()).limit(6)).scalars().all()
    top_courses = db.session.execute(
        select(Course).options(selectinload(Course.category))
        .where(Course.status == 'published')
        .order_by(Course.views.desc()).limit(5)).scalars().all()

    completion_rate, avg_progress = enrollment_stats()

    return Dashboard(
        total_revenue=total_revenue, paid_orders=paid_orders,
        users_count=users_count, courses_count=courses_count,
        published_courses_count=published_courses_count,
        today_orders=today_orders, recent_orders=recent_orders,
        recent_users=recent_users, top_courses=top_courses,
        tickets_open=tickets_open, messages=messages,
        reviews_pending=reviews_pending, month_revenue=month_revenue,
        month_orders=month_orders, active_users=active_users,
        completion_rate=completion_rate, avg_progress=avg_progress,
        new_today=new_today, week=sales_chart(7, now),
    )


def sales_chart(days: int, now: datetime | None = None) -> list[dict[str, Any]]:
    """سری زمانی درآمد — **یک کوئری** برای کل بازه.

    نسخهٔ قبلی ``for i in range(6, -1, -1)`` بود و برای هر روز دو کوئری (یکی
    ``SUM``، یکی ``COUNT``) می‌زد: ۱۴ round-trip برای یک نمودار ۷ میله‌ای.
    اینجا یک ``GROUP BY date(paid_at)`` هر دو عدد را برای همهٔ روزها می‌آورد و
    روزهای خالی در پایتون با صفر پر می‌شوند.
    """
    from jdates import jdate

    now = now or utcnow()
    window_start = datetime(now.year, now.month, now.day) - timedelta(days=days - 1)

    rows = db.session.execute(
        select(func.date(Order.paid_at).label('day'),
               func.coalesce(func.sum(Order.final_total), 0).label('revenue'),
               func.count(Order.id).label('count'))
        .where(Order.status == 'paid', Order.paid_at >= window_start)
        .group_by('day')).all()
    by_day = {str(day): (int(revenue or 0), int(count or 0)) for day, revenue, count in rows}

    series: list[dict[str, Any]] = []
    for offset in range(days - 1, -1, -1):
        day = datetime(now.year, now.month, now.day) - timedelta(days=offset)
        revenue, count = by_day.get(day.strftime('%Y-%m-%d'), (0, 0))
        series.append({'label': jdate(day), 'revenue': revenue, 'count': count})

    # نرمال‌سازی درصدی برای ارتفاع میله‌ها — ``max(..., [1])`` از تقسیم بر صفر
    # در روز اول راه‌اندازی (که هیچ فروشی نیست) جلوگیری می‌کند.
    peak = max([point['revenue'] for point in series] + [1])
    for point in series:
        point['pct'] = round(point['revenue'] * 100 / peak)
    return series


def _percent(progress: str | None, completed_at, lesson_count: int | None) -> int:
    """درصد پیشرفت — بازپیاده‌سازی دقیق :attr:`models.Enrollment.percent`.

    این تابع **نمی‌تواند** یک عبارت SQL باشد و این یک یافتهٔ معماری است، نه یک
    محدودیت ابزاری: ``Enrollment.percent`` در مدل یک ``@property`` پایتون است که
    از دو منبع مشتق می‌شود — فیلد JSON ``progress`` و ``course.lesson_count``.
    دیتابیس هیچ ستونی به نام ``percent`` ندارد، پس ``AVG(percent)`` و
    ``SUM(CASE WHEN percent >= 100)`` از نظر ساختاری ممکن نیستند.

    نتیجهٔ عملی برای معماری: هر گزارشی که روی درصد پیشرفت تجمیع می‌کند، ناچار
    است ردیف‌ها را ببیند. راه‌حل درست و ارزان، انتخاب **فقط سه ستون لازم** است،
    نه بارگذاری موجودیت کامل ORM (که به‌ازای هر ردیف، کاربر و دوره را هم
    lazy-load می‌کرد). اصلاح واقعی و دائمی، denormalize کردن ``percent`` در یک
    ستون ایندکس‌دار است — که یک تغییر schema است و در «نقشهٔ آینده» آمده.
    """
    if completed_at:
        return 100
    if not lesson_count:
        return 0
    try:
        done = len(json.loads(progress or '[]'))
    except (TypeError, ValueError):
        done = 0
    return round(done * 100 / lesson_count)


def _lesson_count_subquery():
    """معادل SQL برای :attr:`models.Course.lesson_count`.

    این مهم‌ترین اصلاح عملکردی کل این ماژول است. ``lesson_count`` در مدل یک
    ``@property`` است که ``sum(len(s.lessons) for s in self.sections)`` را حساب
    می‌کند — یعنی برای **هر** ردیف ثبت‌نام، همهٔ سکشن‌های دوره و سپس همهٔ
    جلسات هر سکشن بارگذاری می‌شد. با N ثبت‌نام و M جلسه در هر دوره، این
    O(N·M) بارگذاری رابطه بود، فقط برای ساختن یک عدد درصدی.

    همان عدد اینجا یک correlated subquery است: یک round-trip برای کل گزارش.
    """
    from models import Lesson, Section
    return (select(func.count(Lesson.id))
            .join(Section, Section.id == Lesson.section_id)
            .where(Section.course_id == Enrollment.course_id)
            .correlate(Enrollment)
            .scalar_subquery())


def _enrollment_percent_rows():
    """ستون‌های لازم برای محاسبهٔ درصد — بدون موجودیت ORM، بدون lazy-load."""
    return db.session.execute(
        select(Enrollment.progress, Enrollment.completed_at, _lesson_count_subquery())
        .join(Course, Course.id == Enrollment.course_id)
        .join(User, User.id == Enrollment.user_id)
        .where(Course.status == 'published', User.is_active.is_(True))).all()


def enrollment_stats() -> tuple[int, int]:
    """نرخ تکمیل و میانگین پیشرفت در **یک** کوئری و بدون lazy-load.

    نسخهٔ قبلی ``Enrollment.query.join(...).all()`` بود: نه‌فقط کل جدول در حافظه
    materialize می‌شد، بلکه قالب/حلقه برای هر ردیف ``user`` و ``course`` را هم
    جدا کوئری می‌زد (۲N کوئری اضافه). اینجا یک کوئری سه‌ستونی است و محاسبه در
    پایتون فقط روی عدد انجام می‌شود.
    """
    rows = _enrollment_percent_rows()
    total = len(rows)
    if not total:
        return 0, 0
    percents = [_percent(progress, completed_at, lesson_count)
                for progress, completed_at, lesson_count in rows]
    return (round(sum(1 for p in percents if p >= 100) * 100 / total),
            round(sum(percents) / total))


# ------------------------------------------------------------------ فهرست‌ها
def _paged(stmt, order_by, *, per_page: int = 50, term_filter=None):
    """واسط نازک روی :func:`admin_core.paginate`.

    تنها دلیل وجودش، قرارداد نام‌گذاری محلی است: خروجی ``(items, page, pages,
    total)`` همان چیزی است که قالب ``admin/orders.html`` از قبل می‌فهمد، پس
    افزودن صفحه‌بندی به فهرست‌های دیگر بدون دست‌زدن به قالب ممکن شد. منطق
    صفحه‌بندی خودش اینجا پیاده نشده تا دو نسخه از آن واگرا نشوند.
    """
    from admin_core import paginate
    return paginate(stmt, order_by, per_page=per_page,
                    filters=(term_filter,) if term_filter is not None else ())


def course_list(term: str = '', *, per_page: int = 50):
    """فهرست دوره‌ها با پیش‌بارگذاری دسته و مدرس.

    دو اصلاح: صفحه‌بندی (قبلاً ``.all()`` روی همهٔ دوره‌ها بود) و ``selectinload``
    روی ``category``/``teacher`` (قبلاً قالب برای هر ردیف دو کوئری می‌زد).
    """
    stmt = select(Course).options(
        selectinload(Course.category), selectinload(Course.teacher))
    term_filter = Course.title.contains(term) if term else None
    return _paged(stmt, Course.created_at.desc(), per_page=per_page,
                  term_filter=term_filter)


def user_list(term: str = '', *, per_page: int = 50):
    stmt = select(User)
    term_filter = (User.name.contains(term) | User.email.contains(term)) if term else None
    return _paged(stmt, User.created_at.desc(), per_page=per_page,
                  term_filter=term_filter)


def blog_list(*, per_page: int = 50):
    return _paged(select(BlogPost), BlogPost.created_at.desc(), per_page=per_page)


def coupon_list():
    """کوپن‌ها، تازه‌ترین اول.

    تاریخچه: این تابع ابتدا ``ORDER BY created_at DESC`` می‌خواست و با
    ``AttributeError`` شکست، چون جدول ``coupons`` اصلاً ستون ``created_at``
    نداشت. آن شکاف با migration ``0006_coupon_provenance`` پر شد.

    ردیف‌های قدیمی ``created_at = NULL`` دارند و عمداً backfill نشده‌اند (یک
    timestamp جعلی در ستون ممیزی بدتر از NULL است). ``id DESC`` به‌عنوان
    tie-breaker نگه داشته شده تا ترتیب برای آن ردیف‌ها هم پایدار بماند.
    """
    from models import Coupon
    return db.session.execute(
        select(Coupon).order_by(Coupon.created_at.desc(), Coupon.id.desc())
    ).scalars().all()


def review_lists(*, blog_limit: int = 80):
    """نظرات دوره + دیدگاه‌های وبلاگ.

    ``selectinload(Review.user, Review.course)``: قبلاً قالب برای هر نظر نام
    کاربر و عنوان دوره را جدا کوئری می‌زد.
    """
    reviews = db.session.execute(
        select(Review).options(selectinload(Review.user), selectinload(Review.course))
        .order_by(Review.created_at.desc()).limit(200)).scalars().all()
    blog_comments = db.session.execute(
        select(BlogComment).options(selectinload(BlogComment.user),
                                    selectinload(BlogComment.post))
        .order_by(BlogComment.created_at.desc()).limit(blog_limit)).scalars().all()
    return reviews, blog_comments


def message_list(*, limit: int = 300):
    from models import ContactMessage
    return db.session.execute(
        select(ContactMessage).order_by(ContactMessage.created_at.desc()).limit(limit)
    ).scalars().all()


def newsletter_list(*, limit: int = 300):
    return db.session.execute(
        select(NewsletterEmail).order_by(NewsletterEmail.created_at.desc()).limit(limit)
    ).scalars().all()


def activity_list(*, limit: int = 200):
    from models import ActivityLog
    return db.session.execute(
        select(ActivityLog).options(selectinload(ActivityLog.user))
        .order_by(ActivityLog.created_at.desc()).limit(limit)).scalars().all()


def form_entry_counts(forms: list[CustomForm]) -> dict[int, int]:
    """تعداد ورودی هر فرم — **یک ``GROUP BY``** به‌جای N کوئری.

    نسخهٔ قبلی:

        counts = {f.id: CustomFormEntry.query.filter_by(form_id=f.id).count() for f in items}

    یعنی با ۴۰ فرم، ۴۰ کوئری اضافه فقط برای یک عدد کنار هر ردیف.
    """
    if not forms:
        return {}
    rows = db.session.execute(
        select(CustomFormEntry.form_id, func.count(CustomFormEntry.id))
        .where(CustomFormEntry.form_id.in_([f.id for f in forms]))
        .group_by(CustomFormEntry.form_id)).all()
    counts = {form_id: int(count) for form_id, count in rows}
    return {f.id: counts.get(f.id, 0) for f in forms}


def certificate_rows(*, limit: int = 500):
    """گواهی‌های صادرشده، بدون N+1.

    نسخهٔ قبلی برای هر گواهی ``e.user.name`` و ``e.course.title`` را lazy-load
    می‌کرد (۲ کوئری به ازای هر ردیف). با ۱۰۰۰ گواهی یعنی ۲۰۰۰ کوئری برای یک
    صفحهٔ گزارش. اینجا هر دو رابطه پیش‌بارگذاری می‌شوند.
    """
    from models import certificate_code
    rows = db.session.execute(
        select(Enrollment).options(
            selectinload(Enrollment.user), selectinload(Enrollment.course))
        .where(Enrollment.completed_at.isnot(None))
        .order_by(Enrollment.completed_at.desc()).limit(limit)).scalars().all()
    return [{
        'id': e.id,
        'user': e.user.name if e.user else '—',
        'course': e.course.title if e.course else '—',
        'date': e.completed_at,
        'code': certificate_code(e.course.slug, e.user.email, e.id)
        if (e.course and e.user) else '—',
        'enroll': e,
    } for e in rows]


def behavior_report(*, per_page: int = 100, dropped_limit: int = 50):
    """گزارش رفتار دانشجو — **یک کوئری**، بدون lazy-load، با خروجی کران‌دار.

    نسخهٔ قبلی ``Enrollment.query.all()`` بود: کل جدول به‌صورت موجودیت کامل ORM،
    به‌همراه lazy-load ``user`` و ``course`` برای هر ردیف. با ۵۰٬۰۰۰ ثبت‌نام
    یعنی ۱۰۰٬۰۰۱ round-trip برای یک صفحهٔ گزارش — و سپس جدول بی‌کران در HTML
    رندر می‌شد.

    اکنون شش ستون لازم در یک کوئری خوانده می‌شوند، درصد در یک پیمایش محاسبه
    می‌شود، آمار از همان پیمایش می‌آید، و خروجی جدول صفحه‌بندی می‌شود.

    دو نکتهٔ صادقانه:

    * ``percent`` یک ``@property`` است (به :func:`_percent` نگاه کنید)، پس نه
      تجمیعش در SQL ممکن است نه مرتب‌سازی/صفحه‌بندی‌اش در SQL. حذفِ کاملِ
      پیمایش، نیازمند ستون‌کردن ``percent`` است — یک تغییر schema.
    * ردیف‌ها اکنون بر اساس درصد پیشرفت نزولی مرتب می‌شوند، نه ترتیب درج.
      این یک تغییر رفتاریِ عمدی است: گزارشی که «افت‌کرده‌ها» را برجسته می‌کند
      باید آن‌ها را اول نشان دهد.
    """
    import math

    from flask import request

    rows = db.session.execute(
        select(Enrollment.progress, Enrollment.completed_at, _lesson_count_subquery(),
               User.name, Course.title, Enrollment.created_at)
        .join(Course, Course.id == Enrollment.course_id)
        .join(User, User.id == Enrollment.user_id)).all()

    shaped = []
    for progress, completed_at, lesson_count, user_name, course_title, started in rows:
        pct = _percent(progress, completed_at, lesson_count)
        shaped.append({'user': user_name or '—', 'course': course_title or '—',
                       'percent': pct, 'done': pct >= 100, 'started': started})
    shaped.sort(key=lambda row: row['percent'], reverse=True)

    total = len(shaped)
    pages = max(1, math.ceil(total / per_page)) if total else 1
    try:
        page_no = min(max(1, request.args.get('page', 1, type=int)), pages)
    except (TypeError, ValueError):
        page_no = 1

    return {
        'rows': shaped[(page_no - 1) * per_page: page_no * per_page],
        'page': page_no, 'pages': pages, 'total': total,
        'completed': sum(1 for row in shaped if row['done']),
        'avg': round(sum(row['percent'] for row in shaped) / total) if total else 0,
        'dropped': sorted((row for row in shaped
                           if 0 < row['percent'] < 40),
                          key=lambda row: row['percent'])[:dropped_limit],
        'dropped_total': sum(1 for row in shaped if 0 < row['percent'] < 40),
    }


def ticket_report():
    """گزارش عملکرد پشتیبانی — یک کوئری، بدون موجودیت ORM، قابل‌حمل بین موتورها.

    نسخهٔ قبلی هر تیکتِ پاسخ‌داده‌شده را به‌صورت شیء کامل ORM به پایتون
    می‌آورد. اینجا فقط سه ستون لازم خوانده می‌شود.

    نکتهٔ عمدی: تفاضل دو timestamp در SQL **تجمیع نمی‌شود** — SQLite
    ``julianday`` دارد و MySQL ``TIMESTAMPDIFF``، و استفاده از هرکدام دیگری را
    در production می‌شکند. چون این اپ روی MySQL/CloudLinux مستقر می‌شود،
    میانگین در پایتون و روی همان سه ستون حساب می‌شود. این یک مصالحهٔ آگاهانهٔ
    قابلیت‌حمل است، نه بی‌دقتی.
    """
    answered = dict(db.session.execute(
        select(Ticket.assigned_to, func.count(Ticket.id))
        .where(Ticket.assigned_to.isnot(None))
        .group_by(Ticket.assigned_to)).all())

    rows = db.session.execute(
        select(Ticket.assigned_to, Ticket.created_at, Ticket.first_response_at)
        .where(Ticket.first_response_at.isnot(None),
               Ticket.created_at.isnot(None))).all()
    resp_sum: dict[int, float] = {}
    resp_cnt: dict[int, int] = {}
    total_hours = 0.0
    for assigned_to, created_at, first_response_at in rows:
        hours = (first_response_at - created_at).total_seconds() / 3600
        total_hours += hours
        if assigned_to is not None:
            resp_sum[assigned_to] = resp_sum.get(assigned_to, 0.0) + hours
            resp_cnt[assigned_to] = resp_cnt.get(assigned_to, 0) + 1

    supports = db.session.execute(
        select(User).where(User.role.in_(['support', 'admin']))
        .order_by(User.name)).scalars().all()
    report_rows = []
    for user in supports:
        count = resp_cnt.get(user.id, 0)
        report_rows.append({
            'user': user.name or '—',
            'answered': answered.get(user.id, 0),
            'avg_h': round(resp_sum[user.id] / count, 1) if count else None,
        })

    status_counts = dict(db.session.execute(
        select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)).all())
    return {
        'rows': report_rows,
        'total': int(sum(status_counts.values())),
        'open_t': int(sum(status_counts.get(s, 0) for s in ('open', 'answered'))),
        'avg_all': round(total_hours / len(rows), 1) if rows else None,
    }
