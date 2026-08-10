# -*- coding: utf-8 -*-
"""ویژگی‌های تکمیلی: آزمون، تمرین، پرسش درس، گیمیفیکیشن، کیف پول، ارجاع، باندل، مقایسه، برنامه مطالعه"""
import json
import os
import random
from datetime import datetime
try:
    from datetime import UTC
except ImportError:  # پایتون < 3.11 (هاست‌های اشتراکی)
    from datetime import timezone as _tz_utc
    UTC = _tz_utc.utc
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, session, abort, jsonify)
from models import (utcnow, db, User, Course, Quiz, QuizQuestion, QuizAttempt,
                    Assignment, AssignmentSubmission, LessonQuestion,
                    Enrollment, Order, OrderItem, Bundle, BundleCourse,
                    StudyPlan, ActivityLog, ChatMessage, StudyDay)
from gamification import (award_points, record_streak, user_badges, wallet_spend,
                          wallet_charge, wallet_bonus, make_referral_code)

from jdates import jtime

features_bp = Blueprint('features', __name__)

_FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def fa_n(n):
    return str(n).translate(_FA)


# ================================================================
# آزمون‌ها
# ================================================================
def _enrolled_or_403(course_id):
    """بررسی عضویت در دوره — مهمان به لاگین، غیرعضو به 403 ریدایرکت می‌شود"""
    if not g.user:
        flash('برای دسترسی به این بخش ابتدا وارد شوید.', 'info')
        return redirect(url_for('auth.login', next=request.path))
    enr = Enrollment.query.filter_by(user_id=g.user.id, course_id=course_id).first()
    if not enr:
        abort(403)
    return enr


def _need_enrollment(quiz):
    """بررسی دسترسی به آزمون — آزمون تعیین سطح سراسری است"""
    if quiz.is_placement:
        return True
    if not g.user:
        flash('برای شرکت در آزمون ابتدا وارد شوید.', 'info')
        return False
    if not _enrolled_or_403(quiz.course_id):
        flash('برای شرکت در این آزمون باید در دوره ثبت‌نام کنید.', 'error')
        return False
    return True


@features_bp.route('/quiz/<int:qid>')
def quiz_view(qid):
    quiz = Quiz.query.get_or_404(qid)
    if not _need_enrollment(quiz):
        return redirect(url_for('auth.login') if not g.user else url_for('site.course_detail', slug=quiz.course.slug))
    best = None
    attempts = []
    if g.user:
        best = QuizAttempt.query.filter_by(quiz_id=qid, user_id=g.user.id) \
            .order_by(QuizAttempt.score.desc()).first()
        attempts = QuizAttempt.query.filter_by(quiz_id=qid, user_id=g.user.id) \
            .order_by(QuizAttempt.finished_at.desc()).all()
    return render_template('features/quiz_view.html', quiz=quiz, best=best,
                           attempts=attempts)


@features_bp.route('/quiz/<int:qid>/start')
def quiz_start(qid):
    quiz = Quiz.query.get_or_404(qid)
    if not _need_enrollment(quiz):
        return redirect(url_for('auth.login') if not g.user else url_for('features.quiz_view', qid=qid))
    if not quiz.questions:
        flash('این آزمون هنوز سوالی ندارد.', 'info')
        return redirect(url_for('site.course_detail', slug=quiz.course.slug))
    return render_template('features/quiz_take.html', quiz=quiz,
                           questions=quiz.questions)


