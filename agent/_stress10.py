"""實機壓力測試 ×10：每輪 剷除全部 EA → 添加 1 個 → 部署（唔同品種）→ 驗證心跳"""
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
EXPERT_DIR = os.path.join(os.environ['APPDATA'], 'MetaQuotes', 'Terminal',
                          'D0E8209F77C8CF37AD8BF550E51FF075', 'MQL5', 'Experts', 'MT5Cloud_EA')

# 10 個 EA（每輪一個 — 唔同）
EAS = ['Support_Resist', 'Stochastic', 'RSI_Over', 'Momentum', 'EMA_Cross',
       'Divergence', 'Bollinger_Band', 'MACD_Cross', 'Heikin_Ashi', 'SMA_Cross']
# 品種輪流
SYMS = ['EURUSD', 'USDJPY', 'GBPUSD', 'AUDUSD', 'USDCHF', 'EURUSD', 'USDJPY', 'GBPUSD', 'AUDUSD', 'USDCHF']


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


def api(opener, method, url, data=None):
    try:
        body = json.dumps(data).encode() if data else b'{}'
        req = urllib.request.Request(url, data=body, method=method,
                                     headers={'Content-Type': 'application/json'})
        resp = opener.open(req, timeout=75)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {'success': False, 'error': str(e)}


def list_paired(opener):
    try:
        resp = opener.open(urllib.request.Request('http://localhost:5001/api/ea-config?t=%d' % int(time.time())), timeout=15)
        d = json.loads(resp.read().decode())
        return list((d.get('mappings') or {}).keys())
    except Exception:
        return []


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


def deploy(ea, sym, magic):
    r = subprocess.run([sys.executable, '-u', 'agent/auto_attach.py',
                        '--ea', ea, '--symbol', sym, '--tf', 'H1',
                        '--magic', str(magic), '--lot', '1'],
                       cwd=PROJECT, capture_output=True, timeout=90)
    out = r.stdout.decode('utf-8', errors='replace')
    ok = '附加成功' in out or '成功 attach' in out
    return ok, out[-150:]


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    opener = login()
    results = []
    for i in range(rounds):
        ea = EAS[i]
        sym = SYMS[i]
        print(f'\n========== 壓力測試 {i+1}/10: {ea} → {sym} ==========')
        row = {'round': i + 1, 'ea': ea, 'sym': sym}
        # 1. 剷除所有 EA
        paired = list_paired(opener)
        del_ok = True
        for p in paired:
            if not api(opener, 'DELETE', f'http://localhost:5001/api/ea-config/{p}').get('success'):
                del_ok = False
        row['delete_all'] = del_ok and len(paired) >= 0
        print(f'  剷除全部: {"✅" if row["delete_all"] else "❌"}（{len(paired)} 個）')
        # 2. 添加（install-local）
        t0 = time.time()
        add = api(opener, 'POST', f'http://localhost:5001/api/ea-library/install-local/{ea}.mq5')
        row['add'] = add.get('success', False)
        print(f'  添加: {"✅" if row["add"] else "❌"}（{time.time()-t0:.0f}s）')
        # 3. 等 compile（最多 90 秒）
        ex5 = os.path.join(EXPERT_DIR, f'{ea}.ex5')
        deadline = time.time() + 90
        while time.time() < deadline and not os.path.isfile(ex5):
            time.sleep(5)
        row['compiled'] = os.path.isfile(ex5)
        print(f'  compile: {"✅" if row["compiled"] else "❌"}')
        # 4. 確保熱鍵（關 MT5 → 寫 → 開）
        t0 = time.time()
        try:
            subprocess.run('taskkill -f -im terminal64.exe', shell=True, capture_output=True)
            time.sleep(3)
            with open(HOTKEYS_INI, 'rb') as f:
                text = f.read().decode('utf-16')
            if ea not in text:
                text = text.replace('</experts>', f'Experts\\MT5Cloud_EA\\{ea}.ex5=Ctrl+1\r\n</experts>')
                with open(HOTKEYS_INI, 'wb') as f:
                    f.write(text.encode('utf-16'))
            subprocess.Popen([r'C:\Program Files\MetaTrader 5\terminal64.exe'])
            time.sleep(55)
        except Exception:
            pass
        print(f'  熱鍵就緒（{time.time()-t0:.0f}s）')
        # 🚨 每輪部署前關閉全部圖表（唔累積 — 留 1 個 = 部署嗰個）
        try:
            subprocess.run([sys.executable, '-u', os.path.join(BASE, '_close_all_charts.py')],
                           cwd=PROJECT, capture_output=True, timeout=120)
        except Exception:
            pass
        # 5. 部署
        t0 = time.time()
        ok, tail = deploy(ea, sym, 241200 + i)
        row['deploy'] = ok
        print(f'  部署: {"✅" if ok else "❌"}（{time.time()-t0:.0f}s）')
        if not ok:
            print(f'  tail: {tail}')
        # 6. 驗證心跳
        time.sleep(10)
        hb = heartbeat(ea)
        row['heartbeat'] = hb == 'running'
        print(f'  心跳: {"✅ running" if row["heartbeat"] else f"❌ {hb}"}')
        results.append(row)
        print(f'  >>> 輪 {i+1} 結果: {"✅ 全部成功" if all([row["delete_all"], row["add"], row["compiled"], row["deploy"], row["heartbeat"]]) else "❌ 有問題"}')
    # 總結
    print('\n========== 總結 ==========')
    full_ok = sum(1 for r in results if r['delete_all'] and r['add'] and r['compiled'] and r['deploy'] and r['heartbeat'])
    print(f'完整成功: {full_ok}/10')
    for r in results:
        mark = '✅' if r['delete_all'] and r['add'] and r['compiled'] and r['deploy'] and r['heartbeat'] else '❌'
        print(f"  {mark} 輪{r['round']}: {r['ea']}→{r['sym']} 剷除{r['delete_all']} 添加{r['add']} compile{r['compiled']} 部署{r['deploy']} 心跳{r['heartbeat']}")
    return 0 if full_ok == 10 else 1


if __name__ == '__main__':
    sys.exit(main())
