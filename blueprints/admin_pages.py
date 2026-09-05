# -*- coding: utf-8 -*-
"""دامنهٔ صفحه‌ها — صفحات صفحه‌ساز، فرم‌ساز و منوها.

جداشده از ``admin_content.py`` که به ۹۲۶ خط و ۴۷ route رسیده بود — همان
مشکلی که تقسیم ``admin_bp.py`` حل کرده بود، در یک‌سوم مقیاس.
"""
from __future__ import annotations

import json
import uuid

from datetime import datetime
from flask import (render_template, request, redirect, url_for, flash, Response)
from admin_core import (
    admin_bp, admin_required, commit, form, go_referrer, slugify
)
from models import (
    CustomForm, CustomFormEntry, Menu, MenuItem, Page, PageRevision, SeoMeta, Setting,
    db
)
from admin_queries import form_entry_counts
from validators import (csv_cell, log_exc as _lexc)
from jdates import (jdate_num, jtime)


@admin_bp.route('/pages')
@admin_required
def pages():
    """لیست تمام صفحات + مدیریت (کپی/حذف موقت/بازیابی/نسخه‌ها)"""
    from models import Page, PageRevision
    items = Page.query.order_by(Page.ptype, Page.updated_at.desc()).all()
    types = {'home': 'صفحه اصلی', 'header': 'هدر', 'footer': 'فوتر',
             'footer_mobile': 'فوتر موبایل', 'mobile_menu': 'منوی موبایل',
             'page': 'صفحه', '404': 'خطای ۴۰۴', 'post': 'قالب مقاله',
             'course': 'قالب دوره', 'teacher': 'قالب مدرس'}
    return render_template('admin/pages.html', pages=items, types=types,
                           rev_count={p.id: PageRevision.query.filter_by(page_id=p.id).count() for p in items})


@admin_bp.route('/pages/<int:pid>/copy', methods=['POST'])
@admin_required
def page_copy(pid):
    """کپی گرفتن از صفحه"""
    from models import Page
    p = db.get_or_404(Page, pid)
    import uuid
    np = Page(title=p.title + ' (کپی)', slug=p.slug + '-copy-' + uuid.uuid4().hex[:4],
              ptype='page', content=p.content, is_published=False)
    db.session.add(np)
    commit(success='کپی صفحه ساخته شد (پیش\u200cنویس). ✂️')
    return redirect(url_for('admin.pages'))


@admin_bp.route('/pages/<int:pid>/toggle', methods=['POST'])
@admin_required
def page_toggle(pid):
    """انتشار / پیش‌نویس"""
    from models import Page
    p = db.get_or_404(Page, pid)
    p.is_published = not p.is_published
    commit(success='وضعیت انتشار تغییر کرد.', category='info')
    return go_referrer('admin.pages')


@admin_bp.route('/pages/<int:pid>/delete', methods=['POST'])
@admin_required
def page_delete(pid):
    """حذف موقت (فقط از فهرست — قابل بازیابی در بازیابی‌ها)"""
    from models import Page
    p = db.get_or_404(Page, pid)
    p.ptype = 'trash'
    p.is_published = False
    commit(success='صفحه به سطل زباله منتقل شد (قابل بازیابی). 🗑', category='info')
    return redirect(url_for('admin.pages'))


@admin_bp.route('/pages/trash')
@admin_required
def pages_trash():
    """صفحات حذف‌شده موقت — بازیابی"""
    from models import Page
    items = Page.query.filter_by(ptype='trash').all()
    return render_template('admin/pages_trash.html', pages=items)


@admin_bp.route('/pages/<int:pid>/restore', methods=['POST'])
@admin_required
def page_restore(pid):
    from models import Page
    p = db.get_or_404(Page, pid)
    p.ptype = 'page'
    commit(success='صفحه بازیابی شد. ♻️')
    return redirect(url_for('admin.pages'))


@admin_bp.route('/pages/<int:pid>/custom-theme', methods=['POST'])
@admin_required
def page_custom_theme(pid):
    """تعیین هدر/فوتر اختصاصی برای صفحه"""
    from models import Page
    p = db.get_or_404(Page, pid)
    p.custom_header = request.form.get('custom_header', '').strip() or None
    p.custom_footer = request.form.get('custom_footer', '').strip() or None
    commit(success='هدر/فوتر اختصاصی صفحه ذخیره شد. 🎨')
    return redirect(url_for('admin.pages'))


