# -*- coding: utf-8 -*-
"""پنل سئو پیشرفته — شبیه Rank Math Pro"""
import re
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, jsonify, abort)
from models import (db, SeoMeta, RedirectRule, NotFoundLog, Setting,
                    Course, BlogPost, Page, User, Category)
from validators import safe_referrer

seo_bp = Blueprint('seo_admin', __name__, url_prefix='/admin/seo')


def _admin_required():
    if not g.user:
        return redirect(url_for('auth.login', next=request.path))
    from permissions import has_permission
    if not has_permission(g.user, 'manage_seo'):
        abort(403)
    return None


@seo_bp.route('/')
def dashboard():
    """داشبورد سلامت سئو — نمای کلی همه صفحات با امتیاز"""
    r = _admin_required()
    if r:
        return r
    # جمع‌آوری همه صفحات قابل سئو
    items = []
    seen = set()
    for c in Course.query.filter_by(status='published').all():
        p = '/course/' + c.slug
        if p not in seen:
            seen.add(p)
            items.append(dict(path=p, name=c.title, kind='course',
                              seo=SeoMeta.query.filter_by(path=p).first()))
    for b in BlogPost.query.filter_by(published=True).all():
        p = '/blog/' + b.slug
        if p not in seen:
            seen.add(p)
            items.append(dict(path=p, name=b.title, kind='post',
                              seo=SeoMeta.query.filter_by(path=p).first()))
    for t in User.query.filter(User.role == 'teacher').all():
        p = '/teacher/' + str(t.id)
        if p not in seen:
            seen.add(p)
            items.append(dict(path=p, name=t.name, kind='teacher',
                              seo=SeoMeta.query.filter_by(path=p).first()))
    for pg in Page.query.filter(Page.ptype.in_(['page', 'home', '404', 'post'])).all():
        p = '/page/' + pg.slug if pg.ptype in ('page',) else ('/' if pg.ptype == 'home' else '/' + pg.ptype)
        if pg.ptype == 'post':
            p = '/page/post-template'
        if p not in seen:
            seen.add(p)
            items.append(dict(path=p, name=pg.title, kind='page',
                              seo=SeoMeta.query.filter_by(path=p).first()))

    # آمار
    with_seo = [i for i in items if i['seo']]
    scored = [i for i in with_seo if i['seo'].score and i['seo'].score > 0]
    avg = round(sum(i['seo'].score for i in scored) / len(scored)) if scored else 0
    great = sum(1 for i in scored if i['seo'].score >= 80)
    good = sum(1 for i in scored if 55 <= i['seo'].score < 80)
    bad = sum(1 for i in scored if i['seo'].score < 55)
    redirects = RedirectRule.query.count()
    notfound = NotFoundLog.query.count()
    return render_template('admin/seo/dashboard.html', items=items,
                           total=len(items), with_seo=len(with_seo),
                           avg=avg, great=great, good=good, bad=bad,
                           redirects=redirects, notfound=notfound)


@seo_bp.route('/analyze/<path:path>')
def analyze(path):
    """تحلیل زنده یک صفحه (با مسیر رمزگذاری‌شده)"""
    r = _admin_required()
    if r:
        return r
    from seo_analyzer import analyze_page as ap
    path = '/' + path if not path.startswith('/') else path
    m = SeoMeta.query.filter_by(path=path).first()
    if not m:
        flash('برای این آدرس متای سئو وجود ندارد. اول بسازید.', 'error')
        return redirect(url_for('seo_admin.dashboard'))

    # پیدا کردن محتوای واقعی بر اساس مسیر
    text, html = '', ''
    course = Course.query.filter_by(slug=path.replace('/course/', '')).first()
    post = BlogPost.query.filter_by(slug=path.replace('/blog/', '')).first()
    page = Page.query.filter(Page.slug == path.replace('/page/', '')).first()
    if course:
        text, html = course.title + ' ' + (course.description or '') + ' ' + (course.what_you_learn or ''), \
                     f'<h1>{course.title}</h1><p>{course.subtitle or ""}</p><img src="/static/img/{course.image}" alt="دوره {course.title}">'
    elif post:
        text, html = post.title + ' ' + (post.excerpt or '') + ' ' + (post.body or ''), \
                     f'<h1>{post.title}</h1><p>{post.excerpt or ""}</p>'
    elif page:
        text, html = (page.title or ''), f'<h1>{page.title or ""}</h1>'
        # استخراج متن از ردیف‌ها
        parts = []
        for r in page.rows():
            for col in r.get('cols', []):
                for w in col:
                    for key in ('text', 'content', 'title'):
                        v = (w.get('data') or {}).get(key)
                        if isinstance(v, str):
                            parts.append(v)
        text = (page.title or '') + ' ' + ' '.join(parts)

    result = ap(path, m.title or '', m.description or '', m.keywords or '',
                m.focus_keyword or '', text, html, m.noindex, m.nofollow)
    return render_template('admin/seo/analyze.html', seo=m, result=result, path=path)


