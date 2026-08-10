# -*- coding: utf-8 -*-
"""ثبت‌نام، ورود (ایمیل و شماره تماس OTP)، تکمیل پروفایل و خروج"""
import random
import time
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, session
from models import db, User
from validators import is_valid_phone, is_valid_national_code
from validators import log_exc as _lexc


def _safe_next(url):
    """اعتبارسنجی پارامتر next — جلوگیری از Open Redirect (فقط مسیرهای نسبی داخلی)"""
    if not url:
        return None
    url = url.strip()
    # فقط مسیرهای نسبی (شروع با / و نه // که پروتکل-نسبی است)
    if url.startswith('/') and not url.startswith('//') and not url.startswith('/\\'):
        # جلوگیری از نویسه‌های خطرناک
        if any(c in url for c in ('\n', '\r', '\x00')):
            return None
        return url[:500]
    return None


auth_bp = Blueprint('auth', __name__)

AVATAR_COLORS = ['#2563eb', '#7c3aed', '#059669', '#dc2626', '#ea580c',
                 '#db2777', '#0891b2', '#f59e0b', '#16a34a', '#9333ea']

# ---------------------------------------------------------------- محدودیت نرخ مبتنی بر IP
# نگهداری تلاش‌های ناموفق به‌ازای IP — مکمل محدودیت session (پاک‌کردن کوکی دور نمی‌زند)
_LOGIN_ATTEMPTS = {}   # ip -> [timestamps]
_LOGIN_LOCK = {}       # ip -> lock_until
MAX_FAILS = 5
LOCK_MINUTES = 15


def _client_ip():
    # پشتیبانی از پراکسی (X-Forwarded-For) — فقط در صورت اعتماد به پراکسی
    xff = request.headers.get('X-Forwarded-For')
    if xff:
        return xff.split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'


def _ip_allowed():
    """بررسی قفل IP — True یعنی مجاز به تلاش"""
    ip = _client_ip()
    lock = _LOGIN_LOCK.get(ip, 0)
    if time.time() < lock:
        return False
    return True


def _ip_fail():
    """ثبت یک تلاش ناموفق برای IP"""
    ip = _client_ip()
    now = time.time()
    lst = [t for t in _LOGIN_ATTEMPTS.get(ip, []) if now - t < LOCK_MINUTES * 60]
    lst.append(now)
    _LOGIN_ATTEMPTS[ip] = lst
    if len(lst) >= MAX_FAILS:
        _LOGIN_LOCK[ip] = now + LOCK_MINUTES * 60
        _LOGIN_ATTEMPTS[ip] = []


