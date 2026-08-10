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

dlg = None
for w in app.windows():
    try:
        if '熱鍵' in w.window_text():
            dlg = w
            break
    except Exception:
        pass
if dlg:
    dw = app.window(handle=int(dlg.element_info.handle))
    dw.set_focus()
    time.sleep(1)
    lv = dw.child_window(class_name='SysListView32')
    # 1. click ListView（focus — 中間位置）
    lv_rect = lv.rectangle()
    pyautogui.click((lv_rect.left + lv_rect.right) // 2, (lv_rect.top + lv_rect.bottom) // 2)
    time.sleep(1)
    # 2. incremental search（打 Div）
    send_keys('Div')
    time.sleep(1.5)
    print('已 send Div（incremental search）')
    # 3. click 設定
    pyautogui.click(1457, 413)
    time.sleep(2.5)
    print('已 click 設定')
    # 4. 讀新 dialog
    for w in app.windows():
        try:
            t = w.window_text()
            if w.class_name() == '#32770' and t.strip() and '熱鍵' not in t:
                print(f'新 Dialog: [{t[:45]}]')
                dw2 = app.window(handle=int(w.element_info.handle))
                for c in dw2.children():
                    try:
                        print(f'  [{c.class_name()[:20]}] [{c.window_text()[:25]}] rect={c.rectangle()}')
                    except Exception:
                        pass
        except Exception:
            pass