@seo_bp.route('/save-score', methods=['POST'])
def save_score():
    r = _admin_required()
    if r:
        return r
    mid = int(request.form.get('mid') or 0)
    score = int(request.form.get('score') or 0)
    grade = request.form.get('grade', '').strip()
    # اعتبارسنجی: فقط مقادیر مجاز ذخیره شوند (جلوگیری از ذخیره داده خراب)
    if grade not in ('great', 'good', 'bad', ''):
        grade = ''
    m = db.session.get(SeoMeta, mid)
    if m:
        m.score = score
        m.score_grade = grade
        db.session.commit()
    return redirect(safe_referrer(url_for('seo_admin.dashboard')))


# ================================================================
# ویرایشگر متا با پیش‌نمایش گوگل (مثل Rank Math)
# ================================================================
@seo_bp.route('/edit/<int:mid>', methods=['GET', 'POST'])
def edit(mid):
    r = _admin_required()
    if r:
        return r
    m = db.get_or_404(SeoMeta, mid)
    if request.method == 'POST':
        m.title = request.form.get('title', '').strip()
        m.description = request.form.get('description', '').strip()
        m.keywords = request.form.get('keywords', '').strip()
        m.focus_keyword = request.form.get('focus_keyword', '').strip()
        m.canonical = request.form.get('canonical', '').strip()
        m.noindex = bool(request.form.get('noindex'))
        m.nofollow = bool(request.form.get('nofollow'))
        m.og_image = request.form.get('og_image', '').strip()
        m.og_title = request.form.get('og_title', '').strip()
        m.og_desc = request.form.get('og_desc', '').strip()
        db.session.commit()
        flash('متا ذخیره شد ✅', 'success')
        return redirect(url_for('seo_admin.edit', mid=m.id))
    return render_template('admin/seo/edit.html', seo=m)


# ================================================================
# ریدایرکت‌های 301
# ================================================================
@seo_bp.route('/redirects', methods=['GET', 'POST'])
def redirects():
    r = _admin_required()
    if r:
        return r
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            source = request.form.get('source', '').strip()
            target = request.form.get('target', '').strip()
            if source and target:
                if not source.startswith('/'):
                    source = '/' + source
                if RedirectRule.query.filter_by(source=source).first():
                    flash('این مسیر قبلاً ثبت شده است.', 'error')
                else:
                    db.session.add(RedirectRule(source=source, target=target,
                                                code=int(request.form.get('code', 301) or 301)))
                    db.session.commit()
                    flash('ریدایرکت اضافه شد ✅', 'success')
            else:
                flash('مسیر مبدأ و مقصد الزامی است.', 'error')
        elif action == 'delete':
            rr = db.session.get(RedirectRule, int(request.form.get('rid') or 0))
            if rr:
                db.session.delete(rr)
                db.session.commit()
                flash('ریدایرکت حذف شد.', 'info')
        elif action == 'toggle':
            rr = db.session.get(RedirectRule, int(request.form.get('rid') or 0))
            if rr:
                rr.is_active = not rr.is_active
                db.session.commit()
        return redirect(url_for('seo_admin.redirects'))
    all_rules = RedirectRule.query.order_by(RedirectRule.source).all()
    return render_template('admin/seo/redirects.html', rules=all_rules)


