"""完整 E2E ×10：部署 → 剷除 → 添加（每個 EA 完整生命周期）"""
import os
import sys
import json
import time
import subprocess
import urllib.request
import http.cookiejar

BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(BASE)
sys.path.insert(0, BASE)

CF = os.path.join(os.environ['APPDATA'], 'MetaQuotes', 'Terminal', 'Common', 'Files')
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


def heartbeat(ea):
    sf = os.path.join(CF, f'state_{ea}.json')
    if not os.path.isfile(sf):
        return None
    with open(sf, 'rb') as f:
        raw = f.read()
    try:
        d = json.loads(raw.decode('utf-8'))
    except Exception:
        d = json.loads(raw.decode('utf-16'))
    return d.get('status')


def hotkey_has(ea):
    with open(HOTKEYS_INI, 'rb') as f:
        text = f.read().decode('utf-16')
    return ea in text


def deploy(ea, magic):
    r = subprocess.run([sys.executable, '-u', 'agent/auto_attach.py',
                        '--ea', ea, '--symbol', 'EURUSD', '--tf', 'H1',
                        '--magic', str(magic), '--lot', '1'],
                       cwd=PROJECT, capture_output=True, timeout=90)
    out = r.stdout.decode('utf-8', errors='replace')
    ok = '附加成功' in out or '成功 attach' in out
    return ok


def delete_ea(opener, ea):
    req = urllib.request.Request(f'http://localhost:5001/api/ea-config/{ea}', method='DELETE')
    try:
        resp = opener.open(req, timeout=20)
        return json.loads(resp.read().decode()).get('success', False)
    except Exception:
        return False


def install(opener, ea):
    req = urllib.request.Request(f'http://localhost:5001/api/ea-library/install-local/{ea}.mq5',
                                 data=b'{}', method='POST')
    try:
        resp = opener.open(req, timeout=75)
        d = json.loads(resp.read().decode())
        return d.get('success', False) and d.get('compile_ok', False)
    except Exception:
        return False


def main():
    opener = login()
    results = []
    for i, ea in enumerate(EAS, 1):
        print(f'\n===== E2E {i}/10: {ea} =====')
        row = {'ea': ea}
        # 1. 部署
        t0 = time.time()
        d_ok = deploy(ea, 241000 + i)
        time.sleep(8)
        hb = heartbeat(ea)
        row['deploy'] = d_ok and hb == 'running'
        print(f'  部署: {"✅" if row["deploy"] else "❌"}（{time.time()-t0:.0f}s 心跳={hb}）')
        # 2. 剷除
        t0 = time.time()
        del_ok = delete_ea(opener, ea)
        time.sleep(2)
        hk_gone = not hotkey_has(ea)
        row['delete'] = del_ok and hk_gone
        print(f'  剷除: {"✅" if row["delete"] else "❌"}（{time.time()-t0:.0f}s 熱鍵釋放={hk_gone}）')
        # 3. 添加
        t0 = time.time()
        add_ok = install(opener, ea)
        time.sleep(2)
        hk_back = hotkey_has(ea)
        row['add'] = add_ok and hk_back
        print(f'  添加: {"✅" if row["add"] else "❌"}（{time.time()-t0:.0f}s 熱鍵={hk_back}）')
        results.append(row)
    # 總結
    ok_all = sum(1 for r in results if r['deploy'] and r['delete'] and r['add'])
    print(f'\n===== 總結 =====')
    print(f'E2E 完整成功: {ok_all}/10')
    for r in results:
        print(f"  {r['ea']}: 部署{'✅' if r['deploy'] else '❌'} 剷除{'✅' if r['delete'] else '❌'} 添加{'✅' if r['add'] else '❌'}")
    return 0 if ok_all == 10 else 1


if __name__ == '__main__':
    sys.exit(main())
