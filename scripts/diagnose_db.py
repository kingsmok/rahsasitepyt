# -*- coding: utf-8 -*-
"""عیب‌یابی اتصال MySQL روی هاست اشتراکی.

اجرا (در پوشه پروژه روی هاست):
    ./venv/bin/python scripts/diagnose_db.py
یا اگر مسیر venv فرق دارد:
    /home/USER/virtualenv/public_html/class/3.11/bin/python scripts/diagnose_db.py

این اسکریپت هیچ چیزی را تغییر نمی‌دهد — فقط تشخیص می‌دهد که خطای
«2013 Lost connection to MySQL server during query» از کجاست.
"""
import os
import socket
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, '.env'), override=True)
except Exception:
    pass


def _mask(url):
    """پنهان‌کردن رمز در خروجی"""
    if '@' not in url:
        return url
    head, tail = url.split('@', 1)
    if ':' in head:
        scheme_user, _pw = head.rsplit(':', 1)
        return scheme_user + ':****@' + tail
    return url


def main():
    print('=' * 62)
    print(' عیب‌یابی دیتابیس — آکادمی')
    print('=' * 62)

    url = os.environ.get('DATABASE_URL', '')
    if not url:
        print('\nDATABASE_URL خالی است → اپ از SQLite استفاده می‌کند.')
        print('اگر انتظار MySQL دارید، فایل .env را بررسی کنید.')
        return 0
    print('\nDATABASE_URL = ' + _mask(url))
    if not url.startswith('mysql'):
        print('این URL مربوط به MySQL نیست — چیزی برای تست نیست.')
        return 0

    # ── تجزیه URL ──
    try:
        from sqlalchemy.engine import make_url
        u = make_url(url)
        host = u.host or 'localhost'
        port = u.port or 3306
        user = u.username or ''
        dbname = u.database or ''
        sock_path = (u.query or {}).get('unix_socket')
    except Exception as e:
        print('❌ URL قابل تجزیه نیست: %s' % e)
        return 1
    print('host=%s  port=%s  user=%s  db=%s  unix_socket=%s'
          % (host, port, user, dbname, sock_path or '-'))

    # ── ۱) DNS ──
    print('\n[۱] بررسی DNS ...')
    try:
        infos = socket.getaddrinfo(host, None)
        ips = sorted({i[4][0] for i in infos})
        print('    ✅ %s → %s' % (host, ', '.join(ips)))
    except Exception as e:
        print('    ❌ نام میزبان پیدا نشد: %s' % e)
        print('    → مقدار Host را از پنل هاست بردارید (اغلب: localhost)')
        return 1

    # ── ۲) پورت TCP ──
    print('\n[۲] بررسی باز بودن پورت %s (تایم‌اوت ۱۰ ثانیه) ...' % port)
    t0 = time.time()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    tcp_ok = False
    try:
        s.connect((host, int(port)))
        tcp_ok = True
        print('    ✅ پورت باز است (%.1f ثانیه)' % (time.time() - t0))
    except socket.timeout:
        print('    ❌ تایم‌اوت بعد از %.0f ثانیه — پورت فیلتر شده است.'
              % (time.time() - t0))
        print('    → این دقیقاً همان علت خطای «2013 Lost connection» است.')
    except Exception as e:
        print('    ❌ اتصال رد شد: %s' % e)
    finally:
        try:
            s.close()
        except Exception:
            pass

    # ── ۳) handshake واقعی MySQL ──
    if tcp_ok:
        print('\n[۳] بررسی handshake سرور MySQL ...')
        try:
            import pymysql
            t0 = time.time()
            conn = pymysql.connect(
                host=host, port=int(port), user=user,
                password=u.password or '', database=dbname,
                connect_timeout=10, read_timeout=20, write_timeout=20,
                charset='utf8mb4')
            with conn.cursor() as cur:
                cur.execute('SELECT VERSION()')
                ver = cur.fetchone()[0]
                cur.execute("SHOW VARIABLES LIKE 'max_connections'")
                mc = cur.fetchone()
                cur.execute("SHOW STATUS LIKE 'Threads_connected'")
                tc = cur.fetchone()
            conn.close()
            print('    ✅ اتصال کامل شد (%.1f ثانیه) — MySQL %s'
                  % (time.time() - t0, ver))
            if mc and tc:
                print('    اتصال‌های فعال: %s از %s' % (tc[1], mc[1]))
        except Exception as e:
            print('    ❌ %s: %s' % (type(e).__name__, str(e)[:200]))
            if '2013' in str(e) or '2003' in str(e):
                print('    → سرور پیش از تکمیل handshake اتصال را بست.')
                print('      معمولاً یعنی host اشتباه است یا هاست فقط')
                print('      سوکت محلی می‌پذیرد (بخش ۴ را ببینید).')

    # ── ۴) سوکت‌های محلی ──
    print('\n[۴] جست‌وجوی سوکت محلی MySQL ...')
    found = []
    for p in ('/var/lib/mysql/mysql.sock', '/var/run/mysqld/mysqld.sock',
              '/run/mysqld/mysqld.sock', '/tmp/mysql.sock', '/tmp/mariadb.sock'):
        if os.path.exists(p):
            found.append(p)
            print('    ✅ پیدا شد: %s' % p)
    if not found:
        print('    (سوکتی پیدا نشد)')
    elif not tcp_ok:
        print('\n    💡 راه‌حل: این خط را در فایل .env بگذارید:')
        base = url.split('?')[0]
        q = 'charset=utf8mb4&unix_socket=' + found[0]
        print('    DATABASE_URL=%s?%s' % (_mask(base), q))
        print('    سپس:  touch passenger_wsgi.py')

    print('\n' + '=' * 62)
    print('اگر بخش ۲ یا ۳ قرمز بود، متن همین خروجی را برای پشتیبانی هاست')
    print('بفرستید و بپرسید MySQL از طریق کدام host/سوکت در دسترس است.')
    print('=' * 62)
    return 0


if __name__ == '__main__':
    sys.exit(main())
