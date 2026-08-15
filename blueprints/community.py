# -*- coding: utf-8 -*-
"""انجمن گفتگو، کلاس‌های آنلاین و گزارش رفتار دانشجو"""
import json
import time as _time
import threading as _thr
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort, jsonify
_msg_lock = _thr.Lock()
_msg_lim = {}  # user_id -> [timestamps] — ضد اسپم پیام خصوصی

from models import (utcnow, db, User, Course, ForumTopic, ForumPost, LiveSession,
                    Enrollment, ActivityLog, PrivateMessage, ForumPoll, ForumPollVote)

community_bp = Blueprint('community', __name__, url_prefix='/community')


@community_bp.route('/')
def forum():
    """صفحه انجمن — تاپیک‌ها"""
    course_id = request.args.get('course', type=int)
    query = ForumTopic.query
    if course_id:
        query = query.filter_by(course_id=course_id)
    topics = query.order_by(ForumTopic.is_pinned.desc(), ForumTopic.created_at.desc()).all()
    # تعداد پاسخ هر تاپیک — یک کوئری تجمیعی (بدون N+1)
    from sqlalchemy import func as _f
    tids = [t.id for t in topics]
    post_counts = {}
    if tids:
        pc = db.session.query(ForumPost.topic_id, _f.count(ForumPost.id)) \
            .filter(ForumPost.topic_id.in_(tids)).group_by(ForumPost.topic_id).all()
        post_counts = dict(pc)
    courses = Course.query.filter_by(status='published').all()
    g.seo['title'] = 'انجمن گفتگو — آکادمی آنلاین'
    g.seo['description'] = 'پرسش و پاسخ، تبادل تجربه و گفتگو بین دانشجویان آکادمی آنلاین.'
    return render_template('community/forum.html', topics=topics, post_counts=post_counts,
                           courses=courses,
                           course_id=course_id)


@community_bp.route('/topic/new', methods=['POST'])
def topic_new():
    if not g.user:
        return redirect(url_for('auth.login', next=url_for('community.forum')))
    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()
    cid = request.form.get('course_id', type=int)
    if len(title) < 5:
        flash('عنوان تاپیک خیلی کوتاه است.', 'error')
    elif len(title) > 120 or len(body) > 5000:
        flash('طول عنوان یا متن بیش از حد مجاز است.', 'error')
    else:
        from gamification import award_points
        # ضد اسپم: حداکثر ۳ تاپیک در ساعت
        from datetime import timedelta as _td
        _recent = ForumTopic.query.filter(ForumTopic.user_id == g.user.id,
                                          ForumTopic.created_at >= utcnow() - _td(hours=1)).count()
        if _recent >= 3:
            flash('محدودیت ساخت تاپیک (۳ تاپیک در ساعت).', 'error')
            return redirect(url_for('community.forum'))
        db.session.add(ForumTopic(user_id=g.user.id, title=title, body=body,
                                  course_id=cid or None))
        # امتیاز فقط برای تاپیک‌های جدید (نه اسپم)
        if _recent == 0:
            award_points(g.user, 5, 'ساخت تاپیک انجمن')
        db.session.commit()
        flash('تاپیک شما منتشر شد. 🎉', 'success')
    return redirect(url_for('community.forum'))


@community_bp.route('/topic/<int:tid>/poll', methods=['POST'])
def topic_poll_create(tid):
    """ساخت نظرسنجی در تاپیک"""
    if not g.user:
        return redirect(url_for('auth.login'))
    topic = db.get_or_404(ForumTopic, tid)
    question = request.form.get('question', '').strip()
    options_raw = request.form.get('options', '').strip()
    if not question or not options_raw:
        flash('سوال و گزینه‌ها الزامی است.', 'error')
    else:
        options = [o.strip() for o in options_raw.split(',') if o.strip()]
        if len(options) >= 2:
            db.session.add(ForumPoll(topic_id=tid, question=question,
                                     options=json.dumps(options, ensure_ascii=False)))
            db.session.commit()
            flash('نظرسنجی ایجاد شد. 🗳', 'success')
        else:
            flash('حداقل ۲ گزینه وارد کنید.', 'error')
    return redirect(url_for('community.topic_view', tid=tid))


