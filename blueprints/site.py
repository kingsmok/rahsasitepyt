# -*- coding: utf-8 -*-
"""صفحات عمومی سایت"""
from flask import Blueprint, render_template, request, abort, redirect, url_for, flash, g, session
import re
import json
from datetime import timedelta
from sqlalchemy import or_

_FA_MAP = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')

def fa_num2(n):
    return str(n).translate(_FA_MAP)
from sqlalchemy.orm import joinedload
from models import db, Course, Category, User, BlogPost, Review, Favorite, ContactMessage, NewsletterEmail, Section, Enrollment, utcnow
from validators import log_exc as _lexc
from validators import safe_referrer

site_bp = Blueprint('site', __name__)


def _pagination(page, per_page, query):
    total = query.count()
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, page, pages, total


# ---------------------------------------------------------------- خانه
class _DesignPage:
    """شبیه‌ساز شیء Page برای نمایش طرح‌های آماده صفحه اصلی"""
    def __init__(self, title, settings, rows):
        self.title = title
        self._settings = settings or {}
        self._rows = rows or []
        self.is_published = True

    def rows(self):
        return self._rows

    def settings(self):
        return self._settings


@site_bp.route('/')
def index():
    from designs import HOME_DESIGNS
    from models import Page as _Pg
    # پارامتر پیش‌نمایش فقط برای مدیر واردشده پذیرفته می‌شود.
    is_admin = bool(g.user and g.user.is_admin)
    preview_design = request.args.get('design') if is_admin else None
    # پیش‌نمایش زندهٔ ویرایشگر: مدیر می‌تواند صفحهٔ اصلیِ هنوز منتشرنشده را ببیند
    is_preview = request.args.get('preview') is not None and is_admin
    design = preview_design or g.settings.get('home_design', '1')
    # انتخاب دستی «صفحه اصلی» در تنظیمات — هر صفحه‌ای از صفحه‌ساز می‌تواند
    # صفحه اصلی سایت باشد (تنظیم home_page_slug)
    hp_slug = (g.settings.get('home_page_slug') or '').strip()
    if hp_slug:
        chosen = _Pg.query.filter_by(slug=hp_slug).first()
        if chosen and (chosen.is_published or is_preview) and chosen.rows():
            g.page_settings = chosen.settings()
            g.page_custom_header = chosen.custom_header
            g.page_custom_footer = chosen.custom_footer
            return render_template('builder/public.html', page=chosen)
    hp = getattr(g, 'pages', {}).get('home')
    if hp is None and (design == 'builder' or is_preview):
        hp = _Pg.query.filter_by(ptype='home').first()
    # fallback: اگر صفحه home در builder خالی باشد → طرح پیش‌فرض (جلوگیری از صفحه خالی)
    if hp and hp.is_published and not hp.rows() and not is_preview:
        hp = None
        design = '1'
    if hp and not hp.is_published and not is_preview:
        hp = None
    # اگر «صفحه صفحه‌ساز» انتخاب شده یا طرح نامعتبر است و صفحه builder موجود است
    if (design == 'builder' or is_preview) and hp and (hp.is_published or is_preview) and hp.rows():
        g.page_settings = hp.settings()
        g.page_custom_header = hp.custom_header
        g.page_custom_footer = hp.custom_footer
        return render_template('builder/public.html', page=hp)
    if design not in HOME_DESIGNS:
        design = '1'
    d = HOME_DESIGNS[design]
    dp = _DesignPage(d['title'], d['settings'], d['rows'])
    g.page_settings = dp.settings()
    return render_template('builder/public.html', page=dp)


# ---------------------------------------------------------------- دوره‌ها
@site_bp.route('/courses')
def courses():
    page = request.args.get('page', 1, type=int)
    # سئو: page=1 و صفحهبندی → ریدایرکت به نسخه بدون پارامتر (جلوگیری از محتوای تکراری)
    if page <= 1 and 'page' in request.args:
        qs = {k: v for k, v in request.args.items() if k != 'page'}
        return redirect(url_for('site.courses', **qs))
    per_page = request.args.get('per', 9, type=int)
    q = request.args.get('q', '').strip()
    cat = request.args.get('cat', '').strip()
    level = request.args.get('level', '').strip()
    price = request.args.get('price', '').strip()
    sort = request.args.get('sort', 'newest')

    from builder_sections import (
        find_builder_page, listing_filters_active, render_builder_page,
    )
    if not listing_filters_active(
            'q', 'cat', 'level', 'price', 'sort', 'per',
            ignore_defaults={'sort': 'newest'}):
        bp = find_builder_page('courses')
        if bp:
            return render_builder_page(bp)

    from sqlalchemy.orm import selectinload as _sil
    query = Course.query.options(joinedload(Course.category), joinedload(Course.teacher),
                                 _sil(Course.sections).selectinload(Section.lessons)) \
        .filter_by(status='published')
    if q:
        like = f'%{q}%'
        query = query.filter(or_(Course.title.ilike(like), Course.subtitle.ilike(like),
                                 Course.tags.ilike(like), Course.description.ilike(like)))
    if cat:
        c = Category.query.filter_by(slug=cat).first()
        if c:
            query = query.filter(Course.category_id == c.id)
        else:
            query = query.filter(Course.id == 0)
    if level:
        query = query.filter(Course.level == level)
    if price == 'free':
        query = query.filter(Course.discount_price == 0, Course.price == 0)
    elif price == 'paid':
        query = query.filter(or_(Course.discount_price > 0, Course.price > 0))

    # «ارزان‌ترین/گران‌ترین» باید بر اساس قیمت نهایی مؤثر مرتب شود، نه صرفاً
    # ستون discount_price: دورهٔ بدون تخفیف مقدار discount_price=0 دارد و قبلاً
    # به‌اشتباه ارزان‌تر از همهٔ دوره‌های تخفیف‌دار (حتی گران‌تر) دیده می‌شد.
    from sqlalchemy import case, and_
    _final_price = case(
        (and_(Course.discount_price > 0, Course.discount_price < Course.price),
         Course.discount_price),
        else_=Course.price,
    )
    sort_map = {
        'newest': Course.created_at.desc(),
        'oldest': Course.created_at.asc(),
        'cheap': _final_price.asc(),
        'expensive': _final_price.desc(),
        'popular': Course.views.desc(),
        'rating': Course.id.desc(),
    }
    query = query.order_by(sort_map.get(sort, Course.created_at.desc()))

    items, page, pages, total = _pagination(page, per_page, query)
    # آمار تجمیعی دوره‌ها: تعداد نظر + میانگین امتیاز + تعداد دانشجو
    # ⚠️ قبلاً همه نظرات و ثبت‌نام‌های هر دوره در پایتون بارگذاری می‌شد (هزاران ردیف!)
    _ids = [c.id for c in items]
    if _ids:
        try:
            _rev_rows = db.session.query(Review.course_id,
                                         db.func.count(Review.id),
                                         db.func.avg(Review.rating)) \
                .filter(Review.course_id.in_(_ids)).group_by(Review.course_id).all()
            _rev_map = {r[0]: (r[1], round(float(r[2] or 0), 1)) for r in _rev_rows}
            _enr_rows = db.session.query(Enrollment.course_id, db.func.count(Enrollment.id)) \
                .filter(Enrollment.course_id.in_(_ids)).group_by(Enrollment.course_id).all()
            _enr_map = dict(_enr_rows)
            for _c in items:
                _rc, _ra = _rev_map.get(_c.id, (0, 0))
                _c._agg_review_count = _rc
                _c._agg_rating = _ra
                _c._agg_students = _enr_map.get(_c.id, 0)
        except Exception:
            _lexc('site.py')
    categories = Category.query.join(Course, Course.category_id == Category.id) \
        .filter(Course.status == 'published').distinct().order_by(Category.sort).all()
    # متای سئوی پویا برای دسته‌بندی‌ها (لندینگ دسته)
    cat_obj = Category.query.filter_by(slug=cat).first() if cat else None
    if cat_obj:
        from models import SeoMeta
        # SeoMeta اختصاصی با مسیر کامل (شامل پارامتر cat) اگر ساخته شده باشد مقدم است
        meta = SeoMeta.query.filter_by(path=request.full_path.rstrip('&')).first() or \
               SeoMeta.query.filter_by(path=request.path + '?' + request.query_string.decode('utf-8')).first()
        n_items = fa_num2(len(items))
        if not meta or not meta.title:
            g.seo['title'] = f"دوره‌های {cat_obj.name} — {g.settings.get('site_name', 'آکادمی آنلاین')}"
        if not meta or not meta.description:
            g.seo['description'] = f"فهرست {n_items} دوره منتشرشده در دسته {cat_obj.name}؛ سرفصل، مدرس، مدت و قیمت هر دوره را بررسی و مقایسه کنید."
        elif meta:
            g.seo['title'] = meta.title or g.seo['title']
            g.seo['description'] = meta.description or g.seo['description']
    return render_template('courses.html', courses=items, page=page, pages=pages, total=total,
                           categories=categories, q=q, cat=cat, level=level, price=price, sort=sort,
                           cat_obj=cat_obj)


