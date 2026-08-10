# -*- coding: utf-8 -*-
"""صفحه‌ساز بصری (شبیه Elementor) — ساخت، ویرایش لایو و رندر صفحات"""
import json
import re
import uuid
import glob
import os
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, g, jsonify, abort)
from models import db, Page, Course, Category, BlogPost, User

builder_bp = Blueprint('builder', __name__)

# ------------------------------------------------------------------
# تعریف ویجت‌ها (مثل ویجت‌های المنتور)
# ------------------------------------------------------------------
IMG_OPTIONS = []
for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'cover-*')) +
                glob.glob(os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'hero.*')) +
                glob.glob(os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'uploads', '*'))):
    IMG_OPTIONS.append(os.path.basename(f))

WIDGETS = {
    'current_course': dict(name='دوره فعلی (داینامیک)', icon='📖', cat='grid',
        desc='نمایش دوره‌ای که در حال مشاهده آن هستید — فقط در قالب صفحه دوره',
        fields=[dict(key='title', label='نمایش عنوان', type='checkbox'),
                dict(key='image', label='نمایش تصویر', type='checkbox'),
                dict(key='price', label='نمایش قیمت', type='checkbox'),
                dict(key='button', label='نمایش دکمه خرید', type='checkbox')]),
    'current_teacher': dict(name='مدرس فعلی (داینامیک)', icon='👨‍🏫', cat='grid',
        desc='نمایش مدرس صفحه — فقط در قالب صفحه مدرس',
        fields=[dict(key='name', label='نمایش نام', type='checkbox'),
                dict(key='avatar', label='نمایش آواتار', type='checkbox'),
                dict(key='courses', label='نمایش دوره‌ها', type='checkbox')]),
    'user_dashboard': dict(name='داشبورد دانشجو (داینامیک)', icon='📊', cat='grid',
        desc='دوره‌های من، فاکتورها، تیکت‌ها، کیف پول و اعلان‌های کاربر — برای قالب داشبورد',
        fields=[dict(key='courses', label='نمایش دوره‌های من', type='checkbox'),
                dict(key='wallet', label='نمایش کیف پول', type='checkbox'),
                dict(key='tickets', label='نمایش تیکت‌ها', type='checkbox'),
                dict(key='orders', label='نمایش فاکتورها', type='checkbox')]),

    # ---------- پایه ----------
    'heading': dict(name='تیتر', icon='T', cat='basic', fields=[
        dict(key='text', label='متن عنوان', type='text'),
        dict(key='tag', label='تگ سئو', type='select', options=[('h1', 'H1 — خیلی بزرگ'), ('h2', 'H2 — بزرگ'), ('h3', 'H3 — متوسط'), ('h4', 'H4 — کوچک'), ('h5', 'H5 — خیلی کوچک'), ('h6', 'H6 — ریز')]),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط'), ('left', 'چپ')]),
        dict(key='color', label='رنگ', type='color'),
        dict(key='mb', label='فاصله پایین', type='select', options=[('0', 'بدون'), ('8', '۸px'), ('16', '۱۶px'), ('24', '۲۴px')]),
    ]),
    'text': dict(name='متن', icon='¶', cat='basic', fields=[
        dict(key='content', label='محتوا', type='textarea'),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط'), ('left', 'چپ')]),
        dict(key='color', label='رنگ', type='color'),
        dict(key='size', label='اندازه فونت', type='select', options=[('14', '۱۴'), ('15', '۱۵'), ('16', '۱۶'), ('18', '۱۸')]),
    ]),
    'button': dict(name='دکمه', icon='▭', cat='basic', fields=[
        dict(key='text', label='متن دکمه', type='text'),
        dict(key='url', label='لینک', type='text'),
        dict(key='btn_style', label='استایل دکمه', type='select', options=[('primary', 'اصلی'), ('outline', 'خطی'), ('accent', 'نارنجی'), ('white', 'سفید'), ('ghost', 'خنثی')]),
        dict(key='size', label='سایز', type='select', options=[('sm', 'کوچک'), ('md', 'متوسط'), ('lg', 'بزرگ')]),
        dict(key='icon', label='آیکون (ایموجی)', type='text'),
        dict(key='hover', label='افکت هاور', type='select', options=[('lift', 'بالا آمدن'), ('glow', 'درخشش'), ('slide', 'لغزش'), ('none', 'بدون')]),
        dict(key='full', label='تمام عرض', type='checkbox'),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط'), ('left', 'چپ')]),
    ]),
    'image': dict(name='تصویر', icon='🖼', cat='basic', fields=[
        dict(key='src', label='تصویر', type='image'),
        dict(key='alt', label='متن جایگزین', type='text'),
        dict(key='radius', label='گردی گوشه', type='select', options=[('0', 'بدون'), ('10', '۱۰px'), ('16', '۱۶px'), ('24', '۲۴px'), ('50', 'دایره')]),
        dict(key='width', label='عرض', type='select', options=[('100', 'تمام عرض'), ('75', '۷۵٪'), ('60', '۶۰٪'), ('50', '۵۰٪'), ('400', '۴۰۰px')]),
        dict(key='filter', label='فیلتر رنگی', type='select', options=[('none', 'بدون فیلتر'), ('grayscale', 'سیاه‌وسفید'), ('sepia', 'سپیا'), ('blur', 'محو'), ('bright', 'روشن‌تر'), ('contrast', 'کنتراست بالا')]),
        dict(key='opacity', label='شفافیت', type='select', options=[('100', '۱۰۰٪'), ('80', '۸۰٪'), ('60', '۶۰٪'), ('40', '۴۰٪')]),
        dict(key='hover', label='بزرگ‌نمایی در هاور', type='checkbox'),
        dict(key='link', label='لینک', type='text'),
        dict(key='shadow', label='سایه', type='checkbox'),
    ]),
    'video': dict(name='ویدیو', icon='▶', cat='basic', fields=[
        dict(key='url', label='آدرس ویدیو (mp4 / یوتیوب / آپارات / ویمیو)', type='text'),
        dict(key='poster', label='تصویر پیش‌نمایش', type='image'),
        dict(key='autoplay', label='پخش خودکار', type='checkbox'),
        dict(key='radius', label='گردی گوشه', type='select', options=[('0', 'بدون'), ('12', '۱۲px'), ('20', '۲۰px')]),
    ]),
    'divider': dict(name='جداکننده', icon='─', cat='basic', fields=[
        dict(key='height', label='ضخامت', type='select', options=[('1', '۱px'), ('2', '۲px'), ('3', '۳px'), ('4', '۴px')]),
        dict(key='color', label='رنگ', type='color'),
        dict(key='line_style', label='نوع خط', type='select', options=[('solid', 'خط کامل'), ('dashed', 'خط چین'), ('dotted', 'نقطه‌چین'), ('gradient', 'گرادیانی')]),
        dict(key='width', label='عرض', type='select', options=[('100', '۱۰۰٪'), ('70', '۷۰٪'), ('50', '۵۰٪')]),
    ]),
    'spacer': dict(name='فاصله‌گذار', icon='⇕', cat='basic', fields=[
        dict(key='height', label='ارتفاع', type='number'),
    ]),
    'html': dict(name='HTML دلخواه', icon='<>', cat='basic', fields=[
        dict(key='code', label='کد HTML', type='textarea'),
    ]),
    'countdown': dict(name='شمارش معکوس', icon='⏱', cat='basic', fields=[
        dict(key='title', label='عنوان', type='text'),
        dict(key='target', label='تاریخ هدف (میلادی)', type='text'),
        dict(key='text', label='متن زیرین', type='text'),
    ]),
    # ---------- اسلایدر و رسانه ----------
    'slider': dict(name='اسلایدر', icon='◫', cat='media', fields=[
        dict(key='slides', label='اسلایدها', type='repeater', item_fields=[
            dict(key='img', label='تصویر اسلاید', type='image'),
            dict(key='title', label='عنوان', type='text'),
            dict(key='sub', label='زیرعنوان', type='textarea'),
            dict(key='btn_text', label='متن دکمه', type='text'),
            dict(key='btn_url', label='لینک دکمه', type='text'),
            dict(key='align', label='تراز متن', type='select', options=[('right', 'راست'), ('center', 'وسط'), ('left', 'چپ')]),
        ]),
        dict(key='height', label='ارتفاع', type='select', options=[('300', '۳۰۰px'), ('360', '۳۶۰px'), ('420', '۴۲۰px'), ('500', '۵۰۰px'), ('600', '۶۰۰px')]),
        dict(key='overlay', label='تیرگی لایه روی تصویر', type='select', options=[('45', '۴۵٪'), ('60', '۶۰٪'), ('70', '۷۰٪'), ('80', '۸۰٪'), ('90', '۹۰٪')]),
        dict(key='radius', label='گردی گوشه', type='select', options=[('0', 'بدون'), ('14', '۱۴px'), ('22', '۲۲px'), ('30', '۳۰px')]),
        dict(key='autoplay', label='پخش خودکار', type='checkbox'),
        dict(key='interval', label='فاصله (ثانیه)', type='number'),
        dict(key='dots', label='نقطه‌ها', type='checkbox'),
        dict(key='arrows', label='فلش‌ها', type='checkbox'),
        dict(key='swipe', label='کشیدن با انگشت (موبایل)', type='checkbox'),
    ]),
    'video_bg': dict(name='ویدیو پس‌زمینه', icon='◍', cat='media', fields=[
        dict(key='title', label='عنوان', type='text'),
        dict(key='sub', label='زیرعنوان', type='textarea'),
        dict(key='url', label='آدرس ویدیو', type='text'),
        dict(key='poster', label='تصویر پیش‌نمایش', type='image'),
        dict(key='btn_text', label='متن دکمه', type='text'),
        dict(key='btn_url', label='لینک دکمه', type='text'),
    ]),
    'price_history': dict(name='نمودار قیمت رقابتی', icon='📉', cat='woo', desc='نمودار تغییرات قیمت + مقایسه با سایر پلتفرم‌ها (مشابه دیجی‌کالا)', fields=[
        dict(key='title', label='عنوان', type='text'),
        dict(key='subtitle', label='زیرعنوان', type='text'),
        dict(key='item_type', label='نوع', type='select', options=[('course', 'دوره'), ('product', 'محصول')]),
        dict(key='item_id', label='آیتم (کد دوره/محصول)', type='number'),
        dict(key='show_compare', label='نمایش مقایسه با سایر پلتفرم‌ها', type='checkbox'),
    ]),
    'amazing_offer': dict(name='پیشنهاد شگفت‌انگیز', icon='⚡', cat='woo', desc='باکس فروش ویژه با تایمر معکوس نئون', fields=[
        dict(key='title', label='عنوان', type='text'),
        dict(key='sub', label='زیرعنوان', type='text'),
        dict(key='item_type', label='نوع', type='select', options=[('course', 'دوره'), ('product', 'محصول')]),
        dict(key='item_id', label='آیتم (کد)', type='number'),
        dict(key='hours', label='ساعت باقی‌مانده', type='number'),
        dict(key='btn_text', label='متن دکمه', type='text'),
        dict(key='btn_url', label='لینک دکمه', type='text'),
    ]),
    'review_pro': dict(name='نظرات پیشرفته', icon='⭐', cat='woo', desc='نظرات با نقاط قوت/ضعف و تأیید خرید (مشابه دیجی‌کالا)', fields=[
        dict(key='title', label='عنوان', type='text'),
        dict(key='limit', label='تعداد', type='number'),
        dict(key='item_type', label='نوع', type='select', options=[('course', 'دوره'), ('product', 'محصول')]),
        dict(key='item_id', label='آیتم (کد)', type='number'),
        dict(key='show_pros', label='نمایش نقاط قوت/ضعف', type='checkbox'),
        dict(key='show_verified', label='نمایش نشان تأیید خرید', type='checkbox'),
    ]),
    # ---------- گریدها (داده از سایت) ----------
    'courses': dict(name='گرید دوره‌ها', icon='▦', cat='grid', fields=[
        dict(key='title', label='عنوان بخش', type='text'),
        dict(key='subtitle', label='زیرعنوان', type='text'),
        dict(key='category', label='دسته‌بندی', type='category'),
        dict(key='limit', label='تعداد', type='select', options=[('4', '۴'), ('6', '۶'), ('8', '۸'), ('12', '۱۲')]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('2', '۲'), ('3', '۳'), ('4', '۴')]),
        dict(key='sort', label='مرتب‌سازی', type='select', options=[('newest', 'جدیدترین'), ('popular', 'پربازدیدترین'), ('cheap', 'ارزان‌ترین'), ('expensive', 'گران‌ترین')]),
        dict(key='show_price', label='نمایش قیمت', type='checkbox'),
    ]),
    'categories': dict(name='گرید دسته‌بندی‌ها', icon='▦', cat='grid', fields=[
        dict(key='title', label='عنوان بخش', type='text'),
        dict(key='limit', label='تعداد (۰ = همه)', type='number'),
        dict(key='columns', label='ستون‌ها', type='select', options=[('3', '۳'), ('4', '۴'), ('6', '۶')]),
    ]),
    'posts': dict(name='گرید مقالات', icon='▦', cat='grid', fields=[
        dict(key='title', label='عنوان بخش', type='text'),
        dict(key='limit', label='تعداد', type='select', options=[('3', '۳'), ('6', '۶')]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('3', '۳')]),
    ]),
    'teachers': dict(name='گرید اساتید', icon='▦', cat='grid', fields=[
        dict(key='title', label='عنوان بخش', type='text'),
        dict(key='limit', label='تعداد', type='number'),
        dict(key='columns', label='ستون‌ها', type='select', options=[('4', '۴'), ('3', '۳')]),
    ]),
    # ---------- پیشرفته ----------
    'feature': dict(name='ویژگی‌ها', icon='✧', cat='adv', fields=[
        dict(key='items', label='ویژگی‌ها', type='repeater', item_fields=[
            dict(key='icon', label='آیکون', type='text'),
            dict(key='title', label='عنوان', type='text'),
            dict(key='text', label='متن', type='textarea'),
        ]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('2', '۲'), ('3', '۳'), ('4', '۴'), ('6', '۶')]),
    ]),
    'stats': dict(name='آمار', icon='📊', cat='adv', fields=[
        dict(key='items', label='آمارها', type='repeater', item_fields=[
            dict(key='value', label='عدد', type='text'),
            dict(key='label', label='برچسب', type='text'),
        ]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('2', '۲'), ('3', '۳'), ('4', '۴')]),
    ]),
    'testimonials': dict(name='نظرات دانشجویان', icon='❝', cat='adv', fields=[
        dict(key='items', label='نظرات', type='repeater', item_fields=[
            dict(key='name', label='نام', type='text'),
            dict(key='role', label='نقش', type='text'),
            dict(key='text', label='متن نظر', type='textarea'),
            dict(key='stars', label='امتیاز', type='select', options=[('5', '۵'), ('4', '۴'), ('3', '۳')]),
            dict(key='color', label='رنگ آواتار', type='color'),
        ]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('1', '۱'), ('2', '۲'), ('3', '۳')]),
    ]),
    'success_stories': dict(name='داستان‌های موفقیت (داینامیک)', icon='🌟', cat='adv', fields=[
        dict(key='title', label='عنوان بخش', type='text'),
        dict(key='limit', label='تعداد', type='select', options=[('3', '۳'), ('4', '۴'), ('6', '۶')]),
    ]),
    'reviews': dict(name='نظرات واقعی دانشجویان (داینامیک)', icon='⭐', cat='adv', fields=[
        dict(key='title', label='عنوان بخش', type='text'),
        dict(key='limit', label='تعداد', type='select', options=[('3', '۳'), ('6', '۶'), ('9', '۹')]),
    ]),
    'exam_cta': dict(name='شبیه‌ساز آزمون (CTA)', icon='🎯', cat='adv', fields=[
        dict(key='title', label='عنوان', type='text'),
        dict(key='text', label='متن', type='textarea'),
    ]),
    'faq': dict(name='سوالات متداول', icon='?', cat='adv', fields=[
        dict(key='title', label='عنوان بخش', type='text'),
        dict(key='items', label='سوال‌ها', type='repeater', item_fields=[
            dict(key='q', label='سوال', type='text'),
            dict(key='a', label='پاسخ', type='textarea'),
        ]),
    ]),
    'pricing': dict(name='قیمت‌گذاری', icon='₿', cat='adv', fields=[
        dict(key='items', label='پلن‌ها', type='repeater', item_fields=[
            dict(key='name', label='نام پلن', type='text'),
            dict(key='price', label='قیمت', type='text'),
            dict(key='period', label='دوره', type='text'),
            dict(key='features', label='ویژگی‌ها (هر خط یکی)', type='textarea'),
            dict(key='btn_text', label='متن دکمه', type='text'),
            dict(key='btn_url', label='لینک دکمه', type='text'),
            dict(key='featured', label='ویژه', type='checkbox'),
        ]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('3', '۳'), ('4', '۴')]),
    ]),
    'cta': dict(name='دعوت به اقدام (CTA)', icon='⚡', cat='adv', fields=[
        dict(key='title', label='عنوان', type='text'),
        dict(key='text', label='متن', type='textarea'),
        dict(key='btn_text', label='متن دکمه', type='text'),
        dict(key='btn_url', label='لینک دکمه', type='text'),
        dict(key='cta_style', label='استایل بنر', type='select', options=[('gradient', 'گرادیانی'), ('dark', 'تیره'), ('primary', 'رنگ اصلی')]),
    ]),
    'newsletter': dict(name='خبرنامه', icon='✉', cat='adv', fields=[
        dict(key='title', label='عنوان', type='text'),
        dict(key='text', label='متن', type='textarea'),
    ]),
    'trust_badges': dict(name='نماد اعتماد', icon='🛡', cat='adv', fields=[
        dict(key='items', label='نمادها', type='repeater', item_fields=[
            dict(key='type', label='نوع نماد', type='select', options=[('enamad', 'نماد اعتماد الکترونیکی'), ('samandehi', 'ساماندهی'), ('etehadiye', 'اتحادیه کشوری'), ('digi', 'نماد سفارشی')]),
            dict(key='code', label='کد (اختیاری)', type='text'),
        ]),
        dict(key='size', label='اندازه', type='select', options=[('60', 'کوچک'), ('80', 'متوسط'), ('100', 'بزرگ')]),
    ]),
    # ---------- هدر ----------
    'topbar': dict(name='نوار بالایی هدر', icon='☰', cat='header', fields=[
        dict(key='right', label='لینک‌های راست', type='repeater', item_fields=[
            dict(key='text', label='متن', type='text'),
            dict(key='url', label='لینک', type='text'),
            dict(key='cls', label='کلاس', type='text'),
        ]),
        dict(key='left', label='لینک‌های چپ', type='repeater', item_fields=[
            dict(key='text', label='متن', type='text'),
            dict(key='url', label='لینک', type='text'),
            dict(key='cls', label='کلاس', type='text'),
        ]),
    ]),
    'logo': dict(name='لوگو', icon='◈', cat='header', fields=[
        dict(key='text', label='نام برند', type='text'),
        dict(key='icon', label='آیکون', type='text'),
        dict(key='sub', label='زیرنویس', type='text'),
    ]),
    'search': dict(name='جستجو', icon='🔍', cat='header', fields=[
        dict(key='placeholder', label='متن راهنما', type='text'),
        dict(key='show_cat', label='انتخاب دسته', type='checkbox'),
    ]),
    'category_mega': dict(name='منوی مگا دسته‌ها', icon='▤', cat='header', fields=[
        dict(key='button', label='متن دکمه', type='text'),
        dict(key='columns', label='ستون‌های منو', type='select', options=[('3', '۳'), ('4', '۴')]),
    ]),
    'category_strip': dict(name='نوار دسته‌ها', icon='▥', cat='header', fields=[
        dict(key='limit', label='تعداد', type='number'),
    ]),
    'icon_link': dict(name='آیکون لینک', icon='🔗', cat='header', fields=[
        dict(key='icon', label='آیکون', type='text'),
        dict(key='label', label='برچسب', type='text'),
        dict(key='url', label='لینک', type='text'),
        dict(key='badge', label='نشانگر عدد', type='select', options=[('', 'بدون'), ('cart', 'سبد خرید'), ('fav', 'علاقه‌مندی'), ('ticket', 'تیکت')]),
    ]),
    'user_menu': dict(name='منوی کاربر', icon='👤', cat='header', fields=[]),
    'nav_menu': dict(name='منوی ناوبری', icon='☷', cat='header', fields=[
        dict(key='links', label='لینک‌ها', type='repeater', item_fields=[
            dict(key='text', label='متن', type='text'),
            dict(key='url', label='لینک', type='text'),
        ]),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط')]),
    ]),
    # ---------- فوتر ----------
    'footer_about': dict(name='معرفی فوتر', icon='🏛', cat='footer', fields=[
        dict(key='desc', label='توضیحات', type='textarea'),
        dict(key='socials', label='نمایش شبکه‌های اجتماعی', type='checkbox'),
    ]),
    'link_list': dict(name='لیست لینک‌ها', icon='☰', cat='footer', fields=[
        dict(key='title', label='عنوان', type='text'),
        dict(key='links', label='لینک‌ها', type='repeater', item_fields=[
            dict(key='text', label='متن', type='text'),
            dict(key='url', label='لینک', type='text'),
        ]),
    ]),
    'contact_info': dict(name='اطلاعات تماس', icon='✆', cat='footer', fields=[
        dict(key='phone', label='تلفن', type='text'),
        dict(key='email', label='ایمیل', type='text'),
        dict(key='address', label='آدرس', type='textarea'),
        dict(key='hours', label='ساعات پاسخگویی', type='text'),
    ]),
    'socials': dict(name='شبکه‌های اجتماعی', icon='✈', cat='footer', fields=[
        dict(key='items', label='شبکه‌ها', type='repeater', item_fields=[
            dict(key='icon', label='آیکون', type='text'),
            dict(key='url', label='لینک', type='text'),
        ]),
    ]),
    'mobile_item': dict(name='آیتم منوی موبایل', icon='▣', cat='footer', fields=[
        dict(key='icon', label='آیکون', type='text'),
        dict(key='label', label='برچسب', type='text'),
        dict(key='url', label='لینک', type='text'),
    ]),
    'mobile_link': dict(name='لینک منوی کشویی موبایل', icon='🔗', cat='footer',
        desc='لینک داخل منوی کشویی موبایل — فقط در موبایل نمایش داده می‌شود', fields=[
        dict(key='icon', label='آیکون', type='text'),
        dict(key='label', label='برچسب', type='text'),
        dict(key='url', label='لینک', type='text'),
        dict(key='badge', label='بج (اختیاری)', type='text'),
    ]),

    # ================= پایه (تکمیلی) =================
    'inner_section': dict(name='بخش داخلی (ستون تودرتو)', icon='⊞', cat='basic', fields=[
        dict(key='title', label='عنوان (اختیاری)', type='text'),
        dict(key='widths', label='عرض ستون‌ها (مثلا: 1fr 2fr)', type='text'),
        dict(key='gap', label='فاصله ستون‌ها (px)', type='number'),
        dict(key='py', label='پدینگ داخلی (px)', type='number'),
        dict(key='bg', label='رنگ پس‌زمینه', type='color'),
        dict(key='radius', label='گردی گوشه (px)', type='number'),
    ]),
    'text_editor': dict(name='ویرایشگر متن (مثل ورد)', icon='✎', cat='basic', fields=[
        dict(key='content', label='محتوا', type='richtext'),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط'), ('left', 'چپ'), ('justify', 'هم‌تراز')]),
        dict(key='color', label='رنگ متن', type='color'),
    ]),
    'google_maps': dict(name='گوگل مپ', icon='🗺', cat='basic', fields=[
        dict(key='query', label='آدرس یا مختصات', type='text'),
        dict(key='height', label='ارتفاع', type='select', options=[('300', '۳۰۰px'), ('400', '۴۰۰px'), ('500', '۵۰۰px')]),
        dict(key='radius', label='گردی گوشه', type='select', options=[('0', 'بدون'), ('12', '۱۲px'), ('20', '۲۰px')]),
    ]),
    'icon': dict(name='آیکون', icon='★', cat='basic', fields=[
        dict(key='icon', label='آیکون (ایموجی)', type='text'),
        dict(key='size', label='اندازه', type='select', options=[('32', '۳۲'), ('48', '۴۸'), ('64', '۶۴'), ('80', '۸۰'), ('100', '۱۰۰')]),
        dict(key='color', label='رنگ', type='color'),
        dict(key='bg', label='رنگ پس‌زمینه', type='color'),
        dict(key='radius', label='گردی گوشه', type='select', options=[('0', 'بدون'), ('12', '۱۲px'), ('24', '۲۴px'), ('50', 'دایره')]),
        dict(key='link', label='لینک', type='text'),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط'), ('left', 'چپ')]),
    ]),

    # ================= عمومی =================
    'image_box': dict(name='جعبه تصویر', icon='▣', cat='general', fields=[
        dict(key='image', label='تصویر', type='image'),
        dict(key='title', label='عنوان', type='text'),
        dict(key='text', label='متن توضیحات', type='textarea'),
        dict(key='link', label='لینک', type='text'),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط')]),
        dict(key='hover', label='افکت هاور (بزرگ‌نمایی تصویر)', type='checkbox'),
    ]),
    'icon_box': dict(name='جعبه آیکون', icon='◈', cat='general', fields=[
        dict(key='icon', label='آیکون', type='text'),
        dict(key='title', label='عنوان', type='text'),
        dict(key='text', label='متن توضیحات', type='textarea'),
        dict(key='icon_color', label='رنگ آیکون', type='color'),
        dict(key='bg', label='رنگ پس‌زمینه', type='color'),
        dict(key='link', label='لینک', type='text'),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط')]),
    ]),
    'progress_bar': dict(name='نوار پیشرفت', icon='▤', cat='general', fields=[
        dict(key='items', label='مهارت‌ها', type='repeater', item_fields=[
            dict(key='label', label='عنوان', type='text'),
            dict(key='percent', label='درصد', type='number'),
            dict(key='color', label='رنگ', type='color'),
        ]),
        dict(key='height', label='ضخامت نوار', type='select', options=[('8', '۸px'), ('12', '۱۲px'), ('16', '۱۶px')]),
        dict(key='animate', label='انیمیشن پر شدن', type='checkbox'),
    ]),
    'counter': dict(name='شمارنده', icon='🔢', cat='general', fields=[
        dict(key='items', label='شمارنده‌ها', type='repeater', item_fields=[
            dict(key='target', label='عدد هدف', type='number'),
            dict(key='prefix', label='پیشوند', type='text'),
            dict(key='suffix', label='پسوند', type='text'),
            dict(key='label', label='برچسب', type='text'),
        ]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('2', '۲'), ('3', '۳'), ('4', '۴')]),
        dict(key='color', label='رنگ اعداد', type='color'),
    ]),
    'icon_list': dict(name='لیست آیکونی', icon='☰', cat='general', fields=[
        dict(key='items', label='آیتم‌ها', type='repeater', item_fields=[
            dict(key='icon', label='آیکون', type='text'),
            dict(key='text', label='متن', type='text'),
            dict(key='url', label='لینک', type='text'),
        ]),
        dict(key='icon_color', label='رنگ آیکون‌ها', type='color'),
        dict(key='columns', label='ستون‌ها', type='select', options=[('1', '۱'), ('2', '۲'), ('3', '۳')]),
    ]),
    'tabs': dict(name='تب‌ها', icon='▭', cat='general', fields=[
        dict(key='items', label='تب‌ها', type='repeater', item_fields=[
            dict(key='title', label='عنوان تب', type='text'),
            dict(key='content', label='محتوا', type='textarea'),
        ]),
        dict(key='orientation', label='جهت', type='select', options=[('horizontal', 'افقی'), ('vertical', 'عمودی')]),
        dict(key='active', label='تب فعال اولیه', type='number'),
    ]),
    'accordion': dict(name='آکاردئون', icon='≣', cat='general', fields=[
        dict(key='items', label='آیتم‌ها', type='repeater', item_fields=[
            dict(key='title', label='عنوان', type='text'),
            dict(key='content', label='محتوا', type='textarea'),
        ]),
        dict(key='multi', label='باز بودن همزمان چند آیتم', type='checkbox'),
        dict(key='first_open', label='باز بودن آیتم اول', type='checkbox'),
    ]),
    'toggle': dict(name='توگل', icon='☰', cat='general', fields=[
        dict(key='items', label='آیتم‌ها', type='repeater', item_fields=[
            dict(key='title', label='عنوان', type='text'),
            dict(key='content', label='محتوا', type='textarea'),
        ]),
    ]),
    'alert': dict(name='هشدار', icon='⚠', cat='general', fields=[
        dict(key='type', label='نوع', type='select', options=[('success', '✅ موفقیت'), ('error', '❌ خطا'), ('warning', '⚠️ هشدار'), ('info', '💡 اطلاع‌رسانی')]),
        dict(key='title', label='عنوان', type='text'),
        dict(key='content', label='متن', type='textarea'),
        dict(key='dismiss', label='قابل بستن', type='checkbox'),
    ]),
    'soundcloud': dict(name='ساندکلاود', icon='♪', cat='general', fields=[
        dict(key='url', label='لینک ساندکلاود', type='text'),
        dict(key='height', label='ارتفاع', type='select', options=[('166', 'کوچک'), ('300', 'متوسط'), ('450', 'بزرگ')]),
        dict(key='autoplay', label='پخش خودکار', type='checkbox'),
    ]),
    'shortcode': dict(name='شورت‌کد', icon='[]', cat='general', fields=[
        dict(key='code', label='کد شورت‌کد', type='textarea'),
    ]),
    'menu_anchor': dict(name='لنگرگاه صفحه', icon='⚓', cat='general', fields=[
        dict(key='id', label='شناسه لنگر (بدون #)', type='text'),
        dict(key='title', label='عنوان (اختیاری)', type='text'),
    ]),
    'social_icons': dict(name='آیکون‌های اجتماعی', icon='✈', cat='general', fields=[
        dict(key='items', label='شبکه‌ها', type='repeater', item_fields=[
            dict(key='network', label='شبکه', type='select', options=[
                ('telegram', 'تلگرام'), ('instagram', 'اینستاگرام'), ('whatsapp', 'واتساپ'),
                ('youtube', 'یوتیوب'), ('linkedin', 'لینکدین'), ('twitter', 'توییتر'), ('facebook', 'فیسبوک')]),
            dict(key='url', label='لینک', type='text'),
        ]),
        dict(key='size', label='اندازه', type='select', options=[('36', 'کوچک'), ('44', 'متوسط'), ('52', 'بزرگ')]),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط'), ('left', 'چپ')]),
    ]),

    # ================= حرفه‌ای (Pro) =================
    'form': dict(name='فرم‌ساز', icon='▣', cat='pro', fields=[
        dict(key='fields', label='فیلدها', type='repeater', item_fields=[
            dict(key='label', label='برچسب', type='text'),
            dict(key='type', label='نوع', type='select', options=[
                ('text', 'متن'), ('email', 'ایمیل'), ('tel', 'تلفن'), ('textarea', 'متن بلند'), ('select', 'انتخابی')]),
            dict(key='options', label='گزینه‌ها (با کاما)', type='text'),
            dict(key='required', label='الزامی', type='checkbox'),
        ]),
        dict(key='button_text', label='متن دکمه', type='text'),
        dict(key='align', label='تراز دکمه', type='select', options=[('right', 'راست'), ('center', 'وسط')]),
        dict(key='success_msg', label='پیام موفقیت', type='text'),
        dict(key='to', label='مقصد', type='select', options=[('contact', 'پیام تماس'), ('newsletter', 'خبرنامه')]),
    ]),
    'portfolio': dict(name='پورتفولیو', icon='▦', cat='pro', fields=[
        dict(key='items', label='نمونه‌کارها', type='repeater', item_fields=[
            dict(key='image', label='تصویر', type='image'),
            dict(key='title', label='عنوان', type='text'),
            dict(key='category', label='دسته', type='text'),
            dict(key='desc', label='توضیحات', type='textarea'),
            dict(key='url', label='لینک', type='text'),
        ]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('2', '۲'), ('3', '۳'), ('4', '۴')]),
        dict(key='filter', label='نمایش فیلتر دسته‌بندی', type='checkbox'),
    ]),
    'gallery': dict(name='گالری تصاویر', icon='▧', cat='pro', fields=[
        dict(key='items', label='تصاویر', type='repeater', item_fields=[
            dict(key='image', label='تصویر', type='image'),
            dict(key='caption', label='زیرنویس', type='text'),
        ]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('2', '۲'), ('3', '۳'), ('4', '۴'), ('6', '۶')]),
        dict(key='lightbox', label='بزرگ‌نمایی با کلیک (لایت‌باکس)', type='checkbox'),
        dict(key='radius', label='گردی گوشه', type='select', options=[('0', 'بدون'), ('10', '۱۰px'), ('16', '۱۶px')]),
    ]),
    'price_list': dict(name='لیست قیمت', icon='₺', cat='pro', fields=[
        dict(key='items', label='آیتم‌ها', type='repeater', item_fields=[
            dict(key='title', label='عنوان', type='text'),
            dict(key='desc', label='توضیحات', type='text'),
            dict(key='price', label='قیمت', type='text'),
            dict(key='image', label='تصویر (اختیاری)', type='image'),
        ]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('1', '۱'), ('2', '۲')]),
    ]),
    'flip_box': dict(name='باکس چرخشی', icon='⇄', cat='pro', fields=[
        dict(key='front_title', label='عنوان رو', type='text'),
        dict(key='front_text', label='متن رو', type='textarea'),
        dict(key='front_icon', label='آیکون رو', type='text'),
        dict(key='front_bg', label='رنگ پس‌زمینه رو', type='color'),
        dict(key='back_title', label='عنوان پشت', type='text'),
        dict(key='back_text', label='متن پشت', type='textarea'),
        dict(key='back_bg', label='رنگ پس‌زمینه پشت', type='color'),
        dict(key='btn_text', label='متن دکمه پشت', type='text'),
        dict(key='btn_url', label='لینک دکمه', type='text'),
        dict(key='height', label='ارتفاع', type='select', options=[('240', '۲۴۰px'), ('300', '۳۰۰px'), ('360', '۳۶۰px')]),
    ]),
    'animated_heading': dict(name='عنوان متحرک', icon='✴', cat='pro', fields=[
        dict(key='text', label='متن ثابت', type='text'),
        dict(key='words', label='کلمات متحرک (با کاما)', type='text'),
        dict(key='tag', label='تگ', type='select', options=[('h1', 'H1'), ('h2', 'H2'), ('h3', 'H3')]),
        dict(key='color', label='رنگ کلمه متحرک', type='color'),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط')]),
    ]),
    'share_buttons': dict(name='اشتراک‌گذاری', icon='⇪', cat='pro', fields=[
        dict(key='items', label='شبکه‌ها', type='repeater', item_fields=[
            dict(key='network', label='شبکه', type='select', options=[
                ('telegram', 'تلگرام'), ('whatsapp', 'واتساپ'), ('twitter', 'توییتر'),
                ('facebook', 'فیسبوک'), ('linkedin', 'لینکدین'), ('email', 'ایمیل'), ('copy', 'کپی لینک')]),
        ]),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط')]),
    ]),
    'code_highlight': dict(name='کد برنامه‌نویسی', icon='</>', cat='pro', fields=[
        dict(key='code', label='کد', type='textarea'),
        dict(key='language', label='زبان', type='select', options=[
            ('python', 'پایتون'), ('javascript', 'جاوااسکریپت'), ('html', 'HTML'),
            ('css', 'CSS'), ('sql', 'SQL'), ('text', 'متن ساده')]),
        dict(key='numbers', label='شماره خطوط', type='checkbox'),
    ]),
    'dynamic_data': dict(name='تگ‌های پویا', icon='⚡', cat='pro', fields=[
        dict(key='items', label='مقادیر', type='repeater', item_fields=[
            dict(key='key', label='مقدار', type='select', options=[
                ('site_name', 'نام سایت'), ('site_desc', 'شعار سایت'), ('course_count', 'تعداد دوره‌ها'),
                ('student_count', 'تعداد دانشجویان'), ('teacher_count', 'تعداد اساتید'),
                ('user_name', 'نام کاربر'), ('user_phone', 'شماره کاربر'), ('user_email', 'ایمیل کاربر'),
                ('year', 'سال جاری'), ('date', 'تاریخ امروز')]),
        ]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('2', '۲'), ('3', '۳'), ('4', '۴')]),
    ]),

    # ================= قالب‌ساز =================
    'site_logo': dict(name='لوگوی سایت', icon='◈', cat='theme', fields=[
        dict(key='icon', label='آیکون', type='text'),
        dict(key='sub', label='زیرنویس', type='text'),
    ]),
    'site_title': dict(name='عنوان سایت', icon='T', cat='theme', fields=[
        dict(key='tag', label='تگ', type='select', options=[('h1', 'H1'), ('h2', 'H2'), ('h3', 'H3'), ('h4', 'H4')]),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط')]),
        dict(key='color', label='رنگ', type='color'),
    ]),
    'post_title': dict(name='عنوان پست', icon='H', cat='theme', fields=[
        dict(key='tag', label='تگ', type='select', options=[('h1', 'H1'), ('h2', 'H2'), ('h3', 'H3')]),
        dict(key='fallback', label='متن جایگزین (وقتی پستی نیست)', type='text'),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط')]),
    ]),
    'post_content': dict(name='محتوای پست', icon='¶', cat='theme', fields=[
        dict(key='excerpt', label='فقط خلاصه', type='checkbox'),
        dict(key='fallback', label='متن جایگزین', type='textarea'),
    ]),
    'featured_image': dict(name='تصویر شاخص', icon='🖼', cat='theme', fields=[
        dict(key='radius', label='گردی گوشه', type='select', options=[('0', 'بدون'), ('12', '۱۲px'), ('20', '۲۰px')]),
        dict(key='fallback', label='تصویر جایگزین', type='image'),
    ]),
    'post_info': dict(name='اطلاعات پست', icon='ℹ', cat='theme', fields=[
        dict(key='show_date', label='تاریخ', type='checkbox'),
        dict(key='show_author', label='نویسنده', type='checkbox'),
        dict(key='show_readtime', label='زمان مطالعه', type='checkbox'),
        dict(key='show_views', label='بازدید', type='checkbox'),
    ]),
    'post_comments': dict(name='دیدگاه‌های پست', icon='💬', cat='theme', fields=[
        dict(key='show_form', label='نمایش فرم دیدگاه', type='checkbox'),
        dict(key='fallback', label='متن جایگزین', type='text'),
    ]),
    'author_box': dict(name='باکس نویسنده', icon='👤', cat='theme', fields=[
        dict(key='fallback', label='متن جایگزین', type='text'),
    ]),

    # ================= فروشگاهی =================
    'products': dict(name='محصولات (دوره‌ها)', icon='🛍', cat='woo', fields=[
        dict(key='title', label='عنوان بخش', type='text'),
        dict(key='filter', label='فیلتر', type='select', options=[
            ('all', 'همه'), ('sale', 'تخفیف‌دار'), ('featured', 'ویژه'), ('popular', 'پرفروش‌ترین')]),
        dict(key='limit', label='تعداد', type='select', options=[('4', '۴'), ('8', '۸'), ('12', '۱۲')]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('2', '۲'), ('3', '۳'), ('4', '۴')]),
        dict(key='show_price', label='نمایش قیمت', type='checkbox'),
    ]),
    'add_to_cart': dict(name='افزودن به سبد', icon='🛒', cat='woo', fields=[
        dict(key='course', label='دوره', type='course'),
        dict(key='text', label='متن دکمه', type='text'),
        dict(key='btn_style', label='استایل دکمه', type='select', options=[('primary', 'اصلی'), ('accent', 'نارنجی'), ('outline', 'خطی')]),
        dict(key='align', label='تراز', type='select', options=[('right', 'راست'), ('center', 'وسط')]),
    ]),
    'cart_widget': dict(name='سبد خرید', icon='🧺', cat='woo', fields=[
        dict(key='title', label='عنوان', type='text'),
        dict(key='show_total', label='نمایش مبلغ کل', type='checkbox'),
    ]),
    'checkout_widget': dict(name='تسویه حساب', icon='💳', cat='woo', fields=[
        dict(key='title', label='عنوان', type='text'),
        dict(key='text', label='متن', type='textarea'),
    ]),
    'my_account': dict(name='حساب کاربری', icon='👥', cat='woo', fields=[
        dict(key='title', label='عنوان', type='text'),
    ]),
    'product_details': dict(name='جزئیات محصول', icon='🏷', cat='woo', fields=[
        dict(key='course', label='دوره', type='course'),
        dict(key='show_price', label='قیمت', type='checkbox'),
        dict(key='show_teacher', label='مدرس', type='checkbox'),
        dict(key='show_rating', label='امتیاز', type='checkbox'),
        dict(key='show_students', label='تعداد دانشجو', type='checkbox'),
        dict(key='show_meta', label='سطح/مدت/دسته', type='checkbox'),
    ]),
}


