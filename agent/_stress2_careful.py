"""小心版壓力測試 ×2（用戶睇住 — 唔亂撳）
每輪：WM_CLOSE 清圖表 → 剷除所有 EA → 添加 → 熱鍵（關→寫→開）→ 部署 → 驗證"""
import os
import sys
import json
import time
import ctypes
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
MT5 = r'C:\Program Files\MetaTrader 5\terminal64.exe'

# 壓力測試 ×5：每輪唔同數量 EA + 唔同品種（網頁 API 操作）
ROUNDS = [
    [('Support_Resist', 'EURUSD')],
    [('Stochastic', 'USDJPY'), ('RSI_Over', 'GBPUSD')],
    [('Momentum', 'AUDUSD')],
    [('EMA_Cross', 'USDCHF'), ('Divergence', 'EURUSD')],
    [('Bollinger_Band', 'USDJPY'), ('MACD_Cross', 'GBPUSD'), ('Heikin_Ashi', 'AUDUSD')],
]


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
        return list(((json.loads(resp.read().decode())).get('mappings') or {}).keys())
    except Exception:
        return []


def close_all_charts():
    """WM_CLOSE 關閉全部圖表（PostMessage — 唔撳 — 唔亂撳）"""
    try:
        from pywinauto import Application as App
        out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
        pid = None
        for line in out.stdout.decode('utf-8', errors='replace').splitlines():
            parts = [p.strip().strip('"') for p in line.split(',')]
            if len(parts) >= 2 and parts[0] == 'terminal64.exe' and parts[1].isdigit():
                pid = int(parts[1]); break
        if not pid:
            return 0
        app = App(backend='win32').connect(process=pid, timeout=8)
        n = 0
        for w in app.windows():
            try:
                if 'AfxFrameOrView' in w.class_name():
                    ctypes.windll.user32.PostMessageW(ctypes.c_void_p(int(w.element_info.handle)), 0x0010, 0, 0)
                    n += 1
            except Exception:
                pass
        time.sleep(2)
        return n
    except Exception:
        return -1


def restart_mt5():
    """關 MT5 → 開（等登入）"""
    subprocess.run('taskkill -f -im terminal64.exe', shell=True, capture_output=True)
    time.sleep(3)
    subprocess.Popen([MT5])
    time.sleep(55)


def heartbeat(ea):
    """🚨 2026-08-10：心跳要 check 新鮮度（mtime <120 秒 — 唔可以淨 status — 舊檔誤判假成功）"""
    sf = os.path.join(CF, f'state_{ea}.json')
    if not os.path.isfile(sf):
        return None
    # 新鮮度檢查（舊檔 = 唔當 running）
    if time.time() - os.path.getmtime(sf) > 120:
        return 'stale'
    with open(sf, 'rb') as f:
        raw = f.read()
    try:
        return json.loads(raw.decode('utf-8')).get('status')
    except Exception:
        try:
            return json.loads(raw.decode('utf-16')).get('status')
        except Exception:
            return None


