# -*- coding: utf-8 -*-
"""دامنهٔ آموزش — دوره، دسته، جلسه، آزمون، تمرین، باندل و بانک سوال.

Route های این دامنه روی Blueprint مشترک ``admin_bp`` (از ``admin_core``)
ثبت می‌شوند؛ ``blueprints/admin_bp.py`` در انتهای خود این ماژول را
import می‌کند تا ثبت انجام شود. هیچ منطقی اینجا نباید مستقیماً
``db.session.commit()`` صدا بزند یا ورودی خام فرم را کست کند — هر دو
از ``admin_core`` می‌آیند.
"""
from __future__ import annotations

import json

from datetime import datetime, timedelta
from flask import (render_template, request, redirect, url_for, flash, g, abort, send_from_directory, Response)
from admin_queries import course_list
from admin_core import (
    form,
    commit,
    go_referrer,
    COVER_IMAGES,
    best_effort,
    admin_bp, admin_required
)
from models import (
    Assignment, AssignmentSubmission, Bundle, BundleCourse, Category, Course,
    DELIVERY_TYPES, Enrollment, Favorite, ForumTopic, Lesson, LessonQuestion,
    Notification, OrderItem, QuestionBank, Quiz, QuizQuestion, Section, Setting, User,
    db, unique_slug_for, utcnow
)
from validators import (
    human_size,csv_cell, detect_video, safe_int, safe_referrer, log_exc as _lexc)
from jdates import (jdate_num)

# ----------------------------------------------------------- پیوست/زیرنویس جلسه
def _save_lesson_file(f):
    """ذخیرهٔ فایل پیوست جلسه (پروژه/دیتا) و بازگرداندن اطلاعات آن.

    نام فایل روی دیسک همیشه ``lesson_<uuid>_<safe>`` است: بخشی از مسیر هرگز
    مستقیماً از ورودی کاربر ساخته نمی‌شود.
    """
    if not f or not f.filename:
        return None
    import os as _os
    import uuid as _uuid

    from uploads_helper import uploads_dir, uploads_url
    from validators import safe_filename
    safe = safe_filename(f.filename or '')
    if not safe:
        return None
    name = 'lesson_' + _uuid.uuid4().hex[:8] + '_' + safe
    path = _os.path.join(uploads_dir('lessons'), name)
    f.save(path)
    return {'url': uploads_url('lessons', name),
            'name': f.filename,
            'size': human_size(_os.path.getsize(path))}


#: تنها پسوندهای زیرنویس که پذیرفته می‌شوند.
_CAPTION_EXT = ('.srt', '.vtt')
#: سقف حجم زیرنویس — یک مگابایت.
_CAPTION_MAX_BYTES = 1024 * 1024


def _save_lesson_captions(f):
    """ذخیرهٔ زیرنویس جلسه (فقط ``srt``/``vtt``)؛ نام فایل یا ``None``.

    زیرنویس در پلیر رندر می‌شود، پس یک فایل متنی می‌تواند حامل اسکریپت باشد.
    سه لایه: پسوند مجاز، سقف حجم، و رد کردن محتوایی که نشانهٔ HTML دارد.
    """
    if not f or not f.filename:
        return None
    import os as _os
    import uuid as _uuid

    ext = _os.path.splitext((f.filename or '').lower())[1]
    if ext not in _CAPTION_EXT:
        return None
    try:
        data = f.read(_CAPTION_MAX_BYTES + 1)
    except Exception:
        return None
    if not data or len(data) > _CAPTION_MAX_BYTES:
        return None
    head = data[:2000].lower()
    if any(marker in head for marker in (b'<script', b'<!doctype', b'<html')):
        return None
    from uploads_helper import uploads_dir
    name = 'cap_' + _uuid.uuid4().hex[:8] + ext
    with open(_os.path.join(uploads_dir('lessons'), name), 'wb') as out:
        out.write(data)
    return name


def _sections_lessons(course):
    """سکشن‌ها همراه با جلساتشان — یک ساختار ثابت برای قالب."""
    return [(section, section.lessons) for section in course.sections]




