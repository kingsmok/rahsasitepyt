# -*- coding: utf-8 -*-
"""تولید فاکتور PDF واقعی با reportlab + فونت وزیرمتن"""
import os
from jdates import jdate,jtime
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas

_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'fonts')
_REGISTERED = False


def _register():
    global _REGISTERED
    if _REGISTERED:
        return
    pdfmetrics.registerFont(TTFont('Vazir', os.path.join(_FONTS_DIR, 'Vazirmatn-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('Vazir-Bold', os.path.join(_FONTS_DIR, 'Vazirmatn-Bold.ttf')))
    _REGISTERED = True


FA_DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def fa_num(n):
    return str(n).translate(FA_DIGITS)


def _fa_price(n):
    try:
        s = f'{int(n):,}'.translate(FA_DIGITS)
    except Exception:
        s = fa_num(n)
    return s


def build_invoice_pdf(order, site, user, items):
    """ساخت فاکتور PDF — خروجی bytes

    order: مدل Order | site: تنظیمات | user: خریدار | items: [(title, qty, price, total)]
    """
    _register()
    from io import BytesIO
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    NAVY = colors.HexColor('#0d1f36')
    ORANGE = colors.HexColor('#f2640c')
    GRAY = colors.HexColor('#64748b')
    LINE = colors.HexColor('#e2e8f0')

    # ---------- هدر ----------
    c.setFillColor(NAVY)
    c.rect(0, h - 130, w, 130, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont('Vazir-Bold', 20)
    c.drawRightString(w - 40, h - 55, site.get('site_name') or 'آکادمی آنلاین')
    c.setFont('Vazir', 10.5)
    c.setFillColor(colors.HexColor('#a8b8c8'))
    c.drawRightString(w - 40, h - 80, 'فاکتور رسمی خرید')
    c.setFillColor(ORANGE)
    c.setFont('Vazir-Bold', 13)
    c.drawRightString(w - 40, h - 105, f'کد سفارش: {order.code}')
    # تاریخ
    c.setFillColor(colors.HexColor('#a8b8c8'))
    c.setFont('Vazir', 10)
    c.drawString(40, h - 55, f'تاریخ: {jdate(order.created_at)}')
    c.drawString(40, h - 80, f'ساعت: {jtime(order.created_at)}')

    # ---------- اطلاعات خریدار ----------
    y = h - 165
    c.setFillColor(NAVY)
    c.setFont('Vazir-Bold', 11)
    c.drawRightString(w - 40, y, 'مشخصات خریدار')
    c.setFillColor(GRAY)
    c.setFont('Vazir', 10)
    c.drawRightString(w - 40, y - 20, f'نام: {user.name}')
    if user.email:
        c.drawRightString(w - 40, y - 38, f'ایمیل: {user.email}')
    if user.phone:
        c.drawRightString(w - 40, y - 56, f'شماره تماس: {fa_num(user.phone)}')

    # ---------- جدول آیتم‌ها ----------
    y = y - 100
    col_x = [40, w - 260, w - 160, w - 40]  # عنوان | قیمت واحد | تعداد | مبلغ کل (راست به چپ)
    c.setFillColor(NAVY)
    c.rect(40, y - 24, w - 80, 24, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont('Vazir-Bold', 10)
    c.drawRightString(col_x[3] - 8, y - 17, 'مبلغ کل')
    c.drawRightString(col_x[2] - 8, y - 17, 'تعداد')
    c.drawRightString(col_x[1] - 8, y - 17, 'قیمت واحد')
    c.drawRightString(col_x[0] + 8, y - 17, 'شرح')

    row_h = 22
    c.setFont('Vazir', 9.5)
    for i, (title, qty, price, total) in enumerate(items):
        yy = y - 24 - (i + 1) * row_h
        if i % 2 == 0:
            c.setFillColor(colors.HexColor('#f8fafc'))
            c.rect(40, yy, w - 80, row_h, fill=1, stroke=0)
        c.setFillColor(colors.HexColor('#14283c'))
        c.drawRightString(col_x[3] - 8, yy + 6, f'{_fa_price(total)} تومان')
        c.drawRightString(col_x[2] - 8, yy + 6, fa_num(qty))
        c.drawRightString(col_x[1] - 8, yy + 6, f'{_fa_price(price)} تومان')
        c.drawRightString(col_x[0] + 8, yy + 6, title[:60])

    # ---------- جمع‌بندی ----------
    yy = y - 24 - (len(items) + 1) * row_h
    c.setStrokeColor(LINE)
    c.line(40, yy, w - 40, yy)
    yy -= 8
    c.setFont('Vazir', 10)
    c.setFillColor(GRAY)
    c.drawRightString(w - 40, yy - 16, f'جمع کل: {_fa_price(order.total)} تومان')
    if order.discount > 0:
        c.drawRightString(w - 40, yy - 34, f'تخفیف: − {_fa_price(order.discount)} تومان')
    c.setFillColor(ORANGE)
    c.setFont('Vazir-Bold', 13)
    c.drawRightString(w - 40, yy - 58, f'مبلغ قابل پرداخت: {_fa_price(order.final_total)} تومان')

    # ---------- وضعیت ----------
    if order.status == 'paid':
        c.setFillColor(colors.HexColor('#16a34a'))
        c.setFont('Vazir-Bold', 11)
        c.drawRightString(w - 40, yy - 86, '✓ پرداخت شده')

    # ---------- فوتر ----------
    c.setStrokeColor(LINE)
    c.line(40, 90, w - 40, 90)
    c.setFillColor(GRAY)
    c.setFont('Vazir', 8.5)
    c.drawCentredString(w / 2, 70, f'{site.get("site_name") or "آکادمی آنلاین"} — {site.get("phone") or ""} — {site.get("email") or ""}')
    c.drawCentredString(w / 2, 52, 'این فاکتور به‌صورت الکترونیکی صادر شده و نیازی به مهر و امضا ندارد.')

    c.showPage()
    c.save()
    return buf.getvalue()
