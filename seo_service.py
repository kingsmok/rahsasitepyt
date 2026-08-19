# -*- coding: utf-8 -*-
"""موتور سئو خودکار شبیه Rank Math — متا تگ + JSON-LD برای دوره/وبلاگ/مدرس.

هر موجودیت سه لایه دارد:
  ۱) تولید خودکار (auto) — عنوان، توضیحات، کلمات کلیدی، canonical، og:image و
     اسکیمای کامل (Course / Article / Person) از دادهٔ واقعی ساخته می‌شود.
  ۲) بازنویسی دستی (override) — رکورد SeoMeta مسیر (مثلاً /course/xxx) می‌تواند
     هر فیلدی را جایگزین کند؛ حتی کل اسکیما با schema_json دستی.
  ۳) همگام‌سازی — ensure_meta() موقع ذخیرهٔ دوره/مطلب/مدرس، رکورد SeoMeta را
     (اگر نباشد) می‌سازد تا در داشبورد سئو قابل ویرایش باشد؛ auto_sync() همه را
     یکجا می‌سازد. هیچ‌وقت مقدار دستی مدیر بازنویسی نمی‌شود.

مسیرهای SeoMeta: ``/course/<slug>`` ، ``/blog/<slug>`` ، ``/teacher/<id>``
"""
import json
import re

from models import db, SeoMeta, Setting
from validators import log_exc as _lexc


def _setting(key, default=''):
    try:
        row = Setting.query.filter_by(key=key).first()
        return row.value if row and row.value else default
    except Exception:
        return default


def site_name():
    return _setting('site_name', 'آکادمی آنلاین') or 'آکادمی آنلاین'


def absolute(base_url, path):
    """URL مطلق — مسیر /static/... یا URL کامل."""
    path = (path or '').strip()
    if not path:
        return ''
    if path.startswith(('http://', 'https://')):
        return path
    base = (base_url or '').rstrip('/')
    if not path.startswith('/'):
        path = '/' + path
    return base + path


def _fa_digits(value):
    return str(value or '').translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))


def _fit_title(title, limit=60):
    """عنوان کوتاه و مناسب سرچ (حداکثر limit کاراکتر)."""
    title = (title or '').strip()
    if len(title) <= limit:
        return title
    return title[: limit - 1].strip() + '…'


# ═══════════════════════════════════════════════════════════════════════════
# لایهٔ بازنویسی دستی (SeoMeta)
# ═══════════════════════════════════════════════════════════════════════════
def get_meta(path):
    try:
        return SeoMeta.query.filter_by(path=path).first()
    except Exception:
        return None


def apply_overrides(seo, path):
    """اعمال تنظیمات دستی SeoMeta روی دیکشنری سئوی تولیدشده.

    هر فیلد SeoMeta که مقدار داشته باشد جایگزین می‌شود؛ schema_json دستی
    (در صورت معتبر بودن JSON) کل اسکیما را عوض می‌کند.
    """
    meta = get_meta(path)
    if not meta:
        return seo
    if meta.title:
        seo['title'] = meta.title
    if meta.description:
        seo['description'] = meta.description
    if meta.keywords:
        seo['keywords'] = meta.keywords
    if meta.canonical:
        seo['canonical'] = meta.canonical
    if meta.noindex:
        seo['noindex'] = True
    if meta.nofollow:
        seo['nofollow'] = True
    if meta.og_image:
        seo['og_image'] = meta.og_image
    if meta.og_title:
        seo['og_title'] = meta.og_title
    if meta.og_desc:
        seo['og_desc'] = meta.og_desc
    if meta.schema_json:
        try:
            data = json.loads(meta.schema_json)
            if isinstance(data, dict):
                seo['schema'] = data
        except (ValueError, TypeError):
            _lexc('seo_service.apply_overrides')
    return seo


def ensure_meta(path, defaults=None):
    """ساخت رکورد SeoMeta اگر نبود (بدون بازنویسی مقادیر دستی)."""
    defaults = defaults or {}
    try:
        meta = SeoMeta.query.filter_by(path=path).first()
        if meta is None:
            meta = SeoMeta(path=path)
            db.session.add(meta)
            db.session.flush()
        return meta
    except Exception:
        _lexc('seo_service.ensure_meta')
        return None


