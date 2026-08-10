# -*- coding: utf-8 -*-
"""موتور تحلیل سئو — شبیه Rank Math Pro
امتیازدهی واقعی بر اساس: عنوان، توضیحات، کلمه کلیدی، ساختار هدینگ،
تصاویر، لینک‌های داخلی، خوانایی فارسی و Schema
"""
import re
import json
from validators import log_exc as _lexc

PERSIAN_CHARS = r'[\u0600-\u06FF]'


# ============================================================
# ابزارهای متنی فارسی
# ============================================================
def fa_words(text):
    """شمارش کلمات فارسی/لاتین در متن"""
    text = (text or '').strip()
    if not text:
        return 0
    # کلمات جدا با فاصله، نیم‌فاصله، خط تیره
    words = re.findall(r'[\w\u0600-\u06FF]+', text)
    return len(words)


def fa_sentences(text):
    text = (text or '').strip()
    if not text:
        return 0
    # جمله = با . ! ؟ و …
    parts = re.split(r'[.!؟…]+\s*', text)
    return len([p for p in parts if p.strip()])


def fa_syllables(text):
    """تقریب هجاها برای خوانایی: مصوت‌ها"""
    text = (text or '')
    vowels = re.findall(r'[ااوهی]', text)
    return len(vowels)


# ============================================================
# تحلیل هر بخش
# ============================================================
def analyze_title(title):
    """عنوان سئو — ایده‌آل ۳۰ تا ۶۰ کاراکتر"""
    t = (title or '').strip()
    n = len(t)
    if not t:
        return 0, 'عنوان سئو وارد نشده است — گوگل عنوان خودش را می‌سازد.'
    if n < 15:
        return 30, f'عنوان خیلی کوتاه است ({n} کاراکتر). ایده‌آل: ۳۰ تا ۶۰ کاراکتر.'
    if 30 <= n <= 60:
        return 100, f'عالی! طول عنوان {n} کاراکتر است (محدوده ایده‌آل ۳۰-۶۰).'
    if 15 <= n < 30:
        return 60, f'عنوان کمی کوتاه است ({n} کاراکتر). ایده‌آل: ۳۰ تا ۶۰ کاراکتر.'
    if 60 < n <= 70:
        return 70, f'عنوان کمی بلند است ({n} کاراکتر) — در نتایج گوگل بریده می‌شود.'
    return 40, f'عنوان خیلی بلند است ({n} کاراکتر) — حتماً در گوگل بریده می‌شود.'


def analyze_description(desc):
    """توضیحات متا — ایده‌آل ۱۲۰ تا ۱۶۰ کاراکتر"""
    d = (desc or '').strip()
    n = len(d)
    if not d:
        return 0, 'توضیحات متا وارد نشده است — گوگل متن صفحه را برمی‌دارد.'
    if n < 70:
        return 40, f'توضیحات کوتاه است ({n} کاراکتر). ایده‌آل: ۱۲۰ تا ۱۶۰ کاراکتر.'
    if 120 <= n <= 160:
        return 100, f'عالی! طول توضیحات {n} کاراکتر است.'
    if 70 <= n < 120:
        return 70, f'توضیحات خوب است ولی بهتر است به ۱۲۰-۱۶۰ برسد (فعلا {n}).'
    return 60, f'توضیحات بلند است ({n} کاراکتر) — در گوگل بریده می‌شود.'


def analyze_focus_keyword(kw, title, desc, text):
    """کلمه کلیدی اصلی — حضور در عنوان، توضیحات، متن و چگالی"""
    kw = (kw or '').strip()
    if not kw:
        return 0, 'کلمه کلیدی اصلی (Focus Keyword) مشخص نشده است.'
    score = 0
    notes = []
    # حضور در عنوان
    if kw in (title or ''):
        score += 30
        notes.append('✅ در عنوان سئو')
    else:
        notes.append('❌ در عنوان سئو نیست')
    # حضور در توضیحات
    if kw in (desc or ''):
        score += 20
        notes.append('✅ در توضیحات متا')
    else:
        notes.append('❌ در توضیحات متا نیست')
    # حضور در ابتدای متن
    head = (text or '')[:400]
    if kw in head:
        score += 20
        notes.append('✅ در ابتدای متن')
    else:
        notes.append('❌ در ابتدای متن نیست')
    # چگالی (۱٪ تا ۳٪)
    words = fa_words(text)
    kw_count = (text or '').count(kw)
    if words > 0 and kw_count > 0:
        density = kw_count * 100 / words
        if 1 <= density <= 3.5:
            score += 30
            notes.append(f'✅ چگالی کلمه کلیدی {density:.1f}٪ (ایده‌آل)')
        elif density > 3.5:
            score += 15
            notes.append(f'⚠️ چگالی زیاد است ({density:.1f}٪) — ریسک کلمه‌چینی')
        else:
            score += 15
            notes.append(f'⚠️ چگالی کم است ({density:.1f}٪)')
    else:
        notes.append('❌ کلمه کلیدی در متن نیست')
    return min(score, 100), ' | '.join(notes)


