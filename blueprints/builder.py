# -*- coding: utf-8 -*-
"""صفحه‌ساز بصری (شبیه Elementor) — ساخت، ویرایش لایو و رندر صفحات"""
import json
import re
import uuid
import glob
import os
import threading
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
        dict(key='search', label='نوار جستجوی دوره روی اسلایدر (سبک فرادرس)', type='checkbox'),
        dict(key='search_hint', label='متن راهنمای نوار جستجو', type='text'),
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
    'amazing_offer': dict(name='پیشنهاد ویژه', icon='⚡', cat='woo', desc='باکس فروش برای تخفیف واقعی ثبت‌شده', fields=[
        dict(key='title', label='عنوان', type='text'),
        dict(key='sub', label='زیرعنوان', type='text'),
        dict(key='item_type', label='نوع', type='select', options=[('course', 'دوره'), ('product', 'محصول')]),
        dict(key='item_id', label='آیتم (کد)', type='number'),
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
        dict(key='subtitle', label='متن/توضیح بخش', type='textarea'),
        dict(key='image', label='تصویر سربرگ بخش (اختیاری)', type='image'),
        dict(key='link_text', label='متن لینک «مشاهده همه»', type='text'),
        dict(key='link_url', label='آدرس لینک', type='text'),
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
        dict(key='subtitle', label='متن/توضیح بخش', type='textarea'),
        dict(key='image', label='تصویر سربرگ بخش (اختیاری)', type='image'),
        dict(key='link_text', label='متن لینک «مشاهده همه»', type='text'),
        dict(key='link_url', label='آدرس لینک', type='text'),
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
    # ============================================================
    # بلوک‌های دیزاین سیستم v2 — همگی کاملاً قابل ویرایش از صفحه‌ساز
    # (متن/تیتر/تصویر/رنگ/دکمه/آیکون/چیدمان + استایل و ریسپانسیو از تب استایل)
    # ============================================================
    'brand_intro': dict(name='معرفی برند / آکادمی', icon='🏛', cat='adv', desc='تصویر یا ویدیو + متن + امتیازها + آمار کوچک', fields=[
        dict(key='eyebrow', label='برچسب بالای تیتر', type='text'),
        dict(key='title', label='تیتر اصلی', type='text'),
        dict(key='subtitle', label='زیرتیتر', type='textarea'),
        dict(key='media', label='تصویر', type='image'),
        dict(key='video', label='ویدیو (به‌جای تصویر)', type='text'),
        dict(key='media_badge_value', label='مقدار نشان روی تصویر', type='text'),
        dict(key='media_badge_label', label='برچسب نشان روی تصویر', type='text'),
        dict(key='points', label='امتیازها (هر خط یکی)', type='textarea'),
        dict(key='btn_text', label='متن دکمه', type='text'),
        dict(key='btn_url', label='لینک دکمه', type='text'),
        dict(key='btn_style', label='استایل دکمه', type='select', options=[('primary', 'اصلی'), ('accent', 'تاکیدی'), ('outline-primary', 'خطی'), ('soft', 'نرم')]),
        dict(key='btn2_text', label='متن دکمه دوم', type='text'),
        dict(key='btn2_url', label='لینک دکمه دوم', type='text'),
        dict(key='layout', label='چیدمان', type='select', options=[('image-left', 'تصویر سمت چپ'), ('image-right', 'تصویر سمت راست')]),
        dict(key='stats', label='آمار کوچک', type='repeater', item_fields=[
            dict(key='icon', label='آیکون', type='text'),
            dict(key='value', label='عدد (پویا: {courses})', type='text'),
            dict(key='label', label='برچسب', type='text'),
        ]),
    ]),
    'instructor': dict(name='معرفی مدرس', icon='👤', cat='adv', desc='آواتار، بیو، دستاوردها و شبکه‌های اجتماعی', fields=[
        dict(key='title', label='تیتر بخش', type='text'),
        dict(key='name', label='نام مدرس', type='text'),
        dict(key='role', label='عنوان شغلی', type='text'),
        dict(key='avatar', label='تصویر مدرس', type='image'),
        dict(key='bio', label='بیوگرافی', type='textarea'),
        dict(key='cv', label='دستاوردها (هر خط یکی)', type='textarea'),
        dict(key='stats', label='آمار مدرس', type='repeater', item_fields=[
            dict(key='value', label='عدد', type='text'),
            dict(key='label', label='برچسب', type='text'),
        ]),
        dict(key='btn_text', label='متن دکمه (دوره‌های مدرس)', type='text'),
        dict(key='btn_url', label='لینک دکمه', type='text'),
        dict(key='socials', label='شبکه‌های اجتماعی', type='repeater', item_fields=[
            dict(key='icon', label='آیکون', type='text'),
            dict(key='url', label='لینک', type='text'),
        ]),
    ]),
    'curriculum': dict(name='سرفصل دوره / محصول', icon='📋', cat='adv', desc='آکاردئون فصل‌ها و جلسات', fields=[
        dict(key='title', label='تیتر بخش', type='text'),
        dict(key='subtitle', label='زیرتیتر', type='text'),
        dict(key='source', label='منبع سرفصل', type='select', options=[('manual', 'دستی (خودم وارد می‌کنم)'), ('current', 'دورهٔ فعلی (در قالب دوره)')]),
        dict(key='chapters', label='فصل‌ها', type='repeater', item_fields=[
            dict(key='title', label='نام فصل', type='text'),
            dict(key='lessons', label='جلسات (هر خط: عنوان | مدت)', type='textarea'),
        ]),
        dict(key='open_first', label='فصل اول باز باشد', type='checkbox'),
        dict(key='btn_text', label='متن دکمه پایین', type='text'),
        dict(key='btn_url', label='لینک دکمه', type='text'),
    ]),
    'learning_path': dict(name='مسیر یادگیری', icon='🗺', cat='adv', desc='گام‌های متصل یادگیری با دوره‌ها', fields=[
        dict(key='eyebrow', label='برچسب بالای تیتر', type='text'),
        dict(key='title', label='تیتر بخش', type='text'),
        dict(key='subtitle', label='زیرتیتر', type='text'),
        dict(key='columns', label='تعداد گام در ردیف', type='select', options=[('3', '۳'), ('4', '۴'), ('5', '۵')]),
        dict(key='steps', label='گام‌ها', type='repeater', item_fields=[
            dict(key='title', label='عنوان گام', type='text'),
            dict(key='text', label='توضیح', type='textarea'),
            dict(key='chip', label='برچسب (مثلا: ۳ دوره)', type='text'),
            dict(key='state', label='وضعیت', type='select', options=[('', 'عادی'), ('done', 'تکمیل‌شده (سبز)'), ('now', 'فعلی (رنگ اصلی)')]),
        ]),
    ]),
    'timeline': dict(name='تایم‌لاین', icon='🕐', cat='adv', desc='رویدادها به‌صورت خط زمانی عمودی', fields=[
        dict(key='eyebrow', label='برچسب بالای تیتر', type='text'),
        dict(key='title', label='تیتر بخش', type='text'),
        dict(key='align', label='چیدمان', type='select', options=[('start', 'راست‌چین'), ('center', 'وسط‌چین')]),
        dict(key='items', label='رویدادها', type='repeater', item_fields=[
            dict(key='date', label='تاریخ / دوره', type='text'),
            dict(key='title', label='عنوان', type='text'),
            dict(key='text', label='توضیح', type='textarea'),
        ]),
    ]),
    'plans_compare': dict(name='مقایسهٔ پلن‌ها', icon='⚖️', cat='adv', desc='جدول مقایسهٔ ویژگی‌ها با ستون ویژه', fields=[
        dict(key='title', label='تیتر بخش', type='text'),
        dict(key='subtitle', label='زیرتیتر', type='text'),
        dict(key='plans', label='پلن‌ها', type='repeater', item_fields=[
            dict(key='name', label='نام پلن', type='text'),
            dict(key='price', label='قیمت', type='text'),
            dict(key='btn_text', label='متن دکمه', type='text'),
            dict(key='btn_url', label='لینک', type='text'),
            dict(key='best', label='ستون ویژه', type='checkbox'),
        ]),
        dict(key='rows', label='ویژگی‌ها (هر خط: عنوان | مقدار۱ | مقدار۲ | ...)', type='textarea'),
    ]),
    'membership': dict(name='عضویت ویژه', icon='💎', cat='adv', desc='کارت‌های اشتراک با پلن پیشنهادی', fields=[
        dict(key='eyebrow', label='برچسب بالای تیتر', type='text'),
        dict(key='title', label='تیتر بخش', type='text'),
        dict(key='subtitle', label='زیرتیتر', type='textarea'),
        dict(key='columns', label='ستون‌ها', type='select', options=[('2', '۲'), ('3', '۳'), ('4', '۴')]),
        dict(key='plans', label='پلن‌ها', type='repeater', item_fields=[
            dict(key='name', label='نام پلن', type='text'),
            dict(key='desc', label='توضیح کوتاه', type='text'),
            dict(key='price', label='قیمت', type='text'),
            dict(key='period', label='واحد (ماهانه/سالانه)', type='text'),
            dict(key='old_price', label='قیمت قبلی (خط‌خورده)', type='text'),
            dict(key='features', label='ویژگی‌ها (هر خط یکی)', type='textarea'),
            dict(key='btn_text', label='متن دکمه', type='text'),
            dict(key='btn_url', label='لینک دکمه', type='text'),
            dict(key='best', label='پلن پیشنهادی', type='checkbox'),
            dict(key='ribbon', label='متن روبان', type='text'),
        ]),
    ]),
    'discount_banner': dict(name='بنر تخفیف', icon='🏷️', cat='adv', desc='بنر کمپین با شمارش معکوس و کد تخفیف', fields=[
        dict(key='badge', label='برچسب (مثلا: ٪۴۰ تخفیف)', type='text'),
        dict(key='title', label='تیتر', type='text'),
        dict(key='text', label='توضیح', type='textarea'),
        dict(key='coupon', label='کد تخفیف', type='text'),
        dict(key='btn_text', label='متن دکمه', type='text'),
        dict(key='btn_url', label='لینک دکمه', type='text'),
        dict(key='target', label='تاریخ پایان (میلادی، مثلا 2026-09-01)', type='text'),
        dict(key='show_countdown', label='نمایش شمارش معکوس', type='checkbox'),
        dict(key='bg', label='رنگ پس‌زمینه (خالی = گرادیان برند)', type='color'),
    ]),
    'file_download': dict(name='دانلود فایل', icon='📥', cat='adv', desc='کارت فایل قابل دانلود با حجم و فرمت', fields=[
        dict(key='title', label='تیتر بخش', type='text'),
        dict(key='items', label='فایل‌ها', type='repeater', item_fields=[
            dict(key='icon', label='آیکون', type='text'),
            dict(key='title', label='نام فایل', type='text'),
            dict(key='desc', label='توضیح', type='text'),
            dict(key='ext', label='فرمت (PDF)', type='text'),
            dict(key='size', label='حجم (۲ مگابایت)', type='text'),
            dict(key='url', label='لینک دانلود', type='text'),
        ]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('1', '۱'), ('2', '۲'), ('3', '۳')]),
    ]),
    'certificates': dict(name='مدارک و گواهی‌ها', icon='🏅', cat='adv', desc='کارت گواهی‌ها + دکمه استعلام', fields=[
        dict(key='eyebrow', label='برچسب بالای تیتر', type='text'),
        dict(key='title', label='تیتر بخش', type='text'),
        dict(key='subtitle', label='زیرتیتر', type='text'),
        dict(key='items', label='گواهی‌ها', type='repeater', item_fields=[
            dict(key='icon', label='آیکون', type='text'),
            dict(key='title', label='عنوان گواهی', type='text'),
            dict(key='text', label='توضیح', type='textarea'),
            dict(key='image', label='تصویر گواهی', type='image'),
        ]),
        dict(key='verify_text', label='متن دکمه استعلام', type='text'),
        dict(key='verify_url', label='لینک استعلام', type='text'),
        dict(key='columns', label='ستون‌ها', type='select', options=[('2', '۲'), ('3', '۳'), ('4', '۴')]),
    ]),
    'trust_box': dict(name='باکس اعتمادسازی', icon='🛡️', cat='adv', desc='تضمین بازگشت وجه، پشتیبانی، پرداخت امن…', fields=[
        dict(key='columns', label='ستون‌ها', type='select', options=[('2', '۲'), ('3', '۳'), ('4', '۴')]),
        dict(key='items', label='آیتم‌های اعتماد', type='repeater', item_fields=[
            dict(key='icon', label='آیکون', type='text'),
            dict(key='title', label='عنوان', type='text'),
            dict(key='text', label='توضیح', type='textarea'),
        ]),
    ]),
    'special_offers': dict(name='پیشنهادهای ویژه (داینامیک)', icon='🔥', cat='adv', desc='دوره‌های تخفیف‌دار واقعی از دیتابیس', fields=[
        dict(key='title', label='تیتر بخش', type='text'),
        dict(key='subtitle', label='زیرتیتر', type='text'),
        dict(key='limit', label='تعداد', type='select', options=[('2', '۲'), ('4', '۴'), ('6', '۶'), ('8', '۸')]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('2', '۲'), ('3', '۳'), ('4', '۴')]),
        dict(key='btn_text', label='متن دکمه (همه تخفیف‌ها)', type='text'),
        dict(key='btn_url', label='لینک دکمه', type='text'),
    ]),
    'related_products': dict(name='محصولات مرتبط (داینامیک)', icon='🧩', cat='woo', desc='کالاهای فروشگاه مرتبط با دسته', fields=[
        dict(key='title', label='تیتر بخش', type='text'),
        dict(key='subtitle', label='زیرتیتر', type='text'),
        dict(key='category', label='دستهٔ محصول', type='category'),
        dict(key='limit', label='تعداد', type='select', options=[('3', '۳'), ('4', '۴'), ('8', '۸')]),
        dict(key='columns', label='ستون‌ها', type='select', options=[('3', '۳'), ('4', '۴')]),
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
        dict(key='menu_id', label='منوی ذخیره‌شده (منوساز پنل مدیریت)', type='menu'),
        dict(key='links', label='لینک‌های دستی (اگر منویی انتخاب نشد)', type='repeater', item_fields=[
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
    'embed': dict(name='بلد (Embed)', icon='🔗', cat='general',
        desc='درج هر محتوای خارجی (یوتیوب، آپارات، اینستاگرام، نقشه، اسلاید و…) با iframe',
        fields=[
            dict(key='url', label='لینک درج (YouTube / Aparat / Instagram / …)', type='text'),
            dict(key='ratio', label='نسبت ابعاد', type='select',
                  options=[('16/9', '۱۶:۹'), ('4/3', '۴:۳'), ('1/1', '۱:۱'), ('21/9', '۲۱:۹')]),
            dict(key='height', label='ارتفاع دستی (px — خالی = نسبت ابعاد)', type='number'),
            dict(key='radius', label='گردی گوشه', type='select', options=[('0', 'بدون'), ('12', '۱۲px'), ('20', '۲۰px')]),
            dict(key='scroll', label='اجازه اسکرول داخل کادر', type='checkbox'),
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
        dict(key='subtitle', label='متن/توضیح بخش', type='textarea'),
        dict(key='image', label='تصویر سربرگ بخش (اختیاری)', type='image'),
        dict(key='link_text', label='متن لینک «مشاهده همه»', type='text'),
        dict(key='link_url', label='آدرس لینک', type='text'),
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
    'hero': dict(name='هیرو (بنر اصلی)', icon='🏠', cat='media',
        desc='بنر تمام‌عرض با تصویر، عنوان و دکمه — ساده‌تر از اسلایدر',
        fields=[
            dict(key='title', label='عنوان', type='text'),
            dict(key='sub', label='زیرعنوان', type='textarea'),
            dict(key='image', label='تصویر پس‌زمینه', type='image'),
            dict(key='btn_text', label='متن دکمه', type='text'),
            dict(key='btn_url', label='لینک دکمه', type='text'),
            dict(key='align', label='تراز', type='select',
                 options=[('right', 'راست'), ('center', 'وسط'), ('left', 'چپ')]),
            dict(key='height', label='ارتفاع', type='select',
                 options=[('320', '۳۲۰px'), ('420', '۴۲۰px'), ('520', '۵۲۰px')]),
            dict(key='overlay', label='تیرگی لایه روی تصویر', type='select',
                 options=[('45', '۴۵٪'), ('60', '۶۰٪'), ('75', '۷۵٪')]),
            dict(key='radius', label='گردی گوشه', type='select',
                 options=[('0', 'بدون'), ('16', '۱۶px'), ('24', '۲۴px')]),
        ]),
    'cert_verify': dict(name='استعلام گواهینامه', icon='🛡', cat='adv',
        desc='فرم استعلام کد رهگیری گواهی پایان دوره',
        fields=[
            dict(key='title', label='عنوان', type='text'),
            dict(key='text', label='توضیح', type='textarea'),
        ]),
    'course_search': dict(name='جستجوی دوره', icon='🔍', cat='grid',
        desc='نوار جستجوی مستقل دوره‌ها برای وسط صفحه',
        fields=[
            dict(key='placeholder', label='متن راهنما', type='text'),
            dict(key='show_cat', label='انتخاب دسته', type='checkbox'),
            dict(key='button', label='متن دکمه', type='text'),
        ]),
    'shop_products': dict(name='فروشگاه محصولات', icon='🛍', cat='woo',
        desc='کارت‌های کالای فیزیکی فروشگاه — لینک به صفحه محصول',
        fields=[
            dict(key='title', label='عنوان بخش', type='text'),
            dict(key='subtitle', label='متن/توضیح بخش', type='textarea'),
            dict(key='link_text', label='متن لینک «مشاهده همه»', type='text'),
            dict(key='link_url', label='آدرس لینک', type='text'),
            dict(key='limit', label='تعداد', type='select',
                 options=[('4', '۴'), ('8', '۸'), ('12', '۱۲')]),
            dict(key='columns', label='ستون‌ها', type='select',
                 options=[('2', '۲'), ('3', '۳'), ('4', '۴')]),
            dict(key='sort', label='مرتب‌سازی', type='select',
                 options=[('newest', 'جدیدترین'), ('popular', 'پربازدیدترین'),
                          ('cheap', 'ارزان‌ترین'), ('expensive', 'گران‌ترین')]),
            dict(key='show_price', label='نمایش قیمت', type='checkbox'),
        ]),
    'bundles': dict(name='بسته‌های آموزشی', icon='📦', cat='grid',
        desc='کارت‌های بسته چند دوره',
        fields=[
            dict(key='title', label='عنوان بخش', type='text'),
            dict(key='limit', label='تعداد', type='select',
                 options=[('3', '۳'), ('6', '۶'), ('9', '۹')]),
            dict(key='columns', label='ستون‌ها', type='select',
                 options=[('2', '۲'), ('3', '۳')]),
            dict(key='show_price', label='نمایش قیمت', type='checkbox'),
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
    'stats': dict(name='بخش آمار', icon='📊', desc='آمار واقعی و پویا از دیتابیس', rows=[{'id': 'st_st', 'settings': {'gap': 0, 'py': 50}, 'cols': [[{'id': 'st_s1', 'type': 'stats', 'data': {'columns': '4', 'items': [{'value': '{courses}', 'label': 'دوره منتشرشده'}, {'value': '{students}', 'label': 'دانشجو'}, {'value': '{hours}', 'label': 'ساعت آموزش'}, {'value': '{lessons}', 'label': 'جلسه منتشرشده'}]}}]]}]),
    'testimonials': dict(name='نظرات مشتریان', icon='💬', desc='نظرات واقعی را خودتان اضافه کنید', rows=[{'id': 'st_tm', 'settings': {'gap': 22, 'py': 60, 'bg': '#ffffff', 'radius': 24}, 'cols': [[{'id': 'st_t1', 'type': 'testimonials', 'data': {'columns': '3', 'items': []}}]]}]),
    'pricing': dict(name='قیمت‌گذاری', icon='💎', desc='اطلاعات واقعی پلن‌های خود را وارد کنید', rows=[{'id': 'st_pr', 'settings': {'gap': 24, 'py': 60}, 'cols': [[{'id': 'st_p1', 'type': 'pricing', 'data': {'columns': '1', 'items': [{'name': 'دوره‌های آموزشی', 'price': 'قیمت هر دوره', 'period': '', 'features': 'قیمت نهایی و شرایط در صفحه هر دوره نمایش داده می‌شود', 'btn_text': 'مشاهده دوره‌ها', 'btn_url': '/courses'}]}}]]}]),
    'cta': dict(name='دعوت به اقدام', icon='🚀', desc='بنر CTA گرادیانی', rows=[{'id': 'st_cta', 'settings': {'gap': 0, 'py': 30}, 'cols': [[{'id': 'st_c2', 'type': 'cta', 'data': {'title': 'آماده شروع هستید؟ 🚀', 'text': 'دوره‌های منتشرشده را بررسی کنید.', 'btn_text': 'مشاهده دوره‌ها', 'btn_url': '/courses'}}]]}]),
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
            {'id': 'w1a', 'type': 'heading', 'data': {'text': '🎥 عنوان رویداد آنلاین', 'tag': 'h1', 'align': 'center', 'mb': '10'}},
            {'id': 'w1b', 'type': 'text', 'data': {'content': 'تاریخ، ساعت، مدت و نام برگزارکننده واقعی را وارد کنید.', 'align': 'center'}},
            {'id': 'w1c', 'type': 'countdown', 'data': {'title': '⏳ زمان باقی‌مانده تا رویداد:', 'text': 'شرایط شرکت در رویداد را وارد کنید.'}},
            {'id': 'w1d', 'type': 'button', 'data': {'text': '📝 مشاهده جزئیات', 'url': '/consultation', 'style': 'accent', 'size': 'lg', 'align': 'center'}}
        ]]}]),
    'campaign': dict(name='صفحه کمپین فروش', icon='🎉', desc='لندینگ تخفیف زمان‌دار با تایمر',
        rows=[{'id': 'c1', 'settings': {'gap': 0, 'py': 60}, 'cols': [[
            {'id': 'c1a', 'type': 'heading', 'data': {'text': 'عنوان کمپین فروش را وارد کنید', 'tag': 'h1', 'align': 'center', 'mb': '10'}},
            {'id': 'c1b', 'type': 'countdown', 'data': {'title': 'زمان پایان کمپین:', 'text': 'تاریخ و شرایط واقعی کمپین را وارد کنید.'}},
            {'id': 'c1c', 'type': 'courses', 'data': {'title': 'دوره‌های تخفیف‌دار', 'limit': '4', 'columns': '4', 'sort': 'popular'}},
            {'id': 'c1d', 'type': 'button', 'data': {'text': '🚀 مشاهده همه تخفیف‌ها', 'url': '/courses?sort=cheap', 'style': 'accent', 'size': 'lg', 'align': 'center'}}
        ]]}]),
    'consult_page': dict(name='صفحه مشاوره', icon='🎯', desc='لندینگ فرم درخواست مشاوره',
        rows=[{'id': 'q1', 'settings': {'gap': 0, 'py': 60}, 'cols': [[
            {'id': 'q1a', 'type': 'heading', 'data': {'text': '🎯 درخواست مشاوره انتخاب مسیر', 'tag': 'h1', 'align': 'center', 'mb': '10'}},
            {'id': 'q1b', 'type': 'text', 'data': {'content': 'روش، هزینه و زمان پاسخگویی واقعی مجموعه را در این بخش بنویسید.', 'align': 'center'}},
            {'id': 'q1c', 'type': 'html', 'data': {'code': '<div style="text-align:center"><a class="btn btn-accent btn-lg" href="/consultation">📞 درخواست مشاوره</a></div>'}}
        ]]}]),
    'faq_page': dict(name='صفحه سوالات متداول', icon='❓', desc='سکشن FAQ با آکاردئون',
        rows=(SECTION_TEMPLATES['faq']['rows'] + SECTION_TEMPLATES['cta']['rows'])),
    'teacher_landing': dict(name='صفحه معرفی مدرس', icon='👨‍🏫', desc='لندینگ معرفی مدرس‌ها',
        rows=[{'id': 't1', 'settings': {'gap': 0, 'py': 60}, 'cols': [[
            {'id': 't1a', 'type': 'heading', 'data': {'text': '👨‍🏫 با اساتید ما آشنا شوید', 'tag': 'h1', 'align': 'center', 'mb': '10'}},
            {'id': 't1b', 'type': 'teachers', 'data': {'title': 'اساتید', 'limit': '4', 'columns': '4'}}
        ]]}]),
}

from builder_sections import (
    EXTRA_PAGE_TEMPLATES, SITE_SECTIONS, ensure_section, section_spec_for_page,
    site_page_specs, theme_specs,
)
PAGE_TEMPLATES.update(EXTRA_PAGE_TEMPLATES)

WIDGET_CATS = [
    ('basic', 'پایه'),
    ('media', 'اسلایدر و رسانه'),
    ('grid', 'دوره و محتوا'),
    ('adv', 'بخش‌های صفحه'),
    ('general', 'عمومی'),
    ('pro', 'حرفه‌ای'),
    ('theme', 'قالب پست / دوره'),
    ('woo', 'فروش'),
    ('header', 'هدر'),
    ('footer', 'فوتر'),
]

# ویجت‌هایی که رندر می‌شوند ولی از پالت پیش‌فرض پنهان‌اند (تکراری، گمراه‌کننده یا خاص قالب)
PALETTE_HIDDEN = frozenset({
    'soundcloud', 'shortcode', 'price_history', 'review_pro',
    'checkout_widget', 'my_account', 'products', 'toggle',
    'site_logo', 'site_title', 'flip_box', 'animated_heading',
    'dynamic_data', 'code_highlight',
})

# زمینه نمایش در پالت: فقط وقتی همان نوع صفحه باز است
WIDGET_CTX = {
    'topbar': 'header', 'logo': 'header', 'search': 'header',
    'category_mega': 'header', 'category_strip': 'header',
    'icon_link': 'header', 'user_menu': 'header', 'nav_menu': 'header',
    'footer_about': 'footer', 'link_list': 'footer', 'contact_info': 'footer',
    'socials': 'footer', 'mobile_item': 'footer', 'mobile_link': 'footer',
    'current_course': 'theme', 'current_teacher': 'theme',
    'user_dashboard': 'theme',
    'post_title': 'theme', 'post_content': 'theme', 'featured_image': 'theme',
    'post_info': 'theme', 'post_comments': 'theme', 'author_box': 'theme',
}

# محتوای شروع واقعی برای ویجت تازه‌افزوده‌شده — تا جعبه خالی دیده نشود
WIDGET_STARTERS = {
    'heading': dict(text='عنوان بخش', tag='h2', align='right', mb='16'),
    'text': dict(content='متن خود را اینجا بنویسید.', align='right', size='15'),
    'text_editor': dict(content='<p>متن خود را اینجا بنویسید.</p>', align='right'),
    'button': dict(text='مشاهده دوره‌ها', url='/courses', btn_style='primary',
                   size='md', hover='lift', align='right'),
    'spacer': dict(height=40),
    'divider': dict(height='1', line_style='solid', width='100'),
    'image': dict(width='100', radius='16', filter='none', opacity='100'),
    'countdown': dict(title='شمارش معکوس', text='تاریخ هدف را از پنل تنظیم کنید.'),
    'slider': dict(
        slides=[dict(img='hero.webp', title='دوره‌های آموزشی',
                     sub='فهرست دوره‌های منتشرشده را ببینید و گزینه مناسب را انتخاب کنید.',
                     btn_text='مشاهده دوره‌ها', btn_url='/courses', align='right')],
        height='420', overlay='60', autoplay=True, interval='5',
        dots=True, arrows=True, swipe=True,
    ),
    'video_bg': dict(title='عنوان بنر ویدیویی',
                     sub='توضیح کوتاه این بخش را بنویسید.',
                     btn_text='مشاهده دوره‌ها', btn_url='/courses'),
    'hero': dict(title='دوره‌های آموزشی',
                 sub='سرفصل، مدرس و شرایط هر دوره را پیش از ثبت‌نام ببینید.',
                 image='hero.webp', btn_text='مشاهده دوره‌ها', btn_url='/courses',
                 align='right', height='420', overlay='60', radius='0'),
    'courses': dict(title='دوره‌های آموزشی', limit='6', columns='3', sort='newest',
                    link_text='همه دوره‌ها', link_url='/courses', show_price=True),
    'categories': dict(title='دسته‌بندی دوره‌ها', columns='4'),
    'posts': dict(title='آخرین مقالات', limit='3', columns='3',
                  link_text='همه مقالات', link_url='/blog'),
    'teachers': dict(title='اساتید', limit=4, columns='4'),
    'feature': dict(columns='3', items=[
        dict(icon='🎬', title='جلسات دوره',
             text='سرفصل و مدت هر دوره را پیش از خرید ببینید.'),
        dict(icon='🏅', title='گواهی قابل استعلام',
             text='پس از تکمیل دوره، کد رهگیری صادر می‌شود.'),
        dict(icon='💬', title='پشتیبانی',
             text='از داخل حساب کاربری تیکت ثبت کنید.'),
    ]),
    'stats': dict(columns='4', items=[
        dict(value='{courses}', label='دوره آموزشی'),
        dict(value='{students}', label='دانشجوی فعال'),
        dict(value='{hours}', label='ساعت آموزش'),
        dict(value='{lessons}', label='درس منتشرشده'),
    ]),
    'faq': dict(title='پرسش‌های متداول', items=[
        dict(q='چگونه دوره بخرم؟',
             a='دوره را به سبد اضافه کنید و یکی از روش‌های پرداخت فعال را انتخاب کنید.'),
        dict(q='گواهی چگونه صادر می‌شود؟',
             a='پس از تکمیل دوره، گواهی با کد رهگیری قابل استعلام صادر می‌شود.'),
    ]),
    'cta': dict(title='آماده شروع هستید؟',
                text='دوره‌های منتشرشده را ببینید و مسیر یادگیری خود را انتخاب کنید.',
                btn_text='مشاهده دوره‌ها', btn_url='/courses', cta_style='gradient'),
    'newsletter': dict(title='عضویت در خبرنامه',
                       text='جدیدترین دوره‌ها را از دست ندهید.'),
    'icon_box': dict(icon='✨', title='عنوان ویژگی',
                     text='توضیح کوتاه این ویژگی را بنویسید.', align='center'),
    'image_box': dict(title='عنوان', text='توضیح کوتاه', align='center'),
    'alert': dict(type='info', title='توجه',
                  content='متن اطلاع‌رسانی را بنویسید.', dismiss=True),
    'form': dict(button_text='ارسال', align='right',
                 success_msg='پیام شما ثبت شد.', to='contact',
                 fields=[
                     dict(label='نام', type='text', required=True),
                     dict(label='ایمیل', type='email', required=True),
                     dict(label='پیام', type='textarea', required=True),
                 ]),
    'cert_verify': dict(title='استعلام گواهینامه',
                        text='کد رهگیری درج‌شده روی گواهی را وارد کنید.'),
    'course_search': dict(placeholder='جستجو در دوره‌ها...', show_cat=True,
                          button='جستجو'),
    'shop_products': dict(title='فروشگاه محصولات', limit='8', columns='4',
                          show_price=True, link_text='همه محصولات',
                          link_url='/products', sort='newest'),
    'bundles': dict(title='بسته‌های آموزشی', limit='6', columns='3',
                    show_price=True),
    'icon': dict(icon='⭐', size='64', align='center'),
    'google_maps': dict(height='400', radius='12'),
    'search': dict(placeholder='جستجو در دوره‌ها...', show_cat=True),
    'logo': dict(text='آکادمی آنلاین', icon='🎓'),
    'nav_menu': dict(align='right'),
    'footer_about': dict(socials=True),
    'amazing_offer': dict(title='پیشنهاد ویژه', item_type='course',
                          btn_text='مشاهده پیشنهاد'),
    'reviews': dict(title='نظرات دانشجویان', limit='6'),
    'success_stories': dict(title='داستان‌های موفقیت', limit='3'),
    'exam_cta': dict(title='آزمون تمرینی',
                     text='با سوالات تصادفی از بانک سوال تمرین کنید.'),
    'accordion': dict(first_open=True, items=[
        dict(title='عنوان اول', content='محتوای این بخش را بنویسید.'),
    ]),
    'tabs': dict(orientation='horizontal', active=0, items=[
        dict(title='تب اول', content='محتوای تب اول.'),
        dict(title='تب دوم', content='محتوای تب دوم.'),
    ]),
    'add_to_cart': dict(text='افزودن به سبد', btn_style='primary', align='right'),
    'cart_widget': dict(title='سبد خرید شما', show_total=True),
    'product_details': dict(show_price=True, show_teacher=True,
                            show_rating=True, show_students=True, show_meta=True),
}

# صفحات ثابت سایت که نسخه‌ساز صفحه‌ساز دارند (slug, عنوان, قالب, مسیر زنده)
SITE_PAGES = [
    (s['slug'], s['title'], s['template'], s['url'])
    for s in site_page_specs()
]

SINGLETON_PTYPES = ('home', 'header', 'footer', 'footer_mobile', 'mobile_menu',
                    '404', 'course', 'teacher', 'post')


def _widgets_for_client():
    """نسخهٔ ویجت‌ها برای جاوااسکریپت ویرایشگر — با پرچم پالت و محتوای شروع."""
    out = {}
    for key, widget in WIDGETS.items():
        item = dict(widget)
        item['palette'] = key not in PALETTE_HIDDEN
        item['ctx'] = WIDGET_CTX.get(key, '')
        item['starter'] = WIDGET_STARTERS.get(key, {})
        out[key] = item
    return out


def page_public_url(page):
    """آدرس زندهٔ صفحه برای پیش‌نمایش و لینک فهرست."""
    spec = section_spec_for_page(page)
    if spec:
        return spec.get('url') or '/'
    slug = getattr(page, 'slug', '') or ''
    try:
        return url_for('site.custom_page', slug=slug)
    except Exception:
        return '/page/' + slug


def _set_setting(key, value):
    from models import Setting
    row = db.session.get(Setting, key)
    value = '' if value is None else str(value)
    if row:
        row.value = value
    else:
        db.session.add(Setting(key=key, value=value))


def _clear_app_cache():
    try:
        from flask import current_app
        clearer = getattr(current_app, 'clear_cache', None)
        if clearer:
            clearer()
    except Exception:
        pass


def _activate_builder_home(page=None):
    """صفحهٔ صفحه‌ساز را به‌عنوان صفحه اصلی سایت (/) فعال کن."""
    _set_setting('home_design', 'builder')
    if page is not None and getattr(page, 'slug', None):
        _set_setting('home_page_slug', page.slug)


def ensure_home_page(seed=True):
    """صفحهٔ ptype=home را بساز یا برگردان؛ در صورت خالی بودن قالب لندینگ بگذار."""
    page = Page.query.filter_by(ptype='home').first()
    created = False
    if page is None:
        slug = 'home'
        n = 2
        while Page.query.filter_by(slug=slug).first():
            slug = f'home-{n}'
            n += 1
        rows = PAGE_TEMPLATES['landing']['rows'] if seed else []
        page = Page(title='صفحه اصلی', slug=slug, ptype='home',
                    is_published=True,
                    content=json.dumps({'settings': {}, 'rows': rows},
                                       ensure_ascii=False))
        db.session.add(page)
        created = True
    elif seed and not page.rows():
        parsed = page.parsed()
        parsed['rows'] = PAGE_TEMPLATES['landing']['rows']
        page.content = json.dumps(parsed, ensure_ascii=False)
    _activate_builder_home(page)
    db.session.commit()
    _clear_app_cache()
    return page, created


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
    """مقادیر پیش‌فرض فیلدهای یک ویجت + محتوای شروع قابل‌ویرایش"""
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
    starter = WIDGET_STARTERS.get(wtype)
    if starter:
        d.update(json.loads(json.dumps(starter)))
    return d


_BUILDER_URL_KEYS = {'url', 'link', 'btn_url'}
_BUILDER_NUMERIC_STYLE_KEYS = {'radius', 'pt', 'pb', 'mt', 'mb'}


def _safe_builder_url(value):
    from html_sanitizer import safe_url
    return safe_url(value)


def _safe_builder_image(value):
    """مرجع تصویر محلی؛ scheme/path traversal و CSS-breaking رد می‌شود."""
    value = str(value or '').strip()[:500]
    if (not value or '..' in value or '\\' in value or '://' in value or
            any(char in value for char in ('\x00', '\r', '\n', '"', "'", '<', '>'))):
        return ''
    return value if re.match(r'^/?[A-Za-z0-9_./-]+$', value) else ''


def _safe_css_value(value):
    """مقدار ساده CSS بدون امکان بستن declaration یا بارگذاری URL بیرونی."""
    value = str(value or '').strip()[:120]
    lowered = value.lower()
    if (not value or any(char in value for char in (';', '{', '}', '<', '>', '"', "'")) or
            any(token in lowered for token in ('url(', 'expression', '@import',
                                                'javascript:', 'behavior:'))):
        return ''
    return value


def _safe_css_identifier(value, multiple=False):
    value = str(value or '').strip()[:160]
    pattern = r'^[A-Za-z_][A-Za-z0-9_-]*(?:\s+[A-Za-z_][A-Za-z0-9_-]*)*$' \
        if multiple else r'^[A-Za-z_][A-Za-z0-9_-]*$'
    return value if re.match(pattern, value) else ''


def _builder_bool(value):
    return value is True or str(value).lower() in ('1', 'true', 'yes', 'on')


def _sanitize_builder_field(field, value):
    key = field.get('key', '')
    ftype = field.get('type', 'text')
    if ftype == 'checkbox':
        return _builder_bool(value)
    if ftype == 'number':
        try:
            return max(-1000000, min(1000000, int(value or 0)))
        except (TypeError, ValueError):
            return 0
    if isinstance(value, (int, float)):
        value = str(value)
    elif not isinstance(value, str):
        value = ''
    if key in _BUILDER_URL_KEYS:
        return _safe_builder_url(value)
    if ftype == 'image':
        return _safe_builder_image(value)
    if ftype == 'color':
        return _safe_css_value(value)
    if ftype == 'select' and field.get('options'):
        allowed = {str(option[0] if isinstance(option, (list, tuple)) else option)
                   for option in field['options']}
        return value if value in allowed else ''
    limit = 50000 if ftype in ('textarea', 'richtext') else 3000
    return value[:limit]


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
            for it in merged[f['key']][:100]:
                if not isinstance(it, dict):
                    continue
                itd = {}
                for sf in f.get('item_fields', []):
                    raw = it.get(sf['key'], False if sf['type'] == 'checkbox' else '')
                    itd[sf['key']] = _sanitize_builder_field(sf, raw)
                cleaned_items.append(itd)
            merged[f['key']] = cleaned_items
        else:
            merged[f['key']] = _sanitize_builder_field(
                f, merged.get(f['key'], False if f['type'] == 'checkbox' else ''))
    # مهاجرت داده قدیمی: ویجت‌هایی که فیلد «style» رشته‌ای داشتند (دکمه/جداکننده/CTA/سبد)
    _style_migrate = {'button': 'btn_style', 'add_to_cart': 'btn_style',
                      'divider': 'line_style', 'cta': 'cta_style'}
    if wt in _style_migrate:
        newk = _style_migrate[wt]
        if not merged.get(newk) and isinstance(merged.get('style'), str) and merged['style']:
            merged[newk] = merged['style']
        if isinstance(merged.get('style'), str):
            merged.pop('style', None)
    # کلاس/id و آبجکت تب استایل فقط از مقادیر محدود CSS ساخته می‌شوند.
    merged['css_class'] = _safe_css_identifier(merged.get('css_class'), multiple=True)
    merged['css_id'] = _safe_css_identifier(merged.get('css_id'))
    if isinstance(merged.get('style'), dict):
        raw_style = merged['style']
        merged['style'] = {
            'align': raw_style.get('align') if raw_style.get('align') in
                     ('right', 'center', 'left', 'justify') else '',
            'color': _safe_css_value(raw_style.get('color')),
            'bg': _safe_css_value(raw_style.get('bg')),
            'width': _safe_css_value(raw_style.get('width')),
        }
        for style_key in _BUILDER_NUMERIC_STYLE_KEYS:
            try:
                merged['style'][style_key] = max(
                    -500, min(2000, int(raw_style.get(style_key) or 0)))
            except (TypeError, ValueError):
                merged['style'][style_key] = 0
    else:
        merged['style'] = {}
    if wt == 'inner_section':
        inner_cols = []
        for col in (wd.get('cols') or [])[:12]:
            if not isinstance(col, list):
                inner_cols.append([])
                continue
            inner_cols.append([x for x in
                               (_sanitize_widget(x) for x in col[:200]) if x])
        merged['cols'] = inner_cols
    widget_id = _safe_css_identifier(w.get('id')) or _new_id('w')
    return {'id': widget_id, 'type': wt, 'data': merged}


def _sanitize_row_settings(value):
    raw = value if isinstance(value, dict) else {}
    settings = {
        'bg': _safe_css_value(raw.get('bg')),
        'bg_image': _safe_builder_image(raw.get('bg_image')),
        'widths': _safe_css_value(raw.get('widths')),
        'css_class': _safe_css_identifier(raw.get('css_class'), multiple=True),
        'css_id': _safe_css_identifier(raw.get('css_id')),
        'hide_mobile': _builder_bool(raw.get('hide_mobile')),
        'hide_desktop': _builder_bool(raw.get('hide_desktop')),
        'locked': _builder_bool(raw.get('locked')),
    }
    for key in ('gap', 'radius', 'py', 'pt', 'pb', 'mt', 'mb'):
        try:
            settings[key] = max(-500, min(2000, int(raw.get(key) or 0)))
        except (TypeError, ValueError):
            settings[key] = 0
    return settings


def _sanitize_page_settings(value):
    raw = value if isinstance(value, dict) else {}
    return {
        'page_bg': _safe_css_value(raw.get('page_bg')),
        'seo_title': str(raw.get('seo_title') or '').strip()[:200],
        'seo_desc': str(raw.get('seo_desc') or '').strip()[:500],
        'hide_header': _builder_bool(raw.get('hide_header')),
        'hide_footer': _builder_bool(raw.get('hide_footer')),
        'template_name': str(raw.get('template_name') or '').strip()[:100],
    }


def _sanitize_rows(rows):
    """پاکسازی داده‌های صفحه‌ساز با سقف اندازه برای جلوگیری از render DoS."""
    out = []
    if not isinstance(rows, list):
        return out
    for r in rows[:200]:
        if not isinstance(r, dict):
            continue
        cols = []
        raw_cols = r.get('cols') if isinstance(r.get('cols'), list) else []
        for c in raw_cols[:12]:
            if not isinstance(c, list):
                continue
            cols.append([x for x in (_sanitize_widget(x) for x in c[:200]) if x])
        row_id = _safe_css_identifier(r.get('id')) or _new_id('r')
        out.append({'id': row_id, 'settings': _sanitize_row_settings(r.get('settings')),
                    'cols': cols})
    return out


def _dynamic_value(key):
    """مقداردهی تگ‌های پویا از دیتابیس"""
    from flask import g as _g
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
            # ⚠️ این endpoint فقط پارامتر slug می‌گیرد؛ ارسال pid باعث BuildError
            # می‌شد و ویجتِ تاریخچهٔ قیمتِ محصولات (لینک + قیمت فعلی) از کار می‌افتاد.
            if item: url = url_for('products.product_detail', slug=item.slug)
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
    # مقایسه فقط از داده واقعی ثبت‌شده مدیر در competitive_prices خوانده می‌شود.
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
    # قیمت رقبا هرگز تخمینی ساخته نمی‌شود؛ فقط داده‌ای که مدیر واقعاً ثبت کرده.
    return dict(item=item, url=url, points=points, current=current, compare=compare)


def builder_amazing_offer(d):
    """داده باکس پیشنهاد شگفت‌انگیز — آیتم دارای بیشترین تخفیف"""
    from cache_safe import CourseLite
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
        # fallback: دورهٔ با بیشترین درصد تخفیف.
        # ⚠️ discount_percent یک property (محاسبه‌شده) است نه ستون جدول؛
        # فیلتر/مرتب‌سازی مستقیم با آن روی کوئری SQLAlchemy باعث خطای 500
        # (TypeError: '>' not supported between 'property' and 'int') می‌شد.
        # بنابراین نامزدها را با ستون‌های واقعی می‌گیریم و در پایتون بهترین را
        # بر اساس همان property انتخاب می‌کنیم.
        candidates = _C.query.filter(
            _C.status == 'published',
            _C.discount_price > 0,
            _C.discount_price < _C.price,
        ).order_by(_C.discount_price.asc()).limit(50).all()
        item = max(candidates, key=lambda c: c.discount_percent, default=None)
    url = '#'
    if item:
        url = url_for('products.product_detail', slug=item.slug) if hasattr(item, 'stock') \
            else url_for('site.course_detail', slug=item.slug)
    disc = item.discount_percent if item and hasattr(item, 'discount_percent') else 0
    if item is not None and not hasattr(item, 'stock'):
        # نسخهٔ سبک برای کش — فقط فیلدهای موردنیاز قالب
        item = CourseLite(item, rating=0, review_count=0, students_count=0)
    return dict(item=item, url=url, discount=disc or 0)


def builder_review_pro(d):
    """نظرات پیشرفته — از Review با pros/cons و تأیید خرید"""
    cid = int(d.get('item_id') or 0) if d.get('item_type') != 'product' else 0
    _lim = max(1, min(12, int(d.get('limit') or 6)))

    def _q():
        from models import Review as _R
        from cache_safe import review_lite
        q = _R.query.options(db.joinedload(_R.user), db.joinedload(_R.course)) \
            .filter_by(is_approved=True).order_by(_R.id.desc())
        if cid:
            q = q.filter_by(course_id=cid)
        rows = q.limit(_lim).all()
        return dict(reviews=[review_lite(r) for r in rows])
    try:
        return _b_cache(f'review_pro:{cid}:{_lim}', 60, _q)
    except Exception:
        return dict(reviews=[])


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
    f = (d or {}).get('filter', 'all')
    _lim = int((d or {}).get('limit') or 8)

    def _q():
        from cache_safe import course_lite
        q = Course.query.options(db.joinedload(Course.category),
                                 db.joinedload(Course.teacher)) \
            .filter_by(status='published')
        if f == 'sale':
            q = q.filter(Course.discount_price > 0, Course.discount_price < Course.price)
        elif f == 'featured':
            q = q.filter(Course.featured == True)
        elif f == 'popular':
            q = q.order_by(Course.views.desc())
        else:
            q = q.order_by(Course.created_at.desc())
        rows = _attach_course_aggs(q.limit(_lim).all())
        return [course_lite(c) for c in rows]
    return _b_cache(f'products:{f}:{_lim}', 60, _q)


def bc_menu(menu_id):
    """آیتم‌های یک منوی ذخیره‌شده (با فیلتر نقش و ساختار زیرمنو) برای ویجت منوی ناوبری"""
    try:
        from models import Menu as _Menu
        m = _Menu.query.filter_by(id=int(menu_id or 0), is_active=True).first()
    except Exception:
        return []
    if not m:
        return []
    role = ''
    try:
        from flask import g as _g
        u = getattr(_g, 'user', None)
        role = (u.role or '') if u else ''
    except Exception:
        pass
    ordered = sorted(m.items, key=lambda it: it.sort or 0)
    visible = []
    for it in ordered:
        roles = [r.strip() for r in (it.roles or '').split(',') if r.strip()]
        if roles and role not in roles:
            continue
        visible.append({'id': it.id, 'label': it.label, 'url': it.url, 'icon': it.icon,
                        'parent_id': it.parent_id, 'children': []})
    by_id = {it['id']: it for it in visible}
    roots = []
    for it in visible:
        p = by_id.get(it['parent_id'])
        if p is not None:
            p['children'].append(it)
        else:
            roots.append(it)
    return roots


def render_shortcodes(text):
    """رندر شورت‌کدهای ساده: [courses limit=4] [categories] [posts] [button] [alert] [anchor]"""
    from html_sanitizer import sanitize_markup
    text = render_dynamic(text or '')
    def at(attrs, key, default=''):
        mm = re.search(key + r'="([^"]*)"', attrs)
        return mm.group(1) if mm else default

    def repl(m):
        if m.group(1):
            name, attrs, inner = m.group(1), m.group(2) or '', ''
        else:
            name, attrs, inner = m.group(3), m.group(4) or '', m.group(5) or ''
        if name == 'courses':
            lim = max(1, min(24, int(at(attrs, 'limit', '4') or 4)))
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
            lim = max(1, min(24, int(at(attrs, 'limit', '3') or 3)))
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
    return sanitize_markup(_SHORTCODE_RE.sub(repl, text))


_SHORTCODE_RE = re.compile(
    r'\[(courses|categories|posts|button|anchor)([^\]]*)\]|\[(alert)([^\]]*)\]([\s\S]*?)\[/alert\]')


def _slugify(t):
    # از تابع مشترک models استفاده می‌شود تا نیم‌فاصله، ارقام فارسی و
    # نویسه‌های عربی در همه‌جای سایت یکسان به اسلاگ تبدیل شوند.
    from models import make_slug
    return make_slug(t, fallback='')


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


def _attach_course_aggs(courses):
    """آمار تجمیعی دوره‌ها (نظر/امتیاز/دانشجو) — یک کوئری به‌جای بارگذاری همه رکوردها.
    این‌جا صرفاً به `annotate_course_stats` در models.py واگذار می‌شود تا یک منبع واحد باشد."""
    from models import annotate_course_stats
    return annotate_course_stats(courses)


def builder_courses(d):
    cat = (d or {}).get('category') or ''
    sort = (d or {}).get('sort', 'newest')
    _lim = int((d or {}).get('limit') or 8)

    def _q():
        from cache_safe import course_lite
        q = (Course.query
             .options(db.joinedload(Course.category), db.joinedload(Course.teacher))
             .filter_by(status='published'))
        if str(cat).isdigit():
            q = q.filter_by(category_id=int(cat))
        # مرتب‌سازی بر اساس قیمت نهایی مؤثر (نه discount_price خام که برای
        # دورهٔ بدون تخفیف صفر است) — مثل لیست اصلی دوره‌ها.
        from sqlalchemy import case as _case, and_ as _and
        _final_price = _case(
            (_and(Course.discount_price > 0, Course.discount_price < Course.price),
             Course.discount_price),
            else_=Course.price,
        )
        order = {'newest': Course.created_at.desc(), 'popular': Course.views.desc(),
                 'cheap': _final_price.asc(), 'expensive': _final_price.desc()}.get(sort, Course.created_at.desc())
        rows = _attach_course_aggs(q.order_by(order).limit(_lim).all())
        # نسخهٔ سبک غیر-ORM — ایمن برای کش بین درخواست‌ها
        return [course_lite(c) for c in rows]
    return _b_cache(f'courses:{cat}:{sort}:{_lim}', 60, _q)


def builder_categories(d):
    lim = int((d or {}).get('limit') or 0)
    def _q():
        from cache_safe import category_lite, course_lite
        q = Category.query.order_by(Category.sort)
        cat_rows = q.limit(lim).all() if lim else q.all()
        # دوره‌های منتشر هر دسته (عنوان/اسلاگ) — یک کوئری
        course_rows = Course.query.filter_by(status='published').all()
        by_cat = {}
        for c in course_rows:
            by_cat.setdefault(c.category_id, []).append(course_lite(c))
        return [category_lite(c, by_cat.get(c.id, [])) for c in cat_rows]
    return _b_cache(f'cats:{lim}', 120, _q)


def builder_posts(d):
    lim = int((d or {}).get('limit') or 3)
    def _q():
        from cache_safe import post_lite
        q = BlogPost.query.filter_by(published=True).order_by(BlogPost.created_at.desc())
        rows = q.limit(lim).all()
        return [post_lite(p) for p in rows]
    return _b_cache(f'posts:{lim}', 60, _q)


def builder_teachers(d):
    lim = int((d or {}).get('limit') or 4)
    def _q():
        from cache_safe import TeacherLite
        rows = User.query.filter(User.role == 'teacher').limit(lim).all()
        return [TeacherLite(u.id, u.name, u.avatar_color, u.bio or '') for u in rows]
    return _b_cache(f'teachers:{lim}', 120, _q)


def builder_shop_products(d):
    sort = (d or {}).get('sort', 'newest')
    _lim = max(1, min(24, int((d or {}).get('limit') or 8)))
    def _q():
        from models import Product
        from cache_safe import product_lite
        q = Product.query.filter_by(is_active=True)
        order = {
            'newest': Product.created_at.desc(),
            'popular': Product.views.desc(),
            'cheap': Product.price.asc(),
            'expensive': Product.price.desc(),
        }.get(sort, Product.created_at.desc())
        rows = q.order_by(order).limit(_lim).all()
        return [product_lite(p) for p in rows]
    return _b_cache(f'shop_products:{sort}:{_lim}', 60, _q)


def builder_bundles(d):
    _lim = max(1, min(24, int((d or {}).get('limit') or 6)))
    def _q():
        from models import Bundle
        from cache_safe import bundle_lite
        rows = (Bundle.query.filter_by(is_active=True)
                .order_by(Bundle.created_at.desc()).limit(_lim).all())
        return [bundle_lite(b) for b in rows]
    return _b_cache(f'bundles:{_lim}', 60, _q)


def builder_special_offers(d):
    """پیشنهادهای ویژه — دوره‌های منتشرشدهٔ تخفیف‌دار واقعی (بیشترین تخفیف)."""
    _lim = max(1, min(12, int((d or {}).get('limit') or 4)))
    def _q():
        from cache_safe import course_lite
        from sqlalchemy import case as _case, and_ as _and
        _final = _case(
            (_and(Course.discount_price > 0, Course.discount_price < Course.price),
             Course.discount_price),
            else_=Course.price)
        _off = (Course.price - _final) * 100 / Course.price
        q = (Course.query
             .options(db.joinedload(Course.category), db.joinedload(Course.teacher))
             .filter_by(status='published')
             .filter(Course.discount_price > 0, Course.discount_price < Course.price))
        rows = _attach_course_aggs(q.order_by(_off.desc()).limit(_lim).all())
        return [course_lite(c) for c in rows]
    return _b_cache(f'special_offers:{_lim}', 60, _q)


def builder_related_products(d):
    """محصولات مرتبط فروشگاه — بر اساس دسته (یا جدیدترین‌ها)."""
    cat = (d or {}).get('category') or ''
    _lim = max(1, min(16, int((d or {}).get('limit') or 4)))
    def _q():
        from models import Product
        from cache_safe import product_lite
        q = Product.query.filter_by(is_active=True)
        if str(cat).isdigit():
            q = q.filter_by(category_id=int(cat))
        rows = q.order_by(Product.created_at.desc()).limit(_lim).all()
        return [product_lite(p) for p in rows]
    return _b_cache(f'related_products:{cat}:{_lim}', 60, _q)


def countdown_secs(target):
    """ثانیهٔ باقی‌مانده تا تاریخ هدف میلادی — برای بنر تخفیف و شمارش معکوس مطلق."""
    s = str(target or '').strip()
    if not s:
        return 0
    from datetime import datetime
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            dt = datetime.strptime(s, fmt)
            if fmt == '%Y-%m-%d':
                dt = dt.replace(hour=23, minute=59, second=0)
            return max(0, int((dt - datetime.now()).total_seconds()))
        except ValueError:
            continue
    return 0


def bc_verify_result():
    """نتیجهٔ استعلام گواهی در صفحهٔ صفحه‌ساز (از g.verify_result)."""
    from flask import g as _g
    return getattr(_g, 'verify_result', None)


def builder_cat_options():
    return [(str(c.id), c.name) for c in Category.query.order_by(Category.sort).all()]


# ------------------------------------------------------------------
# مسیرهای صفحه‌ساز
# ------------------------------------------------------------------
_LIBRARY_LOCK = threading.Lock()


def _library_path(kind):
    root = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        'instance', 'libraries')
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, kind + '_library.json')


