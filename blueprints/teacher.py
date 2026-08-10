# -*- coding: utf-8 -*-
"""پنل استاد — دوره‌های خودش، دانشجویان، تکالیف، پرسش‌ها، درآمد"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from sqlalchemy import func
from models import (utcnow, db, User, Course, Section, Lesson, Enrollment, Order,
                    OrderItem, Assignment, AssignmentSubmission, LessonQuestion,
                    Quiz, QuizAttempt, ActivityLog, Notification, PayoutRequest)

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher-panel')


def _teacher_required():
    if not g.user:
        return redirect(url_for('auth.login', next=request.path))
    if g.user.role not in ('teacher', 'admin', 'super_admin'):
        abort(403)
    return None


@teacher_bp.route('/')
def dashboard():
    r = _teacher_required()
    if r:
        return r
    teacher_id = g.user.id
    courses = Course.query.filter_by(teacher_id=teacher_id).all()
    course_ids = [c.id for c in courses]
    total_students = 0
    for c in courses:
        total_students += len(c.enrollments)
    # درآمد: مجموع فروش دوره‌های خودش (سهم استاد ~ ۵۰٪)
    revenue = 0
    if course_ids:
        revenue = db.session.query(func.coalesce(func.sum(OrderItem.price), 0)) \
            .filter(OrderItem.course_id.in_(course_ids)).scalar() or 0
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
    g.seo['title'] = 'داشبورد استاد — آکادمی آنلاین'
    return render_template('teacher/dashboard.html', courses=courses,
                           total_students=total_students, revenue=revenue,
                           share=round(int(revenue or 0) * 0.5),
                           pending_asgs=pending_asgs, pending_qs=pending_qs,
                           recent_submissions=recent_submissions)


@teacher_bp.route('/courses')
def my_courses():
    r = _teacher_required()
    if r:
        return r
    courses = Course.query.filter_by(teacher_id=g.user.id).all()
    return render_template('teacher/courses.html', courses=courses)


@teacher_bp.route('/students')
def students():
    """همه دانشجویان دوره‌های من (با پیشرفت هر دوره)"""
    r = _teacher_required()
    if r:
        return r
    from models import Enrollment, CourseTeacher
    my_ids = [c.id for c in Course.query.filter_by(teacher_id=g.user.id).all()]
    my_ids += [ct.course_id for ct in CourseTeacher.query.filter_by(teacher_id=g.user.id).all()]
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
    course = Course.query.filter_by(id=cid, teacher_id=g.user.id).first_or_404()
    enrollments = Enrollment.query.filter_by(course_id=cid).all()
    return render_template('teacher/students.html', course=course,
                           enrollments=enrollments)


@teacher_bp.route('/assignments')
def assignments():
    r = _teacher_required()
    if r:
        return r
    course_ids = [c.id for c in Course.query.filter_by(teacher_id=g.user.id).all()]
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
    sub = AssignmentSubmission.query.get_or_404(sid)
    # بررسی: این تکلیف متعلق به دوره خود استاد است؟
    if sub.assignment.course.teacher_id != g.user.id and g.user.role == 'teacher':
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
    return redirect(request.referrer or url_for('teacher.assignments'))


@teacher_bp.route('/questions')
def questions():
    r = _teacher_required()
    if r:
        return r
    course_ids = [c.id for c in Course.query.filter_by(teacher_id=g.user.id).all()]
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
    q = LessonQuestion.query.get_or_404(qid)
    if q.lesson.section.course.teacher_id != g.user.id and g.user.role == 'teacher':
        abort(403)
    q.answer = request.form.get('answer', '').strip()
    q.answered_at = utcnow()
    Notification.notify(q.user_id, 'مدرس به سوال شما پاسخ داد',
                        q.answer[:100], '💬',
                        url_for('student.learn', course_id=q.lesson.section.course_id,
                                lesson=q.lesson_id) + '#lesson-qa')
    db.session.commit()
    flash('پاسخ ثبت و به دانشجو اعلان شد. ✅', 'success')
    return redirect(request.referrer or url_for('teacher.questions'))


@teacher_bp.route('/revenue')
def revenue():
    r = _teacher_required()
    if r:
        return r
    course_ids = [c.id for c in Course.query.filter_by(teacher_id=g.user.id).all()]
    rows = []
    total = 0
    for c in Course.query.filter_by(teacher_id=g.user.id).all():
        sold = db.session.query(func.coalesce(func.sum(OrderItem.price), 0)) \
            .filter(OrderItem.course_id == c.id,
                    OrderItem.order_id.in_(
                        db.session.query(Order.id).filter(Order.status == 'paid')
                    )).scalar() or 0
        cnt = Enrollment.query.filter_by(course_id=c.id).count()
        rows.append({'course': c, 'sold': sold, 'count': cnt, 'share': round(int(sold or 0) * 0.5)})
        total += int(sold or 0)
    pending = PayoutRequest.query.filter_by(teacher_id=g.user.id, status='pending').first()
    return render_template('teacher/revenue.html', rows=rows,
                           total=total, share=round(total * 0.5), pending=pending)


@teacher_bp.route('/payout/request', methods=['POST'])
def payout_request():
    r = _teacher_required()
    if r:
        return r
    from models import PayoutRequest
    amount = request.form.get('amount', 0, type=int)
    account = request.form.get('account', '').strip()
    if amount < 50000:
        flash('حداقل مبلغ تسویه ۵۰,۰۰۰ تومان است.', 'error')
    elif not account:
        flash('شماره شبا یا کارت را وارد کنید.', 'error')
    elif PayoutRequest.query.filter_by(teacher_id=g.user.id, status='pending').first():
        flash('درخواست تسویه قبلی هنوز در انتظار بررسی است.', 'info')
    else:
        db.session.add(PayoutRequest(teacher_id=g.user.id, amount=amount, account=account))
        db.session.commit()
        flash('درخواست تسویه ثبت شد و برای بررسی ارسال گردید. 💰', 'success')
    return redirect(url_for('teacher.revenue'))
