import sys, subprocess, time
sys.path.insert(0, 'agent')
import pyautogui
pyautogui.FAILSAFE = False
from pywinauto import Application
from pywinauto.keyboard import send_keys

out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
lines = out.stdout.decode('utf-8', errors='replace').strip().splitlines()
pid = None
for line in lines:
    parts = [p.strip().strip('"') for p in line.split(',')]
    if len(parts) >= 2 and parts[0] == 'terminal64.exe' and parts[1].isdigit():
        pid = int(parts[1])
        break
print(f'MT5 PID: {pid}')
app = Application(backend='win32').connect(process=pid, timeout=8)

# 開熱鍵視窗（右擊 Navigator 空白 → h）
tree_view = None
best_area = 0
for w in app.windows():
    try:
        for child in w.descendants():
            if child.element_info.class_name == 'SysTreeView32':
                try:
                    tr = child.rectangle()
                    if tr.width() > 50 and tr.height() > 50:
                        a = tr.width() * tr.height()
                        if a > best_area:
                            best_area = a
                            tree_view = child
                except Exception:
                    pass
    except Exception:
        pass
if tree_view:
    tr = tree_view.rectangle()
    print(f'tree: {tr}')
    pyautogui.rightClick(tr.left + 150, tr.bottom - 40)
    time.sleep(2)
    send_keys('h')
    time.sleep(2.5)

# 讀熱鍵視窗 ListView（搵 Bollinger/Divergence/Heikin）
for w in app.windows():
    try:
        if '熱鍵' in w.window_text():
            dw = app.window(handle=int(w.element_info.handle))
            lv = dw.child_window(class_name='SysListView32')
            items = lv.texts()
            print(f'items: {len(items)}')
            for i, t in enumerate(items):
                ts = str(t)
                if any(k in ts for k in ('Bollinger', 'Divergence', 'Heikin', 'SMA')):
                    print(f'  row {i}: [{ts[:60]}]')
            break
    except Exception:
        pass