def _load_library(kind):
    path = _library_path(kind)
    try:
        with open(path, encoding='utf-8') as handle:
            value = json.load(handle)
        return value if isinstance(value, list) else []
    except (OSError, ValueError, TypeError):
        return []


def _append_library(kind, item):
    """افزودن اتمیک قالب به instance؛ امن در برابر چند thread/worker."""
    encoded = json.dumps(item, ensure_ascii=False)
    if len(encoded.encode('utf-8')) > 500 * 1024:
        return False, 'حجم قالب بیشتر از ۵۰۰ کیلوبایت است.'
    path = _library_path(kind)
    lock_path = path + '.lock'
    with _LIBRARY_LOCK:
        lock_handle = open(lock_path, 'a+')
        try:
            try:
                import fcntl
                fcntl.flock(lock_handle, fcntl.LOCK_EX)
            except Exception:
                pass
            library = _load_library(kind)
            library.append(item)
            library = library[-100:]  # جلوگیری از رشد نامحدود فایل
            temp_path = path + '.tmp-' + uuid.uuid4().hex[:8]
            with open(temp_path, 'w', encoding='utf-8') as handle:
                json.dump(library, handle, ensure_ascii=False)
            os.replace(temp_path, path)
        finally:
            try:
                lock_handle.close()
            except Exception:
                pass
    return True, 'در کتابخانه ذخیره شد.'


