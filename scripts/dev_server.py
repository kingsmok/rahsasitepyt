# -*- coding: utf-8 -*-
"""اجرای محلی برای پیش‌نمایش دیزاین سیستم v2 (فقط توسعه).

دیتابیس نمایشی جدا در /tmp می‌سازد، طرح صفحه اصلی «مدرن ۲۰۲۶» را اعمال
می‌کند و سرور را روی 0.0.0.0:5000 بالا می‌آورد.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['APP_ENV'] = 'development'
os.environ['ENABLE_DEMO_FEATURES'] = '1'
_DB = '/tmp/ds_preview.db'
if os.path.exists(_DB):
    os.remove(_DB)
os.environ['DATABASE_URL'] = 'sqlite:///' + _DB

from app import app  # noqa: E402
from models import db, Page  # noqa: E402

with app.app_context():
    import seed as seed_mod
    db.create_all()
    try:
        seed_mod.seed()
        seed_mod._make_sample_files()
        seed_mod.seed_pages()
    except Exception as exc:  # noqa: BLE001
        print('seed skipped:', exc)
    # اعمال طرح صفحه اصلی «مدرن ۲۰۲۶» (شمارهٔ ۶)
    try:
        home = Page.query.filter_by(ptype='home').first()
        if home:
            from designs import HOME_DESIGNS
            import json
            d6 = HOME_DESIGNS['6']
            home.content = json.dumps({'settings': d6.get('settings', {}),
                                       'rows': d6['rows']}, ensure_ascii=False)
            home.is_published = True
            db.session.commit()
            from blueprints.builder import _clear_app_cache
            _clear_app_cache()
            print('home page rows updated')
        # تنظیم طرح فعال صفحه اصلی روی ۶
        from models import Setting
        st = Setting.query.filter_by(key='home_design').first()
        if not st:
            st = Setting(key='home_design')
            db.session.add(st)
        st.value = '6'
        db.session.commit()
        _clear_app_cache()
        print('home design 6 applied')
    except Exception as exc:  # noqa: BLE001
        print('home design apply skipped:', exc)

    # صفحهٔ نمایش بلوک‌های جدید (برای پیش‌نمایش زنده)
    try:
        demo_rows = json.load(open(os.path.join(os.path.dirname(__file__), 'dev_demo_rows.json'), encoding='utf-8'))
        demo = Page.query.filter_by(slug='blocks-demo').first()
        if not demo:
            demo = Page(title='نمایش بلوک‌های دیزاین سیستم', slug='blocks-demo', ptype='page')
            db.session.add(demo)
        demo.content = json.dumps({'settings': {}, 'rows': demo_rows}, ensure_ascii=False)
        demo.is_published = True
        db.session.commit()
        from blueprints.builder import _clear_app_cache as _cac
        _cac()
        print('blocks-demo page ready at /page/blocks-demo')
    except Exception as exc:  # noqa: BLE001
        print('blocks-demo skipped:', exc)

app.run(host='0.0.0.0', port=5000, debug=False)