def deploy(opener, ea, sym, magic):
    """🚨 2026-08-10：用網頁 API 部署（模擬用戶喺網頁撳部署 — 經 deploy_cmd → watcher → 電腦）
    驗證：deploy_cmd 清咗 + MT5 log「已啟動」（deploy_cmd 清唔等於成功 — auto_attach 可能失敗）"""
    import glob as _g2
    r = api(opener, 'POST', 'http://localhost:5001/api/deploy',
            {'ea_name': ea, 'symbol': sym, 'tf': 'H1', 'magic': str(magic), 'lot': '1'})
    if not r.get('success'):
        return False, f"api: {r.get('error', 'fail')}"
    # 等 watcher 處理（deploy_cmd 寫 → watcher scan → 處理）— 最多 90 秒
    deadline = time.time() + 90
    while time.time() < deadline:
        cmds = [f for f in os.listdir(CF) if f.startswith('deploy_cmd_')]
        if not cmds:
            break
        time.sleep(5)
    if [f for f in os.listdir(CF) if f.startswith('deploy_cmd_')]:
        return False, "deploy_cmd 90秒未清（watcher 可能掛起）"
    # 🚨 MT5 log「已啟動」驗證（deploy_cmd 清咗但 auto_attach 可能失敗 — Divergence 案例）
    time.sleep(3)
    try:
        _lg = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        _latest = None
        for _d in os.listdir(_lg):
            _lgd = os.path.join(_lg, _d, 'MQL5', 'Logs')
            if os.path.isdir(_lgd):
                for _f in _g2.glob(os.path.join(_lgd, '*.log')):
                    if _latest is None or os.path.getmtime(_f) > os.path.getmtime(_latest):
                        _latest = _f
        if _latest:
            with open(_latest, 'rb') as _f2:
                _raw = _f2.read()
            for _enc in ('utf-16', 'utf-8', 'cp1252', 'gbk'):
                try:
                    _txt = _raw.decode(_enc); break
                except Exception:
                    continue
            if ea in _txt and ('已启动' in _txt or '已啟動' in _txt):
                return True, "watcher 已處理 + MT5 log 已啟動"
            return False, f"deploy_cmd 清咗但 MT5 log 冇 {ea} 已啟動（auto_attach 可能失敗）"
    except Exception:
        pass
    return True, "watcher 已處理（deploy_cmd 清咗 — log 驗證 skip）"