def _persian_designs_meta():
    """متادیتای ۲۰ طرح برای صفحه‌ساز (پالت + نام + دسته)"""
    from persian_themes import PERSIAN_THEMES
    return [dict(id=t['id'], name=t['name'], category=t['category'],
                 dark=t.get('dark', False),
                 colors=[t['colors']['primary'], t['colors']['accent'], t['colors']['secondary']])
            for t in PERSIAN_THEMES]


def _admin_required():
    if not g.user:
        return redirect(url_for('auth.login', next=request.path))
    from permissions import has_permission
    if not has_permission(g.user, 'manage_builder'):
        abort(403)
    return None


def _builder_csrf_ok():
    """POSTهای JSON صفحه‌ساز از CSRF سراسری معاف‌اند؛ اینجا توکن سشن چک می‌شود."""
    import hmac
    from flask import session
    token = (request.headers.get('X-CSRF-Token') or
             request.form.get('_csrf_token') or '')
    expected = session.get('_csrf_token') or ''
    return bool(token) and bool(expected) and hmac.compare_digest(str(token), str(expected))


@builder_bp.route('/builder')
def index():
    r = _admin_required()
    if r:
        return r
    pages = Page.query.order_by(Page.updated_at.desc()).all()
    section_lib = _load_library('section')
    page_lib = _load_library('page')
    types = {'home': 'صفحه اصلی', 'header': 'هدر سایت', 'footer': 'فوتر سایت',
             'footer_mobile': 'فوتر موبایل', 'mobile_menu': 'منوی موبایل',
             'page': 'صفحه معمولی', '404': 'صفحه خطای ۴۰۴',
             'post': 'قالب مقاله', 'course': 'قالب دوره', 'teacher': 'قالب مدرس'}
    home = next((p for p in pages if p.ptype == 'home'), None)
    chrome = {pt: next((p for p in pages if p.ptype == pt), None)
              for pt in ('header', 'footer', 'footer_mobile', 'mobile_menu')}
    site_slugs = {spec[0] for spec in SITE_PAGES}
    site_status = []
    by_slug = {p.slug: p for p in pages}
    for spec in site_page_specs():
        site_status.append(dict(spec, page=by_slug.get(spec['slug'])))
    theme_status = []
    for spec in theme_specs():
        theme_status.append(dict(spec, page=next(
            (p for p in pages if p.ptype == spec['ptype']), None)))
    custom_pages = [p for p in pages
                    if p.ptype == 'page' and p.slug not in site_slugs]
    other_pages = [p for p in pages
                   if p.ptype not in SINGLETON_PTYPES
                   and not (p.ptype == 'page' and p.slug in site_slugs)]
    home_live = False
    try:
        from models import Setting
        design_row = db.session.get(Setting, 'home_design')
        design = (design_row.value if design_row else '1') or '1'
        slug_row = db.session.get(Setting, 'home_page_slug')
        hp_slug = ((slug_row.value if slug_row else '') or '').strip()
        if home and home.is_published and home.rows() and (
                design == 'builder' or hp_slug == home.slug):
            home_live = True
        if hp_slug:
            chosen = by_slug.get(hp_slug)
            if chosen and chosen.is_published and chosen.rows():
                home_live = True
    except Exception:
        home_live = bool(home and home.is_published and home.rows())
    return render_template('builder/index.html', pages=pages, types=types,
                           section_lib=section_lib, page_lib=page_lib,
                           home=home, chrome=chrome, site_status=site_status,
                           theme_status=theme_status,
                           custom_pages=custom_pages, other_pages=other_pages,
                           home_live=home_live,
                           page_public_url=page_public_url)