@features_bp.route('/quiz/<int:qid>/submit', methods=['POST'])
def quiz_submit(qid):
    quiz = Quiz.query.get_or_404(qid)
    if not _need_enrollment(quiz):
        return redirect(url_for('auth.login') if not g.user else url_for('features.quiz_view', qid=qid))
    total = len(quiz.questions)
    if not total:
        flash('آزمون سوالی ندارد.', 'error')
        return redirect(url_for('features.quiz_view', qid=qid))
    correct = 0
    answers = []
    for i, q in enumerate(quiz.questions):
        chosen = request.form.get(f'q_{q.id}')
        chosen_i = int(chosen) if chosen and chosen.isdigit() else -1
        is_correct = chosen_i == q.correct_index
        if is_correct:
            correct += 1
        answers.append({'q': q.id, 'chosen': chosen_i,
                        'correct': is_correct, 'right': q.correct_index,
                        'explain': q.explanation or ''})
    score = round(correct * 100 / total)
    passed = score >= (quiz.passing_score or 50)
    # آزمون تعیین سطح: محاسبه سطح و نمایش دوره‌های پیشنهادی
    if quiz.is_placement:
        if score >= 70:
            level = 'پیشرفته'
        elif score >= 40:
            level = 'متوسط'
        else:
            level = 'مقدماتی'
        if g.user:
            g.user.level_pref = level
            db.session.commit()
        rec_courses = Course.query.filter_by(status='published', level=level).limit(6).all()
        return render_template('features/placement_result.html', score=score,
                               level=level, courses=rec_courses)

    if g.user:
        attempt = QuizAttempt(quiz_id=qid, user_id=g.user.id, score=score,
                              passed=passed, answers=json.dumps(answers, ensure_ascii=False),
                              started_at=utcnow(), finished_at=utcnow())
        db.session.add(attempt)
        if passed:
            award_points(g.user, 20, f'قبولی در آزمون «{quiz.title}»')
        db.session.commit()
        saved = json.loads(attempt.answers)
    else:
        saved = answers
        attempt = None
    return render_template('features/quiz_result.html', quiz=quiz, score=score,
                           passed=passed, answers=saved, attempt=attempt)


# ================================================================
# تمرین‌ها و ارسال پاسخ
# ================================================================
@features_bp.route('/assignment/<int:aid>', methods=['GET', 'POST'])
def assignment_view(aid):
    asg = Assignment.query.get_or_404(aid)
    _r = _enrolled_or_403(asg.course_id)
    if _r is not None and not isinstance(_r, Enrollment):
        return _r
    sub = AssignmentSubmission.query.filter_by(assignment_id=aid, user_id=g.user.id).first()
    if request.method == 'POST':
        from validators import clamp_field
        text = clamp_field(request.form.get('text'), 'text')
        f = request.files.get('file')
        fname = sub.file if sub else None
        if f and f.filename:
            ext = os.path.splitext(f.filename)[1].lower()
            if ext not in ('.pdf', '.zip', '.rar', '.py', '.js', '.html', '.css', '.docx', '.jpg', '.png', '.txt'):
                flash('فرمت فایل مجاز نیست.', 'error')
                return redirect(url_for('features.assignment_view', aid=aid))
            fname = f'asg-{aid}-{g.user.id}{ext}'
            from uploads_helper import uploads_dir
            f.save(os.path.join(uploads_dir('submissions'), fname))
        if not text and not fname:
            flash('متن پاسخ یا فایل را وارد کنید.', 'error')
            return redirect(url_for('features.assignment_view', aid=aid))
        if sub:
            sub.text = text or sub.text
            sub.file = fname or sub.file
            sub.status = 'submitted'
        else:
            sub = AssignmentSubmission(assignment_id=aid, user_id=g.user.id,
                                       text=text, file=fname)
            db.session.add(sub)
        award_points(g.user, 10, f'ارسال تمرین «{asg.title}»')
        db.session.commit()
        flash('پاسخ شما ثبت شد و برای مدرس ارسال گردید. ✅', 'success')
        return redirect(url_for('features.assignment_view', aid=aid))
    return render_template('features/assignment_view.html', asg=asg, sub=sub)


# ================================================================
# پرسش و پاسخ زیر هر درس
# ================================================================
@features_bp.route('/lesson/<int:lid>/ask', methods=['POST'])
def lesson_ask(lid):
    from models import Lesson
    lesson = Lesson.query.get_or_404(lid)
    _r = _enrolled_or_403(lesson.section.course_id)
    if _r is not None and not isinstance(_r, Enrollment):
        return _r
    from validators import clamp_field
    q = clamp_field(request.form.get('question'), 'question')
    if len(q) < 5:
        flash('سوال شما خیلی کوتاه است.', 'error')
        return redirect(url_for('student.learn', course_id=lesson.section.course_id, lesson=lid))
    db.session.add(LessonQuestion(lesson_id=lid, user_id=g.user.id, question=q))
    award_points(g.user, 5, 'پرسش درسی')
    db.session.commit()
    flash('سوال شما ثبت شد؛ مدرس پاسخ خواهد داد. 🙏', 'success')
    return redirect(url_for('student.learn', course_id=lesson.section.course_id, lesson=lid) + '#lesson-qa')


