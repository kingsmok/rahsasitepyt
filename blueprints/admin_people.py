# -*- coding: utf-8 -*-
"""دامنهٔ افراد — کاربران، نقش‌ها، کیف پول، چت و پیامک.

Route های این دامنه روی Blueprint مشترک ``admin_bp`` (از ``admin_core``)
ثبت می‌شوند؛ ``blueprints/admin_bp.py`` در انتهای خود این ماژول را
import می‌کند تا ثبت انجام شود. هیچ منطقی اینجا نباید مستقیماً
``db.session.commit()`` صدا بزند یا ورودی خام فرم را کست کند — هر دو
از ``admin_core`` می‌آیند.
"""
from __future__ import annotations

import os
import random
import uuid

from sqlalchemy import func
from flask import (render_template, request, redirect, url_for, flash, g, abort, session, jsonify)
from admin_queries import user_list
from admin_core import (
    audit,
    commit,
    require_manager,
    admin_bp, admin_required
)
from models import (
    ActivityLog, CannedReply, ChatMessage, Enrollment, Notification, Order, ROLES,
    Setting, Ticket, User, db, resolve_image_url
)
from validators import (ALLOWED_IMAGE_EXT, file_content_is_safe, safe_filename, safe_int, log_exc as _lexc)


@admin_bp.route('/users')
@admin_required
def users():
    """فهرست کاربران — صفحه‌بندی‌شده.

    قبلاً ``.all()`` روی کل جدول کاربران بود؛ با ۵۰٬۰۰۰ کاربر یعنی رندر
    ۵۰٬۰۰۰ ردیف HTML در یک پاسخ.
    """
    q = request.args.get('q', '').strip()
    items, page, pages, total = user_list(q)
    return render_template('admin/users.html', users=items, q=q,
                           total=total, page=page, pages=pages)


@admin_bp.route('/users/<int:uid>/role', methods=['POST'])
@admin_required
@require_manager
def user_role(uid):
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
    audit('role_change', f'{user.email}: {new_role}')
    commit(success='نقش کاربر به\u200cروزرسانی شد.')
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
    audit('user_toggle', f'{user.email} -> {"فعال" if user.is_active else "غیرفعال"}')
    commit(success='وضعیت کاربر تغییر کرد.')
    return redirect(url_for('admin.users'))


# ---------------------------------------------------------------- سفارش‌ها


@admin_bp.route('/users/bulk', methods=['POST'])
@admin_required
@require_manager
def users_bulk():
    """عملیات گروهی روی کاربران (فعال/غیرفعال‌سازی)"""
    action = request.form.get('action') or request.form.get('bulk_action')
    ids = request.form.getlist('ids') or request.form.getlist('item_ids[]')
    id_list = [safe_int(x) for x in ids if safe_int(x) and safe_int(x) != g.user.id]
    if not id_list:
        flash('هیچ کاربری انتخاب نشده است.', 'error')
        return redirect(url_for('admin.users'))

    query = User.query.filter(User.id.in_(id_list))
    if g.user.role != 'super_admin':
        query = query.filter(~User.role.in_(['admin', 'super_admin']))

    users = query.all()
    count = len(users)
    if action == 'activate':
        for u in users:
            u.is_active = True
        commit(success=f'{count} کاربر با موفقیت فعال شدند. ✅')
    elif action == 'deactivate':
        for u in users:
            u.is_active = False
            u.new_session_token()
        commit(success=f'{count} کاربر غیرفعال شدند.', category='info')

    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:uid>/login-as', methods=['POST'])
@admin_required
@require_manager
def user_login_as(uid):
    """ورود به حساب کاربر توسط مدیر ارشد — با ثبت لاگ."""
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
    commit(context='admin.user_login_as')
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
        commit(success=f'رمز {u.name} تغییر کرد و همه سشن\u200cها باطل شد. 🔑')
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
            commit(context='admin.user_add')
            from gamification import make_referral_code
            make_referral_code(u)
            commit(context='admin.user_add')
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
        if wallet_charge(u, amount, 'شارژ توسط مدیریت — ' + note):
            commit(success=f'{amount:,} تومان به کیف پول {u.name} اضافه شد. ✅')
        else:
            db.session.rollback()
            flash('خطا در افزایش موجودی کیف پول.', 'error')
    elif action == 'deduct':
        if wallet_spend(u, amount, 'کسر توسط مدیریت — ' + note):
            commit(success=f'{amount:,} تومان از کیف پول {u.name} کسر شد.', category='info')
        else:
            db.session.rollback()
            flash(f'موجودی کیف پول کاربر ({u.wallet_balance or 0:,} تومان) کمتر از مبلغ درخواستی برای کسر است.', 'error')
    return redirect(url_for('admin.user_profile', uid=uid))


@admin_bp.route('/users/<int:uid>/notify', methods=['POST'])
@admin_required
def user_notify(uid):
    from models import Notification
    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()
    if title:
        Notification.notify(uid, title, body, '📨')
        commit(success='اعلان به کاربر ارسال شد. ✅')
    return redirect(url_for('admin.user_profile', uid=uid))


# ================================================================
# تسویه با مدرس‌ها
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
    canned = CannedReply.query.all()
    # خواندن پیام‌های کاربر
    for m in msgs:
        if not m.is_admin and not m.is_read:
            m.is_read = True
    commit(context='admin.chat_user')
    return render_template('admin/chat_user.html', u=u, msgs=msgs, canned=canned)


@admin_bp.route('/chat/<int:uid>/poll')
@admin_required
def chat_poll(uid):
    """Polling: پیام جدید از کاربر؟"""
    last = ChatMessage.query.filter_by(user_id=uid).order_by(ChatMessage.created_at.desc()).first()
    new_msg = last and not last.is_admin and not last.is_read
    if new_msg:
        last.is_read = True
        commit(context='admin.chat_poll')
    return jsonify(new_msg=bool(new_msg))


@admin_bp.route('/chat/<int:uid>/send', methods=['POST'])
@admin_required
def chat_send(uid):
    body = request.form.get('body', '').strip()
    if body:
        db.session.add(ChatMessage(user_id=uid, body=body, is_admin=True))
        commit(context='admin.chat_send')
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