# ---------------------------------------------------------------- جزئیات دوره
def _find_course(slug):
    """دوره با slug یا شناسهٔ عددی. پیش‌نویس فقط برای مدیر/مدرس همان دوره."""
    from urllib.parse import unquote
    from models import make_slug
    value = unquote(unquote(slug or '')).strip().strip('/')
    if not value:
        return None
    value = value.replace('+', '-').replace(' ', '-')
    candidates = []
    for cand in (value, make_slug(value, fallback='')):
        if cand and cand not in candidates:
            candidates.append(cand)
    course = None
    for cand in candidates:
        course = Course.query.filter_by(slug=cand).first()
        if course:
            break
    if course is None and value.isdigit():
        course = Course.query.filter_by(id=int(value)).first()
    if course is None:
        return None
    if course.status == 'published':
        return course
    user = getattr(g, 'user', None)
    if user and (getattr(user, 'is_admin', False) or course.teacher_id == user.id):
        return course
    return None


@site_bp.route('/c/<int:cid>')
def course_by_id(cid):
    """آدرس پایدار با شناسه — ضد 404 اسلاگ فارسی روی برخی هاست‌ها."""
    course = db.session.get(Course, cid)
    if course is None:
        abort(404)
    if course.status != 'published':
        user = getattr(g, 'user', None)
        if not (user and (getattr(user, 'is_admin', False) or course.teacher_id == user.id)):
            abort(404)
    if course.slug:
        return redirect(url_for('site.course_detail', slug=course.slug), code=301)
    abort(404)


@site_bp.route('/course/<path:slug>')
def course_detail(slug):
    course = _find_course(slug)
    if course is None:
        abort(404)
    # لینک با شناسهٔ عددی (قدیمی/اشتراک‌گذاری‌شده) → ریدایرکت دائمی به آدرس کانونی
    if str(slug).strip().isdigit() and str(slug).strip() != str(course.slug):
        return redirect(url_for('site.course_detail', slug=course.slug), code=301)
    course = (Course.query.options(joinedload(Course.category), joinedload(Course.teacher),
                                   joinedload(Course.sections).joinedload(Section.lessons))
              .filter_by(id=course.id).first())
    course.views = (course.views or 0) + 1
    db.session.commit()
    enrolled = bool(g.user and any(e.course_id == course.id for e in g.user.enrollments))
    # آزمون و ارسال تمرین تجربهٔ دانشجو است؛ مدیر/مدرس از پنل تخصصی خود
    # مدیریت می‌کنند و در صفحه فروش با لینک منتهی به 403 مواجه نمی‌شوند.
    can_access_coursework = enrolled
    is_fav = bool(g.user and Favorite.query.filter_by(user_id=g.user.id, course_id=course.id).first())
    related = Course.query.filter(Course.category_id == course.category_id,
                                  Course.id != course.id, Course.status == 'published').limit(3).all()
    # اگر در همان دسته دوره دیگری نبود، از دوره‌های دیگر (هم‌تگ یا محبوب) پیشنهاد بده
    if not related:
        related = Course.query.filter(Course.id != course.id, Course.status == 'published') \
            .order_by(Course.views.desc()).limit(3).all()
    # محاسبهٔ یکجا آمار دوره + دوره‌های مرتبط (حذف N+1)
    from models import annotate_course_stats
    annotate_course_stats([course] + list(related))
    reviews = (Review.query.options(joinedload(Review.user))
               .filter_by(course_id=course.id, is_approved=True)
               .order_by(Review.created_at.desc()).all())
    # قالب داینامیک: اگر «قالب صفحه دوره» با صفحه‌ساز ساخته شده باشد
    from models import Page
    tp = Page.query.filter_by(ptype='course').first()
    if tp and tp.is_published and tp.rows():
        g.current_course = course
        g.page_settings = tp.settings()
        return render_template('builder/public.html', page=tp)
    # ─────────────── سئو و اسکیمای خودکار (شبیه Rank Math) + بازنویسی دستی ───────────────
    from seo_service import course_seo, ensure_meta
    base_url = request.host_url.rstrip('/')
    # رکورد متا این مسیر همیشه در داشبورد سئو قابل ویرایش است (فقط اگر نباشد ساخته می‌شود)
    ensure_meta('/course/' + course.slug)
    auto = course_seo(course, base_url)
    g.seo.update(auto)
    # کلمات کلیدی LSI تکمیلی بر اساس دسته
    if course.category and course.category.name != 'برنامه‌نویسی':
        lsi = [course.category.name, course.title] + g.seo.get('keywords', '').split(', ')[:3]
        g.seo['keywords'] = ', '.join(lsi)
    # مقالات مرتبط برای لینک‌سازی داخلی
    from models import BlogPost as _BlogPost
    blog_posts = _BlogPost.query.filter_by(published=True).order_by(_BlogPost.created_at.desc()).limit(3).all()
    done_ids = set()
    if g.user:
        en = next((e for e in g.user.enrollments if e.course_id == course.id), None)
        if en:
            done_ids = set(en.progress_list())
    intro_kind, intro_id = 'none', ''
    try:
        from validators import detect_video
        intro_kind, intro_id = detect_video(course.intro_video or '')
    except Exception:
        _lexc('blueprints/site.py')
    return render_template('course_detail.html', course=course, related=related,
                           reviews=reviews, enrolled=enrolled, is_fav=is_fav,
                           can_access_coursework=can_access_coursework,
                           done_ids=done_ids, blog_posts=blog_posts,
                           intro_kind=intro_kind, intro_id=intro_id)