# ============================================================
# کتابخانه قالب‌های آماده (Section Library) + قالب‌های صفحه
# ============================================================
# -*- coding: utf-8 -*-
SECTION_TEMPLATES = {
    'hero_classic': dict(name='هیرو کلاسیک', icon='🏠', desc='اسلایدر تمام‌عرض با متن و دکمه', rows=[{'id': 'st_hero', 'settings': {'gap': 0, 'py': 0}, 'cols': [[{'id': 'st_h1', 'type': 'slider', 'data': {'height': '430', 'autoplay': True, 'interval': '5', 'dots': True, 'arrows': True, 'slides': [{'img': 'hero.webp', 'title': 'عنوان جذاب اسلایدر', 'sub': 'توضیح کوتاه', 'btn_text': 'مشاهده دوره‌ها', 'btn_url': '/courses', 'align': 'right'}, {'img': 'cover-python.webp', 'title': 'دومین اسلاید', 'sub': 'توضیح دوم', 'btn_text': 'شروع', 'btn_url': '/courses', 'align': 'center'}]}}]]}]),
    'hero_text': dict(name='هیرو متنی', icon='📝', desc='تیتر بزرگ + دکمه CTA', rows=[{'id': 'st_ht', 'settings': {'gap': 0, 'py': 70}, 'cols': [[{'id': 'st_t1', 'type': 'heading', 'data': {'text': 'عنوان اصلی صفحه شما', 'tag': 'h1', 'align': 'center', 'mb': '12'}}, {'id': 'st_t2', 'type': 'text', 'data': {'content': 'توضیح کوتاه درباره کسب‌وکار شما.', 'align': 'center', 'size': '16'}}, {'id': 'st_t3', 'type': 'button', 'data': {'text': 'شروع کنید', 'url': '/courses', 'style': 'primary', 'size': 'lg', 'align': 'center'}}]]}]),
    'features': dict(name='بخش ویژگی‌ها', icon='✨', desc='شبکه ۳ ستونه ویژگی‌ها', rows=[{'id': 'st_feat', 'settings': {'gap': 22, 'py': 60}, 'cols': [[{'id': 'st_f1', 'type': 'feature', 'data': {'columns': '3', 'items': [{'icon': '🎯', 'title': 'ویژگی اول', 'text': 'توضیح اول'}, {'icon': '⚡', 'title': 'ویژگی دوم', 'text': 'توضیح دوم'}, {'icon': '🛡️', 'title': 'ویژگی سوم', 'text': 'توضیح سوم'}]}}]]}]),
    'courses_grid': dict(name='گرید دوره‌ها', icon='📚', desc='نمایش دوره‌های آموزشی', rows=[{'id': 'st_cg', 'settings': {'gap': 24, 'py': 60}, 'cols': [[{'id': 'st_c1', 'type': 'courses', 'data': {'title': 'دوره‌های آموزشی', 'limit': '4', 'columns': '4', 'sort': 'newest'}}]]}]),
    'stats': dict(name='بخش آمار', icon='📊', desc='آمارهای سایت با پس‌زمینه رنگی', rows=[{'id': 'st_st', 'settings': {'gap': 0, 'py': 50}, 'cols': [[{'id': 'st_s1', 'type': 'stats', 'data': {'columns': '4', 'items': [{'value': '۱۵۰+', 'label': 'دوره'}, {'value': '۵۰,۰۰۰+', 'label': 'دانشجو'}, {'value': '۲,۰۰۰+', 'label': 'ساعت'}, {'value': '٪۹۸', 'label': 'رضایت'}]}}]]}]),
    'testimonials': dict(name='نظرات مشتریان', icon='💬', desc='نمایش ۳ نظر', rows=[{'id': 'st_tm', 'settings': {'gap': 22, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[{'id': 'st_t1', 'type': 'testimonials', 'data': {'columns': '3', 'items': [{'name': 'علی محمدی', 'role': 'دانشجو', 'stars': '5', 'color': '#7c3aed', 'text': 'تجربه عالی بود.'}, {'name': 'فاطمه', 'role': 'دانشجو', 'stars': '5', 'color': '#059669', 'text': 'کیفیت عالی.'}, {'name': 'رضا', 'role': 'کاربر', 'stars': '4', 'color': '#db2777', 'text': 'پشتیبانی خوب.'}]}}]]}]),
    'pricing': dict(name='قیمت‌گذاری', icon='💎', desc='جدول مقایسه پلن‌ها', rows=[{'id': 'st_pr', 'settings': {'gap': 24, 'py': 60}, 'cols': [[{'id': 'st_p1', 'type': 'pricing', 'data': {'columns': '3', 'items': [{'name': 'پایه', 'price': 'رایگان', 'period': 'برای همیشه', 'features': 'امکانات پایه', 'btn_text': 'شروع', 'btn_url': '/auth/register'}, {'name': 'حرفه‌ای', 'price': '۲۹۰,۰۰۰', 'period': 'ماهانه', 'features': 'همه امکانات', 'btn_text': 'انتخاب', 'btn_url': '/auth/register', 'featured': True}, {'name': 'سازمانی', 'price': 'تماس بگیرید', 'period': 'سالیانه', 'features': 'آموزش تیمی', 'btn_text': 'ارتباط', 'btn_url': '/contact'}]}}]]}]),
    'cta': dict(name='دعوت به اقدام', icon='🚀', desc='بنر CTA گرادیانی', rows=[{'id': 'st_cta', 'settings': {'gap': 0, 'py': 30}, 'cols': [[{'id': 'st_c2', 'type': 'cta', 'data': {'title': 'آماده شروع هستید؟ 🚀', 'text': 'همین حالا شروع کنید.', 'btn_text': 'ثبت‌نام رایگان', 'btn_url': '/auth/register'}}]]}]),
    'faq': dict(name='سوالات متداول', icon='❓', desc='آکاردئون سوالات', rows=[{'id': 'st_fq', 'settings': {'gap': 0, 'py': 60}, 'cols': [[{'id': 'st_f2', 'type': 'faq', 'data': {'title': 'پرسش‌های متداول', 'items': [{'q': 'سوال اول؟', 'a': 'پاسخ اول.'}, {'q': 'سوال دوم؟', 'a': 'پاسخ دوم.'}, {'q': 'سوال سوم؟', 'a': 'پاسخ سوم.'}]}}]]}]),
    'newsletter': dict(name='خبرنامه', icon='✉️', desc='فرم عضویت خبرنامه', rows=[{'id': 'st_nl', 'settings': {'gap': 0, 'py': 20}, 'cols': [[{'id': 'st_n1', 'type': 'newsletter', 'data': {}}]]}]),
    'trust': dict(name='نمادهای اعتماد', icon='🛡️', desc='نماد اعتماد + پرداخت', rows=[{'id': 'st_tr', 'settings': {'gap': 0, 'py': 40, 'bg': '#ffffff', 'radius': 20}, 'cols': [[{'id': 'st_t2', 'type': 'trust_badges', 'data': {'size': '76', 'items': [{'type': 'enamad'}, {'type': 'samandehi'}, {'type': 'etehadiye'}]}}]]}]),
    'contact_form': dict(name='فرم تماس', icon='📨', desc='فرم تماس با فیلدهای آماده', rows=[{'id': 'st_cf', 'settings': {'gap': 0, 'py': 60}, 'cols': [[{'id': 'st_c3', 'type': 'form', 'data': {'button_text': 'ارسال', 'fields': [{'label': 'نام', 'type': 'text', 'required': True}, {'label': 'ایمیل', 'type': 'email', 'required': True}, {'label': 'پیام', 'type': 'textarea', 'required': True}]}}]]}]),
    'countdown_offer': dict(name='پیشنهاد محدود', icon='⏰', desc='شمارش معکوس + دکمه', rows=[{'id': 'st_co', 'settings': {'gap': 0, 'py': 50}, 'cols': [[{'id': 'st_c4', 'type': 'countdown', 'data': {'title': 'پیشنهاد ویژه', 'text': 'تا پایان تخفیف عجله کنید!'}}, {'id': 'st_c5', 'type': 'button', 'data': {'text': 'خرید با تخفیف', 'url': '/courses', 'style': 'accent', 'size': 'lg', 'align': 'center'}}]]}]),
    'split_section': dict(name='بخش دونیمه', icon='◫', desc='تصویر + متن کنار هم', rows=[{'id': 'st_ss', 'settings': {'gap': 30, 'py': 60, 'widths': '1fr 1fr'}, 'cols': [[{'id': 'st_s3', 'type': 'image', 'data': {'src': 'hero.webp', 'radius': '16', 'shadow': True}}], [{'id': 'st_s4', 'type': 'heading', 'data': {'text': 'عنوان بخش', 'tag': 'h2', 'mb': '10'}}, {'id': 'st_s5', 'type': 'text', 'data': {'content': 'توضیحات این بخش.'}}, {'id': 'st_s6', 'type': 'button', 'data': {'text': 'بیشتر بدانید', 'url': '/about', 'style': 'outline'}}]]}]),
    'gallery_section': dict(name='گالری تصاویر', icon='🖼️', desc='شبکه تصاویر با لایت‌باکس', rows=[{'id': 'st_gl', 'settings': {'gap': 0, 'py': 60}, 'cols': [[{'id': 'st_g1', 'type': 'gallery', 'data': {'columns': '3', 'lightbox': True, 'items': [{'image': 'cover-python.webp', 'caption': 'پایتون'}, {'image': 'cover-django.webp', 'caption': 'جنگو'}, {'image': 'cover-react.webp', 'caption': 'ری‌اکت'}, {'image': 'cover-flask.webp', 'caption': 'فلاسک'}, {'image': 'cover-ml.webp', 'caption': 'ML'}, {'image': 'cover-uiux.webp', 'caption': 'طراحی'}]}}]]}]),
}

