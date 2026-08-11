# -*- coding: utf-8 -*-
"""رگرسیون نصب روی هاست‌هایی که background thread را متوقف می‌کنند."""
import json

from sqlalchemy import create_engine, inspect, text

import installer


def test_request_install_resumes_without_background_thread(tmp_path, monkeypatch):
    """هر درخواست چند جدول بسازد و درخواست آخر seed/marker را کامل کند."""
    db_path = tmp_path / 'resume.db'
    state_path = tmp_path / '.install_progress.json'
    marked = []

    monkeypatch.setattr(installer, '_INSTALL_STATE_FILE', str(state_path))
    monkeypatch.setattr(installer, 'INSTANCE_DIR', str(tmp_path))
    monkeypatch.setattr(installer, '_install_state', {
        'status': 'idle', 'step': 0, 'steps': 5, 'msg': '', 'ok': False,
    })
    monkeypatch.setattr(installer, 'write_env_file',
                        lambda *_args, **_kwargs: str(tmp_path / '.env'))
    monkeypatch.setattr(installer, 'mark_installed', lambda meta: marked.append(meta))

    admin = {
        'name': 'مدیر تست',
        'email': 'resume@example.com',
        'password': 'TestPass123!',
    }
    site = {
        'name': 'سایت تست', 'desc': '', 'phone': '', 'email': '',
        'base_url': '',
    }
    db_url = 'sqlite:///' + str(db_path)

    statuses = []
    for _ in range(30):
        result, _msg, state = installer.run_install_request(
            db_url, admin, site, tables_per_request=7)
        statuses.append(state['status'])
        if result is not None:
            break

    assert statuses[0] == 'waiting'
    assert result is True
    assert statuses[-1] == 'done'
    assert marked

    # state روی دیسک نباید اطلاعات اتصال یا رمز مدیر را نگه دارد.
    disk_state = json.loads(state_path.read_text(encoding='utf-8'))
    assert disk_state['status'] == 'done'
    assert admin['password'] not in state_path.read_text(encoding='utf-8')

    engine = create_engine(db_url)
    assert len(inspect(engine).get_table_names()) >= 60
    with engine.connect() as conn:
        assert conn.execute(text(
            "SELECT COUNT(*) FROM users WHERE email='resume@example.com'"
        )).scalar() == 1
        assert conn.execute(text(
            "SELECT COUNT(*) FROM settings WHERE key='site_name'"
        )).scalar() == 1
    engine.dispose()


def test_mysql_table_options_utf8mb4():
    """بررسی اینکه تمام جدول‌ها مشخصات utf8mb4 و InnoDB مای‌اسکیول را دارند."""
    from models import db
    assert len(db.metadata.tables) > 0
    for name, tbl in db.metadata.tables.items():
        assert tbl.kwargs.get('mysql_charset') == 'utf8mb4', f"جدول {name} فاقد mysql_charset=utf8mb4 است"
        assert tbl.kwargs.get('mysql_collate') == 'utf8mb4_unicode_ci', f"جدول {name} فاقد mysql_collate=utf8mb4_unicode_ci است"
        assert tbl.kwargs.get('mysql_engine') == 'InnoDB', f"جدول {name} فاقد mysql_engine=InnoDB است"

