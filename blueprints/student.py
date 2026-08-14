# -*- coding: utf-8 -*-
"""پنل دانشجو: داشبورد، یادگیری، علاقه‌مندی‌ها، سفارش‌ها، تیکت‌ها، پروفایل، گواهینامه"""
import os
import uuid
try:
    from datetime import UTC
except ImportError:  # پایتون < 3.11 (هاست‌های اشتراکی)
    from datetime import timezone as _tz_utc
    UTC = _tz_utc.utc
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort, session
from models import (utcnow, db, User, Course, Enrollment, Favorite, Order, Ticket, ActivityLog, StudyDay)
from validators import youtube_id, aparat_hash, is_valid_phone, is_valid_national_code
from validators import log_exc as _lexc

student_bp = Blueprint('student', __name__)


def _login_required():
    if not g.user:
        flash('ابتدا وارد حساب خود شوید.', 'error')
        return redirect(url_for('auth.login', next=request.path))
    return None


@student_bp.route('/dashboard')
def dashboard():
    r = _login_required()
    if r:
        return r
    from sqlalchemy.orm import selectinload as _sil
    enrollments = (Enrollment.query
                   .options(_sil(Enrollment.course).selectinload(Course.sections),
                            _sil(Enrollment.course).joinedload(Course.category))
                   .filter_by(user_id=g.user.id).all())
    in_progress = [e for e in enrollments if not e.is_completed]
    orders = Order.query.filter_by(user_id=g.user.id).order_by(Order.created_at.desc()).limit(5).all()
    stats = dict(
        courses=len(enrollments),
        completed=sum(1 for e in enrollments if e.is_completed),
        favorites=Favorite.query.filter_by(user_id=g.user.id).count(),
        orders=Order.query.filter_by(user_id=g.user.id).count(),
    )
        # یادآور ادامه یادگیری: دوره‌ای که شروع شده ولی ۷+ روز است پیشرفت نداشته
    from models import Enrollment as _E
    reminder = None
    try:
        for e in _E.query.filter_by(user_id=g.user.id).all():
            if 0 < e.percent < 100 and e.updated_at:
                if (utcnow() - e.updated_at.replace(tzinfo=None)).days >= 7:
                    reminder = e
                    break
    except Exception:
        _lexc('blueprints/student.py')
    # پیشنهاد شخصی‌سازی‌شده: بر اساس علاقه‌مندی و دوره‌های قبلی
    from models import Favorite as _F
    suggested = []
    try:
        favs = _F.query.filter_by(user_id=g.user.id).all()
        fav_cats = {f.course.category_id for f in favs if f.course and f.course.category_id}
        my_cats = {c.course.category_id for c in g.user.enrollments if c.course and c.course.category_id}
        cats = (fav_cats | my_cats) - {None}
        if cats:
            suggested = Course.query.filter(Course.category_id.in_(cats),
                                            Course.status == 'published',
                                            ~Course.id.in_([c.id for c in g.user.enrollments])) \
                .order_by(Course.views.desc()).limit(3).all()
        if not suggested:
            suggested = Course.query.filter(Course.status == 'published',
                                            ~Course.id.in_([c.id for c in g.user.enrollments])) \
                .order_by(Course.views.desc()).limit(3).all()
    except Exception:
        _lexc('blueprints/student.py')
    return render_template('dashboard/overview.html', enrollments=enrollments,
                           in_progress=in_progress, orders=orders, stats=stats,
                           reminder=reminder, suggested=suggested)


@student_bp.route('/dashboard/my-courses')
def my_courses():
    r = _login_required()
    if r:
        return r
    from sqlalchemy.orm import selectinload as _sil
    enrollments = (Enrollment.query
                   .options(_sil(Enrollment.course).joinedload(Course.category),
                            _sil(Enrollment.course).selectinload(Course.sections))
                   .filter_by(user_id=g.user.id).all())
    return render_template('dashboard/my_courses.html', enrollments=enrollments)