def analyze_headings(html):
    """ساختار هدینگ — دقیقاً یک H1 و وجود H2"""
    if not html:
        return 30, 'محتوایی برای تحلیل ساختار هدینگ نیست.'
    h1s = re.findall(r'<h1[^>]*>', html, re.I)
    h2s = re.findall(r'<h2[^>]*>', html, re.I)
    score = 0
    notes = []
    if len(h1s) == 1:
        score += 50
        notes.append('✅ دقیقاً یک H1')
    elif len(h1s) == 0:
        notes.append('❌ هیچ H1 وجود ندارد')
    else:
        score += 20
        notes.append(f'⚠️ {len(h1s)} عدد H1 — باید فقط یک باشد')
    if h2s:
        score += 30
        notes.append(f'✅ {len(h2s)} عدد H2')
    else:
        notes.append('⚠️ H2 وجود ندارد — ساختار سلسله‌مراتبی ایجاد کنید')
    if h1s and h2s:
        score += 20
        notes.append('✅ ساختار سلسله‌مراتبی صحیح')
    return min(score, 100), ' | '.join(notes)


def analyze_images(html):
    """تصاویر — وجود alt توصیفی"""
    if not html:
        return 0, 'محتوایی برای تحلیل تصاویر نیست.'
    imgs = re.findall(r'<img[^>]*>', html, re.I)
    if not imgs:
        return 40, 'تصویری در صفحه نیست — تصاویر به سئو کمک می‌کنند.'
    total = len(imgs)
    with_alt = [i for i in imgs if re.search(r'alt="[^"]+"', i, re.I)]
    pct = len(with_alt) * 100 // total
    if pct == 100:
        return 100, f'✅ همه {total} تصویر alt توصیفی دارند.'
    return max(20, pct), f'⚠️ {len(with_alt)} از {total} تصویر alt دارند — بقیه را تکمیل کنید.'


def analyze_links(html):
    """لینک‌های داخلی و خارجی"""
    if not html:
        return 30, 'محتوایی برای تحلیل لینک نیست.'
    internal = re.findall(r'href="(/[^"#][^"]*)"', html)
    external = re.findall(r'href="(https?://[^"]+)"', html)
    score = 0
    notes = []
    if len(internal) >= 3:
        score += 60
        notes.append(f'✅ {len(internal)} لینک داخلی')
    elif internal:
        score += 30
        notes.append(f'⚠️ فقط {len(internal)} لینک داخلی — حداقل ۳ بهتر است')
    else:
        notes.append('❌ لینک داخلی وجود ندارد')
    if external:
        score += 20
        notes.append(f'✅ {len(external)} لینک خارجی')
    else:
        notes.append('⚠️ لینک خارجی معتبری نیست (اعتبار E-E-A-T)')
    if len(internal) >= 5:
        score += 20
        notes.append('✅ لینک‌سازی داخلی عالی')
    return min(score, 100), ' | '.join(notes)


def analyze_readability(text):
    """خوانایی فارسی — بر اساس طول جمله و کلمات"""
    text = (text or '').strip()
    if not text:
        return 0, 'متن کافی برای تحلیل خوانایی نیست.'
    words = fa_words(text)
    sentences = max(fa_sentences(text), 1)
    if words < 30:
        return 30, 'متن خیلی کوتاه است — برای تحلیل دقیق حداقل ۳۰ کلمه نیاز است.'
    avg_word = sum(len(w) for w in re.findall(r'[\w\u0600-\u06FF]+', text)) / max(words, 1)
    avg_sent = words / sentences
    score = 100
    notes = []
    if avg_sent > 25:
        score -= 30
        notes.append(f'⚠️ جملات طولانی ({avg_sent:.0f} کلمه در جمله) — جملات کوتاه‌تر بنویسید')
    elif avg_sent > 15:
        score -= 10
        notes.append(f'⚠️ میانگین جمله {avg_sent:.0f} کلمه — خوب است')
    else:
        notes.append(f'✅ جملات کوتاه و خوانا ({avg_sent:.0f} کلمه در جمله)')
    if avg_word > 6:
        score -= 15
        notes.append(f'⚠️ کلمات متوسط بلند ({avg_word:.1f} کاراکتر)')
    else:
        notes.append(f'✅ طول کلمات مناسب ({avg_word:.1f} کاراکتر)')
    paragraphs = len([p for p in text.split('\n') if p.strip()])
    if paragraphs < 2 and words > 80:
        score -= 10
        notes.append('⚠️ پاراگراف‌بندی ضعیف — متن را به پاراگراف تقسیم کنید')
    else:
        notes.append('✅ پاراگراف‌بندی مناسب')
    return max(score, 0), ' | '.join(notes)


