# -*- coding: utf-8 -*-
"""بخش‌های تکمیلی پنل ادمین — گزارش‌ها، رسانه، داستان موفقیت، اعلان گروهی، مشاوره‌ها
(تقسیم‌شده از admin_bp.py برای نگهداری بهتر)"""
import os
import uuid
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect, url_for, flash,
                   g, abort, jsonify, Response)
from sqlalchemy import func as _func

from models import (utcnow, db, User, Category, Course, Section, Lesson, Order, OrderItem,
                    Coupon, BlogPost, NewsletterEmail, ContactMessage,
                    Ticket, Setting, Enrollment, Review, PaymentProof, ActivityLog,
                    Quiz, QuizAttempt, Assignment, AssignmentSubmission,
                    LessonQuestion, Bundle, CustomForm, CustomFormEntry,
                    PayoutRequest, StudyDay, ForumTopic, ForumPost, LiveSession,
                    Installment, TicketReply, SuccessStory, Media, ExamAttempt,
                    CourseTeacher, QuestionBank, SeoMeta, Page, Notification)
from blueprints.admin_bp import admin_bp, admin_required
from validators import safe_filename, human_size, log_exc as _lexc
from jdates import jdate_num, jtime, fa


@admin_bp.route('/consultations', methods=['GET', 'POST'])
@admin_required
def consultations():
    """لیست درخواست‌های مشاوره (لیدهای فروش) — منوی منشی/ادمین"""
    if request.method == 'POST':
        mid = request.form.get('mid', type=int)
        msg = db.session.get(ContactMessage, mid) if mid else None
        if msg:
            if request.form.get('action') == 'read':
                msg.is_read = True
            elif request.form.get('action') == 'unread':
                msg.is_read = False
            elif request.form.get('action') == 'delete':
                db.session.delete(msg)
            db.session.commit()
        return redirect(url_for('admin.consultations'))
    leads = ContactMessage.query.filter(ContactMessage.subject.like('%مشاوره%')) \
        .order_by(ContactMessage.created_at.desc()).all()
    return render_template('admin/consultations.html', leads=leads)




@admin_bp.route('/success-stories', methods=['GET', 'POST'])
@admin_required
def success_stories():
    """داستان‌های موفقیت دانشجویان — مطالعات موردی"""
    from models import SuccessStory as _Story
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('نام دانشجو الزامی است.', 'error')
        else:
            db.session.add(_Story(
                name=name,
                role=request.form.get('role', '').strip(),
                course_id=int(request.form.get('course_id') or 0) or None,
                story=request.form.get('story', '').strip(),
                result=request.form.get('result', '').strip(),
                color=request.form.get('color', '#7c3aed'),
                is_active=bool(request.form.get('is_active')),
                sort=int(request.form.get('sort') or 0),
            ))
            db.session.commit()
            flash('داستان موفقیت اضافه شد. 🌟', 'success')
        return redirect(url_for('admin.success_stories'))
    stories = _Story.query.order_by(_Story.sort, _Story.id.desc()).all()
    courses = Course.query.filter_by(status='published').order_by(Course.title).all()
    return render_template('admin/success_stories.html', stories=stories, courses=courses)




@admin_bp.route('/success-stories/<int:sid>/delete', methods=['POST'])
@admin_required
def success_story_delete(sid):
    from models import SuccessStory as _Story
    s = _Story.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()
    flash('حذف شد.', 'success')
    return redirect(url_for('admin.success_stories'))




@admin_bp.route('/success-stories/<int:sid>/toggle', methods=['POST'])
@admin_required
def success_story_toggle(sid):
    from models import SuccessStory as _Story
    s = _Story.query.get_or_404(sid)
    s.is_active = not s.is_active
    db.session.commit()
    return redirect(url_for('admin.success_stories'))