@student_bp.route('/learn/<int:course_id>')
def learn(course_id):
    r = _login_required()
    if r:
        return r
    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(user_id=g.user.id, course_id=course.id).first()
    if not enrollment:
        flash('شما در این دوره ثبت‌نام نکرده‌اید.', 'error')
        return redirect(url_for('site.course_detail', slug=course.slug))
    # مدت دسترسی: اگر دوره محدودیت روز دارد و منقضی شده
    if course.access_days and course.access_days > 0:
        from datetime import timedelta as _td
        expire = (enrollment.created_at + _td(days=course.access_days)).replace(tzinfo=None)
        if utcnow() > expire:
            flash('مدت دسترسی شما به این دوره به پایان رسیده است. برای تمدید با پشتیبانی تماس بگیرید.', 'error')
            return redirect(url_for('site.course_detail', slug=course.slug))
    lesson_id = request.args.get('lesson', type=int)
    lessons = course.lessons
    current = next((l for l in lessons if l.id == lesson_id), lessons[0] if lessons else None)
    done = set(enrollment.progress_list())
    yt_id = youtube_id(current.video_url) if current.video_type == 'youtube' else None
    ap_hash = aparat_hash(current.video_url) if current.video_type == 'aparat' else None
    # دسترسی تدریجی: جلسات قفل تا تاریخ باز شدن
    from datetime import timedelta as _td
    locked = {}
    for l in lessons:
        if l.release_days and l.release_days > 0 and not l.is_free:
            unlock = (enrollment.created_at + _td(days=l.release_days)).replace(tzinfo=None)
            if utcnow() < unlock:
                locked[l.id] = (unlock - utcnow()).days + 1
    # چک‌پوینت یادگیری: بعد از هر ۵ جلسه، پیشنهاد کوییز
    from models import Quiz as _Quiz
    checkpoint_quiz = None
    try:
        if len(done) >= 5 and len(done) % 5 == 0:
            checkpoint_quiz = _Quiz.query.filter_by(course_id=course.id, is_placement=False).first()
    except Exception:
        _lexc('blueprints/student.py')
    return render_template('dashboard/learn.html', course=course, enrollment=enrollment,
                           lessons=lessons, current=current, done=done,
                           yt_id=yt_id, ap_hash=ap_hash, locked=locked,
                           checkpoint_quiz=checkpoint_quiz)


@student_bp.route('/learn/<int:course_id>/complete/<int:lesson_id>', methods=['POST'])
def complete_lesson(course_id, lesson_id):
    if not g.user:
        abort(403)
    enrollment = Enrollment.query.filter_by(user_id=g.user.id, course_id=course_id).first_or_404()
    lessons = Course.query.get_or_404(course_id).lessons
    lesson = next((l for l in lessons if l.id == lesson_id), None)
    if not lesson:
        abort(404)
    done = set(enrollment.progress_list())
    action = request.form.get('action', 'complete')
    if action == 'complete':
        done.add(lesson_id)
    else:
        done.discard(lesson_id)
    enrollment.save_progress(sorted(done))
    if enrollment.percent >= 100 and not enrollment.completed_at:
        enrollment.completed_at = utcnow()
    from gamification import award_points, record_streak
    record_streak(g.user)
    if action == 'complete':
        award_points(g.user, 10, f'تکمیل جلسه «{lesson.title}»')
        from datetime import date as _date
        today = _date.today().isoformat()
        sd = StudyDay.query.filter_by(user_id=g.user.id, day=today).first()
        if sd:
            sd.lessons_done += 1
        else:
            db.session.add(StudyDay(user_id=g.user.id, day=today, lessons_done=1))
    db.session.commit()
    return redirect(url_for('student.learn', course_id=course_id, lesson=lesson_id))


