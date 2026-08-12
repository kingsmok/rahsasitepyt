# -*- coding: utf-8 -*-
"""صفحات عمومی سایت"""
from flask import Blueprint, render_template, request, abort, redirect, url_for, flash, g, session
import re
import json
from sqlalchemy import or_

_FA_MAP = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')

def fa_num2(n):
    return str(n).translate(_FA_MAP)
from sqlalchemy.orm import joinedload
from models import db, Course, Category, User, BlogPost, Review, Favorite, ContactMessage, NewsletterEmail, Section, Enrollment
from validators import log_exc as _lexc

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
    # طرح انتخابی صفحه اصلی (از تنظیمات یا پارامتر پیش‌نمایش)
    design = request.args.get('design') or g.settings.get('home_design', '1')
    hp = getattr(g, 'pages', {}).get('home')
    # fallback: اگر صفحه home در builder خالی باشد → طرح پیش‌فرض (جلوگیری از صفحه خالی)
    if hp and hp.is_published and not hp.rows():
        hp = None
        design = '1'
    # اگر «صفحه صفحه‌ساز» انتخاب شده یا طرح نامعتبر است و صفحه builder موجود است
    if design == 'builder' and hp and hp.is_published and hp.rows():
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

    sort_map = {
        'newest': Course.created_at.desc(),
        'oldest': Course.created_at.asc(),
        'cheap': Course.discount_price.asc(),
        'expensive': Course.discount_price.desc(),
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
                _c._agg_students = (_c.seeded_students or 0) + _enr_map.get(_c.id, 0)
        except Exception:
            _lexc('site.py')
    categories = Category.query.order_by(Category.sort).all()
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
            g.seo['description'] = f"بهترین دوره‌های {cat_obj.name} با تدریس مدرسان حرفه‌ای — {n_items} دوره پروژه‌محور با گواهینامه معتبر و دسترسی مادام‌العمر."
        elif meta:
            g.seo['title'] = meta.title or g.seo['title']
            g.seo['description'] = meta.description or g.seo['description']
    return render_template('courses.html', courses=items, page=page, pages=pages, total=total,
                           categories=categories, q=q, cat=cat, level=level, price=price, sort=sort,
                           cat_obj=cat_obj)


# ---------------------------------------------------------------- جزئیات دوره
@site_bp.route('/course/<slug>')
def course_detail(slug):
    course = (Course.query.options(joinedload(Course.category), joinedload(Course.teacher),
                                   joinedload(Course.sections).joinedload(Section.lessons))
              .filter_by(slug=slug, status='published').first_or_404())
    course.views = (course.views or 0) + 1
    db.session.commit()
    enrolled = bool(g.user and any(e.course_id == course.id for e in g.user.enrollments))
    co_teachers = [ct for ct in course.co_teachers] if hasattr(course, 'co_teachers') else []
    is_fav = bool(g.user and Favorite.query.filter_by(user_id=g.user.id, course_id=course.id).first())
    related = Course.query.filter(Course.category_id == course.category_id,
                                  Course.id != course.id, Course.status == 'published').limit(3).all()
    # اگر در همان دسته دوره دیگری نبود، از دوره‌های دیگر (هم‌تگ یا محبوب) پیشنهاد بده
    if not related:
        related = Course.query.filter(Course.id != course.id, Course.status == 'published') \
            .order_by(Course.views.desc()).limit(3).all()
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
    # ─────────────── بهینه‌سازی سئو (E-E-A-T + Helpful Content) ───────────────
    site_name = g.settings.get('site_name', 'آکادمی آنلاین')
    # کلمات کلیدی هم‌خانواده و LSI (بر اساس دسته + پایه)
    _lsi = ['آموزش پایتون', 'دوره پایتون', 'برنامه‌نویسی پایتون', 'پایتون از صفر',
            'پایتون پروژه محور', 'آموزش پایتون برای مبتدیان', 'پایتون پیشرفته',
            'یادگیری ماشین با پایتون', 'وب اسکرپینگ با پایتون', 'استخدام برنامه‌نویس پایتون',
            'گواهینامه پایتون', 'کتابخانه‌های پایتون']
    if course.category and course.category.name != 'برنامه‌نویسی':
        _lsi = [course.category.name, course.title] + [k for k in _lsi if k not in ('آموزش پایتون', 'دوره پایتون')][:9]
    g.seo['keywords'] = ', '.join(_lsi[:12])
    # عنوان سئو — کوتاه، کلیک‌خور (< 60 کاراکتر)
    g.seo['title'] = f"{course.title} | {site_name}"
    if len(g.seo['title']) > 60:
        g.seo['title'] = f"{course.title[:45].strip()} | {site_name}"
    # توضیحات متا — ترغیب‌کننده با CTA (۱۳۰ تا ۱۶۰ کاراکتر)
    disc = (course.discount_percent or 0)
    _t = course.title or ''
    _head = _t if _t.startswith('دوره') else f'دوره {_t}'
    meta_parts = [
        _head,
        f"{course.lesson_count} جلسه ویدیویی و {course.duration_hours} ساعت آموزش پروژه‌محور",
    ]
    if course.students_count:
        meta_parts.append(f"با بیش از {course.students_count} دانشجو")
    meta_parts.append("ضمانت بازگشت وجه و گواهینامه معتبر")
    if disc:
        meta_parts.append(f"همین حالا با {disc}٪ تخفیف ثبت‌نام کنید")
    else:
        meta_parts.append("همین حالا ثبت‌نام کنید")
    g.seo['description'] = ('؛ '.join(meta_parts))[:158]
    g.seo['og_image'] = course.image
    # ─────────────── اسکیمای Course کامل (با E-E-A-T) ───────────────
    schema = {
        "@context": "https://schema.org",
        "@type": "Course",
        "name": course.title,
        "description": (course.subtitle or course.description or '')[:300],
        "image": request.host_url.rstrip('/') + '/static/img/' + (course.image or 'hero.webp'),
        "inLanguage": "fa",
        "category": course.category.name if course.category else 'آموزش',
        "provider": {"@type": "Organization", "name": site_name,
                     "url": request.host_url.rstrip('/'),
                     "logo": request.host_url.rstrip('/') + '/static/img/favicon.svg',
                     "sameAs": request.host_url.rstrip('/')},
        "offers": {"@type": "Offer", "price": str(course.final_price),
                   "priceCurrency": "IRR", "availability": "https://schema.org/InStock",
                   "url": request.url, "category": course.category.name if course.category else 'آموزش'},
        "coursePrerequisites": (course.requirements or '').split('\n')[0].strip() or 'بدون پیش‌نیاز خاص',
    }
    if course.duration_hours:
        schema["totalTime"] = f"PT{int(course.duration_hours)}H"
    if course.lesson_count:
        schema["numberOfLessons"] = course.lesson_count
    if course.teacher:
        schema["instructor"] = {"@type": "Person", "name": course.teacher.name,
                                "jobTitle": "مدرس ارشد",
                                "url": request.host_url.rstrip('/') + url_for('site.teacher_detail', uid=course.teacher.id)}
        if course.teacher.bio:
            schema["instructor"]["description"] = course.teacher.bio[:200]
    if course.rating:
        schema["aggregateRating"] = {"@type": "AggregateRating",
                                     "ratingValue": str(course.rating),
                                     "reviewCount": str(len(reviews)),
                                     "bestRating": "5"}
    schema["hasCourseInstance"] = {"@type": "CourseInstance",
                                   "courseMode": "Online",
                                   "courseWorkload": f"PT{int(course.duration_hours or 0)}H",
                                   "inLanguage": "fa"}
    g.seo['schema'] = schema
    g.seo['og_type'] = 'product'
    # مقالات مرتبط برای لینک‌سازی داخلی
    from models import BlogPost as _BlogPost
    blog_posts = _BlogPost.query.filter_by(published=True).order_by(_BlogPost.created_at.desc()).limit(3).all()
    done_ids = set()
    if g.user:
        en = next((e for e in g.user.enrollments if e.course_id == course.id), None)
        if en:
            done_ids = set(en.progress_list())
    return render_template('course_detail.html', course=course, related=related,
                           reviews=reviews, enrolled=enrolled, is_fav=is_fav,
                           done_ids=done_ids, blog_posts=blog_posts)


@site_bp.route('/course/<slug>/review', methods=['POST'])
def add_review(slug):
    if not g.user:
        flash('برای ثبت نظر ابتدا وارد شوید.', 'error')
        return redirect(url_for('auth.login'))
    course = Course.query.filter_by(slug=slug).first_or_404()
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
    if existing:
        existing.rating = max(1, min(5, rating))
        existing.comment = comment
    else:
        db.session.add(Review(course_id=course.id, user_id=g.user.id,
                              rating=max(1, min(5, rating)), comment=comment))
    db.session.commit()
    flash('نظر شما با موفقیت ثبت شد. ممنون از بازخوردتان!', 'success')
    return redirect(url_for('site.course_detail', slug=slug) + '#reviews')


# ---------------------------------------------------------------- صفحه سفارشی ساخته‌شده با صفحه‌ساز
@site_bp.route('/page/<slug>')
def custom_page(slug):
    from models import Page
    page = Page.query.filter_by(slug=slug, ptype='page').first()
    if page:
        g.page_custom_header = page.custom_header
        g.page_custom_footer = page.custom_footer
    if not page or not page.is_published or not page.rows():
        abort(404)
    g.page_settings = page.settings()
    return render_template('builder/public.html', page=page)



# ---------------------------------------------------------------- صفحات قانونی
@site_bp.route('/terms')
def terms():
    return render_template('legal.html', page_title='قوانین و مقررات',
        page_icon='📜', intro='لطفاً پیش از استفاده از خدمات آکادمی آنلاین، قوانین زیر را به دقت مطالعه کنید.',
        sections=[
            ('۱. پذیرش قوانین', 'با ثبت‌نام و استفاده از خدمات آکادمی آنلاین، تمامی قوانین و مقررات این سایت را می‌پذیرید. در صورت عدم موافقت با هر یک از بندها، از استفاده از خدمات خودداری کنید.'),
            ('۲. حساب کاربری', 'مسئولیت حفظ محرمانه‌بودن رمز عبور و تمام فعالیت‌های انجام‌شده با حساب شما بر عهده شماست. اطلاعات هویتی (کد ملی، شماره تماس) باید دقیق و واقعی باشند.'),
            ('۳. خرید و پرداخت', 'با تکمیل فرایند پرداخت، دوره به صورت خودکار به حساب شما اضافه می‌شود. در صورت بروز مشکل در پرداخت، حداکثر تا ۷۲ ساعت وجه به حساب شما بازگردانده می‌شود.'),
            ('۴. حق استفاده از محتوا', 'محتواهای آموزشی صرفاً برای استفاده شخصی شماست. هرگونه کپی‌برداری، فروش مجدد یا انتشار عمومی دوره‌ها پیگرد قانونی دارد.'),
            ('۵. بازگشت وجه', 'تا ۷ روز پس از خرید، در صورت عدم استفاده از بیش از ۲۰٪ محتوا، امکان درخواست بازگشت وجه وجود دارد.'),
            ('۶. گواهینامه‌ها', 'گواهینامه‌های صادرشده دارای کد رهگیری منحصربه‌فرد هستند و صحت آن‌ها از طریق پشتیبانی قابل استعلام است.'),
        ])


@site_bp.route('/privacy')
def privacy():
    return render_template('legal.html', page_title='حریم خصوصی',
        page_icon='🔒', intro='حفظ حریم خصوصی شما برای ما اهمیت بالایی دارد. این خط‌مشی نحوه جمع‌آوری و استفاده از اطلاعات شما را شرح می‌دهد.',
        sections=[
            ('۱. اطلاعات جمع‌آوری‌شده', 'نام، شماره تماس، کد ملی و ایمیل شما صرفاً برای احراز هویت، ارائه خدمات آموزشی و صدور گواهینامه جمع‌آوری می‌شود.'),
            ('۲. استفاده از اطلاعات', 'اطلاعات شما برای مدیریت حساب، پردازش خریدها، ارسال اطلاعیه‌ها و بهبود کیفیت خدمات استفاده می‌شود.'),
            ('۳. واترمارک ویدیو', 'برای حفاظت از محتوای آموزشی، نام و کد ملی شما به صورت ماسک‌شده روی ویدیوهای دوره نمایش داده می‌شود.'),
            ('۴. اشتراک‌گذاری', 'اطلاعات شما هرگز بدون رضایت شما در اختیار اشخاص ثالث قرار نمی‌گیرد، مگر در موارد قانونی.'),
            ('۵. امنیت داده‌ها', 'اطلاعات شما با رمزنگاری و پروتکل‌های امنیتی استاندارد ذخیره می‌شود.'),
            ('۶. حذف اطلاعات', 'در هر زمان می‌توانید از طریق تیکت پشتیبانی درخواست حذف کامل اطلاعات خود را ثبت کنید.'),
        ])


# ---------------------------------------------------------------- حالت تعمیرات
@site_bp.route('/maintenance')
def maintenance():
    from flask import render_template
    return render_template('maintenance.html'), 503 if g.settings.get('maintenance') == '1' else 200



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
    for u in ['/courses', '/teachers', '/blog', '/about', '/faq', '/contact', '/terms', '/privacy', '/become-teacher', '/learning-paths', '/consultation']:
        xml += f'<url><loc>{base}{u}</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>'
    # دوره‌ها با تصویر و اولویت بالا
    from marketplace import _feed_image as _fimg
    for c in Course.query.filter_by(status='published').all():
        xml += f'<url><loc>{_xe(base)}/course/{_xe(c.slug)}</loc><changefreq>monthly</changefreq><priority>0.9</priority>'
        xml += f'<image:image><image:loc>{_xe(base)}/static/img/{_xe(_fimg(c.image))}</image:loc><image:title>{_xe(c.title)}</image:title></image:image>'
        xml += '</url>'
    # مقالات
    for p in BlogPost.query.filter_by(published=True).all():
        xml += f'<url><loc>{_xe(base)}/blog/{_xe(p.slug)}</loc><lastmod>{p.created_at.strftime("%Y-%m-%d")}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority>'
        if p.image:
            xml += f'<image:image><image:loc>{_xe(base)}/static/img/{_xe(p.image)}</image:loc></image:image>'
        xml += '</url>'
    # محصولات فروشگاه
    from models import Product as _Prod
    for pr in _Prod.query.filter(_Prod.stock > 0).all():
        xml += f'<url><loc>{_xe(base)}/product/{_xe(pr.slug)}</loc><changefreq>weekly</changefreq><priority>0.6</priority></url>'
    # اساتید
    for t in User.query.filter(User.role == 'teacher').all():
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
        f"Disallow: /wallet\n"
        f"Disallow: /uploads\n"
        f"Disallow: /maintenance\nDisallow: /static/uploads\n"
        f"\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    return Response(txt, mimetype='text/plain')


# ---------------------------------------------------------------- اساتید
@site_bp.route('/teachers')
def teachers():
    from sqlalchemy import func as _f
    from models import Review, Course, Enrollment
    # ⚠️ قبلاً همه ثبت‌نام‌های هر دوره بارگذاری می‌شد (هزاران ردیف) — حالا فقط شمارش
    teachers = User.query.filter(User.role == 'teacher').all()
    # امتیاز هر استاد با یک کوئری تجمیعی (JOIN Course + Review)
    tids = [t.id for t in teachers]
    ratings = {}
    if tids:
        rows = db.session.query(Course.teacher_id, _f.avg(Review.rating), _f.count(Review.id)) \
            .join(Review, Review.course_id == Course.id) \
            .filter(Course.teacher_id.in_(tids), Review.is_approved == True) \
            .group_by(Course.teacher_id).all()
        for tid, avg, cnt in rows:
            ratings[tid] = round(avg, 1) if avg else None
    # تعداد دانشجو هر استاد — یک کوئری تجمیعی دیگر
    students = {}
    if tids:
        srows = db.session.query(Course.teacher_id, _f.count(Enrollment.id)) \
            .join(Enrollment, Enrollment.course_id == Course.id) \
            .filter(Course.teacher_id.in_(tids)) \
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
    teacher = User.query.filter_by(id=uid, role='teacher').first_or_404()
    courses = (Course.query.options(joinedload(Course.category))
               .filter_by(teacher_id=uid, status='published').all())
    # متای پویا (سئو) — اولویت با SeoMeta اختصاصی است، در غیر این صورت پویا
    from models import SeoMeta
    meta = SeoMeta.query.filter_by(path=request.path).first()
    if not meta or not meta.title:
        g.seo['title'] = f"{teacher.name} — مدرس {g.settings.get('site_name', 'آکادمی آنلاین')}"
    if not meta or not meta.description:
        n_courses = str(len(courses)).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))
        g.seo['description'] = f"صفحه مدرس {teacher.name} — آشنایی با سوابق، تخصص و دوره‌های آموزشی {n_courses} دوره در آکادمی آنلاین."
    # قالب داینامیک: اگر «قالب صفحه مدرس» ساخته شده باشد
    from models import Page
    tp = Page.query.filter_by(ptype='teacher').first()
    if tp and tp.is_published and tp.rows():
        g.current_teacher = teacher
        g.page_settings = tp.settings()
        return render_template('builder/public.html', page=tp)
    return render_template('teacher_detail.html', teacher=teacher, courses=courses)


