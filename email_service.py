# -*- coding: utf-8 -*-
"""ارسال ایمیل واقعی (SMTP)؛ بدون fallback نمایشی.
تنظیمات در پنل مدیریت → تنظیمات → ایمیل
"""
import smtplib
import html as _html
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

log = logging.getLogger('academy.email')


def _esc(v):
    """escape امن برای HTML ایمیل — ضد XSS/HTML Injection (نام کاربر، عنوان دوره و...)"""
    return _html.escape(str(v or ''), quote=True)


def send_email(to_email, subject, html_body, settings):
    """ارسال ایمیل — خروجی (ok, message)"""
    host = (settings.get('smtp_host') or '').strip()
    if not host:
        log.warning('Email skipped: SMTP is not configured')
        return False, 'سرویس ایمیل SMTP پیکربندی نشده است.'
    try:
        port = int(settings.get('smtp_port') or 587)
        user = (settings.get('smtp_user') or '').strip()
        password = (settings.get('smtp_pass') or '').strip()
        sender = (settings.get('smtp_from') or user or 'noreply@academy.ir').strip()
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = to_email
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        server = smtplib.SMTP(host, port, timeout=15)
        server.ehlo()
        if settings.get('smtp_tls') != '0':
            server.starttls()
        if user:
            server.login(user, password)
        server.sendmail(sender, [to_email], msg.as_string())
        server.quit()
        return True, 'ارسال شد'
    except Exception as e:
        log.error(f'EMAIL error: {e}')
        return False, f'خطا: {e}'


def send_welcome(user, settings):
    """ایمیل خوش‌آمدگویی"""
    # احترام به تنظیم اعلان شخصی کاربر (خارج از ایمیل‌های امنیتی)
    if getattr(user, 'notify_email', True) is False:
        return False, 'skipped: user disabled email notifications'
    name = user.name or 'کاربر'
    html = f"""<div dir="rtl" style="font-family:Tahoma;max-width:560px;margin:auto;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden">
      <div style="background:#0d1f36;color:#fff;padding:22px;text-align:center;font-size:20px;font-weight:bold">🎓 {settings.get('site_name') or 'آکادمی آنلاین'}</div>
      <div style="padding:26px;color:#334155;font-size:14px;line-height:2">
        <p>سلام <b>{_esc(name)}</b> عزیز،</p>
        <p>به خانواده بزرگ {settings.get('site_name') or 'آکادمی آنلاین'} خوش آمدی! 🎉</p>
        <p>حالا می‌توانی دوره‌های آموزشی را ببینی، مسیر یادگیری خود را مدیریت کنی و از امکانات حساب کاربری استفاده کنی. برای شروع، از <a href="{settings.get('base_url') or '/'}/courses" style="color:#f2640c;font-weight:bold">دوره‌های موجود</a> دیدن کن.</p>
      </div>
      <div style="background:#f8fafc;padding:14px;text-align:center;font-size:11px;color:#94a3b8">{settings.get('site_name') or 'آکادمی آنلاین'} — این ایمیل به‌صورت خودکار ارسال شده است.</div>
    </div>"""
    return send_email(user.email, f'به {settings.get("site_name") or "آکادمی آنلاین"} خوش آمدی 🎉', html, settings)


def send_payment_notice(user, order, settings):
    """ایمیل تایید خرید"""
    # احترام به تنظیم اعلان شخصی کاربر (خارج از ایمیل‌های امنیتی)
    if getattr(user, 'notify_email', True) is False:
        return False, 'skipped: user disabled email notifications'
    html = f"""<div dir="rtl" style="font-family:Tahoma;max-width:560px;margin:auto;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden">
      <div style="background:#16a34a;color:#fff;padding:20px;text-align:center;font-size:18px;font-weight:bold">✅ پرداخت موفق</div>
      <div style="padding:26px;color:#334155;font-size:14px;line-height:2">
        <p>سلام <b>{_esc(user.name)}</b>،</p>
        <p>پرداخت سفارش <b dir="ltr">{_esc(order.code)}</b> به مبلغ <b>{order.final_total:,}</b> تومان با موفقیت تایید شد.</p>
        <p><a href="{settings.get('base_url') or '/'}/dashboard/orders" style="color:#f2640c;font-weight:bold">مشاهده وضعیت سفارش ←</a></p>
      </div>
    </div>"""
    return send_email(user.email, f'پرداخت سفارش {_esc(order.code)} موفق بود ✅', html, settings)


