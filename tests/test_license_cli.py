# -*- coding: utf-8 -*-
"""آزمون اجرای واقعی ابزارهای فروشنده و ZIP تجاری."""
import hashlib
import json
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.build_commercial_package import _PRIVATE_PEM_RE


ROOT = Path(__file__).resolve().parents[1]
LICENSE_TOOL = ROOT / 'scripts' / 'license_tool.py'
PACKAGE_TOOL = ROOT / 'scripts' / 'build_commercial_package.py'


def _run(*args, env=None):
    return subprocess.run(
        [sys.executable] + [str(item) for item in args],
        cwd=str(ROOT), env=env, check=True, capture_output=True, text=True)


def test_encrypted_keygen_issue_verify_cli(tmp_path):
    private_key = tmp_path / 'vendor-private.pem'
    public_key = tmp_path / 'license_public_key.pem'
    token_file = tmp_path / 'customer.license'
    env = os.environ.copy()
    env['ACADEMY_KEY_PASSWORD'] = 'a-secure-test-password'

    _run(LICENSE_TOOL, 'keygen', '--private', private_key, '--public', public_key,
         '--password-env', 'ACADEMY_KEY_PASSWORD', env=env)
    private_content = private_key.read_bytes()
    assert private_content.startswith(b'-----BEGIN ENCRYPTED PRIVATE KEY-----')
    if os.name != 'nt':
        assert stat.S_IMODE(private_key.stat().st_mode) == 0o600
    with pytest.raises(subprocess.CalledProcessError):
        _run(LICENSE_TOOL, 'keygen', '--private', private_key,
             '--public', public_key, env=env)
    assert private_key.read_bytes() == private_content
    same_path = tmp_path / 'same-key.pem'
    with pytest.raises(subprocess.CalledProcessError):
        _run(LICENSE_TOOL, 'keygen', '--private', same_path,
             '--public', same_path, env=env)
    assert not same_path.exists()
    wrong_env = dict(env, ACADEMY_KEY_PASSWORD='a-different-test-password')
    with pytest.raises(subprocess.CalledProcessError) as wrong_password:
        _run(LICENSE_TOOL, 'issue', '--private', private_key,
             '--password-env', 'ACADEMY_KEY_PASSWORD',
             '--license-id', 'CLI-FAILED-001', '--customer', 'Invalid',
             '--domains', 'academy.example.com', env=wrong_env)
    assert 'Traceback' not in wrong_password.value.stderr
    assert 'ERROR:' in wrong_password.value.stderr

    _run(LICENSE_TOOL, 'issue', '--private', private_key,
         '--password-env', 'ACADEMY_KEY_PASSWORD',
         '--license-id', 'CLI-2026-001', '--customer', 'CLI Customer',
         '--domains', 'academy.example.com,*.customer.example',
         '--expires', '2027-12-31', '--plan', 'business',
         '--features', 'lms,shop', '--output', token_file, env=env)
    if os.name != 'nt':
        assert stat.S_IMODE(token_file.stat().st_mode) == 0o600
    verified = _run(LICENSE_TOOL, 'verify', '--public', public_key,
                    '--token-file', token_file,
                    '--domain', 'panel.customer.example', env=env)
    payload = json.loads(verified.stdout)
    assert payload['valid'] is True
    assert payload['plan'] == 'business'
    assert payload['license_id'] == 'CLI-…-001'


def test_commercial_zip_has_pinned_public_key_and_no_runtime_secrets(tmp_path):
    private_key = tmp_path / 'vendor-private.pem'
    public_key = tmp_path / 'license_public_key.pem'
    output = tmp_path / 'academy-commercial.zip'
    _run(LICENSE_TOOL, 'keygen', '--private', private_key, '--public', public_key)
    app_content = (ROOT / 'app.py').read_bytes()
    with pytest.raises(subprocess.CalledProcessError):
        _run(PACKAGE_TOOL, '--public-key', public_key,
             '--output', ROOT / 'app.py', '--version', 'unsafe', '--allow-dirty')
    assert (ROOT / 'app.py').read_bytes() == app_content

    _run(PACKAGE_TOOL, '--public-key', public_key, '--output', output,
         '--version', 'test-build', '--allow-dirty')

    with zipfile.ZipFile(str(output)) as archive:
        names = set(archive.namelist())
        assert 'license_public_key.pem' in names
        assert 'COMMERCIAL-BUILD.json' in names
        assert '.env' not in names
        assert 'instance/license.json' not in names
        assert not any('private' in Path(name).name.lower() for name in names)
        assert not any(_PRIVATE_PEM_RE.search(archive.read(name))
                       for name in names)
        deploy_mode = archive.getinfo('deploy/deploy.sh').external_attr >> 16
        assert deploy_mode & stat.S_IXUSR

        manifest = json.loads(archive.read('COMMERCIAL-BUILD.json'))
        for name, expected_hash in manifest['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected_hash
