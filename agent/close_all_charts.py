"""Clear all open MT5 charts (close MDI children) to remove duplicates."""
import sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pywinauto import Application
from pywinauto.keyboard import send_keys
import ctypes

mt5_pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
if not mt5_pid:
    # find terminal64
    import subprocess
    out = subprocess.check_output('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV', shell=True, text=True)
    for line in out.splitlines()[1:]:
        if 'terminal64.exe' in line:
            mt5_pid = int(line.split(',')[1].strip('"'))
            break

print(f"MT5 pid={mt5_pid}")
app = Application(backend='win32').connect(process=mt5_pid)
win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
try:
    win.set_focus()
except Exception:
    pass
time.sleep(0.5)

mdi = None
for d in win.descendants():
    if d.element_info.class_name == 'MDIClient':
        mdi = d
        break
if not mdi:
    print("no MDI")
    sys.exit(0)

existing = list(mdi.children())
print(f"closing {len(existing)} charts...")
for ch in existing:
    try:
        ch.set_focus()
        time.sleep(0.3)
        send_keys('^{F4}')
        time.sleep(0.5)
    except Exception as e:
        print("err", e)
# verify
mdi2 = None
for d in win.descendants():
    if d.element_info.class_name == 'MDIClient':
        mdi2 = d
        break
print(f"remaining charts: {len(mdi2.children()) if mdi2 else 0}")
print("done")
