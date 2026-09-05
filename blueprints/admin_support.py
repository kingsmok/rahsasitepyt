# -*- coding: utf-8 -*-
"""دامنهٔ پشتیبانی — تیکت، پیام، خبرنامه، پاسخ آماده و انجمن.

جداشده از ``admin_content.py`` که به ۹۲۶ خط و ۴۷ route رسیده بود — همان
مشکلی که تقسیم ``admin_bp.py`` حل کرده بود، در یک‌سوم مقیاس.
"""
from __future__ import annotations

import os
import uuid

from sqlalchemy import func
from flask import (render_template, request, redirect, url_for, flash, g)
from admin_core import (
    admin_bp, admin_required, commit, go_referrer
)
from models import (
    CannedReply, ForumPost, ForumTopic, NewsletterEmail, Notification, Setting, Ticket,
    TicketReply, User, db, utcnow
)
from admin_queries import message_list, newsletter_list, ticket_report
from validators import (safe_filename, safe_int, log_exc as _lexc)


@admin_bp.route('/messages')
@admin_required
def messages():
    # سقف صریح: یک صندوق پیام بی‌کران نباید در یک پاسخ رندر شود.
    return render_template('admin/messages.html', msgs=message_list())


@admin_bp.route('/newsletters')
@admin_required
def newsletters():
    return render_template('admin/newsletters.html', emails=newsletter_list())


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
                                    url_for('student.ticket_view', tid=t.id))
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
            commit(success='تیکت به\u200cروزرسانی شد.')
        return go_referrer('admin.tickets')
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
    commit(success='پاسخ با پیوست ثبت شد.')
    return redirect(url_for('admin.ticket_detail', tid=tid))


@admin_bp.route('/tickets/report')
@admin_required
def tickets_report():
    """گزارش عملکرد پشتیبان‌ها و میانگین زمان پاسخ.

    یک کوئری سه‌ستونی به‌جای واکشی موجودیت کامل هر تیکت. تفاضل timestamp عمداً
    در SQL تجمیع نمی‌شود (تفاوت SQLite/MySQL) — توضیح کامل در
    :func:`admin_queries.ticket_report`.
    """
    return render_template('admin/tickets_report.html', **ticket_report())


@admin_bp.route('/canned-replies', methods=['GET', 'POST'])
@admin_required
def canned_replies():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
        if title and body:
            db.session.add(CannedReply(title=title, body=body))
            commit(success='پاسخ آماده ذخیره شد.')
        return redirect(url_for('admin.canned_replies'))
    items = CannedReply.query.order_by(CannedReply.created_at.desc()).all()
    return render_template('admin/canned_replies.html', items=items)


@admin_bp.route('/canned-replies/<int:rid>/delete', methods=['POST'])
@admin_required
def canned_reply_delete(rid):
    r = db.get_or_404(CannedReply, rid)
    db.session.delete(r)
    commit(context='admin.canned_reply_delete')
    return redirect(url_for('admin.canned_replies'))


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
    commit(success='وضعیت تایید تاپیک تغییر کرد.')
    return redirect(url_for('admin.forum_moderate'))


@admin_bp.route('/forum/post/<int:pid>/approve', methods=['POST'])
@admin_required
def forum_post_approve(pid):
    post = db.get_or_404(ForumPost, pid)
    post.is_approved = not post.is_approved
    commit(success='وضعیت تایید پاسخ تغییر کرد.')
    return redirect(url_for('admin.forum_moderate'))


@admin_bp.route('/forum/<int:tid>/delete', methods=['POST'])
@admin_required
def forum_topic_delete(tid):
    t = db.get_or_404(ForumTopic, tid)
    db.session.delete(t)
    commit(success='تاپیک حذف شد.', category='info')
    return redirect(url_for('admin.forum_moderate'))


@admin_bp.route('/forum/<int:tid>/pin', methods=['POST'])
@admin_required
def forum_topic_pin(tid):
    t = db.get_or_404(ForumTopic, tid)
    t.is_pinned = not t.is_pinned
    commit(context='admin.forum_topic_pin')
    return redirect(url_for('admin.forum_moderate'))


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