@admin_bp.route('/pages/<int:pid>/schedule', methods=['POST'])
@admin_required
def page_schedule(pid):
    """زمان‌بندی انتشار صفحه"""
    from models import Page
    from datetime import datetime as _dt
    p = db.get_or_404(Page, pid)
    raw = request.form.get('publish_at', '').strip()
    if raw:
        try:
            from app import jalali_to_gregorian
            _parts = raw.strip().split()
            _date_part = _parts[0] if _parts else ''
            _time_part = _parts[1] if len(_parts) > 1 else '00:00'
            _g = jalali_to_gregorian(_date_part)
            if not _g:
                raise ValueError('bad date')
            p.publish_at = _dt.strptime(_g + ' ' + _time_part, '%Y-%m-%d %H:%M')
            p.is_published = False
            flash(f'انتشار برای {raw} زمان‌بندی شد. 🕐', 'success')
        except Exception:
            flash('فرمت تاریخ نادرست است — از تقویم شمسی استفاده کنید (مثال: ۱۴۰۵/۰۵/۱۵ ۱۴:۳۰).', 'error')
    else:
        p.publish_at = None
        p.is_published = True
        flash('صفحه فوراً منتشر شد.', 'success')
    commit(context='admin.page_schedule')
    return redirect(url_for('admin.pages'))


@admin_bp.route('/pages/<int:pid>/seo', methods=['GET', 'POST'])
@admin_required
def page_seo(pid):
    """SEO هر صفحه"""
    from models import Page, SeoMeta
    p = db.get_or_404(Page, pid)
    meta = SeoMeta.query.filter_by(path='/page/' + p.slug).first()
    if request.method == 'POST':
        if not meta:
            meta = SeoMeta(path='/page/' + p.slug)
            db.session.add(meta)
        meta.title = request.form.get('title', '').strip()
        meta.description = request.form.get('description', '').strip()
        meta.focus_keyword = request.form.get('focus_keyword', '').strip()
        meta.noindex = bool(request.form.get('noindex'))
        commit(success='SEO صفحه ذخیره شد. ✅')
        return redirect(url_for('admin.pages'))
    return render_template('admin/page_seo.html', page=p, meta=meta)


@admin_bp.route('/pages/<int:pid>/revisions')
@admin_required
def page_revisions(pid):
    """تاریخچه نسخه‌های صفحه"""
    from models import Page, PageRevision
    p = db.get_or_404(Page, pid)
    revs = PageRevision.query.filter_by(page_id=pid) \
        .order_by(PageRevision.created_at.desc()).all()
    return render_template('admin/page_revisions.html', page=p, revs=revs)


@admin_bp.route('/pages/revisions/<int:rid>/restore', methods=['POST'])
@admin_required
def page_revision_restore(rid):
    from models import PageRevision
    rev = db.get_or_404(PageRevision, rid)
    p = rev.page
    p.content = rev.content
    commit(success='نسخه قبلی صفحه بازیابی شد. ↩️')
    return redirect(url_for('builder.editor', slug=p.slug))



# ================================================================
# فرم‌ساز حرفه‌ای
# ================================================================


@admin_bp.route('/forms')
@admin_required
def forms():
    items = CustomForm.query.order_by(CustomForm.created_at.desc()).all()
    # یک GROUP BY به‌جای یک COUNT به‌ازای هر فرم (الگوی N+1 قبلی).
    return render_template('admin/forms.html', forms=items,
                           counts=form_entry_counts(items))


