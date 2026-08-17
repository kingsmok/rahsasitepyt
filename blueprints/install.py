# -*- coding: utf-8 -*-
"""نصب‌کننده وب — مشابه وردپرس (مسیر /install)

قانون طلایی: همه مسیرهای POST این بلوپرینت **همیشه** JSON برمی‌گردانند —
حتی هنگام خطای 500 (با errorhandler) یا ریدایرکت. این یعنی مرورگر هرگز
خطای «JSON.parse» نمی‌گیرد.
"""
import hmac
import os
import sys
import time
import traceback as _tb

from flask import (Blueprint, render_template, request, redirect, url_for,
                   jsonify, current_app, g, session)
from werkzeug.exceptions import HTTPException

from installer import (is_installed, build_db_url, validate_mysql,
                       test_connection, check_db_health, env_db_url,
                       INSTANCE_DIR, run_install_request, install_progress,
                       detect_local_data, inspect_database,
                       attach_existing_database)

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
    return jsonify(ok=True, done=True, msg='نصب قبلاً انجام شده است.', redirect='/')


def _login_installed_admin(email=''):
    """ثبت سشن مدیر پس از آخرین تکه نصب؛ شکست آن نباید نصب را خراب کند."""
    try:
        from models import User
        from flask import session
        q = User.query.filter(User.role == 'super_admin')
        adm = q.filter(User.email == email).first() if email else None
        adm = adm or q.order_by(User.id).first()
        if adm:
            session['uid'] = adm.id
    except Exception:
        pass


@install_bp.route('/install')
def wizard():
    # اگر اصلاً نصب نشده → مستقیم صفحهٔ نصب (حتی اگر دیتابیسِ خالی سالم باشد،
    # نباید به index ریدایرکت کند چون سایت آماده نیست)
    if not is_installed():
        return render_template('install/wizard.html')
    # نصب شده — سلامت دیتابیس؟
    ok, _ = check_db_health()
    if ok:
        return redirect(url_for('site.index'))
    # نصب ناقص (دیتابیس خراب) → صفحه تعمیر — نه ریدایرکت (ضد حلقه)
    return render_template('install/wizard.html')


def _url_from_request(d):
    db_type = d.get('db_type') or d.get('type') or 'sqlite'
    if db_type in ('mysql', 'attach', 'xampp'):
        err = validate_mysql(d.get('host') or d.get('db_host') or '',
                             d.get('name') or d.get('db_name') or '',
                             d.get('user') or d.get('db_user') or '')
        if err:
            return None, err
        return build_db_url(
            'mysql',
            d.get('host') or d.get('db_host') or '',
            d.get('port') or d.get('db_port') or '',
            d.get('name') or d.get('db_name') or '',
            d.get('user') or d.get('db_user') or '',
            d.get('password') or d.get('db_pass') or '',
        ), ''
    return '', ''


@install_bp.route('/install/test-db', methods=['POST'])
def test_db():
    """تست اتصال دیتابیس — همیشه JSON؛ حتی بعد از نصب هم کار می‌کند."""
    try:
        d = request.get_json(silent=True) or request.form or {}
        if is_installed() and not _repair_authorized(d):
            return jsonify(ok=False, msg='دسترسی نصب‌کننده بسته است.'), 403
        url, err = _url_from_request(d)
        if err:
            return jsonify(ok=False, msg=err)
        ok, msg = test_connection(url)
        return jsonify(ok=ok, msg=msg)
    except Exception as e:
        current_app.logger.error('install test-db error: %s', e)
        return jsonify(ok=False, msg='خطا در تست اتصال: ' + str(e)[:200]), 500


@install_bp.route('/install/detect')
def detect_db():
    """تشخیص دیتابیس محلی؛ جزئیات نصب فعال فقط برای سوپرادمین."""
    if is_installed() and not _repair_authorized(request.args):
        return jsonify(ok=True, installed=True)
    info = detect_local_data()
    return jsonify(ok=True, **info)


@install_bp.route('/install/inspect-db', methods=['POST'])
def inspect_db():
    """خواندن خلاصهٔ دیتابیس ساخته‌شده — بدون نوشتن."""
    try:
        d = request.get_json(silent=True) or request.form or {}
        if is_installed() and not _repair_authorized(d):
            return jsonify(ok=False, msg='دسترسی نصب‌کننده بسته است.'), 403
        url, err = _url_from_request(d)
        if err:
            return jsonify(ok=False, msg=err)
        report = inspect_database(url)
        local = detect_local_data()
        report['local'] = {
            'sqlite_has_data': local['sqlite_has_data'],
            'sqlite_users': local['sqlite_users'],
            'sqlite_courses': local['sqlite_courses'],
            'sqlite_site_name': local['sqlite_site_name'],
        }
        return jsonify(**report)
    except Exception as e:
        current_app.logger.error('install inspect-db error: %s', e)
        return jsonify(ok=False, msg='خطا در بررسی دیتابیس: ' + str(e)[:200]), 500