# ================================================================
# اعلان‌های داخلی
# ================================================================
@features_bp.route('/dashboard/notifications')
def notifications():
    if not g.user:
        return redirect(url_for('auth.login'))
    from models import Notification
    items = Notification.query.filter_by(user_id=g.user.id) \
        .order_by(Notification.created_at.desc()).limit(50).all()
    # علامت خوانده‌شدن
    unread = Notification.query.filter_by(user_id=g.user.id, is_read=False).all()
    for n in unread:
        n.is_read = True
    db.session.commit()
    g.seo['title'] = "اعلان‌ها — آکادمی آنلاین"
    return render_template('features/notifications.html', items=items)


@features_bp.route('/api/notifications/unread')
def notifications_unread():
    from models import Notification
    if not g.user:
        return jsonify(count=0)
    n = Notification.query.filter_by(user_id=g.user.id, is_read=False).count()
    return jsonify(count=n)


# ================================================================
# آزمون استعدادیابی
# ================================================================
TALENT_QUESTIONS = [
    {'q': 'در مدرسه/دانشگاه کدام درس را بیشتر دوست داشتی؟',
     'o': [('ریاضی و منطق', 'web'), ('نقاشی و طراحی', 'design'), ('ادبیات و تحقیق', 'marketing'), ('زیست و آزمایش', 'ai')]},
    {'q': 'وقتی وقت آزاد داری بیشتر دوست داری چه کار کنی؟',
     'o': [('حل پازل و بازی فکری', 'web'), ('طراحی و خلاقیت', 'design'), ('گفتگو و شبکه اجتماعی', 'marketing'), ('کشف چیزهای جدید', 'ai')]},
    {'q': 'کدام پروژه برایت جذاب‌تر است؟',
     'o': [('ساخت یک وب‌سایت', 'web'), ('طراحی لوگو و پوستر', 'design'), ('کمپین تبلیغاتی', 'marketing'), ('تحلیل داده‌ها', 'ai')]},
    {'q': 'در کار تیمی معمولاً چه نقشی می‌گیری؟',
     'o': [('حل مسئله فنی', 'web'), ('ایده‌پردازی و طراحی', 'design'), ('ارتباط با مشتری', 'marketing'), ('بررسی و تحلیل', 'ai')]},
    {'q': 'کدام مهارت را اولویت اول یادگیری می‌دانی؟',
     'o': [('برنامه‌نویسی', 'web'), ('ابزارهای طراحی', 'design'), ('بازاریابی دیجیتال', 'marketing'), ('هوش مصنوعی', 'ai')]},
    {'q': 'اگر یک محصول بسازی، بیشتر به چه چیزی اهمیت می‌دهی؟',
     'o': [('اینکه درست کار کند', 'web'), ('اینکه زیبا باشد', 'design'), ('اینکه فروش برود', 'marketing'), ('اینکه هوشمند باشد', 'ai')]},
    {'q': 'کدام محیط کاری برایت بهتر است؟',
     'o': [('پشت سیستم با کد', 'web'), ('استودیو طراحی', 'design'), ('جلسات و شبکه‌سازی', 'marketing'), ('آزمایشگاه داده', 'ai')]},
    {'q': 'کدام جمله به تو نزدیک‌تر است؟',
     'o': [('من عاشق ساختن هستم', 'web'), ('من عاشق زیبایی هستم', 'design'), ('من عاشق ارتباط هستم', 'marketing'), ('من عاشق کشف هستم', 'ai')]},
]

PATHS = {
    'web': {'name': 'توسعه‌دهنده وب', 'icon': '💻', 'color': '#2563eb',
            'desc': 'برنامه‌نویسی، ساخت سایت و اپلیکیشن — مسیر پرمتقاضی بازار کار',
            'courses': [1, 2, 3, 4]},
    'design': {'name': 'طراح محصول (UI/UX)', 'icon': '🎨', 'color': '#ea580c',
               'desc': 'طراحی رابط و تجربه کاربری — ترکیب خلاقیت و فناوری',
               'courses': [6]},
    'marketing': {'name': 'بازاریابی دیجیتال', 'icon': '📈', 'color': '#059669',
                  'desc': 'دیجیتال مارکتینگ، فروش آنلاین و برندینگ',
                  'courses': [8]},
    'ai': {'name': 'هوش مصنوعی و علم داده', 'icon': '🤖', 'color': '#7c3aed',
           'desc': 'یادگیری ماشین، تحلیل داده و هوش مصنوعی',
           'courses': [5]},
}


