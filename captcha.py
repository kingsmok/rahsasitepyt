# -*- coding: utf-8 -*-
"""کپچای ساده ریاضی + هانی‌پات — ضد اسپم فرم‌های عمومی"""
import random
from flask import session, request


def gen_captcha():
    """ساخت کپچا و ذخیره پاسخ در session — خروجی: (متن نمایشی، نام فیلد پاسخ)"""
    a = random.randint(3, 9)
    b = random.randint(2, 9)
    op = random.choice(['+', '×'])
    answer = a + b if op == '+' else a * b
    session['captcha'] = str(answer)
    text = f'{a} {op} {b} = ?'
    session['captcha_text'] = text
    return text, 'captcha'


def current_captcha():
    """کپچای فعلی (بدون ساخت مجدد) — برای نمایش در قالب"""
    text = session.get('captcha_text')
    if text:
        return text
    return gen_captcha()[0]


def verify_captcha():
    """بررسی پاسخ کپچا — در صورت درستی، حذف از session"""
    ans = (request.form.get('captcha') or '').strip()
    correct = session.pop('captcha', '')
    session.pop('captcha_text', None)
    return bool(correct) and ans == correct


def verify_honeypot():
    """فیلد مخفی — ربات‌ها پر می‌کنند؛ اگر پر بود یعنی ربات است"""
    return not (request.form.get('hp_website') or '').strip()
