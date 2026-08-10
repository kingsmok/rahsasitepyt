# -*- coding: utf-8 -*-
"""نصب‌کننده وب — مشابه وردپرس (مسیر /install)

قانون طلایی: همه مسیرهای POST این بلوپرینت **همیشه** JSON برمی‌گردانند —
حتی هنگام خطای 500 (با errorhandler) یا ریدایرکت. این یعنی مرورگر هرگز
خطای «JSON.parse» نمی‌گیرد.
"""
import os
import sys
import traceback as _tb

from flask import (Blueprint, render_template, request, redirect, url_for,
                   jsonify, current_app)
from werkzeug.exceptions import HTTPException

from installer import (is_installed, build_db_url, validate_mysql,
                       test_connection, run_install, check_db_health,
                       env_db_url, INSTANCE_DIR, start_background_install,
                       install_progress)

install_bp = Blueprint('install', __name__)


# ────────────────────────────────────────────────────────────
# هر خطای غیرمنتظره در مسیرهای نصب → JSON (نه صفحه HTML 500)
# ────────────────────────────────────────────────────────────
@install_bp.errorhandler(Exception)
def _install_json_error(e):
    try:
        if isinstance(e, HTTPException):
            return jsonify(ok=False, msg=(e.description or 'خطا'),
                           code=getattr(e, 'code', 500)), getattr(e, 'code', 500)
        current_app.logger.error('install error: %s\n%s', e, _tb.format_exc())
    except Exception:
        pass
    return jsonify(ok=False,
                   msg='خطای سرور در نصب: ' + str(e)[:200] +
                       ' — لاگ سرور را ببینید.'), 500


def _already_installed_json():
    """پاسخ JSON وقتی نصب قبلاً انجام شده — ضد دوبار کلیک و درخواست تکراری"""
    return jsonify(ok=True, msg='نصب قبلاً انجام شده است.', redirect='/')


@install_bp.route('/install')
def wizard():
    if is_installed():
        ok, _ = check_db_health()
        if ok:
            return redirect(url_for('site.index'))
        # نصب ناقص (دیتابیس خراب) → صفحه تعمیر — نه ریدایرکت (ضد حلقه)
        return render_template('install/wizard.html')
    return render_template('install/wizard.html')


@install_bp.route('/install/test-db', methods=['POST'])
def test_db():
    """تست اتصال دیتابیس — همیشه JSON"""
    try:
        if is_installed():
            return _already_installed_json()
        d = request.get_json(silent=True) or request.form or {}
        db_type = d.get('db_type', 'sqlite')
        if db_type == 'mysql':
            err = validate_mysql(d.get('host', ''), d.get('name', ''), d.get('user', ''))
            if err:
                return jsonify(ok=False, msg=err)
            url = build_db_url('mysql', d.get('host', ''), d.get('port', ''),
                               d.get('name', ''), d.get('user', ''),
                               d.get('password', ''))
        else:
            url = ''
        ok, msg = test_connection(url)
        return jsonify(ok=ok, msg=msg)
    except Exception as e:
        current_app.logger.error('install test-db error: %s', e)
        return jsonify(ok=False, msg='خطا در تست اتصال: ' + str(e)[:200]), 500


@install_bp.route('/install/run', methods=['POST'])
def run():
    try:
        if is_installed():
            return _already_installed_json()

        d = request.form or {}
        db_type = d.get('db_type', 'sqlite')
        db_url = build_db_url(db_type, d.get('db_host', ''), d.get('db_port', ''),
                              d.get('db_name', ''), d.get('db_user', ''),
                              d.get('db_pass', ''))

        admin = {
            'name': d.get('admin_name', '').strip(),
            'email': d.get('admin_email', '').strip().lower(),
            'password': d.get('admin_pass', ''),
        }
        site = {
            'name': d.get('site_name', '').strip(),
            'desc': d.get('site_desc', '').strip(),
            'phone': d.get('site_phone', '').strip(),
            'email': d.get('site_email', '').strip(),
            'base_url': d.get('site_url', '').strip(),
        }
        create_demo = d.get('demo_student') == '1'

        # اعتبارسنجی
        if not admin['name'] or len(admin['name']) < 3:
            return jsonify(ok=False, msg='نام مدیر حداقل ۳ حرف باشد.'), 400
        if '@' not in admin['email']:
            return jsonify(ok=False, msg='ایمیل مدیر نامعتبر است.'), 400
        if len(admin['password']) < 8:
            return jsonify(ok=False, msg='رمز مدیر حداقل ۸ کاراکتر باشد.'), 400
        if admin['password'] != d.get('admin_pass2', ''):
            return jsonify(ok=False, msg='تکرار رمز مطابقت ندارد.'), 400
        if not site['name']:
            return jsonify(ok=False, msg='نام سایت الزامی است.'), 400
        if db_type == 'mysql':
            err = validate_mysql(d.get('db_host', ''), d.get('db_name', ''), d.get('db_user', ''))
            if err:
                return jsonify(ok=False, msg=err), 400

        # نصب در پس‌زمینه — ضد «Request Timeout» هاست (هر درخواست کوتاه می‌ماند)
        started, s_msg = start_background_install(db_url, admin, site, create_demo)
        if not started:
            return jsonify(ok=False, msg=s_msg), 400

        # لاگین خودکار مدیر (پس از اتمام نصب — از status انجام می‌شود)
        return jsonify(ok=True, started=True, msg='نصب شروع شد — در حال انجام...', redirect=None)
    except Exception as e:
        current_app.logger.error('install run error: %s\n%s', e, _tb.format_exc())
        return jsonify(ok=False, msg='خطا در شروع نصب: ' + str(e)[:250]), 500


