# -*- coding: utf-8 -*-
# 壓力測試 2026-08-17 — 一體化部署（Ctrl+9 → OpenChart script 開圖表 + 套模板掛 EA）
# 每輪：清圖表 → 剸除全部 EA → 添加 N 個 EA → 部署（網頁 API）→ 驗證（MT5 log）
import sys, os, time, json, glob, ctypes, subprocess
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:\Users\hongk\Desktop\mt5-cloud\agent')

PORT = 5001
EA_LIB = r'C:\Users\hongk\Desktop\mt5-cloud\server\static\ea_library'
EA_DIR = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\MT5Cloud_EA'
LOG_DIR = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Logs'
COMMON = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\Common\Files'
TERMINAL = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\config\hotkeys.ini'

# 可用目標 EA（真實 — 有心跳 + 唔係 ADX_Trend 失敗測試）
TARGET_EAS = ['EMA_Cross', 'Breakout', 'RSI_Over', 'MACD_Cross', 'Bollinger_Band', 'Parabolic_SAR']
SYMBOLS = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCHF', 'USDCNH']

def api(path, method='GET', data=None):
    import urllib.request
    url = f'http://127.0.0.1:{PORT}{path}'
    if data is not None:
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, method='POST', headers={'Content-Type': 'application/json'})
    else:
        req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {'error': str(e)}

def login():
    r = api('/login', 'POST', {'username': 'dev'})
    return r

def close_all_charts():
    """Ctrl+W 逐個關圖表"""
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        from pywinauto import Application
        out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True, text=True).stdout
        pid = None
        for line in out.splitlines():
            p = [x.strip().strip('"') for x in line.split(',')]
            if len(p) >= 2 and p[0] == 'terminal64.exe' and p[1].isdigit():
                pid = int(p[1]); break
        if not pid:
            return 0
        app = Application(backend='win32').connect(process=pid, timeout=8)
        win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
        import ctypes as ct
        u = ct.windll.user32
        u.SetForegroundWindow(ct.c_void_p(int(win.element_info.handle)))
        time.sleep(1)
        # count charts (AfxFrameOrView children)
        n = 0
        try:
            for d in win.descendants():
                if d.element_info.class_name == 'MDIClient':
                    n = len(d.children()); break
        except Exception:
            pass
        for _ in range(min(n, 15)):
            pyautogui.hotkey('ctrl', 'w')
            time.sleep(0.6)
        time.sleep(1)
        return n
    except Exception as e:
        print(f'  close_all_charts err: {e}')
        return 0

def remove_all_eas():
    """通過完整移除（remove-local）剸除所有本機 EA"""
    removed = []
    for f in os.listdir(EA_DIR):
        if f.endswith(('.ex5', '.mq5')):
            base = os.path.splitext(f)[0]
            if base == 'OpenChart_Helper':
                continue
            try:
                os.remove(os.path.join(EA_DIR, f))
                removed.append(f)
            except Exception as e:
                print(f'  刪 {f} 失敗: {e}')
    # 清 hotkeys.ini（保留 scripts Ctrl+9）
    try:
        c = open(TERMINAL, encoding='utf-16-le', errors='ignore').read()
        # 保留 <scripts>，清 <experts>
        scripts_part = ''
        if '<scripts>' in c:
            import re
            m = re.search(r'<scripts>.*?</scripts>', c, flags=re.S)
            if m:
                scripts_part = m.group(0)
        open(TERMINAL, 'w', encoding='utf-16-le').write(scripts_part or '')
    except Exception as e:
        print(f'  清 hotkeys err: {e}')
    return removed