PAGE_TEMPLATES = {
    'landing': dict(name='لندینگ کامل', icon='🚀', desc='هیرو + ویژگی + دوره + قیمت + نظرات + CTA',
        rows=(SECTION_TEMPLATES['hero_classic']['rows'] + SECTION_TEMPLATES['features']['rows']
              + SECTION_TEMPLATES['courses_grid']['rows'] + SECTION_TEMPLATES['stats']['rows']
              + SECTION_TEMPLATES['testimonials']['rows'] + SECTION_TEMPLATES['pricing']['rows']
              + SECTION_TEMPLATES['cta']['rows'] + SECTION_TEMPLATES['newsletter']['rows'])),
    'about_page': dict(name='درباره ما', icon='🏛', desc='معرفی + ارزش‌ها + آمار',
        rows=(SECTION_TEMPLATES['hero_text']['rows'] + SECTION_TEMPLATES['stats']['rows']
              + SECTION_TEMPLATES['features']['rows'] + SECTION_TEMPLATES['cta']['rows'])),
    'contact_page': dict(name='تماس با ما', icon='📨', desc='اطلاعات تماس + فرم',
        rows=(SECTION_TEMPLATES['hero_text']['rows'] + SECTION_TEMPLATES['contact_form']['rows']
              + SECTION_TEMPLATES['trust']['rows'])),
    'pricing_page': dict(name='صفحه قیمت‌گذاری', icon='💎', desc='قیمت + سوالات + CTA',
        rows=(SECTION_TEMPLATES['pricing']['rows'] + SECTION_TEMPLATES['faq']['rows']
              + SECTION_TEMPLATES['cta']['rows'])),
    'webinar': dict(name='صفحه وبینار', icon='🎥', desc='لندینگ وبینار با تایمر و ثبت‌نام',
        rows=[{'id': 'w1', 'settings': {'gap': 0, 'py': 60}, 'cols': [[
            {'id': 'w1a', 'type': 'heading', 'data': {'text': '🎥 وبینار رایگان: مسیر استخدام در برنامه‌نویسی', 'tag': 'h1', 'align': 'center', 'mb': '10'}},
            {'id': 'w1b', 'type': 'text', 'data': {'content': 'در این وبینار ۹۰ دقیقه‌ای، نقشه راه کامل ورود به بازار کار را یاد می‌گیرید.', 'align': 'center'}},
            {'id': 'w1c', 'type': 'countdown', 'data': {'title': '⏳ شروع وبینار تا:', 'text': 'ثبت‌نام رایگان — ظرفیت محدود'}},
            {'id': 'w1d', 'type': 'button', 'data': {'text': '📝 ثبت‌نام رایگان در وبینار', 'url': '/consultation', 'style': 'accent', 'size': 'lg', 'align': 'center'}}
        ]]}]),
    'campaign': dict(name='صفحه کمپین فروش', icon='🎉', desc='لندینگ تخفیف زمان‌دار با تایمر',
        rows=[{'id': 'c1', 'settings': {'gap': 0, 'py': 60}, 'cols': [[
            {'id': 'c1a', 'type': 'heading', 'data': {'text': '🎉 جشنواره بزرگ پاییز — تا ۵۰٪ تخفیف', 'tag': 'h1', 'align': 'center', 'mb': '10'}},
            {'id': 'c1b', 'type': 'countdown', 'data': {'title': '⏳ پایان جشنواره:', 'text': 'فرصت را از دست نده!'}},
            {'id': 'c1c', 'type': 'courses', 'data': {'title': 'دوره‌های تخفیف‌دار', 'limit': '4', 'columns': '4', 'sort': 'popular'}},
            {'id': 'c1d', 'type': 'button', 'data': {'text': '🚀 مشاهده همه تخفیف‌ها', 'url': '/courses?sort=cheap', 'style': 'accent', 'size': 'lg', 'align': 'center'}}
        ]]}]),
    'consult_page': dict(name='صفحه مشاوره', icon='🎯', desc='لندینگ فرم دریافت مشاوره رایگان',
        rows=[{'id': 'q1', 'settings': {'gap': 0, 'py': 60}, 'cols': [[
            {'id': 'q1a', 'type': 'heading', 'data': {'text': '🎯 مشاوره رایگان انتخاب مسیر', 'tag': 'h1', 'align': 'center', 'mb': '10'}},
            {'id': 'q1b', 'type': 'text', 'data': {'content': 'کارشناسان ما با شما تماس می‌گیرند.', 'align': 'center'}},
            {'id': 'q1c', 'type': 'html', 'data': {'code': '<div style="text-align:center"><a class="btn btn-accent btn-lg" href="/consultation">📞 درخواست مشاوره</a></div>'}}
        ]]}]),
    'faq_page': dict(name='صفحه سوالات متداول', icon='❓', desc='سکشن FAQ با آکاردئون',
        rows=(SECTION_TEMPLATES['faq']['rows'] + SECTION_TEMPLATES['cta']['rows'])),
    'teacher_landing': dict(name='صفحه معرفی مدرس', icon='👨‍🏫', desc='لندینگ مدرس با دوره‌ها و نظرات',
        rows=[{'id': 't1', 'settings': {'gap': 0, 'py': 60}, 'cols': [[
            {'id': 't1a', 'type': 'heading', 'data': {'text': '👨‍🏫 با اساتید ما آشنا شوید', 'tag': 'h1', 'align': 'center', 'mb': '10'}},
            {'id': 't1b', 'type': 'teachers', 'data': {'title': 'اساتید برتر', 'limit': '4', 'columns': '4'}},
            {'id': 't1c', 'type': 'testimonials', 'data': {'columns': '3', 'items': [
                {'name': 'رضا موسوی', 'role': 'دانشجوی ML', 'stars': '5', 'color': '#0891b2', 'text': 'کیفیت تدریس فوق‌العاده بود.'}
            ]}}
        ]]}]),
}

