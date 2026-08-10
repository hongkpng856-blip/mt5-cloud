import ctypes, subprocess, time
from ctypes import wintypes

user32 = ctypes.windll.user32
out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
lines = out.stdout.decode('utf-8', errors='replace').strip().splitlines()
pid = None
for line in lines:
    parts = [p.strip().strip('"') for p in line.split(',')]
    if len(parts) >= 2 and parts[0] == 'terminal64.exe' and parts[1].isdigit():
        pid = int(parts[1])
        break

from pywinauto import Application
app = Application(backend='win32').connect(process=pid, timeout=8)
for w in app.windows():
    try:
        if w.class_name() == '#32770' and w.window_text() == 'MetaTrader 5':
            dw = app.window(handle=int(w.element_info.handle))
            for b in dw.children(class_name='Button'):
                try:
                    if '是' in b.window_text() or 'Yes' in b.window_text():
                        b.click()
                        print('已撳「是」— 附加完成')
                        time.sleep(3)
                        break
                except Exception:
                    pass
            break
    except Exception:
        pass

# 檢查心跳（Bollinger_Band 有控制層 — 應該寫心跳）
import os
sf = os.path.join(os.environ['APPDATA'], 'MetaQuotes', 'Terminal', 'Common', 'Files', 'state_Bollinger_Band.json')
print(f'心跳: {open(sf).read() if os.path.isfile(sf) else "未有心跳（等 tick）"}')
