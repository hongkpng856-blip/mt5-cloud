"""剷除 10 個 EA（DELETE API）— 驗證熱鍵釋放"""
import os
import sys
import json
import time
import urllib.request
import http.cookiejar

BASE = os.path.dirname(os.path.abspath(__file__))
HOTKEYS_INI = os.path.join(os.environ['APPDATA'], 'MetaQuotes', 'Terminal',
                           'D0E8209F77C8CF37AD8BF550E51FF075', 'config', 'hotkeys.ini')

EAS = ['Bollinger_Band', 'Breakout', 'Divergence', 'EMA_Cross', 'Grid_Trading',
       'Heikin_Ashi', 'Machine_Learn', 'Momentum', 'Price_Action', 'SMA_Cross']


def login():
    cj = http.cookiejar.MozillaCookieJar()
    try:
        cj.load('/tmp/e2e7.txt')
    except Exception:
        pass
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    # 確保登入
    try:
        req = urllib.request.Request('http://localhost:5001/login',
                                     data=b'username=dev&password=dev1234',
                                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
        opener.open(req, timeout=10)
    except Exception:
        pass
    return opener


def delete_ea(opener, ea):
    req = urllib.request.Request(f'http://localhost:5001/api/ea-config/{ea}',
                                 method='DELETE')
    try:
        resp = opener.open(req, timeout=20)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {'success': False, 'error': str(e)}


def hotkey_gone(ea):
    with open(HOTKEYS_INI, 'rb') as f:
        text = f.read().decode('utf-16')
    return ea not in text


def main():
    opener = login()
    results = []
    for i, ea in enumerate(EAS, 1):
        r = delete_ea(opener, ea)
        time.sleep(2)
        hk = hotkey_gone(ea)
        ok = r.get('success') and hk
        results.append((ea, r.get('success'), hk))
        print(f'{i}/10 {ea}: DELETE {"✅" if r.get("success") else "❌"} 熱鍵釋放 {"✅" if hk else "❌"}')
    ok_n = sum(1 for _, d, h in results if d and h)
    print(f'\n剷除+熱鍵釋放: {ok_n}/10')
    return 0 if ok_n == 10 else 1


if __name__ == '__main__':
    sys.exit(main())