# ================================================================
# مانیتور 404
# ================================================================
@seo_bp.route('/notfound')
def notfound():
    r = _admin_required()
    if r:
        return r
    logs = NotFoundLog.query.order_by(NotFoundLog.count.desc()).limit(100).all()
    return render_template('admin/seo/notfound.html', logs=logs)


@seo_bp.route('/notfound/clear', methods=['POST'])
def notfound_clear():
    r = _admin_required()
    if r:
        return r
    NotFoundLog.query.delete()
    db.session.commit()
    flash('لاگ‌های 404 پاک شد.', 'info')
    return redirect(url_for('seo_admin.notfound'))


# ================================================================
# ویرایش انبوه
# ================================================================
@seo_bp.route('/bulk', methods=['GET', 'POST'])
def bulk():
    r = _admin_required()
    if r:
        return r
    if request.method == 'POST':
        # ذخیره انبوه — هر ردیف: mid_title, mid_desc, mid_kw, mid_focus
        saved = 0
        for key, val in request.form.items():
            mm = re.match(r'^f_(\d+)_(title|desc|kw|focus)$', key)
            if mm:
                mid, field = int(mm.group(1)), mm.group(2)
                m = db.session.get(SeoMeta, mid)
                if m:
                    if field == 'title':
                        m.title = val.strip()
                    elif field == 'desc':
                        m.description = val.strip()
                    elif field == 'kw':
                        m.keywords = val.strip()
                    elif field == 'focus':
                        m.focus_keyword = val.strip()
                    saved += 1
        db.session.commit()
        flash(f'{saved} فیلد ذخیره شد ✅', 'success')
        return redirect(url_for('seo_admin.bulk'))
    metas = SeoMeta.query.order_by(SeoMeta.path).all()
    return render_template('admin/seo/bulk.html', metas=metas)


# ================================================================
# ساخت خودکار متا (تکمیل‌شده با کلمه کلیدی)
# ================================================================
@seo_bp.route('/auto-generate', methods=['POST'])
def auto_generate():
    r = _admin_required()
    if r:
        return r
    from seo_analyzer import fa_words
    site_name = db.session.get(Setting, 'site_name')
    sn = site_name.value if site_name else 'آکادمی آنلاین'
    created = updated = 0
    # دوره‌ها
    for c in Course.query.filter_by(status='published').all():
        m = SeoMeta.query.filter_by(path='/course/' + c.slug).first()
        if not m:
            m = SeoMeta(path='/course/' + c.slug)
            db.session.add(m)
            created += 1
        if not m.title:
            m.title = f'{c.title} | {sn}'
        if not m.description:
            m.description = (c.subtitle or c.description or '')[:160]
        if not m.focus_keyword:
            # کلمه کلیدی از عنوان: اولین کلمه مهم
            words = [w for w in (c.title or '').split() if len(w) > 2][:2]
            m.focus_keyword = ' '.join(words)
        if not m.og_image:
            m.og_image = c.image
        updated += 1
    # مقالات
    for p in BlogPost.query.filter_by(published=True).all():
        m = SeoMeta.query.filter_by(path='/blog/' + p.slug).first()
        if not m:
            m = SeoMeta(path='/blog/' + p.slug)
            db.session.add(m)
            created += 1
        if not m.title:
            m.title = f'{p.title} | {sn}'
        if not m.description:
            m.description = (p.excerpt or '')[:160]
        if not m.focus_keyword:
            words = [w for w in (p.title or '').split() if len(w) > 2][:2]
            m.focus_keyword = ' '.join(words)
        updated += 1
    db.session.commit()
    flash(f'متاها ساخته/تکمیل شد: {created} جدید، {updated} بررسی شد ✅', 'success')
    return redirect(url_for('seo_admin.dashboard'))
