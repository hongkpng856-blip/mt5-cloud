# -*- coding: utf-8 -*-
"""測試：市場報價打字方式開圖表（Ctrl+M → focus Market Watch → 打字 symbol → 雙擊開圖表）"""
import sys, time, subprocess, ctypes
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pywinauto import Application
from pywinauto.keyboard import send_keys
import pyautogui
pyautogui.FAILSAFE = False

pid = None
out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True).stdout
for line in out.splitlines():
    if isinstance(line, bytes):
        line = line.decode('utf-8', errors='replace')
    parts = [p.strip().strip('"') for p in line.split(',')]
    if len(parts) >= 2 and parts[0] == 'terminal64.exe' and str(parts[1]).isdigit():
        pid = int(parts[1])
        break
print(f'MT5 PID={pid}')

app = Application(backend='win32').connect(process=pid)
win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
win.set_focus()
time.sleep(1)

# 1. Ctrl+M 開市場報價
send_keys('^m')
time.sleep(2)

# 2. 搵市場報價窗口
u = ctypes.windll.user32
mw = None
def cb(hwnd, _):
    global mw
    if u.IsWindowVisible(hwnd):
        ln = u.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(ln + 1)
        u.GetWindowTextW(hwnd, buf, ln + 1)
        t = buf.value
        if ('市場報價' in t or 'Market Watch' in t) and u.IsWindow(hwnd):
            mw = hwnd
            return False
    return True
u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(cb), None)
print(f'市場報價窗口: {mw}')

# 3. focus 市場報價 + 打字
if mw:
    mw_win = app.window(handle=mw)
    mw_win.set_focus()
    time.sleep(1)
else:
    # fallback: 主視窗 focus（Ctrl+M 後可能自動 focus）
    win.set_focus()
    time.sleep(1)

print('打字 XAUUSD ...')
send_keys('XAUUSD')
time.sleep(2)

# 4. 雙擊（市場報價列表第一項 — 揀中嘅 symbol）
try:
    if mw:
        r = mw_win.rectangle()
        cx = r.left + r.width() // 2
        cy = r.top + 30  # 列表第一行
        pyautogui.doubleClick(cx, cy)
        print(f'雙擊 ({cx},{cy})')
    else:
        # fallback: 主視窗中間雙擊
        r = win.rectangle()
        pyautogui.doubleClick(r.left + r.width() // 2, r.top + 200)
except Exception as e:
    print(f'雙擊失敗: {e}')

time.sleep(3)

# 5. 驗證圖表標題
titles = []
def cb2(hwnd, _):
    if u.IsWindowVisible(hwnd):
        ln = u.GetWindowTextLengthW(hwnd)
        if ln > 0 and ln < 200:
            buf = ctypes.create_unicode_buffer(ln + 1)
            u.GetWindowTextW(hwnd, buf, ln + 1)
            cls = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(hwnd, cls, 64)
            if 'MetaQuotes::MetaTrader' in cls.value:
                titles.append(buf.value)
    return True
u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(cb2), None)
print('圖表 tabs:')
for t in titles:
    print(f'  {t}')
