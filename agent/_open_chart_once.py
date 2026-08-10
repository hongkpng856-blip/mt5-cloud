# Navigator double-click OpenChart（開 1 個圖表就停 — 讀 open_chart_cmd.json 指定 symbol）
import sys, subprocess, time, ctypes
sys.path.insert(0, 'agent')
import pyautogui
pyautogui.FAILSAFE = False
from pywinauto import Application
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

# Navigator（左邊）
nav = None
for w in app.windows():
    try:
        if '導航' in w.window_text() or 'Navigator' in w.window_text():
            nav = w
            break
    except Exception:
        pass
if not nav:
    print('❌ 搵唔到 Navigator')
    sys.exit(1)
r = nav.rectangle()
print(f'Navigator: {r}')

before = chart_count()
print(f'開始: {before} 圖表')
# scan Navigator（由頂至底 — double-click — 開到圖表就停）
found = False
for y in range(r.top + 30, r.bottom - 30, 22):
    pyautogui.doubleClick(r.left + 60, y)
    time.sleep(2)
    c = chart_count()
    if c > before:
        print(f'🎯 開咗圖表！y={y} → {c}')
        found = True
        break
if not found:
    print('⚠️ 冇開到圖表（scan 完）')
print(f'最後: {chart_count()} 圖表')