@admin_bp.route('/courses')
@admin_required
def courses():
    """فهرست دوره‌ها.

    دو اصلاح: صفحه‌بندی (قبلاً همهٔ دوره‌ها یکجا بارگذاری و رندر می‌شد) و
    پیش‌بارگذاری ``category``/``teacher`` (قبلاً قالب برای هر ردیف دو کوئری
    اضافه می‌زد).
    """
    q = request.args.get('q', '').strip()
    items, page, pages, total = course_list(q)
    return render_template('admin/courses.html', courses=items, q=q,
                           total=total, page=page, pages=pages)


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
    teachers = User.query.filter(User.role.in_(['teacher', 'admin'])).all()
    categories = Category.query.all()
    images = COVER_IMAGES
    if request.method == 'POST':
        f = request.form
        ff = form()   # ورودی عددی هرگز خام کست نمی‌شود — clamp + بدون استثنا
        was_new = course is None
        _old_path_c = ('/course/' + course.slug) if (course and course.slug) else None
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
        course.category_id = ff.int('category_id') or None
        course.teacher_id = ff.int('teacher_id') or None
        course.price = ff.int('price', lo=0)
        course.discount_price = ff.int('discount_price', lo=0)
        course.level = f.get('level', 'مقدماتی')
        course.duration_hours = ff.int('duration_hours', lo=0)
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
        course.access_days = ff.int('access_days', lo=0)
        course.delivery_type = f.get('delivery_type', 'online')
        from models import DELIVERY_TYPES
        if course.delivery_type not in DELIVERY_TYPES:
            course.delivery_type = 'online'
        course.allow_download = bool(f.get('allow_download'))
        course.attendance_required_percent = ff.int('attendance_required_percent', 75, lo=0, hi=100)
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
        course.unlock_per_installment = ff.int('unlock_per_installment', 0, lo=0, hi=500)
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
            total_co_share = 0
            for tid in selected_ids:
                share_raw = f.get('co_share_{}'.format(tid), '').strip()
                share = None
                if share_raw.isdigit():
                    share = max(0, min(100, int(share_raw)))
                    total_co_share += share
                db.session.add(_CT(course_id=course.id, teacher_id=tid,
                                   share_percent=share))
            if total_co_share > 100:
                flash('هشدار: مجموع درصد مدرسین همکار بیش از ۱۰۰٪ است و سهم آن‌ها در سقف ۱۰۰٪ متعادل محاسبه خواهد شد.', 'warning')
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
            # ایندکس سریع در Bing — کار جانبی که هرگز نباید ذخیرهٔ دوره را بشکند.
            if course.status == 'published' and course.slug:
                def _index_bing():
                    from integrations import submit_bing_async
                    submit_bing_async(request.host_url.rstrip('/') +
                                      url_for('site.course_detail', slug=course.slug))
                best_effort(_index_bing, 'admin.course_index')
            commit(context='admin._course_form')
            def _sync_seo():
                from seo_service import ensure_meta, save_seo_from_form
                _p_c = '/course/' + (course.slug or str(course.id))
                ensure_meta(_p_c)
                commit(context='admin._course_form')
                save_seo_from_form(_p_c, f, old_path=_old_path_c)
                commit(context='admin._course_form')
            best_effort(_sync_seo, 'admin.course_seo')
            if course.status == 'published' and course.slug:
                flash('دوره ذخیره شد. آدرس عمومی: /course/' + course.slug +
                      '  —  اگر ۴۰۴ دیدید از /c/' + str(course.id) + ' استفاده کنید.', 'success')
            else:
                flash('دوره به‌صورت پیش‌نویس ذخیره شد و تا انتشار در سایت ۴۰۴ می‌دهد. از همین فرم وضعیت را «منتشر شده» کنید.', 'info')
            return redirect(url_for('admin.course_lessons', cid=course.id))
    _seo_c = None
    if course and course.slug:
        from seo_service import get_seo_for
        _seo_c = get_seo_for('/course/' + course.slug)
    return render_template('admin/course_form.html', course=course, teachers=teachers,
                           categories=categories, images=images, seo=_seo_c)


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
    commit(success='دوره حذف شد.', category='info')
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
                commit(success='سکشن اضافه شد.')
        elif action == 'del_section':
            sec = db.session.get(Section, safe_int(request.form.get('sid')))
            if sec and sec.course_id == course.id:
                db.session.delete(sec)
                commit(success='سکشن حذف شد.', category='info')
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
                _cap = _save_lesson_captions(request.files.get('captions_file'))
                db.session.add(Lesson(section_id=sec.id, title=title,
                                      video_type=_vtype,
                                      video_url=_vurl,
                                      video_url_hd=request.form.get('video_url_hd', '').strip() or None,
                                      captions=_cap,
                                      file_url=fl['url'] if fl else None,
                                      file_name=fl['name'] if fl else None,
                                      file_size=fl['size'] if fl else None,
                                      duration=request.form.get('duration') or '00:10:00',
                                      release_days=request.form.get('release_days', 0, type=int),
                                      is_free=bool(request.form.get('is_free')),
                                      content=request.form.get('content', '').strip(),
                                      sort=len(sec.lessons)))
                commit(success='جلسه اضافه شد.')
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
                les.video_url_hd = request.form.get('video_url_hd', '').strip() or None
                _cap = _save_lesson_captions(request.files.get('captions_file'))
                if _cap:
                    les.captions = _cap
                fl = _save_lesson_file(request.files.get('file'))
                if fl:
                    les.file_url, les.file_name, les.file_size = fl['url'], fl['name'], fl['size']
                commit(success='جلسه ویرایش شد.')
        elif action == 'del_lesson':
            les = db.session.get(Lesson, safe_int(request.form.get('lid')))
            if les and les.section.course_id == course.id:
                db.session.delete(les)
                commit(success='جلسه حذف شد.', category='info')
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
            if not name:
                flash('نام دسته‌بندی را وارد کنید.', 'error')
            elif Category.query.filter_by(name=name).first():
                flash('دسته‌بندی با همین نام از قبل وجود دارد.', 'error')
            else:
                # اسلاگ باید یکتا باشد: دو نام متفاوت («برنامه‌نویسی وب» و
                # «برنامه نویسی وب») می‌توانند به یک اسلاگ برسند. بدون این،
                # درج دوم با IntegrityError کل صفحه را با خطای ۵۰۰ می‌شکست.
                from models import unique_slug_for
                db.session.add(Category(
                    name=name,
                    slug=unique_slug_for(Category, name, fallback='category'),
                    icon=request.form.get('icon', '📚'),
                    color=request.form.get('color', '#2563eb'),
                    description=request.form.get('description', ''),
                    sort=safe_int(request.form.get('sort'))))
                try:
                    db.session.commit()
                    flash('دسته‌بندی اضافه شد.', 'success')
                except Exception:
                    db.session.rollback()
                    _lexc('admin_bp.py')
                    flash('ثبت دسته‌بندی ناموفق بود؛ دوباره تلاش کنید.', 'error')
        elif action == 'delete':
            c = db.session.get(Category, safe_int(request.form.get('cid')))
            if c:
                db.session.delete(c)
                commit(success='دسته\u200cبندی حذف شد.', category='info')
        return redirect(url_for('admin.categories'))
    cats = Category.query.order_by(Category.sort).all()
    return render_template('admin/categories.html', cats=cats)