@admin_bp.route('/notifications', methods=['GET', 'POST'])
@admin_required
def admin_notifications():
    """اعلان گروهی — ارسال به همه / نقش خاص / دانشجویان یک دوره"""
    from models import Notification as _Notif
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
        icon = request.form.get('icon', '🔔').strip() or '🔔'
        link = request.form.get('link', '').strip()
        audience = request.form.get('audience', 'all')
        role = request.form.get('role', '')
        course_id = request.form.get('course_id', type=int)
        if not title:
            flash('عنوان اعلان الزامی است.', 'error')
            return redirect(url_for('admin.admin_notifications'))
        if audience == 'all':
            targets = [u.id for u in User.query.filter_by(is_active=True)]
        elif audience == 'role' and role:
            targets = [u.id for u in User.query.filter_by(role=role, is_active=True)]
        elif audience == 'course' and course_id:
            targets = [e.user_id for e in Enrollment.query.filter_by(course_id=course_id)]
        else:
            targets = []
        for uid in targets:
            _Notif.notify(uid, title, body, icon, link)
        db.session.commit()
        flash(f'🔔 اعلان برای {len(targets)} کاربر ارسال شد.', 'success')
        try:
            db.session.add(ActivityLog(user_id=g.user.id, action='broadcast',
                                       detail=f'اعلان گروهی: {title} ({len(targets)} کاربر)',
                                       ip=request.headers.get('X-Forwarded-For', request.remote_addr or '')[:60]))
            db.session.commit()
        except Exception:
            _lexc('blueprints/admin_bp.py')
        return redirect(url_for('admin.admin_notifications'))
    recent = _Notif.query.order_by(_Notif.id.desc()).limit(60).all()
    courses = Course.query.filter_by(status='published').order_by(Course.title).all()
    return render_template('admin/notifications.html', recent=recent, courses=courses)





@admin_bp.route('/media', methods=['GET', 'POST'])
@admin_required
def media_library():
    """کتابخانه رسانه مرکزی — آپلود، مدیریت و انتخاب فایل‌ها"""
    from models import Media as _Media
    from PIL import Image as _Img
    if request.method == 'POST':
        # سهمیه روزانه ادمین: ۲۰۰ فایل
        from datetime import datetime as _dt, timedelta as _td
        _since = _dt.now() - _td(hours=24)
        _cnt = _Media.query.filter(_Media.uploaded_by == g.user.id, _Media.created_at >= _since).count()
        if _cnt >= 200:
            flash('سقف ۲۰۰ آپلود در روز رسید.', 'error')
            return redirect(url_for('admin.media_library'))
        files = request.files.getlist('files')
        saved = 0
        for f in files:
            if not f or not f.filename:
                continue
            from validators import safe_filename
            safe = safe_filename(f.filename or '')
            if not safe:
                continue
            import os as _os
            up = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)),
                               'static', 'uploads', 'media')
            _os.makedirs(up, exist_ok=True)
            ext = _os.path.splitext(safe)[1].lower()
            fname = 'm_' + uuid.uuid4().hex[:10] + ext
            fpath = _os.path.join(up, fname)
            f.save(fpath)
            size = _os.path.getsize(fpath)
            mime = f.mimetype or ''
            kind = 'file'
            if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.avif'):
                kind = 'image'
            elif ext in ('.mp4', '.webm', '.mov'):
                kind = 'video'
            elif ext in ('.mp3', '.wav', '.ogg'):
                kind = 'audio'
            width = height = None
            if kind == 'image' and ext != '.svg':
                try:
                    with _Img.open(fpath) as im:
                        width, height = im.size
                except Exception:
                    _lexc('blueprints/admin_bp.py')
            db.session.add(_Media(filename=safe, path='uploads/media/' + fname,
                                  mime=mime, size=size, width=width, height=height,
                                  kind=kind, uploaded_by=g.user.id))
            saved += 1
        db.session.commit()
        flash(f'📁 {saved} فایل به کتابخانه اضافه شد.', 'success')
        return redirect(url_for('admin.media_library'))

    q = request.args.get('q', '').strip()
    kind = request.args.get('kind', '').strip()
    query = _Media.query
    if q:
        query = query.filter(_Media.filename.ilike(f'%{q}%'))
    if kind:
        query = query.filter_by(kind=kind)
    items = query.order_by(_Media.id.desc()).limit(200).all()
    kinds = [r[0] for r in db.session.query(_Media.kind).distinct().all() if r[0]]
    total = _Media.query.count()
    return render_template('admin/media.html', items=items, q=q, kind=kind,
                           kinds=kinds, total=total)