WIDGET_CATS = [
    ('basic', 'پایه'),
    ('general', 'عمومی'),
    ('media', 'اسلایدر و رسانه'),
    ('grid', 'گریدهای محتوا'),
    ('adv', 'پیشرفته'),
    ('pro', 'حرفه‌ای (Pro)'),
    ('theme', 'قالب‌ساز'),
    ('woo', 'فروشگاهی'),
    ('header', 'ویجت‌های هدر'),
    ('footer', 'ویجت‌های فوتر'),
]


def _norm_fields(fields):
    """استانداردسازی فیلدهای ویجت — تحمل هر دو فرمت dict و tuple قدیمی"""
    out = []
    for f in fields or []:
        if isinstance(f, dict):
            out.append(f)
        elif isinstance(f, (tuple, list)) and len(f) >= 2:
            out.append(dict(key=str(f[0]), label=str(f[1]),
                            type=str(f[2]) if len(f) > 2 else 'text'))
        else:
            continue
    return out


def defaults(wtype):
    """مقادیر پیش‌فرض فیلدهای یک ویجت"""
    d = {}
    w = WIDGETS.get(wtype)
    if w:
        for f in _norm_fields(w.get('fields', [])):
            if f['type'] == 'repeater':
                d[f['key']] = []
            elif f['type'] == 'checkbox':
                d[f['key']] = False
            else:
                d[f['key']] = ''
    # اسلایدر: همیشه با ۳ اسلاید نمونه شروع شود تا خالی نماند
    if wtype == 'slider':
        imgs = [i for i in IMG_OPTIONS if i.startswith('cover-') and i.endswith(('.webp', '.jpg', '.png'))]
        imgs = (imgs or IMG_OPTIONS)[:3]
        d['slides'] = [
            dict(img=imgs[0] if imgs else '', title='دوره‌های حرفه‌ای را همین حالا شروع کنید',
                 sub='با بیش از ۲۲۰ درس عملی و مدرسین مجرب، مهارت آینده خود را بسازید.',
                 btn_text='مشاهده دوره‌ها', btn_url='/courses', align='right'),
            dict(img=imgs[1] if len(imgs) > 1 else (imgs[0] if imgs else ''), title='یادگیری با ضمانت بازگشت وجه',
                 sub='تا ۷ روز ضمانت بازگشت کامل وجه دارید؛ اگر راضی نبودید پولتان برمی‌گردد.',
                 btn_text='ثبت‌نام رایگان', btn_url='/register', align='center'),
            dict(img=imgs[2] if len(imgs) > 2 else (imgs[0] if imgs else ''), title='همراه با پشتیبانی مدرس',
                 sub='در مسیر یادگیری تنها نیستید؛ هر سوالی دارید از مدرس بپرسید.',
                 btn_text='دوره‌ها', btn_url='/courses', align='right'),
        ]
        d['height'] = '420'
        d['overlay'] = '60'
        d['autoplay'] = True
        d['interval'] = '5'
        d['dots'] = True
        d['arrows'] = True
        d['swipe'] = True
    return d