# ---------------------------------------------------------------- کاربران


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
                     is_published=bool(request.form.get('is_published')),
                     time_limit=request.form.get('time_limit', 0, type=int))
            db.session.add(q)
            commit(context='admin.quiz_new')
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
        q.is_placement = bool(request.form.get('is_placement'))
        q.is_published = bool(request.form.get('is_published'))
        _save_questions(q, request.form.get('questions_raw', ''))
        commit(success='آزمون به\u200cروزرسانی شد.')
        return redirect(url_for('admin.quizzes'))
    return render_template('admin/quiz_form.html', quiz=q, courses=courses,
                           raw=_questions_raw(q))


def _questions_raw(q):
    """بازسازی متن سوالات برای فرم ویرایش — بدون این، textarea خالی است و
    ذخیرهٔ ویرایش همه سوالات را پاک می‌کند."""
    lines = []
    for qq in (q.questions if q else []):
        choices = '،'.join(qq.choices_list())
        expl = (qq.explanation or '').strip()
        lines.append('%s | %s | %s | %s' % (qq.text, choices, qq.correct_index, expl))
    return '\n'.join(lines)


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
    commit(success='آزمون حذف شد.', category='info')
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
                                      max_score=request.form.get('max_score', 100, type=int),
                                      is_published=bool(request.form.get('is_published'))))
            commit(success='تمرین ساخته شد.')
            return redirect(url_for('admin.assignments'))
    return render_template('admin/assignment_form.html', item=None, courses=courses)


