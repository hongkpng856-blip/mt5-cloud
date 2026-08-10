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

app = Application(backend='win32').connect(process=pid, timeout=8)

# 熱鍵視窗（已經開住 — 搵返）
dlg = None
for w in app.windows():
    try:
        if '熱鍵' in w.window_text():
            dlg = w
            break
    except Exception:
        pass
if not dlg:
    print('熱鍵視窗未開')
else:
    dw = app.window(handle=int(dlg.element_info.handle))
    # 帶最前
    dw.set_focus()
    time.sleep(1)
    lv = dw.child_window(class_name='SysListView32')
    # select Divergence（row 235）
    try:
        lv.select(235)
        print('select Divergence OK')
        time.sleep(1)
    except Exception as e:
        print(f'select fail: {e}')
    # 真 click「設定」按鈕（(1412,402)-(1502,425) 中心 1457,413）
    pyautogui.click(1457, 413)
    time.sleep(2.5)
    print('已 click 設定')
    # 檢查設定 dialog（「設定」/快捷鍵輸入）
    import ctypes
    user32 = ctypes.windll.user32
    for w in app.windows():
        try:
            t = w.window_text()
            if w.class_name() == '#32770' and t.strip() and '熱鍵' not in t:
                print(f'新 Dialog: [{t[:45]}]')
                # 讀結構
                dw2 = app.window(handle=int(w.element_info.handle))
                for c in dw2.children():
                    try:
                        print(f'  [{c.class_name()[:20]}] [{c.window_text()[:25]}] rect={c.rectangle()}')
                    except Exception:
                        pass
        except Exception:
            pass
