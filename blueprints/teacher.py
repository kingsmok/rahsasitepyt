# -*- coding: utf-8 -*-
"""پنل استاد — دوره‌های خودش، دانشجویان، تکالیف، پرسش‌ها، درآمد"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from sqlalchemy import func
from datetime import datetime
from validators import safe_referrer
from models import (utcnow, db, User, Course, Section, Lesson, Enrollment, Order,
                    OrderItem, Assignment, AssignmentSubmission, LessonQuestion,
                    Quiz, QuizAttempt, ActivityLog, Notification, PayoutRequest,
                    CourseMeeting, AttendanceRecord, CourseTeacher)

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher-panel')


def _teacher_required():
    if not g.user:
        return redirect(url_for('auth.login', next=request.path))
    if g.user.role not in ('teacher', 'admin', 'super_admin'):
        abort(403)
    return None


def _can_manage_course(course):
    if g.user.role in ('admin', 'super_admin'):
        return True
    if course.teacher_id == g.user.id:
        return True
    return CourseTeacher.query.filter_by(course_id=course.id, teacher_id=g.user.id).first() is not None


def _managed_course_ids():
    """همه دوره‌های قابل مدیریت، شامل دوره‌های همکار مدرس و دسترسی مدیر."""
    if g.user.role in ('admin', 'super_admin'):
        return [row[0] for row in db.session.query(Course.id).all()]
    primary = [row[0] for row in db.session.query(Course.id)
               .filter(Course.teacher_id == g.user.id).all()]
    shared = [row[0] for row in db.session.query(CourseTeacher.course_id)
              .filter(CourseTeacher.teacher_id == g.user.id).all()]
    return list(dict.fromkeys(primary + shared))


def _managed_courses():
    ids = _managed_course_ids()
    if not ids:
        return []
    return Course.query.filter(Course.id.in_(ids)).order_by(Course.created_at.desc()).all()


@teacher_bp.route('/')
def dashboard():
    r = _teacher_required()
    if r:
        return r
    courses = _managed_courses()
    course_ids = [c.id for c in courses]
    total_students = Enrollment.query.filter(
        Enrollment.course_id.in_(course_ids)).count() if course_ids else 0
    # فقط تراکنش قطعی؛ سفارش pending/failed نباید درآمد استاد را بالا ببرد.
    revenue = 0
    if course_ids:
        revenue = db.session.query(func.coalesce(func.sum(OrderItem.price), 0)) \
            .join(Order, Order.id == OrderItem.order_id) \
            .filter(OrderItem.course_id.in_(course_ids), Order.status == 'paid') \
            .scalar() or 0
    # تکالیف در انتظار
    pending_asgs = AssignmentSubmission.query \
        .join(Assignment).filter(Assignment.course_id.in_(course_ids),
                                 AssignmentSubmission.status == 'submitted').count()
    # پرسش‌های بدون پاسخ
    pending_qs = LessonQuestion.query.filter(
        LessonQuestion.answer.is_(None),
        LessonQuestion.lesson_id.in_(
            db.session.query(Lesson.id).join(Section).filter(Section.course_id.in_(course_ids))
        )).count()
    recent_submissions = AssignmentSubmission.query \
        .join(Assignment).filter(Assignment.course_id.in_(course_ids),
                                 AssignmentSubmission.status == 'submitted') \
        .order_by(AssignmentSubmission.created_at.desc()).limit(8).all()
    # سهم واقعی این مدرس — طبق درصد تعیین‌شده برای هر دوره (نه ۵۰٪ ثابت)
    share = 0
    for course in courses:
        sold = db.session.query(func.coalesce(func.sum(OrderItem.price), 0)) \
            .join(Order, Order.id == OrderItem.order_id) \
            .filter(OrderItem.course_id == course.id, Order.status == 'paid') \
            .scalar() or 0
        share += course.teacher_share_amount(g.user.id, sold)
    g.seo['title'] = 'داشبورد استاد — آکادمی آنلاین'
    return render_template('teacher/dashboard.html', courses=courses,
                           total_students=total_students, revenue=revenue,
                           share=share,
                           pending_asgs=pending_asgs, pending_qs=pending_qs,
                           recent_submissions=recent_submissions)


@teacher_bp.route('/courses')
def my_courses():
    r = _teacher_required()
    if r:
        return r
    return render_template('teacher/courses.html', courses=_managed_courses())


@teacher_bp.route('/students')
def students():
    """همه دانشجویان دوره‌های من (با پیشرفت هر دوره)"""
    r = _teacher_required()
    if r:
        return r
    my_ids = _managed_course_ids()
    rows = []
    if my_ids:
        ens = (Enrollment.query
               .filter(Enrollment.course_id.in_(my_ids))
               .order_by(Enrollment.created_at.desc()).all())
        for e in ens:
            rows.append(e)
    return render_template('teacher/students_all.html', rows=rows)


@teacher_bp.route('/courses/<int:cid>/students')
def course_students(cid):
    r = _teacher_required()
    if r:
        return r
    course = db.get_or_404(Course, cid)
    if not _can_manage_course(course):
        abort(403)
    enrollments = Enrollment.query.filter_by(course_id=cid).all()
    closed_meetings = CourseMeeting.query.filter_by(course_id=cid, is_closed=True).count()
    attendance_percent = {}
    if closed_meetings and enrollments:
        rows = db.session.query(AttendanceRecord.enrollment_id, func.count(AttendanceRecord.id)) \
            .join(CourseMeeting, CourseMeeting.id == AttendanceRecord.meeting_id) \
            .filter(CourseMeeting.course_id == cid, CourseMeeting.is_closed == True,
                    AttendanceRecord.status.in_(['present', 'late'])) \
            .group_by(AttendanceRecord.enrollment_id).all()
        present_counts = dict(rows)
        attendance_percent = {
            enrollment.id: round(present_counts.get(enrollment.id, 0) * 100 / closed_meetings)
            for enrollment in enrollments
        }
    return render_template('teacher/students.html', course=course,
                           enrollments=enrollments, closed_meetings=closed_meetings,
                           attendance_percent=attendance_percent)


@teacher_bp.route('/enrollments/<int:eid>/completion', methods=['POST'])
def enrollment_completion(eid):
    r = _teacher_required()
    if r:
        return r
    enrollment = db.get_or_404(Enrollment, eid)
    if not _can_manage_course(enrollment.course):
        abort(403)
    if not enrollment.course.is_attendance_based:
        abort(400)
    action = request.form.get('action', 'complete')
    if action == 'complete':
        closed = CourseMeeting.query.filter_by(course_id=enrollment.course_id,
                                               is_closed=True).count()
        if closed:
            attended = AttendanceRecord.query.join(
                CourseMeeting, CourseMeeting.id == AttendanceRecord.meeting_id
            ).filter(
                CourseMeeting.course_id == enrollment.course_id,
                CourseMeeting.is_closed == True,
                AttendanceRecord.enrollment_id == enrollment.id,
                AttendanceRecord.status.in_(['present', 'late'])
            ).count()
            percent = round(attended * 100 / closed)
            required = enrollment.course.attendance_required_percent or 75
            if percent < required:
                flash(f'درصد حضور دانشجو {percent}٪ است و به حداقل {required}٪ نرسیده.', 'error')
                return redirect(url_for('teacher.course_students', cid=enrollment.course_id))
        enrollment.completed_at = utcnow()
        enrollment.save_progress([lesson.id for lesson in enrollment.course.lessons])
        flash('دوره برای این دانشجو تکمیل شد.', 'success')
    elif action == 'undo':
        enrollment.completed_at = None
        enrollment.save_progress([])
        flash('وضعیت تکمیل دانشجو لغو شد.', 'info')
    else:
        abort(400)
    db.session.commit()
    return redirect(url_for('teacher.course_students', cid=enrollment.course_id))


@teacher_bp.route('/courses/<int:cid>/attendance', methods=['GET', 'POST'])
def attendance_sessions(cid):
    r = _teacher_required()
    if r:
        return r
    course = db.get_or_404(Course, cid)
    if not _can_manage_course(course):
        abort(403)
    if not course.is_attendance_based:
        flash('حضور و غیاب فقط برای دوره حضوری یا ترکیبی فعال است.', 'info')
        return redirect(url_for('teacher.my_courses'))
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        starts_raw = request.form.get('starts_at', '').strip()
        try:
            starts_at = datetime.fromisoformat(starts_raw)
            duration = max(15, min(720, int(request.form.get('duration_min') or 90)))
        except (TypeError, ValueError):
            flash('تاریخ، ساعت یا مدت جلسه معتبر نیست.', 'error')
        else:
            if not title:
                flash('عنوان جلسه الزامی است.', 'error')
            else:
                db.session.add(CourseMeeting(
                    course_id=course.id, title=title, starts_at=starts_at,
                    duration_min=duration,
                    notes=request.form.get('notes', '').strip()[:500],
                    created_by=g.user.id))
                db.session.commit()
                flash('جلسه حضوری برای حضور و غیاب ساخته شد.', 'success')
                return redirect(url_for('teacher.attendance_sessions', cid=cid))
    meetings = CourseMeeting.query.filter_by(course_id=cid) \
        .order_by(CourseMeeting.starts_at.desc()).all()
    counts = {}
    for meeting in meetings:
        counts[meeting.id] = {
            'marked': len(meeting.records),
            'present': sum(1 for record in meeting.records if record.status in ('present', 'late')),
        }
    return render_template('teacher/attendance_sessions.html', course=course,
                           meetings=meetings, counts=counts)


@teacher_bp.route('/attendance/<int:mid>', methods=['GET', 'POST'])
def attendance_mark(mid):
    r = _teacher_required()
    if r:
        return r
    meeting = db.get_or_404(CourseMeeting, mid)
    if not _can_manage_course(meeting.course):
        abort(403)
    enrollments = Enrollment.query.filter_by(course_id=meeting.course_id).all()
    records = {record.enrollment_id: record for record in meeting.records}
    if request.method == 'POST':
        allowed_statuses = {'present', 'late', 'absent', 'excused'}
        for enrollment in enrollments:
            status = request.form.get(f'status_{enrollment.id}', 'absent')
            if status not in allowed_statuses:
                status = 'absent'
            record = records.get(enrollment.id)
            if not record:
                record = AttendanceRecord(meeting_id=meeting.id,
                                          enrollment_id=enrollment.id)
                db.session.add(record)
            record.status = status
            record.note = request.form.get(f'note_{enrollment.id}', '').strip()[:300]
            record.marked_by = g.user.id
            record.marked_at = utcnow()
        meeting.is_closed = request.form.get('close') == '1'
        db.session.commit()
        flash('حضور و غیاب ذخیره شد.', 'success')
        return redirect(url_for('teacher.attendance_mark', mid=meeting.id))
    return render_template('teacher/attendance_mark.html', meeting=meeting,
                           course=meeting.course, enrollments=enrollments,
                           records=records)


@teacher_bp.route('/attendance/<int:mid>/delete', methods=['POST'])
def attendance_delete(mid):
    r = _teacher_required()
    if r:
        return r
    meeting = db.get_or_404(CourseMeeting, mid)
    if not _can_manage_course(meeting.course):
        abort(403)
    course_id = meeting.course_id
    db.session.delete(meeting)
    db.session.commit()
    flash('جلسه حضور و غیاب حذف شد.', 'info')
    return redirect(url_for('teacher.attendance_sessions', cid=course_id))


@teacher_bp.route('/assignments')
def assignments():
    r = _teacher_required()
    if r:
        return r
    course_ids = _managed_course_ids()
    if not course_ids:
        return render_template('teacher/assignments.html', subs=[])
    subs = AssignmentSubmission.query \
        .join(Assignment).filter(Assignment.course_id.in_(course_ids)) \
        .order_by(AssignmentSubmission.created_at.desc()).all()
    return render_template('teacher/assignments.html', subs=subs)


@teacher_bp.route('/assignments/<int:sid>/grade', methods=['POST'])
def grade(sid):
    r = _teacher_required()
    if r:
        return r
    sub = db.get_or_404(AssignmentSubmission, sid)
    if not _can_manage_course(sub.assignment.course):
        abort(403)
    sub.score = request.form.get('score', 0, type=int)
    sub.feedback = request.form.get('feedback', '').strip()
    sub.status = 'graded'
    sub.graded_at = utcnow()
    Notification.notify(sub.user_id, 'نمره تمرین شما ثبت شد',
                        f'تمرین «{sub.assignment.title}»: نمره {sub.score}',
                        '📌', url_for('features.assignment_view', aid=sub.assignment_id))
    db.session.commit()
    flash('نمره ثبت و به دانشجو اعلان شد. ✅', 'success')
    return redirect(safe_referrer(url_for('teacher.assignments')))


@teacher_bp.route('/questions')
def questions():
    r = _teacher_required()
    if r:
        return r
    course_ids = _managed_course_ids()
    if not course_ids:
        return render_template('teacher/questions.html', qs=[])
    qs = LessonQuestion.query.filter(
        LessonQuestion.answer.is_(None),
        LessonQuestion.lesson_id.in_(
            db.session.query(Lesson.id).join(Section).filter(Section.course_id.in_(course_ids))
        )).order_by(LessonQuestion.created_at.desc()).all()
    return render_template('teacher/questions.html', qs=qs)


@teacher_bp.route('/questions/<int:qid>/answer', methods=['POST'])
def answer_question(qid):
    r = _teacher_required()
    if r:
        return r
    q = db.get_or_404(LessonQuestion, qid)
    if not _can_manage_course(q.lesson.section.course):
        abort(403)
    q.answer = request.form.get('answer', '').strip()
    q.answered_at = utcnow()
    Notification.notify(q.user_id, 'مدرس به سوال شما پاسخ داد',
                        q.answer[:100], '💬',
                        url_for('student.learn', course_id=q.lesson.section.course_id,
                                lesson=q.lesson_id) + '#lesson-qa')
    db.session.commit()
    flash('پاسخ ثبت و به دانشجو اعلان شد. ✅', 'success')
    return redirect(safe_referrer(url_for('teacher.questions')))


@teacher_bp.route('/revenue')
def revenue():
    r = _teacher_required()
    if r:
        return r
    courses = _managed_courses()
    rows = []
    total = 0
    share = 0
    for course in courses:
        sold = db.session.query(func.coalesce(func.sum(OrderItem.price), 0)) \
            .join(Order, Order.id == OrderItem.order_id) \
            .filter(OrderItem.course_id == course.id, Order.status == 'paid') \
            .scalar() or 0
        count = Enrollment.query.filter_by(course_id=course.id).count()
        # سهم این مدرس طبق درصد همان دوره (مدرس اصلی = باقی‌مانده پس از کسر کمکی‌ها)
        course_share = course.teacher_share_amount(g.user.id, sold)
        rows.append({'course': course, 'sold': sold, 'count': count,
                     'share': course_share,
                     'percent': course.teacher_percent()})
        total += int(sold or 0)
        share += course_share
    pending = PayoutRequest.query.filter_by(teacher_id=g.user.id, status='pending').first()
    paid_out = db.session.query(func.coalesce(func.sum(PayoutRequest.amount), 0)) \
        .filter_by(teacher_id=g.user.id, status='paid').scalar() or 0
    available = max(0, share - int(paid_out or 0) - (pending.amount if pending else 0))
    return render_template('teacher/revenue.html', rows=rows,
                           total=total, share=share, pending=pending,
                           paid_out=paid_out, available=available)


@teacher_bp.route('/payout/request', methods=['POST'])
def payout_request():
    r = _teacher_required()
    if r:
        return r
    if g.user.role != 'teacher':
        abort(403)
    amount = request.form.get('amount', 0, type=int)
    account = request.form.get('account', '').strip()
    # سهم قابل تسویه = مجموع سهم این مدرس از هر دوره طبق درصد همان دوره
    available = 0
    for course in _managed_courses():
        sold = db.session.query(func.coalesce(func.sum(OrderItem.price), 0)) \
            .join(Order, Order.id == OrderItem.order_id) \
            .filter(OrderItem.course_id == course.id, Order.status == 'paid') \
            .scalar() or 0
        available += course.teacher_share_amount(g.user.id, sold)
    paid_out = db.session.query(func.coalesce(func.sum(PayoutRequest.amount), 0)) \
        .filter_by(teacher_id=g.user.id, status='paid').scalar() or 0
    pending_out = db.session.query(func.coalesce(func.sum(PayoutRequest.amount), 0)) \
        .filter_by(teacher_id=g.user.id, status='pending').scalar() or 0
    available = max(0, int(available) - int(paid_out or 0) - int(pending_out or 0))
    if amount < 50000:
        flash('حداقل مبلغ تسویه ۵۰,۰۰۰ تومان است.', 'error')
    elif amount > available:
        flash('مبلغ درخواست از مانده قابل تسویه بیشتر است.', 'error')
    elif not account:
        flash('شماره شبا یا کارت را وارد کنید.', 'error')
    elif PayoutRequest.query.filter_by(teacher_id=g.user.id, status='pending').first():
        flash('درخواست تسویه قبلی هنوز در انتظار بررسی است.', 'info')
    else:
        db.session.add(PayoutRequest(teacher_id=g.user.id, amount=amount, account=account))
        db.session.commit()
        flash('درخواست تسویه ثبت شد و برای بررسی ارسال گردید. 💰', 'success')
    return redirect(url_for('teacher.revenue'))