@admin_bp.route('/forms/new', methods=['GET', 'POST'])
@admin_required
def form_new():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('عنوان الزامی است.', 'error')
        else:
            slug = slugify(title) or 'form'
            while CustomForm.query.filter_by(slug=slug).first():
                slug += '-2'
            fields = _parse_form_fields(request.form.get('fields_raw', ''))
            f = CustomForm(title=title, slug=slug,
                           description=request.form.get('description', '').strip(),
                           fields=json.dumps(fields, ensure_ascii=False),
                           notify_sms=bool(request.form.get('notify_sms')),
                           notify_messenger=request.form.get('notify_messenger', ''),
                           success_msg=request.form.get('success_msg', 'ثبت شد ✅').strip() or 'ثبت شد ✅')
            db.session.add(f)
            commit(success='فرم ساخته شد. لینک: /form/' + slug)
            return redirect(url_for('admin.forms'))
    return render_template('admin/form_builder.html', form=None)


@admin_bp.route('/forms/<int:pid>/edit', methods=['GET', 'POST'])
@admin_required
def form_edit(pid):
    f = db.get_or_404(CustomForm, pid)
    if request.method == 'POST':
        f.title = request.form.get('title', f.title).strip()
        f.description = request.form.get('description', '').strip()
        f.fields = json.dumps(_parse_form_fields(request.form.get('fields_raw', '')),
                              ensure_ascii=False)
        f.notify_sms = bool(request.form.get('notify_sms'))
        f.notify_messenger = request.form.get('notify_messenger', '')
        f.success_msg = request.form.get('success_msg', 'ثبت شد ✅').strip()
        commit(success='فرم به\u200cروزرسانی شد.')
        return redirect(url_for('admin.forms'))
    raw = '\n'.join(_field_to_line(x) for x in f.fields_list())
    return render_template('admin/form_builder.html', form=f, raw=raw)


@admin_bp.route('/forms/<int:pid>/entries')
@admin_required
def form_entries(pid):
    f = db.get_or_404(CustomForm, pid)
    entries = CustomFormEntry.query.filter_by(form_id=pid) \
        .order_by(CustomFormEntry.created_at.desc()).all()
    return render_template('admin/form_entries.html', form=f, entries=entries)


@admin_bp.route('/forms/<int:pid>/entries/export')
@admin_required
def form_entries_export(pid):
    """خروجی اکسل (CSV) پاسخ‌های فرم"""
    import csv, io
    from flask import Response
    f = db.get_or_404(CustomForm, pid)
    entries = CustomFormEntry.query.filter_by(form_id=pid) \
        .order_by(CustomFormEntry.created_at.desc()).all()
    labels = [x['label'] for x in f.fields_list()]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['#', 'زمان'] + labels)
    from validators import csv_cell
    for i, e in enumerate(entries, 1):
        data = {}
        try:
            data = json.loads(e.data or '{}')
        except Exception:
            _lexc('blueprints/admin_bp.py')
        w.writerow([i, jdate_num(e.created_at) + ' ' + jtime(e.created_at)] +
                   [csv_cell(data.get(l, '')) for l in labels])
    out = '\ufeff' + buf.getvalue()  # BOM برای اکسل
    from urllib.parse import quote
    return Response(out, mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote('form-' + f.slug + '.csv')})


@admin_bp.route('/forms/<int:pid>/toggle', methods=['POST'])
@admin_required
def form_toggle(pid):
    f = db.get_or_404(CustomForm, pid)
    f.is_active = not f.is_active
    commit(context='admin.form_toggle')
    return redirect(url_for('admin.forms'))


def _parse_form_fields(raw):
    """هر خط: برچسب | نوع | الزامی(1/0) | گزینه‌ها(با - جدا)"""
    fields = []
    for line in (raw or '').split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split('|')]
        if not parts[0]:
            continue
        fields.append({
            'label': parts[0],
            'type': parts[1] if len(parts) > 1 and parts[1] in (
                'text', 'phone', 'email', 'textarea', 'select', 'radio',
                'checkbox', 'file', 'date') else 'text',
            'required': len(parts) > 2 and parts[2] == '1',
            'options': parts[3].split('-') if len(parts) > 3 and parts[3] else [],
        })
    return fields


def _field_to_line(x):
    return '|'.join([x.get('label', ''), x.get('type', 'text'),
                     '1' if x.get('required') else '0',
                     '-'.join(x.get('options', []))])


# ================================================================
# پاسخ‌های آماده تیکت
# ================================================================


