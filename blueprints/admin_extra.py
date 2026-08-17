# -*- coding: utf-8 -*-
"""بخش‌های تکمیلی پنل ادمین — گزارش‌ها، رسانه، داستان موفقیت، اعلان گروهی، مشاوره‌ها
(تقسیم‌شده از admin_bp.py برای نگهداری بهتر)"""
import hashlib
import hmac
import json
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
        from permissions import has_permission
        if not has_permission(g.user, 'track_leads') and not g.user.is_admin:
            abort(403)
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
    s = db.get_or_404(_Story, sid)
    db.session.delete(s)
    db.session.commit()
    flash('حذف شد.', 'success')
    return redirect(url_for('admin.success_stories'))




@admin_bp.route('/success-stories/<int:sid>/toggle', methods=['POST'])
@admin_required
def success_story_toggle(sid):
    from models import SuccessStory as _Story
    s = db.get_or_404(_Story, sid)
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
            from validators import file_content_is_safe as _fcs, ALLOWED_MEDIA_EXT as _AME
            safe = safe_filename(f.filename or '', _AME)
            if not safe:
                continue
            import os as _os
            # محتوای فایل هم چک شود (SVG/تصویر حاوی اسکریپت رد می‌شود)
            if not _fcs(f.stream, _os.path.splitext(safe)[1].lower()):
                continue
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
    m = db.get_or_404(_Media, mid)
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
    """صفحه بروزرسانی — بررسی نسخه، اجرای دستی و تنظیم شاخهٔ Git."""
    from updater import _display_repo, get_repo_url, get_update_branch
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
    return render_template('admin/update.html',
                           repo_url=_display_repo(repo),
                           branch=get_update_branch(),
                           webhook_url=request.url_root.rstrip('/') +
                           url_for('admin.github_update_webhook'),
                           is_super=g.user.role in ('super_admin', 'admin'))


@admin_bp.route('/update/save-repo', methods=['POST'])
@admin_required
def update_save_repo():
    """ذخیرهٔ آدرس مخزن و شاخهٔ هدف؛ URL ماسک‌شده توکن قبلی را حفظ می‌کند."""
    from models import Setting as _S
    from updater import _validate_repo_url
    url = (request.form.get('repo_url') or '').strip()
    branch = (request.form.get('branch') or '').strip()
    current = db.session.get(_S, 'git_repo_url')
    # اگر URL شامل ***@ است، کاربر همان مقدار قبلی را submit کرده است.
    if '***@' in url:
        if current and current.value:
            url = current.value.strip()
        else:
            # توکن از محیط آمده و مقدار ماسک‌شده نباید به‌عنوان URL واقعی ذخیره شود.
            url = ''
    if url:
        try:
            _validate_repo_url(url)
        except Exception as exc:
            flash(str(exc), 'error')
            return redirect(url_for('admin.update_page'))
    if current:
        current.value = url
    else:
        db.session.add(_S(key='git_repo_url', value=url))
    branch_row = db.session.get(_S, 'git_branch')
    if branch:
        if branch.startswith('refs/heads/'):
            branch = branch[len('refs/heads/'):]
        if ('..' in branch or '//' in branch or
                not all(ch.isalnum() or ch in '._/-' for ch in branch) or
                (not branch or not branch[0].isalnum())):
            flash('نام شاخهٔ گیت نامعتبر است.', 'error')
            return redirect(url_for('admin.update_page'))
    if branch_row:
        branch_row.value = branch
    elif branch:
        db.session.add(_S(key='git_branch', value=branch))
    db.session.commit()
    flash('تنظیمات مخزن گیت ذخیره شد ✅', 'success')
    return redirect(url_for('admin.update_page'))


@admin_bp.route('/update/check')
@admin_required
def update_check():
    """بررسی وجود نسخهٔ جدید، بدون reset یا تغییر دیتابیس."""
    from updater import UpdateError, check_for_update, get_repo_url
    # بررسی وجود مخزن
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
    if not repo:
        return jsonify(ok=False, msg='آدرس مخزن گیت تنظیم نشده است. لطفاً ابتدا آدرس مخزن را وارد و ذخیره کنید.'), 400
    try:
        result = check_for_update()
        return jsonify(result)
    except Exception as exc:
        msg = str(exc)
        if isinstance(exc, UpdateError):
            return jsonify(ok=False, msg=msg), 400
        return jsonify(ok=False, msg='خطا در بررسی مخزن: ' + msg[:300]), 500


@admin_bp.route('/update/run', methods=['POST'])
@admin_required
def update_run():
    """شروع بروزرسانی در پس‌زمینه — فقط مدیر مجاز به تغییر کد."""
    if g.user.role not in ('super_admin', 'admin'):
        return jsonify(ok=False, msg='فقط مدیر کل می‌تواند بروزرسانی کند.'), 403
    from updater import start_update, get_repo_url
    # بررسی وجود مخزن
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
    if not repo:
        return jsonify(ok=False, msg='آدرس مخزن گیت تنظیم نشده است. لطفاً ابتدا آدرس مخزن را وارد و ذخیره کنید.'), 400

    branch = (request.form.get('branch') or '').strip() or None
    started, msg = start_update(branch=branch)
    if not started:
        return jsonify(ok=False, msg=msg), 400
    return jsonify(ok=True, msg=msg)