@install_bp.route('/install/attach', methods=['POST'])
def attach_db():
    """وصل کردن دیتابیس موجود / فایل آپلودشده؛ فقط برای مالک نصب."""
    try:
        d = request.get_json(silent=True) or request.form or {}
        if is_installed() and not _repair_authorized(d):
            return jsonify(ok=False, msg='اتصال دیتابیس مجاز نیست.'), 403
        url, err = _url_from_request(d)
        if err:
            return jsonify(ok=False, msg=err)
        copy_flag = str(d.get('copy_sqlite') or '').strip() in ('1', 'true', 'yes', 'on')
        ok, msg = attach_existing_database(url, copy_from_sqlite=copy_flag)
        if not ok:
            return jsonify(ok=False, msg=msg), 400
        try:
            from models import User
            from flask import session
            adm = User.query.filter(User.role == 'super_admin').order_by(User.id).first()
            if adm:
                session['uid'] = adm.id
        except Exception:
            pass
        session.pop('install_repair_authorized_at', None)
        return jsonify(ok=True, done=True, msg=msg, redirect='/')
    except Exception as e:
        current_app.logger.error('install attach error: %s\n%s', e, _tb.format_exc())
        return jsonify(ok=False, msg='خطا در اتصال دیتابیس: ' + str(e)[:250]), 500


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
        # نسخهٔ نهایی هیچ حساب یا محتوای نمایشی ایجاد نمی‌کند.
        create_demo = False

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

        # نصب تکه‌ای داخل درخواست‌های کوتاه: هاست نمی‌تواند thread پس‌زمینه را
        # بعد از پایان response متوقف کند. مرورگر تا done درخواست بعدی را می‌فرستد.
        result, s_msg, prog = run_install_request(
            db_url, admin, site, create_demo)
        if result is False:
            return jsonify(ok=False, done=False, msg=s_msg,
                           install_status='error'), 400
        if result is True:
            _login_installed_admin(admin['email'])
        return jsonify(
            ok=True,
            started=True,
            done=result is True,
            msg=s_msg,
            install_status=prog.get('status'),
            install_step=prog.get('step'),
            install_steps=prog.get('steps'),
            chunks=prog.get('chunks'),
            redirect='/' if result is True else None,
        )
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
    """وضعیت نصب؛ جزئیات نسخه/دیتابیس نصب فعال عمومی نمی‌شود."""
    installed = is_installed()
    if installed and not _repair_authorized(request.args):
        return jsonify(installed=True, install_status='locked')
    prog = install_progress()
    info = {
        'installed': installed,
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
        'install_mode': prog.get('mode'),
        'install_chunks': prog.get('chunks', 0),
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


def _repair_authorized(data):
    """اثبات مالکیت برای تعمیر نصب؛ بدون رمز یا حساب پیش‌فرض."""
    user = getattr(g, 'user', None)
    if user and user.role == 'super_admin':
        return True
    # پس از تایید نخست، درخواست‌های تکه‌ای همان سشن تا ۱۵ دقیقه معتبرند.
    authorized_at = session.get('install_repair_authorized_at', 0)
    if authorized_at and time.time() - authorized_at < 900:
        return True
    email = (data.get('admin_email') or '').strip().lower()
    password = data.get('admin_pass') or ''
    try:
        from models import User
        admin = User.query.filter_by(email=email, role='super_admin', is_active=True).first()
        if admin and admin.check_password(password):
            session['install_repair_authorized_at'] = time.time()
            return True
    except Exception:
        # اگر جدول کاربران خراب/حذف شده باشد فقط کلید اضطراری فایل .env معتبر است.
        pass
    supplied = (data.get('repair_token') or
                request.headers.get('X-Install-Repair-Token') or '')
    expected = os.environ.get('INSTALL_REPAIR_TOKEN', '')
    if expected and supplied and hmac.compare_digest(str(supplied), str(expected)):
        session['install_repair_authorized_at'] = time.time()
        return True
    return False


@install_bp.route('/install/repair', methods=['POST'])
def repair():
    """تعمیر idempotent نصب؛ فقط پس از اثبات مالکیت سرور/سوپرادمین."""
    try:
        if not is_installed():
            return jsonify(ok=False, msg='نصب انجام نشده — از فرم نصب استفاده کنید.'), 400
        d = request.form or {}
        if not _repair_authorized(d):
            return jsonify(ok=False,
                           msg='تعمیر مجاز نیست؛ رمز سوپرادمین یا کلید بازیابی .env لازم است.'), 403
        admin = {
            'name': d.get('admin_name', '').strip(),
            'email': d.get('admin_email', '').strip().lower(),
            'password': d.get('admin_pass', ''),
        }
        # در تعمیر اضطراری با token و جدول کاربران خراب، همین اطلاعات حساب جدید
        # را می‌سازد؛ هیچ ایمیل/رمز قابل حدسی در کد وجود ندارد.
        if not admin['name'] or len(admin['name']) < 3:
            return jsonify(ok=False, msg='نام مدیر حداقل ۳ حرف باشد.'), 400
        if '@' not in admin['email']:
            return jsonify(ok=False, msg='ایمیل مدیر معتبر لازم است.'), 400
        if len(admin['password']) < 8:
            return jsonify(ok=False, msg='رمز مدیر حداقل ۸ کاراکتر باشد.'), 400
        db_url = env_db_url()
        site = {}
        create_demo = False
        # تعمیر نیز تکه‌ای و idempotent است؛ مرورگر تا پایان درخواست بعدی می‌فرستد.
        result, s_msg, prog = run_install_request(
            db_url, admin, site, create_demo)
        if result is False:
            return jsonify(ok=False, done=False, msg=s_msg,
                           install_status='error'), 400
        if result is True:
            _login_installed_admin(admin['email'])
            session.pop('install_repair_authorized_at', None)
        return jsonify(
            ok=True,
            started=True,
            done=result is True,
            msg=s_msg,
            install_status=prog.get('status'),
            install_step=prog.get('step'),
            install_steps=prog.get('steps'),
            chunks=prog.get('chunks'),
            redirect='/' if result is True else None,
        )
    except Exception as e:
        current_app.logger.error('install repair error: %s\n%s', e, _tb.format_exc())
        return jsonify(ok=False, msg='خطا در تعمیر: ' + str(e)[:250]), 500