def _sanitize_widget(w):
    """پاکسازی یک ویجت (با پشتیبانی بازگشتی از بخش داخلی)"""
    if not isinstance(w, dict):
        return None
    wt = w.get('type', 'text')
    if wt not in WIDGETS:
        return None
    wd = w.get('data')
    wd = wd if isinstance(wd, dict) else {}
    merged = defaults(wt)
    merged.update(wd)
    for f in _norm_fields(WIDGETS[wt].get('fields', [])):
        if f['type'] == 'repeater':
            if not isinstance(merged.get(f['key']), list):
                merged[f['key']] = []
            cleaned_items = []
            for it in merged[f['key']]:
                if not isinstance(it, dict):
                    continue
                itd = {}
                for sf in f.get('item_fields', []):
                    itd[sf['key']] = it.get(sf['key'],
                        ([] if sf['type'] == 'repeater' else (False if sf['type'] == 'checkbox' else '')))
                cleaned_items.append(itd)
            merged[f['key']] = cleaned_items
        elif f['type'] == 'number':
            # مقادیر عددی: خالی → 0
            try:
                merged[f['key']] = int(merged.get(f['key']) or 0)
            except (TypeError, ValueError):
                merged[f['key']] = 0
        elif f['type'] == 'checkbox':
            # بولین اجباری
            merged[f['key']] = bool(merged.get(f['key']))
        else:
            # همه فیلدهای متنی/انتخابی/رنگ/تصویر: رشته اجباری — هر نوع دیگری (لیست/دیکته/عدد) به رشته امن تبدیل شود
            v = merged.get(f['key'])
            if v is None or v is False:
                merged[f['key']] = ''
            elif isinstance(v, str):
                merged[f['key']] = v
            elif isinstance(v, (int, float)):
                merged[f['key']] = str(v)
            else:
                # لیست/دیکته/چیزهای عجیب → رشته امن (ضد هرگونه .get روی داده ناسازگار)
                merged[f['key']] = ''
    # مهاجرت داده قدیمی: ویجت‌هایی که فیلد «style» رشته‌ای داشتند (دکمه/جداکننده/CTA/سبد)
    _style_migrate = {'button': 'btn_style', 'add_to_cart': 'btn_style',
                      'divider': 'line_style', 'cta': 'cta_style'}
    if wt in _style_migrate:
        newk = _style_migrate[wt]
        if not merged.get(newk) and isinstance(merged.get('style'), str) and merged['style']:
            merged[newk] = merged['style']
        if isinstance(merged.get('style'), str):
            merged.pop('style', None)
    # آبجکت «style» تب استایل: همیشه دیکشنری امن (اگر رشته/لیست باشد → خالی)
    if 'style' in merged and not isinstance(merged.get('style'), dict):
        merged['style'] = {}
    if wt == 'inner_section':
        inner_cols = []
        for col in (wd.get('cols') or []):
            if not isinstance(col, list):
                inner_cols.append([])
                continue
            inner_cols.append([x for x in (_sanitize_widget(x) for x in col) if x])
        merged['cols'] = inner_cols
    return {'id': w.get('id') or _new_id('w'), 'type': wt, 'data': merged}


