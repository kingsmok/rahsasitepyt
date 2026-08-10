# -*- coding: utf-8 -*-
"""پالت‌های دست‌چین‌شده ۲۰ طرح ایرانی — جایگزین رنگ‌های الگوریتمی قبلی

ساختار هر طرح:
  colors: ۵ رنگ پایه (primary, secondary, accent, background, text)
  tokens: توکن‌های کلیدی دستی (primary2, accent2, bg2, footer, hero و...)
          بقیه توکن‌ها از این مقادیر با الگوریتم بهینه‌شده مشتق می‌شوند.
"""
PALETTES = {
    # ── ۱) فیروزه‌ای اصفهان — فیروزه تیره + کرم عاجی + طلایی سنتی ──
    'pd-01': dict(
        colors=dict(primary='#0F766E', secondary='#EFE7D3', accent='#C9971C', background='#FAF8F2', text='#1C2B33'),
        tokens=dict(primary2='#115E59', accent2='#A87E14', bg2='#F1EEE4',
                    footer_bg='#0B3B3A', footer_text='#BFD8D4', footer_text2='#8FB4AE',
                    hero_from='#0F766E', hero_to='#0B3B3A')),
    # ── ۲) زعفرانی قائنات — زعفران + سرمه‌ای عمیق + سفید ──
    'pd-02': dict(
        colors=dict(primary='#C8912A', secondary='#1F3A5F', accent='#E8B54A', background='#FDFAF3', text='#2B2313'),
        tokens=dict(primary2='#A97A1B', accent2='#D09A2E', bg2='#F6EFDD',
                    footer_bg='#141C2E', footer_text='#C3CBDD', footer_text2='#8B96AE',
                    hero_from='#C8912A', hero_to='#8F6414')),
    # ── ۳) لاجوردی شیراز — لاجورد + مس روشن + خاکستری مات ──
    'pd-03': dict(
        colors=dict(primary='#2E4E8F', secondary='#C97B4A', accent='#8FA3BF', background='#F6F7FA', text='#232C3B'),
        tokens=dict(primary2='#223B6E', accent2='#A8613A', bg2='#EAEDF4',
                    footer_bg='#1B2A4A', footer_text='#C6CDE0', footer_text2='#8B97B5',
                    hero_from='#2E4E8F', hero_to='#1B2A4A')),
    # ── ۴) اناری یزد — قرمز اناری + شنی + زیتونی ──
    'pd-04': dict(
        colors=dict(primary='#B3272E', secondary='#E3CFA4', accent='#5A6B3A', background='#FAF6EF', text='#331F1C'),
        tokens=dict(primary2='#8F1D24', accent2='#46542C', bg2='#F2EADB',
                    footer_bg='#3F1618', footer_text='#D9B9B8', footer_text2='#AE8486',
                    hero_from='#B3272E', hero_to='#7A1420')),
    # ── ۵) سفال کویر — آجری + خاکستری گرم + سفید ──
    'pd-05': dict(
        colors=dict(primary='#B85C38', secondary='#8A8A80', accent='#D9A05B', background='#F8F4EF', text='#352A24'),
        tokens=dict(primary2='#94462A', accent2='#BD843F', bg2='#EFE7DE',
                    footer_bg='#4A3A30', footer_text='#D8C8BC', footer_text2='#B09A8A',
                    hero_from='#B85C38', hero_to='#8F452B')),
    # ── ۶) ترمه یزدی — بنفش ترمه + طلایی مات + صورتی ملایم ──
    'pd-06': dict(
        colors=dict(primary='#5B3E8F', secondary='#E8B4C8', accent='#C9A227', background='#FAF7F4', text='#2C2340'),
        tokens=dict(primary2='#452E70', accent2='#A3851C', bg2='#F1ECE7',
                    footer_bg='#2E1F4D', footer_text='#CBC0E0', footer_text2='#9D8FBE',
                    hero_from='#5B3E8F', hero_to='#3A2668')),
    # ── ۷) میناکاری — آبی کاربنی + فیروزه روشن + سفید ──
    'pd-07': dict(
        colors=dict(primary='#16324F', secondary='#2EC4B6', accent='#48A9A6', background='#F5F9FB', text='#15212E'),
        tokens=dict(primary2='#10263E', accent2='#1FA396', bg2='#E9F1F6',
                    footer_bg='#0B1C2E', footer_text='#BCD0E0', footer_text2='#7E9BB3',
                    hero_from='#16324F', hero_to='#0B1C2E')),
    # ── ۸) گلاب قمصر — صورتی رز + طوسی روشن + سبز نود ──
    'pd-08': dict(
        colors=dict(primary='#C26C87', secondary='#E8E8EC', accent='#9DB89A', background='#FCF9FA', text='#3A3340'),
        tokens=dict(primary2='#A85570', accent2='#7F9E7B', bg2='#F6EDF0',
                    footer_bg='#7A4A5C', footer_text='#E3C6D2', footer_text2='#C29DAB',
                    hero_from='#C26C87', hero_to='#8F4560')),
    # ── ۹) پسته رفسنجان — سبز پسته + کرم + شکلاتی ──
    'pd-09': dict(
        colors=dict(primary='#6FA34F', secondary='#F4EDDD', accent='#8A6A44', background='#FAF9F3', text='#2A3326'),
        tokens=dict(primary2='#57823D', accent2='#6F5436', bg2='#F0F2E8',
                    footer_bg='#3E5130', footer_text='#CBD6BE', footer_text2='#9DAE8F',
                    hero_from='#6FA34F', hero_to='#4F7A38')),
    # ── ۱۰) مرمر کهن — مشکی زغالی + طلایی + سفید مرمری (تیره) ──
    'pd-10': dict(
        colors=dict(primary='#C9A227', secondary='#8E8E93', accent='#F2EFE6', background='#121316', text='#F2EFE6'),
        tokens=dict(primary2='#A5851B', accent2='#D8D5CC', bg2='#191A1F', card='#1D1E24',
                    border='#2E3038', border2='#3F424C', text2='#B9B6AC', text3='#8B8983',
                    footer_bg='#0B0C10', footer_text='#C9C6BC', footer_text2='#8F8C84',
                    hero_from='#1D1E24', hero_to='#0B0C10')),
    # ── ۱۱) کاشی سنتی — آبی متمایل به سبز + کرم نان + زرد لیمویی ──
    'pd-11': dict(
        colors=dict(primary='#1D6E7A', secondary='#F0E3C0', accent='#F2C94C', background='#FAF7EE', text='#26323A'),
        tokens=dict(primary2='#15555E', accent2='#D4A72E', bg2='#F1EDE0',
                    footer_bg='#123F46', footer_text='#BFD5D8', footer_text2='#8AA8AC',
                    hero_from='#1D6E7A', hero_to='#144F57')),
    # ── ۱۲) شیشه رنگی ارسی — قرمز + فیروزه + زرد (زمینه سفید) ──
    'pd-12': dict(
        colors=dict(primary='#E63946', secondary='#2A9D8F', accent='#F4D35E', background='#FFFFFF', text='#2B2D42'),
        tokens=dict(primary2='#C02734', accent2='#D8B62E', bg2='#F7F7FA',
                    footer_bg='#26264A', footer_text='#D6D6EA', footer_text2='#A3A3C8',
                    hero_from='#E63946', hero_to='#B02330')),
    # ── ۱۳) چوب و حصیر — قهوه خاکی + کرم چرمی + سبز زیتونی ──
    'pd-13': dict(
        colors=dict(primary='#7B5B3A', secondary='#D9C2A7', accent='#6B705C', background='#F7F3EC', text='#35291C'),
        tokens=dict(primary2='#61472E', accent2='#555A47', bg2='#EFE7DC',
                    footer_bg='#3E2F1F', footer_text='#D8C7B2', footer_text2='#B09B7F',
                    hero_from='#7B5B3A', hero_to='#5A4128')),
    # ── ۱۴) مینیاتور ایرانی — نارنجی مینیاتوری + آبی نفتی + طوسی فیلی ──
    'pd-14': dict(
        colors=dict(primary='#E07B39', secondary='#1F3A5F', accent='#9AA0A8', background='#FBF6EE', text='#3A2E24'),
        tokens=dict(primary2='#C05F24', accent2='#7E848C', bg2='#F3EADB',
                    footer_bg='#14263F', footer_text='#C3CEE0', footer_text2='#8B9AB5',
                    hero_from='#E07B39', hero_to='#B85920')),
    # ── ۱۵) شب کویر — سرمه تیره + زرد ستاره‌ای + بنفش (تیره) ──
    'pd-15': dict(
        colors=dict(primary='#FFD166', secondary='#7C5CBF', accent='#B8C4D6', background='#0A1420', text='#E8ECF1'),
        tokens=dict(primary2='#E5B24B', accent2='#8F9DB8', bg2='#101C2C', card='#0F1B2A',
                    border='#223349', border2='#33496A', text2='#B6C2D1', text3='#8394A8',
                    footer_bg='#060B12', footer_text='#C7D0DA', footer_text2='#8A97A8',
                    hero_from='#101C2C', hero_to='#060B12')),
    # ── ۱۶) سهند و سبلان — آبی یخی + طوسی فضایی + سفید ──
    'pd-16': dict(
        colors=dict(primary='#5C8FA8', secondary='#E8EDF2', accent='#8FA3B8', background='#FBFCFD', text='#2A3440'),
        tokens=dict(primary2='#46758C', accent2='#63788C', bg2='#EFF3F6',
                    footer_bg='#2C3E4E', footer_text='#C3CDD6', footer_text2='#8FA0AF',
                    hero_from='#5C8FA8', hero_to='#3E6B81')),
    # ── ۱۷) خلیج فارس — آبی نیلگون + طلایی ساحلی + سفید ──
    'pd-17': dict(
        colors=dict(primary='#0077B6', secondary='#E9C46A', accent='#48CAE4', background='#F5FAFD', text='#1C3140'),
        tokens=dict(primary2='#005E93', accent2='#1FA8C4', bg2='#E9F2F9',
                    footer_bg='#0B3A5C', footer_text='#C3D9E8', footer_text2='#8AAFC8',
                    hero_from='#0077B6', hero_to='#00507E')),
    # ── ۱۸) عقیق خراسانی — عنابی + طوسی موشی + کرم خاکی ──
    'pd-18': dict(
        colors=dict(primary='#6D2E46', secondary='#D6C7A1', accent='#8D99AE', background='#F8F5F0', text='#332A2E'),
        tokens=dict(primary2='#552336', accent2='#6E7A90', bg2='#F0EAE0',
                    footer_bg='#421B2A', footer_text='#DBBEC8', footer_text2='#B58E9C',
                    hero_from='#6D2E46', hero_to='#4E1F33')),
    # ── ۱۹) باغ ایرانی — سبز زمردی + زرد آفتابی + استخوانی ──
    'pd-19': dict(
        colors=dict(primary='#1B7A4A', secondary='#F4D03F', accent='#F2EFE7', background='#FAFCF7', text='#26382C'),
        tokens=dict(primary2='#145E39', accent2='#D8D3C9', bg2='#EFF5EC',
                    footer_bg='#0F4A2C', footer_text='#C3DCCB', footer_text2='#8FB5A2',
                    hero_from='#1B7A4A', hero_to='#115733')),
    # ── ۲۰) مدرن تهران — گلسمورفیسم + خط نستعلیق + رنگ‌های خنثی ──
    'pd-20': dict(
        colors=dict(primary='#4F5D75', secondary='#B08D57', accent='#7A8B99', background='#F3F4F7', text='#22262E'),
        tokens=dict(primary2='#3E4A5E', accent2='#5F6E7A', bg2='#EAECF2',
                    footer_bg='#2A2F3A', footer_text='#C7CBD6', footer_text2='#9299A8',
                    hero_from='#4F5D75', hero_to='#333B4C')),
}