# ═══════════════════════════════════════════════════════════════════════════
# دوره — Course
# ═══════════════════════════════════════════════════════════════════════════
def course_seo(course, base_url=''):
    """متا تگ + اسکیمای Course کامل برای صفحهٔ دوره."""
    from models import Review
    sn = site_name()
    base_url = (base_url or '').rstrip('/')
    path = '/course/' + (course.slug or str(course.id))
    reviews = (Review.query.filter_by(course_id=course.id, is_approved=True)
               .order_by(Review.created_at.desc()).limit(50).all())
    title = _fit_title('{} | {}'.format(course.title or '', sn), 60)
    disc = course.discount_percent or 0
    head = (course.title or '')
    if not head.startswith('دوره'):
        head = 'دوره ' + head
    parts = [head]
    if course.lesson_count:
        parts.append('{} جلسه و {} ساعت محتوای ثبت‌شده'.format(
            _fa_digits(course.lesson_count), _fa_digits(course.duration_hours or 0)))
    if course.students_count:
        parts.append('{} دانشجوی ثبت‌نام‌شده'.format(_fa_digits(course.students_count)))
    parts.append('گواهی پایان دوره با کد رهگیری')
    if disc:
        parts.append('همین حالا با {}٪ تخفیف ثبت‌نام کنید'.format(_fa_digits(disc)))
    else:
        parts.append('همین حالا ثبت‌نام کنید')
    description = ('؛ '.join(parts))[:158]
    keywords = ', '.join(
        (['دوره ' + (course.title or ''), course.category.name if course.category else 'آموزش',
          'آموزش آنلاین', 'گواهینامه'] if course.title else
         ['آموزش آنلاین', 'گواهینامه']))

    schema = {
        '@context': 'https://schema.org',
        '@type': 'Course',
        'name': course.title,
        'description': (course.subtitle or course.description or '')[:300],
        'image': absolute(base_url, course.image_url),
        'inLanguage': 'fa',
        'category': course.category.name if course.category else 'آموزش',
        'provider': {
            '@type': 'Organization',
            'name': sn,
            'url': base_url,
            'logo': absolute(base_url, '/static/img/favicon.svg'),
            'sameAs': base_url,
        },
        'offers': {
            '@type': 'Offer',
            'price': str(course.final_price or 0),
            'priceCurrency': 'IRR',
            'availability': 'https://schema.org/InStock',
            'url': base_url + path,
            'category': course.category.name if course.category else 'آموزش',
        },
        'coursePrerequisites': (course.requirements or '').split('\n')[0].strip() or 'بدون پیش‌نیاز خاص',
    }
    if course.duration_hours:
        schema['totalTime'] = 'PT{}H'.format(int(course.duration_hours or 0))
    if course.lesson_count:
        schema['numberOfLessons'] = course.lesson_count
    if course.teacher:
        schema['instructor'] = {
            '@type': 'Person',
            'name': course.teacher.name,
            'jobTitle': 'مدرس ارشد',
            'url': base_url + '/teacher/' + str(course.teacher.id),
        }
        if course.teacher.bio:
            schema['instructor']['description'] = (course.teacher.bio or '')[:200]
    if course.rating and reviews:
        schema['aggregateRating'] = {
            '@type': 'AggregateRating',
            'ratingValue': str(course.rating),
            'reviewCount': str(len(reviews)),
            'bestRating': '5',
        }
    schema['hasCourseInstance'] = {
        '@type': 'CourseInstance',
        'courseMode': {'online': 'Online', 'offline': 'OnDemand',
                       'inperson': 'Offline', 'hybrid': 'Mixed'}.get(
                           course.delivery_type or 'online', 'Online'),
        'courseWorkload': 'PT{}H'.format(int(course.duration_hours or 0)),
        'inLanguage': 'fa',
    }

    seo = {
        'title': title,
        'description': description,
        'keywords': keywords,
        'canonical': base_url + path,
        'og_type': 'product',
        'og_image': course.image_url,
        'og_title': title,
        'og_desc': description,
        'schema': schema,
        'noindex': False,
        'nofollow': False,
    }
    return apply_overrides(seo, path)


