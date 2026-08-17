# -*- coding: utf-8 -*-
"""🚀 打字方式開圖表 — 示範（2026-08-15 用戶要求）
方法：Alt+F → Enter（Symbols dialog）→ Ctrl+A 全選 → 打字 symbol → Enter（揀中）→ Enter（開圖表）
"""
import sys, time, subprocess
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from pywinauto import Application
from pywinauto.keyboard import send_keys

# 1. 攞 MT5 PID
pid = None
out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True).stdout
for line in out.splitlines():
    if isinstance(line, bytes):
        line = line.decode('utf-8', errors='replace')
    parts = [p.strip().strip('"') for p in line.split(',')]
    if len(parts) >= 2 and parts[0] == 'terminal64.exe' and str(parts[1]).isdigit():
        pid = int(parts[1])
        break
if not pid:
    print('❌ MT5 未開')
    sys.exit(1)
print(f'✅ MT5 PID={pid}')

# 2. 連接 + 帶到最前
app = Application(backend='win32').connect(process=pid)
win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
win.set_focus()
time.sleep(1)

# 3. Alt+F → Enter（Symbols dialog）
print('⏳ Alt+F → Enter（新圖表 dialog）...')
send_keys('%f')
time.sleep(1.5)
send_keys('{ENTER}')
time.sleep(2)

# 4. 打字方式揀 symbol
print('⏳ Ctrl+A 全選 → 打字 EURUSD → Enter → Enter ...')
send_keys('^a')          # 全選（清空現有）
time.sleep(0.8)
send_keys('NZDUSD')      # 打字 symbol
time.sleep(2)
send_keys('{ENTER}')     # 揀中（自動完成）
time.sleep(1.5)
send_keys('{ENTER}')     # 開圖表
time.sleep(3)
print('✅ 已開圖表（打字方式 — NZDUSD）')

# 5. 驗證圖表標題
try:
    import ctypes
    u = ctypes.windll.user32
    titles = []
    def _cb(hwnd, _):
        if u.IsWindowVisible(hwnd):
            ln = u.GetWindowTextLengthW(hwnd)
            if ln > 0:
                buf = ctypes.create_unicode_buffer(ln + 1)
                u.GetWindowTextW(hwnd, buf, ln + 1)
                t = buf.value
                if 'NZDUSD' in t and (',' in t):
                    titles.append(t)
        return True
    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_cb), None)
    if titles:
        print(f'✅ 圖表標題驗證: {titles[:3]}')
    else:
        print('⚠️ 圖表標題未搵到（可能 dialog 未關 / 開錯）')
except Exception as e:
    print(f'⚠️ 驗證異常: {e}')