@site_bp.route('/course/<slug>/review', methods=['POST'])
def add_review(slug):
    if not g.user:
        flash('برای ثبت نظر ابتدا وارد شوید.', 'error')
        return redirect(url_for('auth.login'))
    course = _find_course(slug)
    if course is None:
        abort(404)
    rating = request.form.get('rating', 5, type=int)
    from validators import clamp_field
    comment = clamp_field(request.form.get('comment'), 'comment')
    if not comment:
        flash('متن نظر را وارد کنید.', 'error')
        return redirect(url_for('site.course_detail', slug=slug))
    if not any(e.course_id == course.id for e in g.user.enrollments):
        flash('فقط دانشجویان دوره می‌توانند نظر ثبت کنند.', 'error')
        return redirect(url_for('site.course_detail', slug=slug))
    existing = Review.query.filter_by(course_id=course.id, user_id=g.user.id).first()
    from content_filter import moderate_text
    from models import Notification
    ok_c, comment, reason = moderate_text(comment, 2000)
    if not ok_c:
        flash(reason or 'متن نظر مجاز نیست.', 'error')
        return redirect(url_for('site.course_detail', slug=slug) + '#reviews')
    if existing:
        existing.rating = max(1, min(5, rating))
        existing.comment = comment
        existing.is_approved = False
    else:
        db.session.add(Review(course_id=course.id, user_id=g.user.id,
                              rating=max(1, min(5, rating)), comment=comment,
                              is_approved=False))
    try:
        Notification.notify_staff('نظر دوره در انتظار تایید',
                                  f'{g.user.name}: {course.title}',
                                  '⭐', '/admin/reviews')
    except Exception:
        _lexc('blueprints/site.py')
    db.session.commit()
    flash('نظر شما ثبت شد و پس از تایید مدیر نمایش داده می‌شود.', 'success')
    return redirect(url_for('site.course_detail', slug=slug) + '#reviews')


# ---------------------------------------------------------------- صفحه سفارشی ساخته‌شده با صفحه‌ساز
@site_bp.route('/page/<slug>')
def custom_page(slug):
    from models import Page
    page = Page.query.filter_by(slug=slug, ptype='page').first()
    if page:
        g.page_custom_header = page.custom_header
        g.page_custom_footer = page.custom_footer
    # پیش‌نمایش زندهٔ ویرایشگر: فقط مدیر می‌تواند صفحهٔ منتشرنشده را ببیند
    is_preview = request.args.get('preview') is not None
    is_admin = bool(g.user and getattr(g.user, 'is_admin', False))
    if not page or (not page.is_published and not (is_preview and is_admin)):
        abort(404)
    if not page.rows():
        # صفحه ساخته شده ولی هنوز محتوایی ندارد. قبلاً اینجا ۴۰۴ می‌داد و
        # مدیر گمان می‌کرد صفحه ساخته نشده؛ حالا برای مدیر پیام راهنما و
        # لینک ویرایش نشان می‌دهیم و برای بازدیدکننده ۴۰۴ می‌ماند.
        if not (g.user and getattr(g.user, 'is_admin', False)):
            abort(404)
    g.page_settings = page.settings()
    return render_template('builder/public.html', page=page)



# ---------------------------------------------------------------- صفحات قانونی
def _builder_page(slug):
    """نسخهٔ صفحه‌ساز یک صفحهٔ ثابت (درباره/تماس/قوانین/...).

    اگر مدیر برای این slug یک صفحهٔ منتشرشده با محتوا در صفحه‌ساز ساخته باشد،
    همان صفحه رندر می‌شود؛ وگرنه None برمی‌گردد تا قالب ثابت قبلی نمایش داده شود.
    پیش‌نمایش مدیر با ?preview هم پذیرفته می‌شود.
    """
    from builder_sections import find_builder_page
    return find_builder_page(slug)


def _render_builder_page(page):
    """رندر مشترک نسخهٔ صفحه‌ساز برای صفحات ثابت سایت"""
    from builder_sections import render_builder_page
    return render_builder_page(page)


@site_bp.route('/terms')
def terms():
    bp = _builder_page('terms')
    if bp:
        return _render_builder_page(bp)
    try:
        refund_days = max(0, int(g.settings.get('refund_days') or 0))
    except (TypeError, ValueError):
        refund_days = 0
    sections = [
        ('۱. پذیرش قوانین', 'با ثبت‌نام و استفاده از خدمات سایت، قوانین منتشرشده در این صفحه را می‌پذیرید.'),
        ('۲. حساب کاربری', 'مسئولیت حفظ رمز عبور و فعالیت‌های حساب بر عهده کاربر است. فقط اطلاعات لازم برای ارائه خدمات را وارد کنید.'),
        ('۳. خرید و پرداخت', 'دسترسی خرید پس از تایید قطعی تراکنش فعال می‌شود. تراکنش ناموفق به‌عنوان خرید موفق ثبت نخواهد شد.'),
        ('۴. حق استفاده از محتوا', 'محتوای آموزشی صرفاً برای استفاده شخصی خریدار است و انتشار یا فروش مجدد آن مجاز نیست.'),
    ]
    if refund_days:
        sections.append(('۵. بازگشت وجه',
                         f'مهلت ثبت درخواست بازگشت وجه {refund_days} روز پس از خرید است. شرایط هر درخواست توسط پشتیبانی و مطابق میزان استفاده از محتوا بررسی می‌شود.'))
    else:
        sections.append(('۵. بازگشت وجه',
                         'در حال حاضر مهلت عمومی بازگشت وجه تعریف نشده است. پیش از پرداخت، توضیحات و پیش‌نیازهای دوره را بررسی کنید و در صورت سوال با پشتیبانی تماس بگیرید.'))
    sections.append(('۶. گواهی پایان دوره',
                     'گواهی‌های صادرشده دارای کد رهگیری منحصربه‌فرد و از صفحه استعلام سایت قابل بررسی هستند.'))
    return render_template('legal.html', page_title='قوانین و مقررات',
        page_icon='📜', intro='لطفاً پیش از استفاده از خدمات، قوانین زیر را مطالعه کنید.',
        sections=sections)