@features_bp.route('/talent-test')
def talent_test():
    g.seo['title'] = 'آزمون استعدادیابی — انتخاب مسیر شغلی | آکادمی آنلاین'
    g.seo['description'] = 'با ۸ سوال کوتاه، استعداد و مسیر شغلی مناسب خود را کشف کنید.'
    return render_template('features/talent_test.html', questions=TALENT_QUESTIONS)


@features_bp.route('/talent-test/result', methods=['POST'])
def talent_result():
    scores = {'web': 0, 'design': 0, 'marketing': 0, 'ai': 0}
    for i, tq in enumerate(TALENT_QUESTIONS):
        ans = request.form.get(f't_{i}')
        for text, path in tq['o']:
            if ans == text:
                scores[path] += 1
    best = max(scores, key=scores.get)
    path = PATHS[best]
    if g.user:
        g.user.level_pref = path['name']
        db.session.commit()
    from models import Course
    courses = [db.session.get(Course, cid) for cid in path['courses']]
    courses = [c for c in courses if c]
    return render_template('features/talent_result.html', path=path, scores=scores,
                           courses=courses, best=best)


# ================================================================
# رضایت سنجی پس از دوره
# ================================================================
@features_bp.route('/feedback/<int:course_id>', methods=['GET', 'POST'])
def course_feedback(course_id):
    if not g.user:
        return redirect(url_for('auth.login'))
    from models import CourseFeedback, Enrollment
    course = Course.query.get_or_404(course_id)
    # فقط ثبت‌نام‌شده‌ها — جلوگیری از بازخورد جعلی (IDOR)
    enrolled = Enrollment.query.filter_by(user_id=g.user.id, course_id=course_id).first()
    if not enrolled:
        flash('برای ثبت بازخورد باید در این دوره ثبت‌نام کرده باشید.', 'error')
        return redirect(url_for('site.course_detail', slug=course.slug))
    existing = CourseFeedback.query.filter_by(user_id=g.user.id, course_id=course_id).first()
    if request.method == 'POST':
        score = request.form.get('score', 5, type=int)
        recommend = bool(request.form.get('recommend'))
        comment = request.form.get('comment', '').strip()
        if existing:
            existing.score = score
            existing.recommend = recommend
            existing.comment = comment
        else:
            db.session.add(CourseFeedback(user_id=g.user.id, course_id=course_id,
                                          score=score, recommend=recommend, comment=comment))
        db.session.commit()
        flash('بازخورد شما ثبت شد — ممنون! 🙏', 'success')
        return redirect(url_for('student.my_courses'))
    return render_template('features/course_feedback.html', course=course, existing=existing)


# ================================================================
# چت آنلاین پشتیبانی (سمت کاربر)
# ================================================================
@features_bp.route('/support-chat')
def support_chat():
    if not g.user:
        return redirect(url_for('auth.login'))
    msgs = ChatMessage.query.filter_by(user_id=g.user.id) \
        .order_by(ChatMessage.created_at.asc()).limit(200).all()
    g.seo['title'] = 'چت آنلاین پشتیبانی'
    return render_template('features/support_chat.html', msgs=msgs)


@features_bp.route('/api/chat/send', methods=['POST'])
def chat_send():
    if not g.user:
        return jsonify(ok=False), 401
    body = (request.json.get('body') if request.is_json else request.form.get('body', '')).strip()
    if not body:
        return jsonify(ok=False, msg='پیام خالی است'), 400
    db.session.add(ChatMessage(user_id=g.user.id, body=body[:1000]))
    db.session.commit()
    return jsonify(ok=True)


@features_bp.route('/api/chat/poll')
def chat_poll():
    """Polling برای دریافت پیام‌های جدید — پاسخ پشتیبانی"""
    if not g.user:
        return jsonify(msgs=[])
    after = request.args.get('after', 0, type=int)
    msgs = ChatMessage.query.filter(ChatMessage.user_id == g.user.id,
                                    ChatMessage.id > after) \
        .order_by(ChatMessage.created_at.asc()).all()
    return jsonify(msgs=[{'id': m.id, 'body': m.body, 'is_admin': m.is_admin,
                          'time': jtime(m.created_at)} for m in msgs])


