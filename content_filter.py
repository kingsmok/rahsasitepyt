# -*- coding: utf-8 -*-
"""پالایش متن انجمن/نظرات: لینک و فحش."""
import re

_URL_RE = re.compile(
    r'(?i)((?:https?://|www\.)\S+|t\.me/\S+|telegram\.me/\S+|'
    r'[a-z0-9.-]+\.(?:com|ir|net|org|info|me|io|co|xyz|site|online)\S*)'
)
_PROFANITY = (
    'کص', 'کون', 'کیر', 'جنده', 'کسکش', 'کونی', 'لاشی', 'حرومزاده',
    'fuck', 'shit', 'bitch', 'asshole',
)


def strip_links(text):
    return _URL_RE.sub('[لینک حذف شد]', text or '')


def contains_profanity(text):
    low = (text or '').lower()
    return any(w in low for w in _PROFANITY)


def moderate_text(text, max_len=5000):
    """خروجی: (ok, cleaned, reason). ok=False یعنی رد کامل."""
    cleaned = strip_links((text or '').strip())[:max_len]
    if contains_profanity(cleaned):
        return False, cleaned, 'متن حاوی الفاظ نامناسب است.'
    return True, cleaned, ''
