# -*- coding: utf-8 -*-
"""رگرسیون نصب وابستگی‌ها روی Python/cPanel جدید و قدیمی."""
from pathlib import Path

import updater


ROOT = Path(__file__).resolve().parents[1]


def test_binary_dependencies_are_pinned_to_manylinux2014_releases():
    requirements = (ROOT / 'requirements.txt').read_text(encoding='utf-8')

    assert '--only-binary=greenlet,Pillow' in requirements
    assert 'greenlet==3.2.5' in requirements
    assert 'Pillow==11.3.0; python_version < "3.10"' in requirements
    assert 'Pillow==12.2.0; python_version >= "3.10"' in requirements
    assert 'greenlet==3.0.3' not in requirements


def test_updater_gives_pip_network_retries(monkeypatch):
    captured = {}

    def fake_run(cmd, cwd=updater.BASE_DIR, timeout=120, env=None):
        captured.update(cmd=cmd, timeout=timeout, env=env)
        return 0, 'ok'

    monkeypatch.setattr(updater, '_requirements_changed', lambda *args, **kwargs: True)
    monkeypatch.setattr(updater, '_run', fake_run)
    monkeypatch.delenv('PIP_DEFAULT_TIMEOUT', raising=False)
    monkeypatch.delenv('PIP_RETRIES', raising=False)
    monkeypatch.delenv('UPDATE_INSTALL_DEPENDENCIES', raising=False)

    result = updater._install_changed_dependencies('old')

    assert result == 'وابستگی‌های جدید نصب شدند.'
    assert captured['cmd'][-2:] == ['-r', 'requirements.txt']
    assert captured['env']['PIP_DEFAULT_TIMEOUT'] == '120'
    assert captured['env']['PIP_RETRIES'] == '10'
    assert captured['env']['PIP_PREFER_BINARY'] == '1'