# ---------------------------------------------------------------- وبلاگ
@site_bp.route('/blog')
def blog():
    page = request.args.get('page', 1, type=int)
    cat = request.args.get('cat', '').strip()
    query = BlogPost.query.options(db.joinedload(BlogPost.author)).filter_by(published=True)
    if cat:
        query = query.filter(BlogPost.category == cat)
    query = query.order_by(BlogPost.created_at.desc())
    items, page, pages, total = _pagination(page, 6, query)
    cats = db.session.query(BlogPost.category).distinct().all()
    return render_template('blog.html', posts=items, page=page, pages=pages, cats=[c[0] for c in cats], cat=cat)


@site_bp.route('/blog/<slug>', methods=['GET', 'POST'])
def blog_post(slug):
    from models import BlogComment
    post = BlogPost.query.filter_by(slug=slug, published=True).first_or_404()
    g.current_post = post
    if request.method == 'POST':
        from validators import clamp_field
        name = clamp_field(request.form.get('name'), 'name')
        comment = clamp_field(request.form.get('comment'), 'comment')
        if name and comment:
            db.session.add(BlogComment(post_id=post.id, name=name, comment=comment))
            db.session.commit()
            flash('دیدگاه شما ثبت شد. ممنون! 🙏', 'success')
        else:
            flash('نام و متن دیدگاه الزامی است.', 'error')
        return redirect(url_for('site.blog_post', slug=slug) + '#comments')
    post.views = (post.views or 0) + 1
    db.session.commit()
    # schema.org مقاله
    g.seo['schema'] = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post.title,
        "description": (post.excerpt or '')[:300],
        "image": request.host_url.rstrip('/') + '/static/img/' + (post.image or 'hero.webp'),
        "datePublished": post.created_at.strftime('%Y-%m-%d'),
        "author": {"@type": "Person", "name": post.author.name if post.author else 'تیم آکادمی'},
        "publisher": {"@type": "Organization", "name": g.settings.get('site_name', 'آکادمی آنلاین')},
        "mainEntityOfPage": request.url,
    }
    g.seo['og_type'] = 'article'
    if not g.seo['title']:
        g.seo['title'] = f"{post.title} | {g.settings.get('site_name', 'آکادمی آنلاین')}"
    if not g.seo['description']:
        g.seo['description'] = (post.excerpt or '')[:160]
    g.seo['og_image'] = post.image or 'hero.webp'
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
            .order_by(Course.seeded_students.desc()).first()
    return render_template('blog_post.html', post=post, recent=recent,
                           related_course=related_course)