def install_ea(ea):
    """install-local 配對"""
    src = os.path.join(EA_LIB, f'{ea}.mq5')
    if not os.path.isfile(src):
        return f'{ea} 唔喺庫'
    import shutil
    shutil.copy(src, os.path.join(EA_DIR, f'{ea}.mq5'))
    # 複製完 → 編譯（MetaEditor）+ 加熱鍵
    try:
        subprocess.run([r'C:\Program Files\MetaTrader 5\MetaEditor64.exe', f'/compile:{os.path.join(EA_DIR, ea)}.mq5', '/log'], timeout=60)
        time.sleep(5)
    except Exception:
        pass
    # 加熱鍵（避免 Ctrl+9 — 用 1-8）
    try:
        c = open(TERMINAL, encoding='utf-16-le', errors='ignore').read()
        used = set()
        import re
        for m in re.finditer(r'=Ctrl\+(\d)', c):
            used.add(f'Ctrl+{m.group(1)}')
        combo = None
        for i in range(1, 9):
            if f'Ctrl+{i}' not in used:
                combo = f'Ctrl+{i}'
                break
        if combo:
            experts_part = f'Experts\\MT5Cloud_EA\\{ea}.ex5={combo}'
            if '<experts>' in c:
                # 插入 <experts> 區
                c = re.sub(r'(<experts>\r?\n)(.*?)(</experts>)', lambda m: m.group(1) + m.group(2) + experts_part + '\r\n' + m.group(3), c, flags=re.S)
            else:
                c = f'<experts>\r\n{experts_part}\r\n</experts>\r\n' + c
            open(TERMINAL, 'w', encoding='utf-16-le').write(c)
            print(f'    {ea} 熱鍵 {combo}')
    except Exception as e:
        print(f'  熱鍵 err: {e}')
    return f'{ea} 已配對'

def restart_mt5():
    """重啟 MT5（reload 所有熱鍵）"""
    subprocess.run('taskkill -f -im terminal64.exe', shell=True, capture_output=True)
    time.sleep(4)
    subprocess.run("powershell -Command \"Start-Process 'C:\\Program Files\\MetaTrader 5\\terminal64.exe'\"", shell=True, capture_output=True)
    time.sleep(25)

def write_json(ea, sym):
    with open(os.path.join(COMMON, 'open_chart_cmd.json'), 'w', encoding='utf-8') as f:
        json.dump({'symbol': sym, 'tf': 'H1', 'ea': ea, 'tpl': f'{ea}_{sym}_H1.tpl'}, f)

def gen_tpl(ea, sym):
    """生成模板（改 symbol + path）"""
    tdir = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Profiles\Templates'
    src = os.path.join(tdir, f'{ea}_EURUSD_H1.tpl')
    dst = os.path.join(tdir, f'{ea}_{sym}_H1.tpl')
    if os.path.isfile(src) and not os.path.isfile(dst):
        c = open(src, encoding='utf-16-le', errors='ignore').read()
        c = c.replace('symbol=EURUSD', f'symbol={sym}')
        c = c.replace(f'path=Experts\\{ea}.ex5', f'path=Experts\\MT5Cloud_EA\\{ea}.ex5')
        open(dst, 'w', encoding='utf-16-le').write(c)

