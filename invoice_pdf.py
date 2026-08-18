# -*- coding: utf-8 -*-
"""تولید فاکتور PDF فارسی با فونت محلی، RTL صحیح و جدول چندصفحه‌ای."""
import os
from io import BytesIO
from xml.sax.saxutils import escape

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from jdates import jdate, jtime

_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'fonts')
_REGISTERED = False
FA_DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')

NAVY = colors.HexColor('#0d1f36')
ORANGE = colors.HexColor('#f2640c')
TEXT = colors.HexColor('#14283c')
MUTED = colors.HexColor('#64748b')
LINE = colors.HexColor('#e2e8f0')
SOFT = colors.HexColor('#f8fafc')
SUCCESS = colors.HexColor('#15803d')


def _register():
    global _REGISTERED
    if _REGISTERED:
        return
    regular = os.path.join(_FONTS_DIR, 'DejaVuSans.ttf')
    bold = os.path.join(_FONTS_DIR, 'DejaVuSans-Bold.ttf')
    if not os.path.isfile(regular) or not os.path.isfile(bold):
        raise FileNotFoundError('فونت‌های PDF در static/fonts موجود نیستند.')
    pdfmetrics.registerFont(TTFont('AcademyFa', regular))
    pdfmetrics.registerFont(TTFont('AcademyFa-Bold', bold))
    _REGISTERED = True


def _rtl(value):
    """شکل‌دهی حروف فارسی و تبدیل به ترتیب دیداری موردنیاز ReportLab."""
    text = str(value or '')
    return get_display(arabic_reshaper.reshape(text))


def fa_num(value):
    return str(value).translate(FA_DIGITS)


def _fa_price(value):
    try:
        return f'{int(value or 0):,}'.translate(FA_DIGITS)
    except (TypeError, ValueError):
        return fa_num(value)


def _paragraph(value, style):
    return Paragraph(escape(_rtl(value)), style)


