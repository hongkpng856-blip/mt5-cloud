# -*- coding: utf-8 -*-
# 壓力測試 2026-08-18 — v0.9.57 新方案（用戶 08-10 定案）
# 開圖表 = Alt+F → Enter → Down×N → Enter（唔使 script 熱鍵）
# 掛 EA = <experts> 熱鍵（Ctrl+1/2/3... — 已證 work）
# 唔使 Ctrl+9 / 唔使 OpenChart script / 唔使每次重啟 MT5
# 每輪：清圖表 → 剸除全部 → 添加 N 個 EA（含熱鍵）→ 部署 → 驗證 MT5 active 圖表標題
import sys, os, time, json, glob, subprocess, shutil
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:\Users\hongk\Desktop\mt5-cloud\agent')
import auto_attach

EA_LIB = r'C:\Users\hongk\Desktop\mt5-cloud\server\static\ea_library'
EA_DIR = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\MT5Cloud_EA'
LOG_DIR = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Logs'
COMMON = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\Common\Files'
HOTKEYS = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\config\hotkeys.ini'
TDIR = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Profiles\Templates'

TARGETS = ['EMA_Cross', 'Breakout', 'RSI_Over', 'MACD_Cross', 'Bollinger_Band', 'Parabolic_SAR']
SYMBOLS = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCHF']

def get_mt5_pid():
    out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True, text=True).stdout
    for line in out.splitlines():
        p = [x.strip().strip('"') for x in line.split(',')]
        if len(p) >= 2 and p[0] == 'terminal64.exe' and p[1].isdigit():
            return int(p[1])
    return None

def close_all_charts():
    import pyautogui
    pyautogui.FAILSAFE = False
    from pywinauto import Application
    pid = get_mt5_pid()
    if not pid: return 0
    try:
        app = Application(backend='win32').connect(process=pid, timeout=8)
        win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
        import ctypes as ct
        u = ct.windll.user32
        u.SetForegroundWindow(ct.c_void_p(int(win.element_info.handle)))
        time.sleep(1)
        n = 0
        for d in win.descendants():
            if d.element_info.class_name == 'MDIClient':
                n = len(d.children()); break
        for _ in range(min(n, 15)):
            pyautogui.hotkey('ctrl', 'w'); time.sleep(0.5)
        time.sleep(1)
        return n
    except Exception:
        return 0

def cleanup():
    """剸除所有 EA 檔案 + 熱鍵 + 模板（新方案：hotkeys.ini 只留空 <experts>）"""
    n = 0
    for f in os.listdir(EA_DIR):
        if f.endswith(('.ex5', '.mq5')):
            try:
                os.remove(os.path.join(EA_DIR, f)); n += 1
            except Exception: pass
    for f in os.listdir(TDIR) if os.path.isdir(TDIR) else []:
        if any(e in f for e in TARGETS) and f.endswith('.tpl'):
            try: os.remove(os.path.join(TDIR, f))
            except Exception: pass
    # 清熱鍵（新方案唔使 <scripts> — 留空 <experts>）
    try:
        with open(HOTKEYS, 'wb') as f:
            f.write(b'\xff\xfe')
            f.write('<experts>\r\n</experts>'.encode('utf-16-le'))
    except Exception: pass
    return n

def install_ea(ea):
    """複製 + 編譯 + 加熱鍵（<experts> 段，utf-16 BOM）"""
    shutil.copy(os.path.join(EA_LIB, f'{ea}.mq5'), os.path.join(EA_DIR, f'{ea}.mq5'))
    try:
        subprocess.run([r'C:\Program Files\MetaTrader 5\MetaEditor64.exe', f'/compile:{os.path.join(EA_DIR, ea)}.mq5', '/log'], timeout=60)
        time.sleep(5)
    except Exception: pass
    # 熱鍵（<experts> — 唔使 Ctrl+9 / 唔使 <scripts>）
    try:
        import re
        c = open(HOTKEYS, encoding='utf-16', errors='ignore').read()
        used = set(re.findall(r'=Ctrl\+(\d)', c))
        combo = next((f'Ctrl+{i}' for i in range(1, 9) if str(i) not in used), None)
        exp_line = f'Experts\\MT5Cloud_EA\\{ea}.ex5={combo}'
        if combo:
            # 保留現有 experts 行 + 加新
            m = re.search(r'<experts>.*?</experts>', c, flags=re.S)
            if m:
                block = m.group(0).replace('</experts>', f'{exp_line}\r\n</experts>')
                c = c[:m.start()] + block + c[m.end():]
            else:
                c = f'<experts>\r\n{exp_line}\r\n</experts>\r\n' + c
            with open(HOTKEYS, 'wb') as f:
                f.write(b'\xff\xfe')
                f.write(c.encode('utf-16-le'))
    except Exception: pass

