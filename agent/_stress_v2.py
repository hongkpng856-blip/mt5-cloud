# -*- coding: utf-8 -*-
# 壓力測試 2026-08-17 — 用 auto_attach.attach_ea_hotkey（完整一體化邏輯）做 5 輪部署
# 每輪：清圖表 → 剸除全部 → 添加 N 個 EA → attach_ea_hotkey(open_chart=True, symbol) → 驗證 MT5 log
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

def close_all_charts():
    import pyautogui
    pyautogui.FAILSAFE = False
    from pywinauto import Application
    out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True, text=True).stdout
    pid = None
    for line in out.splitlines():
        p = [x.strip().strip('"') for x in line.split(',')]
        if len(p) >= 2 and p[0] == 'terminal64.exe' and p[1].isdigit():
            pid = int(p[1]); break
    if not pid: return 0
    app = Application(backend='win32').connect(process=pid, timeout=8)
    win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
    import ctypes as ct
    u = ct.windll.user32
    u.SetForegroundWindow(ct.c_void_p(int(win.element_info.handle)))
    time.sleep(1)
    n = 0
    try:
        for d in win.descendants():
            if d.element_info.class_name == 'MDIClient':
                n = len(d.children()); break
    except Exception:
        pass
    for _ in range(min(n, 15)):
        pyautogui.hotkey('ctrl', 'w'); time.sleep(0.5)
    time.sleep(1)
    return n

def cleanup():
    """剸除所有 EA 檔案 + 熱鍵 + 模板（保留 scripts Ctrl+9 — 用 utf-16 BOM）"""
    n = 0
    for f in os.listdir(EA_DIR):
        if f.endswith(('.ex5', '.mq5')) and f != 'OpenChart_Helper.mq5':
            try:
                os.remove(os.path.join(EA_DIR, f)); n += 1
            except Exception: pass
    # 清模板
    for f in os.listdir(TDIR) if os.path.isdir(TDIR) else []:
        if any(e in f for e in TARGETS) and f.endswith('.tpl'):
            try: os.remove(os.path.join(TDIR, f))
            except Exception: pass
    # 清熱鍵（保留 scripts Ctrl+9 — 寫返 utf-16 BOM）
    try:
        with open(HOTKEYS, 'wb') as f:
            f.write(b'\xff\xfe')
            f.write('<scripts>\r\nScripts\\OpenChart.ex5=Ctrl+9\r\n</scripts>'.encode('utf-16-le'))
    except Exception: pass
    return n

def install_ea(ea):
    """複製 + 編譯 + 加熱鍵（utf-16 BOM）"""
    shutil.copy(os.path.join(EA_LIB, f'{ea}.mq5'), os.path.join(EA_DIR, f'{ea}.mq5'))
    try:
        subprocess.run([r'C:\Program Files\MetaTrader 5\MetaEditor64.exe', f'/compile:{os.path.join(EA_DIR, ea)}.mq5', '/log'], timeout=60)
        time.sleep(5)
    except Exception: pass
    # 熱鍵（避免 Ctrl+9 — 讀 utf-16 keep BOM）
    try:
        import re
        c = open(HOTKEYS, encoding='utf-16', errors='ignore').read()
        # 剝 BOM（utf-16 讀已剝）
        used = set(re.findall(r'=Ctrl\+(\d)', c))
        combo = next((f'Ctrl+{i}' for i in range(1, 9) if str(i) not in used), None)
        scripts_part = ''
        m2 = re.search(r'<scripts>.*?</scripts>', c, flags=re.S)
        if m2:
            scripts_part = m2.group(0)
        exp_line = f'Experts\\MT5Cloud_EA\\{ea}.ex5={combo}'
        if combo:
            new_c = f'<experts>\r\n{exp_line}\r\n</experts>\r\n{scripts_part}'
            with open(HOTKEYS, 'wb') as f:
                f.write(b'\xff\xfe')
                f.write(new_c.encode('utf-16-le'))
    except Exception: pass

def restart_mt5():
    subprocess.run('taskkill -f -im terminal64.exe', shell=True, capture_output=True)
    time.sleep(4)
    subprocess.run("powershell -Command \"Start-Process 'C:\\Program Files\\MetaTrader 5\\terminal64.exe'\"", shell=True, capture_output=True)
    time.sleep(25)

def latest_log():
    files = sorted(glob.glob(os.path.join(LOG_DIR, '2026*.log')), key=os.path.getmtime, reverse=True)
    return files[0] if files else None

ROUNDS = [
    [('EMA_Cross', 'EURUSD')],
    [('Breakout', 'GBPUSD'), ('RSI_Over', 'USDJPY')],
    [('MACD_Cross', 'AUDUSD'), ('Bollinger_Band', 'USDCHF'), ('Parabolic_SAR', 'USDJPY')],
    [('EMA_Cross', 'GBPUSD'), ('Breakout', 'USDJPY')],
    [('RSI_Over', 'EURUSD'), ('MACD_Cross', 'GBPUSD'), ('Bollinger_Band', 'USDJPY')],
]

results = []
for ri, round_eas in enumerate(ROUNDS, 1):
    print(f'\n{"="*55}\n🏁 第 {ri}/{len(ROUNDS)} 輪 — {[e for e,_ in round_eas]}', flush=True)
    # 1. 清圖表
    nc = close_all_charts()
    print(f'  關圖表: {nc} 個', flush=True)
    # 2. 剸除全部
    nr = cleanup()
    print(f'  剸除: {nr} 個本機 EA', flush=True)
    # 3. 添加 EA + 熱鍵
    for ea, _ in round_eas:
        install_ea(ea)
        print(f'  添加: {ea}', flush=True)
    # 4. 重啟 MT5
    print('  重啟 MT5（load 熱鍵 + scripts Ctrl+9）...', flush=True)
    restart_mt5()
    # 5. 部署（auto_attach 一體化）
    log_before = latest_log()
    round_ok = True
    for ea, sym in round_eas:
        # 攞 MT5 PID
        out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True, text=True).stdout
        pid = None
        for line in out.splitlines():
            p = [x.strip().strip('"') for x in line.split(',')]
            if len(p) >= 2 and p[0] == 'terminal64.exe' and p[1].isdigit():
                pid = int(p[1]); break
        try:
            ok = auto_attach.attach_ea_hotkey(ea, pid, symbol=sym, open_chart=True)
            msg = 'OK' if ok else 'FAIL'
        except Exception as e:
            ok, msg = False, str(e)[:60]
        # 驗證：log 有「已開新圖表 SYM」+ EA (SYM) 已啟動
        time.sleep(3)
        log_ok = False
        lf = latest_log()
        if lf:
            c = open(lf, encoding='utf-16-le', errors='ignore').read()
            log_ok = (f'{ea} ({sym},H1)' in c and '已啟動' in c)
        print(f'  部署 {ea}→{sym}: {"✅" if ok else "❌"}({msg}) log={"✅" if log_ok else "❌"}', flush=True)
        if not (ok and log_ok):
            round_ok = False
    results.append((ri, round_ok, len(round_eas)))
    print(f'  第 {ri} 輪: {"✅ 成功" if round_ok else "❌ 失敗"}', flush=True)

print(f'\n{"="*55}\n📊 壓力測試總結: {sum(1 for _,ok,_ in results if ok)}/{len(ROUNDS)} 輪完整成功')