# ═══════════════════════════════════════════════════════════════════════════
# وبلاگ — Article
# ═══════════════════════════════════════════════════════════════════════════
def blog_seo(post, base_url=''):
    """متا تگ + اسکیمای Article کامل برای صفحهٔ مطلب."""
    sn = site_name()
    base_url = (base_url or '').rstrip('/')
    path = '/blog/' + (post.slug or str(post.id))
    title = _fit_title('{} | {}'.format(post.title or '', sn), 60)
    description = (post.excerpt or (post.body or '').replace('\n', ' '))[:158]
    schema = {
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': post.title,
        'description': (post.excerpt or '')[:300],
        'image': absolute(base_url, post.image_url),
        'inLanguage': 'fa',
        'datePublished': (post.created_at.strftime('%Y-%m-%d')
                          if post.created_at else ''),
        'author': {
            '@type': 'Person',
            'name': post.author.name if post.author else 'تیم آکادمی',
        },
        'publisher': {
            '@type': 'Organization',
            'name': sn,
            'logo': {'@type': 'ImageObject',
                     'url': absolute(base_url, '/static/img/favicon.svg')},
        },
        'mainEntityOfPage': base_url + path,
    }
    seo = {
        'title': title,
        'description': description,
        'keywords': (post.category or 'آموزش') + ', مقاله, وبلاگ',
        'canonical': base_url + path,
        'og_type': 'article',
        'og_image': post.image or '',
        'og_title': title,
        'og_desc': description,
        'schema': schema,
        'noindex': False,
        'nofollow': False,
    }
    return apply_overrides(seo, path)


# ═══════════════════════════════════════════════════════════════════════════
# مدرس — Person + ProfilePage
# ═══════════════════════════════════════════════════════════════════════════
def teacher_seo(teacher, base_url=''):
    """متا تگ + اسکیمای Person برای صفحهٔ مدرس."""
    from models import Course
    sn = site_name()
    base_url = (base_url or '').rstrip('/')
    path = '/teacher/' + str(teacher.id)
    courses = Course.query.filter_by(teacher_id=teacher.id,
                                     status='published').all()
    title = _fit_title('{} — مدرس {}'.format(teacher.name or '', sn), 60)
    description = ('صفحه مدرس {}. آشنایی با سوابق، تخصص و {}.'.format(
        teacher.name or '',
        'دوره‌های آموزشی' if not courses else
        '{} دورهٔ آموزشی'.format(_fa_digits(len(courses)))))[:158]
    schema = {
        '@context': 'https://schema.org',
        '@type': 'Person',
        'name': teacher.name,
        'jobTitle': 'مدرس',
        'url': base_url + path,
        'image': absolute(base_url, teacher.avatar_url) if teacher.avatar_url else '',
        'worksFor': {'@type': 'EducationalOrganization', 'name': sn,
                     'url': base_url},
        'description': (teacher.bio or '')[:300],
        'knowsAbout': [c.title for c in courses[:10]],
        'sameAs': [],
    }
    if not schema['image']:
        schema.pop('image', None)
    seo = {
        'title': title,
        'description': description,
        'keywords': (teacher.name or '') + ', مدرس, آموزش',
        'canonical': base_url + path,
        'og_type': 'profile',
        'og_image': teacher.avatar_url or '',
        'og_title': title,
        'og_desc': description,
        'schema': schema,
        'noindex': False,
        'nofollow': False,
    }
    return apply_overrides(seo, path)


# ═══════════════════════════════════════════════════════════════════════════
# همگام‌سازی خودکار رکوردهای SeoMeta (شبیه Rank Math auto-config)
# ═══════════════════════════════════════════════════════════════════════════
def auto_sync():
    """ساخت SeoMeta برای همهٔ دوره‌ها/مطالب/مدرس‌های بدون رکورد.

    فقط رکوردهای ناقص «ساخته» می‌شوند؛ مقدارهای دستی مدیر هرگز دست نمی‌خورند.
    خروجی: (created, total)
    """
    from models import BlogPost, Course, User
    created = 0
    total = 0
    for c in Course.query.filter_by(status='published').all():
        path = '/course/' + c.slug
        total += 1
        if SeoMeta.query.filter_by(path=path).first() is None:
            db.session.add(SeoMeta(path=path))
            created += 1
    for p in BlogPost.query.filter_by(published=True).all():
        path = '/blog/' + p.slug
        total += 1
        if SeoMeta.query.filter_by(path=path).first() is None:
            db.session.add(SeoMeta(path=path))
            created += 1
    for t in User.query.filter(User.role.in_(('teacher', 'admin')),
                               User.is_active == True).all():
        path = '/teacher/' + str(t.id)
        total += 1
        if SeoMeta.query.filter_by(path=path).first() is None:
            db.session.add(SeoMeta(path=path))
            created += 1
    try:
        db.session.commit()
    except Exception:
        _lexc('seo_service.auto_sync')
        try:
            db.session.rollback()
        except Exception:
            pass
    return created, total