# ---------------------------------------------------------------- صفحات ثابت
@site_bp.route('/about')
def about():
    from models import User as _U, Lesson as _L, Review as _RV
    teachers = _U.query.filter(_U.role.in_(['teacher', 'admin'])).count()
    total_courses = Course.query.filter_by(status='published').count()
    total_students = _U.query.filter_by(role='student').count()
    total_lessons = _L.query.count()
    total_hours = int(sum((c.duration_hours or 0) for c in Course.query.all()))
    total_reviews = _RV.query.filter_by(is_approved=True).count()
    _avg_rating = db.session.query(db.func.avg(_RV.rating)).filter(_RV.is_approved == True).scalar() or 0
    total_satisfaction = round((_avg_rating or 0) / 5 * 100)
    design = request.args.get('design') or g.settings.get('about_design', '1')
    if design not in [str(i) for i in range(1, 6)]:
        design = '1'
    return render_template(f'about/design{design}.html', teachers=teachers,
                           total_courses=total_courses, total_students=total_students,
                           total_lessons=total_lessons, total_hours=total_hours,
                           total_reviews=total_reviews, total_satisfaction=total_satisfaction)


@site_bp.route('/faq')
def faq():
    return render_template('faq.html')


@site_bp.route('/learning-paths')
def learning_paths():
    """صفحه مسیرهای یادگیری — نقشه راه پیشنهادی دوره‌ها"""
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
    """فرم دریافت مشاوره رایگان — تولید لید"""
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
            flash('درخواست مشاوره شما ثبت شد! کارشناسان ما به‌زودی با شما تماس می‌گیرند. 📞', 'success')
            return redirect(url_for('site.consultation'))
    g.seo['title'] = "دریافت مشاوره رایگان — انتخاب بهترین مسیر یادگیری | آکادمی آنلاین"
    g.seo['description'] = "مشاوره رایگان برای انتخاب دوره مناسب: کارشناسان ما بر اساس هدف و سطح شما بهترین مسیر یادگیری را پیشنهاد می‌دهند."
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
        from models import Enrollment, Course
        if not code.startswith('CRT-'):
            code = 'CRT-' + code
        # جستجو در گواهی‌های صادرشده — هم کد جدید (MD5) و هم کد قدیمی (SHA-1)
        from models import certificate_code, certificate_code_legacy_sha1
        for e in Enrollment.query.filter(Enrollment.completed_at.isnot(None)).all():
            c = e.course
            cert_code = certificate_code(c.slug, e.user.email, e.id)
            if cert_code == code or certificate_code_legacy_sha1(c.slug, e.user.email, e.id) == code:
                result = {'code': cert_code, 'user': e.user.name, 'course': c.title,
                          'date': e.completed_at, 'valid': True}
                break
        if not result:
            result = {'code': code, 'valid': False}
    g.seo['title'] = 'استعلام گواهینامه — آکادمی آنلاین'
    g.seo['description'] = 'با وارد کردن کد رهگیری گواهینامه، از صحت آن مطمئن شوید.'
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
        from validators import clamp_field
        name = clamp_field(request.form.get('name'), 'name')
        email = clamp_field(request.form.get('email'), 'email')
        subject = clamp_field(request.form.get('subject'), 'subject')
        message = clamp_field(request.form.get('message'), 'message')
        if not name or not message:
            flash('نام و متن پیام الزامی است.', 'error')
        else:
            db.session.add(ContactMessage(name=name, email=email, subject=subject, message=message))
            db.session.commit()
            flash('پیام شما با موفقیت ارسال شد. به زودی پاسخ می‌دهیم.', 'success')
            return redirect(url_for('site.contact'))
    design = request.args.get('design') or g.settings.get('contact_design', '1')
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
    return redirect(request.referrer or url_for('site.index'))