def analyze_schema(html):
    """داده‌های ساختاریافته (JSON-LD)"""
    if not html:
        return 0, 'محتوایی برای تحلیل Schema نیست.'
    ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    if not ld:
        return 20, '❌ داده ساختاریافته (Schema) وجود ندارد.'
    valid = 0
    types = []
    for block in ld:
        try:
            data = json.loads(block)
            valid += 1
            if isinstance(data, dict) and data.get('@type'):
                types.append(data['@type'])
        except Exception:
            _lexc('seo_analyzer.py')
    if valid == 0:
        return 20, '❌ JSON-LD نامعتبر است.'
    score = 40 + valid * 15
    notes = [f'✅ {valid} بلوک JSON-LD معتبر: {", ".join(types[:4])}']
    return min(score, 100), ' | '.join(notes)


def analyze_technical(seo, has_canonical=True):
    """مسائل فنی: canonical، robots، طول URL"""
    score = 100
    notes = []
    if seo.get('noindex'):
        score -= 60
        notes.append('⚠️ صفحه noindex است (عمدی باشد؟)')
    else:
        notes.append('✅ ایندکس‌پذیر')
    if seo.get('nofollow'):
        score -= 30
        notes.append('⚠️ nofollow فعال است')
    return score, ' | '.join(notes)


# ============================================================
# تحلیل کامل یک صفحه
# ============================================================
def analyze_page(path, title, desc, keywords, focus_kw, text, html, noindex=False, nofollow=False):
    """امتیاز کلی سئو (۰-۱۰۰) + تحلیل هر بخش"""
    results = {}
    # ۱) عنوان
    t_score, t_note = analyze_title(title)
    results['title'] = (t_score, t_note)
    # ۲) توضیحات
    d_score, d_note = analyze_description(desc)
    results['description'] = (d_score, d_note)
    # ۳) کلمه کلیدی
    k_score, k_note = analyze_focus_keyword(focus_kw, title, desc, text)
    results['keyword'] = (k_score, k_note)
    # ۴) هدینگ‌ها
    h_score, h_note = analyze_headings(html)
    results['headings'] = (h_score, h_note)
    # ۵) تصاویر
    i_score, i_note = analyze_images(html)
    results['images'] = (i_score, i_note)
    # ۶) لینک‌ها
    l_score, l_note = analyze_links(html)
    results['links'] = (l_score, l_note)
    # ۷) خوانایی
    r_score, r_note = analyze_readability(text)
    results['readability'] = (r_score, r_note)
    # ۸) Schema
    s_score, s_note = analyze_schema(html)
    results['schema'] = (s_score, s_note)
    # ۹) فنی
    f_score, f_note = analyze_technical({'noindex': noindex, 'nofollow': nofollow})
    results['technical'] = (f_score, f_note)

    # میانگین وزنی
    weights = {'title': 15, 'description': 12, 'keyword': 18, 'headings': 10,
               'images': 8, 'links': 10, 'readability': 12, 'schema': 8, 'technical': 7}
    total_w = sum(weights.values())
    total = sum(results[k][0] * weights[k] for k in weights)
    overall = round(total / total_w)
    if overall >= 80:
        grade = 'great'
        grade_fa = 'عالی'
    elif overall >= 55:
        grade = 'good'
        grade_fa = 'خوب'
    else:
        grade = 'bad'
        grade_fa = 'نیاز به بهبود'
    return {
        'overall': overall,
        'grade': grade,
        'grade_fa': grade_fa,
        'sections': results,
        'weights': weights,
    }


# ============================================================
# استخراج متن/HTML واقعی از منابع
# ============================================================
def content_from_course(course):
    text = ' '.join([course.title or '', course.subtitle or '', course.description or '',
                     course.what_you_learn or '', course.tags or ''])
    html = f'<h1>{course.title}</h1><p>{course.subtitle or ""}</p><img src="/static/img/{course.image}" alt="دوره {course.title}">'
    return text, html


def content_from_post(post):
    text = ' '.join([post.title or '', post.excerpt or '', post.body or ''])
    html = f'<h1>{post.title}</h1><p>{post.excerpt or ""}</p><img src="/static/img/{post.image}" alt="{post.title}">'
    return text, html


def content_from_page(page):
    """استخراج متن از ردیف‌های صفحه‌ساز"""
    texts = []
    html_parts = ['<h1>%s</h1>' % (page.title or '')]
    try:
        for r in page.rows():
            for col in r.get('cols', []):
                for w in col:
                    d = w.get('data', {}) or {}
                    for key in ('text', 'content', 'title', 'subtitle', 'sub', 'desc'):
                        v = d.get(key)
                        if isinstance(v, str) and v.strip():
                            texts.append(v)
                    # آیتم‌های ریپیتر
                    for ikey in ('items', 'slides', 'fields'):
                        for it in (d.get(ikey) or []):
                            for key in ('title', 'text', 'content', 'sub', 'q', 'a', 'label'):
                                v = it.get(key)
                                if isinstance(v, str) and v.strip():
                                    texts.append(v)
    except Exception:
        _lexc('seo_analyzer.py')
    return ' '.join(texts), ''.join(html_parts)
