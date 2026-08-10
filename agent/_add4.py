"""添加 4 個 EA（install-local — 配對 + compile + 熱鍵）"""
import os, sys, json, time, urllib.request, http.cookiejar

EAS = ['Swing_Trader', 'TestRunner', 'Trend_Follow', 'Volume_Spike']


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
        d = json.loads(resp.read().decode())
        return d.get('success', False), d.get('compile_ok', False), d.get('error', '')
    except Exception as e:
        return False, False, str(e)


def main():
    opener = login()
    results = []
    for i, ea in enumerate(EAS, 1):
        ok, cok, err = install(opener, ea)
        results.append((ea, ok, cok))
        print(f'{i}/{len(EAS)} {ea}: 添加 {"✅" if ok else "❌"} compile={"✅" if cok else "❌"}')
        if err:
            print(f'  error: {err}')
        time.sleep(2)
    print(f'\n添加: {sum(1 for _, o, _ in results if o)}/{len(EAS)}')
    return 0 if all(o for _, o, _ in results) else 1


if __name__ == '__main__':
    sys.exit(main())