def send_certificate_email(user, course, cert_code, settings):
    """ایمیل صدور گواهی"""
    # احترام به تنظیم اعلان شخصی کاربر (خارج از ایمیل‌های امنیتی)
    if getattr(user, 'notify_email', True) is False:
        return False, 'skipped: user disabled email notifications'
    html = f"""<div dir="rtl" style="font-family:Tahoma;max-width:560px;margin:auto;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden">
      <div style="background:linear-gradient(135deg,#0d1f36,#1d4a75);color:#fff;padding:20px;text-align:center;font-size:18px;font-weight:bold">🏅 گواهینامه شما صادر شد</div>
      <div style="padding:26px;color:#334155;font-size:14px;line-height:2">
        <p>تبریک <b>{_esc(user.name)}</b>! 🎉</p>
        <p>دوره «<b>{_esc(course.title)}</b>» را با موفقیت کامل کردی و گواهینامه پایان دوره برایت صادر شد.</p>
        <p>کد رهگیری: <b dir="ltr">{_esc(cert_code)}</b></p>
        <p>هر کسی می‌تواند با این کد، صحت گواهی تو را در <a href="{settings.get('base_url') or '/'}/verify-certificate" style="color:#f2640c">صفحه استعلام</a> بررسی کند.</p>
      </div>
    </div>"""
    return send_email(user.email, f'گواهینامه دوره «{_esc(course.title)}» صادر شد 🏅', html, settings)


def send_ticket_reply(user, ticket, reply, settings):
    # احترام به تنظیم اعلان شخصی کاربر (خارج از ایمیل‌های امنیتی)
    if getattr(user, 'notify_email', True) is False:
        return False, 'skipped: user disabled email notifications'
    # پاسخ را پیش از قرار گرفتن در بدنهٔ HTML escape کن (ضد HTML Injection)
    reply_html = _esc(reply).replace('\n', '<br>')
    html = f"""<div dir="rtl" style="font-family:Tahoma;max-width:560px;margin:auto;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden">
      <div style="background:#0891b2;color:#fff;padding:20px;text-align:center;font-size:18px;font-weight:bold">🎫 پاسخ تیکت پشتیبانی</div>
      <div style="padding:26px;color:#334155;font-size:14px;line-height:2">
        <p>سلام <b>{_esc(user.name)}</b>،</p>
        <p>تیکت «<b>{_esc(ticket.subject)}</b>» پاسخ داده شد:</p>
        <div style="background:#f5f7fa;border-radius:12px;padding:14px;margin:10px 0">{reply_html}</div>
        <p><a href="{settings.get('base_url') or '/'}/dashboard/tickets" style="color:#f2640c;font-weight:bold">مشاهده تیکت ←</a></p>
      </div>
    </div>"""
    return send_email(user.email, f'پاسخ تیکت: {_esc(ticket.subject)}', html, settings)


def send_password_reset_email(user, reset_code, settings):
    """ایمیل بازیابی رمز عبور با کد تایید"""
    # احترام به تنظیم اعلان شخصی کاربر (خارج از ایمیل‌های امنیتی)
    if getattr(user, 'notify_email', True) is False:
        return False, 'skipped: user disabled email notifications'
    name = user.name or 'کاربر'
    base_url = settings.get('base_url') or ''
    html = f"""<div dir="rtl" style="font-family:Tahoma;max-width:560px;margin:auto;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden">
      <div style="background:#dc2626;color:#fff;padding:22px;text-align:center;font-size:20px;font-weight:bold">🔑 بازیابی رمز عبور</div>
      <div style="padding:26px;color:#334155;font-size:14px;line-height:2">
        <p>سلام <b>{_esc(name)}</b> عزیز،</p>
        <p>درخواست بازیابی رمز عبور برای حساب شما در <b>{settings.get('site_name') or 'آکادمی آنلاین'}</b> ثبت شد.</p>
        <p>کد تأیید شما:</p>
        <div style="background:#f1f5f9;border:2px dashed #cbd5e1;border-radius:12px;padding:16px;margin:16px 0;text-align:center;font-size:28px;font-weight:bold;letter-spacing:6px;color:#1e40af;font-family:monospace">{reset_code}</div>
        <p style="font-size:12px;color:#64748b">⚠️ اگر شما درخواست بازیابی رمز عبور نداده‌اید، این ایمیل را نادیده بگیرید. این کد تا ۱۰ دقیقه معتبر است.</p>
        <p style="font-size:12px;color:#64748b">🔐 هرگز این کد را با دیگران به اشتراک نگذارید.</p>
      </div>
      <div style="background:#f8fafc;padding:14px;text-align:center;font-size:11px;color:#94a3b8">{settings.get('site_name') or 'آکادمی آنلاین'} — این ایمیل به‌صورت خودکار ارسال شده است.</div>
    </div>"""
    subject = f'کد بازیابی رمز عبور — {settings.get("site_name") or "آکادمی آنلاین"}'
    return send_email(user.email, subject, html, settings)