def _pkg_version(mod, attr='__version__'):
    """نسخه پکیج یا None — بدون کرش"""
    try:
        m = __import__(mod)
        return str(getattr(m, attr, '?') or '?')
    except Exception:
        return None


@install_bp.route('/install/status')
def status():
    """وضعیت نصب (پیشرفت پس‌زمینه) + سلامت سرور — همیشه JSON و سریع"""
    prog = install_progress()
    info = {
        'installed': is_installed(),
        'repair': request.args.get('repair') == '1',
        'python': sys.version.split()[0],
        'flask': _pkg_version('flask'),
        'flask_sqlalchemy': _pkg_version('flask_sqlalchemy'),
        'sqlalchemy': _pkg_version('sqlalchemy'),
        'pymysql': _pkg_version('pymysql'),
        'pillow': _pkg_version('PIL'),
        'cryptography': _pkg_version('cryptography'),
        'reportlab': _pkg_version('reportlab'),
        'gunicorn': _pkg_version('gunicorn'),
        'instance_writable': os.access(INSTANCE_DIR, os.W_OK) if os.path.isdir(INSTANCE_DIR) else None,
        'env_exists': os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')),
        # پیشرفت نصب پس‌زمینه
        'install_status': prog.get('status'),
        'install_step': prog.get('step'),
        'install_steps': prog.get('steps'),
        'install_msg': prog.get('msg'),
        'install_stale': prog.get('stale', False),
    }
    if prog.get('status') == 'done' and prog.get('ok'):
        # لاگین خودکار مدیر — یک بار بعد از اتمام نصب
        try:
            from installer import _bg_logged_in
            if not _bg_logged_in():
                from models import User
                from flask import session as _sess
                adm = User.query.order_by(User.id).filter(User.role == 'super_admin').first()
                if adm:
                    _sess['uid'] = adm.id
                    import installer as _inst_mod
                    _inst_mod._mark_bg_logged_in()
        except Exception:
            pass
    if info['installed'] and prog.get('status') in ('idle', 'done', 'error'):
        ok, msg = check_db_health()
        info['db_ok'] = ok
        info['db_msg'] = msg
        info['db_type'] = 'mysql' if str(env_db_url()).startswith('mysql') else 'sqlite'
    return jsonify(info)


@install_bp.route('/install/repair', methods=['POST'])
def repair():
    """تعمیر نصب ناقص — جدول‌ها و داده‌های اولیه را دوباره می‌سازد (بدون حذف داده موجود)"""
    try:
        if not is_installed():
            return jsonify(ok=False, msg='نصب انجام نشده — از فرم نصب استفاده کنید.'), 400
        d = request.form or {}
        db_url = env_db_url()
        admin = {
            'name': d.get('admin_name', '').strip() or 'مدیر',
            'email': (d.get('admin_email', '').strip().lower() or 'admin@academy.ir'),
            'password': d.get('admin_pass', '') or 'Admin12345!',
        }
        site = {}
        create_demo = d.get('demo_student') == '1'
        # تعمیر هم پس‌زمینه — ضد Request Timeout (همان عملیات سنگین است)
        started, s_msg = start_background_install(db_url, admin, site, create_demo)
        if not started:
            return jsonify(ok=False, msg=s_msg), 400
        return jsonify(ok=True, started=True, msg='تعمیر شروع شد — در حال انجام...', redirect=None)
    except Exception as e:
        current_app.logger.error('install repair error: %s\n%s', e, _tb.format_exc())
        return jsonify(ok=False, msg='خطا در تعمیر: ' + str(e)[:250]), 500