@builder_bp.route('/builder/open-home')
def open_home():
    """یک کلیک: صفحه اصلی را بساز/باز کن و روی / نمایش بده.

    مسیر جدا از ``/builder/<slug>`` است تا اسلاگ واقعیِ ``home``
    به حلقهٔ ریدایرکت نیفتد.
    """
    r = _admin_required()
    if r:
        return r
    page, created = ensure_home_page(seed=True)
    if created:
        flash('صفحه اصلی ساخته شد و روی نشانی / فعال است. عناصر را اضافه کنید و ذخیره کنید.', 'success')
    else:
        flash('صفحه اصلی باز شد. تغییرات بعد از ذخیره روی نشانی / دیده می‌شود.', 'info')
    return redirect(url_for('builder.editor', slug=page.slug))


@builder_bp.route('/builder/open/<key>')
def open_section(key):
    """یک کلیک: بخش عمومی سایت را بساز (اگر نیست) و ویرایشگر را باز کن."""
    r = _admin_required()
    if r:
        return r
    if key not in SITE_SECTIONS:
        abort(404)
    spec = SITE_SECTIONS[key]
    page, created = ensure_section(key, seed=True)
    if created:
        flash(f'«{spec["title"]}» ساخته شد — عناصر را اضافه کنید و ذخیره کنید.', 'success')
    else:
        flash(f'«{spec["title"]}» باز شد. بعد از ذخیره روی نشانی {spec["url"]} دیده می‌شود.', 'info')
    return redirect(url_for('builder.editor', slug=page.slug))


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
    if ptype not in ('page', 'post', '404', 'home', 'header', 'footer',
                     'mobile_menu', 'footer_mobile', 'course', 'teacher'):
        ptype = 'page'
    if ptype in SINGLETON_PTYPES:
        if ptype in SITE_SECTIONS:
            page, created = ensure_section(ptype, seed=True)
            if not created:
                flash('این نوع صفحه از قبل وجود دارد — همان را باز کردیم.', 'info')
            return redirect(url_for('builder.editor', slug=page.slug))
        existing = Page.query.filter_by(ptype=ptype).first()
        if existing:
            if ptype == 'home':
                _activate_builder_home(existing)
                db.session.commit()
                _clear_app_cache()
            flash('این نوع صفحه از قبل وجود دارد — همان را باز کردیم.', 'info')
            return redirect(url_for('builder.editor', slug=existing.slug))
    if not title:
        flash('عنوان صفحه را وارد کنید.', 'error')
        return redirect(url_for('builder.index'))
    if ptype == 'home':
        page, _created = ensure_home_page(seed=True)
        return redirect(url_for('builder.editor', slug=page.slug))
    base = _slugify(title)
    slug = base or 'page'
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


