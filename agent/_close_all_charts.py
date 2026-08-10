# 剷除所有 MT5 圖表（Ctrl+W 逐個 — 直到冇圖表）
import sys, subprocess, time, ctypes
sys.path.insert(0, 'agent')
import pyautogui
pyautogui.FAILSAFE = False
from pywinauto import Application
from pywinauto.keyboard import send_keys
user32 = ctypes.windll.user32

out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
lines = out.stdout.decode('utf-8', errors='replace').strip().splitlines()
pid = None
for line in lines:
    parts = [p.strip().strip('"') for p in line.split(',')]
    if len(parts) >= 2 and parts[0] == 'terminal64.exe' and parts[1].isdigit():
        pid = int(parts[1]); break
app = Application(backend='win32').connect(process=pid, timeout=8)
win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
win.set_focus()
time.sleep(1)

def chart_count():
    count = 0
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    def cb(hwnd, _):
        nonlocal count
        cls = ctypes.create_unicode_buffer(60)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 60)
        if 'AfxFrameOrView' in cls.value:
            count += 1
        return True
    for w in app.windows():
        try:
            user32.EnumChildWindows(ctypes.c_void_p(int(w.element_info.handle)), cb, 0)
        except Exception:
            pass
    return count

n = chart_count()
print(f'開始: {n} 圖表')
for i in range(60):
    c = chart_count()
    if c == 0:
        print(f'✅ 全部圖表已關閉（{i} 次 Ctrl+W）')
        break
    # 確保圖表 active（click 圖表區）+ Ctrl+W
    r = win.rectangle()
    pyautogui.click((r.left + r.right) // 2, (r.top + r.bottom) // 2)
    time.sleep(0.5)
    send_keys('^w')
    time.sleep(1)
    if i % 10 == 0:
        print(f'  ...{c} 圖表剩餘')
else:
    print(f'⚠️ 60 次後仲有 {chart_count()} 圖表')
print(f'最後: {chart_count()} 圖表')