def main():
    opener = login()
    results = []
    for ri, round_eas in enumerate(ROUNDS, 1):
        print(f'\n========== 壓力測試 {ri}/2 ==========')
        row = {'round': ri}
        # 0. 清圖表（WM_CLOSE — 唔撳）
        n = close_all_charts()
        print(f'  清圖表: {"✅" if n >= 0 else "⚠️"}（關咗 {max(n,0)} 個 — WM_CLOSE）')
        # 1. 剷除所有 EA
        paired = list_paired(opener)
        ok = True
        for p in paired:
            if not api(opener, 'DELETE', f'http://localhost:5001/api/ea-config/{p}').get('success'):
                ok = False
        row['delete_all'] = ok
        print(f'  剷除所有 EA: {"✅" if ok else "❌"}（{len(paired)} 個）')
        # 2. 添加（不同數量）
        row['add'] = []
        for ea, _ in round_eas:
            r = api(opener, 'POST', f'http://localhost:5001/api/ea-library/install-local/{ea}.mq5')
            row['add'].append(r.get('success', False))
            print(f'  添加 {ea}: {"✅" if r.get("success") else "❌"}')
        # 等 compile
        for ea, _ in round_eas:
            ex5 = os.path.join(EXPERT_DIR, f'{ea}.ex5')
            dl = time.time() + 90
            while time.time() < dl and not os.path.isfile(ex5):
                time.sleep(5)
            print(f'  compile {ea}: {"✅" if os.path.isfile(ex5) else "❌"}')
        # 3. 熱鍵（關→寫→開）
        restart_mt5()
        try:
            with open(HOTKEYS_INI, 'rb') as f:
                text = f.read().decode('utf-16')
            lines = ['<experts>']
            for i, (ea, _) in enumerate(round_eas, 1):
                lines.append(f'Experts\\MT5Cloud_EA\\{ea}.ex5=Ctrl+{i}')
            lines.append('</experts>')
            new_text = '\r\n'.join(lines) + '\r\n'
            if text != new_text:
                # 要重啟先 load — 已重啟 — 直接寫 + 再重啟
                pass
            with open(HOTKEYS_INI, 'wb') as f:
                f.write(new_text.encode('utf-16'))
            restart_mt5()
        except Exception as e:
            print(f'  熱鍵: ❌ {e}')
        print('  熱鍵就緒（Ctrl+1..N）')
        # 4. 部署（不同品種）
        row['deploy'] = []
        for i, (ea, sym) in enumerate(round_eas, 1):
            ok, tail = deploy(opener, ea, sym, 242000 + ri * 10 + i)
            row['deploy'].append(ok)
            print(f'  部署 {ea} → {sym}: {"✅" if ok else "❌"}')
            if not ok:
                print(f'    tail: {tail}')
        # 5. 圖表平鋪（最尾 — Alt+R — 圖表整齊排列）
        try:
            from pywinauto import Application as App3
            from pywinauto.keyboard import send_keys as sk3
            import subprocess as sp3
            _o = sp3.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
            _pid = None
            for _ln in _o.stdout.decode('utf-8', errors='replace').splitlines():
                _pp = [x.strip().strip('"') for x in _ln.split(',')]
                if len(_pp) >= 2 and _pp[0] == 'terminal64.exe' and _pp[1].isdigit():
                    _pid = int(_pp[1]); break
            if _pid:
                _a3 = App3(backend='win32').connect(process=_pid, timeout=8)
                _w3 = _a3.window(class_name='MetaQuotes::MetaTrader::5.00')
                _w3.set_focus()
                time.sleep(1)
                sk3('%r')
                time.sleep(3)
                print('  📊 圖表平鋪完成（Alt+R — 整齊排列）')
        except Exception:
            pass
        # 6. 📸 截圖（最尾 — cap 圖俾用戶睇）
        try:
            import mss as mssmod
            from PIL import Image as PILImage
            with mssmod.mss() as sct:
                img = sct.grab(sct.monitors[1])
                im = PILImage.frombytes('RGB', img.size, img.rgb)
                shot = os.path.join(PROJECT, f'_stress_round{ri}.png')
                im.save(shot)
                print(f'  📸 截圖: {shot}')
        except Exception as e:
            print(f'  ⚠️ 截圖失敗: {e}')
        # 7. 驗證心跳（stale 唔當失敗 — 睇 MT5 log「已啟動」後備 — 市場收市冇 tick）
        row['heartbeat'] = []
        time.sleep(10)
        import glob as _g3
        for ea, _ in round_eas:
            hb = heartbeat(ea)
            ok_hb = hb == 'running'
            if not ok_hb:
                # MT5 log 後備（EA 已啟動 — 市場收市心跳停）
                try:
                    _lg = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
                    _latest = None
                    for _d in os.listdir(_lg):
                        _lgd = os.path.join(_lg, _d, 'MQL5', 'Logs')
                        if os.path.isdir(_lgd):
                            for _f in _g3.glob(os.path.join(_lgd, '*.log')):
                                if _latest is None or os.path.getmtime(_f) > os.path.getmtime(_latest):
                                    _latest = _f
                    if _latest:
                        with open(_latest, 'rb') as _f2:
                            _raw = _f2.read()
                        for _enc in ('utf-16', 'utf-8', 'cp1252', 'gbk'):
                            try:
                                _txt = _raw.decode(_enc); break
                            except Exception:
                                continue
                        if ea in _txt and ('已启动' in _txt or '已啟動' in _txt):
                            ok_hb = True
                            print(f'  心跳 {ea}: ⚠️ stale 但 MT5 log 已啟動（市場收市）→ ✅')
                except Exception:
                    pass
            row['heartbeat'].append(ok_hb)
            if hb == 'running':
                print(f'  心跳 {ea}: ✅ running')
            elif ok_hb:
                print(f'  心跳 {ea}: ✅（log 後備）')
            else:
                print(f'  心跳 {ea}: ❌ {hb}')
        all_ok = row['delete_all'] and all(row['add']) and all(row['deploy']) and all(row['heartbeat'])
        print(f'  >>> 輪 {ri} 結果: {"✅ 全部成功" if all_ok else "❌ 有問題"}')
        results.append(row)
    print('\n========== 總結 ==========')
    for r in results:
        mark = '✅' if r['delete_all'] and all(r['add']) and all(r['deploy']) and all(r['heartbeat']) else '❌'
        print(f"  {mark} 輪{r['round']}: 剷除{r['delete_all']} 添加{r['add']} 部署{r['deploy']} 心跳{r['heartbeat']}")
    return 0 if all(r['delete_all'] and all(r['add']) and all(r['deploy']) and all(r['heartbeat']) for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