@builder_bp.route('/builder/ensure-site-pages', methods=['POST'])
def ensure_site_pages():
    """ساخت نسخهٔ صفحه‌ساز برای صفحات ثابت سایت (درباره، تماس، قوانین و...).

    اگر صفحه‌ای با همان slug از قبل موجود باشد، دست‌نخورده می‌ماند؛
    برای صفحات جدید، ردیف‌های شروع از قالب‌های آمادهٔ موجود بارگذاری می‌شود.
    """
    r = _admin_required()
    if r:
        return r
    only = (request.form.get('only') or '').strip()
    specs = site_page_specs()
    if only:
        specs = [s for s in specs if s['key'] == only or s['slug'] == only]
    made = 0
    for spec in specs:
        _page, created = ensure_section(spec['key'], seed=True, publish=False)
        if created:
            made += 1
    if made:
        flash(f'نسخهٔ صفحه‌ساز {made} صفحهٔ ثابت ساخته شد. حالا از دکمه «ویرایش» محتوای هرکدام را کامل کنید. 🧩', 'success')
    elif only:
        flash('این صفحه از قبل در صفحه‌ساز موجود است.', 'info')
    else:
        flash('همهٔ صفحات ثابت از قبل در صفحه‌ساز موجود بودند.', 'info')
    return redirect(url_for('builder.index'))


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
        safe_settings = _sanitize_page_settings(data.get('settings', {}))
        safe_rows = _sanitize_rows(data.get('rows', []))
        page = Page(title=title, slug=slug, ptype=ptype, is_published=False,
                    content=json.dumps({'settings': safe_settings,
                                        'rows': safe_rows}, ensure_ascii=False))
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
    from models import Menu as _Menu
    menu_options = [[str(m.id), m.title] for m in
                    _Menu.query.filter_by(is_active=True).order_by(_Menu.title).all()]
    if page.ptype == 'home':
        _activate_builder_home(page)
        db.session.commit()
        _clear_app_cache()
    return render_template('builder/editor.html', page=page,
                           widgets=_widgets_for_client(),
                           cats=WIDGET_CATS, images=IMG_OPTIONS,
                           cat_options=builder_cat_options(), other_pages=other_pages,
                           course_options=course_options, menu_options=menu_options,
                           section_templates=SECTION_TEMPLATES,
                           page_templates=PAGE_TEMPLATES,
                           preview_url=page_public_url(page),
                           section_spec=section_spec_for_page(page),
                           persian_designs=_persian_designs_meta())