@admin_bp.route('/media/<int:mid>/delete', methods=['POST'])
@admin_required
def media_delete(mid):
    """حذف فایل از کتابخانه (و از دیسک)"""
    from models import Media as _Media
    m = _Media.query.get_or_404(mid)
    import os as _os
    try:
        p = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'static', m.path)
        if _os.path.exists(p):
            _os.remove(p)
    except Exception:
        _lexc('blueprints/admin_bp.py')
    db.session.delete(m)
    db.session.commit()
    flash('فایل حذف شد. 🗑', 'success')
    return redirect(url_for('admin.media_library'))




@admin_bp.route('/reports')
@admin_required
def reports_index():
    """نمایه گزارش‌ها — ریدایرکت به اولین گزارش"""
    return redirect(url_for('admin.report_revenue_courses'))


@admin_bp.route('/reports/export')
@admin_required
def reports_export():
    """خروجی اکسل (CSV) گزارش فروش"""
    import csv, io
    from flask import Response
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['کد سفارش', 'کاربر', 'مبلغ کل', 'تخفیف', 'نهایی', 'درگاه', 'وضعیت', 'زمان'])
    for o in Order.query.order_by(Order.created_at.desc()).limit(2000).all():
        w.writerow([o.code, o.user.email if o.user else '', o.total, o.discount,
                    o.final_total, o.gateway or '', o.status,
                    jdate_num(o.created_at) + ' ' + jtime(o.created_at)])
    out = '\ufeff' + buf.getvalue()
    return Response(out, mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename=orders-report.csv'})





@admin_bp.route('/reports/revenue-courses')
@admin_required
def report_revenue_courses():
    """گزارش درآمد هر دوره"""
    from sqlalchemy import func as _func
    rows = []
    for c in Course.query.all():
        sold = db.session.query(_func.coalesce(_func.sum(OrderItem.price), 0)) \
            .filter(OrderItem.course_id == c.id,
                    OrderItem.order_id.in_(
                        db.session.query(Order.id).filter(Order.status == 'paid')
                    )).scalar() or 0
        cnt = Enrollment.query.filter_by(course_id=c.id).count()
        rows.append({'course': c.title, 'sold': sold, 'count': cnt})
    rows.sort(key=lambda r: -r['sold'])
    return render_template('admin/report_revenue_courses.html', rows=rows)




@admin_bp.route('/reports/coupons')
@admin_required
def report_coupons():
    """گزارش مصرف کدهای تخفیف"""
    from sqlalchemy import func as _func
    rows = []
    total_saved = 0
    for c in Coupon.query.all():
        orders = Order.query.filter(Order.coupon_id == c.id, Order.status == 'paid').all()
        used = len(orders)
        saved = sum(o.discount or 0 for o in orders)
        total_saved += saved
        rows.append({'coupon': c, 'used': used, 'saved': saved,
                     'revenue': sum(o.final_total for o in orders)})
    rows.sort(key=lambda r: -r['used'])
    return render_template('admin/report_coupons.html', rows=rows, total_saved=total_saved)




@admin_bp.route('/reports/feedback')
@admin_required
def report_feedback():
    """گزارش رضایت‌سنجی دوره‌ها"""
    from sqlalchemy import func as _func
    from models import CourseFeedback
    rows = []
    for c in Course.query.all():
        fb = CourseFeedback.query.filter_by(course_id=c.id).all()
        if not fb:
            continue
        avg = round(sum(f.score for f in fb) / len(fb), 1)
        recommend = sum(1 for f in fb if f.recommend)
        rows.append({'course': c.title, 'count': len(fb), 'avg': avg,
                     'recommend': recommend, 'pct': round(recommend * 100 / len(fb))})
    rows.sort(key=lambda r: -r['avg'])
    all_fb = CourseFeedback.query.all()
    overall = round(sum(f.score for f in all_fb) / len(all_fb), 1) if all_fb else 0
    return render_template('admin/report_feedback.html', rows=rows, overall=overall,
                           total=len(all_fb))




@admin_bp.route('/reports/teachers')
@admin_required
def report_teachers():
    """گزارش درآمد مدرس‌ها"""
    from sqlalchemy import func as _func
    from models import PayoutRequest, CourseTeacher
    rows = []
    for t in User.query.filter(User.role.in_(['teacher', 'admin'])).all():
        course_ids = [c.id for c in Course.query.filter_by(teacher_id=t.id).all()]
        course_ids += [ct.course_id for ct in CourseTeacher.query.filter_by(teacher_id=t.id).all()]
        revenue = 0
        students = 0
        if course_ids:
            revenue = db.session.query(_func.coalesce(_func.sum(OrderItem.price), 0)) \
                .filter(OrderItem.course_id.in_(course_ids),
                        OrderItem.order_id.in_(
                            db.session.query(Order.id).filter(Order.status == 'paid'))).scalar() or 0
            students = Enrollment.query.filter(Enrollment.course_id.in_(course_ids)).count()
        paid_out = sum(p.amount for p in PayoutRequest.query.filter_by(teacher_id=t.id, status='paid'))
        pending = sum(p.amount for p in PayoutRequest.query.filter_by(teacher_id=t.id, status='pending'))
        rows.append({'teacher': t, 'revenue': revenue, 'students': students,
                     'paid_out': paid_out, 'pending': pending,
                     'share': round(int(revenue or 0) * 50 / 100)})
    rows.sort(key=lambda r: -r['revenue'])
    return render_template('admin/report_teachers.html', rows=rows)




@admin_bp.route('/reports/exams')
@admin_required
def report_exams():
    """گزارش شبیه‌ساز آزمون"""
    from sqlalchemy import func as _func
    from models import ExamAttempt
    attempts = ExamAttempt.query.all()
    users = len({a.user_id for a in attempts})
    total_q = sum(a.total for a in attempts)
    correct = sum(a.score for a in attempts)
    avg_pct = round(correct * 100 / total_q) if total_q else 0
    cats = {}
    for a in attempts:
        c = cats.setdefault(a.category or '—', [0, 0])
        c[0] += 1
        c[1] += a.score
    cat_rows = sorted([{'cat': k, 'n': v[0], 'score': v[1]} for k, v in cats.items()],
                      key=lambda r: -r['n'])
    return render_template('admin/report_exams.html', attempts=attempts, users=users,
                           total_q=total_q, correct=correct, avg_pct=avg_pct,
                           cat_rows=cat_rows)




@admin_bp.route('/reports/popular-pages')
@admin_required
def report_popular_pages():
    """صفحات پربازدید"""
    from models import SeoMeta
    pages = []
    for c in Course.query.filter_by(status='published').all():
        pages.append({'url': '/course/' + c.slug, 'title': c.title, 'views': c.views or 0})
    for p in BlogPost.query.filter_by(published=True).all():
        pages.append({'url': '/blog/' + p.slug, 'title': p.title, 'views': p.views or 0})
    pages.sort(key=lambda r: -r['views'])
    return render_template('admin/report_popular_pages.html', pages=pages[:50])




@admin_bp.route('/reports/inactive-users')
@admin_required
def report_inactive_users():
    """کاربران غیرفعال"""
    from datetime import timedelta
    cutoff = (utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    users = User.query.filter(User.last_active.is_(None) |
                              (User.last_active < cutoff)).order_by(User.created_at.desc()).all()
    return render_template('admin/report_inactive_users.html', users=users)




@admin_bp.route('/reports/seo-health')
@admin_required
def report_seo_health():
    """صفحات بدون عنوان/توضیحات سئو"""
    from models import SeoMeta
    missing = []
    meta_paths = {m.path for m in SeoMeta.query.all()}
    # صفحات اصلی
    for path, name in [('/', 'خانه'), ('/courses', 'دوره‌ها'), ('/blog', 'وبلاگ'),
                       ('/faq', 'سوالات'), ('/contact', 'تماس'), ('/about', 'درباره'),
                       ('/teachers', 'مدرس‌ها'), ('/cart', 'سبد'), ('/terms', 'قوانین'),
                       ('/privacy', 'حریم خصوصی')]:
        m = SeoMeta.query.filter_by(path=path).first()
        missing.append({'path': path, 'name': name, 'has_meta': bool(m and m.title),
                        'title': m.title if m else '', 'desc': m.description if m else ''})
    for c in Course.query.filter_by(status='published').all():
        m = SeoMeta.query.filter_by(path='/course/' + c.slug).first()
        missing.append({'path': '/course/' + c.slug, 'name': c.title[:40],
                        'has_meta': bool(m and m.title),
                        'title': m.title if m else '', 'desc': m.description if m else ''})
    return render_template('admin/report_seo_health.html', rows=missing)




@admin_bp.route('/icons')
@admin_required
def icons_browser():
    """مرورگر آیکون‌ها — Tabler (390 آیکون) با کد کپی"""
    from icons import icon_names
    names = icon_names()
    return render_template('admin/icons_browser.html', names=names, total=len(names))


# ════════════════════════════════════════════════════════════
# 🔄 بروزرسانی خودکار نرم‌افزار از گیت
# ════════════════════════════════════════════════════════════
@admin_bp.route('/update')
@admin_required
def update_page():
    """صفحه بروزرسانی — دکمه + وضعیت + آدرس گیت قابل تنظیم"""
    from updater import get_repo_url
    repo = get_repo_url()
    if not repo:
        import subprocess as _sp
        try:
            r = _sp.run(['git', 'remote', 'get-url', 'origin'], capture_output=True,
                        text=True, timeout=10)
            if r.returncode == 0:
                repo = r.stdout.strip()
        except Exception:
            pass
    return render_template('admin/update.html', repo_url=repo,
                           is_super=g.user.role in ('super_admin', 'admin'))


@admin_bp.route('/update/save-repo', methods=['POST'])
@admin_required
def update_save_repo():
    """ذخیره آدرس مخزن گیت در تنظیمات"""
    from models import Setting as _S
    url = (request.form.get('repo_url') or '').strip()
    st = db.session.get(_S, 'git_repo_url')
    if st:
        st.value = url
    else:
        db.session.add(_S(key='git_repo_url', value=url))
    db.session.commit()
    flash('آدرس مخزن گیت ذخیره شد ✅', 'success')
    return redirect(url_for('admin.update_page'))


@admin_bp.route('/update/run', methods=['POST'])
@admin_required
def update_run():
    """شروع بروزرسانی در پس‌زمینه — فقط super_admin"""
    if g.user.role not in ('super_admin', 'admin'):
        return jsonify(ok=False, msg='فقط مدیر کل می‌تواند بروزرسانی کند.'), 403
    from updater import start_update
    started, msg = start_update()
    if not started:
        return jsonify(ok=False, msg=msg), 400
    return jsonify(ok=True, msg=msg)


@admin_bp.route('/update/status')
@admin_required
def update_status():
    """وضعیت بروزرسانی (polling)"""
    from updater import update_progress
    p = update_progress()
    return jsonify(**p)


@admin_bp.route('/update/log')
@admin_required
def update_log():
    """گزارش آخرین بروزرسانی‌ها"""
    import os as _os
    logf = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)),
                         'instance', 'update_history.json')
    rows = []
    try:
        with open(logf, encoding='utf-8') as f:
            rows = json.load(f)
    except Exception:
        rows = []
    return render_template('admin/update.html', repo_url='', is_super=True,
                           history=rows, view='log')


