import ctypes, subprocess
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
        if w.class_name() == '#32770':
            t = w.window_text()
            print(f'Dialog: [{t}] rect={w.rectangle()}')
            dw = app.window(handle=int(w.element_info.handle))
            for c in dw.children():
                try:
                    print(f'  [{c.class_name()[:20]}] [{c.window_text()[:50]}]')
                except Exception:
                    pass
    except Exception:
        pass
