import sys, subprocess, time
sys.path.insert(0, 'agent')
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
if pid:
    app = Application(backend='win32').connect(process=pid, timeout=8)
    for w in app.windows():
        try:
            if w.class_name() == 'MetaQuotes::MetaTrader::5.00':
                w.set_focus()
                time.sleep(1)
                break
        except Exception:
            pass
    print('send Ctrl+2（SMA_Cross）...')
    send_keys('^2')
    time.sleep(3.5)
    for w in app.windows():
        try:
            if w.class_name() == '#32770':
                print(f'Dialog: [{w.window_text()[:50]}]')
        except Exception:
            pass
    out2 = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
    print(f'MT5 仲生: {b"terminal64" in out2.stdout}')