@admin_bp.route('/update/status')
@admin_required
def update_status():
    """وضعیت بروزرسانی (polling)."""
    from updater import update_progress
    p = update_progress()
    return jsonify(**p)


@admin_bp.route('/update/webhook', methods=['POST'])
def github_update_webhook():
    """Webhook رسمی GitHub برای بروزرسانی خودکار پس از push.

    امنیت فقط با GITHUB_WEBHOOK_SECRET محیط انجام می‌شود؛ بدون secret این مسیر
    عمداً غیرفعال است و هیچ‌کس نمی‌تواند از بیرون reset اجرا کند.
    """
    secret = os.environ.get('GITHUB_WEBHOOK_SECRET', '')
    if not secret:
        return jsonify(ok=False, msg='Webhook بروزرسانی فعال نشده است.'), 503
    signature = request.headers.get('X-Hub-Signature-256', '')
    expected = 'sha256=' + hmac.new(secret.encode('utf-8'), request.get_data(),
                                    hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        return jsonify(ok=False, msg='امضای Webhook نامعتبر است.'), 401
    event = request.headers.get('X-GitHub-Event', '')
    if event == 'ping':
        return jsonify(ok=True, ignored=True, msg='Webhook آماده است ✅')
    if event != 'push':
        return jsonify(ok=True, ignored=True, msg='این نوع رویداد نادیده گرفته شد.')
    payload = request.get_json(silent=True) or {}
    ref = payload.get('ref', '')
    branch = ref[len('refs/heads/'):] if ref.startswith('refs/heads/') else ''
    from updater import get_update_branch, start_update
    configured = get_update_branch()
    if configured and configured.startswith('refs/heads/'):
        configured = configured[len('refs/heads/'):]
    if configured and branch != configured:
        return jsonify(ok=True, ignored=True, msg='Push روی شاخهٔ هدف نبود.')
    if not branch:
        return jsonify(ok=True, ignored=True, msg='شاخهٔ Push قابل تشخیص نیست.')
    started, msg = start_update(branch=branch)
    return jsonify(ok=started, started=started, msg=msg), (202 if started else 409)


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
    from installer import is_installed, check_db_health, env_db_url, detect_local_data
    from updater import _display_repo, get_git_info, get_repo_url
    db_url_str = str(env_db_url() or '')
    db_type = 'mysql' if db_url_str.startswith('mysql') else 'sqlite'
    local_data = detect_local_data()
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
                           repo_url=_display_repo(repo_url),
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


@admin_bp.route('/install-manager/inspect-db', methods=['POST'])
@admin_required
def install_inspect_db():
    """بررسی دیتابیس ساخته‌شده در سی‌پنل بدون تغییر داده."""
    from installer import build_db_url, inspect_database, validate_mysql, detect_local_data
    host = (request.form.get('host') or 'localhost').strip()
    port = (request.form.get('port') or '3306').strip()
    name = (request.form.get('name') or '').strip()
    user = (request.form.get('user') or '').strip()
    password = request.form.get('password') or ''
    err = validate_mysql(host, name, user)
    if err:
        return jsonify(ok=False, msg=err), 400
    url = build_db_url('mysql', host, port, name, user, password)
    report = inspect_database(url)
    report['local'] = detect_local_data()
    return jsonify(**report)


@admin_bp.route('/install-manager/attach-db', methods=['POST'])
@admin_required
def install_attach_db():
    """وصل دائمی به دیتابیس موجود — داده پاک نمی‌شود."""
    if g.user.role not in ('super_admin', 'admin'):
        return jsonify(ok=False, msg='فقط مدیر کل می‌تواند اتصال دیتابیس را تغییر دهد.'), 403
    from installer import (attach_existing_database, build_db_url, validate_mysql)
    host = (request.form.get('host') or 'localhost').strip()
    port = (request.form.get('port') or '3306').strip()
    name = (request.form.get('name') or '').strip()
    user = (request.form.get('user') or '').strip()
    password = request.form.get('password') or ''
    copy_sqlite = request.form.get('copy_sqlite') == '1'
    err = validate_mysql(host, name, user)
    if err:
        return jsonify(ok=False, msg=err), 400
    url = build_db_url('mysql', host, port, name, user, password)
    ok, msg = attach_existing_database(url, copy_from_sqlite=copy_sqlite)
    return jsonify(ok=ok, msg=msg), (200 if ok else 400)


@admin_bp.route('/install-manager/use-sqlite', methods=['POST'])
@admin_required
def install_use_sqlite():
    """استفاده از فایل SQLite آپلودشده در instance/academy.db."""
    if g.user.role not in ('super_admin', 'admin'):
        return jsonify(ok=False, msg='فقط مدیر کل می‌تواند اتصال دیتابیس را تغییر دهد.'), 403
    from installer import attach_existing_database
    ok, msg = attach_existing_database('', copy_from_sqlite=False)
    return jsonify(ok=ok, msg=msg), (200 if ok else 400)


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