# ════════════════════════════════════════════════════════════
# 🛠 مدیریت نصب و اتصالات (زمپ / گیت / دیتابیس)
# ════════════════════════════════════════════════════════════
@admin_bp.route('/install-manager')
@admin_required
def install_manager():
    """صفحه جامع مدیریت نصب، اتصال زمپ (XAMPP)، گیت و وضعیت دیتابیس"""
    from installer import is_installed, check_db_health, env_db_url
    from updater import get_git_info, get_repo_url
    db_url_str = str(env_db_url() or '')
    db_type = 'mysql' if db_url_str.startswith('mysql') else 'sqlite'
    # پنهان‌سازی رمز در نمایش URL
    safe_db_url = db_url_str
    if '@' in safe_db_url and ':' in safe_db_url.split('@')[0]:
        parts = safe_db_url.split('@')
        user_pass = parts[0].rsplit(':', 1)
        safe_db_url = f"{user_pass[0]}:***@{parts[1]}"
    ok_health, msg_health = check_db_health()
    git_info = get_git_info()
    repo_url = get_repo_url()
    return render_template('admin/install_manager.html',
                           is_installed=is_installed(),
                           db_type=db_type,
                           safe_db_url=safe_db_url or 'sqlite:///instance/academy.db (پیش‌فرض محلی)',
                           db_ok=ok_health,
                           db_msg=msg_health,
                           git_info=git_info,
                           repo_url=repo_url,
                           is_super=g.user.role in ('super_admin', 'admin'))