def _sanitize_rows(rows):
    """پاکسازی داده‌های صفحه‌ساز"""
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        cols = []
        for c in (r.get('cols') or []):
            if not isinstance(c, list):
                continue
            cols.append([x for x in (_sanitize_widget(x) for x in c) if x])
        rs = r.get('settings')
        rs = rs if isinstance(rs, dict) else {}
        out.append({'id': r.get('id') or _new_id('r'), 'settings': rs, 'cols': cols})
    return out


def _dynamic_value(key):
    """مقداردهی تگ‌های پویا از دیتابیس"""
    from flask import g as _g
    from datetime import datetime
    try:
        from datetime import UTC as _dt
    except ImportError:
        from datetime import timezone as _tz2
        _dt = _tz2.utc
    try:
        if key == 'site_name':
            return _g.settings.get('site_name', 'آکادمی آنلاین')
        if key == 'site_desc':
            return _g.settings.get('site_desc', '')
        if key == 'course_count':
            return str(Course.query.filter_by(status='published').count())
        if key == 'student_count':
            return str(sum(c.students_count for c in Course.query.all()))
        if key == 'teacher_count':
            return str(User.query.filter(User.role == 'teacher').count())
        if key == 'user_name':
            return _g.user.name if _g.user else 'میهمان'
        if key == 'user_phone':
            return (_g.user.phone or '') if _g.user else ''
        if key == 'user_email':
            return (_g.user.email or '') if _g.user else ''
        if key == 'year':
            return str(_dt.utcnow().year)
        if key == 'date':
            from jdates import jdate
            return jdate(_dt.utcnow())
    except Exception:
        return ''
    return ''


def render_dynamic(text):
    """جایگزینی {tag} در متن"""
    text = text or ''
    for m in set(re.findall(r'\{([a-z_]+)\}', text)):
        text = text.replace('{' + m + '}', _dynamic_value(m))
    return text


def uniq_cats(items):
    """دسته‌های یکتا از آیتم‌های پورتفولیو — ایمن در برابر داده ناسازگار"""
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        c = str(it.get('category') or '').strip()
        if c and c not in out:
            out.append(c)
    return out


def builder_price_history(d):
    """داده نمودار قیمت — از PriceHistory + مقایسه با پلتفرم‌ها (استاتیک/تنظیمات)"""
    from ext_models import PriceHistory
    from jdates import jdate
    from models import Course as _C, Product as _P
    item = None
    url = '#'
    try:
        if d.get('item_type') == 'product':
            item = db.session.get(_P, int(d.get('item_id') or 0))
            if item: url = url_for('products.product_detail', pid=item.id)
        else:
            item = db.session.get(_C, int(d.get('item_id') or 0))
            if item: url = url_for('site.course_detail', slug=item.slug)
    except Exception:
        item = None
    points = []
    if item:
        itype = 'product' if d.get('item_type') == 'product' else 'course'
        rows = PriceHistory.query.filter_by(item_type=itype, item_id=item.id) \
            .order_by(PriceHistory.recorded_at.asc()).limit(14).all()
        for r in rows:
            points.append(dict(price=r.final_price or r.price, date_fa=jdate(r.recorded_at)))
    current = item.final_price if item and hasattr(item, 'final_price') else 0
    # مقایسه با پلتفرم‌های دیگر — نمونه: از تنظیمات site (competitive_prices JSON) یا پیش‌فرض
    compare = []
    try:
        from models import Setting as _S
        ss = db.session.get(_S, 'competitive_prices')
        data = json.loads(ss.value) if ss and ss.value else {}
        key = str(item.id) if item else ''
        if key in data:
            for name, price in data[key].items():
                compare.append(dict(name=name, price=int(price)))
    except Exception as _e:
        from validators import log_exc as _lexc2
        _lexc2(f'builder.price_compare: {_e}')
    if not compare and item:
        base = current or 0
        compare = [dict(name='ترب', price=max(1, int(base * 0.97))),
                   dict(name='دیجی‌کالا', price=int(base * 1.05)),
                   dict(name='فرادرس', price=int(base * 1.12))]
    return dict(item=item, url=url, points=points, current=current, compare=compare)


