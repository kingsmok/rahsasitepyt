# -*- coding: utf-8 -*-
"""رگرسیون نصب دستی/خودکار وابستگی‌های قفل‌شدهٔ Python 3.11."""
import os
from pathlib import Path

import pytest

import installer
import updater


ROOT = Path(__file__).resolve().parents[1]


def test_requirements_are_python311_binary_only_and_fully_pinned():
    requirements = (ROOT / 'requirements.txt').read_text(encoding='utf-8')
    package_lines = [
        line.strip() for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith(('#', '--'))
    ]

    assert '--only-binary=:all:' in requirements
    assert 'greenlet==3.2.5' in package_lines
    assert 'Pillow==12.2.0' in package_lines
    assert 'SQLAlchemy==2.0.30' in package_lines
    assert all('==' in line for line in package_lines)
    assert not any(any(operator in line for operator in ('>=', '<=', '~=', '!='))
                   for line in package_lines)


def test_install_helper_requires_cpython311_and_runs_pip_check():
    helper = (ROOT / 'scripts' / 'install_dependencies.sh').read_text(encoding='utf-8')

    assert 'sys.version_info[:2] == (3, 11)' in helper
    assert 'platform.python_implementation() == "CPython"' in helper
    assert '--only-binary=:all:' in helper
    assert '-m pip check' in helper


def test_updater_upgrades_tools_installs_binary_wheels_and_checks(monkeypatch):
    calls = []

    def fake_run(cmd, cwd=updater.BASE_DIR, timeout=120, env=None):
        calls.append({'cmd': cmd, 'timeout': timeout, 'env': env})
        return 0, 'ok'

    monkeypatch.setattr(updater, '_requirements_changed', lambda *args, **kwargs: True)
    monkeypatch.setattr(updater, '_validate_update_runtime', lambda: None)
    monkeypatch.setattr(updater, '_run', fake_run)
    monkeypatch.delenv('PIP_DEFAULT_TIMEOUT', raising=False)
    monkeypatch.delenv('PIP_RETRIES', raising=False)
    monkeypatch.delenv('UPDATE_INSTALL_DEPENDENCIES', raising=False)

    result = updater._install_changed_dependencies('old')

    assert 'pip check موفق بود' in result
    assert len(calls) == 3
    assert calls[0]['cmd'][-4:] == ['--upgrade', 'pip', 'setuptools', 'wheel']
    assert calls[1]['cmd'][-2:] == ['-r', str(ROOT / 'requirements.txt')]
    assert calls[2]['cmd'] == [updater.sys.executable, '-m', 'pip', 'check']
    assert '--only-binary=:all:' in calls[0]['cmd']
    assert '--prefer-binary' in calls[1]['cmd']
    assert calls[1]['timeout'] == 900
    assert calls[1]['env']['PIP_DEFAULT_TIMEOUT'] == '120'
    assert calls[1]['env']['PIP_RETRIES'] == '10'
    assert calls[1]['env']['PIP_PREFER_BINARY'] == '1'
    assert calls[1]['env']['PIP_ONLY_BINARY'] == ':all:'


def test_updater_reports_pip_check_failure(monkeypatch):
    call_number = {'value': 0}

    def fake_run(cmd, cwd=updater.BASE_DIR, timeout=120, env=None):
        call_number['value'] += 1
        if cmd[-1] == 'check':
            return 1, 'broken-package requires missing-package'
        return 0, 'ok'

    monkeypatch.setattr(updater, '_requirements_changed', lambda *args, **kwargs: True)
    monkeypatch.setattr(updater, '_validate_update_runtime', lambda: None)
    monkeypatch.setattr(updater, '_run', fake_run)

    with pytest.raises(updater.UpdateError, match='pip check') as exc_info:
        updater._install_changed_dependencies('old')

    assert 'broken-package requires missing-package' in str(exc_info.value)
    assert call_number['value'] == 3


