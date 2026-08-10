import sys, subprocess, time
sys.path.insert(0, 'agent')
from pywinauto import Application

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
            lv = dw.child_window(class_name='SysListView32')
            # 試 ensure_visible + 雙擊
            try:
                item = lv.get_item(28)
                item.ensure_visible()
                time.sleep(1)
                print(f'item 28 ensure_visible OK: [{item.window_text()[:40]}]')
            except Exception as e:
                print(f'ensure: {e}')
            try:
                item.double_click()
                print('double_click OK')
                time.sleep(2.5)
            except Exception as e:
                print(f'dblclick: {e}')
            break
    except Exception:
        pass

# 檢查新 MT5 dialog
for w in app.windows():
    try:
        t = w.window_text()
        if w.class_name() == '#32770' and t.strip() and '熱鍵' not in t:
            print(f'MT5 Dialog: [{t[:45]}]')
    except Exception:
        pass