@admin_bp.route('/assignments/<int:aid>/edit', methods=['GET', 'POST'])
@admin_required
def assignment_edit(aid):
    a = db.get_or_404(Assignment, aid)
    courses = Course.query.order_by(Course.title).all()
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        cid = request.form.get('course_id', type=int)
        if not title or not cid:
            flash('عنوان و دوره الزامی است.', 'error')
        else:
            a.title = title
            a.course_id = cid
            a.description = request.form.get('description', '').strip()
            a.max_score = request.form.get('max_score', 100, type=int)
            a.is_published = bool(request.form.get('is_published'))
            commit(success='تمرین به\u200cروزرسانی شد.')
            return redirect(url_for('admin.assignments'))
    return render_template('admin/assignment_form.html', item=a, courses=courses)


@admin_bp.route('/assignments/<int:aid>/delete', methods=['POST'])
@admin_required
def assignment_delete(aid):
    a = db.get_or_404(Assignment, aid)
    db.session.delete(a)
    commit(success='تمرین حذف شد.', category='info')
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
    commit(success='نمره ثبت شد.')
    return go_referrer('admin.submissions')


# ================================================================
# پرسش‌های درسی
# ================================================================


@admin_bp.route('/talent-test', methods=['GET', 'POST'])
@admin_required
def talent_test_admin():
    """ویرایش سوالات آزمون استعدادیابی — ذخیره در تنظیمات (JSON)"""
    import json as _json
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save':
            questions = []
            qs = request.form.getlist('q[]')
            for qi, qtext in enumerate(qs):
                qtext = (qtext or '').strip()
                opts = []
                for oi in range(4):
                    text = request.form.get(f'o[{qi}][{oi}]', '').strip()
                    path = request.form.get(f'p[{qi}][{oi}]', '').strip()
                    if text and path in ('web', 'design', 'marketing', 'ai'):
                        opts.append([text, path])
                if qtext and len(opts) >= 2:
                    questions.append({'q': qtext[:300], 'o': opts})
            s = db.session.get(Setting, 'talent_questions')
            if questions:
                val = _json.dumps(questions, ensure_ascii=False)
                if s:
                    s.value = val
                else:
                    db.session.add(Setting(key='talent_questions', value=val))
            elif s:
                db.session.delete(s)
            commit(success='سوالات استعدادیابی ذخیره شد.')
        elif action == 'reset':
            s = db.session.get(Setting, 'talent_questions')
            if s:
                db.session.delete(s)
                commit(context='admin.talent_test_admin')
            flash('سوالات به حالت پیش‌فرض برگشت.', 'info')
        return redirect(url_for('admin.talent_test_admin'))
    try:
        _row = db.session.get(Setting, 'talent_questions')
        questions = _json.loads(_row.value) if _row and _row.value else None
    except Exception:
        questions = None
    if not isinstance(questions, list):
        from blueprints.features import TALENT_DEFAULT_QUESTIONS
        questions = [{'q': t['q'], 'o': [[text, path] for text, path in t['o']]}
                     for t in TALENT_DEFAULT_QUESTIONS]
    paths = [('web', 'توسعه وب'), ('design', 'طراحی'), ('marketing', 'بازاریابی'), ('ai', 'هوش مصنوعی')]
    return render_template('admin/talent_test.html', questions=questions, paths=paths)


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
    commit(success='پاسخ ثبت شد.')
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
        if not title:
            flash('عنوان الزامی است.', 'error')
        else:
            # اسلاگ یکتا؛ در غیر این صورت دومین باندل با همین عنوان با
            # IntegrityError صفحه را با خطای ۵۰۰ می‌شکست.
            from models import unique_slug_for
            slug = unique_slug_for(
                Bundle, request.form.get('slug', '').strip() or title,
                fallback='bundle')
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
            commit(success='باندل ساخته شد.')
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
            commit(success='باندل به\u200cروزرسانی شد. ✏️')
            return redirect(url_for('admin.bundles'))
    return render_template('admin/bundle_form.html', item=b, courses=courses)


@admin_bp.route('/bundles/<int:bid>/delete', methods=['POST'])
@admin_required
def bundle_delete(bid):
    b = db.get_or_404(Bundle, bid)
    db.session.delete(b)
    commit(success='باندل حذف شد.', category='info')
    return redirect(url_for('admin.bundles'))


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
                commit(success='سوال به بانک اضافه شد. ✅')
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
    commit(success=f'سوال به آزمون «{quiz.title}» اضافه شد. ✅')
    return redirect(url_for('admin.question_bank'))


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
