# -*- coding: utf-8 -*-
"""پنل مدیریت — مدیریت کامل سایت"""
import functools
import json
import os
import random
import uuid
from datetime import datetime
try:
    from datetime import UTC
except ImportError:  # پایتون < 3.11 (هاست‌های اشتراکی)
    from datetime import timezone as _tz_utc
    UTC = _tz_utc.utc
from flask import (Blueprint, render_template, request, redirect, url_for, flash,
                   g, abort, session, jsonify, current_app)
from sqlalchemy import func
from models import (utcnow, db, User, Category, Course, Section, Lesson, Order, OrderItem,
                    Coupon, BlogPost, BlogComment, NewsletterEmail, ContactMessage,
                    Ticket, Setting, Enrollment, Review, PaymentProof, ActivityLog,
                    Quiz, QuizQuestion, QuizAttempt, Assignment, AssignmentSubmission,
                    LessonQuestion, Bundle, BundleCourse, CustomForm, CustomFormEntry, CannedReply, Menu, MenuItem, ChatMessage,
                    PayoutRequest, StudyDay, ForumTopic, ForumPost, LiveSession, Installment, TicketReply,
                    Page, RedirectRule)

import re as _re
from validators import human_size, safe_int
from validators import log_exc as _lexc
from validators import safe_referrer
from jdates import jdate_num, jtime, fa_num


def _save_lesson_file(f):
    """ذخیره فایل پیوست جلسه (پروژه/دیتا) و برگرداندن اطلاعات آن"""
    if not f or not f.filename:
        return None
    from uploads_helper import uploads_dir, uploads_url
    up = uploads_dir('lessons')
    from validators import safe_filename
    safe = safe_filename(f.filename or '')
    if not safe:
        return None
    name = 'lesson_' + uuid.uuid4().hex[:8] + '_' + safe
    path = os.path.join(up, name)
    f.save(path)
    size = os.path.getsize(path)
    return {'url': uploads_url('lessons', name),
            'name': f.filename,
            'size': human_size(size)}


def slugify(text):
    text = (text or '').strip().replace(' ', '-')
    return _re.sub(r'[^\w\u0600-\u06FF\-]', '', text)

admin_bp = Blueprint('admin', __name__)

# مقادیر محرمانه هرگز دوباره داخل HTML نمایش داده نمی‌شوند. خالی گذاشتن فیلد
# در ویرایش بعدی یعنی «مقدار فعلی را نگه دار»، نه پاک‌کردن ناخواسته.
_SECRET_SETTING_KEYS = {
    'idpay_api_key', 'parsian_login_account', 'melli_password', 'sadad_key',
    'snapp_client_secret', 'digipay_api_key', 'tarb_api_key',
    'sms_kavenegar_key', 'sms_melli_password', 'sms_faraz_token',
    'smtp_pass', 'dk_access_token', 'basalam_webhook_secret',
}


