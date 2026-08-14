# -*- coding: utf-8 -*-
"""سرویس‌های رایگان و بدون تحریم — Clarity · Crisp · Groq · Bing Webmaster

همه کلیدها از متغیرهای محیطی (.env) خوانده می‌شوند:
    CLARITY_ID=...         Microsoft Clarity — تحلیل رفتار کاربر
    CRISP_WEBSITE_ID=...   Crisp Chat — پشتیبانی آنلاین
    GROQ_API_KEY=...       Groq (Llama-3) — تولید مقاله/چت هوشمند
    BING_API_KEY=...       Bing Webmaster — ایندکس سریع URL

اگر کلیدی تنظیم نشده باشد، سرویس به‌صورت خودکار غیرفعال می‌شود (بدون خطا).
"""
import os
import threading

import requests as _rq
from validators import log_exc as _lexc

# ---------------------------------------------------------------
# خواندن متغیرهای محیطی (با کش ساده)
# ---------------------------------------------------------------
_env_cache = {}


def env(key, default=''):
    """خواندن متغیر محیطی با کش — بعد از استارت، تغییر .env نیاز به ری‌استارت دارد"""
    if key not in _env_cache:
        _env_cache[key] = (os.environ.get(key) or '').strip()
    return _env_cache[key]


import re as _re

# شناسه‌های سرویس‌های بیرونی فقط می‌توانند حروف/عدد/خط‌تیره باشند.
# اگر مقدار .env دستکاری شود (مثلاً `x"></script><script>...`) بدون این اعتبارسنجی
# مستقیماً داخل تگ <script> در همهٔ صفحات تزریق می‌شد — یعنی XSS سراسری،
# که Google Safe Browsing آن را «Dangerous site» علامت می‌زند.
_ID_RE = _re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def _safe_id(value):
    v = (value or '').strip()
    return v if _ID_RE.match(v) else ''


def clarity_id():
    return _safe_id(env('CLARITY_ID'))


def crisp_id():
    return _safe_id(env('CRISP_WEBSITE_ID'))


def groq_key():
    return env('GROQ_API_KEY')


def bing_key():
    return env('BING_API_KEY')


def bing_key_location():
    """مسیر ریشه سایت برای فایل کلید IndexNow — حتماً باید در دسترس عموم باشد"""
    return env('BING_KEY_LOCATION', '')


# ---------------------------------------------------------------
# Microsoft Clarity — کد جاوااسکریپت (مستقیم در base.html استفاده می‌شود)
# ---------------------------------------------------------------
def clarity_script():
    """اسکریپت استاندارد Clarity — اگر CLARITY_ID خالی باشد خروجی خالی"""
    cid = clarity_id()
    if not cid:
        return ''
    return f'''<script type="text/javascript">
    (function(c,l,a,r,i,t,y){{c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments)}};
    t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
    y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);}})(window, document, "clarity", "script", "{cid}");
</script>'''


# ---------------------------------------------------------------
# Crisp Chat — ویجت پشتیبانی آنلاین
# ---------------------------------------------------------------
def crisp_script():
    """اسکریپت Crisp — اگر CRISP_WEBSITE_ID خالی باشد خروجی خالی"""
    wid = crisp_id()
    if not wid:
        return ''
    return f'''<script type="text/javascript">window.$crisp=[];window.CRISP_WEBSITE_ID="{wid}";
(function(){{d=document;s=d.createElement("script");s.src="https://client.crisp.chat/l.js";
s.async=1;d.getElementsByTagName("head")[0].appendChild(s);}})();
</script>'''


# ---------------------------------------------------------------
# Groq AI — Llama-3 (رایگان، بدون تحریم)
# ---------------------------------------------------------------
GROQ_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL = 'llama-3.3-70b-versatile'   # مدل قوی رایگان
GROQ_MODEL_FAST = 'llama-3.1-8b-instant'  # مدل سریع برای چت

_SYSTEM_PROMPT = (
    'شما یک دستیار متخصص سئو و تولید محتوای فارسی برای یک آکادمی آموزشی آنلاین هستید. '
    'همیشه به زبان فارسی روان و با لحن حرفه‌ای پاسخ دهید. '
    'برای تولید مقاله: عنوان جذاب + مقدمه + زیرعنوان‌های H2/H3 + پاراگراف‌های مفید + نتیجه‌گیری + CTA. '
    'متن را با فرمت Markdown ساده برگردانید. تاریخ امروز: ۱۴۰۵/۰۵/۱۶.'
)


def groq_chat(messages, temperature=0.7, max_tokens=1500, fast=False):
    """فراخوانی Groq API — لیست messages شامل dict های role/content"""
    key = groq_key()
    if not key:
        return None, 'کلید GROQ_API_KEY در فایل .env تنظیم نشده است'
    try:
        r = _rq.post(GROQ_URL,
                     headers={'Authorization': f'Bearer {key}',
                              'Content-Type': 'application/json'},
                     json=dict(model=GROQ_MODEL_FAST if fast else GROQ_MODEL,
                               messages=messages,
                               temperature=temperature,
                               max_tokens=max_tokens),
                     timeout=(10, 60))
        if r.status_code != 200:
            return None, f'Groq خطا داد (HTTP {r.status_code}): {r.text[:200]}'
        data = r.json()
        return data['choices'][0]['message']['content'], None
    except Exception as e:
        _lexc('integrations.groq')
        return None, f'خطا در اتصال به Groq: {str(e)[:120]}'


