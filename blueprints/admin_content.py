# -*- coding: utf-8 -*-
"""دامنهٔ محتوا — وبلاگ، نظرات، تیکت، صفحه، فرم، منو، انجمن و گواهی.

Route های این دامنه روی Blueprint مشترک ``admin_bp`` (از ``admin_core``)
ثبت می‌شوند؛ ``blueprints/admin_bp.py`` در انتهای خود این ماژول را
import می‌کند تا ثبت انجام شود. هیچ منطقی اینجا نباید مستقیماً
``db.session.commit()`` صدا بزند یا ورودی خام فرم را کست کند — هر دو
از ``admin_core`` می‌آیند.
"""
from __future__ import annotations

import json
import os
import uuid

from datetime import datetime, timedelta
from flask import (render_template, request, redirect, url_for, flash, g, Response)
from admin_queries import (activity_list, behavior_report as behavior_data, blog_list,
                           certificate_rows, form_entry_counts, message_list,
                           newsletter_list, review_lists, ticket_report)
from admin_core import (
    audit,
    commit,
    go_referrer,
    COVER_IMAGES,
    best_effort,
    slugify,
    admin_bp, admin_required, form
)
from models import (
    ActivityLog, BlogComment, BlogPost, CannedReply, ContactMessage, CustomForm,
    CustomFormEntry, Enrollment, ForumPost, ForumTopic, Menu, MenuItem,
    NewsletterEmail, Notification, Page, PageRevision, Review, SeoMeta, Setting,
    Ticket, TicketReply, User, certificate_code, db,
    slug_matches_title, unique_slug_for, utcnow
)
from validators import (csv_cell, safe_filename, safe_int, safe_referrer, log_exc as _lexc)
from jdates import (jdate_num, jtime)


@admin_bp.route('/blog', methods=['GET', 'POST'])
@admin_required
def blog():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'delete':
            p = db.session.get(BlogPost, safe_int(request.form.get('pid')))
            if p:
                db.session.delete(p)
                commit(success='مطلب حذف شد.', category='info')
        return redirect(url_for('admin.blog'))
    # صفحه‌بندی‌شده؛ قبلاً همهٔ مطالب یکجا رندر می‌شد.
    posts, page, pages, total = blog_list()
    return render_template('admin/blog.html', posts=posts, total=total,
                           page=page, pages=pages)


@admin_bp.route('/blog/new', methods=['GET', 'POST'])
@admin_required
def blog_new():
    return _blog_form(None)


@admin_bp.route('/blog/<int:pid>/edit', methods=['GET', 'POST'])
@admin_required
def blog_edit(pid):
    post = db.get_or_404(BlogPost, pid)
    return _blog_form(post)


def _blog_form(post):
    if request.method == 'POST':
        f = request.form
        if not post:
            post = BlogPost(author_id=g.user.id)
            from models import unique_slug_for as _usfb
            post.slug = _usfb(BlogPost, f.get('title', ''), fallback='post')
            db.session.add(post)
        _old_title_b = post.title
        _old_path_b = '/blog/' + post.slug if post.slug else None
        post.title = f.get('title', '').strip()
        # همگام‌سازی اسلاگ در ویرایش — جلوگیری از ۴۰۴ بعد از تغییر عنوان
        from models import unique_slug_for as _usf2, slug_matches_title as _smt2
        _slug_in_b = (f.get('slug') or '').strip()
        if _slug_in_b:
            post.slug = _usf2(BlogPost, _slug_in_b, exclude_id=post.id, fallback='post')
        elif not post.slug:
            post.slug = _usf2(BlogPost, post.title, exclude_id=post.id, fallback='post')
        elif _old_title_b and _old_title_b != post.title \
                and _smt2(post.slug, _old_title_b, 'post'):
            post.slug = _usf2(BlogPost, post.title, exclude_id=post.id, fallback='post')
        post.excerpt = f.get('excerpt', '').strip()
        post.body = f.get('body', '').strip()
        post.category = f.get('category', 'آموزش').strip()
        post.image = f.get('image', 'cover-python.webp')
        post.published = bool(f.get('published'))
        if not post.title:
            flash('عنوان الزامی است.', 'error')
        else:
            commit(context='admin._blog_form')
            def _sync_seo():
                from seo_service import ensure_meta, save_seo_from_form
                _p_b = '/blog/' + (post.slug or str(post.id))
                ensure_meta(_p_b)
                commit(context='admin._blog_form')
                save_seo_from_form(_p_b, f, old_path=_old_path_b)
            best_effort(_sync_seo, 'admin.blog_seo')
            flash('مطلب ذخیره شد.', 'success')
            return redirect(url_for('admin.blog'))
    images = COVER_IMAGES
    _seo_b = None
    if post and post.slug:
        from seo_service import get_seo_for
        _seo_b = get_seo_for('/blog/' + post.slug)
    return render_template('admin/blog_form.html', post=post, images=images, seo=_seo_b)


# ---------------------------------------------------------------- نظرات دوره‌ها


@admin_bp.route('/reviews', methods=['GET', 'POST'])
@admin_required
def reviews():
    if request.method == 'POST':
        action = request.form.get('action')
        rid = safe_int(request.form.get('rid'))
        if action in ('approve_blog', 'delete_blog'):
            bc = db.session.get(BlogComment, rid)
            if bc:
                if action == 'approve_blog':
                    bc.is_approved = True
                    commit(success='دیدگاه وبلاگ تایید شد.')
                else:
                    db.session.delete(bc)
                    commit(success='دیدگاه وبلاگ حذف شد.', category='info')
            return redirect(url_for('admin.reviews'))
        rv = db.session.get(Review, rid)
        if rv:
            if action == 'approve':
                rv.is_approved = True
                commit(success='نظر تایید شد.')
            elif action == 'delete':
                db.session.delete(rv)
                commit(success='نظر حذف شد.', category='info')
        return redirect(url_for('admin.reviews'))
    reviews, blog_comments = review_lists()
    return render_template('admin/reviews.html', reviews=reviews,
                           blog_comments=blog_comments)