def admin_required(view):
    """گارد مرکزی پنل؛ مدیران و کارکنان فقط endpoint مجاز خود را می‌بینند."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash('برای ورود به پنل ابتدا وارد حساب خود شوید.', 'error')
            return redirect(url_for('auth.login', next=request.path))
        from permissions import can_access_endpoint
        if not can_access_endpoint(g.user, request.endpoint):
            # کاربر دانشجو/مدرس به صفحه عمومی برگردد؛ کارکنانی که صرفاً مجوز
            # این بخش را ندارند پاسخ صریح 403 می‌گیرند.
            if g.user.role not in ('admin', 'super_admin', 'secretary', 'support', 'operator'):
                flash('دسترسی غیرمجاز — این بخش در نقش شما فعال نیست.', 'error')
                return redirect(url_for('site.index'))
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def _sections_lessons(course):
    return [(s, s.lessons) for s in course.sections]


# ---------------------------------------------------------------- داشبورد ادمین
@admin_bp.route('/')
@admin_required
def overview():
    # نقش‌های عملیاتی نباید داشبورد مالی کامل مدیر را ببینند. کارت‌ها بر اساس
    # همان Permissionهایی ساخته می‌شوند که مسیرها را کنترل می‌کنند.
    if g.user.role in ('secretary', 'support', 'operator'):
        from permissions import has_permission, menu_for
        cards = []
        if has_permission(g.user, 'view_users'):
            cards.append(('👥', 'کاربران فعال', User.query.filter_by(is_active=True).count(),
                          'admin.users'))
        if has_permission(g.user, 'view_orders'):
            cards.append(('🧾', 'سفارش‌های در انتظار', Order.query.filter_by(status='pending').count(),
                          'admin.orders'))
        if has_permission(g.user, 'approve_payments'):
            cards.append(('💳', 'فیش‌های در انتظار', PaymentProof.query.filter_by(status='pending').count(),
                          'admin.proofs'))
        if has_permission(g.user, 'reply_tickets'):
            cards.append(('🎫', 'تیکت‌های باز', Ticket.query.filter(
                Ticket.status.in_(['open', 'answered'])).count(), 'admin.tickets'))
        if has_permission(g.user, 'view_consultations'):
            cards.append(('🎯', 'مشاوره‌های خوانده‌نشده', ContactMessage.query.filter(
                ContactMessage.subject.like('%مشاوره%'),
                ContactMessage.is_read == False).count(), 'admin.consultations'))
        if has_permission(g.user, 'view_daily_classes'):
            cards.append(('🎥', 'کلاس‌های پیش رو', LiveSession.query.filter(
                LiveSession.starts_at >= utcnow()).count(), 'admin.live_sessions'))
        links = [(endpoint, label) for endpoint, label in menu_for(g.user)
                 if endpoint not in ('sep', 'admin.overview')]
        return render_template('admin/staff_overview.html', cards=cards, links=links)

    from datetime import timedelta
    total_revenue = db.session.query(func.coalesce(func.sum(Order.final_total), 0)) \
        .filter(Order.status == 'paid').scalar()
    paid_orders = Order.query.filter_by(status='paid').count()
    users_count = User.query.filter_by(is_active=True).count()
    courses_count = Course.query.count()
    published_courses_count = Course.query.filter_by(status='published').count()
    today_orders = Order.query.filter(func.date(Order.created_at) == func.date(func.now())).count()
    from sqlalchemy.orm import selectinload as _sil
    recent_orders = Order.query.options(_sil(Order.items)).order_by(Order.created_at.desc()).limit(8).all()
    recent_users = User.query.filter_by(is_active=True).order_by(User.created_at.desc()).limit(6).all()
    top_courses = Course.query.options(db.joinedload(Course.category)) \
        .filter_by(status='published').order_by(Course.views.desc()).limit(5).all()
    tickets_open = Ticket.query.filter(Ticket.status.in_(['open', 'answered'])).count()
    messages = ContactMessage.query.filter_by(is_read=False).count()
    # نمودار فروش ۷ روز اخیر
    week = []
    now = utcnow()
    for i in range(6, -1, -1):
        d = now - timedelta(days=i)
        start = datetime(d.year, d.month, d.day)
        end = start + timedelta(days=1)
        rev = db.session.query(func.coalesce(func.sum(Order.final_total), 0)) \
            .filter(Order.status == 'paid', Order.paid_at >= start, Order.paid_at < end).scalar()
        cnt = Order.query.filter(Order.status == 'paid', Order.paid_at >= start,
                                 Order.paid_at < end).count()
        from jdates import jdate
        week.append({'label': jdate(d), 'revenue': rev or 0, 'count': cnt or 0})
    max_rev = max([w['revenue'] for w in week] + [1])
    for w in week:
        w['pct'] = round(w['revenue'] * 100 / max_rev)
    reviews_pending = Review.query.join(Course, Course.id == Review.course_id) \
        .filter(Review.is_approved == False, Course.status == 'published').count()
    # گزارش‌های تکمیلی: نرخ تکمیل دوره‌ها، کاربران فعال، فروش ماه
    from datetime import timedelta
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_revenue = db.session.query(func.coalesce(func.sum(Order.final_total), 0)) \
        .filter(Order.status == 'paid', Order.paid_at >= month_start).scalar() or 0
    month_orders = Order.query.filter(Order.status == 'paid', Order.paid_at >= month_start).count()
    active_users = User.query.filter(User.is_active == True, User.last_active.isnot(None),
                                     User.last_active >= (now - timedelta(days=7)).strftime('%Y-%m-%d')).count()
    enrolls = Enrollment.query.join(Course, Course.id == Enrollment.course_id) \
        .join(User, User.id == Enrollment.user_id) \
        .filter(Course.status == 'published', User.is_active == True).all()
    completion_rate = round(sum(1 for e in enrolls if e.percent >= 100) * 100 / len(enrolls)) if enrolls else 0
    avg_progress = round(sum(e.percent for e in enrolls) / len(enrolls)) if enrolls else 0
    # ثبت‌نام‌های امروز
    new_today = User.query.filter(User.is_active == True,
                                  func.date(User.created_at) == func.date(func.now())).count()
    return render_template('admin/overview.html', total_revenue=total_revenue,
                           paid_orders=paid_orders, users_count=users_count,
                           courses_count=courses_count,
                           published_courses_count=published_courses_count,
                           today_orders=today_orders,
                           recent_orders=recent_orders, recent_users=recent_users,
                           top_courses=top_courses, tickets_open=tickets_open,
                           messages=messages, week=week, reviews_pending=reviews_pending,
                           month_revenue=month_revenue, month_orders=month_orders,
                           active_users=active_users, completion_rate=completion_rate,
                           avg_progress=avg_progress, new_today=new_today)


# ---------------------------------------------------------------- راه‌اندازی نهایی یکپارچه
@admin_bp.route('/go-live', methods=['GET', 'POST'])
@admin_required
def go_live():
    """مرکز راه‌اندازی و انتشار کنترل‌شده سایت.

    نصب تازه عمداً غیرفعال است. انتشار فقط زمانی انجام می‌شود که هویت عمومی،
    محتوای واقعی و ـ در صورت وجود کالای پولی ـ یک درگاه واقعی آماده باشند.
    """
    keys = [
        'site_name', 'site_desc', 'phone', 'email', 'address', 'support_hours',
        'about_text', 'base_url', 'currency', 'refund_days',
        'shipping_flat_rate', 'shipping_note',
        'c2c_card', 'c2c_name', 'zarinpal_merchant', 'idpay_api_key',
        'zibal_merchant', 'parsian_login_account', 'melli_terminal',
        'melli_username', 'melli_password', 'sepah_terminal',
        'sadad_merchant', 'sadad_terminal', 'sadad_key',
        'sms_provider', 'sms_test_phone', 'sms_kavenegar_key',
        'sms_kavenegar_sender', 'sms_kavenegar_template',
        'sms_melli_username', 'sms_melli_password', 'sms_melli_sender',
        'sms_faraz_token', 'sms_faraz_sender',
        'smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass', 'smtp_from', 'smtp_tls',
    ]

    def _readiness(values):
        from gateways import GATEWAYS, gateway_ready
        from sms import provider_ready
        from models import Product
        published = Course.query.filter_by(status='published').all()
        active_products = Product.query.filter_by(is_active=True).all()
        public_ready = bool(values.get('site_name') and values.get('site_desc') and
                            (values.get('phone') or values.get('email')))
        payment_ready = any(gateway_ready(item['id'], values)
                            for item in GATEWAYS if item.get('kind') != 'test')
        paid_content = any((item.final_price or 0) > 0
                           for item in published + active_products)
        content_ready = bool(published or active_products)
        from licensing import get_license_manager
        license_state = get_license_manager().status(request.host)
        checks = {
            'public': public_ready,
            # اگر کل محتوای منتشرشده رایگان است، درگاه شرط انتشار نیست.
            'payment': payment_ready or not paid_content,
            'sms': provider_ready(values),
            'smtp': bool(values.get('smtp_host') and values.get('smtp_from')),
            'content': content_ready,
            # بسته community قفل ندارد؛ بسته تجاری باید لایسنس معتبر داشته باشد.
            'license': license_state.valid or not license_state.enforced,
        }
        launch_ready = (checks['public'] and checks['content'] and
                        checks['payment'] and checks['license'])
        return (checks, launch_ready, len(published), len(active_products),
                paid_content, license_state)

    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action in ('activate', 'deactivate'):
            values = {row.key: row.value for row in Setting.query.all()}
            checks, launch_ready, _cc, _pc, _paid, _license = _readiness(values)
            force = str(request.form.get('force') or '') == '1'
            is_super = g.user.role == 'super_admin'
            if action == 'activate' and not launch_ready and not (force and is_super):
                missing = [label for key, label in
                           (('public', 'برند و تماس'), ('content', 'محتوا'),
                            ('payment', 'پرداخت'), ('license', 'لایسنس'))
                           if key in checks and not checks[key]]
                flash('انتشار انجام نشد؛ این موارد هنوز کامل نیست: ' +
                      ('، '.join(missing) if missing else 'موارد الزامی') +
                      '. (سوپر ادمین می‌تواند با گزینهٔ «فعال‌سازی اجباری» انتشار دهد.)',
                      'error')
                return redirect(url_for('admin.go_live'))
            row = db.session.get(Setting, 'site_active')
            value = '1' if action == 'activate' else '0'
            if row:
                row.value = value
            else:
                db.session.add(Setting(key='site_active', value=value))
            db.session.commit()
            clear = getattr(current_app, 'clear_cache', None)
            if callable(clear):
                clear()
            if value == '1' and force and not launch_ready:
                flash('سایت به‌صورت اجباری برای عموم فعال شد؛ موارد ناقص را در اولین فرصت تکمیل کنید. ⚠️', 'warning')
            else:
                flash('سایت برای عموم فعال شد. ✅' if value == '1' else
                      'سایت از دسترس عموم خارج شد؛ مدیر همچنان پیش‌نمایش کامل دارد.',
                      'success' if value == '1' else 'info')
            return redirect(url_for('admin.go_live'))

        for key in keys:
            if key not in request.form:
                continue
            value = request.form.get(key, '').strip()
            if key in _SECRET_SETTING_KEYS and not value:
                continue
            if key in ('refund_days',):
                try:
                    value = str(max(0, min(90, int(value or 0))))
                except ValueError:
                    value = '0'
            elif key == 'shipping_flat_rate':
                try:
                    value = str(max(0, int(value or 0)))
                except ValueError:
                    value = '0'
            row = db.session.get(Setting, key)
            if row:
                row.value = value
            else:
                db.session.add(Setting(key=key, value=value))
        db.session.commit()
        clear = getattr(current_app, 'clear_cache', None)
        if callable(clear):
            clear()
        flash('اطلاعات راه‌اندازی ذخیره شد. وضعیت بخش‌ها دوباره محاسبه شد.', 'success')
        return redirect(url_for('admin.go_live'))

    values = {row.key: row.value for row in Setting.query.all()}
    (checks, launch_ready, courses_count, products_count,
     paid_content, current_license) = _readiness(values)
    score = round(sum(1 for ready in checks.values() if ready) * 100 / len(checks))
    return render_template('admin/go_live.html', vals=values, checks=checks,
                           score=score, courses_count=courses_count,
                           products_count=products_count,
                           launch_ready=launch_ready, paid_content=paid_content,
                           current_license=current_license,
                           is_super=g.user.role == 'super_admin',
                           site_active=values.get('site_active', '1') == '1')


# ---------------------------------------------------------------- دوره‌ها
@admin_bp.route('/courses')
@admin_required
def courses():
    q = request.args.get('q', '').strip()
    query = Course.query
    if q:
        query = query.filter(Course.title.contains(q))
    all_courses = query.order_by(Course.created_at.desc()).all()
    return render_template('admin/courses.html', courses=all_courses, q=q)


@admin_bp.route('/courses/new', methods=['GET', 'POST'])
@admin_required
def course_new():
    return _course_form(None)


@admin_bp.route('/courses/<int:cid>/edit', methods=['GET', 'POST'])
@admin_required
def course_edit(cid):
    course = db.get_or_404(Course, cid)
    return _course_form(course)


def _course_form(course):
    from app import THEMES
    teachers = User.query.filter(User.role.in_(['teacher', 'admin'])).all()
    categories = Category.query.all()
    images = ['cover-python.webp', 'cover-flask.webp', 'cover-django.webp', 'cover-react.webp',
              'cover-ml.webp', 'cover-uiux.webp', 'cover-excel.webp', 'cover-marketing.webp',
              'cover-android.webp', 'cover-wordpress.svg', 'cover-english.svg', 'cover-security.svg']
    if request.method == 'POST':
        f = request.form
        was_new = course is None
        if was_new:
            course = Course()
        course.title = f.get('title', '').strip()
        from models import unique_slug_for as _usf
        _slug_src = (f.get('slug') or '').strip() or course.title
        if _slug_src:
            course.slug = _usf(Course, _slug_src, exclude_id=getattr(course, 'id', None), fallback='course')
        elif not getattr(course, 'slug', None):
            course.slug = _usf(Course, course.title or 'course', exclude_id=getattr(course, 'id', None), fallback='course')
        if was_new:
            db.session.add(course)
        course.subtitle = f.get('subtitle', '').strip()
        course.description = f.get('description', '').strip()
        course.category_id = int(f.get('category_id') or 0) or None
        course.teacher_id = int(f.get('teacher_id') or 0) or None
        course.price = int(f.get('price') or 0)
        course.discount_price = int(f.get('discount_price') or 0)
        course.level = f.get('level', 'مقدماتی')
        course.duration_hours = int(f.get('duration_hours') or 0)
        course.image = f.get('image') or 'course-placeholder.webp'
        course.status = f.get('status', 'published') or 'published'
        course.featured = bool(f.get('featured'))
        course.what_you_learn = f.get('what_you_learn', '').strip()
        course.requirements = f.get('requirements', '').strip()
        course.tags = f.get('tags', '').strip()
        _iv = f.get('intro_video', '').strip()
        if _iv and not (_iv.startswith(('http://', 'https://', '/')) or 'youtube' in _iv or 'aparat' in _iv or 'vimeo' in _iv):
            _iv = ''
        course.intro_video = _iv
        course.access_days = int(f.get('access_days') or 0)
        course.delivery_type = f.get('delivery_type', 'online')
        from models import DELIVERY_TYPES
        if course.delivery_type not in DELIVERY_TYPES:
            course.delivery_type = 'online'
        course.allow_download = bool(f.get('allow_download'))
        try:
            course.attendance_required_percent = max(0, min(100, int(f.get('attendance_required_percent') or 75)))
        except (TypeError, ValueError):
            course.attendance_required_percent = 75
        course.audience = f.get('audience', '').strip()
        # سهم درآمد مدرس این دوره (٪) — خالی یعنی پیش‌فرض سایت
        _rev_raw = f.get('revenue_percent', '').strip()
        if _rev_raw == '':
            course.revenue_percent = None
        else:
            try:
                course.revenue_percent = max(0, min(100, int(_rev_raw)))
            except (TypeError, ValueError):
                course.revenue_percent = None
        # تعداد جلسات بازشونده به ازای هر قسط (۰ = همه باز)
        try:
            course.unlock_per_installment = max(0, min(500, int(f.get('unlock_per_installment') or 0)))
        except (TypeError, ValueError):
            course.unlock_per_installment = 0
        # مدرس‌های کمکی + درصد سهم هر کدام (باگ قبلی: انتخاب‌ها هرگز ذخیره نمی‌شد)
        try:
            from models import CourseTeacher as _CT
            db.session.flush()  # دوره جدید id بگیرد تا لینک‌ها قابل حذف/ساخت باشند
            _CT.query.filter_by(course_id=course.id).delete()
            selected_ids = []
            for raw in f.getlist('co_teacher_ids'):
                for piece in raw.split(','):
                    piece = piece.strip()
                    if piece.isdigit() and int(piece) not in selected_ids:
                        selected_ids.append(int(piece))
            if course.teacher_id in selected_ids:
                selected_ids.remove(course.teacher_id)
            for tid in selected_ids:
                share_raw = f.get('co_share_{}'.format(tid), '').strip()
                share = None
                if share_raw.isdigit():
                    share = max(0, min(100, int(share_raw)))
                db.session.add(_CT(course_id=course.id, teacher_id=tid,
                                   share_percent=share))
        except Exception:
            _lexc('blueprints/admin_bp.py')
        if not course.title:
            flash('عنوان دوره الزامی است.', 'error')
        else:
            # اعلان تخفیف جدید به علاقه‌مندان دوره
            try:
                from models import Notification, Favorite
                if course.discount_price and course.discount_price < course.price:
                    fans = Favorite.query.filter_by(course_id=course.id).all()
                    for fav in fans:
                        Notification.notify(fav.user_id,
                                            'تخفیف جدید روی دوره مورد علاقه شما 🎉',
                                            f'«{course.title}» حالا با تخفیف ویژه در دسترس است.',
                                            '🔥', url_for('site.course_detail', slug=course.slug))
                    if fans:
                        db.session.commit()
            except Exception:
                _lexc('blueprints/admin_bp.py')
            # ایندکس سریع در Bing — فقط دوره‌های منتشرشده
            try:
                if course.status == 'published' and course.slug:
                    from integrations import submit_bing_async
                    submit_bing_async(request.host_url.rstrip('/') + url_for('site.course_detail', slug=course.slug))
            except Exception:
                _lexc('admin_bp.course_index')
            db.session.commit()
            try:
                from seo_service import ensure_meta
                ensure_meta('/course/' + (course.slug or str(course.id)))
                db.session.commit()
            except Exception:
                _lexc('blueprints/admin_bp.py')
            if course.status == 'published' and course.slug:
                flash('دوره ذخیره شد. آدرس عمومی: /course/' + course.slug, 'success')
            else:
                flash('دوره به‌صورت پیش‌نویس ذخیره شد و تا انتشار در سایت ۴۰۴ می‌دهد. از همین فرم وضعیت را «منتشر شده» کنید.', 'info')
            return redirect(url_for('admin.course_lessons', cid=course.id))
    return render_template('admin/course_form.html', course=course, teachers=teachers,
                           categories=categories, images=images)


@admin_bp.route('/courses/<int:cid>/delete', methods=['POST'])
@admin_required
def course_delete(cid):
    """حذف ایمن دوره — بدون یتیم‌کردن داده‌های وابسته.

    حذف فیزیکی دوره‌ای که دانشجو/سفارش/علاقه‌مندی/آزمون دارد، ردیف‌های وابسته را
    بدون FK-cascade بی‌سرپرست می‌کرد (enrollments، order_items، favorites،
    quizzes، assignments و...) و سپس داشبورد دانشجو/مدرس با
    ``NoneType.lesson_count`` خطای 500 می‌داد. برای دورهٔ دارای سوابق، به‌جای
    حذف، مدیر باید آن را «پیش‌نویس» کند؛ حذف فیزیکی فقط برای دوره‌های کاملاً
    خالی (بدون هیچ وابستگی) مجاز است.
    """
    course = db.get_or_404(Course, cid)
    from models import Enrollment, Favorite, OrderItem, Quiz, Assignment, BundleCourse, ForumTopic
    dependents = []
    if Enrollment.query.filter_by(course_id=course.id).first():
        dependents.append('ثبت‌نام دانشجویان')
    if OrderItem.query.filter_by(course_id=course.id).first():
        dependents.append('سفارش‌ها/فاکتورها')
    if Favorite.query.filter_by(course_id=course.id).first():
        dependents.append('علاقه‌مندی‌ها')
    if Quiz.query.filter_by(course_id=course.id).first():
        dependents.append('آزمون‌ها')
    if Assignment.query.filter_by(course_id=course.id).first():
        dependents.append('تمرین‌ها')
    if BundleCourse.query.filter_by(course_id=course.id).first():
        dependents.append('باندل‌ها')
    if ForumTopic.query.filter_by(course_id=course.id).first():
        dependents.append('تاپیک‌های انجمن')
    if dependents:
        flash('این دوره قابل حذف نیست؛ سوابق وابسته دارد: ' +
              '، '.join(dependents) +
              '. برای مخفی‌کردن آن، وضعیت را به «پیش‌نویس» تغییر دهید.', 'error')
        return redirect(url_for('admin.courses'))
    db.session.delete(course)
    db.session.commit()
    flash('دوره حذف شد.', 'info')
    return redirect(url_for('admin.courses'))


@admin_bp.route('/courses/<int:cid>/lessons', methods=['GET', 'POST'])
@admin_required
def course_lessons(cid):
    """مدیریت سکشن‌ها و جلسات دوره"""
    course = db.get_or_404(Course, cid)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_section':
            title = request.form.get('title', '').strip()
            if title:
                db.session.add(Section(course_id=course.id, title=title,
                                       sort=len(course.sections)))
                db.session.commit()
                flash('سکشن اضافه شد.', 'success')
        elif action == 'del_section':
            sec = db.session.get(Section, safe_int(request.form.get('sid')))
            if sec and sec.course_id == course.id:
                db.session.delete(sec)
                db.session.commit()
                flash('سکشن حذف شد.', 'info')
        elif action == 'add_lesson':
            sec = db.session.get(Section, safe_int(request.form.get('section_id')))
            title = request.form.get('title', '').strip()
            if sec and sec.course_id == course.id and title:
                fl = _save_lesson_file(request.files.get('file'))
                # اعلان جلسه جدید به دانشجویان دوره
                try:
                    from models import Notification
                    students = Enrollment.query.filter_by(course_id=course.id).all()
                    for en in students:
                        Notification.notify(en.user_id, 'جلسه جدید منتشر شد 🎬',
                                            f'«{title}» به دوره {course.title[:30]} اضافه شد.',
                                            '🎬', url_for('student.learn', course_id=course.id))
                except Exception:
                    _lexc('blueprints/admin_bp.py')
                _vurl = request.form.get('video_url', '').strip()
                _vtype = request.form.get('video_type', 'direct')
                try:
                    from validators import detect_video
                    _kind, _ = detect_video(_vurl)
                    if _kind != 'none':
                        _vtype = _kind
                except Exception:
                    _lexc('admin_bp.lesson_detect')
                db.session.add(Lesson(section_id=sec.id, title=title,
                                      video_type=_vtype,
                                      video_url=_vurl,
                                      file_url=fl['url'] if fl else None,
                                      file_name=fl['name'] if fl else None,
                                      file_size=fl['size'] if fl else None,
                                      duration=request.form.get('duration') or '00:10:00',
                                      release_days=request.form.get('release_days', 0, type=int),
                                      is_free=bool(request.form.get('is_free')),
                                      content=request.form.get('content', '').strip(),
                                      sort=len(sec.lessons)))
                db.session.commit()
                flash('جلسه اضافه شد.', 'success')
        elif action == 'edit_lesson':
            les = db.session.get(Lesson, safe_int(request.form.get('lid')))
            if les:
                les.title = request.form.get('title', '').strip() or les.title
                les.video_url = request.form.get('video_url', '').strip()
                les.video_type = request.form.get('video_type', les.video_type)
                try:
                    from validators import detect_video
                    _kind, _ = detect_video(les.video_url)
                    if _kind != 'none':
                        les.video_type = _kind
                except Exception:
                    _lexc('admin_bp.lesson_edit_detect')
                les.duration = request.form.get('duration') or les.duration
                les.release_days = request.form.get('release_days', 0, type=int)
                les.is_free = bool(request.form.get('is_free'))
                les.content = request.form.get('content', '').strip()
                fl = _save_lesson_file(request.files.get('file'))
                if fl:
                    les.file_url, les.file_name, les.file_size = fl['url'], fl['name'], fl['size']
                db.session.commit()
                flash('جلسه ویرایش شد.', 'success')
        elif action == 'del_lesson':
            les = db.session.get(Lesson, safe_int(request.form.get('lid')))
            if les and les.section.course_id == course.id:
                db.session.delete(les)
                db.session.commit()
                flash('جلسه حذف شد.', 'info')
        return redirect(url_for('admin.course_lessons', cid=course.id))
    return render_template('admin/course_lessons.html', course=course)


# ---------------------------------------------------------------- دسته‌بندی‌ها
@admin_bp.route('/categories', methods=['GET', 'POST'])
@admin_required
def categories():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name', '').strip()
            if name and not Category.query.filter_by(name=name).first():
                db.session.add(Category(name=name, slug=slugify(name), icon=request.form.get('icon', '📚'),
                                        color=request.form.get('color', '#2563eb'),
                                        description=request.form.get('description', ''),
                                        sort=safe_int(request.form.get('sort'))))
                db.session.commit()
                flash('دسته‌بندی اضافه شد.', 'success')
        elif action == 'delete':
            c = db.session.get(Category, safe_int(request.form.get('cid')))
            if c:
                db.session.delete(c)
                db.session.commit()
                flash('دسته‌بندی حذف شد.', 'info')
        return redirect(url_for('admin.categories'))
    cats = Category.query.order_by(Category.sort).all()
    return render_template('admin/categories.html', cats=cats)


# ---------------------------------------------------------------- کاربران
@admin_bp.route('/users')
@admin_required
def users():
    q = request.args.get('q', '').strip()
    query = User.query
    if q:
        query = query.filter(User.name.contains(q) | User.email.contains(q))
    all_users = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users, q=q)


@admin_bp.route('/users/<int:uid>/role', methods=['POST'])
@admin_required
def user_role(uid):
    if g.user.role not in ('admin', 'super_admin'):
        abort(403)
    from models import ROLES
    user = db.get_or_404(User, uid)
    if user.id == g.user.id:
        flash('برای جلوگیری از قفل‌شدن پنل، نمی‌توانید نقش حساب فعلی خود را تغییر دهید.', 'error')
        return redirect(url_for('admin.users'))
    new_role = request.form.get('role', 'student').strip()
    if new_role not in ROLES:
        abort(400)
    # فقط سوپرادمین می‌تواند نقش‌های مدیریتی را اعطا/تغییر دهد. کارکنان عملیاتی
    # حتی با دسترسی سفارشی edit_users نمی‌توانند سطح دسترسی خود را بالا ببرند.
    privileged = {'admin', 'super_admin'}
    if (user.role in privileged or new_role in privileged) and \
            g.user.role != 'super_admin':
        abort(403)
    user.role = new_role
    user.new_session_token()  # نقش جدید فوراً روی همه سشن‌های قبلی اعمال شود
    db.session.commit()
    flash('نقش کاربر به‌روزرسانی شد.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:uid>/toggle', methods=['POST'])
@admin_required
def user_toggle(uid):
    user = db.get_or_404(User, uid)
    if user.id == g.user.id:
        flash('نمی‌توانید حسابی را که اکنون با آن وارد شده‌اید غیرفعال کنید.', 'error')
        return redirect(url_for('admin.users'))
    if user.role in ('admin', 'super_admin') and g.user.role != 'super_admin':
        abort(403)
    user.is_active = not user.is_active
    user.new_session_token()
    db.session.commit()
    flash('وضعیت کاربر تغییر کرد.', 'success')
    return redirect(url_for('admin.users'))


# ---------------------------------------------------------------- سفارش‌ها
@admin_bp.route('/orders')
@admin_required
def orders():
    status = request.args.get('status', '')
    query = Order.query
    if status:
        query = query.filter(Order.status == status)
    # صفحه‌بندی — قبلاً همه سفارش‌ها (هزاران ردیف) یکجا بارگذاری و رندر می‌شد
    try:
        page = max(1, request.args.get('page', 1, type=int))
    except Exception:
        page = 1
    per_page = 50
    total = query.count()
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    all_orders = query.order_by(Order.created_at.desc()) \
        .offset((page - 1) * per_page).limit(per_page).all()
    return render_template('admin/orders.html', orders=all_orders, status=status,
                           page=page, pages=pages, total=total)


@admin_bp.route('/orders/<int:oid>')
@admin_required
def order_detail(oid):
    order = db.get_or_404(Order, oid)
    proofs = PaymentProof.query.filter_by(order_id=oid).order_by(PaymentProof.created_at.desc()).all()
    return render_template('admin/order_detail.html', order=order, proofs=proofs)


@admin_bp.route('/orders/<int:oid>/fulfillment', methods=['POST'])
@admin_required
def order_fulfillment(oid):
    order = db.get_or_404(Order, oid)
    if order.fulfillment_status == 'not_required':
        abort(400)
    status = request.form.get('status', '')
    if status not in ('stock_issue', 'processing', 'shipped', 'delivered'):
        abort(400)
    order.fulfillment_status = status
    db.session.commit()
    flash('وضعیت ارسال سفارش ذخیره شد.', 'success')
    return redirect(url_for('admin.order_detail', oid=oid))


@admin_bp.route('/proofs/<int:pid>/verify', methods=['POST'])
@admin_required
def proof_verify(pid):
    """تایید فیش کارت‌به‌کارت → فعال‌سازی سفارش و ثبت‌نام خودکار"""
    proof = db.get_or_404(PaymentProof, pid)
    action = request.form.get('action', '')
    if action == 'approve':
        order = proof.order
        if int(proof.amount or 0) != int(order.final_total or 0):
            flash('مبلغ فیش با مبلغ نهایی سفارش یکسان نیست؛ فیش تایید نشد.', 'error')
            return redirect(url_for('admin.order_detail', oid=order.id))
        from blueprints.shop import _mark_paid
        if not _mark_paid(order, 'C2C-' + proof.ref_number, 'card2card_verified'):
            flash('وضعیت سفارش تغییر نکرد؛ احتمالاً قبلاً پردازش شده است.', 'error')
            return redirect(url_for('admin.order_detail', oid=order.id))
        proof.status = 'approved'
        proof.verified_at = utcnow()
        proof.admin_note = request.form.get('note', '')
        db.session.add(proof)
        db.session.commit()
        flash(f'فیش سفارش {order.code} تایید و سفارش فعال شد. ✅', 'success')
    elif action == 'reject':
        proof.status = 'rejected'
        proof.admin_note = request.form.get('note', '')
        order = proof.order
        order.status = 'pending'
        db.session.commit()
        flash('فیش رد شد و سفارش به حالت در انتظار بازگشت.', 'info')
    return redirect(safe_referrer(url_for('admin.orders')))


@admin_bp.route('/proofs')
@admin_required
def proofs():
    """فهرست فیش‌های واریزی"""
    status = request.args.get('status', '')
    query = PaymentProof.query
    if status:
        query = query.filter(PaymentProof.status == status)
    items = query.order_by(PaymentProof.created_at.desc()).all()
    return render_template('admin/proofs.html', proofs=items, status=status)


# ---------------------------------------------------------------- کوپن‌ها
@admin_bp.route('/coupons', methods=['GET', 'POST'])
@admin_required
def coupons():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            code = request.form.get('code', '').strip().upper()
            if code and not Coupon.query.filter_by(code=code).first():
                exp = request.form.get('expires_at', '').strip()
                db.session.add(Coupon(
                    code=code, type=request.form.get('type', 'percent'),
                    value=safe_int(request.form.get('value')),
                    max_uses=safe_int(request.form.get('max_uses')),
                    min_amount=safe_int(request.form.get('min_amount')),
                    expires_at=(lambda _e: datetime.strptime(_e, '%Y-%m-%d') if _e else None)(
                        __import__('app', fromlist=['jalali_to_gregorian']).jalali_to_gregorian(exp) if exp else None)))
                db.session.commit()
                flash('کوپن ساخته شد.', 'success')
        elif action == 'delete':
            c = db.session.get(Coupon, safe_int(request.form.get('cid')))
            if c:
                db.session.delete(c)
                db.session.commit()
                flash('کوپن حذف شد.', 'info')
        return redirect(url_for('admin.coupons'))
    all_coupons = Coupon.query.all()
    return render_template('admin/coupons.html', coupons=all_coupons)


# ---------------------------------------------------------------- وبلاگ
@admin_bp.route('/blog', methods=['GET', 'POST'])
@admin_required
def blog():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'delete':
            p = db.session.get(BlogPost, safe_int(request.form.get('pid')))
            if p:
                db.session.delete(p)
                db.session.commit()
                flash('مطلب حذف شد.', 'info')
        return redirect(url_for('admin.blog'))
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template('admin/blog.html', posts=posts)


@admin_bp.route('/blog/new', methods=['GET', 'POST'])
@admin_required
def blog_new():
    return _blog_form(None)


@admin_bp.route('/blog/<int:pid>/edit', methods=['GET', 'POST'])
@admin_required
def blog_edit(pid):
    post = db.get_or_404(BlogPost, pid)
    return _blog_form(post)


def _blog_form(post):
    from app import THEMES
    if request.method == 'POST':
        f = request.form
        if not post:
            post = BlogPost(author_id=g.user.id)
            from models import unique_slug_for as _usfb
            post.slug = _usfb(BlogPost, f.get('title', ''), fallback='post')
            db.session.add(post)
        post.title = f.get('title', '').strip()
        post.excerpt = f.get('excerpt', '').strip()
        post.body = f.get('body', '').strip()
        post.category = f.get('category', 'آموزش').strip()
        post.image = f.get('image', 'cover-python.webp')
        post.published = bool(f.get('published'))
        if not post.title:
            flash('عنوان الزامی است.', 'error')
        else:
            db.session.commit()
            try:
                from seo_service import ensure_meta
                ensure_meta('/blog/' + (post.slug or str(post.id)))
                db.session.commit()
            except Exception:
                _lexc('blueprints/admin_bp.py')
            flash('مطلب ذخیره شد.', 'success')
            return redirect(url_for('admin.blog'))
    images = ['cover-python.webp', 'cover-flask.webp', 'cover-django.webp', 'cover-react.webp',
              'cover-ml.webp', 'cover-uiux.webp', 'cover-excel.webp', 'cover-marketing.webp',
              'cover-android.webp', 'cover-wordpress.svg', 'cover-english.svg', 'cover-security.svg']
    return render_template('admin/blog_form.html', post=post, images=images)


# ---------------------------------------------------------------- نظرات دوره‌ها
@admin_bp.route('/reviews', methods=['GET', 'POST'])
@admin_required
def reviews():
    if request.method == 'POST':
        action = request.form.get('action')
        rid = safe_int(request.form.get('rid'))
        rv = db.session.get(Review, rid)
        if rv:
            if action == 'approve':
                rv.is_approved = True
                db.session.commit()
                flash('نظر تایید شد.', 'success')
            elif action == 'delete':
                db.session.delete(rv)
                db.session.commit()
                flash('نظر حذف شد.', 'info')
        return redirect(url_for('admin.reviews'))
    all_reviews = Review.query.order_by(Review.created_at.desc()).all()
    return render_template('admin/reviews.html', reviews=all_reviews)


# ---------------------------------------------------------------- گالری طراحی‌ها (پیش‌نمایش + انتخاب اصلی)
@admin_bp.route('/designs', methods=['GET', 'POST'])
@admin_required
def designs():
    """🖼 طراحی‌های سایت — ۲۰ طرح ایرانی + طرح‌های کلاسیک؛ انتخاب، پیش‌نمایش و اعمال"""
    from designs import HOME_DESIGNS, HOME_DESIGN_NAMES, SITE_DESIGNS
    from persian_themes import PERSIAN_THEMES, home_rows, CATEGORIES
    if request.method == 'POST':
        field = request.form.get('field', '')
        value = request.form.get('value', '')
        if field == 'site_design' and value in SITE_DESIGNS:
            s = db.session.get(Setting, field)
            if s:
                s.value = value
            else:
                db.session.add(Setting(key=field, value=value))
            db.session.commit()
            nm = SITE_DESIGNS[value]['name']
            flash(f'طرح «{nm}» به عنوان طراحی سراسری سایت انتخاب شد ✅', 'success')
            return redirect(url_for('admin.designs'))
        if field == 'home_reset' and value in SITE_DESIGNS:
            # بازنشانی چیدمان صفحه اصلی با ردیف‌های طرح (فقط با تأیید کاربر در سمت کلاینت)
            from persian_themes import get_theme
            t = get_theme(value)
            if t:
                page = Page.query.filter_by(slug='home').first()
                if page:
                    page.content = json.dumps({'settings': page.settings(), 'rows': home_rows(t)},
                                              ensure_ascii=False)
                    db.session.commit()
                    flash(f'صفحه اصلی با چیدمان طرح «{t["name"]}» بازنویسی شد ✅', 'success')
            return redirect(url_for('admin.designs'))
        if field in ('home_design', 'about_design', 'contact_design') and value:
            s = db.session.get(Setting, field)
            if s:
                s.value = value
            else:
                db.session.add(Setting(key=field, value=value))
            db.session.commit()
            flash('طراحی انتخابی ذخیره شد ✅', 'success')
        return redirect(url_for('admin.designs'))
    cur_site = db.session.get(Setting, 'site_design')
    cur_site = cur_site.value if cur_site else '1'
    return render_template('admin/designs.html',
                           persian_themes=PERSIAN_THEMES, categories=CATEGORIES,
                           home_designs=HOME_DESIGNS, home_names=HOME_DESIGN_NAMES,
                           site_designs=SITE_DESIGNS,
                           cur_site=cur_site,
                           cur_home=db.session.get(Setting, 'home_design').value if db.session.get(Setting, 'home_design') else '1',
                           cur_about=db.session.get(Setting, 'about_design').value if db.session.get(Setting, 'about_design') else '1',
                           cur_contact=db.session.get(Setting, 'contact_design').value if db.session.get(Setting, 'contact_design') else '1')


# ---------------------------------------------------------------- پشتیبان‌گیری
@admin_bp.route('/backup')
@admin_required
def backup():
    import shutil
    import tempfile
    from flask import send_file, after_this_request
    src_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'instance', 'academy.db')
    if os.path.exists(src_db):
        temp_dir = os.path.join(os.path.dirname(src_db), 'backups')
        os.makedirs(temp_dir, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix='academy-download-', suffix='.db', dir=temp_dir)
        os.close(fd)
        shutil.copy2(src_db, tmp)

        @after_this_request
        def _cleanup(response):
            try:
                os.remove(tmp)
            except OSError:
                pass
            return response

        return send_file(tmp, as_attachment=True, download_name='academy-backup.db')
    flash('فایل دیتابیس پیدا نشد.', 'error')
    return redirect(url_for('admin.overview'))


# ---------------------------------------------------------------- پیام‌ها و خبرنامه
@admin_bp.route('/messages')
@admin_required
def messages():
    msgs = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template('admin/messages.html', msgs=msgs)


@admin_bp.route('/newsletters')
@admin_required
def newsletters():
    emails = NewsletterEmail.query.order_by(NewsletterEmail.created_at.desc()).all()
    return render_template('admin/newsletters.html', emails=emails)


# ---------------------------------------------------------------- تیکت‌ها
@admin_bp.route('/tickets', methods=['GET', 'POST'])
@admin_required
def tickets():
    if request.method == 'POST':
        action = request.form.get('action')
        t = db.session.get(Ticket, safe_int(request.form.get('tid')))
        if t:
            if action == 'reply':
                reply_text = request.form.get('reply', '').strip()
                t.admin_reply = reply_text
                t.status = 'answered'
                t.answered_at = utcnow()
                if not t.first_response_at:
                    t.first_response_at = utcnow()
                t.priority = request.form.get('priority', t.priority)
                t.category = request.form.get('category', t.category)
                db.session.add(TicketReply(ticket_id=t.id, user_id=g.user.id,
                                           body=reply_text, is_admin=True))
                from models import Notification
                Notification.notify(t.user_id, 'پاسخ تیکت شما ثبت شد',
                                    reply_text[:100], '🎫',
                                    url_for('student.tickets'))
                try:
                    from email_service import send_ticket_reply
                    tu = db.session.get(User, t.user_id)
                    if tu and tu.email and reply_text:
                        send_ticket_reply(tu, t, reply_text, g.settings)
                except Exception:
                    _lexc('blueprints/admin_bp.py')
            elif action == 'assign':
                t.assigned_to = request.form.get('assigned_to', type=int) or None
                flash('تیکت ارجاع شد.', 'info')
            elif action == 'priority':
                t.priority = request.form.get('priority', 'normal')
            elif action == 'category':
                t.category = request.form.get('category', 'عمومی')
            elif action == 'close':
                t.status = 'closed'
            db.session.commit()
            flash('تیکت به‌روزرسانی شد.', 'success')
        return redirect(safe_referrer(url_for('admin.tickets')))
    status = request.args.get('status', '')
    prio = request.args.get('priority', '')
    cat = request.args.get('cat', '')
    q = Ticket.query
    if status:
        q = q.filter(Ticket.status == status)
    if prio:
        q = q.filter(Ticket.priority == prio)
    if cat:
        q = q.filter(Ticket.category == cat)
    tickets = q.order_by(Ticket.created_at.desc()).all()
    supports = User.query.filter(User.role.in_(['support', 'admin', 'super_admin'])).all()
    return render_template('admin/tickets.html', tickets=tickets, supports=supports,
                           status=status, prio=prio, cat=cat)


@admin_bp.route('/tickets/<int:tid>')
@admin_required
def ticket_detail(tid):
    """تاریخچه کامل مکالمه تیکت"""
    t = db.get_or_404(Ticket, tid)
    replies = TicketReply.query.filter_by(ticket_id=tid).order_by(TicketReply.created_at.asc()).all()
    supports = User.query.filter(User.role.in_(['support', 'admin', 'super_admin'])).all()
    return render_template('admin/ticket_detail.html', t=t, replies=replies, supports=supports)


@admin_bp.route('/tickets/<int:tid>/reply-file', methods=['POST'])
@admin_required
def ticket_reply_file(tid):
    """پاسخ با فایل پیوست"""
    t = db.get_or_404(Ticket, tid)
    f = request.files.get('attachment')
    body = request.form.get('body', '').strip() or '📎 فایل پیوست'
    fname = None
    if f and f.filename:
        import os as _os
        from uploads_helper import uploads_dir
        up = uploads_dir('tickets')
        from validators import safe_filename
        safe = safe_filename(f.filename or '')
        if safe:
            fname = 't_' + uuid.uuid4().hex[:8] + _os.path.splitext(safe)[1]
            f.save(_os.path.join(up, fname))
            t.attachment = fname
    db.session.add(TicketReply(ticket_id=t.id, user_id=g.user.id, body=body, is_admin=True,
                               attachment=fname))
    t.status = 'answered'
    t.answered_at = utcnow()
    if not t.first_response_at:
        t.first_response_at = utcnow()
    db.session.commit()
    flash('پاسخ با پیوست ثبت شد.', 'success')
    return redirect(url_for('admin.ticket_detail', tid=tid))


@admin_bp.route('/tickets/report')
@admin_required
def tickets_report():
    """گزارش عملکرد پشتیبان‌ها و میانگین زمان پاسخ"""
    support_ids = [u.id for u in User.query.filter(User.role.in_(['support', 'admin'])).all()]
    rows = []
    for sid in support_ids:
        u = db.session.get(User, sid)
        answered = Ticket.query.filter(Ticket.assigned_to == sid).count()
        samples = []
        for t in Ticket.query.filter(Ticket.assigned_to == sid,
                                     Ticket.first_response_at.isnot(None)).all():
            samples.append((t.first_response_at - t.created_at).total_seconds() / 3600)
        avg_h = round(sum(samples) / len(samples), 1) if samples else None
        rows.append({'user': u.name if u else '—', 'answered': answered, 'avg_h': avg_h})
    total_tickets = Ticket.query.count()
    open_tickets = Ticket.query.filter(Ticket.status.in_(['open', 'answered'])).count()
    samples = []
    for t in Ticket.query.filter(Ticket.first_response_at.isnot(None)).all():
        samples.append((t.first_response_at - t.created_at).total_seconds() / 3600)
    avg_all = round(sum(samples) / len(samples), 1) if samples else None
    return render_template('admin/tickets_report.html', rows=rows,
                           total=total_tickets, open_t=open_tickets, avg_all=avg_all)


@admin_bp.route('/activity')
@admin_required
def activity():
    """لاگ فعالیت کاربران"""
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(200).all()
    return render_template('admin/activity.html', logs=logs)




# ================================================================
# آزمون‌ها
# ================================================================
@admin_bp.route('/quizzes')
@admin_required
def quizzes():
    items = Quiz.query.order_by(Quiz.created_at.desc()).all()
    return render_template('admin/quizzes.html', quizzes=items)


@admin_bp.route('/quizzes/new', methods=['GET', 'POST'])
@admin_required
def quiz_new():
    courses = Course.query.order_by(Course.title).all()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        cid = request.form.get('course_id', type=int)
        passing = request.form.get('passing_score', 50, type=int)
        is_placement = bool(request.form.get('is_placement'))
        if not title or not cid:
            flash('عنوان و دوره الزامی است.', 'error')
        else:
            q = Quiz(course_id=cid, title=title,
                     description=request.form.get('description', '').strip(),
                     passing_score=passing, is_placement=is_placement,
                     time_limit=request.form.get('time_limit', 0, type=int))
            db.session.add(q)
            db.session.commit()
            _save_questions(q, request.form.get('questions_raw', ''))
            flash('آزمون ساخته شد. حالا سوالات را تکمیل کنید.', 'success')
            return redirect(url_for('admin.quiz_edit', qid=q.id))
    return render_template('admin/quiz_form.html', quiz=None, courses=courses)


@admin_bp.route('/quizzes/<int:qid>/edit', methods=['GET', 'POST'])
@admin_required
def quiz_edit(qid):
    q = db.get_or_404(Quiz, qid)
    courses = Course.query.order_by(Course.title).all()
    if request.method == 'POST':
        q.title = request.form.get('title', q.title).strip()
        q.description = request.form.get('description', '').strip()
        q.passing_score = request.form.get('passing_score', 50, type=int)
        q.time_limit = request.form.get('time_limit', 0, type=int)
        q.course_id = request.form.get('course_id', q.course_id, type=int)
        _save_questions(q, request.form.get('questions_raw', ''))
        db.session.commit()
        flash('آزمون به‌روزرسانی شد.', 'success')
        return redirect(url_for('admin.quizzes'))
    return render_template('admin/quiz_form.html', quiz=q, courses=courses)


def _save_questions(q, raw):
    """فرمت هر خط: سوال | گزینه۱،گزینه۲،گزینه۳،گزینه۴ | شاخص_درست | توضیح"""
    import json as _json
    for old in q.questions:
        db.session.delete(old)
    db.session.flush()
    n = 0
    for line in (raw or '').split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 2:
            continue
        choices = [c.strip() for c in parts[1].split('،') if c.strip()]
        if len(choices) < 2:
            continue
        try:
            correct = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        except Exception:
            correct = 0
        db.session.add(QuizQuestion(quiz_id=q.id, text=parts[0],
                                    choices=_json.dumps(choices, ensure_ascii=False),
                                    correct_index=max(0, min(correct, len(choices) - 1)),
                                    explanation=parts[3] if len(parts) > 3 else '',
                                    sort=n))
        n += 1


@admin_bp.route('/quizzes/<int:qid>/delete', methods=['POST'])
@admin_required
def quiz_delete(qid):
    q = db.get_or_404(Quiz, qid)
    db.session.delete(q)
    db.session.commit()
    flash('آزمون حذف شد.', 'info')
    return redirect(url_for('admin.quizzes'))


# ================================================================
# تمرین‌ها و پاسخ‌ها
# ================================================================
@admin_bp.route('/assignments')
@admin_required
def assignments():
    items = Assignment.query.order_by(Assignment.created_at.desc()).all()
    return render_template('admin/assignments.html', items=items)


@admin_bp.route('/assignments/new', methods=['GET', 'POST'])
@admin_required
def assignment_new():
    courses = Course.query.order_by(Course.title).all()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        cid = request.form.get('course_id', type=int)
        if not title or not cid:
            flash('عنوان و دوره الزامی است.', 'error')
        else:
            db.session.add(Assignment(course_id=cid, title=title,
                                      description=request.form.get('description', '').strip(),
                                      max_score=request.form.get('max_score', 100, type=int)))
            db.session.commit()
            flash('تمرین ساخته شد.', 'success')
            return redirect(url_for('admin.assignments'))
    return render_template('admin/assignment_form.html', item=None, courses=courses)


@admin_bp.route('/assignments/<int:aid>/delete', methods=['POST'])
@admin_required
def assignment_delete(aid):
    a = db.get_or_404(Assignment, aid)
    db.session.delete(a)
    db.session.commit()
    flash('تمرین حذف شد.', 'info')
    return redirect(url_for('admin.assignments'))


@admin_bp.route('/submissions')
@admin_required
def submissions():
    status = request.args.get('status', '')
    query = AssignmentSubmission.query
    if status:
        query = query.filter(AssignmentSubmission.status == status)
    items = query.order_by(AssignmentSubmission.created_at.desc()).all()
    return render_template('admin/submissions.html', items=items, status=status)


@admin_bp.route('/submissions/<int:sid>/grade', methods=['POST'])
@admin_required
def submission_grade(sid):
    sub = db.get_or_404(AssignmentSubmission, sid)
    sub.score = request.form.get('score', 0, type=int)
    sub.feedback = request.form.get('feedback', '').strip()
    sub.status = 'graded'
    sub.graded_at = utcnow()
    db.session.commit()
    flash('نمره ثبت شد.', 'success')
    return redirect(safe_referrer(url_for('admin.submissions')))


# ================================================================
# پرسش‌های درسی
# ================================================================
@admin_bp.route('/lesson-questions')
@admin_required
def lesson_questions():
    items = LessonQuestion.query.filter(LessonQuestion.answer.is_(None)) \
        .order_by(LessonQuestion.created_at.desc()).all()
    return render_template('admin/lesson_questions.html', items=items)


@admin_bp.route('/lesson-questions/<int:qid>/answer', methods=['POST'])
@admin_required
def lesson_question_answer(qid):
    q = db.get_or_404(LessonQuestion, qid)
    q.answer = request.form.get('answer', '').strip()
    q.answered_at = utcnow()
    db.session.commit()
    flash('پاسخ ثبت شد.', 'success')
    return redirect(url_for('admin.lesson_questions'))


# ================================================================
# باندل‌ها
# ================================================================
@admin_bp.route('/bundles')
@admin_required
def bundles():
    items = Bundle.query.all()
    return render_template('admin/bundles.html', items=items)


@admin_bp.route('/bundles/new', methods=['GET', 'POST'])
@admin_required
def bundle_new():
    courses = Course.query.filter_by(status='published').all()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        slug = request.form.get('slug', '').strip() or title
        import re as _re
        slug = _re.sub(r'[^\w\u0600-\u06FF-]+', '-', slug).strip('-')
        if not title:
            flash('عنوان الزامی است.', 'error')
        else:
            b = Bundle(title=title, slug=slug,
                       description=request.form.get('description', '').strip(),
                       price=request.form.get('price', 0, type=int),
                       discount_price=request.form.get('discount_price', 0, type=int),
                       image=request.form.get('image') or 'course-placeholder.webp')
            db.session.add(b)
            db.session.flush()
            for cid in request.form.getlist('course_ids'):
                c = db.session.get(Course, int(cid))
                if c:
                    db.session.add(BundleCourse(bundle_id=b.id, course_id=c.id))
            db.session.commit()
            flash('باندل ساخته شد.', 'success')
            return redirect(url_for('admin.bundles'))
    return render_template('admin/bundle_form.html', item=None, courses=courses)


@admin_bp.route('/bundles/<int:bid>/edit', methods=['GET', 'POST'])
@admin_required
def bundle_edit(bid):
    """ویرایش باندل — عنوان، قیمت، دوره‌ها"""
    b = db.get_or_404(Bundle, bid)
    courses = Course.query.filter_by(status='published').all()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('عنوان الزامی است.', 'error')
        else:
            b.title = title
            b.description = request.form.get('description', '').strip()
            b.price = request.form.get('price', 0, type=int)
            b.discount_price = request.form.get('discount_price', 0, type=int)
            b.image = request.form.get('image') or b.image or 'course-placeholder.webp'
            b.is_active = bool(request.form.get('is_active'))
            for old in list(b.courses):
                b.courses.remove(old)
            for cid in request.form.getlist('course_ids'):
                c = db.session.get(Course, int(cid))
                if c and c not in b.courses:
                    b.courses.append(c)
            db.session.commit()
            flash('باندل به‌روزرسانی شد. ✏️', 'success')
            return redirect(url_for('admin.bundles'))
    return render_template('admin/bundle_form.html', item=b, courses=courses)


@admin_bp.route('/bundles/<int:bid>/delete', methods=['POST'])
@admin_required
def bundle_delete(bid):
    b = db.get_or_404(Bundle, bid)
    db.session.delete(b)
    db.session.commit()
    flash('باندل حذف شد.', 'info')
    return redirect(url_for('admin.bundles'))


@admin_bp.route('/gateways', methods=['GET', 'POST'])
@admin_required
def gateways():
    """مدیریت درگاه‌های پرداخت — فقط کدها را وارد کنید"""
    if request.method == 'POST':
        keys = ['c2c_card', 'c2c_name',
                'zarinpal_merchant', 'idpay_api_key', 'zibal_merchant',
                'parsian_login_account',
                'melli_terminal', 'melli_username', 'melli_password',
                'sepah_terminal',
                'sadad_merchant', 'sadad_terminal', 'sadad_key',
                'snapp_client_id', 'snapp_client_secret', 'snapp_merchant',
                'digipay_api_key', 'digipay_merchant',
                'tarb_api_url', 'tarb_api_key', 'tarb_merchant']
        for k in keys:
            v = request.form.get(k, '').strip()
            if k in _SECRET_SETTING_KEYS and not v:
                continue
            st = db.session.get(Setting, k)
            if st:
                st.value = v
            else:
                db.session.add(Setting(key=k, value=v))
        db.session.commit()
        flash('تنظیمات درگاه‌ها ذخیره شد. ✅', 'success')
        return redirect(url_for('admin.gateways'))
    return render_template('admin/gateways.html')


@admin_bp.route('/gateways/test/<gw>', methods=['POST'])
@admin_required
def gateway_test(gw):
    """تست اتصال درگاه — بدون تراکنش واقعی"""
    from gateways import test_gateway
    # اول ذخیره فیلدهای همین فرم
    keys = ['c2c_card', 'c2c_name',
            'zarinpal_merchant', 'idpay_api_key', 'zibal_merchant',
            'parsian_login_account',
            'melli_terminal', 'melli_username', 'melli_password',
            'sepah_terminal',
            'sadad_merchant', 'sadad_terminal', 'sadad_key',
            'snapp_client_id', 'snapp_client_secret', 'snapp_merchant',
            'digipay_api_key', 'digipay_merchant',
            'tarb_api_url', 'tarb_api_key', 'tarb_merchant']
    for k in keys:
        v = request.form.get(k, '').strip()
        if k in _SECRET_SETTING_KEYS and not v:
            continue
        st = db.session.get(Setting, k)
        if st:
            st.value = v
        elif v:
            db.session.add(Setting(key=k, value=v))
    db.session.commit()
    # خواندن تنظیمات تازه
    settings = {s.key: s.value for s in Setting.query.all()}
    ok, msg = test_gateway(gw, settings)
    flash(('✅ ' if ok else '❌ ') + msg, 'success' if ok else 'error')
    return redirect(url_for('admin.gateways'))



@admin_bp.route('/messengers', methods=['GET', 'POST'])
@admin_required
def messengers():
    """اتصال ربات‌های پیام‌رسان + ارسال همگانی"""
    from messengers import MESSENGERS, send_to_all
    results = None
    if request.method == 'POST':
        keys = []
        for m in MESSENGERS:
            keys += [m['token_key'], m['chat_key']]
        for k in keys:
            v = request.form.get(k, '').strip()
            st = db.session.get(Setting, k)
            if st:
                st.value = v
            elif v:
                db.session.add(Setting(key=k, value=v))
        db.session.commit()
        if request.form.get('action') == 'broadcast':
            text = request.form.get('broadcast_text', '').strip()
            link = request.form.get('broadcast_link', '').strip()
            if not text:
                flash('متن پیام را وارد کنید.', 'error')
            else:
                settings = {s.key: s.value for s in Setting.query.all()}
                results = send_to_all(text, settings, link or None)
                ok_count = sum(1 for ok, _ in results.values() if ok)
                flash(f'ارسال همگانی: {ok_count} پیام‌رسان با موفقیت. 📣', 'success')
        else:
            flash('تنظیمات پیام‌رسان‌ها ذخیره شد. ✅', 'success')
    settings = {s.key: s.value for s in Setting.query.all()}
    return render_template('admin/messengers.html', messengers=MESSENGERS,
                           site=settings, results=results)


@admin_bp.route('/messengers/test/<mid>', methods=['POST'])
@admin_required
def messenger_test(mid):
    """تست اتصال ربات یک پیام‌رسان"""
    from messengers import test_platform, MESSENGERS
    for m in MESSENGERS:
        for k in (m['token_key'], m['chat_key']):
            v = request.form.get(k, '').strip()
            st = db.session.get(Setting, k)
            if st:
                st.value = v
            elif v:
                db.session.add(Setting(key=k, value=v))
    db.session.commit()
    settings = {s.key: s.value for s in Setting.query.all()}
    ok, msg = test_platform(mid, settings)
    flash(('✅ ' if ok else '❌ ') + msg, 'success' if ok else 'error')
    return redirect(url_for('admin.messengers'))



@admin_bp.route('/sms', methods=['GET', 'POST'])
@admin_required
def sms_settings():
    """تنظیمات پیامک خودکار"""
    from sms import PROVIDERS, send_sms, test_sms
    if request.method == 'POST':
        keys = ['sms_provider', 'sms_kavenegar_key', 'sms_kavenegar_sender', 'sms_kavenegar_template',
                'sms_melli_username', 'sms_melli_password', 'sms_melli_sender',
                'sms_faraz_token', 'sms_faraz_sender', 'sms_test_phone']
        for k in keys:
            v = request.form.get(k, '').strip()
            if k in _SECRET_SETTING_KEYS and not v:
                continue
            st = db.session.get(Setting, k)
            if st:
                st.value = v
            elif v:
                db.session.add(Setting(key=k, value=v))
        db.session.commit()
        if request.form.get('action') == 'test':
            settings = {s.key: s.value for s in Setting.query.all()}
            ok, msg = test_sms(settings)
            flash(('✅ ' if ok else '❌ ') + msg, 'success' if ok else 'error')
        else:
            flash('تنظیمات پیامک ذخیره شد. ✅', 'success')
        return redirect(url_for('admin.sms_settings'))
    settings = {s.key: s.value for s in Setting.query.all()}
    return render_template('admin/sms.html', providers=PROVIDERS, site=settings)



@admin_bp.route('/optimizer', methods=['GET', 'POST'])
@admin_required
def optimizer():
    """بهینه‌ساز تصویر — غیرفعال؛ فشرده‌سازی خودکار هنگام آپلود."""
    flash('بهینه‌ساز دستی غیرفعال است. تصاویر هنگام آپلود به‌صورت خودکار فشرده می‌شوند.', 'info')
    return redirect(url_for('admin.media_library'))
    """legacy optimizer — kept unreachable"""
    from PIL import Image
    import os
    items = []
    fmt = request.form.get('fmt', 'webp') if request.method == 'POST' else 'webp'
    quality = safe_int(request.form.get('quality'), 80, 20, 95) if request.method == 'POST' else 80
    maxw = safe_int(request.form.get('maxw'), 0, 0, 8000) if request.method == 'POST' else 0
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'static', 'uploads', 'opt')
    os.makedirs(out_dir, exist_ok=True)
    if request.method == 'POST' and request.files.getlist('images'):
        for fobj in request.files.getlist('images'):
            if not fobj.filename:
                continue
            ext = os.path.splitext(fobj.filename)[1].lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
                continue
            try:
                im = Image.open(fobj.stream).convert('RGB')
                old_size = len(fobj.read()) if False else im.size
                fobj.stream.seek(0)
                if maxw and im.width > maxw:
                    h = round(im.height * maxw / im.width)
                    im = im.resize((maxw, h), Image.LANCZOS)
                base = os.path.splitext(os.path.basename(fobj.filename))[0]
                fname = f'{base}-opt.{fmt}'
                im.save(os.path.join(out_dir, fname), fmt.upper() if fmt == 'jpeg' else 'WEBP',
                        quality=quality, optimize=True)
                new_size = os.path.getsize(os.path.join(out_dir, fname))
                raw = Image.open(fobj.stream) if False else None
                fobj.stream.seek(0)
                import io
                raw_bytes = fobj.stream.read()
                items.append(dict(fname=fname, name=os.path.basename(fobj.filename),
                                  old_kb=round(len(raw_bytes)/1024), new_kb=round(new_size/1024),
                                  pct=round((1 - new_size/max(len(raw_bytes),1))*100)))
            except Exception as e:
                flash(f'خطا در {fobj.filename}: {str(e)[:80]}', 'error')
    # آمار پوشه img
    import glob
    img_files = glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       'static', 'img', '*.*'))
    img_files = [f for f in img_files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
    total = sum(os.path.getsize(f) for f in img_files)
    return render_template('admin/optimizer.html', items=items, fmt=fmt,
                           quality=quality, maxw=maxw,
                           img_count=len(img_files), total_mb=round(total/1024/1024, 1))


@admin_bp.route('/optimizer/bulk', methods=['POST'])
@admin_required
def optimizer_bulk():
    """بهینه‌سازی همه تصاویر پوشه static/img به WebP"""
    from PIL import Image
    import glob, os
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'img')
    out_dir = os.path.join(base, 'optimized')
    os.makedirs(out_dir, exist_ok=True)
    lines = []
    done = 0
    for f in glob.glob(os.path.join(base, '*.*')):
        if not f.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue
        try:
            im = Image.open(f).convert('RGB')
            name = os.path.splitext(os.path.basename(f))[0]
            out = os.path.join(out_dir, name + '.webp')
            im.save(out, 'WEBP', quality=80, method=6)
            old = os.path.getsize(f); new = os.path.getsize(out)
            lines.append(f'✅ {os.path.basename(f)}: {round(old/1024)}KB → {round(new/1024)}KB (−{round((1-new/old)*100)}٪)')
            done += 1
        except Exception as e:
            lines.append(f'❌ {os.path.basename(f)}: {str(e)[:60]}')
    lines.insert(0, f'بهینه‌سازی {done} فایل انجام شد. خروجی‌ها در static/img/optimized/')
    flash(f'{done} تصویر بهینه شد. ✅', 'success')
    return render_template('admin/optimizer.html', items=[], fmt='webp', quality=80,
                           maxw=0, img_count=0, total_mb=0, bulk=lines)



@admin_bp.route('/pages')
@admin_required
def pages():
    """لیست تمام صفحات + مدیریت (کپی/حذف موقت/بازیابی/نسخه‌ها)"""
    from models import Page, PageRevision
    items = Page.query.order_by(Page.ptype, Page.updated_at.desc()).all()
    types = {'home': 'خانه', 'header': 'هدر', 'footer': 'فوتر', 'mobile_menu': 'منوی موبایل',
             'page': 'صفحه', '404': 'خطای ۴۰۴', 'post': 'قالب مقاله'}
    return render_template('admin/pages.html', pages=items, types=types,
                           rev_count={p.id: PageRevision.query.filter_by(page_id=p.id).count() for p in items})


@admin_bp.route('/pages/<int:pid>/copy', methods=['POST'])
@admin_required
def page_copy(pid):
    """کپی گرفتن از صفحه"""
    from models import Page
    p = db.get_or_404(Page, pid)
    import uuid
    np = Page(title=p.title + ' (کپی)', slug=p.slug + '-copy-' + uuid.uuid4().hex[:4],
              ptype='page', content=p.content, is_published=False)
    db.session.add(np)
    db.session.commit()
    flash('کپی صفحه ساخته شد (پیش‌نویس). ✂️', 'success')
    return redirect(url_for('admin.pages'))


@admin_bp.route('/pages/<int:pid>/toggle', methods=['POST'])
@admin_required
def page_toggle(pid):
    """انتشار / پیش‌نویس"""
    from models import Page
    p = db.get_or_404(Page, pid)
    p.is_published = not p.is_published
    db.session.commit()
    flash('وضعیت انتشار تغییر کرد.', 'info')
    return redirect(safe_referrer(url_for('admin.pages')))


@admin_bp.route('/pages/<int:pid>/delete', methods=['POST'])
@admin_required
def page_delete(pid):
    """حذف موقت (فقط از فهرست — قابل بازیابی در بازیابی‌ها)"""
    from models import Page
    p = db.get_or_404(Page, pid)
    p.ptype = 'trash'
    p.is_published = False
    db.session.commit()
    flash('صفحه به سطل زباله منتقل شد (قابل بازیابی). 🗑', 'info')
    return redirect(url_for('admin.pages'))


@admin_bp.route('/pages/trash')
@admin_required
def pages_trash():
    """صفحات حذف‌شده موقت — بازیابی"""
    from models import Page
    items = Page.query.filter_by(ptype='trash').all()
    return render_template('admin/pages_trash.html', pages=items)


@admin_bp.route('/pages/<int:pid>/restore', methods=['POST'])
@admin_required
def page_restore(pid):
    from models import Page
    p = db.get_or_404(Page, pid)
    p.ptype = 'page'
    db.session.commit()
    flash('صفحه بازیابی شد. ♻️', 'success')
    return redirect(url_for('admin.pages'))


@admin_bp.route('/pages/<int:pid>/custom-theme', methods=['POST'])
@admin_required
def page_custom_theme(pid):
    """تعیین هدر/فوتر اختصاصی برای صفحه"""
    from models import Page
    p = db.get_or_404(Page, pid)
    p.custom_header = request.form.get('custom_header', '').strip() or None
    p.custom_footer = request.form.get('custom_footer', '').strip() or None
    db.session.commit()
    flash('هدر/فوتر اختصاصی صفحه ذخیره شد. 🎨', 'success')
    return redirect(url_for('admin.pages'))


@admin_bp.route('/pages/<int:pid>/schedule', methods=['POST'])
@admin_required
def page_schedule(pid):
    """زمان‌بندی انتشار صفحه"""
    from models import Page
    from datetime import datetime as _dt
    p = db.get_or_404(Page, pid)
    raw = request.form.get('publish_at', '').strip()
    if raw:
        try:
            from app import jalali_to_gregorian
            _parts = raw.strip().split()
            _date_part = _parts[0] if _parts else ''
            _time_part = _parts[1] if len(_parts) > 1 else '00:00'
            _g = jalali_to_gregorian(_date_part)
            if not _g:
                raise ValueError('bad date')
            p.publish_at = _dt.strptime(_g + ' ' + _time_part, '%Y-%m-%d %H:%M')
            p.is_published = False
            flash(f'انتشار برای {raw} زمان‌بندی شد. 🕐', 'success')
        except Exception:
            flash('فرمت تاریخ نادرست است — از تقویم شمسی استفاده کنید (مثال: ۱۴۰۵/۰۵/۱۵ ۱۴:۳۰).', 'error')
    else:
        p.publish_at = None
        p.is_published = True
        flash('صفحه فوراً منتشر شد.', 'success')
    db.session.commit()
    return redirect(url_for('admin.pages'))


@admin_bp.route('/pages/<int:pid>/seo', methods=['GET', 'POST'])
@admin_required
def page_seo(pid):
    """SEO هر صفحه"""
    from models import Page, SeoMeta
    p = db.get_or_404(Page, pid)
    meta = SeoMeta.query.filter_by(path='/page/' + p.slug).first()
    if request.method == 'POST':
        if not meta:
            meta = SeoMeta(path='/page/' + p.slug)
            db.session.add(meta)
        meta.title = request.form.get('title', '').strip()
        meta.description = request.form.get('description', '').strip()
        meta.focus_keyword = request.form.get('focus_keyword', '').strip()
        meta.noindex = bool(request.form.get('noindex'))
        db.session.commit()
        flash('SEO صفحه ذخیره شد. ✅', 'success')
        return redirect(url_for('admin.pages'))
    return render_template('admin/page_seo.html', page=p, meta=meta)


@admin_bp.route('/pages/<int:pid>/revisions')
@admin_required
def page_revisions(pid):
    """تاریخچه نسخه‌های صفحه"""
    from models import Page, PageRevision
    p = db.get_or_404(Page, pid)
    revs = PageRevision.query.filter_by(page_id=pid) \
        .order_by(PageRevision.created_at.desc()).all()
    return render_template('admin/page_revisions.html', page=p, revs=revs)


@admin_bp.route('/pages/revisions/<int:rid>/restore', methods=['POST'])
@admin_required
def page_revision_restore(rid):
    from models import PageRevision
    rev = db.get_or_404(PageRevision, rid)
    p = rev.page
    p.content = rev.content
    db.session.commit()
    flash('نسخه قبلی صفحه بازیابی شد. ↩️', 'success')
    return redirect(url_for('builder.editor', slug=p.slug))



# ================================================================
# فرم‌ساز حرفه‌ای
# ================================================================
@admin_bp.route('/forms')
@admin_required
def forms():
    items = CustomForm.query.order_by(CustomForm.created_at.desc()).all()
    counts = {f.id: CustomFormEntry.query.filter_by(form_id=f.id).count() for f in items}
    return render_template('admin/forms.html', forms=items, counts=counts)


@admin_bp.route('/forms/new', methods=['GET', 'POST'])
@admin_required
def form_new():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('عنوان الزامی است.', 'error')
        else:
            import re as _re
            slug = _re.sub(r'[^\w\u0600-\u06FF-]+', '-', title).strip('-') or 'form'
            while CustomForm.query.filter_by(slug=slug).first():
                slug += '-2'
            fields = _parse_form_fields(request.form.get('fields_raw', ''))
            f = CustomForm(title=title, slug=slug,
                           description=request.form.get('description', '').strip(),
                           fields=json.dumps(fields, ensure_ascii=False),
                           notify_sms=bool(request.form.get('notify_sms')),
                           notify_messenger=request.form.get('notify_messenger', ''),
                           success_msg=request.form.get('success_msg', 'ثبت شد ✅').strip() or 'ثبت شد ✅')
            db.session.add(f)
            db.session.commit()
            flash('فرم ساخته شد. لینک: /form/' + slug, 'success')
            return redirect(url_for('admin.forms'))
    return render_template('admin/form_builder.html', form=None)


@admin_bp.route('/forms/<int:pid>/edit', methods=['GET', 'POST'])
@admin_required
def form_edit(pid):
    f = db.get_or_404(CustomForm, pid)
    if request.method == 'POST':
        f.title = request.form.get('title', f.title).strip()
        f.description = request.form.get('description', '').strip()
        f.fields = json.dumps(_parse_form_fields(request.form.get('fields_raw', '')),
                              ensure_ascii=False)
        f.notify_sms = bool(request.form.get('notify_sms'))
        f.notify_messenger = request.form.get('notify_messenger', '')
        f.success_msg = request.form.get('success_msg', 'ثبت شد ✅').strip()
        db.session.commit()
        flash('فرم به‌روزرسانی شد.', 'success')
        return redirect(url_for('admin.forms'))
    raw = '\n'.join(_field_to_line(x) for x in f.fields_list())
    return render_template('admin/form_builder.html', form=f, raw=raw)


@admin_bp.route('/forms/<int:pid>/entries')
@admin_required
def form_entries(pid):
    f = db.get_or_404(CustomForm, pid)
    entries = CustomFormEntry.query.filter_by(form_id=pid) \
        .order_by(CustomFormEntry.created_at.desc()).all()
    return render_template('admin/form_entries.html', form=f, entries=entries)


@admin_bp.route('/forms/<int:pid>/entries/export')
@admin_required
def form_entries_export(pid):
    """خروجی اکسل (CSV) پاسخ‌های فرم"""
    import csv, io
    from flask import Response
    f = db.get_or_404(CustomForm, pid)
    entries = CustomFormEntry.query.filter_by(form_id=pid) \
        .order_by(CustomFormEntry.created_at.desc()).all()
    labels = [x['label'] for x in f.fields_list()]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['#', 'زمان'] + labels)
    from validators import csv_cell
    for i, e in enumerate(entries, 1):
        data = {}
        try:
            data = json.loads(e.data or '{}')
        except Exception:
            _lexc('blueprints/admin_bp.py')
        w.writerow([i, jdate_num(e.created_at) + ' ' + jtime(e.created_at)] +
                   [csv_cell(data.get(l, '')) for l in labels])
    out = '\ufeff' + buf.getvalue()  # BOM برای اکسل
    from urllib.parse import quote
    return Response(out, mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote('form-' + f.slug + '.csv')})


@admin_bp.route('/forms/<int:pid>/toggle', methods=['POST'])
@admin_required
def form_toggle(pid):
    f = db.get_or_404(CustomForm, pid)
    f.is_active = not f.is_active
    db.session.commit()
    return redirect(url_for('admin.forms'))


def _parse_form_fields(raw):
    """هر خط: برچسب | نوع | الزامی(1/0) | گزینه‌ها(با - جدا)"""
    fields = []
    for line in (raw or '').split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split('|')]
        if not parts[0]:
            continue
        fields.append({
            'label': parts[0],
            'type': parts[1] if len(parts) > 1 and parts[1] in (
                'text', 'phone', 'email', 'textarea', 'select', 'radio',
                'checkbox', 'file', 'date') else 'text',
            'required': len(parts) > 2 and parts[2] == '1',
            'options': parts[3].split('-') if len(parts) > 3 and parts[3] else [],
        })
    return fields


def _field_to_line(x):
    return '|'.join([x.get('label', ''), x.get('type', 'text'),
                     '1' if x.get('required') else '0',
                     '-'.join(x.get('options', []))])


# ================================================================
# پاسخ‌های آماده تیکت
# ================================================================
@admin_bp.route('/canned-replies', methods=['GET', 'POST'])
@admin_required
def canned_replies():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
        if title and body:
            db.session.add(CannedReply(title=title, body=body))
            db.session.commit()
            flash('پاسخ آماده ذخیره شد.', 'success')
        return redirect(url_for('admin.canned_replies'))
    items = CannedReply.query.order_by(CannedReply.created_at.desc()).all()
    return render_template('admin/canned_replies.html', items=items)


@admin_bp.route('/canned-replies/<int:rid>/delete', methods=['POST'])
@admin_required
def canned_reply_delete(rid):
    r = db.get_or_404(CannedReply, rid)
    db.session.delete(r)
    db.session.commit()
    return redirect(url_for('admin.canned_replies'))


@admin_bp.route('/users/<int:uid>/login-as', methods=['POST'])
@admin_required
def user_login_as(uid):
    """ورود به حساب کاربر توسط مدیر ارشد — با ثبت لاگ."""
    if g.user.role not in ('admin', 'super_admin'):
        abort(403)
    target = db.get_or_404(User, uid)
    if target.id == g.user.id or not target.is_active:
        abort(400)
    if target.role in ('admin', 'super_admin') and g.user.role != 'super_admin':
        abort(403)
    if not target.session_token:
        target.new_session_token()
    db.session.add(ActivityLog(user_id=g.user.id, action='login_as',
                               detail=f'ورود به حساب {target.email}',
                               ip=request.headers.get('X-Forwarded-For', request.remote_addr or '')[:60]))
    db.session.commit()
    session['uid'] = target.id
    session['st'] = target.session_token
    session['admin_impersonating'] = g.user.id
    flash(f'شما به حساب {target.name} وارد شدید (حالت ادمین).', 'info')
    return redirect(url_for('student.dashboard'))


@admin_bp.route('/impersonate/exit')
def impersonate_exit():
    """بازگشت ادمین از حالت ورود به حساب کاربر — فقط اگر واقعاً در حالت impersonation باشد"""
    admin_id = session.pop('admin_impersonating', None)
    if not admin_id:
        # بدون حالت impersonation: به خانه برگرد (نه /admin)
        return redirect(url_for('site.index'))
    session['uid'] = admin_id
    admin = db.session.get(User, admin_id)
    if admin:
        session['st'] = admin.session_token
    flash('به حساب مدیریتی خود بازگشتید.', 'info')
    return redirect(url_for('admin.overview'))


# ================================================================
# منوساز حرفه‌ای
# ================================================================
@admin_bp.route('/menus')
@admin_required
def menus():
    items = Menu.query.order_by(Menu.created_at.desc()).all()
    return render_template('admin/menus.html', menus=items)


@admin_bp.route('/menus/new', methods=['GET', 'POST'])
@admin_required
def menu_new():
    if request.method == 'GET':
        return redirect(url_for('admin.menus'))
    title = request.form.get('title', '').strip()
    if title:
        import re as _re
        slug = _re.sub(r'[^\w\u0600-\u06FF-]+', '-', title).strip('-') or 'menu'
        while Menu.query.filter_by(slug=slug).first():
            slug += '-2'
        db.session.add(Menu(title=title, slug=slug,
                            location=request.form.get('location', 'main'),
                            is_active=bool(request.form.get('is_active'))))
        db.session.commit()
        flash('منو ساخته شد.', 'success')
    return redirect(url_for('admin.menus'))


@admin_bp.route('/menus/<int:mid>', methods=['GET', 'POST'])
@admin_required
def menu_edit(mid):
    m = db.get_or_404(Menu, mid)
    if request.method == 'POST':
        m.title = request.form.get('title', m.title).strip()
        m.location = request.form.get('location', m.location)
        m.is_active = bool(request.form.get('is_active'))
        # آیتم‌ها: خط = برچسب|آدرس|آیکون|نقش‌ها|شماره خط والد (۱-پایه)
        raw = request.form.get('items_raw', '')
        for old in list(m.items):
            db.session.delete(old)
        db.session.flush()
        created = []
        for i, line in enumerate(raw.splitlines()):
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split('|')]
            parent_idx = int(parts[4]) - 1 if len(parts) > 4 and parts[4].isdigit() else -1
            parent = created[parent_idx] if 0 <= parent_idx < len(created) else None
            item = MenuItem(menu_id=m.id, label=parts[0],
                            url=parts[1] if len(parts) > 1 and parts[1] else '#',
                            icon=parts[2] if len(parts) > 2 else '',
                            roles=parts[3] if len(parts) > 3 else '',
                            parent_id=parent.id if parent else None,
                            sort=i)
            db.session.add(item)
            db.session.flush()  # ست شدن id برای زیرمنو
            created.append(item)
        db.session.commit()
        flash('منو به‌روزرسانی شد.', 'success')
        return redirect(url_for('admin.menus'))
    raw = '\n'.join(f"{i.label}|{i.url}|{i.icon}|{i.roles}" for i in m.items)
    return render_template('admin/menu_edit.html', m=m, raw=raw)


@admin_bp.route('/menus/<int:mid>/toggle', methods=['POST'])
@admin_required
def menu_toggle(mid):
    m = db.get_or_404(Menu, mid)
    m.is_active = not m.is_active
    db.session.commit()
    return redirect(url_for('admin.menus'))


@admin_bp.route('/menus/<int:mid>/delete', methods=['POST'])
@admin_required
def menu_delete(mid):
    m = db.get_or_404(Menu, mid)
    db.session.delete(m)
    db.session.commit()
    flash('منو حذف شد.', 'info')
    return redirect(url_for('admin.menus'))


# ================================================================
# مدیریت کاربر تکمیلی: پروفایل کامل، ریست رمز، افزودن، ارسال اعلان
# ================================================================
@admin_bp.route('/users/<int:uid>/profile')
@admin_required
def user_profile(uid):
    from permissions import has_permission, can_access_endpoint
    u = db.get_or_404(User, uid)
    is_manager = g.user.role in ('admin', 'super_admin')
    can_view_courses = is_manager or has_permission(g.user, 'view_user_courses')
    can_view_orders = is_manager or has_permission(g.user, 'view_orders')
    can_view_tickets = is_manager or has_permission(g.user, 'reply_tickets')
    can_view_activity = is_manager or has_permission(g.user, 'view_reports')
    enrollments = Enrollment.query.filter_by(user_id=uid).all() if can_view_courses else []
    orders = (Order.query.filter_by(user_id=uid).order_by(Order.created_at.desc()).all()
              if can_view_orders else [])
    tickets = (Ticket.query.filter_by(user_id=uid).order_by(Ticket.created_at.desc()).all()
               if can_view_tickets else [])
    acts = (ActivityLog.query.filter_by(user_id=uid)
            .order_by(ActivityLog.created_at.desc()).limit(20).all()
            if can_view_activity else [])
    protected_user = u.role in ('admin', 'super_admin') and g.user.role != 'super_admin'
    capabilities = {
        'wallet': is_manager,
        'reset_password': (not protected_user and has_permission(g.user, 'edit_users')),
        'notify': can_access_endpoint(g.user, 'admin.user_notify'),
        'courses': can_view_courses, 'orders': can_view_orders,
        'tickets': can_view_tickets, 'activity': can_view_activity,
    }
    return render_template('admin/user_profile.html', u=u, enrollments=enrollments,
                           orders=orders, tickets=tickets, acts=acts,
                           capabilities=capabilities)


@admin_bp.route('/users/<int:uid>/reset-password', methods=['POST'])
@admin_required
def user_reset_password(uid):
    u = db.get_or_404(User, uid)
    if u.role in ('admin', 'super_admin') and g.user.role != 'super_admin':
        abort(403)
    new_pass = request.form.get('password', '').strip()
    if len(new_pass) < 8:
        flash('رمز باید حداقل ۸ کاراکتر باشد.', 'error')
    else:
        u.set_password(new_pass)
        u.new_session_token()  # خروج از همه دستگاه‌ها
        db.session.add(ActivityLog(user_id=g.user.id, action='reset_password',
                                   detail=f'تغییر رمز {u.email}'))
        db.session.commit()
        flash(f'رمز {u.name} تغییر کرد و همه سشن‌ها باطل شد. 🔑', 'success')
    return redirect(url_for('admin.user_profile', uid=uid))


@admin_bp.route('/users/add', methods=['GET', 'POST'])
@admin_required
def user_add():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'student').strip()
        from models import ROLES
        if role not in ROLES:
            abort(400)
        if g.user.role not in ('admin', 'super_admin') and role != 'student':
            abort(403)
        if role in ('admin', 'super_admin') and g.user.role != 'super_admin':
            abort(403)
        if len(name) < 3 or len(password) < 8 or '@' not in email:
            flash('نام، ایمیل معتبر و رمز (حداقل ۸ کاراکتر) الزامی است.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('این ایمیل قبلاً ثبت شده.', 'error')
        elif phone and User.query.filter_by(phone=phone).first():
            flash('این شماره قبلاً ثبت شده.', 'error')
        else:
            u = User(name=name, email=email, phone=phone or None, role=role,
                     avatar_color=random.choice(['#2563eb', '#7c3aed', '#059669', '#dc2626', '#ea580c']))
            # آواتار: آپلود مستقیم اولویت دارد؛ بعد مقدار انتخاب‌شده از کتابخانهٔ رسانه
            avatar_file = request.files.get('avatar_file') if request.files else None
            avatar_value = (request.form.get('avatar') or '').strip()
            if avatar_file and avatar_file.filename:
                from validators import (safe_filename, ALLOWED_IMAGE_EXT,
                                        file_content_is_safe)
                safe = safe_filename(avatar_file.filename or '', ALLOWED_IMAGE_EXT)
                ext = os.path.splitext(safe or '')[1].lower()
                if safe and file_content_is_safe(avatar_file.stream, ext):
                    up = os.path.join(os.path.dirname(os.path.dirname(
                        os.path.abspath(__file__))), 'static', 'img',
                        'uploads', 'avatars')
                    os.makedirs(up, exist_ok=True)
                    fname = 'av_' + uuid.uuid4().hex[:10] + ext
                    avatar_file.save(os.path.join(up, fname))
                    u.avatar = fname
                else:
                    flash('فایل آواتار نامعتبر است و نادیده گرفته شد.', 'error')
            elif avatar_value:
                # مقدار کامل مسیر از کتابخانه رسانه (uploads/media/...) یا URL
                from models import resolve_image_url
                if resolve_image_url(avatar_value):
                    u.avatar = avatar_value
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            from gamification import make_referral_code
            make_referral_code(u)
            db.session.commit()
            if u.role in ('teacher', 'admin'):
                try:
                    from seo_service import ensure_meta
                    ensure_meta('/teacher/' + str(u.id))
                    db.session.commit()
                except Exception:
                    _lexc('blueprints/admin_bp.py')
            flash(f'کاربر «{name}» با نقش {role} ساخته شد. ✅', 'success')
            return redirect(url_for('admin.users'))
    return render_template('admin/user_add.html')




@admin_bp.route('/users/<int:uid>/wallet', methods=['POST'])
@admin_required
def user_wallet(uid):
    """مدیریت کیف پول کاربر — فقط مدیران اصلی."""
    if g.user.role not in ('admin', 'super_admin'):
        abort(403)
    from gamification import wallet_charge, wallet_spend
    u = db.get_or_404(User, uid)
    action = request.form.get('action', '')
    amount = request.form.get('amount', 0, type=int)
    note = request.form.get('note', '').strip() or 'توسط مدیریت'
    if amount <= 0:
        flash('مبلغ نامعتبر است.', 'error')
    elif action == 'charge':
        wallet_charge(u, amount, 'شارژ توسط مدیریت — ' + note)
        db.session.commit()
        flash(f'{amount:,} تومان به کیف پول {u.name} اضافه شد. ✅', 'success')
    elif action == 'deduct':
        wallet_spend(u, amount, 'کسر توسط مدیریت — ' + note)
        db.session.commit()
        flash(f'{amount:,} تومان از کیف پول {u.name} کسر شد.', 'info')
    return redirect(url_for('admin.user_profile', uid=uid))


@admin_bp.route('/installments')
@admin_required
def installments():
    """مدیریت پرداخت اقساطی — همه قسط‌ها"""
    from models import Installment
    status = request.args.get('status', '')
    q = Installment.query
    if status:
        q = q.filter(Installment.status == status)
    items = q.order_by(Installment.due_date.asc()).all()
    return render_template('admin/installments.html', items=items, status=status)


@admin_bp.route('/installments/<int:iid>/mark-paid', methods=['POST'])
@admin_required
def installment_mark_paid(iid):
    """ثبت دستی پرداخت یک قسط — برای همگام‌سازی وصولی‌های اسنپ‌پی/دیجی‌پی
    (که در پنل خود ارائه‌دهنده انجام می‌شود) و باز شدن جلسات بعدی دوره."""
    from models import Installment as _I, Notification as _N
    inst = db.get_or_404(_I, iid)
    if inst.status == 'paid':
        flash('این قسط قبلاً پرداخت شده است.', 'info')
        return redirect(url_for('admin.installments'))
    order = inst.order
    inst.status = 'paid'
    inst.paid_at = utcnow()
    inst.ref_id = (inst.ref_id or '') + ' | ADMIN-MANUAL'
    remaining = _I.query.filter_by(order_id=order.id).filter(
        _I.status != 'paid').count()
    _N.notify(order.user_id, 'قسط شما ثبت شد ✅',
              'قسط {} از {} سفارش {} ثبت شد. جلسات بیشتری از دوره باز شد.'.format(
                  fa_num(inst.number), fa_num(order.installment_count or 1), order.code),
              '💳', url_for('student.my_courses'))
    if remaining == 0:
        order.status = 'paid'
        order.paid_at = utcnow()
        _N.notify(order.user_id, 'تکمیل پرداخت اقساطی 🎉',
                  'همه قسط‌های سفارش {} پرداخت شد؛ همه جلسات دوره باز شد.'.format(order.code),
                  '✅', url_for('student.my_courses'))
    db.session.commit()
    flash('قسط {}/{} به‌عنوان پرداخت‌شده ثبت شد؛ جلسات دوره طبق قفل اقساطی باز شد.'.format(
        fa_num(inst.number), fa_num(order.installment_count or 1)), 'success')
    return redirect(url_for('admin.installments'))


@admin_bp.route('/users/<int:uid>/notify', methods=['POST'])
@admin_required
def user_notify(uid):
    from models import Notification
    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()
    if title:
        Notification.notify(uid, title, body, '📨')
        db.session.commit()
        flash('اعلان به کاربر ارسال شد. ✅', 'success')
    return redirect(url_for('admin.user_profile', uid=uid))


# ================================================================
# تسویه با مدرس‌ها
# ================================================================
@admin_bp.route('/payouts')
@admin_required
def payouts():
    items = PayoutRequest.query.order_by(PayoutRequest.created_at.desc()).all()
    return render_template('admin/payouts.html', items=items)


@admin_bp.route('/payouts/<int:pid>/action', methods=['POST'])
@admin_required
def payout_action(pid):
    p = db.get_or_404(PayoutRequest, pid)
    action = request.form.get('action', '')
    if action == 'paid':
        p.status = 'paid'
        p.paid_at = utcnow()
        p.admin_note = request.form.get('note', '')
        from models import Notification
        Notification.notify(p.teacher_id, 'تسویه حساب انجام شد 💰',
                            f'مبلغ {p.amount:,} تومان به حساب شما واریز شد.', '💰')
    elif action == 'rejected':
        p.status = 'rejected'
        p.admin_note = request.form.get('note', '')
        from models import Notification
        Notification.notify(p.teacher_id, 'درخواست تسویه رد شد',
                            request.form.get('note', '') or 'لطفاً اطلاعات حساب را بررسی کنید.', '⚠️')
    db.session.commit()
    flash('وضعیت تسویه به‌روزرسانی شد.', 'success')
    return redirect(url_for('admin.payouts'))


# ================================================================
# چت آنلاین پشتیبانی (سمت ادمین)
# ================================================================
@admin_bp.route('/chat')
@admin_required
def chat():
    users = db.session.query(ChatMessage.user_id, User.name, User.email,
                             func.max(ChatMessage.created_at), func.sum(~ChatMessage.is_read)) \
        .join(User, User.id == ChatMessage.user_id) \
        .group_by(ChatMessage.user_id) \
        .order_by(func.max(ChatMessage.created_at).desc()).all()
    return render_template('admin/chat.html', chats=users)


@admin_bp.route('/chat/<int:uid>')
@admin_required
def chat_user(uid):
    u = db.get_or_404(User, uid)
    msgs = ChatMessage.query.filter_by(user_id=uid).order_by(ChatMessage.created_at.asc()).all()
    # خواندن پیام‌های کاربر
    for m in msgs:
        if not m.is_admin and not m.is_read:
            m.is_read = True
    db.session.commit()
    return render_template('admin/chat_user.html', u=u, msgs=msgs)


@admin_bp.route('/chat/<int:uid>/poll')
@admin_required
def chat_poll(uid):
    """Polling: پیام جدید از کاربر؟"""
    last = ChatMessage.query.filter_by(user_id=uid).order_by(ChatMessage.created_at.desc()).first()
    new_msg = last and not last.is_admin and not last.is_read
    if new_msg:
        last.is_read = True
        db.session.commit()
    return jsonify(new_msg=bool(new_msg))


@admin_bp.route('/chat/<int:uid>/send', methods=['POST'])
@admin_required
def chat_send(uid):
    body = request.form.get('body', '').strip()
    if body:
        db.session.add(ChatMessage(user_id=uid, body=body, is_admin=True))
        db.session.commit()
    return redirect(url_for('admin.chat_user', uid=uid))



@admin_bp.route('/users/send-sms', methods=['POST'])
@admin_required
def users_send_sms():
    """ارسال گروهی پیامک به کاربران یک نقش"""
    from sms import send_sms
    role = request.form.get('role', '')
    text = request.form.get('text', '').strip()
    if not text:
        flash('متن پیام را وارد کنید.', 'error')
        return redirect(url_for('admin.users'))
    users = User.query.filter_by(role=role).all() if role else User.query.all()
    sent = 0
    for u in users:
        if u.phone and getattr(u, 'notify_sms', True) is not False:
            ok, _ = send_sms(u.phone, text, {s.key: s.value for s in Setting.query.all()})
            if ok:
                sent += 1
    flash(f'پیامک به {sent} کاربر ارسال شد. 📱', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/courses/<int:cid>/students/export')
@admin_required
def course_students_export(cid):
    """خروجی اکسل (CSV) دانشجویان یک دوره"""
    import csv, io
    from flask import Response
    from urllib.parse import quote
    course = db.get_or_404(Course, cid)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['نام', 'موبایل', 'ایمیل', 'پیشرفت٪', 'تاریخ ثبت‌نام', 'گواهی'])
    from validators import csv_cell
    for e in Enrollment.query.filter_by(course_id=cid).all():
        w.writerow([csv_cell(e.user.name if e.user else ''),
                    csv_cell(e.user.phone if e.user else ''),
                    csv_cell(e.user.email if e.user else ''), e.percent,
                    jdate_num(e.created_at), 'بله' if e.completed_at else 'خیر'])
    out = '\ufeff' + buf.getvalue()
    return Response(out, mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote('students-' + course.slug + '.csv')})



# ================================================================
# مدیریت کلاس‌های آنلاین + انجمن + گواهی‌ها + گزارش رفتار
# ================================================================
@admin_bp.route('/live-sessions', methods=['GET', 'POST'])
@admin_required
def live_sessions():
    from datetime import datetime as _dt
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        link = request.form.get('link', '').strip()
        starts = request.form.get('starts_at', '').strip()
        if title and starts:
            try:
                dt = _dt.strptime(starts, '%Y-%m-%dT%H:%M')
                db.session.add(LiveSession(course_id=request.form.get('course_id', type=int) or None,
                                          title=title, description=request.form.get('description', '').strip(),
                                          link=link or None, starts_at=dt,
                                          duration_min=request.form.get('duration_min', 90, type=int),
                                          is_recorded=bool(request.form.get('is_recorded'))))
                db.session.commit()
                flash('کلاس آنلاین ساخته شد. 🎥', 'success')
            except Exception:
                flash('فرمت تاریخ نادرست است — از تقویم شمسی استفاده کنید.', 'error')
        return redirect(url_for('admin.live_sessions'))
    sessions = LiveSession.query.order_by(LiveSession.starts_at.desc()).all()
    courses = Course.query.filter_by(status='published').all()
    return render_template('admin/live_sessions.html', sessions=sessions, courses=courses)


@admin_bp.route('/live-sessions/<int:sid>/delete', methods=['POST'])
@admin_required
def live_session_delete(sid):
    s_ = db.get_or_404(LiveSession, sid)
    db.session.delete(s_)
    db.session.commit()
    return redirect(url_for('admin.live_sessions'))


@admin_bp.route('/forum-moderate')
@admin_required
def forum_moderate():
    topics = ForumTopic.query.order_by(ForumTopic.is_approved.asc(), ForumTopic.created_at.desc()).all()
    pending_posts = ForumPost.query.filter_by(is_approved=False).order_by(ForumPost.created_at.desc()).limit(80).all()
    return render_template('admin/forum_moderate.html', topics=topics, pending_posts=pending_posts)


@admin_bp.route('/forum/<int:tid>/approve', methods=['POST'])
@admin_required
def forum_topic_approve(tid):
    tpc = db.get_or_404(ForumTopic, tid)
    tpc.is_approved = not tpc.is_approved
    db.session.commit()
    flash('وضعیت تایید تاپیک تغییر کرد.', 'success')
    return redirect(url_for('admin.forum_moderate'))


@admin_bp.route('/forum/post/<int:pid>/approve', methods=['POST'])
@admin_required
def forum_post_approve(pid):
    post = db.get_or_404(ForumPost, pid)
    post.is_approved = not post.is_approved
    db.session.commit()
    flash('وضعیت تایید پاسخ تغییر کرد.', 'success')
    return redirect(url_for('admin.forum_moderate'))


@admin_bp.route('/forum/<int:tid>/delete', methods=['POST'])
@admin_required
def forum_topic_delete(tid):
    t = db.get_or_404(ForumTopic, tid)
    db.session.delete(t)
    db.session.commit()
    flash('تاپیک حذف شد.', 'info')
    return redirect(url_for('admin.forum_moderate'))


@admin_bp.route('/forum/<int:tid>/pin', methods=['POST'])
@admin_required
def forum_topic_pin(tid):
    t = db.get_or_404(ForumTopic, tid)
    t.is_pinned = not t.is_pinned
    db.session.commit()
    return redirect(url_for('admin.forum_moderate'))


@admin_bp.route('/certificates')
@admin_required
def certificates():
    """مدیریت گواهی‌های صادرشده"""
    from models import Enrollment
    items = Enrollment.query.filter(Enrollment.completed_at.isnot(None)) \
        .order_by(Enrollment.completed_at.desc()).all()
    certs = []
    from models import certificate_code
    for e in items:
        code = certificate_code(e.course.slug, e.user.email, e.id)
        certs.append({'id': e.id, 'user': e.user.name if e.user else '—',
                      'course': e.course.title if e.course else '—',
                      'date': e.completed_at, 'code': code, 'enroll': e})
    return render_template('admin/certificates.html', certs=certs)


@admin_bp.route('/certificates/<int:eid>/revoke', methods=['POST'])
@admin_required
def certificate_revoke(eid):
    """لغو گواهی — حذف completed_at"""
    from models import Enrollment
    e = db.get_or_404(Enrollment, eid)
    e.completed_at = None
    from models import Notification
    Notification.notify(e.user_id, 'گواهی شما لغو شد ⚠️',
                        'در صورت اعتراض با پشتیبانی تماس بگیرید.', '⚠️')
    db.session.commit()
    flash('گواهی لغو شد.', 'warning')
    return redirect(url_for('admin.certificates'))


@admin_bp.route('/behavior-report')
@admin_required
def behavior_report():
    """گزارش رفتار دانشجو: نرخ تکمیل، افت، میانگین پیشرفت"""
    from models import Enrollment
    enrolls = Enrollment.query.all()
    rows = []
    for e in enrolls:
        if not e.user or not e.course:
            continue
        rows.append({'user': e.user.name, 'course': e.course.title,
                     'percent': e.percent, 'done': e.percent >= 100,
                     'started': e.created_at})
    total = len(rows)
    completed = sum(1 for r in rows if r['done'])
    avg = round(sum(r['percent'] for r in rows) / total) if total else 0
    # دوره‌های با بیشترین افت (شروع ولی ناقص)
    dropped = [r for r in rows if 0 < r['percent'] < 40]
    return render_template('admin/behavior_report.html', rows=rows, total=total,
                           completed=completed, avg=avg, dropped=dropped)


@admin_bp.route('/settings/email-test', methods=['POST'])
@admin_required
def email_test():
    """ارسال ایمیل تست"""
    from email_service import send_email
    keys = ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass', 'smtp_from', 'smtp_tls']
    for k in keys:
        v = request.form.get(k, '').strip()
        if k in _SECRET_SETTING_KEYS and not v:
            continue
        st = db.session.get(Setting, k)
        if st:
            st.value = v
        elif v:
            db.session.add(Setting(key=k, value=v))
    db.session.commit()
    settings = {s.key: s.value for s in Setting.query.all()}
    to = request.form.get('smtp_test_to', '').strip() or g.user.email
    ok, msg = send_email(to, 'تست ایمیل آکادمی ✅',
                         '<div style="font-family:Tahoma;padding:20px;text-align:center"><h2>✅ اتصال ایمیل برقرار است</h2><p>این یک ایمیل تست از آکادمی است.</p></div>',
                         settings)
    flash(('✅ ' if ok else '❌ ') + msg, 'success' if ok else 'error')
    return redirect(url_for('admin.super_settings', tab='sms'))



@admin_bp.route('/newsletters/send', methods=['POST'])
@admin_required
def newsletter_send():
    """ارسال خبرنامه به همه ثبت‌نام‌شده‌ها (ایمیل/پیامک/پیام‌رسان)"""
    from email_service import send_email
    subject = request.form.get('subject', '').strip()
    body = request.form.get('body', '').strip()
    channel = request.form.get('channel', 'email')
    if not subject or not body:
        flash('عنوان و متن خبرنامه الزامی است.', 'error')
        return redirect(url_for('admin.newsletters'))
    settings = {s.key: s.value for s in Setting.query.all()}
    sent = 0
    if channel == 'email':
        for e in NewsletterEmail.query.all():
            html = f'<div dir="rtl" style="font-family:Tahoma;max-width:560px;margin:auto;border:1px solid #e2e8f0;border-radius:16px;padding:24px;line-height:2;color:#334155">{body}</div>'
            ok, _ = send_email(e.email, subject, html, settings)
            if ok:
                sent += 1
    elif channel == 'messenger':
        from messengers import send_to_all
        results = send_to_all(subject + '\n' + body, settings)
        sent = sum(1 for ok, _ in results.values() if ok)
    elif channel == 'sms':
        from sms import send_sms
        for e in NewsletterEmail.query.all():
            ok, _ = send_sms(e.email, body, settings)
            if ok:
                sent += 1
    flash(f'خبرنامه به {sent} گیرنده ارسال شد. 📣', 'success')
    return redirect(url_for('admin.newsletters'))



@admin_bp.route('/question-bank', methods=['GET', 'POST'])
@admin_required
def question_bank():
    """بانک سوال — سوالات مشترک برای آزمون‌ها"""
    from models import QuestionBank
    if request.method == 'POST':
        text = request.form.get('text', '').strip()
        choices_raw = request.form.get('choices', '').strip()
        correct = request.form.get('correct_index', 0, type=int)
        if text and choices_raw:
            choices = [c.strip() for c in choices_raw.split(',') if c.strip()]
            if len(choices) >= 2:
                db.session.add(QuestionBank(category=request.form.get('category', 'عمومی').strip(),
                                           text=text,
                                           choices=json.dumps(choices, ensure_ascii=False),
                                           correct_index=max(0, min(correct, len(choices) - 1)),
                                           explanation=request.form.get('explanation', '').strip()))
                db.session.commit()
                flash('سوال به بانک اضافه شد. ✅', 'success')
        return redirect(url_for('admin.question_bank'))
    items = QuestionBank.query.order_by(QuestionBank.created_at.desc()).all()
    from models import Quiz
    quizzes = Quiz.query.order_by(Quiz.title).all()
    return render_template('admin/question_bank.html', items=items, quizzes=quizzes)


@admin_bp.route('/question-bank/<int:qid>/add-to-quiz', methods=['POST'])
@admin_required
def question_bank_add_to_quiz(qid):
    """افزودن سوال بانک به یک آزمون"""
    from models import QuestionBank, QuizQuestion, Quiz
    q = db.get_or_404(QuestionBank, qid)
    quiz_id = request.form.get('quiz_id', type=int)
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz:
        flash('آزمون انتخاب نشده.', 'error')
        return redirect(url_for('admin.question_bank'))
    db.session.add(QuizQuestion(quiz_id=quiz.id, text=q.text,
                                choices=q.choices, correct_index=q.correct_index,
                                explanation=q.explanation or '',
                                sort=len(quiz.questions)))
    db.session.commit()
    flash(f'سوال به آزمون «{quiz.title}» اضافه شد. ✅', 'success')
    return redirect(url_for('admin.question_bank'))




@admin_bp.route('/roles', methods=['GET', 'POST'])
@admin_required
def roles_manage():
    """مدیریت نقش‌ها و دسترسی‌ها"""
    from models import ROLES, PERMISSION_FA
    if request.method == 'POST':
        # ذخیره دسترسی‌های سفارشی در تنظیمات
        perms = {}
        for role in ROLES:
            selected = request.form.getlist('perms_' + role)
            perms[role] = selected
        import json as _json
        st = db.session.get(Setting, 'role_permissions')
        if st:
            st.value = _json.dumps(perms)
        else:
            db.session.add(Setting(key='role_permissions', value=_json.dumps(perms)))
        db.session.commit()
        flash('دسترسی نقش‌ها ذخیره شد. ✅', 'success')
        return redirect(url_for('admin.roles_manage'))
    import json as _json
    custom = {}
    st = db.session.get(Setting, 'role_permissions')
    if st and st.value:
        try:
            custom = _json.loads(st.value)
        except Exception:
            custom = {}
    all_perms = sorted(PERMISSION_FA.keys())
    return render_template('admin/roles.html', ROLES=ROLES, PERMISSION_FA=PERMISSION_FA,
                           all_perms=all_perms, custom=custom)




@admin_bp.route('/files/lesson/<int:lid>')
def protected_lesson_file(lid):
    """دانلود محافظت‌شده؛ فقط مدیر یا دانشجوی مجاز در دورهٔ قابل‌دانلود."""
    from models import Lesson
    from blueprints.student import _installment_locked
    from flask import send_from_directory
    if not g.user:
        return redirect(url_for('auth.login', next=request.path))
    les = db.get_or_404(Lesson, lid)
    course = les.section.course
    if not g.user.is_admin:
        if not course.allow_download:
            abort(403)
        enr = Enrollment.query.filter_by(user_id=g.user.id, course_id=course.id).first()
        if not enr:
            abort(403)
        if les.release_days and les.release_days > 0 and not les.is_free:
            from datetime import timedelta as _td
            if utcnow() < (enr.created_at + _td(days=les.release_days)).replace(tzinfo=None):
                abort(403)
        if _installment_locked(enr, les):
            abort(403)
    if not les.file_url:
        abort(404)
    fname = les.file_url.split('/')[-1]
    from uploads_helper import uploads_dir
    return send_from_directory(uploads_dir('lessons'), fname, as_attachment=True)



@admin_bp.route('/backup/list')
@admin_required
def backup_list():
    """لیست بکاپ‌ها + بازیابی"""
    import glob, os as _os
    bk_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'instance', 'backups')
    bks = []
    for f in sorted(glob.glob(_os.path.join(bk_dir, 'academy-*.*')), key=_os.path.getmtime, reverse=True):
        if not f.endswith(('.db', '.json')):
            continue
        bks.append({'name': _os.path.basename(f), 'size': _os.path.getsize(f) // 1024,
                    'time': _os.path.getmtime(f)})
    return render_template('admin/backup_list.html', backups=bks)


@admin_bp.route('/backup/create', methods=['POST'])
@admin_required
def backup_create():
    """ساخت بکاپ دستی — SQLite: کپی فایل | MySQL: دامپ JSON همه جدول‌ها"""
    import os as _os, json as _json
    from datetime import datetime as _dt
    bk_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'instance', 'backups')
    _os.makedirs(bk_dir, exist_ok=True)
    stamp = f'{_dt.now():%Y%m%d-%H%M}'
    db_url = _os.environ.get('DATABASE_URL', '')
    if db_url.startswith('mysql'):
        # ── MySQL: دامپ JSON (قابل بازیابی با اسکریپت migrate) ──
        name = f'academy-{stamp}-mysql.json'
        try:
            from sqlalchemy import inspect as _insp
            insp = _insp(db.engine)
            dump = {'engine': 'mysql', 'created_at': _dt.now().isoformat(), 'tables': {}}
            for t in insp.get_table_names():
                if t.startswith('sqlite_') or t in ('alembic_version',):
                    continue
                rows = [dict(r._mapping) for r in db.session.execute(db.text(f'SELECT * FROM `{t}`'))]
                dump['tables'][t] = rows
            with open(_os.path.join(bk_dir, name), 'w', encoding='utf-8') as fh:
                _json.dump(dump, fh, ensure_ascii=False, default=str)
            flash(f'بکاپ MySQL «{name}» ساخته شد ({sum(len(v) for v in dump["tables"].values())} ردیف) ✅', 'success')
            return redirect(url_for('admin.backup_list'))
        except Exception as e:
            flash('خطا در بکاپ MySQL: ' + str(e)[:150], 'error')
            return redirect(url_for('admin.backup_list'))
    # ── SQLite: VACUUM INTO (کپی امن همراه WAL) ──
    import shutil
    src = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'instance', 'academy.db')
    if not _os.path.exists(src):
        flash('فایل دیتابیس پیدا نشد.', 'error')
        return redirect(url_for('admin.backup_list'))
    name = f'academy-{stamp}-manual.db'
    try:
        import sqlite3
        con = sqlite3.connect(src)
        con.execute(f"VACUUM INTO '{_os.path.join(bk_dir, name)}'")
        con.close()
    except Exception:
        shutil.copy2(src, _os.path.join(bk_dir, name))
    flash(f'بکاپ «{name}» ساخته شد ✅', 'success')
    return redirect(url_for('admin.backup_list'))


@admin_bp.route('/backup/restore/<name>', methods=['POST'])
@admin_required
def backup_restore(name):
    """بازیابی دیتابیس از بکاپ (فقط سوپر ادمین)"""
    if g.user.role != 'super_admin' and g.user.role != 'admin':
        abort(403)
    import shutil, os as _os
    import re as _re
    if not _re.match(r'^academy-[\w\-]+\.(db|json)$', name):
        flash('نام بکاپ نامعتبر.', 'error')
        return redirect(url_for('admin.backup_list'))
    if _os.environ.get('DATABASE_URL', '').startswith('mysql'):
        flash('بازیابی خودکار فقط برای SQLite است — در MySQL از پنل هاست/phpMyAdmin استفاده کنید.', 'error')
        return redirect(url_for('admin.backup_list'))
    bk = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'instance', 'backups', name)
    if not _os.path.exists(bk):
        flash('بکاپ یافت نشد.', 'error')
        return redirect(url_for('admin.backup_list'))
    # نسخه فعلی را قبل از بازگردانی بکاپ بگیر
    db_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'instance', 'academy.db')
    if _os.path.exists(db_path):
        from datetime import datetime as _dt
        shutil.copy2(db_path, _os.path.join(_os.path.dirname(_os.path.dirname(__file__)),
                                            'instance', 'backups', f'pre-restore-{_dt.now():%Y%m%d-%H%M}.db'))
    try:
        db.engine.dispose()
    except Exception:
        pass
    for sidecar in (db_path + '-wal', db_path + '-shm'):
        if _os.path.exists(sidecar):
            try:
                _os.remove(sidecar)
            except OSError:
                pass
    shutil.copy2(bk, db_path)
    flash('دیتابیس از بکاپ بازیابی شد — برای اعمال، سرور ری‌استارت می‌شود. ♻️', 'success')
    # ری‌استارت خودکار در dev ممکن نیست — کاربر را راهنمایی می‌کنیم
    return redirect(url_for('admin.backup_list'))


@admin_bp.route('/settings')
@admin_required
def settings_legacy():
    """مسیر قدیمی — به پنل تنظیمات سوپر منتقل شد"""
    return redirect(url_for('admin.super_settings'))


@admin_bp.route('/settings-old', methods=['GET', 'POST'])
@admin_required
def settings():
    if request.method == 'POST':
        keys = ['site_name', 'site_desc', 'phone', 'email', 'address', 'telegram', 'instagram',
                'brand_color', 'brand_color2', 'custom_logo',
                'certificate_text', 'certificate_sign', 'invoice_prefix',
                'base_url', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass', 'smtp_from', 'smtp_tls',
                'whatsapp', 'bale', 'eitaa', 'rubika', 'soroush', 'aparat', 'twitter', 'linkedin', 'youtube', 'github',
                'support_hours', 'about_text', 'zarinpal_merchant', 'sandbox_mode',
                'kit_container', 'kit_radius', 'watermark_enabled',
                'maintenance', 'allow_register', 'allow_phone_login',
                'site_design', 'home_design', 'about_design', 'contact_design']
        for k in keys:
            v = request.form.get(k, '').strip()
            if k in _SECRET_SETTING_KEYS and not v:
                continue
            if k == 'sandbox_mode':
                v = '0'
            s = db.session.get(Setting, k)
            if s:
                s.value = v
            else:
                db.session.add(Setting(key=k, value=v))
        # آپلود لوگو
        logo_f = request.files.get('custom_logo_file')
        if logo_f and logo_f.filename:
            up = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'static', 'img', 'uploads', 'brand')
            os.makedirs(up, exist_ok=True)
            from validators import (safe_filename, ALLOWED_IMAGE_EXT_TRUSTED,
                                    file_content_is_safe)
            safe = safe_filename(logo_f.filename or '', ALLOWED_IMAGE_EXT_TRUSTED)
            # محتوای فایل هم چک شود — svg/تصویری که <script> داشته باشد رد می‌شود
            if safe and not file_content_is_safe(logo_f.stream,
                                                 os.path.splitext(safe)[1].lower()):
                flash('فایل لوگو حاوی کد اجرایی است و پذیرفته نشد.', 'error')
                safe = None
            if safe:
                lname = 'logo' + os.path.splitext(safe)[1].lower()
                logo_f.save(os.path.join(up, lname))
                # ⚠️ باگ قبلی: اگر فایل رد می‌شد، lname تعریف نشده بود و
                # همین‌جا NameError → خطای ۵۰۰ می‌داد. حالا فقط در حالت موفق ذخیره می‌شود.
                st = db.session.get(Setting, 'custom_logo')
                if st:
                    st.value = '/static/img/uploads/brand/' + lname
                else:
                    db.session.add(Setting(key='custom_logo',
                                           value='/static/img/uploads/brand/' + lname))
        db.session.commit()
        flash('تنظیمات با موفقیت ذخیره شد.', 'success')
        return redirect(url_for('admin.settings'))
    return render_template('admin/settings.html')


@admin_bp.route('/design-preview/<did>')
@admin_required
def design_variant_preview(did):
    """پیش‌نمایش ۸ بخش UI/UX یک واریانت (از design_variants.py)"""
    from design_variants import all_variants
    variant = next((v for v in all_variants() if v['design_id'] == did), None)
    if not variant:
        flash('واریانت پیدا نشد', 'error')
        return redirect(url_for('admin.designs'))
    return render_template('admin/design_preview.html', variant=variant)


@admin_bp.route('/design-variant-json/<did>')
@admin_required
def design_variant_json(did):
    """دانلود JSON کامل یک واریانت"""
    from flask import Response as _Resp
    from design_variants import all_variants
    variant = next((v for v in all_variants() if v['design_id'] == did), None)
    if not variant:
        return 'not found', 404
    body = json.dumps(variant, ensure_ascii=False, indent=2)
    return _Resp(body, mimetype='application/json',
                 headers={'Content-Disposition': f'attachment; filename={did}.json'})


@admin_bp.route('/super-settings', methods=['GET', 'POST'])
@admin_required
def super_settings():
    """⚙️ پنل تنظیمات سوپر — ۶ تب: عمومی/برند · سئو+ریدایرکت · فروش/درگاه · پیامک/اعلان · مارکت‌پلیس/سرویس · امنیت/نگهداری"""
    # ── ذخیره تنظیمات (POST) ──
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        # الف) ذخیره گروه‌های تنظیمات
        if action == 'save':
            keys = [
                # عمومی و برند
                'site_name', 'site_desc', 'phone', 'email', 'address', 'support_hours',
                'about_text', 'contact_intro', 'custom_logo', 'brand_color', 'brand_color2',
                'telegram', 'instagram', 'whatsapp', 'bale', 'eitaa', 'rubika', 'soroush',
                'aparat', 'twitter', 'linkedin', 'youtube', 'github',
                # سئو
                'seo_title', 'seo_desc', 'seo_keywords', 'seo_author', 'seo_og_image',
                'seo_robots_main', 'seo_twitter', 'ga_code',
                # فروش و درگاه‌ها
                'currency', 'sandbox_mode', 'c2c_card', 'c2c_name',
                'zarinpal_merchant', 'idpay_api_key',
                'zibal_merchant', 'parsian_login_account',
                'melli_terminal', 'melli_username', 'melli_password',
                'sepah_terminal',
                'sadad_merchant', 'sadad_terminal', 'sadad_key',
                'snapp_client_id', 'snapp_client_secret', 'snapp_merchant',
                'digipay_api_key', 'digipay_merchant', 'tarb_api_url', 'tarb_api_key', 'tarb_merchant',
                'invoice_prefix', 'certificate_text', 'certificate_sign',
                'certificate_logo', 'certificate_stamp', 'certificate_sign_image',
                'watermark_enabled', 'bnpl_enabled', 'bnpl_max_installments', 'cashback_percent',
                'teacher_default_share',
                'loyalty_discount_percent', 'referral_bonus_percent', 'refund_days',
                # پیامک و ایمیل
                'sms_provider', 'sms_test_phone', 'sms_kavenegar_key', 'sms_kavenegar_sender',
                'sms_kavenegar_template', 'sms_melli_username', 'sms_melli_password',
                'sms_melli_sender', 'sms_faraz_token', 'sms_faraz_sender',
                'smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass', 'smtp_from', 'smtp_tls',
                # مارکت‌پلیس و سرویس‌ها
                'dk_api_base', 'dk_access_token', 'basalam_webhook_secret', 'emalls_seller_id',
                'competitive_prices', 'shipping_flat_rate', 'shipping_note',
                # صفحه‌ساز و طراحی
                'kit_container', 'kit_radius', 'site_design', 'home_design',
                'about_design', 'contact_design',
                # امنیت و نگهداری
                'maintenance', 'allow_register', 'allow_phone_login',
                'admin_2fa_enabled', 'exam_enabled', 'spin_enabled',
            ]
            for k in keys:
                # هر تب فقط فیلدهای خودش را ارسال می‌کند؛ تنظیمات تب‌های دیگر
                # نباید با ذخیرهٔ این تب خالی شوند.
                if k not in request.form:
                    continue
                v = request.form.get(k, '').strip()
                if k in _SECRET_SETTING_KEYS and not v:
                    continue
                # پرداخت ساختگی در نسخهٔ نهایی قابل فعال‌سازی نیست.
                if k == 'sandbox_mode':
                    v = '0'
                elif k == 'refund_days':
                    try:
                        v = str(max(0, min(90, int(v or 0))))
                    except ValueError:
                        v = '0'
                elif k in ('cashback_percent', 'loyalty_discount_percent',
                            'referral_bonus_percent', 'teacher_default_share'):
                    try:
                        v = str(max(0, min(50, int(v or 0))))
                    except ValueError:
                        v = '0'
                elif k == 'bnpl_max_installments':
                    try:
                        v = str(max(2, min(4, int(v or 4))))
                    except ValueError:
                        v = '4'
                elif k == 'shipping_flat_rate':
                    try:
                        v = str(max(0, int(v or 0)))
                    except ValueError:
                        v = '0'
                elif k == 'admin_2fa_enabled' and v == '1':
                    from sms import provider_ready
                    current_settings = {row.key: row.value for row in Setting.query.all()}
                    if not g.user.phone or not provider_ready(current_settings):
                        v = '0'
                        flash('تایید دومرحله‌ای فعال نشد؛ ابتدا شماره مدیر و سرویس پیامک واقعی را تکمیل و تست کنید.', 'error')
                st = db.session.get(Setting, k)
                if st:
                    st.value = v
                else:
                    db.session.add(Setting(key=k, value=v))
            # آپلود لوگو
            logo_f = request.files.get('custom_logo_file')
            if logo_f and logo_f.filename:
                up = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  'static', 'img', 'uploads', 'brand')
                os.makedirs(up, exist_ok=True)
                from validators import (safe_filename, ALLOWED_IMAGE_EXT_TRUSTED,
                                        file_content_is_safe)
                safe = safe_filename(logo_f.filename or '', ALLOWED_IMAGE_EXT_TRUSTED)
                # محتوای فایل هم چک شود — svg/تصویری که <script> داشته باشد رد می‌شود
                if safe and not file_content_is_safe(logo_f.stream,
                                                     os.path.splitext(safe)[1].lower()):
                    flash('فایل لوگو حاوی کد اجرایی است و پذیرفته نشد.', 'error')
                    safe = None
                if safe:
                    lname = 'logo' + os.path.splitext(safe)[1].lower()
                    logo_f.save(os.path.join(up, lname))
                    st = db.session.get(Setting, 'custom_logo')
                    # مسیر کانونی یکسان برای هر دو فرم تنظیمات (باگ قبلی:
                    # این فرم «uploads/brand/...» ذخیره می‌کرد که لوگو را می‌شکست)
                    if st:
                        st.value = '/static/img/uploads/brand/' + lname
                    else:
                        db.session.add(Setting(key='custom_logo',
                                               value='/static/img/uploads/brand/' + lname))
            db.session.commit()
            flash('تنظیمات با موفقیت ذخیره شد ✅', 'success')
            return redirect(url_for('admin.super_settings', tab=request.form.get('tab', '')))
        # ب) ریدایرکت‌های سئو
        if action == 'redirect_add':
            source = request.form.get('source', '').strip()
            target = request.form.get('target', '').strip()
            code = safe_int(request.form.get('code'), 301)
            if not source.startswith('/'):
                source = '/' + source
            if not target.startswith('/'):
                target = '/' + target
            if not source or not target:
                flash('مسیر مبدأ و مقصد الزامی است.', 'error')
            elif source == target:
                flash('مبدأ و مقصد نمی‌توانند یکسان باشند (حلقه ریدایرکت).', 'error')
            elif RedirectRule.query.filter_by(source=source).first():
                flash('این مسیر قبلاً ثبت شده است.', 'error')
            else:
                db.session.add(RedirectRule(source=source[:300], target=target[:300], code=code))
                db.session.commit()
                flash(f'ریدایرکت {source} → {target} اضافه شد ✅', 'success')
            return redirect(url_for('admin.super_settings', tab='seo'))
        if action == 'redirect_edit':
            rid = safe_int(request.form.get('rid'))
            rr = db.session.get(RedirectRule, rid)
            if rr:
                source = request.form.get('source', '').strip()
                target = request.form.get('target', '').strip()
                if not source.startswith('/'):
                    source = '/' + source
                if not target.startswith('/'):
                    target = '/' + target
                if source == target:
                    flash('حلقه ریدایرکت مجاز نیست.', 'error')
                else:
                    rr.source = source[:300]
                    rr.target = target[:300]
                    rr.code = safe_int(request.form.get('code'), 301)
                    db.session.commit()
                    flash('ریدایرکت ویرایش شد ✅', 'success')
            return redirect(url_for('admin.super_settings', tab='seo'))
        if action == 'redirect_delete':
            rr = db.session.get(RedirectRule, safe_int(request.form.get('rid')))
            if rr:
                db.session.delete(rr)
                db.session.commit()
                flash('ریدایرکت حذف شد.', 'info')
            return redirect(url_for('admin.super_settings', tab='seo'))
        if action == 'redirect_toggle':
            rr = db.session.get(RedirectRule, safe_int(request.form.get('rid')))
            if rr:
                rr.is_active = not rr.is_active
                db.session.commit()
            return redirect(url_for('admin.super_settings', tab='seo'))
        if action == 'notfound_to_redirect':
            # تبدیل ۴۰۴ پرتکرار به ریدایرکت
            path = request.form.get('path', '').strip()
            target = request.form.get('target', '').strip()
            if path and target:
                if not path.startswith('/'):
                    path = '/' + path
                if not target.startswith('/'):
                    target = '/' + target
                if path != target and not RedirectRule.query.filter_by(source=path).first():
                    db.session.add(RedirectRule(source=path[:300], target=target[:300], code=301))
                    db.session.commit()
                    flash(f'ریدایرکت از {path} ساخته شد ✅', 'success')
            return redirect(url_for('admin.super_settings', tab='seo'))
        if action == 'notfound_clear':
            try:
                from models import NotFoundLog as _NFL
                db.session.query(_NFL).delete()
                db.session.commit()
                flash('لاگ ۴۰۴ پاک شد.', 'info')
            except Exception:
                flash('خطا در پاک‌سازی لاگ.', 'error')
            return redirect(url_for('admin.super_settings', tab='seo'))

    # ── خواندن مقادیر فعلی ──
    from models import NotFoundLog as _NFL, Setting as _S
    vals = {}
    for st in _S.query.all():
        vals[st.key] = st.value
    rules = RedirectRule.query.order_by(RedirectRule.source).all()
    notfound = _NFL.query.order_by(_NFL.count.desc()).limit(15).all() if hasattr(_NFL, 'count') else _NFL.query.order_by(_NFL.id.desc()).limit(15).all()
    try:
        from sqlalchemy import inspect as _inspect
        db_engine_name = db.engine.dialect.name
        inspector = _inspect(db.engine)
        index_count = sum(len(inspector.get_indexes(table))
                          for table in inspector.get_table_names())
    except Exception:
        db_engine_name, index_count = 'نامشخص', 0
    return render_template('admin/super_settings.html', vals=vals, rules=rules,
                           notfound=notfound, tab=request.args.get('tab', 'general'),
                           redirect_count=RedirectRule.query.count(), settings_count=_S.query.count(),
                           db_engine_name=db_engine_name, index_count=index_count)


@admin_bp.route('/themes')
@admin_required
def themes():
    """مدیریت تم‌ها به «طراحی‌های سایت» منتقل شده است"""
    flash('مدیریت تم‌ها به بخش «طراحی‌های سایت» منتقل شد 🖼', 'info')
    return redirect(url_for('admin.designs'))



# ================================================================
# فروشگاه — مدیریت محصولات فیزیکی
# ================================================================
def _product_int(value, maximum=2_000_000_000):
    try:
        return max(0, min(maximum, int(value or 0)))
    except (TypeError, ValueError):
        return 0


def _save_product_image(file_storage, uploader_id=None):
    """ذخیره امن تصویر محصول + ثبت در کتابخانه رسانه مرکزی.

    برگرداندن مسیر نسبی (مثل uploads/products/product-xxx.jpg)؛
    اگر آپلود نامعتبر باشد None و خطا flash می‌شود.
    """
    if not file_storage or not file_storage.filename:
        return None
    from validators import (ALLOWED_IMAGE_EXT, file_content_is_safe,
                            safe_filename as _safe_filename)
    safe = _safe_filename(file_storage.filename, ALLOWED_IMAGE_EXT)
    ext = os.path.splitext(safe or '')[1].lower()
    if not safe or not file_content_is_safe(file_storage.stream, ext):
        flash('تصویر محصول معتبر نیست؛ فقط JPG، PNG، WebP، GIF یا AVIF امن مجاز است.', 'error')
        return None
    directory = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'static', 'img', 'uploads', 'products')
    os.makedirs(directory, exist_ok=True)
    filename = f'product-{uuid.uuid4().hex[:12]}{ext}'
    fpath = os.path.join(directory, filename)
    file_storage.save(fpath)
    try:
        from uploads_helper import compress_image_file
        compressed = compress_image_file(fpath)
        if compressed:
            width, height, size = compressed
    except Exception:
        _lexc('blueprints/admin_bp.py')
    # ثبت در کتابخانه رسانه مرکزی — تصویر آپلودشده اینجا هم قابل استفاده است
    try:
        from models import Media
        size = os.path.getsize(fpath)
        width = height = None
        try:
            from PIL import Image as _Img
            with _Img.open(fpath) as im:
                width, height = im.size
        except Exception:
            pass
        db.session.add(Media(filename=safe, path='uploads/products/' + filename,
                             mime=file_storage.mimetype or '', size=size,
                             width=width, height=height, kind='image',
                             uploaded_by=uploader_id or (getattr(g, 'user', None) and g.user.id)))
        db.session.flush()
    except Exception:
        _lexc('blueprints/admin_bp.py')
    return 'uploads/products/' + filename


@admin_bp.route('/products', methods=['GET', 'POST'])
@admin_required
def products_admin():
    """لیست محصولات + ساخت محصول جدید"""
    from models import Product as _P
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('عنوان محصول الزامی است.', 'error')
        else:
            import re as _re2
            from models import unique_slug_for
            slug = unique_slug_for(_P, title, fallback='product')
            from validators import clamp_field
            image_file = request.files.get('image_file')
            uploaded_image = _save_product_image(image_file)
            if image_file and image_file.filename and not uploaded_image:
                return redirect(url_for('admin.products_admin'))
            image = (uploaded_image or request.form.get('image', '').strip() or
                     'cover-product-mug.webp')
            _p = _P(
                title=title, slug=slug,
                description=clamp_field(request.form.get('description'), 'default'),
                price=_product_int(request.form.get('price')),
                discount_price=_product_int(request.form.get('discount_price')),
                image=image,
                category=clamp_field(request.form.get('category'), 'default'),
                sku=clamp_field(request.form.get('sku'), 'default'),
                dimensions=clamp_field(request.form.get('dimensions'), 'default'),
                weight=clamp_field(request.form.get('weight'), 'default'),
                material=clamp_field(request.form.get('material'), 'default'),
                features=request.form.get('features', '').strip(),
                stock=_product_int(request.form.get('stock'), maximum=10_000_000),
                featured=bool(request.form.get('featured')),
                is_active=True,
            )
            db.session.add(_p)
            db.session.commit()
            try:
                from seo_service import ensure_meta
                ensure_meta('/product/' + _p.slug)
                db.session.commit()
            except Exception:
                _lexc('blueprints/admin_bp.py')
            flash('محصول ساخته شد. آدرس عمومی: /product/' + slug, 'success')
        return redirect(url_for('admin.products_admin'))
    items = _P.query.order_by(_P.created_at.desc()).all()
    return render_template('admin/products.html', items=items)


@admin_bp.route('/products/<int:pid>/edit', methods=['GET', 'POST'])
@admin_required
def product_admin_edit(pid):
    from models import Product as _P
    p = db.get_or_404(_P, pid)
    if request.method == 'POST':
        from validators import clamp_field
        image_file = request.files.get('image_file')
        uploaded_image = _save_product_image(image_file)
        if image_file and image_file.filename and not uploaded_image:
            return redirect(url_for('admin.product_admin_edit', pid=p.id))
        p.title = clamp_field(request.form.get('title'), 'title') or p.title
        p.description = clamp_field(request.form.get('description'), 'default')
        p.price = _product_int(request.form.get('price'))
        p.discount_price = _product_int(request.form.get('discount_price'))
        p.image = uploaded_image or request.form.get('image', '').strip() or p.image
        p.category = clamp_field(request.form.get('category'), 'default')
        p.sku = clamp_field(request.form.get('sku'), 'default')
        p.dimensions = clamp_field(request.form.get('dimensions'), 'default')
        p.weight = clamp_field(request.form.get('weight'), 'default')
        p.material = clamp_field(request.form.get('material'), 'default')
        p.features = request.form.get('features', '').strip()
        p.stock = _product_int(request.form.get('stock'), maximum=10_000_000)
        p.featured = bool(request.form.get('featured'))
        p.is_active = bool(request.form.get('is_active'))
        db.session.commit()
        try:
            from seo_service import ensure_meta
            ensure_meta('/product/' + p.slug)
            db.session.commit()
        except Exception:
            _lexc('blueprints/admin_bp.py')
        flash('محصول به‌روزرسانی شد. ✏️', 'success')
        return redirect(url_for('admin.products_admin'))
    return render_template('admin/product_form.html', p=p)


@admin_bp.route('/products/<int:pid>/delete', methods=['POST'])
@admin_required
def product_admin_delete(pid):
    from models import Product as _P
    p = db.get_or_404(_P, pid)
    db.session.delete(p)
    db.session.commit()
    flash('محصول حذف شد.', 'info')
    return redirect(url_for('admin.products_admin'))

@admin_bp.route('/system/restart', methods=['POST'])
@admin_required
def system_restart():
    """ری‌استارت اپ روی هاست (Passenger/cPanel: tmp/restart.txt)."""
    import os as _os
    base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    written = []
    for rel in ('tmp/restart.txt', 'tmp/restart', 'instance/restart.txt'):
        path = _os.path.join(base, rel)
        try:
            _os.makedirs(_os.path.dirname(path), exist_ok=True)
            with open(path, 'a', encoding='utf-8') as fh:
                fh.write(str(utcnow()) + '\n')
            written.append(rel)
        except OSError:
            continue
    if written:
        flash('درخواست ری‌استارت ثبت شد (' + '، '.join(written) + '). اگر صفحه قدیمی ماند، در سی‌پنل Restart بزنید.', 'success')
    else:
        flash('نتوانستیم فایل ری‌استارت را بنویسیم. از پنل هاست Restart کنید.', 'error')
    return redirect(url_for('admin.update_page'))


@admin_bp.route('/faq', methods=['GET', 'POST'])
@admin_required
def faq_manage():
    """CMS سوالات متداول."""
    import json as _json
    row = db.session.get(Setting, 'faq_items')
    items = []
    if row and row.value:
        try:
            items = _json.loads(row.value)
        except Exception:
            items = []
    if not isinstance(items, list):
        items = []
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            q = (request.form.get('q') or '').strip()
            a = (request.form.get('a') or '').strip()
            icon = (request.form.get('icon') or '❓').strip()[:8]
            if q and a:
                items.append({'q': q[:300], 'a': a[:2000], 'icon': icon})
        elif action == 'delete':
            try:
                idx = int(request.form.get('idx') or -1)
                if 0 <= idx < len(items):
                    items.pop(idx)
            except (TypeError, ValueError):
                pass
        payload = _json.dumps(items, ensure_ascii=False)
        if row:
            row.value = payload
        else:
            db.session.add(Setting(key='faq_items', value=payload))
        db.session.commit()
        flash('سوالات متداول ذخیره شد.', 'success')
        return redirect(url_for('admin.faq_manage'))
    return render_template('admin/faq.html', items=items)


# بارگذاری بخش‌های تکمیلی (گزارش‌ها، رسانه، داستان موفقیت، اعلان‌ها، مشاوره‌ها)
# این import صرفاً برای اجرای decoratorهای @admin_bp.route در admin_extra است
# (star-import نمی‌کنیم تا namespace admin_bp آلودهٔ متغیرهای محلی admin_extra نشود)

@admin_bp.route('/pages-content', methods=['GET', 'POST'])
@admin_required
def pages_content():
    """ویرایش متن درباره ما و مقدمه تماس — مثل FAQ."""
    keys = ('about_text', 'contact_intro')
    if request.method == 'POST':
        for key in keys:
            value = (request.form.get(key) or '').strip()[:8000]
            row = db.session.get(Setting, key)
            if row:
                row.value = value
            else:
                db.session.add(Setting(key=key, value=value))
        db.session.commit()
        flash('متن صفحات درباره ما و تماس ذخیره شد.', 'success')
        return redirect(url_for('admin.pages_content'))
    vals = {k: ((db.session.get(Setting, k).value if db.session.get(Setting, k) else '') or '')
            for k in keys}
    return render_template('admin/pages_content.html', vals=vals)


import blueprints.admin_extra  # noqa: F401  (side-effect: رجیستر routeها)
