# 試 Market Watch right-click → 「圖表窗口」（鍵盤 'c'）
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

print(f'開始: {chart_count()} 圖表')
# right-click 市場報價第一行
for w in app.windows():
    try:
        if '市場報價' in w.window_text():
            r = w.rectangle()
            pyautogui.rightClick(r.left + 60, r.top + 25)
            time.sleep(2)
            break
    except Exception:
        pass
# 試 send 'c'（圖表窗口）
send_keys('c')
time.sleep(3)
print(f"send 'c': {chart_count()} 圖表")
# 如果冇 — 試 't'（或其它）
send_keys('t')
time.sleep(3)
print(f"send 't': {chart_count()} 圖表")