def deploy(ea, sym):
    """一體化部署：開圖表 → Ctrl+9 → 套模板掛 EA"""
    write_json(ea, sym)
    gen_tpl(ea, sym)
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        from pywinauto import Application
        out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True, text=True).stdout
        pid = None
        for line in out.splitlines():
            p = [x.strip().strip('"') for x in line.split(',')]
            if len(p) >= 2 and p[0] == 'terminal64.exe' and p[1].isdigit():
                pid = int(p[1]); break
        if not pid:
            return False, 'MT5 未開'
        app = Application(backend='win32').connect(process=pid, timeout=8)
        win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
        import ctypes as ct
        u = ct.windll.user32
        u.SetForegroundWindow(ct.c_void_p(int(win.element_info.handle)))
        time.sleep(1)
        # 開空圖表
        pyautogui.hotkey('alt', 'f'); time.sleep(1.2)
        pyautogui.press('enter'); time.sleep(1.2)
        pyautogui.press('enter'); time.sleep(2.5)
        # focus 圖表
        r = win.rectangle()
        pyautogui.click(r.left + r.width() // 2, r.top + r.height() // 2)
        time.sleep(0.8)
        # Ctrl+9 → OpenChart script
        pyautogui.hotkey('ctrl', '9')
        time.sleep(5)
        # 驗證 log
        log_files = sorted(glob.glob(os.path.join(LOG_DIR, '2026*.log')), key=os.path.getmtime, reverse=True)
        if log_files:
            c = open(log_files[0], encoding='utf-16-le', errors='ignore').read()
            if '已開新圖表' in c and sym in c and ea in c:
                return True, 'log 確認'
            return False, 'log 冇確認'
        return False, '冇 log'
    except Exception as e:
        return False, str(e)

def verify_ea(ea, sym):
    """驗證 EA 掛咗（心跳 + log）"""
    # 心跳
    sp = os.path.join(COMMON, f'state_{ea}.json')
    hb_ok = False
    if os.path.isfile(sp):
        if time.time() - os.path.getmtime(sp) < 120:
            hb_ok = True
    # log
    log_ok = False
    log_files = sorted(glob.glob(os.path.join(LOG_DIR, '2026*.log')), key=os.path.getmtime, reverse=True)
    if log_files:
        c = open(log_files[0], encoding='utf-16-le', errors='ignore').read()
        if ea in c and sym in c and '已啟動' in c:
            log_ok = True
    return hb_ok or log_ok, {'heartbeat': hb_ok, 'log': log_ok}

# ============ MAIN ============
print('login:', login())

# 每輪組合（數量遞增）
ROUNDS = [
    [('EMA_Cross', 'EURUSD')],
    [('Breakout', 'GBPUSD'), ('RSI_Over', 'USDJPY')],
    [('MACD_Cross', 'AUDUSD'), ('Bollinger_Band', 'USDCHF'), ('Parabolic_SAR', 'USDJPY')],
    [('EMA_Cross', 'GBPUSD'), ('Breakout', 'USDJPY')],
    [('RSI_Over', 'EURUSD'), ('MACD_Cross', 'GBPUSD'), ('Bollinger_Band', 'USDJPY')],
]

results = []
for ri, round_eas in enumerate(ROUNDS, 1):
    print(f'\n{"="*50}\n🏁 第 {ri}/{len(ROUNDS)} 輪 — {[e for e,_ in round_eas]}')
    # 1. 清圖表 + 剸除所有 EA
    n = close_all_charts()
    print(f'  關圖表: {n} 個')
    rem = remove_all_eas()
    print(f'  剸除: {len(rem)} 個本機 EA')
    # 重啟 MT5（清熱鍵後 reload）
    if ri > 1:
        print('  重啟 MT5...')
        restart_mt5()
    # 2. 添加 EA
    for ea, _ in round_eas:
        r = install_ea(ea)
        print(f'  添加: {r}')
    # 重啟 MT5（reload 全部熱鍵 + scripts）
    print('  重啟 MT5（load 熱鍵 + scripts Ctrl+9）...')
    restart_mt5()
    # 3. 部署（逐個 — 一體化）
    round_ok = True
    for ea, sym in round_eas:
        ok, msg = deploy(ea, sym)
        print(f'  部署 {ea}→{sym}: {"✅" if ok else "❌"} ({msg})')
        if not ok:
            round_ok = False
    # 4. 驗證
    time.sleep(3)
    for ea, sym in round_eas:
        ok2, detail = verify_ea(ea, sym)
        print(f'  驗證 {ea}: {"✅" if ok2 else "❌"} {detail}')
        if not ok2:
            round_ok = False
    results.append((ri, round_ok, len(round_eas)))
    print(f'  第 {ri} 輪: {"✅ 成功" if round_ok else "❌ 失敗"}')

print(f'\n{"="*50}\n📊 壓力測試總結: {sum(1 for _,ok,_ in results if ok)}/{len(ROUNDS)} 輪完整成功')