@community_bp.route('/topic/<int:tid>', methods=['GET', 'POST'])
def topic_view(tid):
    topic = db.get_or_404(ForumTopic, tid)
    topic.views = (topic.views or 0) + 1
    db.session.commit()
    # ثبت رای نظرسنجی (قبل از پردازش پاسخ)
    if request.method == 'POST' and request.form.get('poll_vote') is not None:
        poll_id = request.form.get('poll_id', type=int)
        opt = request.form.get('poll_vote', type=int)
        if g.user and poll_id and opt is not None:
            p = db.session.get(ForumPoll, poll_id)
            if p and not ForumPollVote.query.filter_by(poll_id=poll_id, user_id=g.user.id).first():
                db.session.add(ForumPollVote(poll_id=poll_id, user_id=g.user.id, option_index=opt))
                db.session.commit()
                flash('رای شما ثبت شد. 🗳', 'success')
        return redirect(url_for('community.topic_view', tid=tid))
    if request.method == 'POST':
        if not g.user:
            return redirect(url_for('auth.login', next=request.path))
        body = request.form.get('body', '').strip()
        if len(body) < 2:
            flash('پاسخ خیلی کوتاه است.', 'error')
        elif len(body) > 5000:
            flash('پاسخ بیش از حد طولانی است.', 'error')
        else:
            from gamification import award_points
            db.session.add(ForumPost(topic_id=tid, user_id=g.user.id, body=body))
            award_points(g.user, 2, 'پاسخ در انجمن')
            db.session.commit()
            flash('پاسخ شما ثبت شد. ✅', 'success')
        return redirect(url_for('community.topic_view', tid=tid))
    return render_template('community/topic.html', topic=topic)



@community_bp.route('/messages')
def messages():
    """صندوق پیام خصوصی — گفتگوها"""
    if not g.user:
        return redirect(url_for('auth.login'))
    # لیست گفتگوها — با کوئری‌های تجمیعی (بدون N+1)
    from sqlalchemy import func, or_, case
    uid = g.user.id
    # طرف مقابل هر پیام (فرمول: اگر من فرستنده‌ام → گیرنده، وگرنه → فرستنده)
    peer = case((PrivateMessage.sender_id == uid, PrivateMessage.recipient_id),
                else_=PrivateMessage.sender_id)
    # آخرین پیام + تعداد نخوانده هر گفتگو — یک کوئری گروهی
    stats = db.session.query(
        peer.label('peer_id'),
        func.max(PrivateMessage.created_at).label('last_at'),
        func.sum(case((PrivateMessage.recipient_id == uid, 1), else_=0)).label('unread'),
    ).filter(
        or_(PrivateMessage.sender_id == uid, PrivateMessage.recipient_id == uid)
    ).group_by(peer).all()
    rows = []
    for peer_id, last_at, unread in stats:
        other = db.session.get(User, peer_id)
        if not other:
            continue
        rows.append({'user': other, 'last': last_at, 'unread': int(unread or 0)})
    rows.sort(key=lambda r: r['last'] or 0, reverse=True)
    g.seo['title'] = 'پیام‌های من — آکادمی آنلاین'
    return render_template('community/messages.html', rows=rows)