@student_bp.route('/certificate/<int:course_id>')
def certificate(course_id):
    r = _login_required()
    if r:
        return r
    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(user_id=g.user.id, course_id=course.id).first_or_404()
    if not enrollment.is_completed:
        flash('برای دریافت گواهینامه باید تمام جلسات دوره را کامل کنید.', 'error')
        return redirect(url_for('student.learn', course_id=course.id))
    from models import certificate_code
    code = certificate_code(course.slug, g.user.email, enrollment.id)
    return render_template('certificate.html', course=course, enrollment=enrollment, code=code)


    try:
        from models import Notification
        Notification.notify(g.user.id, 'گواهینامه شما صادر شد 🏅',
                            f'گواهی دوره «{course.title}» آماده دانلود است.',
                            '🏅', url_for('student.certificate', course_id=course_id))
        from models import certificate_code
        cert_code = certificate_code(course.slug, g.user.email, enrollment.id)
        from email_service import send_certificate_email
        if g.user.email:
            send_certificate_email(g.user, course, cert_code, g.settings)
        db.session.commit()
    except Exception:
        _lexc('blueprints/student.py')
@student_bp.route('/dashboard/favorites')
def favorites():
    r = _login_required()
    if r:
        return r
    favs = Favorite.query.filter_by(user_id=g.user.id).order_by(Favorite.created_at.desc()).all()
    return render_template('dashboard/favorites.html', favs=favs)


@student_bp.route('/dashboard/orders')
def orders():
    r = _login_required()
    if r:
        return r
    from sqlalchemy.orm import selectinload as _sil
    orders = (Order.query
              .options(_sil(Order.items), _sil(Order.installments))
              .filter_by(user_id=g.user.id)
              .order_by(Order.created_at.desc()).all())
    from gateways import GATEWAY_MAP as _gmap
    return render_template('dashboard/orders.html', orders=orders,
                           installments={o.id: o.installments for o in orders},
                           gateway_names={k: v['name'] for k, v in _gmap.items()})


@student_bp.route('/invoice/<code>')
def invoice(code):
    if not g.user:
        return redirect(url_for('auth.login'))
    order = Order.query.filter_by(code=code).first_or_404()
    if order.user_id != g.user.id and not g.user.is_admin:
        abort(403)
    return render_template('dashboard/invoice.html', order=order)


@student_bp.route('/invoice/<code>/pdf')
def invoice_pdf(code):
    """فاکتور PDF واقعی (reportlab + وزیرمتن) — با fallback به HTML چاپی"""
    if not g.user:
        return redirect(url_for('auth.login'))
    order = Order.query.filter_by(code=code).first_or_404()
    if order.user_id != g.user.id and not g.user.is_admin:
        abort(403)
    items = [(oi.course.title if oi.course else 'دوره حذف‌شده',
              1, oi.price, oi.price or 0)
             for oi in order.items]
    from flask import Response
    try:
        from invoice_pdf import build_invoice_pdf
        pdf_bytes = build_invoice_pdf(order, g.settings, g.user, items)
        return Response(pdf_bytes, mimetype='application/pdf',
                        headers={'Content-Disposition': f'inline; filename=invoice-{code}.pdf'})
    except Exception as e:
        # fallback: HTML چاپی (در صورت نبود reportlab یا خطای فونت)
        print('PDF error, falling back to print HTML:', e)
        html = render_template('dashboard/invoice_print.html', order=order)
        return Response(html, mimetype='text/html',
                        headers={'Content-Disposition': f'inline; filename=invoice-{code}.html'})


# ---------------------------------------------------------------- تیکت‌ها
@student_bp.route('/dashboard/tickets')
def tickets():
    r = _login_required()
    if r:
        return r
    tickets = Ticket.query.filter_by(user_id=g.user.id).order_by(Ticket.created_at.desc()).all()
    return render_template('dashboard/tickets.html', tickets=tickets)


@student_bp.route('/dashboard/tickets/new', methods=['GET', 'POST'])
def ticket_new():
    r = _login_required()
    if r:
        return r
    if request.method == 'POST':
        from validators import clamp_field
        subject = clamp_field(request.form.get('subject'), 'subject')
        body = request.form.get('body', '').strip()
        if len(subject) < 3 or not body:
            flash('موضوع و متن تیکت را کامل وارد کنید.', 'error')
        else:
            db.session.add(Ticket(user_id=g.user.id, subject=subject, body=body))
            db.session.commit()
            flash('تیکت شما ثبت شد. پاسخ در اسرع وقت ارسال می‌شود.', 'success')
            return redirect(url_for('student.tickets'))
    return render_template('dashboard/ticket_new.html')