# ================================================================
# چالش هفتگی و تقویم مطالعه
# ================================================================
@features_bp.route('/dashboard/challenge')
def challenge():
    if not g.user:
        return redirect(url_for('auth.login'))
    from datetime import timedelta, date as _date
    today = _date.today()
    week_start = today - timedelta(days=today.weekday())
    week_days = [week_start + timedelta(days=i) for i in range(7)]
    # جلسات تکمیل‌شده این هفته (از study_days)
    done_week = 0
    days_map = {}
    for d in week_days:
        sd = StudyDay.query.filter_by(user_id=g.user.id, day=d.isoformat()).first()
        n = sd.lessons_done if sd else 0
        days_map[d.isoformat()] = n
        done_week += n
    goal = 5  # هدف هفتگی
    # تقویم ۳۰ روز اخیر
    cal = []
    for i in range(29, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        sd = StudyDay.query.filter_by(user_id=g.user.id, day=d).first()
        cal.append({'day': d, 'count': sd.lessons_done if sd else 0})
    g.seo['title'] = 'چالش هفتگی و تقویم مطالعه'
    return render_template('features/challenge.html', days_map=days_map,
                           done_week=done_week, goal=goal, cal=cal,
                           week_days=week_days)


# ================================================================
# گیمیفیکیشن: لیدربورد
# ================================================================
@features_bp.route('/leaderboard')
def leaderboard():
    users = User.query.filter(User.points > 0).order_by(User.points.desc()).limit(50).all()
    g.seo['title'] = "جدول برترین‌های یادگیری — آکادمی آنلاین"
    return render_template('features/leaderboard.html', users=users)


# ================================================================
# کیف پول
# ================================================================
@features_bp.route('/dashboard/wallet', methods=['GET', 'POST'])
def wallet():
    if not g.user:
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        amount = request.form.get('amount', '').strip()
        if not amount.isdigit() or int(amount) < 10000:
            flash('حداقل مبلغ شارژ ۱۰,۰۰۰ تومان است.', 'error')
        else:
            # شارژ با شبیه‌ساز پرداخت
            code = f"WAL-{datetime.now():%y%m%d}-{random.randint(1000, 9999)}"
            session['wallet_amount'] = int(amount)
            session['wallet_code'] = code
            return render_template('pay/bank.html',
                                   wallet_mode=True, wallet_code=code, wallet_amount=int(amount))
    from models import WalletTransaction
    txns = WalletTransaction.query.filter_by(user_id=g.user.id) \
        .order_by(WalletTransaction.created_at.desc()).limit(30).all()
    return render_template('features/wallet.html', txns=txns)


@features_bp.route('/wallet/confirm', methods=['POST'])
def wallet_confirm():
    if not g.user:
        return redirect(url_for('auth.login'))
    decision = request.form.get('decision', 'ok')
    amount = int(session.get('wallet_amount') or 0)
    code = session.get('wallet_code') or ''
    if decision == 'ok' and amount > 0:
        wallet_charge(g.user, amount, f'شارژ کیف پول ({code})')
        award_points(g.user, 5, 'شارژ کیف پول')
        db.session.commit()
        flash(f'کیف پول شما به مبلغ {fa_n(f"{amount:,}")} تومان شارژ شد. ✅', 'success')
    else:
        flash('شارژ کیف پول لغو شد.', 'info')
    session.pop('wallet_amount', None)
    session.pop('wallet_code', None)
    return redirect(url_for('features.wallet'))


# ================================================================
# ارجاع دوستان
# ================================================================
@features_bp.route('/dashboard/referral')
def referral():
    if not g.user:
        return redirect(url_for('auth.login'))
    if not g.user.referral_code:
        make_referral_code(g.user)
        db.session.commit()
    from models import User, Order, WalletTransaction
    invited_users = User.query.filter_by(referred_by=g.user.id).order_by(User.created_at.desc()).all()
    invited_ids = [u.id for u in invited_users]
    # خریدهای پرداخت‌شده دعوت‌شده‌ها
    invited_orders = []
    if invited_ids:
        invited_orders = Order.query.filter(Order.user_id.in_(invited_ids), Order.status == 'paid') \
            .order_by(Order.paid_at.desc()).all()
    total_purchased = sum(o.final_total for o in invited_orders)
    # پاداش‌های کسب‌شده از ارجاع (کیف پول)
    bonuses = WalletTransaction.query.filter_by(user_id=g.user.id) \
        .filter(WalletTransaction.detail.like('%ارجاع%') | WalletTransaction.detail.like('%معرفی%')) \
        .order_by(WalletTransaction.created_at.desc()).all()
    bonus_sum = sum(t.amount for t in bonuses)
    # رتبه افیلیت بر اساس مجموع خرید دعوت‌شده‌ها
    rank = 'نقره‌ای'
    if total_purchased >= 20_000_000:
        rank = 'الماس'
    elif total_purchased >= 10_000_000:
        rank = 'طلایی'
    elif total_purchased >= 3_000_000:
        rank = 'برنزی'
    next_rank_gap = max(0, 3_000_000 - total_purchased)
    link = request.host_url.rstrip('/') + '/register?ref=' + g.user.referral_code
    g.seo['title'] = "دعوت دوستان — آکادمی آنلاین"
    return render_template('features/referral.html', link=link,
                           invited=len(invited_users), invited_users=invited_users,
                           invited_orders=invited_orders, total_purchased=total_purchased,
                           bonuses=bonuses, bonus_sum=bonus_sum, rank=rank,
                           next_rank_gap=next_rank_gap)


# ================================================================
# شبیه‌ساز آزمون (کنکور) — آزمون تصادفی از بانک سوال
# ================================================================
@features_bp.route('/exam/practice')
def exam_practice():
    """صفحه انتخاب آزمون تمرینی"""
    from models import QuestionBank, ExamAttempt
    if not g.user:
        return redirect(url_for('auth.login', next=request.path))
    cats = [r[0] for r in db.session.query(QuestionBank.category)
            .distinct().order_by(QuestionBank.category).all() if r[0]]
    total_q = QuestionBank.query.count()
    history = ExamAttempt.query.filter_by(user_id=g.user.id) \
        .order_by(ExamAttempt.created_at.desc()).limit(10).all()
    g.seo['title'] = "شبیه‌ساز آزمون — تمرین تستی از بانک سوال | آکادمی آنلاین"
    g.seo['description'] = "آزمون تمرینی زمان‌دار با سوالات تصادفی از بانک سوال: مثل جلسه کنکور تمرین کن، نمره بگیر و پیشرفتت را ببین."
    return render_template('features/exam_practice.html', cats=cats, total_q=total_q,
                           history=history)


@features_bp.route('/exam/practice/start', methods=['POST'])
def exam_practice_start():
    """شروع آزمون: انتخاب تصادفی سوالات از بانک"""
    from models import QuestionBank
    if not g.user:
        return redirect(url_for('auth.login'))
    cat = request.form.get('category', '').strip()
    count = min(40, max(5, int(request.form.get('count') or 10)))
    q = QuestionBank.query
    if cat:
        q = q.filter_by(category=cat)
    pool = q.all()
    if not pool:
        flash('در این دسته سوالی وجود ندارد. اول سوال بسازید.', 'error')
        return redirect(url_for('features.exam_practice'))
    import random as _r
    chosen = _r.sample(pool, min(count, len(pool)))
    ids = [c.id for c in chosen]
    session['exam'] = {'ids': ids, 'start': utcnow().isoformat(),
                       'cat': cat or 'همه دسته‌ها', 'count': len(ids)}
    return redirect(url_for('features.exam_practice_take'))


@features_bp.route('/exam/practice/take')
def exam_practice_take():
    if not g.user:
        return redirect(url_for('auth.login'))
    from models import QuestionBank
    exam = session.get('exam')
    if not exam:
        flash('ابتدا یک آزمون شروع کنید.', 'info')
        return redirect(url_for('features.exam_practice'))
    questions = [q for q in QuestionBank.query.filter(QuestionBank.id.in_(exam['ids']))]
    # ترتیب اصلی سوالات را حفظ کن
    by_id = {q.id: q for q in questions}
    questions = [by_id[i] for i in exam['ids'] if i in by_id]
    total_sec = len(questions) * 45  # ۴۵ ثانیه برای هر سوال
    g.seo['title'] = "آزمون در حال اجرا ⏱ — آکادمی آنلاین"
    return render_template('features/exam_take.html', questions=questions,
                           total_sec=total_sec, exam=exam)


@features_bp.route('/exam/practice/submit', methods=['POST'])
def exam_practice_submit():
    from models import QuestionBank, ExamAttempt
    from datetime import datetime as _dt
    if not g.user:
        return redirect(url_for('auth.login'))
    exam = session.get('exam')
    if not exam:
        flash('جلسه آزمون منقضی شده است.', 'info')
        return redirect(url_for('features.exam_practice'))
    questions = QuestionBank.query.filter(QuestionBank.id.in_(exam['ids'])).all()
    by_id = {q.id: q for q in questions}
    score = 0
    answers = {}
    for qid in exam['ids']:
        q = by_id.get(qid)
        if not q:
            continue
        chosen = request.form.get(f'q_{qid}')
        chosen_i = int(chosen) if chosen and chosen.isdigit() else -1
        answers[str(qid)] = chosen_i
        if chosen_i == q.correct_index:
            score += 1
    try:
        start = _dt.fromisoformat(exam['start'])
        duration = max(0, int((utcnow() - start).total_seconds()))
    except Exception:
        duration = 0
    attempt = ExamAttempt(user_id=g.user.id, category=exam['cat'],
                          question_ids=json.dumps(exam['ids'], ensure_ascii=False),
                          answers=json.dumps(answers, ensure_ascii=False),
                          score=score, total=len(exam['ids']),
                          duration_sec=duration)
    db.session.add(attempt)
    db.session.commit()
    session.pop('exam', None)
    return redirect(url_for('features.exam_practice_result', aid=attempt.id))


@features_bp.route('/exam/practice/result/<int:aid>')
def exam_practice_result(aid):
    from models import ExamAttempt, QuestionBank
    if not g.user:
        return redirect(url_for('auth.login'))
    attempt = ExamAttempt.query.get_or_404(aid)
    if attempt.user_id != g.user.id and g.user.role not in ('admin', 'super_admin'):
        flash('این آزمون متعلق به شما نیست.', 'error')
        return redirect(url_for('features.exam_practice'))
    questions = QuestionBank.query.filter(QuestionBank.id.in_(attempt.qids())).all()
    by_id = {q.id: q for q in questions}
    questions = [by_id[i] for i in attempt.qids() if i in by_id]
    answers = attempt.answers_map()
    g.seo['title'] = "نتیجه آزمون — آکادمی آنلاین"
    return render_template('features/exam_result.html', attempt=attempt,
                           questions=questions, answers=answers)


@features_bp.route('/exam/practice/history')
def exam_practice_history():
    from models import ExamAttempt
    if not g.user:
        return redirect(url_for('auth.login'))
    items = ExamAttempt.query.filter_by(user_id=g.user.id) \
        .order_by(ExamAttempt.created_at.desc()).all()
    best = max((i.score for i in items), default=0)
    avg = round(sum(i.score * 100 / i.total for i in items if i.total) / len(items)) if items else 0
    g.seo['title'] = "تاریخچه آزمون‌ها — آکادمی آنلاین"
    return render_template('features/exam_history.html', items=items, best=best, avg=avg)


# ================================================================
# داستان‌های موفقیت
# ================================================================
@features_bp.route('/success-stories')
def success_stories():
    from models import SuccessStory
    stories = SuccessStory.query.filter_by(is_active=True).order_by(SuccessStory.sort).all()
    g.seo['title'] = "داستان‌های موفقیت دانشجویان — آکادمی آنلاین"
    g.seo['description'] = "نتایج واقعی دانشجویان آکادمی: چه کسانی چه مسیری را رفتند و به کجا رسیدند."
    return render_template('features/success_stories.html', stories=stories)


# ================================================================
# باندل‌ها
# ================================================================
@features_bp.route('/bundles')
def bundles():
    items = Bundle.query.filter_by(is_active=True).all()
    g.seo['title'] = "بسته‌های آموزشی (باندل) — آکادمی آنلاین"
    return render_template('features/bundles.html', bundles=items)


@features_bp.route('/bundle/<slug>')
def bundle_detail(slug):
    b = Bundle.query.filter_by(slug=slug, is_active=True).first_or_404()
    g.seo['title'] = f"{b.title} — آکادمی آنلاین"
    return render_template('features/bundle_detail.html', b=b)


@features_bp.route('/bundle/<slug>/buy', methods=['POST'])
def bundle_buy(slug):
    if not g.user:
        return redirect(url_for('auth.login', next=request.path))
    b = Bundle.query.filter_by(slug=slug, is_active=True).first_or_404()
    if not b.courses:
        flash('این بسته هنوز دوره‌ای ندارد.', 'error')
        return redirect(url_for('features.bundle_detail', slug=slug))
    # ساخت سفارش با همه دوره‌های باندل
    final = b.discount_price if b.discount_price and b.discount_price < b.price else b.price
    code = f"AC-{datetime.now():%y%m%d}-{random.randint(1000, 9999)}"
    while Order.query.filter_by(code=code).first():
        code = f"AC-{datetime.now():%y%m%d}-{random.randint(1000, 9999)}"
    order = Order(code=code, user_id=g.user.id, total=b.price, discount=b.price - final,
                  final_total=final, status='pending', bundle_id=b.id)
    for c in b.courses:
        order.items.append(OrderItem(course_id=c.id, price=c.final_price))
    db.session.add(order)
    db.session.commit()
    flash('سفارش بسته ثبت شد. لطفاً پرداخت را تکمیل کنید.', 'info')
    return redirect(url_for('shop.pay_start', code=code))


# ================================================================
# مقایسه دوره‌ها
# ================================================================
@features_bp.route('/compare')
def compare():
    ids = request.args.get('ids', '')
    try:
        id_list = [int(x) for x in ids.split(',') if x.strip().isdigit()][:4]
    except Exception:
        id_list = []
    courses = []
    if id_list:
        courses = [Course.query.filter_by(id=i, status='published').first() for i in id_list]
        courses = [c for c in courses if c]
    g.seo['title'] = "مقایسه دوره‌های آموزشی — آکادمی آنلاین"
    return render_template('features/compare.html', courses=courses)


# ================================================================
# برنامه مطالعاتی شخصی
# ================================================================
@features_bp.route('/dashboard/study-plan', methods=['GET', 'POST'])
def study_plan():
    if not g.user:
        return redirect(url_for('auth.login'))
    plan = StudyPlan.query.filter_by(user_id=g.user.id).first()
    if request.method == 'POST':
        minutes = request.form.get('daily_minutes', '60').strip()
        goal = request.form.get('goal', '').strip()
        if not plan:
            plan = StudyPlan(user_id=g.user.id)
            db.session.add(plan)
        plan.daily_minutes = int(minutes) if minutes.isdigit() else 60
        plan.goal = goal
        g.user.study_daily_minutes = plan.daily_minutes
        db.session.commit()
        flash('برنامه مطالعاتی شما ذخیره شد. 📅', 'success')
        return redirect(url_for('features.study_plan'))
    # محاسبه پیشنهاد بر اساس دوره‌های ثبت‌نامی
    enrolled = Enrollment.query.filter_by(user_id=g.user.id).all()
    total_hours = sum(e.course.duration_hours or 0 for e in enrolled)
    daily = plan.daily_minutes if plan else (g.user.study_daily_minutes or 60)
    days_needed = round(total_hours * 60 / max(daily, 1)) if daily else 0
    return render_template('features/study_plan.html', plan=plan,
                           enrolled=enrolled, total_hours=total_hours,
                           days_needed=days_needed)


# ================================================================
# تعیین سطح هوشمند (آزمون سراسری)
# ================================================================
@features_bp.route('/placement-test')
def placement():
    quiz = Quiz.query.filter_by(is_placement=True, is_published=True).first()
    if not quiz:
        flash('آزمون تعیین سطح به‌زودی برگزار می‌شود.', 'info')
        return redirect(url_for('site.index'))
    return redirect(url_for('features.quiz_start', qid=quiz.id))


@features_bp.route('/placement/result', methods=['POST'])
def placement_result():
    quiz = Quiz.query.filter_by(is_placement=True).first()
    if not quiz:
        return redirect(url_for('site.index'))
    total = len(quiz.questions)
    correct = 0
    for q in quiz.questions:
        chosen = request.form.get(f'q_{q.id}')
        if chosen and chosen.isdigit() and int(chosen) == q.correct_index:
            correct += 1
    pct = round(correct * 100 / total) if total else 0
    if pct >= 70:
        level = 'پیشرفته'
    elif pct >= 40:
        level = 'متوسط'
    else:
        level = 'مقدماتی'
    if g.user:
        g.user.level_pref = level
        db.session.commit()
    courses = Course.query.filter_by(status='published', level=level).limit(6).all()
    return render_template('features/placement_result.html', score=pct, level=level,
                           courses=courses)
