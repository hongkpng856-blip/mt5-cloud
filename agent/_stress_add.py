"""添加 10 個 EA（install-local）— 驗證 compile + 熱鍵分配"""
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
    try:
        req = urllib.request.Request('http://localhost:5001/login',
                                     data=b'username=dev&password=dev1234',
                                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
        opener.open(req, timeout=10)
    except Exception:
        pass
    return opener


def install(opener, ea):
    req = urllib.request.Request(f'http://localhost:5001/api/ea-library/install-local/{ea}.mq5',
                                 data=b'{}', method='POST')
    try:
        resp = opener.open(req, timeout=75)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {'success': False, 'error': str(e)}


def hotkey_has(ea):
    with open(HOTKEYS_INI, 'rb') as f:
        text = f.read().decode('utf-16')
    return ea in text


def main():
    opener = login()
    results = []
    for i, ea in enumerate(EAS, 1):
        t0 = time.time()
        r = install(opener, ea)
        dt = time.time() - t0
        hk = hotkey_has(ea)
        ok = r.get('success') and hk
        results.append((ea, ok, r.get('compile_ok'), hk, dt))
        print(f'{i}/10 {ea}: 添加 {"✅" if ok else "❌"} compile={r.get("compile_ok")} 熱鍵={"✅" if hk else "❌"} ({dt:.0f}s)')
        if not ok:
            print(f'   error: {r.get("error", "")}')
    ok_n = sum(1 for _, o, _, _, _ in results if o)
    print(f'\n添加+compile+熱鍵: {ok_n}/10')
    return 0 if ok_n == 10 else 1


if __name__ == '__main__':
    sys.exit(main())