@admin_bp.route('/menus')
@admin_required
def menus():
    items = Menu.query.order_by(Menu.created_at.desc()).all()
    return render_template('admin/menus.html', menus=items)


@admin_bp.route('/menus/new', methods=['GET', 'POST'])
@admin_required
def menu_new():
    if request.method == 'GET':
        return redirect(url_for('admin.menus'))
    title = request.form.get('title', '').strip()
    if title:
        slug = slugify(title) or 'menu'
        while Menu.query.filter_by(slug=slug).first():
            slug += '-2'
        db.session.add(Menu(title=title, slug=slug,
                            location=request.form.get('location', 'main'),
                            is_active=bool(request.form.get('is_active'))))
        commit(success='منو ساخته شد.')
    return redirect(url_for('admin.menus'))


@admin_bp.route('/menus/<int:mid>', methods=['GET', 'POST'])
@admin_required
def menu_edit(mid):
    m = db.get_or_404(Menu, mid)
    if request.method == 'POST':
        m.title = request.form.get('title', m.title).strip()
        m.location = request.form.get('location', m.location)
        m.is_active = bool(request.form.get('is_active'))
        # آیتم‌ها: خط = برچسب|آدرس|آیکون|نقش‌ها|شماره خط والد (۱-پایه)
        raw = request.form.get('items_raw', '')
        for old in list(m.items):
            db.session.delete(old)
        db.session.flush()
        created = []
        for i, line in enumerate(raw.splitlines()):
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split('|')]
            parent_idx = int(parts[4]) - 1 if len(parts) > 4 and parts[4].isdigit() else -1
            parent = created[parent_idx] if 0 <= parent_idx < len(created) else None
            item = MenuItem(menu_id=m.id, label=parts[0],
                            url=parts[1] if len(parts) > 1 and parts[1] else '#',
                            icon=parts[2] if len(parts) > 2 else '',
                            roles=parts[3] if len(parts) > 3 else '',
                            parent_id=parent.id if parent else None,
                            sort=i)
            db.session.add(item)
            db.session.flush()  # ست شدن id برای زیرمنو
            created.append(item)
        commit(success='منو به\u200cروزرسانی شد.')
        return redirect(url_for('admin.menus'))
    ordered = sorted(m.items, key=lambda it: it.sort or 0)
    idx_of = {it.id: n + 1 for n, it in enumerate(ordered)}
    items = [dict(label=it.label, url=it.url, icon=it.icon, roles=it.roles,
                   parent_idx=idx_of.get(it.parent_id, '')) for it in ordered]
    return render_template('admin/menu_edit.html', m=m, items=items)


@admin_bp.route('/menus/<int:mid>/toggle', methods=['POST'])
@admin_required
def menu_toggle(mid):
    m = db.get_or_404(Menu, mid)
    m.is_active = not m.is_active
    commit(context='admin.menu_toggle')
    return redirect(url_for('admin.menus'))


@admin_bp.route('/menus/<int:mid>/delete', methods=['POST'])
@admin_required
def menu_delete(mid):
    m = db.get_or_404(Menu, mid)
    db.session.delete(m)
    commit(success='منو حذف شد.', category='info')
    return redirect(url_for('admin.menus'))


# ================================================================
# مدیریت کاربر تکمیلی: پروفایل کامل، ریست رمز، افزودن، ارسال اعلان
# ================================================================


@admin_bp.route('/pages-content', methods=['GET', 'POST'])
@admin_required
def pages_content():
    """ویرایش متن درباره ما و مقدمه تماس — مثل FAQ."""
    keys = ('about_text', 'contact_intro')
    if request.method == 'POST':
        for key in keys:
            value = (request.form.get(key) or '').strip()[:8000]
            row = db.session.get(Setting, key)
            if row:
                row.value = value
            else:
                db.session.add(Setting(key=key, value=value))
        commit(success='متن صفحات درباره ما و تماس ذخیره شد.')
        return redirect(url_for('admin.pages_content'))
    vals = {k: ((db.session.get(Setting, k).value if db.session.get(Setting, k) else '') or '')
            for k in keys}
    return render_template('admin/pages_content.html', vals=vals)


import blueprints.admin_extra  # noqa: F401  (side-effect: رجیستر routeها)