# ---------------------------------------------------------------- پروفایل
@student_bp.route('/dashboard/profile', methods=['GET', 'POST'])
def profile():
    r = _login_required()
    if r:
        return r
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        nc = request.form.get('national_code', '').strip()
        bio = request.form.get('bio', '').strip()
        color = request.form.get('avatar_color', '#2563eb')
        password = request.form.get('password', '')
        err = None
        if len(name) < 3:
            err = 'نام و نام خانوادگی را کامل وارد کنید.'
        elif not is_valid_phone(phone):
            err = 'شماره تماس معتبر نیست — باید با 09 شروع شود و ۱۱ رقم باشد.'
        elif User.query.filter(User.phone == phone, User.id != g.user.id).first():
            err = 'این شماره تماس قبلاً برای حساب دیگری ثبت شده است.'
        elif nc and not is_valid_national_code(nc):
            err = 'کد ملی معتبر نیست — کد ملی ۱۰ رقمی صحیح خود را وارد کنید.'
        elif nc and User.query.filter(User.national_code == nc, User.id != g.user.id).first():
            err = 'این کد ملی قبلاً ثبت شده است.'
        elif password and len(password) < 6:
            err = 'رمز عبور باید حداقل ۶ کاراکتر باشد.'
        if err:
            flash(err, 'error')
            return redirect(url_for('student.profile'))
        g.user.name = name
        g.user.phone = phone
        g.user.national_code = nc or None
        g.user.bio = bio
        g.user.avatar_color = color
        g.user.notify_email = bool(request.form.get('notify_email'))
        g.user.notify_sms = bool(request.form.get('notify_sms'))
        # اطلاعات تکمیلی پروفایل (فرم کامل)
        from validators import clamp_field
        g.user.national_id = clamp_field(request.form.get('national_id'), 'default')
        g.user.birth_date = clamp_field(request.form.get('birth_date'), 'default')
        g.user.education_level = clamp_field(request.form.get('education_level'), 'default')
        g.user.education_major = clamp_field(request.form.get('education_major'), 'default')
        g.user.marital_status = clamp_field(request.form.get('marital_status'), 'default')
        if password:
            g.user.set_password(password)
        # آپلود عکس پروفایل
        f = request.files.get('avatar')
        if f and f.filename:
            up = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'static', 'img', 'uploads', 'avatars')
            os.makedirs(up, exist_ok=True)
            from validators import safe_filename, ALLOWED_IMAGE_EXT
            safe = safe_filename(f.filename or '', ALLOWED_IMAGE_EXT)
            if safe:
                fname = f'av_{g.user.id}_{uuid.uuid4().hex[:6]}{os.path.splitext(safe)[1].lower()}'
                f.save(os.path.join(up, fname))
                # حذف آواتار قبلی (جلوگیری از زباله دیسک)
                if g.user.avatar and g.user.avatar.startswith('av_'):
                    try:
                        _old = os.path.join(up, g.user.avatar)
                        if os.path.exists(_old) and _old != os.path.join(up, fname):
                            os.remove(_old)
                    except OSError:
                        pass
                g.user.avatar = fname
        db.session.commit()
        flash('پروفایل شما با موفقیت به‌روزرسانی شد.', 'success')
    colors = ['#2563eb', '#7c3aed', '#059669', '#dc2626', '#ea580c', '#db2777', '#0891b2', '#f59e0b']
    return render_template('dashboard/profile.html', colors=colors)


@student_bp.route('/dashboard/logout-all', methods=['POST'])
def logout_all():
    """خروج از همه دستگاه‌ها — تغییر توکن سشن"""
    r = _login_required()
    if r:
        return r
    g.user.new_session_token()
    db.session.add(ActivityLog(user_id=g.user.id, action='logout_all', detail='خروج از همه دستگاه‌ها'))
    db.session.commit()
    session.clear()
    flash('با موفقیت از همه دستگاه‌ها خارج شدید. 🔐', 'success')
    return redirect(url_for('auth.login'))