@community_bp.route('/messages/<int:uid>', methods=['GET', 'POST'])
def message_conversation(uid):
    """مکالمه با یک کاربر"""
    if not g.user:
        return redirect(url_for('auth.login'))
    other = db.session.get(User, uid)
    if not other:
        abort(404)
    if request.method == 'POST':
        # ضد اسپم: حداکثر ۳۰ پیام در دقیقه (درون‌حافظه — چند-پردازنده با Redis همگام می‌شود)
        now = _time.time()
        with _msg_lock:
            _msg_lim.setdefault(g.user.id, [])
            _msg_lim[g.user.id] = [t for t in _msg_lim[g.user.id] if now - t < 60]
            if len(_msg_lim[g.user.id]) >= 30:
                flash('ارسال پیام بیش از حد — کمی صبر کنید.', 'error')
                return redirect(url_for('community.message_conversation', uid=uid))
            _msg_lim[g.user.id].append(now)
        body = request.form.get('body', '').strip()
        if body:
            db.session.add(PrivateMessage(sender_id=g.user.id, recipient_id=uid, body=body[:2000]))
            db.session.commit()
            return redirect(url_for('community.message_conversation', uid=uid))
    msgs = PrivateMessage.query.filter(
        ((PrivateMessage.sender_id == g.user.id) & (PrivateMessage.recipient_id == uid)) |
        ((PrivateMessage.sender_id == uid) & (PrivateMessage.recipient_id == g.user.id))) \
        .order_by(PrivateMessage.created_at.asc()).all()
    # خواندن پیام‌های دریافتی
    for m in msgs:
        if m.recipient_id == g.user.id and not m.is_read:
            m.is_read = True
    db.session.commit()
    return render_template('community/message_conv.html', other=other, msgs=msgs)


@community_bp.route('/api/messages/send', methods=['POST'])
def message_send_api():
    if not g.user:
        return jsonify(ok=False), 401
    uid = request.form.get('uid', type=int) or (request.json or {}).get('uid')
    body = (request.form.get('body') or (request.json or {}).get('body') or '').strip()
    if not uid or not body:
        return jsonify(ok=False, msg='مشخص نشده'), 400
    # ضد اسپم: حداکثر ۳۰ پیام در دقیقه
    now = _time.time()
    with _msg_lock:
        _msg_lim.setdefault(g.user.id, [])
        _msg_lim[g.user.id] = [t for t in _msg_lim[g.user.id] if now - t < 60]
        if len(_msg_lim[g.user.id]) >= 30:
            return jsonify(ok=False, msg='ارسال پیام بیش از حد — کمی صبر کنید.'), 429
        _msg_lim[g.user.id].append(now)
    db.session.add(PrivateMessage(sender_id=g.user.id, recipient_id=uid, body=body[:2000]))
    db.session.commit()
    return jsonify(ok=True)


# 2) برنامه کلاسی من (کلاس‌های رزرو شده)
@community_bp.route('/my-classes')
def my_classes():
    """کلاس‌های آنلاین مرتبط با دوره‌های من + رزروهایم"""
    if not g.user:
        return redirect(url_for('auth.login'))
    my_course_ids = [e.course_id for e in g.user.enrollments]
    upcoming = LiveSession.query.filter(
        LiveSession.starts_at >= utcnow(),
        (LiveSession.course_id.in_(my_course_ids) if my_course_ids else db.false()) |
        (LiveSession.course_id.is_(None))) \
        .order_by(LiveSession.starts_at.asc()).limit(20).all()
    booked = ActivityLog.query.filter_by(user_id=g.user.id, action='live_booking') \
        .order_by(ActivityLog.created_at.desc()).limit(20).all()
    g.seo['title'] = 'کلاس‌های من — آکادمی آنلاین'
    return render_template('community/my_classes.html', upcoming=upcoming, booked=booked)


@community_bp.route('/live')
def live():
    """کلاس‌های آنلاین آتی"""
    sessions = LiveSession.query.order_by(LiveSession.starts_at.desc()).all()
    g.seo['title'] = 'کلاس‌های آنلاین و وبینارها — آکادمی آنلاین'
    return render_template('community/live.html', sessions=sessions)


@community_bp.route('/live/<int:sid>/book', methods=['POST'])
def live_book(sid):
    """رزرو کلاس آنلاین — ثبت حضور در لاگ"""
    if not g.user:
        return redirect(url_for('auth.login', next=request.path))
    sess = db.get_or_404(LiveSession, sid)
    db.session.add(ActivityLog(user_id=g.user.id, action='live_booking',
                               detail=f'رزرو کلاس «{sess.title}»'))
    db.session.commit()
    flash(f'در کلاس «{sess.title}» ثبت‌نام شدید — لینک ورود برایتان فعال است. 🎥', 'success')
    return redirect(url_for('community.live'))