@admin_bp.route('/reviews/bulk', methods=['POST'])
@admin_required
def reviews_bulk():
    """عملیات گروهی روی نظرات دوره یا وبلاگ"""
    action = request.form.get('action') or request.form.get('bulk_action')
    review_type = request.form.get('type', 'course')
    ids = request.form.getlist('ids') or request.form.getlist('item_ids[]')
    id_list = [safe_int(x) for x in ids if safe_int(x)]
    if not id_list:
        flash('هیچ موردی انتخاب نشده است.', 'error')
        return redirect(url_for('admin.reviews'))

    if review_type == 'blog':
        if action == 'approve':
            BlogComment.query.filter(BlogComment.id.in_(id_list)).update({BlogComment.is_approved: True}, synchronize_session=False)
            commit(success=f'{len(id_list)} دیدگاه وبلاگ تایید شدند. ✅')
        elif action == 'delete':
            BlogComment.query.filter(BlogComment.id.in_(id_list)).delete(synchronize_session=False)
            commit(success=f'{len(id_list)} دیدگاه وبلاگ حذف شدند.', category='info')
    else:
        if action == 'approve':
            Review.query.filter(Review.id.in_(id_list)).update({Review.is_approved: True}, synchronize_session=False)
            commit(success=f'{len(id_list)} نظر دوره تایید شدند. ✅')
        elif action == 'delete':
            Review.query.filter(Review.id.in_(id_list)).delete(synchronize_session=False)
            commit(success=f'{len(id_list)} نظر دوره حذف شدند.', category='info')

    return redirect(url_for('admin.reviews'))


@admin_bp.route('/activity')
@admin_required
def activity():
    """لاگ فعالیت کاربران"""
    return render_template('admin/activity.html', logs=activity_list())


# ================================================================
# آزمون‌ها
# ================================================================


@admin_bp.route('/certificates')
@admin_required
def certificates():
    """مدیریت گواهی‌های صادرشده.

    قبلاً به‌ازای هر گواهی ``user`` و ``course`` جدا lazy-load می‌شد (۲N کوئری).
    اکنون هر دو رابطه پیش‌بارگذاری می‌شوند.
    """
    return render_template('admin/certificates.html', certs=certificate_rows())


@admin_bp.route('/certificates/<int:eid>/revoke', methods=['POST'])
@admin_required
def certificate_revoke(eid):
    """لغو گواهی — ثبت تاریخ ابطال، حذف completed_at و ریست پیشرفت کامل"""
    from models import Enrollment, utcnow
    e = db.get_or_404(Enrollment, eid)
    e.completed_at = None
    e.revoked_at = utcnow()
    audit('certificate_revoke', f'enrollment #{e.id}')
    if e.progress:
        prog = e.progress_list()
        if prog:
            prog.pop()
            e.save_progress(prog)
    from models import Notification
    Notification.notify(e.user_id, 'گواهی شما لغو شد ⚠️',
                        'گواهینامه دوره توسط مدیریت باطل گردید. در صورت اعتراض با پشتیبانی تماس بگیرید.', '⚠️')
    commit(success='گواهی با موفقیت باطل شد.', category='warning')
    return redirect(url_for('admin.certificates'))


@admin_bp.route('/behavior-report')
@admin_required
def behavior_report():
    """گزارش رفتار دانشجو: نرخ تکمیل، افت، میانگین پیشرفت.

    قبلاً ``Enrollment.query.all()`` بود — کل جدول به‌صورت موجودیت کامل ORM،
    همراه با lazy-load کاربر، دوره، سکشن‌ها و جلساتِ هر دوره به‌ازای هر ردیف.
    محاسبهٔ درصد به :func:`admin_queries._lesson_count_subquery` منتقل شده که
    همان عدد را با یک correlated subquery می‌گیرد.
    """
    return render_template('admin/behavior_report.html', **behavior_data())

@admin_bp.route('/faq', methods=['GET', 'POST'])
@admin_required
def faq_manage():
    """CMS سوالات متداول."""
    import json as _json
    row = db.session.get(Setting, 'faq_items')
    items = []
    if row and row.value:
        try:
            items = _json.loads(row.value)
        except Exception:
            items = []
    if not isinstance(items, list):
        items = []
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            q = (request.form.get('q') or '').strip()
            a = (request.form.get('a') or '').strip()
            icon = (request.form.get('icon') or '❓').strip()[:8]
            if q and a:
                items.append({'q': q[:300], 'a': a[:2000], 'icon': icon})
        elif action == 'delete':
            try:
                idx = form().int('idx', -1)
                if 0 <= idx < len(items):
                    items.pop(idx)
            except (TypeError, ValueError):
                pass
        payload = _json.dumps(items, ensure_ascii=False)
        if row:
            row.value = payload
        else:
            db.session.add(Setting(key='faq_items', value=payload))
        commit(success='سوالات متداول ذخیره شد.')
        return redirect(url_for('admin.faq_manage'))
    return render_template('admin/faq.html', items=items)


# بارگذاری بخش‌های تکمیلی (گزارش‌ها، رسانه، داستان موفقیت، اعلان‌ها، مشاوره‌ها)
# این import صرفاً برای اجرای decoratorهای @admin_bp.route در admin_extra است
# (star-import نمی‌کنیم تا namespace admin_bp آلودهٔ متغیرهای محلی admin_extra نشود)
