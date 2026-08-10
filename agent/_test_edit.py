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
for w in app.windows():
    try:
        if '熱鍵' in w.window_text():
            dw = app.window(handle=int(w.element_info.handle))
            dw.set_focus()
            time.sleep(1)
            # Edit 欄清空 + 打 Div
            for c in dw.children():
                if c.class_name() == 'Edit':
                    r = c.rectangle()
                    pyautogui.click((r.left + r.right) // 2, (r.top + r.bottom) // 2)
                    time.sleep(0.8)
                    send_keys('^a{DELETE}')  # 清空
                    time.sleep(0.5)
                    send_keys('Div')
                    time.sleep(1.5)
                    print(f'已打 Div — Edit: [{c.window_text()}]')
                    break
            # ListView 有冇變（filter？）
            lv = dw.child_window(class_name='SysListView32')
            try:
                items = lv.texts()
                print(f'ListView items: {len(items)}')
                for i, t in enumerate(items[:5]):
                    print(f'  row {i}: [{str(t)[:40]}]')
            except Exception as e:
                print(f'lv: {e}')
            break
    except Exception:
        pass