def builder_amazing_offer(d):
    """داده باکس پیشنهاد شگفت‌انگیز — آیتم دارای بیشترین تخفیف"""
    from models import Course as _C, Product as _P
    item = None
    try:
        if d.get('item_type') == 'product':
            item = db.session.get(_P, int(d.get('item_id') or 0))
        else:
            item = db.session.get(_C, int(d.get('item_id') or 0))
    except Exception:
        item = None
    if not item:
        item = _C.query.filter(_C.discount_percent > 0, _C.status == 'published') \
            .order_by(_C.discount_percent.desc()).first()
    url = '#'
    if item:
        url = url_for('products.product_detail', slug=item.slug) if hasattr(item, 'stock') \
            else url_for('site.course_detail', slug=item.slug)
    disc = item.discount_percent if item and hasattr(item, 'discount_percent') else 0
    return dict(item=item, url=url, discount=disc or 0)


def builder_review_pro(d):
    """نظرات پیشرفته — از Review با pros/cons و تأیید خرید"""
    from models import Review as _R, Course as _C, Product as _P
    reviews = []
    try:
        if d.get('item_type') == 'product':
            # محصولات فعلاً نظر ندارند — از دوره‌های مرتبط
            pass
        q = _R.query.filter_by(is_approved=True).order_by(_R.id.desc())
        cid = int(d.get('item_id') or 0) if d.get('item_type') != 'product' else 0
        if cid:
            q = q.filter_by(course_id=cid)
        reviews = q.limit(max(1, min(12, int(d.get('limit') or 6)))).all()
    except Exception:
        reviews = []
    return dict(reviews=reviews)


def record_price(item_type, item_id, price, final_price):
    """ثبت نقطه قیمت — هنگام ساخت/ویرایش قیمت و خرید صدا زده شود"""
    from ext_models import PriceHistory
    last = PriceHistory.query.filter_by(item_type=item_type, item_id=item_id) \
        .order_by(PriceHistory.id.desc()).first()
    if last and last.final_price == final_price and last.price == price:
        return
    db.session.add(PriceHistory(item_type=item_type, item_id=item_id,
                                price=price, final_price=final_price))
    db.session.commit()


def builder_products(d):
    """محصولات/دوره‌ها با فیلترهای فروشگاهی"""
    q = Course.query.filter_by(status='published')
    f = (d or {}).get('filter', 'all')
    if f == 'sale':
        q = q.filter(Course.discount_price > 0, Course.discount_price < Course.price)
    elif f == 'featured':
        q = q.filter(Course.featured == True)
    elif f == 'popular':
        q = q.order_by(Course.views.desc())
    else:
        q = q.order_by(Course.created_at.desc())
    return q.limit(int((d or {}).get('limit') or 8)).all()


def render_shortcodes(text):
    """رندر شورت‌کدهای ساده: [courses limit=4] [categories] [posts] [button] [alert] [anchor]"""
    from markupsafe import Markup
    text = render_dynamic(text or '')
    def at(attrs, key, default=''):
        mm = re.search(key + r'="([^"]*)"', attrs)
        return mm.group(1) if mm else default

    def repl(m):
        name, attrs, inner = m.group(1), m.group(2) or '', m.group(3) or ''
        if name == 'courses':
            lim = int(at(attrs, 'limit', '4') or 4)
            cat = at(attrs, 'category', '')
            q = Course.query.filter_by(status='published')
            if cat.isdigit():
                q = q.filter_by(category_id=int(cat))
            cs = q.limit(lim).all()
            lis = ''.join('<li><a href="/course/%s">%s</a></li>' % (c.slug, c.title) for c in cs)
            return '<ul class="pb-sc-list">' + lis + '</ul>'
        if name == 'categories':
            cats = Category.query.order_by(Category.sort).all()
            lis = ''.join('<li><a href="/courses?cat=%s">%s %s</a></li>' % (c.slug, c.icon, c.name) for c in cats)
            return '<ul class="pb-sc-list">' + lis + '</ul>'
        if name == 'posts':
            lim = int(at(attrs, 'limit', '3') or 3)
            ps = BlogPost.query.filter_by(published=True).order_by(BlogPost.created_at.desc()).limit(lim).all()
            lis = ''.join('<li><a href="/blog/%s">%s</a></li>' % (p.slug, p.title) for p in ps)
            return '<ul class="pb-sc-list">' + lis + '</ul>'
        if name == 'button':
            return '<a class="btn btn-%s" href="%s">%s</a>' % (at(attrs, 'style', 'primary'), at(attrs, 'url', '#'), at(attrs, 'text', 'دکمه'))
        if name == 'alert':
            return '<div class="pb-alert pb-alert-%s">%s</div>' % (at(attrs, 'type', 'info'), inner)
        if name == 'anchor':
            return '<div class="pb-anchor" id="%s"></div>' % at(attrs, 'id', 'anchor')
        return ''
    return Markup(_SHORTCODE_RE.sub(repl, text))


_SHORTCODE_RE = re.compile(
    r'\[(courses|categories|posts|button|anchor)([^\]]*)\]|\[(alert)([^\]]*)\]([\s\S]*?)\[/alert\]')


def _slugify(t):
    t = (t or '').strip().replace(' ', '-')
    return re.sub(r'[^\w\u0600-\u06FF\-]', '', t)


def _new_id(prefix='w'):
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


# ------------------------------------------------------------------
# رندر بلوک‌ها (توابع کمکی برای قالب)
# ------------------------------------------------------------------
_BUILDER_CACHE = {}
import threading as _bthr
_BUILDER_LOCK = _bthr.Lock()


def _b_cache(key, ttl, fn):
    import time as _bt
    now = _bt.time()
    with _BUILDER_LOCK:
        hit = _BUILDER_CACHE.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    val = fn()
    with _BUILDER_LOCK:
        _BUILDER_CACHE[key] = (now, val)
        if len(_BUILDER_CACHE) > 100:
            _BUILDER_CACHE.clear()
    return val


def builder_courses(d):
    cat = (d or {}).get('category') or ''
    sort = (d or {}).get('sort', 'newest')
    _lim = int((d or {}).get('limit') or 8)

    def _q():
        from sqlalchemy.orm import selectinload as _sil
        q = (Course.query
             .options(db.joinedload(Course.category), db.joinedload(Course.teacher),
                      _sil(Course.enrollments), _sil(Course.reviews))
             .filter_by(status='published'))
        if str(cat).isdigit():
            q = q.filter_by(category_id=int(cat))
        order = {'newest': Course.created_at.desc(), 'popular': Course.views.desc(),
                 'cheap': Course.discount_price.asc(), 'expensive': Course.discount_price.desc()}.get(sort, Course.created_at.desc())
        return q.order_by(order).limit(_lim).all()
    return _b_cache(f'courses:{cat}:{sort}:{_lim}', 30, _q)


def builder_categories(d):
    q = Category.query.order_by(Category.sort)
    lim = int((d or {}).get('limit') or 0)
    return q.limit(lim).all() if lim else q.all()


def builder_posts(d):
    q = BlogPost.query.filter_by(published=True).order_by(BlogPost.created_at.desc())
    return q.limit(int((d or {}).get('limit') or 3)).all()


def builder_teachers(d):
    q = User.query.filter(User.role == 'teacher')
    return q.limit(int((d or {}).get('limit') or 4)).all()


def builder_cat_options():
    return [(str(c.id), c.name) for c in Category.query.order_by(Category.sort).all()]


# ------------------------------------------------------------------
# مسیرهای صفحه‌ساز
# ------------------------------------------------------------------
def _persian_designs_meta():
    """متادیتای ۲۰ طرح برای صفحه‌ساز (پالت + نام + دسته)"""
    from persian_themes import PERSIAN_THEMES
    return [dict(id=t['id'], name=t['name'], category=t['category'],
                 dark=t.get('dark', False),
                 colors=[t['colors']['primary'], t['colors']['accent'], t['colors']['secondary']])
            for t in PERSIAN_THEMES]


def _admin_required():
    if not g.user or not g.user.is_admin:
        flash('دسترسی غیرمجاز — این بخش مخصوص مدیر است.', 'error')
        return redirect(url_for('site.index'))
    return None


@builder_bp.route('/builder')
def index():
    r = _admin_required()
    if r:
        return r
    pages = Page.query.order_by(Page.updated_at.desc()).all()
    try:
        sl_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'section_library.json')
        section_lib = json.loads(open(sl_path, encoding='utf-8').read()) if os.path.exists(sl_path) else []
        pl_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'page_library.json')
        page_lib = json.loads(open(pl_path, encoding='utf-8').read()) if os.path.exists(pl_path) else []
    except Exception:
        section_lib, page_lib = [], []
    types = {'home': 'خانه', 'header': 'هدر سایت', 'footer': 'فوتر سایت',
             'footer_mobile': 'فوتر موبایل', 'mobile_menu': 'منوی موبایل',
             'page': 'صفحه معمولی', '404': 'صفحه خطای ۴۰۴'}
    from persian_themes import PERSIAN_THEMES
    return render_template('builder/index.html', pages=pages, types=types,
                           section_lib=section_lib, page_lib=page_lib,
                           persian_themes=PERSIAN_THEMES)


@builder_bp.route('/builder/new', methods=['GET', 'POST'])
def new_page():
    r = _admin_required()
    if r:
        return r
    if request.method == 'GET':
        return redirect(url_for('builder.index'))
    title = request.form.get('title', '').strip()
    ptype = request.form.get('ptype', 'page')
    template = request.form.get('template', '')
    if not title:
        flash('عنوان صفحه را وارد کنید.', 'error')
        return redirect(url_for('builder.index'))
    base = _slugify(title)
    slug = base
    n = 2
    while Page.query.filter_by(slug=slug).first():
        slug = f'{base}-{n}'
        n += 1
    rows = []
    if template in PAGE_TEMPLATES:
        rows = PAGE_TEMPLATES[template]['rows']
    # طرح آماده ایرانی: ?design=pd-XX → چیدمان کامل طرح
    design = request.form.get('design', '')
    if design:
        from persian_themes import get_theme, home_rows
        t = get_theme(design)
        if t:
            rows = home_rows(t)
    page = Page(title=title, slug=slug, ptype=ptype,
                content=json.dumps({'settings': {}, 'rows': rows}, ensure_ascii=False))
    db.session.add(page)
    db.session.commit()
    return redirect(url_for('builder.editor', slug=slug))


@builder_bp.route('/builder/<slug>/delete', methods=['POST'])
def delete_page(slug):
    r = _admin_required()
    if r:
        return r
    page = Page.query.filter_by(slug=slug).first_or_404()
    db.session.delete(page)
    db.session.commit()
    flash('صفحه حذف شد.', 'info')
    return redirect(url_for('builder.index'))


