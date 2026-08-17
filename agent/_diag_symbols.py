# -*- coding: utf-8 -*-
"""診斷：MT5 Symbols dialog 結構（搵搜尋框 Edit control）"""
import sys, time, subprocess
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pywinauto import Application
from pywinauto.keyboard import send_keys

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

# 開 Symbols dialog（File → New Chart）
send_keys('%f')
time.sleep(1.5)
send_keys('{ENTER}')
time.sleep(2)

# 列出所有視窗 + controls
import ctypes
u = ctypes.windll.user32
def enum_windows():
    wins = []
    def cb(hwnd, _):
        if u.IsWindowVisible(hwnd):
            ln = u.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(ln + 1)
            u.GetWindowTextW(hwnd, buf, ln + 1)
            cls = ctypes.create_unicode_buffer(256)
            u.GetClassNameW(hwnd, cls, 256)
            wins.append((hwnd, buf.value[:60], cls.value))
        return True
    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(cb), None)
    return wins

for hwnd, title, cls in enum_windows():
    if 'Symbol' in title or '商品' in title or 'Market' in title or '報價' in title or 'Charts' in title or '圖表' in title or 'New' in title or '新' in title:
        print(f'  視窗: [{hwnd}] {title!r} class={cls}')
        try:
            dlg = app.window(handle=hwnd)
            for ctrl in dlg.children():
                try:
                    print(f'    control: {ctrl.friendly_class_name()} {ctrl.window_text()[:30]!r}')
                except Exception:
                    pass
        except Exception as e:
            print(f'    （讀 controls 失敗: {e}）')

# 關 dialog（ESC）
time.sleep(1)
send_keys('{ESC}')
print('done')