def ai_writer(prompt, mode='article'):
    """تولید مقاله سئوشده یا پاسخ به سوال — برای مدیران

    mode: article → مقاله کامل سئو · answer → پاسخ سوال · seo → عنوان و متا
    """
    system = _SYSTEM_PROMPT
    if mode == 'answer':
        user_msg = f'به این سوال کاربر پاسخ دهید:\n{prompt}'
        return groq_chat([{'role': 'system', 'content': system},
                          {'role': 'user', 'content': user_msg}],
                         fast=True, max_tokens=1000)
    if mode == 'seo':
        user_msg = (f'برای موضوع «{prompt}» موارد زیر را تولید کن:\n'
                    '1) عنوان سئو (کمتر از ۶۰ کاراکتر)\n'
                    '2) توضیحات متا (۱۳۰-۱۵۰ کاراکتر)\n'
                    '3) ۵ کلمه کلیدی LSI\n'
                    '4) اسلاگ پیشنهادی انگلیسی')
        return groq_chat([{'role': 'system', 'content': system},
                          {'role': 'user', 'content': user_msg}],
                         max_tokens=700)
    # article
    user_msg = (f'یک مقاله کامل و سئوشده به زبان فارسی درباره موضوع زیر بنویس:\n"{prompt}"\n'
                'ساختار: عنوان جذاب، مقدمه (هوک)، دست‌کم ۴ زیرعنوان H2 با محتوای کاربردی، '
                'نکات کلیدی، نتیجه‌گیری و یک فراخوان به اقدام مناسب برای یک آکادمی آموزشی.')
    return groq_chat([{'role': 'system', 'content': system},
                      {'role': 'user', 'content': user_msg}])


# ---------------------------------------------------------------
# Bing Webmaster — ایندکس سریع URL (IndexNow + URL Submission)
# ---------------------------------------------------------------
def submit_bing(url):
    """ارسال URL به Bing برای ایندکس سریع — در پس‌زمینه اجرا می‌شود

    از دو مسیر استفاده می‌کند:
    1) IndexNow (پیشنهادی Bing) — نیاز به فایل کلید در ریشه سایت
    2) Bing URL Submission API (ssl.bing.com/webmaster/api.svc/json/SubmitUrl)
    """
    key = bing_key()
    if not key or not url:
        return False, 'BING_API_KEY تنظیم نشده است'
    errors = []
    # ── مسیر ۱: IndexNow ──
    try:
        loc = bing_key_location()
        if loc:
            # باید فایل {key}.txt در ریشه سایت موجود باشد
            r = _rq.get('https://api.indexnow.org/indexnow',
                        params={'url': url, 'key': key, 'keyLocation': loc},
                        timeout=(5, 20))
            if r.status_code in (200, 202):
                return True, f'IndexNow: {r.status_code}'
            errors.append(f'IndexNow {r.status_code}')
        else:
            errors.append('IndexNow بدون keyLocation')
    except Exception as e:
        errors.append(f'IndexNow {str(e)[:60]}')
    # ── مسیر ۲: Bing URL Submission ──
    try:
        r = _rq.post('https://ssl.bing.com/webmaster/api.svc/json/SubmitUrl',
                     params={'apikey': key},
                     json={'url': url},
                     headers={'Content-Type': 'application/json'},
                     timeout=(5, 20))
        if r.status_code == 200:
            return True, f'Bing SubmitUrl: {r.status_code}'
        errors.append(f'SubmitUrl {r.status_code}')
    except Exception as e:
        errors.append(f'SubmitUrl {str(e)[:60]}')
    return False, '; '.join(errors)


def submit_bing_async(url):
    """ارسال بدون بلاک‌کردن درخواست — با thread (مثل Celery سبک)"""
    if not url or not bing_key():
        return
    threading.Thread(target=submit_bing, args=(url,), daemon=True).start()


# ---------------------------------------------------------------
# Blueprint — API هوش مصنوعی برای مدیران
# ---------------------------------------------------------------
from flask import Blueprint, request, jsonify, g

services_bp = Blueprint('services', __name__)


@services_bp.route('/api/ai-writer', methods=['POST'])
def api_ai_writer():
    """تولید مقاله سئوشده / پاسخ به سوال با Groq (Llama-3) — فقط مدیران

    ورودی (JSON): {prompt: str, mode: article|answer|seo}
    خروجی: {ok, text} یا {ok: False, msg}
    """
    # دسترسی: فقط ادمین/سوپرادمین
    u = getattr(g, 'user', None)
    if not u or u.role not in ('admin', 'super_admin'):
        return jsonify(ok=False, msg='دسترسی غیرمجاز — این سرویس مخصوص مدیران است'), 403
    data = request.get_json(force=True, silent=True) or {}
    prompt = (data.get('prompt') or '').strip()
    mode = (data.get('mode') or 'article').strip()
    if not prompt:
        return jsonify(ok=False, msg='متن درخواست (prompt) الزامی است'), 400
    if len(prompt) > 2000:
        return jsonify(ok=False, msg='متن درخواست بیش از حد طولانی است'), 413
    if mode not in ('article', 'answer', 'seo'):
        mode = 'article'
    text, err = ai_writer(prompt, mode)
    if err:
        return jsonify(ok=False, msg=err), 502
    return jsonify(ok=True, text=text, mode=mode)


@services_bp.route('/admin/ai-writer')
def admin_ai_writer_page():
    """صفحه ابزار تولید مقاله با هوش مصنوعی — فقط مدیران"""
    from flask import render_template
    u = getattr(g, 'user', None)
    if not u or u.role not in ('admin', 'super_admin'):
        return jsonify(ok=False, msg='دسترسی غیرمجاز'), 403
    return render_template('admin/ai_writer.html', key_set=bool(groq_key()))