def build_invoice_pdf(order, site, user, items):
    """ساخت فاکتور PDF و برگرداندن bytes.

    ``items`` شامل tupleهای ``(title, quantity, unit_price, line_total)`` است.
    جدول در سفارش‌های طولانی به صفحه بعد می‌رود و ردیف عنوان تکرار می‌شود.
    """
    _register()
    output = BytesIO()
    site_name = site.get('site_name') or 'آکادمی آنلاین'
    invoice_title = f'فاکتور سفارش {order.code}'

    doc = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=43 * mm, bottomMargin=25 * mm,
        title=invoice_title, author=site_name,
        subject='فاکتور فروش الکترونیکی',
    )

    normal = ParagraphStyle(
        'fa-normal', fontName='AcademyFa', fontSize=9.2, leading=15,
        textColor=TEXT, alignment=TA_RIGHT,
    )
    small = ParagraphStyle(
        'fa-small', parent=normal, fontSize=8, leading=12, textColor=MUTED,
    )
    bold = ParagraphStyle(
        'fa-bold', parent=normal, fontName='AcademyFa-Bold', fontSize=10,
    )
    heading = ParagraphStyle(
        'fa-heading', parent=bold, fontSize=12, leading=18, textColor=NAVY,
        spaceAfter=7,
    )
    center = ParagraphStyle(
        'fa-center', parent=normal, alignment=TA_CENTER,
    )
    center_bold = ParagraphStyle(
        'fa-center-bold', parent=bold, alignment=TA_CENTER,
    )

    def page_frame(canvas, _doc):
        width, height = A4
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, height - 34 * mm, width, 34 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont('AcademyFa-Bold', 17)
        canvas.drawRightString(width - 18 * mm, height - 14 * mm, _rtl(site_name))
        canvas.setFont('AcademyFa', 9)
        canvas.setFillColor(colors.HexColor('#cbd5e1'))
        canvas.drawRightString(width - 18 * mm, height - 22 * mm,
                               _rtl('فاکتور فروش الکترونیکی'))
        canvas.setFillColor(ORANGE)
        canvas.roundRect(18 * mm, height - 25 * mm, 48 * mm, 10 * mm,
                         2.5 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont('AcademyFa-Bold', 9)
        canvas.drawCentredString(42 * mm, height - 21.5 * mm, str(order.code))

        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, 17 * mm, width - 18 * mm, 17 * mm)
        footer_parts = [value for value in (site.get('phone'), site.get('email')) if value]
        footer = ' — '.join(footer_parts) or 'سند صادرشده از سامانه فروش'
        canvas.setFillColor(MUTED)
        canvas.setFont('AcademyFa', 7.5)
        canvas.drawCentredString(width / 2, 11 * mm, _rtl(footer))
        canvas.drawRightString(width - 18 * mm, 6 * mm,
                               _rtl(f'صفحه {fa_num(canvas.getPageNumber())}'))
        canvas.restoreState()

    story = []
    meta = Table([
        [_paragraph(f'{jdate(order.created_at)} — {jtime(order.created_at)}', normal),
         _paragraph('تاریخ صدور', small)],
        [Paragraph(escape(str(order.code)), normal), _paragraph('شماره سفارش', small)],
        [_paragraph('پرداخت‌شده' if order.status == 'paid' else order.status_fa, bold),
         _paragraph('وضعیت', small)],
    ], colWidths=[118 * mm, 48 * mm], hAlign='RIGHT')
    meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), SOFT),
        ('BOX', (0, 0), (-1, -1), 0.7, LINE),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TEXTCOLOR', (0, 2), (0, 2), SUCCESS if order.status == 'paid' else ORANGE),
    ]))
    story.extend([meta, Spacer(1, 8 * mm), _paragraph('مشخصات خریدار', heading)])

    customer_rows = [
        [_paragraph(user.name or '—', normal), _paragraph('نام خریدار', small)],
        [Paragraph(escape(user.email or '—'), normal), _paragraph('ایمیل', small)],
        [Paragraph(escape(fa_num(user.phone) if user.phone else '—'), normal),
         _paragraph('شماره تماس', small)],
    ]
    customer = Table(customer_rows, colWidths=[118 * mm, 48 * mm], hAlign='RIGHT')
    customer.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.7, LINE),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (1, 0), (1, -1), SOFT),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.extend([customer, Spacer(1, 8 * mm), _paragraph('شرح سفارش', heading)])

    table_data = [[
        _paragraph('مبلغ', center_bold), _paragraph('تعداد', center_bold),
        _paragraph('قیمت واحد', center_bold), _paragraph('شرح', bold),
    ]]
    for title, quantity, unit_price, line_total in items:
        table_data.append([
            _paragraph(f'{_fa_price(line_total)} تومان', center),
            Paragraph(escape(fa_num(quantity)), center),
            _paragraph(f'{_fa_price(unit_price)} تومان', center),
            _paragraph(title, normal),
        ])
    if len(table_data) == 1:
        table_data.append(['—', '—', '—', _paragraph('آیتمی ثبت نشده است', normal)])

    item_table = Table(table_data, repeatRows=1,
                       colWidths=[35 * mm, 18 * mm, 35 * mm, 78 * mm],
                       hAlign='RIGHT')
    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.7, LINE),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]
    for row_index in range(1, len(table_data)):
        if row_index % 2 == 0:
            style_commands.append(('BACKGROUND', (0, row_index), (-1, row_index), SOFT))
    item_table.setStyle(TableStyle(style_commands))
    story.extend([item_table, Spacer(1, 7 * mm)])

    totals = [
        [_paragraph(f'{_fa_price(order.total)} تومان', bold), _paragraph('جمع اقلام', normal)],
    ]
    if order.discount:
        totals.append([_paragraph(f'− {_fa_price(order.discount)} تومان', normal),
                       _paragraph('تخفیف', normal)])
    if getattr(order, 'shipping_cost', 0):
        totals.append([_paragraph(f'{_fa_price(order.shipping_cost)} تومان', normal),
                       _paragraph('هزینه ارسال', normal)])
    totals.append([_paragraph(f'{_fa_price(order.final_total)} تومان', bold),
                   _paragraph('مبلغ نهایی', bold)])
    totals_table = Table(totals, colWidths=[75 * mm, 45 * mm], hAlign='LEFT')
    totals_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.7, LINE),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, LINE),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fff7ed')),
        ('TEXTCOLOR', (0, -1), (-1, -1), ORANGE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))

    note = _paragraph(
        'این سند به‌صورت الکترونیکی توسط سامانه صادر شده است. '
        'وضعیت قطعی پرداخت از طریق کد سفارش در حساب کاربری قابل پیگیری است.',
        small,
    )
    story.extend([KeepTogether([totals_table, Spacer(1, 6 * mm), note])])
    doc.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    return output.getvalue()