@site_bp.route('/privacy')
def privacy():
    bp = _builder_page('privacy')
    if bp:
        return _render_builder_page(bp)
    return render_template('legal.html', page_title='حریم خصوصی',
        page_icon='🔒', intro='حفظ حریم خصوصی شما برای ما اهمیت بالایی دارد. این خط‌مشی نحوه جمع‌آوری و استفاده از اطلاعات شما را شرح می‌دهد.',
        sections=[
            ('۱. اطلاعات جمع‌آوری‌شده', 'نام، ایمیل و اطلاعات لازم برای حساب و سفارش ذخیره می‌شود. شماره تماس و کد ملی فقط در قابلیت‌هایی که به آن نیاز دارند و در صورت ورود کاربر دریافت می‌شوند.'),
            ('۲. استفاده از اطلاعات', 'اطلاعات برای مدیریت حساب، ارائه محتوای خریداری‌شده، پردازش سفارش، پشتیبانی و اطلاع‌رسانی‌های انتخاب‌شده استفاده می‌شود.'),
            ('۳. واترمارک ویدیو', 'اگر واترمارک توسط مدیر فعال باشد، بخشی از اطلاعات حساب به‌صورت ماسک‌شده روی محتوای ویدیویی نمایش داده می‌شود.'),
            ('۴. ارائه‌دهندگان خدمت', 'برای پرداخت یا ارسال پیام، اطلاعات ضروری درخواست ممکن است به درگاه پرداخت یا سرویس پیامک انتخاب‌شده منتقل شود. ارائه اطلاعات در موارد الزام قانونی نیز ممکن است انجام شود.'),
            ('۵. امنیت داده‌ها', 'رمزهای عبور به‌صورت هش‌شده نگهداری می‌شوند و کنترل دسترسی و سیاست‌های امنیتی برای کاهش دسترسی غیرمجاز اعمال می‌شود.'),
            ('۶. درخواست حذف یا اصلاح', 'می‌توانید از طریق تیکت پشتیبانی درخواست اصلاح یا حذف اطلاعات را ثبت کنید. انجام درخواست با توجه به الزامات قانونی و سوابق مالی بررسی می‌شود.'),
        ])


# ---------------------------------------------------------------- حالت تعمیرات
@site_bp.route('/maintenance')
def maintenance():
    from flask import render_template
    unavailable = (g.settings.get('maintenance') == '1' or
                   g.settings.get('site_active', '1') != '1')
    return render_template('maintenance.html',
                           prelaunch=g.settings.get('site_active', '1') != '1'), \
        503 if unavailable else 200



# ---------------------------------------------------------------- SEO: sitemap و robots
@site_bp.route('/sitemap.xml')
def sitemap():
    from flask import Response
    from models import Page
    from marketplace import _xml_escape as _xe
    base = request.host_url.rstrip('/')
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
    xml += 'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">'
    # صفحات اصلی
    xml += f'<url><loc>{base}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>'
    for u in ['/courses', '/teachers', '/blog', '/about', '/faq', '/contact',
              '/terms', '/privacy', '/become-teacher', '/learning-paths',
              '/consultation', '/products', '/success-stories',
              '/verify-certificate', '/bundles']:
        xml += f'<url><loc>{base}{u}</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>'
    # دوره‌ها با تصویر و اولویت بالا
    for c in Course.query.filter_by(status='published').all():
        xml += f'<url><loc>{_xe(base)}/course/{_xe(c.slug)}</loc><changefreq>monthly</changefreq><priority>0.9</priority>'
        image_url = c.image_url if c.image_url.startswith('https://') else base + c.image_url
        xml += f'<image:image><image:loc>{_xe(image_url)}</image:loc><image:title>{_xe(c.title)}</image:title></image:image>'
        xml += '</url>'
    # مقالات
    for p in BlogPost.query.filter_by(published=True).all():
        xml += f'<url><loc>{_xe(base)}/blog/{_xe(p.slug)}</loc><lastmod>{p.created_at.strftime("%Y-%m-%d")}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority>'
        if p.image:
            xml += f'<image:image><image:loc>{_xe(base)}/static/img/{_xe(p.image)}</image:loc></image:image>'
        xml += '</url>'
    # محصولات فروشگاه
    from models import Product as _Prod
    for pr in _Prod.query.filter(_Prod.stock > 0, _Prod.is_active == True).all():
        xml += f'<url><loc>{_xe(base)}/product/{_xe(pr.slug)}</loc><changefreq>weekly</changefreq><priority>0.6</priority></url>'
    # اساتید
    for t in User.query.filter(User.role == 'teacher', User.is_active == True).all():
        xml += f'<url><loc>{_xe(base)}/teacher/{t.id}</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>'
    # صفحات صفحه‌ساز
    for pg in Page.query.filter_by(ptype='page', is_published=True).all():
        xml += f'<url><loc>{_xe(base)}/page/{_xe(pg.slug)}</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>'
    xml += '</urlset>'
    resp = Response(xml, mimetype='application/xml')
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    return resp