@admin_bp.route('/install-manager/test-xampp', methods=['POST'])
@admin_required
def install_test_xampp():
    """تست اتصال به زمپ (XAMPP MySQL) + ساخت خودکار دیتابیس"""
    from installer import test_connection
    db_name = (request.form.get('db_name') or 'academy_db').strip()
    xampp_url = f"mysql+pymysql://root:@localhost:3306/{db_name}?charset=utf8mb4"
    ok, msg = test_connection(xampp_url)
    return jsonify(ok=ok, msg=msg, url=xampp_url)


@admin_bp.route('/install-manager/connect-xampp', methods=['POST'])
@admin_required
def install_connect_xampp():
    """اتصال پروژه به زمپ (XAMPP MySQL) و بروزرسانی فایل .env"""
    if g.user.role not in ('super_admin', 'admin'):
        return jsonify(ok=False, msg='فقط مدیر کل می‌تواند اتصال دیتابیس را تغییر دهد.'), 403
    from installer import test_connection, write_env_file, ensure_mysql_db
    from flask import current_app as _app
    db_name = (request.form.get('db_name') or 'academy_db').strip()
    xampp_url = f"mysql+pymysql://root:@localhost:3306/{db_name}?charset=utf8mb4"
    ok, msg = test_connection(xampp_url)
    if not ok:
        return jsonify(ok=False, msg=msg), 400
    try:
        ensure_mysql_db(xampp_url)
        write_env_file(xampp_url, _app.config.get('SECRET_KEY', 'academy-secret-key-1403'))
        return jsonify(ok=True, msg=f'اتصال به زمپ (دیتابیس `{db_name}`) برقرار شد و در .env ذخیره گردید ✅. لطفاً سرور را ری‌استارت کنید.')
    except Exception as e:
        return jsonify(ok=False, msg='خطا در اتصال به زمپ: ' + str(e)), 500


@admin_bp.route('/install-manager/test-git', methods=['POST'])
@admin_required
def install_test_git():
    """تست دسترسی به مخزن گیت (عمومی یا خصوصی)"""
    from updater import test_git_repo
    url = (request.form.get('repo_url') or '').strip()
    ok, msg = test_git_repo(url)
    return jsonify(ok=ok, msg=msg)


@admin_bp.route('/install-manager/migrate-db', methods=['POST'])
@admin_required
def install_migrate_db():
    """اجرای دستی مایگریشن خودکار دیتابیس"""
    if g.user.role not in ('super_admin', 'admin'):
        return jsonify(ok=False, msg='دسترسی غیرمجاز'), 403
    from updater import _migrate_db
    try:
        msg = _migrate_db()
        return jsonify(ok=True, msg='بروزرسانی ساختار دیتابیس انجام شد ✅ ' + msg)
    except Exception as e:
        return jsonify(ok=False, msg='خطا در مایگریشن دیتابیس: ' + str(e)), 500