def restart_mt5():
    subprocess.run('taskkill -f -im terminal64.exe', shell=True, capture_output=True)
    time.sleep(4)
    subprocess.run("powershell -Command \"Start-Process 'C:\\Program Files\\MetaTrader 5\\terminal64.exe'\"", shell=True, capture_output=True)
    time.sleep(25)

def active_chart_has(sym):
    """驗證 MT5 active 圖表標題含 symbol（開圖表成功 = 目標 symbol 圖表 active）"""
    import ctypes as ct
    u = ct.windll.user32
    found = {'v': False}
    @ct.WINFUNCTYPE(ct.c_bool, ct.c_size_t, ct.c_size_t)
    def cb(hwnd, _):
        if u.IsWindowVisible(ct.c_void_p(hwnd)):
            cls = ct.create_unicode_buffer(80)
            u.GetClassNameW(ct.c_void_p(hwnd), cls, 80)
            if 'Chart' in cls.value or 'MetaTrader' in cls.value:
                l = u.GetWindowTextLengthW(ct.c_void_p(hwnd))
                if l > 0:
                    buf = ct.create_unicode_buffer(l + 1)
                    u.GetWindowTextW(ct.c_void_p(hwnd), buf, l + 1)
                    if sym in buf.value:
                        found['v'] = True
                        return False
        return True
    u.EnumWindows(cb, None)
    return found['v']

ROUNDS = [
    [('EMA_Cross', 'EURUSD')],
    [('Breakout', 'GBPUSD'), ('RSI_Over', 'USDJPY')],
    [('MACD_Cross', 'AUDUSD'), ('Bollinger_Band', 'USDCHF'), ('Parabolic_SAR', 'USDJPY')],
    [('EMA_Cross', 'GBPUSD'), ('Breakout', 'USDJPY')],
    [('RSI_Over', 'EURUSD'), ('MACD_Cross', 'GBPUSD'), ('Bollinger_Band', 'USDJPY')],
]

results = []
restart_done = False
for ri, round_eas in enumerate(ROUNDS, 1):
    print(f'\n{"=" * 55}\n🏁 第 {ri}/{len(ROUNDS)} 輪 — {[e for e, _ in round_eas]}', flush=True)
    nc = close_all_charts()
    print(f'  關圖表: {nc} 個', flush=True)
    nr = cleanup()
    print(f'  剸除: {nr} 個本機 EA', flush=True)
    for ea, _ in round_eas:
        install_ea(ea)
        print(f'  添加: {ea}', flush=True)
    # 第一次輪重啟 MT5 load 熱鍵（唔使 Ctrl+9；只 load <experts> 熱鍵）
    if not restart_done:
        print('  重啟 MT5（load <experts> 熱鍵）...', flush=True)
        restart_mt5()
        restart_done = True
    round_ok = True
    for ea, sym in round_eas:
        pid = get_mt5_pid()
        try:
            ok = auto_attach.attach_ea_hotkey(ea, pid, symbol=sym, open_chart=True)
            msg = 'OK' if ok else 'FAIL'
        except Exception as e:
            ok, msg = False, str(e)[:60]
        time.sleep(3)
        chart_ok = active_chart_has(sym)
        print(f'  部署 {ea}→{sym}: {"✅" if ok else "❌"}({msg}) 圖表={sym}={"✅" if chart_ok else "❌"}', flush=True)
        if not (ok and chart_ok):
            round_ok = False
    results.append((ri, round_ok, len(round_eas)))
    print(f'  第 {ri} 輪: {"✅ 成功" if round_ok else "❌ 失敗"}', flush=True)

print(f'\n{"=" * 55}\n📊 壓力測試總結: {sum(1 for _, ok, _ in results if ok)}/{len(ROUNDS)} 輪完整成功')