@site_bp.route('/robots.txt')
def robots():
    from flask import Response
    base = request.host_url.rstrip('/')
    txt = (
        f"User-agent: *\n"
        f"Allow: /\n"
        f"Disallow: /admin\n"
        f"Disallow: /builder\n"
        f"Disallow: /dashboard\n"
        f"Disallow: /cart\n"
        f"Disallow: /checkout\n"
        f"Disallow: /pay\n"
        f"Disallow: /auth\n"
        f"Disallow: /api\n"
        f"Disallow: /install\n"
        f"Disallow: /license\n"
        f"Disallow: /wallet\n"
        f"Disallow: /uploads\n"
        f"Disallow: /maintenance\nDisallow: /health\nDisallow: /static/uploads\n"
        f"\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return Response(txt, mimetype='text/plain')


# ---------------------------------------------------------------- اساتید
@site_bp.route('/teachers')
def teachers():
    bp = _builder_page('teachers')
    if bp:
        return _render_builder_page(bp)
    from sqlalchemy import func as _f
    from models import Review, Course, Enrollment
    # ⚠️ قبلاً همه ثبت‌نام‌های هر دوره بارگذاری می‌شد (هزاران ردیف) — حالا فقط شمارش
    teachers = User.query.filter(User.role == 'teacher', User.is_active == True).all()
    # امتیاز هر استاد با یک کوئری تجمیعی (JOIN Course + Review)
    tids = [t.id for t in teachers]
    ratings = {}
    if tids:
        rows = db.session.query(Course.teacher_id, _f.avg(Review.rating), _f.count(Review.id)) \
            .join(Review, Review.course_id == Course.id) \
            .filter(Course.teacher_id.in_(tids), Course.status == 'published',
                    Review.is_approved == True) \
            .group_by(Course.teacher_id).all()
        for tid, avg, cnt in rows:
            ratings[tid] = round(avg, 1) if avg else None
    # تعداد دانشجو هر استاد — یک کوئری تجمیعی دیگر
    students = {}
    if tids:
        srows = db.session.query(Course.teacher_id, _f.count(Enrollment.id)) \
            .join(Enrollment, Enrollment.course_id == Course.id) \
            .filter(Course.teacher_id.in_(tids), Course.status == 'published') \
            .group_by(Course.teacher_id).all()
        students = {tid: n for tid, n in srows}
    # تعداد دورهٔ منتشر هر استاد — یک کوئری به‌جای بارگذاری رابطه
    course_counts = {}
    if tids:
        crows = db.session.query(Course.teacher_id, _f.count(Course.id)) \
            .filter(Course.teacher_id.in_(tids), Course.status == 'published') \
            .group_by(Course.teacher_id).all()
        course_counts = {tid: n for tid, n in crows}
    return render_template('teachers.html', teachers=teachers, ratings=ratings,
                           teacher_students=students, teacher_courses=course_counts)


@site_bp.route('/teacher/<int:uid>')
def teacher_detail(uid):
    # مدرسان می‌توانند نقش teacher یا admin داشته باشند (در فرم دوره هر دو
    # قابل انتخاب‌اند)؛ فیلتر قبلی فقط role='teacher' بود و پروفایل مدرسانی
    # که نقش admin داشتند را 404 می‌کرد.
    teacher = User.query.filter(User.id == uid,
                                User.role.in_(('teacher', 'admin')),
                                User.is_active == True).first_or_404()
    courses = (Course.query.options(joinedload(Course.category))
               .filter_by(teacher_id=uid, status='published').all())
    # ── سئو و اسکیمای خودکار Person (شبیه Rank Math) + بازنویسی دستی ──
    from seo_service import teacher_seo, ensure_meta as _ensure_teacher_meta
    _ensure_teacher_meta('/teacher/' + str(uid))
    g.seo.update(teacher_seo(teacher, request.host_url.rstrip('/')))
    # قالب داینامیک: اگر «قالب صفحه مدرس» ساخته شده باشد
    from models import Page, MeetingBooking
    available_meetings = MeetingBooking.query.filter_by(teacher_id=uid, status='available').all()
    tp = Page.query.filter_by(ptype='teacher').first()
    if tp and tp.is_published and tp.rows():
        g.current_teacher = teacher
        g.page_settings = tp.settings()
        return render_template('builder/public.html', page=tp)
    return render_template('teacher_detail.html', teacher=teacher, courses=courses, available_meetings=available_meetings)


# ---------------------------------------------------------------- وبلاگ
@site_bp.route('/blog')
def blog():
    page = request.args.get('page', 1, type=int)
    cat = request.args.get('cat', '').strip()
    from builder_sections import listing_filters_active
    if not listing_filters_active('cat'):
        bp = _builder_page('blog')
        if bp:
            return _render_builder_page(bp)
    query = BlogPost.query.options(db.joinedload(BlogPost.author)).filter_by(published=True)
    if cat:
        query = query.filter(BlogPost.category == cat)
    query = query.order_by(BlogPost.created_at.desc())
    items, page, pages, total = _pagination(page, 6, query)
    cats = db.session.query(BlogPost.category).distinct().all()
    return render_template('blog.html', posts=items, page=page, pages=pages, cats=[c[0] for c in cats], cat=cat)


@site_bp.route('/blog/<slug>', methods=['GET', 'POST'])
def blog_post(slug):
    from models import BlogComment, find_by_slug_or_id
    post = find_by_slug_or_id(BlogPost, slug, fallback='post')
    if post is None:
        abort(404)
    # پیش‌نویس فقط برای مدیر و نویسندهٔ همان مطلب قابل مشاهده است
    if not post.published:
        _u = getattr(g, 'user', None)
        _own = _u and getattr(post, 'author_id', None) == getattr(_u, 'id', None)
        if not (_u and (getattr(_u, 'is_admin', False) or _own)):
            abort(404)
    # اگر آدرس واردشده با اسلاگ رسمی فرق دارد، به آدرس درست منتقل شود (SEO)
    if post.slug and slug != post.slug:
        return redirect(url_for('site.blog_post', slug=post.slug), code=301)
    g.current_post = post
    if request.method == 'POST':
        from validators import clamp_field
        # ضد اسپم: honeypot خالی باشد (ربات‌ها پر می‌کنند) + محدودیت تعداد در هر IP
        if (request.form.get('website') or '').strip():
            return redirect(url_for('site.blog_post', slug=slug) + '#comments')
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
        # محدودیت نرخ از روی خودِ دیتابیس محاسبه می‌شود (شمارش دیدگاه‌های
        # همان IP در ۱۰ دقیقهٔ گذشته)؛ کلید کش درون‌حافظه‌ای لازم نیست.
        recent = BlogComment.query.filter(
            BlogComment.post_id == post.id,
            # ⚠️ حتماً از utcnow() پروژه استفاده شود، نه datetime.utcnow():
            # created_at با همان تابع پر می‌شود و باید مبنای زمانی یکسان
            # داشته باشند. ضمناً datetime.utcnow() در پایتون ۳.۱۲+ منسوخ
            # شده و در نسخه‌های بعدی حذف می‌شود.
            BlogComment.created_at >= utcnow() - timedelta(minutes=10),
            BlogComment.ip == client_ip).count()
        if recent >= 5:
            flash('تعداد دیدگاه‌ها زیاد است؛ چند دقیقه دیگر دوباره تلاش کنید.', 'error')
            return redirect(url_for('site.blog_post', slug=slug) + '#comments')
        name = clamp_field(request.form.get('name'), 'name')
        comment = clamp_field(request.form.get('comment'), 'comment')
        if name and comment:
            from content_filter import moderate_text
            ok_c, comment, reason = moderate_text(comment, 2000)
            if not ok_c:
                flash(reason or 'متن دیدگاه مجاز نیست.', 'error')
                return redirect(url_for('site.blog_post', slug=slug) + '#comments')
            # تأیید دستی فقط وقتی مدیر آن را روشن کرده باشد؛ در غیر این صورت
            # دیدگاه بلافاصله منتشر می‌شود (متن قبلاً از فیلتر لینک/فحش گذشته).
            needs_review = str(g.settings.get('blog_comment_moderation') or '0') == '1'
            db.session.add(BlogComment(post_id=post.id, name=name,
                                       comment=comment, ip=client_ip[:60],
                                       is_approved=not needs_review))
            try:
                from models import Notification
                Notification.notify_staff(
                    'دیدگاه وبلاگ در انتظار تایید' if needs_review else 'دیدگاه جدید وبلاگ',
                    f'{name}: {post.title}',
                    '💬', '/admin/reviews')
            except Exception:
                _lexc('blueprints/site.py')
            db.session.commit()
            flash('دیدگاه شما ثبت شد و پس از تایید مدیر نمایش داده می‌شود.' if needs_review
                  else 'دیدگاه شما ثبت شد. سپاس از همراهی 🙏', 'success')
        else:
            flash('نام و متن دیدگاه الزامی است.', 'error')
        return redirect(url_for('site.blog_post', slug=slug) + '#comments')
    post.views = (post.views or 0) + 1
    db.session.commit()
    # ── سئو و اسکیمای خودکار Article (شبیه Rank Math) + بازنویسی دستی ──
    from seo_service import blog_seo, ensure_meta as _ensure_blog_meta
    _ensure_blog_meta('/blog/' + post.slug)
    g.seo.update(blog_seo(post, request.host_url.rstrip('/')))
    # اگر «صفحه پست» با صفحه‌ساز ساخته شده باشد، به جای قالب عادی نمایش بده
    from models import Page
    tp = Page.query.filter_by(ptype='post').first()
    if tp and tp.is_published and tp.rows():
        g.page_settings = tp.settings()
        return render_template('builder/public.html', page=tp)
    recent = BlogPost.query.filter(BlogPost.id != post.id, BlogPost.published == True) \
        .order_by(BlogPost.created_at.desc()).limit(4).all()
    # دوره پیشنهادی مرتبط با پست (بر اساس کلمه مشترک در عنوان یا پرفروش‌ترین)
    from models import Course
    related_course = None
    words = [w for w in re.split(r'[\s،,؟?\-]', post.title or '') if len(w) > 2]
    for w in words:
        related_course = Course.query.filter(Course.status == 'published',
                                             Course.title.like(f'%{w}%')).first()
        if related_course:
            break
    if not related_course:
        related_course = Course.query.filter_by(status='published') \
            .order_by(Course.views.desc(), Course.created_at.desc()).first()
    return render_template('blog_post.html', post=post, recent=recent,
                           related_course=related_course)


# ---------------------------------------------------------------- صفحات ثابت
@site_bp.route('/about')
def about():
    bp = _builder_page('about')
    if bp:
        return _render_builder_page(bp)
    from models import User as _U, Section as _S, Lesson as _L, Review as _RV
    teachers = _U.query.filter(_U.role.in_(['teacher', 'admin']), _U.is_active == True).count()
    total_courses = Course.query.filter_by(status='published').count()
    total_students = _U.query.filter_by(role='student', is_active=True).count()
    total_lessons = db.session.query(_L.id).join(_S, _S.id == _L.section_id) \
        .join(Course, Course.id == _S.course_id).filter(Course.status == 'published').count()
    total_hours = int(db.session.query(db.func.coalesce(db.func.sum(Course.duration_hours), 0))
                      .filter(Course.status == 'published').scalar() or 0)
    total_reviews = db.session.query(_RV.id).join(Course, Course.id == _RV.course_id) \
        .filter(_RV.is_approved == True, Course.status == 'published').count()
    _avg_rating = db.session.query(db.func.avg(_RV.rating)).join(Course, Course.id == _RV.course_id) \
        .filter(_RV.is_approved == True, Course.status == 'published').scalar() or 0
    total_satisfaction = round((_avg_rating or 0) / 5 * 100)
    preview_design = request.args.get('design') if (g.user and g.user.is_admin) else None
    design = preview_design or g.settings.get('about_design', '1')
    if design not in [str(i) for i in range(1, 6)]:
        design = '1'
    return render_template(f'about/design{design}.html', teachers=teachers,
                           total_courses=total_courses, total_students=total_students,
                           total_lessons=total_lessons, total_hours=total_hours,
                           total_reviews=total_reviews, total_satisfaction=total_satisfaction)


@site_bp.route('/faq')
def faq():
    bp = _builder_page('faq')
    if bp:
        return _render_builder_page(bp)
    import json as _json
    items = []
    raw = (g.settings or {}).get('faq_items') or ''
    if raw:
        try:
            items = _json.loads(raw)
        except Exception:
            items = []
    if not isinstance(items, list):
        items = []
    items = [x for x in items if isinstance(x, dict) and (x.get('q') or x.get('a'))]
    return render_template('faq.html', faq_items=items)


@site_bp.route('/learning-paths')
def learning_paths():
    """صفحه مسیرهای یادگیری — نقشه راه پیشنهادی دوره‌ها"""
    bp = _builder_page('learning-paths')
    if bp:
        return _render_builder_page(bp)
    from models import Category
    paths = []
    # مسیر ۱: برنامه‌نویسی وب (از صفر تا استخدام)
    web_cats = [c for c in Category.query.all() if c.slug in ('برنامه-نویسی', 'وب')]
    courses = []
    for c in web_cats:
        for cs in c.courses:
            if cs.status == 'published':
                courses.append(cs)
    # مرتب‌سازی: پایتون → Flask → Django → React → وردپرس
    order = {'پایتون': 0, 'Flask': 1, 'Django': 2, 'React': 3, 'وردپرس': 4}
    courses.sort(key=lambda x: next((order[k] for k in order if k in x.title), 9))
    paths.append({'id': 'web', 'icon': '💻', 'title': 'توسعه‌دهنده وب (از صفر تا استخدام)',
                  'desc': 'مسیر کامل برنامه‌نویسی وب: پایتون → فریم‌ورک → فرانت‌اند → پروژه واقعی',
                  'courses': courses[:6], 'color': '#2563eb'})

    # مسیر ۲: هوش مصنوعی و داده
    ai_cats = [c for c in Category.query.all() if c.slug in ('هوش-مصنوعی',)]
    ai = []
    for c in ai_cats:
        for cs in c.courses:
            if cs.status == 'published':
                ai.append(cs)
    paths.append({'id': 'ai', 'icon': '🤖', 'title': 'هوش مصنوعی و علم داده',
                  'desc': 'یادگیری ماشین با پایتون و مسیر داده‌محور',
                  'courses': ai[:6], 'color': '#7c3aed'})

    # مسیر ۳: طراحی محصول
    d_cats = [c for c in Category.query.all() if c.slug in ('طراحی',)]
    ds = []
    for c in d_cats:
        for cs in c.courses:
            if cs.status == 'published':
                ds.append(cs)
    paths.append({'id': 'design', 'icon': '🎨', 'title': 'طراح محصول (UI/UX)',
                  'desc': 'از اصول طراحی تا ابزارهای حرفه‌ای',
                  'courses': ds[:6], 'color': '#ea580c'})

    # مسیر ۴: کسب‌وکار دیجیتال
    b_cats = [c for c in Category.query.all() if c.slug in ('کسب-وکار', 'آفیس')]
    bs = []
    for c in b_cats:
        for cs in c.courses:
            if cs.status == 'published':
                bs.append(cs)
    paths.append({'id': 'biz', 'icon': '📈', 'title': 'کسب‌وکار دیجیتال و مهارت‌های اداری',
                  'desc': 'مارکتینگ، فروش آنلاین و بهره‌وری با ابزارهای آفیس',
                  'courses': bs[:6], 'color': '#059669'})

    g.seo['title'] = "مسیرهای یادگیری — نقشه راه دوره‌ها | آکادمی آنلاین"
    g.seo['description'] = "مسیر یادگیری قدم‌به‌قدم: برنامه‌نویسی وب، هوش مصنوعی، طراحی محصول و کسب‌وکار دیجیتال — بدانید بعد از هر دوره، کدام دوره را بگذرانید."
    return render_template('learning_paths.html', paths=paths)


@site_bp.route('/consultation', methods=['GET', 'POST'])
def consultation():
    """فرم درخواست مشاوره — ثبت و پیگیری لید."""
    if request.method == 'POST':
        from captcha import verify_captcha, verify_honeypot
        if not verify_honeypot() or not verify_captcha():
            flash('پاسخ سوال امنیتی اشتباه است.', 'error')
            return redirect(url_for('site.consultation'))
        from validators import clamp_field
        name = clamp_field(request.form.get('name'), 'name')
        phone = clamp_field(request.form.get('phone'), 'phone')
        goal = clamp_field(request.form.get('goal'), 'goal')
        if not name or not phone:
            flash('نام و شماره تماس الزامی است.', 'error')
        else:
            ptime = request.form.get('preferred_time', '')
            pdate = request.form.get('preferred_date', '')
            extra = ''
            if ptime or pdate:
                extra = f'\nزمان ترجیحی: {ptime} {pdate}'.strip()
            db.session.add(ContactMessage(name=name, email='',
                                          subject=f'📞 درخواست مشاوره — {goal or "عمومی"}',
                                          message=f'تلفن: {phone}\nهدف: {goal or "—"}{extra}'))
            db.session.commit()
            flash('درخواست شما ثبت شد. نتیجه بررسی از راه اطلاعات تماس ثبت‌شده اطلاع داده می‌شود. ✅', 'success')
            return redirect(url_for('site.consultation'))
    g.seo['title'] = "درخواست مشاوره انتخاب مسیر یادگیری | آکادمی آنلاین"
    g.seo['description'] = "فرم درخواست مشاوره برای بررسی دوره‌ها و انتخاب مسیر یادگیری؛ اطلاعات تماس و هدف خود را ثبت کنید."
    bp = _builder_page('consultation')
    if bp:
        return _render_builder_page(bp)
    return render_template('consultation.html')


@site_bp.route('/r/<code>')
def ref_landing(code):
    """لینک معرف — ذخیره کد و هدایت به ثبت‌نام"""
    session['ref_code'] = code.strip().upper()
    return redirect(url_for('auth.register'))


@site_bp.route('/verify-certificate', methods=['GET', 'POST'])
def verify_certificate():
    """استعلام عمومی گواهی — با کد رهگیری"""
    result = None
    code = ''
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        from models import Enrollment
        if not code.startswith('CRT-'):
            code = 'CRT-' + code
        # جستجو در گواهی‌های صادرشده — هم کد جدید (MD5) و هم کد قدیمی (SHA-1)
        from models import (certificate_code, certificate_code_legacy_md5,
                            certificate_code_legacy_sha1)
        # ابتدا بررسی گواهی‌های معتبر فعال
        for e in Enrollment.query.filter(Enrollment.completed_at.isnot(None)).all():
            c = e.course
            if not c or not e.user:
                continue
            cert_code = certificate_code(c.slug, e.user.email, e.id)
            accepted = {
                cert_code,
                certificate_code_legacy_md5(c.slug, e.user.email, e.id),
                certificate_code_legacy_sha1(c.slug, e.user.email, e.id),
            }
            if code in accepted:
                result = {'code': cert_code, 'user': e.user.name, 'course': c.title,
                          'date': e.completed_at, 'valid': True, 'revoked': False}
                break
        # اگر در گواهی‌های فعال نبود، بررسی گواهی‌های باطل‌شده
        if not result:
            for e in Enrollment.query.filter(Enrollment.revoked_at.isnot(None)).all():
                c = e.course
                if not c or not e.user:
                    continue
                cert_code = certificate_code(c.slug, e.user.email, e.id)
                accepted = {
                    cert_code,
                    certificate_code_legacy_md5(c.slug, e.user.email, e.id),
                    certificate_code_legacy_sha1(c.slug, e.user.email, e.id),
                }
                if code in accepted:
                    result = {'code': cert_code, 'user': e.user.name, 'course': c.title,
                              'date': e.revoked_at, 'valid': False, 'revoked': True}
                    break
        if not result:
            result = {'code': code, 'valid': False, 'revoked': False}
    g.seo['title'] = 'استعلام گواهینامه — آکادمی آنلاین'
    g.seo['description'] = 'با وارد کردن کد رهگیری گواهینامه، از صحت آن مطمئن شوید.'
    g.verify_result = result
    bp = _builder_page('verify-certificate')
    if bp:
        return _render_builder_page(bp)
    return render_template('verify_certificate.html', result=result, code=code)


@site_bp.route('/become-teacher', methods=['GET', 'POST'])
def become_teacher():
    """صفحه «مدرس شو» — ثبت درخواست تدریس"""
    if request.method == 'POST':
        from validators import clamp_field
        name = clamp_field(request.form.get('name'), 'name')
        email = clamp_field(request.form.get('email'), 'email')
        phone = clamp_field(request.form.get('phone'), 'phone')
        expertise = clamp_field(request.form.get('expertise'), 'default')
        sample = clamp_field(request.form.get('sample'), 'default')
        message = clamp_field(request.form.get('message'), 'message')
        from captcha import verify_captcha, verify_honeypot
        if not verify_honeypot():
            flash('درخواست شما ثبت نشد (خطای امنیتی).', 'error')
        elif not verify_captcha():
            flash('پاسخ سوال امنیتی اشتباه است.', 'error')
        elif not name or not expertise:
            flash('نام و تخصص شما الزامی است.', 'error')
        else:
            full = f"📚 درخواست مدرس شدن — تخصص: {expertise}"
            if phone:
                full += f" | تلفن: {phone}"
            if sample:
                full += f" | نمونه‌کار: {sample}"
            full += f"\n\n{message}"
            db.session.add(ContactMessage(name=name, email=email, subject=full, message=message or '—'))
            db.session.commit()
            flash('درخواست شما ثبت شد! کارشناسان ما برای هماهنگی با شما تماس می‌گیرند. 🎉', 'success')
            return redirect(url_for('site.become_teacher'))
    bp = _builder_page('become-teacher')
    if bp:
        return _render_builder_page(bp)
    return render_template('become_teacher.html')


@site_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        from captcha import verify_captcha, verify_honeypot
        if not verify_honeypot():
            flash('پیام شما ثبت نشد (خطای امنیتی).', 'error')
            return redirect(url_for('site.contact'))
        if not verify_captcha():
            flash('پاسخ سوال امنیتی اشتباه است. دوباره تلاش کنید.', 'error')
            return redirect(url_for('site.contact'))
        from validators import clamp_field, is_valid_phone
        name = clamp_field(request.form.get('name'), 'name')
        email = clamp_field(request.form.get('email'), 'email')
        phone = clamp_field(request.form.get('phone'), 'phone')
        subject = clamp_field(request.form.get('subject'), 'subject')
        message = clamp_field(request.form.get('message'), 'message')
        if not name or not message:
            flash('نام و متن پیام الزامی است.', 'error')
        else:
            # شماره تماس نامعتبر → ذخیره نشود تا گزارش‌ها درست بمانند
            if phone and not is_valid_phone(phone):
                phone = ''
            db.session.add(ContactMessage(name=name, email=email, phone=phone,
                                          subject=subject, message=message))
            try:
                from models import Notification
                Notification.notify_staff('پیام تماس جدید', f'{name}: {subject or "بدون موضوع"}',
                                          '✉️', '/admin/messages')
            except Exception:
                _lexc('blueprints/site.py')
            db.session.commit()
            flash('پیام شما با موفقیت ارسال شد. به زودی پاسخ می‌دهیم.', 'success')
            return redirect(url_for('site.contact'))
    bp = _builder_page('contact')
    if bp:
        return _render_builder_page(bp)
    preview_design = request.args.get('design') if (g.user and g.user.is_admin) else None
    design = preview_design or g.settings.get('contact_design', '1')
    if design not in [str(i) for i in range(1, 6)]:
        design = '1'
    return render_template(f'contact/design{design}.html')



@site_bp.route('/form/<slug>', methods=['GET', 'POST'])
def custom_form(slug):
    """نمایش و ثبت فرم ساخته‌شده با فرم‌ساز"""
    from models import CustomForm, CustomFormEntry
    f = CustomForm.query.filter_by(slug=slug, is_active=True).first_or_404()
    if request.method == 'POST':
        data = {}
        for field in f.fields_list():
            from validators import clamp_field
            val = clamp_field(request.form.get(field['label']), 'default')
            if field.get('type') == 'file':
                up = request.files.get(field['label'])
                if up and up.filename:
                    import os, uuid
                    from validators import safe_filename
                    safe = safe_filename(up.filename or '')
                    if not safe:
                        flash('فرمت فایل مجاز نیست.', 'error')
                        return redirect(request.url)
                    from validators import file_content_is_safe
                    if not file_content_is_safe(up.stream, os.path.splitext(safe)[1].lower()):
                        flash('محتوای فایل ارسالی نامعتبر یا ناامن است.', 'error')
                        return redirect(request.url)
                    from uploads_helper import uploads_dir, uploads_url
                    up_dir = uploads_dir('forms')
                    fname = 'f_' + uuid.uuid4().hex[:8] + os.path.splitext(safe)[1]
                    up.save(os.path.join(up_dir, fname))
                    val = uploads_url('forms', fname)
            data[field['label']] = val
        db.session.add(CustomFormEntry(form_id=f.id,
                                       user_id=g.user.id if g.user else None,
                                       data=json.dumps(data, ensure_ascii=False)))
        db.session.commit()
        # اعلان به پیام‌رسان
        if f.notify_messenger:
            try:
                from messengers import send_message
                summary = ' | '.join(f'{k}: {str(v)[:40]}' for k, v in data.items() if v)
                send_message(f.notify_messenger, f'📥 فرم «{f.title}» ثبت شد\n{summary}', g.settings)
            except Exception:
                _lexc('blueprints/site.py')
        flash(f.success_msg or 'ثبت شد ✅', 'success')
        return redirect(url_for('site.custom_form', slug=slug))
    g.seo['title'] = f.title + ' — ' + (g.settings.get('site_name') or 'آکادمی آنلاین')
    return render_template('site_form.html', f=f)


@site_bp.route('/newsletter', methods=['POST'])
def newsletter():
    from captcha import verify_honeypot
    if not verify_honeypot():
        return redirect(url_for('site.index'))
    email = request.form.get('email', '').strip()
    if '@' not in email:
        flash('ایمیل معتبر وارد کنید.', 'error')
    elif NewsletterEmail.query.filter_by(email=email).first():
        flash('این ایمیل قبلاً در خبرنامه ثبت شده است.', 'info')
    else:
        db.session.add(NewsletterEmail(email=email))
        db.session.commit()
        flash('عضویت شما در خبرنامه با موفقیت ثبت شد! 🎉', 'success')
    return redirect(safe_referrer(url_for('site.index')))
