import subprocess, time
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
# 直接搵「導航熱鍵」dialog（所有 windows 包括 hidden）
for w in app.windows():
    try:
        t = w.window_text()
        if '熱鍵' in t:
            print(f'熱鍵 dialog: [{t}] rect={w.rectangle()}')
            for c in w.children():
                try:
                    print(f'  [{c.class_name()[:30]}] [{c.window_text()[:30]}] rect={c.rectangle()}')
                except Exception:
                    pass
            break
    except Exception:
        pass