def test_updater_rejects_non_cpython311_for_dependency_changes(monkeypatch):
    class Python312(tuple):
        major = 3
        minor = 12

    monkeypatch.setattr(updater.sys, 'version_info', Python312((3, 12, 0)))

    with pytest.raises(updater.UpdateError, match='CPython 3.11'):
        updater._validate_update_runtime()


def test_updater_can_explicitly_disable_dependency_install(monkeypatch):
    monkeypatch.setattr(updater, '_requirements_changed', lambda *args, **kwargs: True)
    monkeypatch.setenv('UPDATE_INSTALL_DEPENDENCIES', '0')
    monkeypatch.setattr(
        updater, '_run',
        lambda *args, **kwargs: pytest.fail('pip must not run when explicitly disabled'),
    )

    result = updater._install_changed_dependencies('old')

    assert 'غیرفعال' in result


def test_installer_preserves_update_and_unknown_environment_settings(tmp_path, monkeypatch):
    env_path = tmp_path / '.env'
    env_path.write_text(
        'SECRET_KEY=' + ('s' * 64) + '\n'
        'GIT_REPO_URL=https://github.com/example/project.git\n'
        'GIT_BRANCH=release\n'
        'GITHUB_WEBHOOK_SECRET=webhook-secret\n'
        'UPDATE_INSTALL_DEPENDENCIES=0\n'
        'UPDATE_TOUCH_RESTART=0\n'
        'GIT_FETCH_TIMEOUT=450\n'
        'DB_MIGRATION_TIMEOUT=1200\n'
        'PIP_INSTALL_TIMEOUT=1000\n'
        'PIP_DEFAULT_TIMEOUT=180\n'
        'PIP_RETRIES=12\n'
        'PIP_INDEX_URL=https://mirror.example/simple/\n'
        'CUSTOM_PAYMENT_SECRET=must-survive\n',
        encoding='utf-8',
    )
    monkeypatch.setattr(installer, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(installer, '_persisted_db_url', lambda value: value)
    monkeypatch.setitem(os.environ, 'SECRET_KEY', 'test-before')
    monkeypatch.setitem(os.environ, 'INSTALL_REPAIR_TOKEN', 'test-before')

    installer.write_env_file('', 'n' * 64)
    rewritten = env_path.read_text(encoding='utf-8')

    for expected in (
        'GIT_REPO_URL=https://github.com/example/project.git',
        'GIT_BRANCH=release',
        'GITHUB_WEBHOOK_SECRET=webhook-secret',
        'UPDATE_INSTALL_DEPENDENCIES=0',
        'UPDATE_TOUCH_RESTART=0',
        'GIT_FETCH_TIMEOUT=450',
        'DB_MIGRATION_TIMEOUT=1200',
        'PIP_INSTALL_TIMEOUT=1000',
        'PIP_DEFAULT_TIMEOUT=180',
        'PIP_RETRIES=12',
        'PIP_INDEX_URL=https://mirror.example/simple/',
        'CUSTOM_PAYMENT_SECRET=must-survive',
    ):
        assert expected in rewritten


def test_installer_writes_safe_update_defaults_for_new_install(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr(installer, '_persisted_db_url', lambda value: value)
    monkeypatch.setitem(os.environ, 'SECRET_KEY', 'test-before')
    monkeypatch.setitem(os.environ, 'INSTALL_REPAIR_TOKEN', 'test-before')

    installer.write_env_file('', 'n' * 64)
    rewritten = (tmp_path / '.env').read_text(encoding='utf-8')

    assert 'GIT_BRANCH=main' in rewritten
    assert 'UPDATE_INSTALL_DEPENDENCIES=1' in rewritten
    assert 'UPDATE_TOUCH_RESTART=1' in rewritten
    assert 'PIP_DEFAULT_TIMEOUT=120' in rewritten
    assert 'PIP_RETRIES=10' in rewritten