@builder_bp.route('/builder/api/render', methods=['POST'])
def api_render():
    r = _admin_required()
    if r:
        return jsonify(ok=False, msg='دسترسی غیرمجاز'), 403
    if not _builder_csrf_ok():
        return jsonify(ok=False, msg='توکن امنیتی نامعتبر است'), 400
    data = request.get_json(force=True)
    edit = bool(data.get('edit'))
    rows = _sanitize_rows(data.get('rows', []))
    parts = []
    for row in rows:
        try:
            parts.append(render_template('builder/fragment_row.html', row=row, edit=edit))
        except Exception as e:
            from markupsafe import escape
            from validators import log_exc
            log_exc('builder.render_row: ' + str(e)[:150])
            safe_error = str(escape(str(e)))
            parts.append('<div class="pb-row pb-row-error" title="' +
                         safe_error[:200] + '">⚠️ خطا در رندر این ردیف: ' +
                         safe_error[:120] +
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
    if not _builder_csrf_ok():
        return jsonify(ok=False, msg='توکن امنیتی نامعتبر است'), 400
    data = request.get_json(force=True)
    # محدودیت سایز منطقی صفحه — ضد DoS با JSON عظیم
    if len(json.dumps(data, ensure_ascii=False)) > 500_000:
        return jsonify(ok=False, msg='حجم صفحه بیش از حد مجاز است (۵۰۰KB)'), 413
    page = Page.query.filter_by(slug=data.get('slug', '')).first_or_404()
    safe_settings = _sanitize_page_settings(data.get('settings'))
    safe_rows = _sanitize_rows(data.get('rows'))
    new_content = json.dumps({'settings': safe_settings, 'rows': safe_rows},
                             ensure_ascii=False)
    # نسخه‌بندی: اگر محتوا تغییر کرده، نسخه قبلی ذخیره شود (تاریخچه)
    if page.content != new_content:
        from models import PageRevision
        db.session.add(PageRevision(page_id=page.id, content=page.content,
                                    note=str(data.get('note') or 'ویرایش خودکار')[:200],
                                    author_id=g.user.id if g.user else None))
        # حداکثر ۲۰ نسخه نگهداری شود
        old_revs = PageRevision.query.filter_by(page_id=page.id) \
            .order_by(PageRevision.created_at.desc()).offset(19).all()
        for o in old_revs:
            db.session.delete(o)
    page.content = new_content
    if 'published' in data:
        page.is_published = _builder_bool(data['published'])
    if page.ptype == 'home' and page.is_published:
        _activate_builder_home(page)
    db.session.commit()
    _clear_app_cache()
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
    if not _builder_csrf_ok():
        return jsonify(ok=False, msg='توکن امنیتی نامعتبر است'), 400
    from models import PageRevision
    rev = db.get_or_404(PageRevision, rev_id)
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
    if not _builder_csrf_ok():
        return jsonify(ok=False, msg='توکن امنیتی نامعتبر است'), 400
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()[:80]
    row = data.get('row')
    if not name or not isinstance(row, dict) or not row:
        return jsonify(ok=False, msg='نام و سکشن معتبر الزامی است'), 400
    clean_rows = _sanitize_rows([row])
    if not clean_rows:
        return jsonify(ok=False, msg='سکشن قابل ذخیره‌سازی نیست'), 400
    ok, message = _append_library('section', {'name': name, 'row': clean_rows[0]})
    return jsonify(ok=ok, msg=message), 200 if ok else 413


@builder_bp.route('/builder/api/page-template', methods=['POST'])
def api_page_template():
    """ذخیره صفحه به عنوان قالب آماده"""
    r = _admin_required()
    if r:
        return jsonify(ok=False), 403
    if not _builder_csrf_ok():
        return jsonify(ok=False, msg='توکن امنیتی نامعتبر است'), 400
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()[:80]
    rows = data.get('rows')
    settings = data.get('settings') or {}
    if not name or not isinstance(rows, list) or not rows or not isinstance(settings, dict):
        return jsonify(ok=False, msg='نام و محتوای معتبر صفحه الزامی است'), 400
    clean_rows = _sanitize_rows(rows)
    if not clean_rows:
        return jsonify(ok=False, msg='صفحه قابل ذخیره‌سازی نیست'), 400
    ok, message = _append_library(
        'page', {'name': name, 'rows': clean_rows,
                 'settings': _sanitize_page_settings(settings)})
    return jsonify(ok=ok, msg=message), 200 if ok else 413


@builder_bp.route('/builder/api/upload', methods=['POST'])
def api_upload():
    r = _admin_required()
    if r:
        return jsonify(ok=False), 403
    if not _builder_csrf_ok():
        return jsonify(ok=False, msg='توکن امنیتی نامعتبر است'), 400
    f = request.files.get('file')
    if not f:
        return jsonify(ok=False), 400
    from validators import (safe_filename, ALLOWED_IMAGE_EXT_TRUSTED,
                            file_content_is_safe)
    safe = safe_filename(f.filename or '', ALLOWED_IMAGE_EXT_TRUSTED)
    if not safe:
        return jsonify(ok=False, msg='فرمت فایل مجاز نیست (فقط تصویر)'), 400
    # محتوای واقعی فایل هم بررسی شود (SVG/تصویر حاوی <script> = XSS ذخیره‌شده)
    if not file_content_is_safe(f.stream, os.path.splitext(safe)[1].lower()):
        return jsonify(ok=False, msg='فایل حاوی کد اجرایی است و پذیرفته نشد'), 400
    up_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'img', 'uploads')
    os.makedirs(up_dir, exist_ok=True)
    ext = os.path.splitext(safe)[1].lower()
    name = 'up_' + uuid.uuid4().hex[:10] + ext
    dest = os.path.join(up_dir, name)
    f.save(dest)
    try:
        from uploads_helper import compress_image_file
        compress_image_file(dest)
    except Exception:
        pass
    return jsonify(ok=True, file=name)
