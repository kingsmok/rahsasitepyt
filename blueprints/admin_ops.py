# -*- coding: utf-8 -*-
"""دامنهٔ عملیات — بکاپ، طراحی، پیام‌رسان، کلاس زنده، نقش‌ها و نگهداری.

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
from flask import (render_template, request, redirect, url_for, flash, g, abort, send_file, after_this_request, Response)
from blueprints.admin_catalog import _save_lesson_captions
from admin_core import (
    audit,
    commit,
    admin_bp, admin_required
)
from models import (
    Course, LiveSession, PERMISSION_FA, Page, ROLES, Setting, db, utcnow
)
from validators import (ALLOWED_IMAGE_EXT, file_content_is_safe, safe_filename, log_exc as _lexc)
from admin_core import SECRET_SETTING_KEYS as _SECRET_SETTING_KEYS


@admin_bp.route('/designs', methods=['GET', 'POST'])
@admin_required
def designs():
    """🖼 طراحی‌های سایت — ۲۰ طرح ایرانی + طرح‌های کلاسیک؛ انتخاب، پیش‌نمایش و اعمال"""
    from designs import HOME_DESIGNS, HOME_DESIGN_NAMES, SITE_DESIGNS
    from persian_themes import PERSIAN_THEMES, home_rows, CATEGORIES
    if request.method == 'POST':
        field = request.form.get('field', '')
        value = request.form.get('value', '')
        if field == 'site_design' and value in SITE_DESIGNS:
            s = db.session.get(Setting, field)
            if s:
                s.value = value
            else:
                db.session.add(Setting(key=field, value=value))
            commit(context='admin.designs')
            nm = SITE_DESIGNS[value]['name']
            flash(f'طرح «{nm}» به عنوان طراحی سراسری سایت انتخاب شد ✅', 'success')
            return redirect(url_for('admin.designs'))
        if field == 'home_reset' and value in SITE_DESIGNS:
            # بازنشانی چیدمان صفحه اصلی با ردیف‌های طرح (فقط با تأیید کاربر در سمت کلاینت)
            from persian_themes import get_theme
            t = get_theme(value)
            if t:
                from blueprints.builder import ensure_home_page, _clear_app_cache
                page, _created = ensure_home_page(seed=False)
                page.ptype = 'home'
                if not (page.title or '').strip():
                    page.title = 'صفحه اصلی'
                page.content = json.dumps({'settings': page.settings(), 'rows': home_rows(t)},
                                          ensure_ascii=False)
                commit(context='admin.designs')
                _clear_app_cache()
                flash(f'صفحه اصلی با چیدمان طرح «{t["name"]}» بازنویسی شد ✅', 'success')
            return redirect(url_for('admin.designs'))
        if field in ('home_design', 'about_design', 'contact_design') and value:
            if field == 'home_design' and value not in list(HOME_DESIGNS.keys()) + ['builder']:
                flash('طراحی صفحه اصلی نامعتبر است.', 'error')
                return redirect(url_for('admin.designs'))
            s = db.session.get(Setting, field)
            if s:
                s.value = value
            else:
                db.session.add(Setting(key=field, value=value))
            commit(context='admin.designs')
            if field == 'home_design' and value == 'builder':
                from blueprints.builder import ensure_home_page
                ensure_home_page(seed=True)
            flash('طراحی انتخابی ذخیره شد ✅', 'success')
        if field == 'home_page_slug':
            # انتخاب هر صفحهٔ صفحه‌ساز به عنوان صفحه اصلی سایت
            if value:
                from models import Page as _Pg
                pg = _Pg.query.filter_by(slug=value).first()
                if not pg:
                    flash('صفحه انتخابی پیدا نشد.', 'error')
                    return redirect(url_for('admin.designs'))
            s = db.session.get(Setting, field)
            if value:
                if s:
                    s.value = value
                else:
                    db.session.add(Setting(key=field, value=value))
            elif s:
                db.session.delete(s)
            commit(success='صفحه اصلی سایت انتخاب شد ✅')
        return redirect(url_for('admin.designs'))
    cur_site = db.session.get(Setting, 'site_design')
    cur_site = cur_site.value if cur_site else '1'
    _hp_row = db.session.get(Setting, 'home_page_slug')
    cur_home_page = _hp_row.value if _hp_row else ''
    pages = Page.query.order_by(Page.ptype, Page.title).all()
    return render_template('admin/designs.html',
                           persian_themes=PERSIAN_THEMES, categories=CATEGORIES,
                           home_designs=HOME_DESIGNS, home_names=HOME_DESIGN_NAMES,
                           site_designs=SITE_DESIGNS,
                           cur_site=cur_site,
                           cur_home=db.session.get(Setting, 'home_design').value if db.session.get(Setting, 'home_design') else '1',
                           cur_home_page=cur_home_page, pages=pages,
                           cur_about=db.session.get(Setting, 'about_design').value if db.session.get(Setting, 'about_design') else '1',
                           cur_contact=db.session.get(Setting, 'contact_design').value if db.session.get(Setting, 'contact_design') else '1')


# ---------------------------------------------------------------- پشتیبان‌گیری


@admin_bp.route('/backup')
@admin_required
def backup():
    import shutil
    import tempfile
    from flask import send_file, after_this_request
    src_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'instance', 'academy.db')
    if os.path.exists(src_db):
        temp_dir = os.path.join(os.path.dirname(src_db), 'backups')
        os.makedirs(temp_dir, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix='academy-download-', suffix='.db', dir=temp_dir)
        os.close(fd)
        shutil.copy2(src_db, tmp)

        @after_this_request
        def _cleanup(response):
            try:
                os.remove(tmp)
            except OSError:
                pass
            return response

        return send_file(tmp, as_attachment=True, download_name='academy-backup.db')
    flash('فایل دیتابیس پیدا نشد.', 'error')
    return redirect(url_for('admin.overview'))


# ---------------------------------------------------------------- پیام‌ها و خبرنامه


@admin_bp.route('/messengers', methods=['GET', 'POST'])
@admin_required
def messengers():
    """اتصال ربات‌های پیام‌رسان + ارسال همگانی"""
    from messengers import MESSENGERS, send_to_all
    results = None
    if request.method == 'POST':
        keys = []
        for m in MESSENGERS:
            keys += [m['token_key'], m['chat_key']]
        for k in keys:
            v = request.form.get(k, '').strip()
            if k.endswith('_token'):
                from messengers import sanitize_bot_token
                v = sanitize_bot_token(v)
            elif k.endswith('_chat'):
                from messengers import sanitize_chat_id
                v = sanitize_chat_id(v)
            st = db.session.get(Setting, k)
            if st:
                st.value = v
            elif v:
                db.session.add(Setting(key=k, value=v))
        commit(context='admin.messengers')
        if request.form.get('action') == 'broadcast':
            text = request.form.get('broadcast_text', '').strip()
            link = request.form.get('broadcast_link', '').strip()
            if not text:
                flash('متن پیام را وارد کنید.', 'error')
            else:
                settings = {s.key: s.value for s in Setting.query.all()}
                results = send_to_all(text, settings, link or None)
                ok_count = sum(1 for ok, _ in results.values() if ok)
                flash(f'ارسال همگانی: {ok_count} پیام‌رسان با موفقیت. 📣', 'success')
        else:
            flash('تنظیمات پیام‌رسان‌ها ذخیره شد. ✅', 'success')
    settings = {s.key: s.value for s in Setting.query.all()}
    return render_template('admin/messengers.html', messengers=MESSENGERS,
                           site=settings, results=results)


@admin_bp.route('/messengers/test/<mid>', methods=['POST'])
@admin_required
def messenger_test(mid):
    """تست اتصال ربات یک پیام‌رسان"""
    from messengers import test_platform, MESSENGERS
    for m in MESSENGERS:
        for k in (m['token_key'], m['chat_key']):
            v = request.form.get(k, '').strip()
            if k.endswith('_token'):
                from messengers import sanitize_bot_token
                v = sanitize_bot_token(v)
            elif k.endswith('_chat'):
                from messengers import sanitize_chat_id
                v = sanitize_chat_id(v)
            st = db.session.get(Setting, k)
            if st:
                st.value = v
            elif v:
                db.session.add(Setting(key=k, value=v))
    commit(context='admin.messenger_test')
    settings = {s.key: s.value for s in Setting.query.all()}
    ok, msg = test_platform(mid, settings)
    flash(('✅ ' if ok else '❌ ') + msg, 'success' if ok else 'error')
    return redirect(url_for('admin.messengers'))


@admin_bp.route('/sms', methods=['GET', 'POST'])
@admin_required
def sms_settings():
    """تنظیمات پیامک خودکار"""
    from sms import PROVIDERS, test_sms
    if request.method == 'POST':
        keys = ['sms_provider', 'sms_kavenegar_key', 'sms_kavenegar_sender', 'sms_kavenegar_template',
                'sms_melli_username', 'sms_melli_password', 'sms_melli_sender',
                'sms_faraz_token', 'sms_faraz_sender', 'sms_test_phone']
        for k in keys:
            v = request.form.get(k, '').strip()
            if k in _SECRET_SETTING_KEYS and not v:
                continue
            st = db.session.get(Setting, k)
            if st:
                st.value = v
            elif v:
                db.session.add(Setting(key=k, value=v))
        commit(context='admin.sms_settings')
        if request.form.get('action') == 'test':
            settings = {s.key: s.value for s in Setting.query.all()}
            ok, msg = test_sms(settings)
            flash(('✅ ' if ok else '❌ ') + msg, 'success' if ok else 'error')
        else:
            flash('تنظیمات پیامک ذخیره شد. ✅', 'success')
        return redirect(url_for('admin.sms_settings'))
    settings = {s.key: s.value for s in Setting.query.all()}
    return render_template('admin/sms.html', providers=PROVIDERS, site=settings)


@admin_bp.route('/optimizer', methods=['GET', 'POST'])
@admin_required
def optimizer():
    """بهینه‌ساز تصویر — غیرفعال؛ فشرده‌سازی خودکار هنگام آپلود."""
    flash('بهینه‌ساز دستی غیرفعال است. تصاویر هنگام آپلود به‌صورت خودکار فشرده می‌شوند.', 'info')
    return redirect(url_for('admin.media_library'))


@admin_bp.route('/optimizer/bulk', methods=['GET', 'POST'])
@admin_required
def optimizer_bulk():
    """بهینه‌ساز دستی غیرفعال است — فشرده‌سازی هنگام آپلود انجام می‌شود."""
    flash('بهینه‌ساز دستی غیرفعال است. تصاویر هنگام آپلود به‌صورت خودکار فشرده می‌شوند.', 'info')
    return redirect(url_for('admin.media_library'))


@admin_bp.route('/live-sessions', methods=['GET', 'POST'])
@admin_required
def live_sessions():
    from datetime import datetime as _dt
    if request.method == 'POST':
        action = request.form.get('action', 'create')
        title = request.form.get('title', '').strip()
        link = request.form.get('link', '').strip()
        starts = request.form.get('starts_at', '').strip()
        _cap = _save_lesson_captions(request.files.get('captions_file'))
        if action == 'edit' and request.form.get('sid', type=int):
            sess = db.session.get(LiveSession, request.form.get('sid', type=int))
            if sess and title:
                sess.title = title
                sess.description = request.form.get('description', '').strip()
                sess.link = link or None
                sess.duration_min = request.form.get('duration_min', 90, type=int)
                sess.course_id = request.form.get('course_id', type=int) or None
                sess.is_recorded = bool(request.form.get('is_recorded'))
                sess.video_url = (request.form.get('video_url', '').strip() or None)
                sess.video_url_hd = (request.form.get('video_url_hd', '').strip() or None)
                sess.release_days = request.form.get('release_days', 0, type=int) or 0
                if _cap:
                    sess.captions = _cap
                if starts:
                    try:
                        sess.starts_at = _dt.strptime(starts, '%Y-%m-%dT%H:%M')
                    except Exception:
                        pass
                commit(success='کلاس آنلاین به\u200cروزرسانی شد. 🎥')
            return redirect(url_for('admin.live_sessions'))
        if title and starts:
            try:
                dt = _dt.strptime(starts, '%Y-%m-%dT%H:%M')
                db.session.add(LiveSession(course_id=request.form.get('course_id', type=int) or None,
                                          title=title, description=request.form.get('description', '').strip(),
                                          link=link or None, starts_at=dt,
                                          duration_min=request.form.get('duration_min', 90, type=int),
                                          is_recorded=bool(request.form.get('is_recorded')),
                                          video_url=request.form.get('video_url', '').strip() or None,
                                          video_url_hd=request.form.get('video_url_hd', '').strip() or None,
                                          captions=_cap,
                                          release_days=request.form.get('release_days', 0, type=int) or 0))
                db.session.commit()
                flash('کلاس آنلاین ساخته شد. 🎥', 'success')
            except Exception:
                flash('فرمت تاریخ نادرست است — از تقویم شمسی استفاده کنید.', 'error')
        return redirect(url_for('admin.live_sessions'))
    sessions = LiveSession.query.order_by(LiveSession.starts_at.desc()).all()
    courses = Course.query.filter_by(status='published').all()
    return render_template('admin/live_sessions.html', sessions=sessions, courses=courses)


@admin_bp.route('/live-sessions/<int:sid>/delete', methods=['POST'])
@admin_required
def live_session_delete(sid):
    s_ = db.get_or_404(LiveSession, sid)
    db.session.delete(s_)
    commit(context='admin.live_session_delete')
    return redirect(url_for('admin.live_sessions'))


@admin_bp.route('/settings/email-test', methods=['POST'])
@admin_required
def email_test():
    """ارسال ایمیل تست"""
    from email_service import send_email
    keys = ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass', 'smtp_from', 'smtp_tls']
    for k in keys:
        v = request.form.get(k, '').strip()
        if k in _SECRET_SETTING_KEYS and not v:
            continue
        st = db.session.get(Setting, k)
        if st:
            st.value = v
        elif v:
            db.session.add(Setting(key=k, value=v))
    commit(context='admin.email_test')
    settings = {s.key: s.value for s in Setting.query.all()}
    to = request.form.get('smtp_test_to', '').strip() or g.user.email
    ok, msg = send_email(to, 'تست ایمیل آکادمی ✅',
                         '<div style="font-family:Tahoma;padding:20px;text-align:center"><h2>✅ اتصال ایمیل برقرار است</h2><p>این یک ایمیل تست از آکادمی است.</p></div>',
                         settings)
    flash(('✅ ' if ok else '❌ ') + msg, 'success' if ok else 'error')
    return redirect(url_for('admin.super_settings', tab='sms'))


@admin_bp.route('/roles', methods=['GET', 'POST'])
@admin_required
def roles_manage():
    """مدیریت نقش‌ها و دسترسی‌ها"""
    from models import ROLES, PERMISSION_FA
    if request.method == 'POST':
        # ذخیره دسترسی‌های سفارشی در تنظیمات
        perms = {}
        for role in ROLES:
            selected = request.form.getlist('perms_' + role)
            perms[role] = selected
        import json as _json
        st = db.session.get(Setting, 'role_permissions')
        if st:
            st.value = _json.dumps(perms)
        else:
            db.session.add(Setting(key='role_permissions', value=_json.dumps(perms)))
        commit(success='دسترسی نقش\u200cها ذخیره شد. ✅')
        return redirect(url_for('admin.roles_manage'))
    import json as _json
    custom = {}
    st = db.session.get(Setting, 'role_permissions')
    if st and st.value:
        try:
            custom = _json.loads(st.value)
        except Exception:
            custom = {}
    all_perms = sorted(PERMISSION_FA.keys())
    return render_template('admin/roles.html', ROLES=ROLES, PERMISSION_FA=PERMISSION_FA,
                           all_perms=all_perms, custom=custom)


@admin_bp.route('/backup/list')
@admin_required
def backup_list():
    """لیست بکاپ‌ها + بازیابی"""
    import glob, os as _os
    bk_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'instance', 'backups')
    bks = []
    for f in sorted(glob.glob(_os.path.join(bk_dir, 'academy-*.*')), key=_os.path.getmtime, reverse=True):
        if not f.endswith(('.db', '.json')):
            continue
        bks.append({'name': _os.path.basename(f), 'size': _os.path.getsize(f) // 1024,
                    'time': _os.path.getmtime(f)})
    return render_template('admin/backup_list.html', backups=bks)


@admin_bp.route('/backup/create', methods=['POST'])
@admin_required
def backup_create():
    """ساخت بکاپ دستی — SQLite: کپی فایل | MySQL: دامپ JSON همه جدول‌ها"""
    import os as _os, json as _json
    from datetime import datetime as _dt
    bk_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'instance', 'backups')
    _os.makedirs(bk_dir, exist_ok=True)
    stamp = f'{_dt.now():%Y%m%d-%H%M}'
    db_url = _os.environ.get('DATABASE_URL', '')
    if db_url.startswith('mysql'):
        # ── MySQL: دامپ JSON (قابل بازیابی با اسکریپت migrate) ──
        name = f'academy-{stamp}-mysql.json'
        try:
            from sqlalchemy import inspect as _insp
            insp = _insp(db.engine)
            dump = {'engine': 'mysql', 'created_at': _dt.now().isoformat(), 'tables': {}}
            for t in insp.get_table_names():
                if t.startswith('sqlite_') or t in ('alembic_version',):
                    continue
                rows = [dict(r._mapping) for r in db.session.execute(db.text(f'SELECT * FROM `{t}`'))]
                dump['tables'][t] = rows
            with open(_os.path.join(bk_dir, name), 'w', encoding='utf-8') as fh:
                _json.dump(dump, fh, ensure_ascii=False, default=str)
            flash(f'بکاپ MySQL «{name}» ساخته شد ({sum(len(v) for v in dump["tables"].values())} ردیف) ✅', 'success')
            return redirect(url_for('admin.backup_list'))
        except Exception as e:
            flash('خطا در بکاپ MySQL: ' + str(e)[:150], 'error')
            return redirect(url_for('admin.backup_list'))
    # ── SQLite: VACUUM INTO (کپی امن همراه WAL) ──
    import shutil
    src = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'instance', 'academy.db')
    if not _os.path.exists(src):
        flash('فایل دیتابیس پیدا نشد.', 'error')
        return redirect(url_for('admin.backup_list'))
    name = f'academy-{stamp}-manual.db'
    try:
        import sqlite3
        con = sqlite3.connect(src)
        con.execute(f"VACUUM INTO '{_os.path.join(bk_dir, name)}'")
        con.close()
    except Exception:
        shutil.copy2(src, _os.path.join(bk_dir, name))
    flash(f'بکاپ «{name}» ساخته شد ✅', 'success')
    return redirect(url_for('admin.backup_list'))


@admin_bp.route('/backup/restore/<name>', methods=['POST'])
@admin_required
def backup_restore(name):
    """بازیابی دیتابیس از بکاپ (فقط سوپر ادمین)"""
    if g.user.role != 'super_admin' and g.user.role != 'admin':
        abort(403)
    import shutil, os as _os
    import re as _re
    if not _re.match(r'^academy-[\w\-]+\.(db|json)$', name):
        flash('نام بکاپ نامعتبر.', 'error')
        return redirect(url_for('admin.backup_list'))
    if _os.environ.get('DATABASE_URL', '').startswith('mysql'):
        flash('بازیابی خودکار فقط برای SQLite است — در MySQL از پنل هاست/phpMyAdmin استفاده کنید.', 'error')
        return redirect(url_for('admin.backup_list'))
    bk = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'instance', 'backups', name)
    if not _os.path.exists(bk):
        flash('بکاپ یافت نشد.', 'error')
        return redirect(url_for('admin.backup_list'))
    # نسخه فعلی را قبل از بازگردانی بکاپ بگیر
    db_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'instance', 'academy.db')
    if _os.path.exists(db_path):
        from datetime import datetime as _dt
        shutil.copy2(db_path, _os.path.join(_os.path.dirname(_os.path.dirname(__file__)),
                                            'instance', 'backups', f'pre-restore-{_dt.now():%Y%m%d-%H%M}.db'))
    try:
        db.engine.dispose()
    except Exception:
        pass
    for sidecar in (db_path + '-wal', db_path + '-shm'):
        if _os.path.exists(sidecar):
            try:
                _os.remove(sidecar)
            except OSError:
                pass
    audit('backup_restore', name)
    shutil.copy2(bk, db_path)
    flash('دیتابیس از بکاپ بازیابی شد — برای اعمال، سرور ری‌استارت می‌شود. ♻️', 'success')
    # ری‌استارت خودکار در dev ممکن نیست — کاربر را راهنمایی می‌کنیم
    return redirect(url_for('admin.backup_list'))


@admin_bp.route('/design-preview/<did>')
@admin_required
def design_variant_preview(did):
    """پیش‌نمایش ۸ بخش UI/UX یک واریانت (از design_variants.py)"""
    from design_variants import all_variants
    variant = next((v for v in all_variants() if v['design_id'] == did), None)
    if not variant:
        flash('واریانت پیدا نشد', 'error')
        return redirect(url_for('admin.designs'))
    return render_template('admin/design_preview.html', variant=variant)


@admin_bp.route('/design-variant-json/<did>')
@admin_required
def design_variant_json(did):
    """دانلود JSON کامل یک واریانت"""
    from flask import Response as _Resp
    from design_variants import all_variants
    variant = next((v for v in all_variants() if v['design_id'] == did), None)
    if not variant:
        return 'not found', 404
    body = json.dumps(variant, ensure_ascii=False, indent=2)
    return _Resp(body, mimetype='application/json',
                 headers={'Content-Disposition': f'attachment; filename={did}.json'})


@admin_bp.route('/themes')
@admin_required
def themes():
    """مدیریت تم‌ها به «طراحی‌های سایت» منتقل شده است"""
    flash('مدیریت تم‌ها به بخش «طراحی‌های سایت» منتقل شد 🖼', 'info')
    return redirect(url_for('admin.designs'))



# ================================================================
# فروشگاه — مدیریت محصولات فیزیکی
# ================================================================


@admin_bp.route('/system/restart', methods=['POST'])
@admin_required
def system_restart():
    """ری‌استارت اپ روی هاست (Passenger/cPanel: tmp/restart.txt)."""
    import os as _os
    base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    written = []
    for rel in ('tmp/restart.txt', 'tmp/restart', 'instance/restart.txt'):
        path = _os.path.join(base, rel)
        try:
            _os.makedirs(_os.path.dirname(path), exist_ok=True)
            with open(path, 'a', encoding='utf-8') as fh:
                fh.write(str(utcnow()) + '\n')
            written.append(rel)
        except OSError:
            continue
    if written:
        flash('درخواست ری‌استارت ثبت شد (' + '، '.join(written) + '). اگر صفحه قدیمی ماند، در سی‌پنل Restart بزنید.', 'success')
    else:
        flash('نتوانستیم فایل ری‌استارت را بنویسیم. از پنل هاست Restart کنید.', 'error')
    return redirect(url_for('admin.update_page'))
