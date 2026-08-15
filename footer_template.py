# -*- coding: utf-8 -*-
"""قالب فوتر — کلاسیک آکادمیک (سرمه‌ای + نارنجی)"""

FOOTER_ROWS = [
    {
        "id": "f_main",
        "settings": {"gap": 36, "py": 58, "bg": "", "widths": "1.5fr 1fr 1fr 1.3fr"},
        "cols": [
            # ستون ۱: درباره آکادمی
            [
                {"id": "f_about", "type": "footer_about", "data": {
                    "desc": "",
                    "socials": True}}
            ],
            # ستون ۲: خدمات دانشجویان
            [
                {"id": "f_links1", "type": "link_list", "data": {
                    "title": "خدمات دانشجویان",
                    "links": [
                        {"text": "ثبت‌نام در دوره‌ها", "url": "/auth/register"},
                        {"text": "دوره‌های من", "url": "/dashboard/my-courses"},
                        {"text": "پیگیری سفارش", "url": "/dashboard/orders"},
                        {"text": "پشتیبانی تیکت", "url": "/dashboard/tickets/new"},
                        {"text": "سوالات متداول", "url": "/faq"},
                        {"text": "شرایط بازگشت وجه", "url": "/faq"},
                    ]}}
            ],
            # ستون ۳: محبوب‌ترین دسته‌ها
            [
                {"id": "f_links2", "type": "link_list", "data": {
                    "title": "محبوب‌ترین دسته‌ها",
                    "links": [
                        {"text": "برنامه‌نویسی", "url": "/courses?cat=برنامه-نویسی"},
                        {"text": "وب و فرانت‌اند", "url": "/courses?cat=وب"},
                        {"text": "هوش مصنوعی", "url": "/courses?cat=هوش-مصنوعی"},
                        {"text": "طراحی UI/UX", "url": "/courses?cat=طراحی"},
                        {"text": "دیجیتال مارکتینگ", "url": "/courses?cat=کسب-وکار"},
                        {"text": "امنیت اطلاعات", "url": "/courses?cat=امنیت"},
                    ]}}
            ],
            # ستون ۴: تماس + خبرنامه
            [
                # ⚠️ اطلاعات تماس خالی — مدیر مقدار واقعی را در پنل ثبت می‌کند.
                # شماره/ایمیل نمونه روی سایت واقعی = اطلاعات تماس جعلی، که یکی از
                # سیگنال‌های «محتوای فریب‌دهنده» برای Google Safe Browsing است.
                {"id": "f_contact", "type": "contact_info", "data": {
                    "phone": "", "email": "",
                    "address": "",
                    "hours": ""}},
                {"id": "f_news", "type": "newsletter", "data": {
                    "title": "عضویت در خبرنامه",
                    "text": "از تخفیف‌ها و دوره‌های جدید با خبر شوید!"}},
            ],
        ],
    },
    {
        "id": "f_trust",
        "settings": {"gap": 30, "py": 28, "bg": "", "widths": "1fr 1fr"},
        "cols": [
            [
                {"id": "f_badges", "type": "trust_badges", "data": {
                    "size": "74",
                    "items": [
                        {"type": "enamad", "code": ""},
                        {"type": "samandehi", "code": ""},
                        {"type": "etehadiye", "code": ""},
                    ]}}
            ],
            [
                {"id": "f_pay", "type": "html", "data": {
                    "code": (
                        '<div class="f-pay-section">'
                        '<span class="f-pay-title">💳 روش‌های پرداخت فعال و واقعی در مرحله تسویه‌حساب نمایش داده می‌شوند.</span>'
                        '</div>'
                    )}}
            ],
        ],
    },
    {
        "id": "f_bottom",
        "settings": {"gap": 20, "py": 22, "bg": "", "widths": "1fr auto 1fr"},
        "cols": [
            [
                {"id": "f_copy", "type": "text", "data": {
                    "content": "تمامی حقوق این وب‌سایت محفوظ است.",
                    "align": "right", "color": "", "size": "13"}}
            ],
            [
                {"id": "f_iran", "type": "html", "data": {
                    "code": '<div class="f-iran-badge">🇮🇷 ساخته‌شده با <span class="f-heart">❤️</span> در ایران</div>'}}
            ],
            [
                {"id": "f_legal", "type": "link_list", "data": {
                    "title": "",
                    "links": [
                        {"text": "قوانین و مقررات", "url": "/terms"},
                        {"text": "حریم خصوصی", "url": "/privacy"},
                    ]}}
            ],
        ],
    },
    {
        "id": "f_flag",
        "settings": {"gap": 0, "py": 0, "bg": ""},
        "cols": [
            [
                {"id": "f_flag1", "type": "html", "data": {
                    "code": '<div class="iran-flag-stripe"></div>'}}
            ],
        ],
    },
]
