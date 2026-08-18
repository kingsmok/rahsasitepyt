#!/usr/bin/env bash
# نصب قابل‌اعتماد وابستگی‌ها روی Linux/cPanel با timeout بلند و wheelهای آماده.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -gt 1 ]]; then
    echo "Usage: bash scripts/install_dependencies.sh [path/to/python]" >&2
    exit 2
fi

if [[ $# -eq 1 ]]; then
    PYTHON_BIN="$1"
elif [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
elif [[ -x "./venv/bin/python" ]]; then
    PYTHON_BIN="./venv/bin/python"
elif [[ -x "./.venv/bin/python" ]]; then
    PYTHON_BIN="./.venv/bin/python"
else
    echo "محیط مجازی پیدا نشد. ابتدا اجرا کنید: python3 -m venv venv" >&2
    exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "فایل Python قابل اجرا نیست: $PYTHON_BIN" >&2
    exit 1
fi

PIP_NETWORK_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-120}"
PIP_NETWORK_RETRIES="${PIP_RETRIES:-10}"
PIP_ARGS=(--timeout "$PIP_NETWORK_TIMEOUT" --retries "$PIP_NETWORK_RETRIES" --prefer-binary)

"$PYTHON_BIN" - <<'PY'
import sys
if not ((3, 9) <= sys.version_info[:2] <= (3, 14)):
    raise SystemExit(
        "این نسخه پروژه به CPython 3.9 تا 3.14 نیاز دارد؛ نسخه فعلی: "
        + sys.version.split()[0]
    )
print("Python:", sys.version.split()[0])
PY

echo "به‌روزرسانی ابزارهای نصب (timeout=${PIP_NETWORK_TIMEOUT}s, retries=${PIP_NETWORK_RETRIES})..."
"$PYTHON_BIN" -m pip install "${PIP_ARGS[@]}" --upgrade pip setuptools wheel

echo "نصب requirements.txt از wheelهای باینری سازگار..."
"$PYTHON_BIN" -m pip install "${PIP_ARGS[@]}" -r requirements.txt
"$PYTHON_BIN" -m pip check

echo "وابستگی‌ها با موفقیت نصب شدند."
