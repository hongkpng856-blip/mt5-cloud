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
if not pid:
    print('MT5 未開')
else:
    app = Application(backend='win32').connect(process=pid, timeout=8)
    # 主視窗帶最前（快捷鍵需要 active）
    for w in app.windows():
        try:
            if w.class_name() == 'MetaQuotes::MetaTrader::5.00':
                w.set_focus()
                time.sleep(1)
                break
        except Exception:
            pass
    # 關熱鍵 dialog（如果有）
    import ctypes
    user32 = ctypes.windll.user32
    for w in app.windows():
        try:
            if '熱鍵' in w.window_text():
                user32.PostMessageW(ctypes.c_void_p(int(w.element_info.handle)), 0x0010, 0, 0)
                time.sleep(1)
        except Exception:
            pass
    # send Ctrl+1（Bollinger_Band 快捷鍵）
    print('send Ctrl+1...')
    send_keys('^1')
    time.sleep(4)
    print('已 send')
    # 檢查 Properties dialog（Bollinger）
    for w in app.windows():
        try:
            if w.class_name() == '#32770':
                print(f'Dialog: [{w.window_text()[:45]}]')
        except Exception:
            pass
    out2 = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
    print(f'MT5 仲生: {b"terminal64" in out2.stdout}')