def _ip_success():
    ip = _client_ip()
    _LOGIN_ATTEMPTS.pop(ip, None)
    _LOGIN_LOCK.pop(ip, None)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if g.settings.get('allow_register') == '0':
        flash('ثبت‌نام جدید موقتاً غیرفعال است. با پشتیبانی تماس بگیرید.', 'error')
        return redirect(url_for('auth.login'))
    if g.user:
        return redirect(url_for('site.index'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        nc = request.form.get('national_code', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        err = None
        if len(name) < 3:
            err = 'نام و نام خانوادگی را کامل وارد کنید.'
        elif not is_valid_phone(phone):
            err = 'شماره تماس معتبر نیست — باید با 09 شروع شود و ۱۱ رقم باشد. (مثال: 09123456789)'
        elif User.query.filter_by(phone=phone).first():
            err = 'این شماره تماس قبلاً ثبت شده است. با همان شماره وارد شوید.'
        elif not is_valid_national_code(nc):
            err = 'کد ملی معتبر نیست. لطفاً کد ملی ۱۰ رقمی صحیح خود را وارد کنید.'
        elif User.query.filter_by(national_code=nc).first():
            err = 'این کد ملی قبلاً در سیستم ثبت شده است.'
        elif '@' not in email:
            err = 'ایمیل معتبر وارد کنید.'
        elif User.query.filter_by(email=email).first():
            err = 'این ایمیل قبلاً ثبت شده است.'
        elif len(password) < 8:
            err = 'رمز عبور باید حداقل ۸ کاراکتر باشد.'
        elif password != confirm:
            err = 'تکرار رمز عبور مطابقت ندارد.'
        if err:
            flash(err, 'error')
        else:
            user = User(name=name, phone=phone, national_code=nc, email=email,
                        role='student', avatar_color=random.choice(AVATAR_COLORS))
            user.set_password(password)
            # کد معرف (ارجاع دوستان) — از پارامتر ref یا کوکی
            ref = request.args.get('ref') or request.form.get('ref') or session.pop('ref_code', '')
            ref = (ref or '').strip().upper()
            if ref:
                referrer = User.query.filter_by(referral_code=ref).first()
                if referrer and referrer.id and referrer.email != email:
                    user.referred_by = referrer.id
            db.session.add(user)
            db.session.commit()
            if not user.referral_code:
                from gamification import make_referral_code
                make_referral_code(user)
                db.session.commit()
            session['uid'] = user.id
            try:
                from email_service import send_welcome
                send_welcome(user, g.settings)
            except Exception:
                _lexc('blueprints/auth.py')
            flash(f'خوش آمدید {user.name}! عضویت شما با موفقیت انجام شد. 🎉', 'success')
            return redirect(url_for('student.dashboard'))
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('site.index'))
    # قفل مبتنی بر IP (در برابر پاک‌کردن کوکی و حملات توزیع‌شده)
    if not _ip_allowed():
        flash('به دلیل تلاش‌های ناموفق زیاد از این آدرس، ورود موقتاً قفل شد. ۱۵ دقیقه دیگر تلاش کنید.', 'error')
        return render_template('auth/login.html')
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('ایمیل یا رمز عبور اشتباه است.', 'error')
        elif not user.is_active:
            # ضد Enumeration: پیام همان «رمز اشتباه» — عدم افشای وجود حساب غیرفعال
            flash('ایمیل یا رمز عبور اشتباه است.', 'error')
            import logging as _lg
            _lg.getLogger('academy.auth').info(f'login blocked: حساب غیرفعال ({email})')
        else:
            session.permanent = bool(request.form.get('remember'))
            if not user.session_token:
                user.new_session_token()
                db.session.commit()
            session['uid'] = user.id
            session['st'] = user.session_token
            session.pop('login_fails', None)
            _ip_success()
            # تایید دومرحله‌ای برای مدیران
            if user.role in ('admin', 'super_admin'):
                code2 = str(random.randint(100000, 999999))
                session['admin_2fa'] = code2
                session['admin_2fa_ts'] = time.time()
                from sms import send_sms
                send_sms(user.phone or '', f'کد تایید دومرحله‌ای ورود به پنل: {code2}', g.settings)
                flash(f'🔐 کد تایید دومرحله‌ای (دمو): {code2}', 'info')
                return redirect(url_for('auth.admin_2fa'))
            from models import ActivityLog
            db.session.add(ActivityLog(user_id=user.id, action='login',
                                       detail='ورود با ایمیل', ip=_client_ip()))
            from gamification import award_points, record_streak
            record_streak(user)
            # هشدار ورود مشکوک: اگر IP تغییر کرده باشد
            try:
                from models import Notification
                ip_now = _client_ip()
                if user.last_login_ip and user.last_login_ip != ip_now:
                    Notification.notify(user.id, 'ورود از دستگاه/آدرس جدید ⚠️',
                                        f'ورود جدید از {ip_now} — اگر شما نبودید، رمز را عوض کنید و خروج از همه دستگاه‌ها را بزنید.',
                                        '⚠️', url_for('student.profile'))
                    db.session.add(ActivityLog(user_id=user.id, action='suspicious_login',
                                               detail=f'IP جدید: {ip_now} (قبلی: {user.last_login_ip})'))
                user.last_login_ip = ip_now
            except Exception:
                _lexc('blueprints/auth.py')
            db.session.commit()
            flash(f'خوش برگشتی {user.name}! 👋', 'success')
            if not user.profile_complete():
                return redirect(url_for('auth.complete_profile'))
            return redirect(_safe_next(request.args.get('next')) or url_for('student.dashboard'))
        # شمارش تلاشهای ناموفق — محدودیت ۵ بار در ۱۵ دقیقه (session + IP)
        fails = session.get('login_fails', 0) + 1
        session['login_fails'] = fails
        _ip_fail()
        if fails >= 5:
            session['login_lock'] = time.time()
            flash('به دلیل تلاشهای ناموفق مکرر، ورود ۱۵ دقیقه قفل شد.', 'error')
            session.pop('login_fails', None)
        elif fails >= 3:
            from app import fa as _fa
            flash(f'⚠️ {_fa(5 - fails)} تلاش دیگر تا قفل شدن ورود.', 'info')
    if time.time() - session.get('login_lock', 0) < 900:
        flash('ورود موقتاً قفل است. ۱۵ دقیقه دیگر تلاش کنید.', 'error')
        return render_template('auth/login.html')
    return render_template('auth/login.html')


# ---------------------------------------------------------------- ورود با شماره تماس (OTP)
@auth_bp.route('/phone-send', methods=['GET', 'POST'])
def phone_send():
    if g.settings.get('allow_phone_login') == '0':
        flash('ورود با شماره تماس موقتاً غیرفعال است.', 'error')
        return redirect(url_for('auth.login'))
    """ارسال کد تایید به شماره تماس — در حالت دمو کد روی صفحه نمایش داده می‌شود"""
    phone = (request.form.get('phone') or request.args.get('phone') or '').strip()
    if not is_valid_phone(phone):
        flash('شماره تماس معتبر نیست — باید با 09 شروع شود و ۱۱ رقم باشد.', 'error')
        return redirect(url_for('auth.login'))
    # محدودیت ارسال: هر ۶۰ ثانیه یک بار، حداکثر ۵ بار در ۱۰ دقیقه
    now = time.time()
    last = session.get('otp_last_send', 0)
    count = session.get('otp_send_count', 0)
    if now - last < 60:
        flash('لطفاً ۶۰ ثانیه صبر کنید تا کد بعدی ارسال شود.', 'error')
        return redirect(url_for('auth.login'))
    if count >= 5 and now - session.get('otp_first_send', now) < 600:
        flash('تعداد تلاش‌ها بیش از حد مجاز است. ۱۰ دقیقه دیگر تلاش کنید.', 'error')
        return redirect(url_for('auth.login'))
    code = str(random.randint(10000, 99999))
    session['otp_phone'] = phone
    session['otp_code'] = code
    session['otp_ts'] = now
    session['otp_last_send'] = now
    session['otp_send_count'] = count + 1
    if 'otp_first_send' not in session:
        session['otp_first_send'] = now
    # ارسال کد: اگر پنل پیامکی واقعی تنظیم شده باشد پیامک می‌شود، وگرنه حالت دمو
    from sms import send_otp
    ok, msg = send_otp(phone, code, g.settings)
    if ok and g.settings.get('sms_provider') not in ('', 'demo', None):
        flash('📲 کد تایید به شماره شما پیامک شد.', 'success')
    else:
        flash(f'📲 کد تایید شما (حالت دمو): {code}', 'info')
    return redirect(url_for('auth.phone_verify'))


@auth_bp.route('/phone-verify', methods=['GET', 'POST'])
def phone_verify():
    phone = session.get('otp_phone')
    if not phone:
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        # محدودیت تلاش (۵ بار) — ضد brute-force
        otp_tries = session.get('otp_tries', 0) + 1
        session['otp_tries'] = otp_tries
        if otp_tries > 5:
            session.pop('otp_phone', None)
            session.pop('otp_code', None)
            session.pop('otp_tries', None)
            flash('تلاش‌های ناموفق بیش از حد — کد جدید درخواست کنید.', 'error')
            return redirect(url_for('auth.login'))
        if code != session.get('otp_code'):
            flash(f'کد تایید اشتباه است. ({5 - otp_tries + 1} تلاش باقی‌مانده)', 'error')
        elif time.time() - session.get('otp_ts', 0) > 600:
            flash('کد تایید منقضی شده است. دوباره ارسال کنید.', 'error')
            session.pop('otp_phone', None)
            session.pop('otp_code', None)
            session.pop('otp_tries', None)
            return redirect(url_for('auth.login'))
        else:
            session.pop('otp_tries', None)
            user = User.query.filter_by(phone=phone).first()
            if not user:
                user = User(phone=phone, name='', role='student',
                            avatar_color=random.choice(AVATAR_COLORS))
                db.session.add(user)
                db.session.commit()
                flash('حساب شما با شماره تماس ساخته شد — برای ادامه، پروفایل را تکمیل کنید.', 'info')
            else:
                flash(f'خوش برگشتی {user.name or "کاربر"}! 👋', 'success')
            if not user.session_token:
                user.new_session_token()
                db.session.commit()
            session['uid'] = user.id
            session['st'] = user.session_token
            session.pop('otp_phone', None)
            session.pop('otp_code', None)
            session.pop('otp_ts', None)
            if not user.profile_complete():
                return redirect(url_for('auth.complete_profile'))
            return redirect(url_for('student.dashboard'))
    return render_template('auth/phone_verify.html', phone=phone)


# ---------------------------------------------------------------- بازیابی رمز عبور (OTP موبایل)
@auth_bp.route('/admin-2fa', methods=['GET', 'POST'])
def admin_2fa():
    """تایید دومرحله‌ای ورود مدیر"""
    if not g.user or g.user.role not in ('admin', 'super_admin'):
        return redirect(url_for('site.index'))
    if not session.get('admin_2fa'):
        return redirect(url_for('student.dashboard'))
    if request.method == 'POST':
        # انقضای کد (۵ دقیقه)
        if time.time() - session.get('admin_2fa_ts', 0) > 300:
            session.pop('admin_2fa', None)
            session.pop('admin_2fa_ts', None)
            session.pop('admin_2fa_tries', None)
            flash('کد تایید منقضی شده — دوباره وارد شوید.', 'error')
            return redirect(url_for('auth.login'))
        # محدودیت تلاش (۵ بار) — ضد brute-force
        tries = session.get('admin_2fa_tries', 0) + 1
        session['admin_2fa_tries'] = tries
        if tries > 5:
            session.pop('admin_2fa', None)
            session.pop('admin_2fa_ts', None)
            session.pop('admin_2fa_tries', None)
            flash('تلاش‌های ناموفق بیش از حد — دوباره وارد شوید.', 'error')
            return redirect(url_for('auth.login'))
        code = request.form.get('code', '').strip()
        if code == session.get('admin_2fa'):
            session.pop('admin_2fa', None)
            session.pop('admin_2fa_ts', None)
            session.pop('admin_2fa_tries', None)
            from models import ActivityLog
            db.session.add(ActivityLog(user_id=g.user.id, action='login',
                                       detail='تایید دومرحله‌ای موفق', ip=_client_ip()))
            db.session.commit()
            flash('ورود امن تایید شد. ✅', 'success')
            return redirect(url_for('admin.overview'))
        flash(f'کد تایید اشتباه است. ({5 - tries + 1} تلاش باقی‌مانده)', 'error')
    return render_template('auth/admin_2fa.html')


@auth_bp.route('/forgot', methods=['GET', 'POST'])
def forgot():
    """فراموشی رمز — ارسال کد به موبایل و تغییر رمز"""
    if g.user:
        return redirect(url_for('site.index'))
    if request.method == 'POST':
        phone = (request.form.get('phone') or '').strip()
        if not is_valid_phone(phone):
            flash('شماره تماس معتبر نیست.', 'error')
            return redirect(url_for('auth.forgot'))
        user = User.query.filter_by(phone=phone).first()
        # ضد Enumeration: پیام یکسان چه شماره ثبت شده باشد چه نه — کد فقط برای شماره موجود ارسال میشود
        if not user:
            import logging as _lg
            _lg.getLogger('academy.auth').info('forgot: شماره ثبتنشده درخواست بازیابی داد')
            flash('اگر این شماره در سیستم ثبت شده باشد، کد بازیابی ارسال میشود.', 'info')
            return redirect(url_for('auth.forgot'))
        if not user.email and not user.password_hash:
            flash('این حساب رمز عبور ندارد (ورود فقط با کد تایید). می‌توانید از همان ورود با کد استفاده کنید.', 'info')
            return redirect(url_for('auth.login'))
        # ارسال کد (مکانیزم مشترک OTP)
        now = time.time()
        last = session.get('otp_last_send', 0)
        if now - last < 60:
            flash('لطفاً ۶۰ ثانیه صبر کنید.', 'error')
            return redirect(url_for('auth.forgot'))
        code = str(random.randint(10000, 99999))
        session['otp_phone'] = phone
        session['otp_code'] = code
        session['otp_ts'] = now
        session['otp_last_send'] = now
        session['otp_purpose'] = 'reset'
        flash(f'📲 کد بازیابی شما (حالت دمو): {code}', 'info')
        return redirect(url_for('auth.forgot_verify'))
    return render_template('auth/forgot.html')


@auth_bp.route('/forgot-verify', methods=['GET', 'POST'])
def forgot_verify():
    if g.user:
        return redirect(url_for('site.index'))
    phone = session.get('otp_phone')
    if not phone or session.get('otp_purpose') != 'reset':
        return redirect(url_for('auth.forgot'))
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if code != session.get('otp_code'):
            flash('کد تایید اشتباه است.', 'error')
        elif time.time() - session.get('otp_ts', 0) > 600:
            flash('کد منقضی شده است. دوباره تلاش کنید.', 'error')
            session.pop('otp_phone', None)
            session.pop('otp_code', None)
            session.pop('otp_purpose', None)
            return redirect(url_for('auth.forgot'))
        elif len(password) < 6:
            flash('رمز جدید باید حداقل ۶ کاراکتر باشد.', 'error')
        elif password != confirm:
            flash('تکرار رمز مطابقت ندارد.', 'error')
        else:
            user = User.query.filter_by(phone=phone).first()
            if user:
                user.set_password(password)
                user.new_session_token()  # باطل‌کردن همه سشن‌های قبلی
                db.session.commit()
                flash('رمز عبور شما با موفقیت تغییر کرد. حالا وارد شوید. ✅', 'success')
            session.pop('otp_phone', None)
            session.pop('otp_code', None)
            session.pop('otp_purpose', None)
            return redirect(url_for('auth.login'))
    return render_template('auth/forgot_verify.html', phone=phone)


# ---------------------------------------------------------------- تکمیل پروفایل
@auth_bp.route('/complete-profile', methods=['GET', 'POST'])
def complete_profile():
    """برای کاربرانی که با شماره تماس وارد شده‌اند: کد ملی، نام، ایمیل و رمز"""
    if not g.user:
        return redirect(url_for('auth.login'))
    if g.user.profile_complete():
        return redirect(url_for('student.dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        nc = request.form.get('national_code', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        err = None
        if len(name) < 3:
            err = 'نام و نام خانوادگی را کامل وارد کنید.'
        elif not is_valid_national_code(nc):
            err = 'کد ملی معتبر نیست — کد ملی ۱۰ رقمی صحیح خود را وارد کنید.'
        elif User.query.filter(User.national_code == nc, User.id != g.user.id).first():
            err = 'این کد ملی قبلاً در سیستم ثبت شده است.'
        elif '@' not in email:
            err = 'ایمیل معتبر وارد کنید.'
        elif User.query.filter(User.email == email, User.id != g.user.id).first():
            err = 'این ایمیل قبلاً ثبت شده است.'
        elif not g.user.password_hash and len(password) < 6:
            err = 'برای حساب خود یک رمز عبور (حداقل ۶ کاراکتر) تعیین کنید.'
        if err:
            flash(err, 'error')
        else:
            g.user.name = name
            g.user.national_code = nc
            g.user.email = email
            if password:
                g.user.set_password(password)
            db.session.commit()
            flash('پروفایل شما تکمیل شد — خوش آمدید! 🎉', 'success')
            return redirect(url_for('student.dashboard'))
    return render_template('auth/complete_profile.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('با موفقیت خارج شدید. به امید دیدار!', 'info')
    return redirect(url_for('site.index'))
