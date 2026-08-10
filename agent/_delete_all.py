"""剷除全部現有配對 EA"""
import os, sys, json, time, urllib.request, http.cookiejar

EAS = ['ADX_Trend', 'Bollinger_Band', 'Breakout', 'Correlation', 'Divergence', 'EMA_Cross',
       'Grid_Trading', 'Heikin_Ashi', 'MACD_Cross', 'Machine_Learn', 'Mean_Reversion',
       'Momentum', 'Price_Action', 'SMA_Cross', 'Trend_Follow', 'Volume_Spike']


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


def delete_ea(opener, ea):
    req = urllib.request.Request(f'http://localhost:5001/api/ea-config/{ea}', method='DELETE')
    try:
        resp = opener.open(req, timeout=20)
        return json.loads(resp.read().decode()).get('success', False)
    except Exception:
        return False


def main():
    opener = login()
    ok_n = 0
    for i, ea in enumerate(EAS, 1):
        ok = delete_ea(opener, ea)
        if ok:
            ok_n += 1
        print(f'{i}/{len(EAS)} {ea}: {"✅" if ok else "❌"}')
        time.sleep(1)
    print(f'\n剷除: {ok_n}/{len(EAS)}')
    return 0 if ok_n == len(EAS) else 1


if __name__ == '__main__':
    sys.exit(main())