@builder_bp.route('/builder/<slug>/duplicate', methods=['POST'])
def duplicate_page(slug):
    r = _admin_required()
    if r:
        return r
    page = Page.query.filter_by(slug=slug).first_or_404()
    base = _slugify(page.title + '-کپی')
    new_slug = base
    n = 2
    while Page.query.filter_by(slug=new_slug).first():
        new_slug = f'{base}-{n}'
        n += 1
    copy = Page(title=page.title + ' (کپی)', slug=new_slug, ptype=page.ptype,
                content=page.content, is_published=False)
    db.session.add(copy)
    db.session.commit()
    flash('صفحه با موفقیت کپی شد — آن را ویرایش و منتشر کنید.', 'success')
    return redirect(url_for('builder.editor', slug=new_slug))


@builder_bp.route('/builder/<slug>/export')
def export_page(slug):
    r = _admin_required()
    if r:
        return r
    from flask import Response
    page = Page.query.filter_by(slug=slug).first_or_404()
    data = {'title': page.title, 'ptype': page.ptype,
            'settings': page.settings(), 'rows': page.rows()}
    body = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(body, mimetype='application/json',
                    headers={'Content-Disposition': f'attachment; filename={slug}.json'})


@builder_bp.route('/builder/import', methods=['POST'])
def import_page():
    r = _admin_required()
    if r:
        return r
    f = request.files.get('file')
    if not f or not f.filename:
        flash('فایل JSON انتخاب کنید.', 'error')
        return redirect(url_for('builder.index'))
    try:
        data = json.loads(f.read().decode('utf-8'))
        title = (data.get('title') or 'صفحه واردشده').strip()
        ptype = data.get('ptype', 'page')
        if ptype not in ('home', 'header', 'footer', 'footer_mobile', 'mobile_menu', 'page', '404', 'post'):
            ptype = 'page'
        base = _slugify(title)
        slug = base
        n = 2
        while Page.query.filter_by(slug=slug).first():
            slug = f'{base}-{n}'
            n += 1
        page = Page(title=title, slug=slug, ptype=ptype, is_published=False,
                    content=json.dumps({'settings': data.get('settings', {}),
                                        'rows': data.get('rows', [])}, ensure_ascii=False))
        db.session.add(page)
        db.session.commit()
        flash('صفحه با موفقیت وارد شد.', 'success')
        return redirect(url_for('builder.editor', slug=slug))
    except Exception as e:
        flash('فایل JSON نامعتبر است: ' + str(e)[:100], 'error')
        return redirect(url_for('builder.index'))


@builder_bp.route('/builder/<slug>')
def editor(slug):
    r = _admin_required()
    if r:
        return r
    page = Page.query.filter_by(slug=slug).first_or_404()
    other_pages = [{'slug': p.slug, 'title': p.title, 'ptype': p.ptype}
                   for p in Page.query.filter(Page.id != page.id).order_by(Page.ptype).all()]
    course_options = [(str(c.id), c.title) for c in
                      Course.query.order_by(Course.title).limit(60).all()]
    # بارگذاری طرح آماده با پارامتر ?design=pd-XX — ردیف‌های طرح جایگزین محتوای فعلی می‌شوند (برای ویرایش)
    design = request.args.get('design', '')
    if design:
        from persian_themes import get_theme, home_rows
        t = get_theme(design)
        if t and not page.rows():
            # صفحه خالی: مستقیم ذخیره کن تا پیش‌نمایش فوری درست باشد
            page.content = json.dumps({'settings': page.settings(), 'rows': home_rows(t)},
                                      ensure_ascii=False)
            db.session.commit()
    return render_template('builder/editor.html', page=page, widgets=WIDGETS,
                           cats=WIDGET_CATS, images=IMG_OPTIONS,
                           cat_options=builder_cat_options(), other_pages=other_pages,
                           course_options=course_options,
                           section_templates=SECTION_TEMPLATES,
                           page_templates=PAGE_TEMPLATES,
                           persian_designs=_persian_designs_meta())


@builder_bp.route('/builder/api/render', methods=['POST'])
def api_render():
    r = _admin_required()
    if r:
        return jsonify(ok=False, msg='دسترسی غیرمجاز'), 403
    data = request.get_json(force=True)
    edit = bool(data.get('edit'))
    rows = _sanitize_rows(data.get('rows', []))
    parts = []
    for row in rows:
        try:
            parts.append(render_template('builder/fragment_row.html', row=row, edit=edit))
        except Exception as e:
            from validators import log_exc
            log_exc('builder.render_row: ' + str(e)[:150])
            parts.append('<div class="pb-row pb-row-error" title="' +
                         str(e).replace('"', '&quot;')[:200] + '">⚠️ خطا در رندر این ردیف: ' +
                         str(e).replace('"', '&quot;')[:120] +
                         '<br><small style="opacity:.75">صفحه را با Ctrl+Shift+R رفرش کنید — اگر ادامه داشت، ردیف را حذف و دوباره بسازید.</small></div>')
    html = ''.join(parts)
    return jsonify(ok=True, html=html, count=len(rows))


@builder_bp.route('/builder/api/design-rows/<did>')
def api_design_rows(did):
    """ردیف‌های چیدمان یک طرح آماده (برای اعمال در صفحه‌ساز)"""
    r = _admin_required()
    if r:
        return jsonify(ok=False, msg='دسترسی غیرمجاز'), 403
    from persian_themes import get_theme, home_rows
    t = get_theme(did)
    if not t:
        return jsonify(ok=False, msg='طرح پیدا نشد'), 404
    return jsonify(ok=True, rows=home_rows(t), name=t['name'])


@builder_bp.route('/builder/api/save', methods=['POST'])
def api_save():
    r = _admin_required()
    if r:
        return jsonify(ok=False, msg='دسترسی غیرمجاز'), 403
    data = request.get_json(force=True)
    # محدودیت سایز منطقی صفحه — ضد DoS با JSON عظیم
    if len(json.dumps(data, ensure_ascii=False)) > 500_000:
        return jsonify(ok=False, msg='حجم صفحه بیش از حد مجاز است (۵۰۰KB)'), 413
    page = Page.query.filter_by(slug=data.get('slug', '')).first_or_404()
    new_content = json.dumps({'settings': data.get('settings', {}), 'rows': data.get('rows', [])},
                             ensure_ascii=False)
    # نسخه‌بندی: اگر محتوا تغییر کرده، نسخه قبلی ذخیره شود (تاریخچه)
    if page.content != new_content:
        from models import PageRevision
        db.session.add(PageRevision(page_id=page.id, content=page.content,
                                    note=data.get('note') or 'ویرایش خودکار',
                                    author_id=g.user.id if g.user else None))
        # حداکثر ۲۰ نسخه نگهداری شود
        old_revs = PageRevision.query.filter_by(page_id=page.id) \
            .order_by(PageRevision.created_at.desc()).offset(19).all()
        for o in old_revs:
            db.session.delete(o)
    page.content = new_content
    if 'published' in data:
        page.is_published = bool(data['published'])
    db.session.commit()
    return jsonify(ok=True, msg='ذخیره شد ✅')


@builder_bp.route('/builder/api/revisions/<slug>')
def api_revisions(slug):
    """تاریخچه نسخه‌های یک صفحه"""
    r = _admin_required()
    if r:
        return jsonify(ok=False), 403
    from models import PageRevision
    page = Page.query.filter_by(slug=slug).first_or_404()
    from jdates import jdatetime
    revs = PageRevision.query.filter_by(page_id=page.id) \
        .order_by(PageRevision.created_at.desc()).limit(20).all()
    return jsonify(ok=True, revisions=[{
        'id': v.id, 'note': v.note or '', 'created': jdatetime(v.created_at),
        'author': v.author.name if v.author else '—'
    } for v in revs])


@builder_bp.route('/builder/api/restore/<int:rev_id>', methods=['POST'])
def api_restore(rev_id):
    """بازگردانی نسخه قبلی صفحه"""
    r = _admin_required()
    if r:
        return jsonify(ok=False), 403
    from models import PageRevision
    rev = PageRevision.query.get_or_404(rev_id)
    page = rev.page
    # نسخه فعلی قبل از بازگردانی ذخیره شود
    db.session.add(PageRevision(page_id=page.id, content=page.content,
                                note='قبل از بازگردانی نسخه %s' % rev_id,
                                author_id=g.user.id if g.user else None))
    page.content = rev.content
    db.session.commit()
    return jsonify(ok=True, msg='نسخه قبلی بازیابی شد ✅', content=page.content)



@builder_bp.route('/builder/api/section-template', methods=['POST'])
def api_section_template():
    """ذخیره سکشن به کتابخانه قالب‌ها"""
    r = _admin_required()
    if r:
        return jsonify(ok=False), 403
    data = request.get_json(force=True)
    name = (data.get('name') or '').strip()
    row = data.get('row')
    if not name or not row:
        return jsonify(ok=False, msg='نام و سکشن الزامی است')
    lib = json.loads(open(os.path.join(os.path.dirname(__file__), '..', 'section_library.json'), encoding='utf-8').read()) if os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'section_library.json')) else []
    lib.append({'name': name, 'row': row})
    with open(os.path.join(os.path.dirname(__file__), '..', 'section_library.json'), 'w', encoding='utf-8') as f:
        json.dump(lib, f, ensure_ascii=False)
    return jsonify(ok=True, msg='ذخیره شد')


@builder_bp.route('/builder/api/page-template', methods=['POST'])
def api_page_template():
    """ذخیره صفحه به عنوان قالب آماده"""
    r = _admin_required()
    if r:
        return jsonify(ok=False), 403
    data = request.get_json(force=True)
    name = (data.get('name') or '').strip() or 'قالب بدون نام'
    lib = json.loads(open(os.path.join(os.path.dirname(__file__), '..', 'page_library.json'), encoding='utf-8').read()) if os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'page_library.json')) else []
    lib.append({'name': name, 'rows': data.get('rows', []), 'settings': data.get('settings', {})})
    with open(os.path.join(os.path.dirname(__file__), '..', 'page_library.json'), 'w', encoding='utf-8') as f:
        json.dump(lib, f, ensure_ascii=False)
    return jsonify(ok=True, msg='ذخیره شد')


@builder_bp.route('/builder/api/upload', methods=['POST'])
def api_upload():
    r = _admin_required()
    if r:
        return jsonify(ok=False), 403
    f = request.files.get('file')
    if not f:
        return jsonify(ok=False), 400
    from validators import safe_filename, ALLOWED_IMAGE_EXT
    safe = safe_filename(f.filename or '', ALLOWED_IMAGE_EXT)
    if not safe:
        return jsonify(ok=False, msg='فرمت فایل مجاز نیست (فقط تصویر)'), 400
    up_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'img', 'uploads')
    os.makedirs(up_dir, exist_ok=True)
    ext = os.path.splitext(safe)[1].lower()
    name = 'up_' + uuid.uuid4().hex[:10] + ext
    f.save(os.path.join(up_dir, name))
    return jsonify(ok=True, file=name)
