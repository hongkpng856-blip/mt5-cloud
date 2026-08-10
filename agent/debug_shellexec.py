"""Debug ShellExecute - why doesn't opening .tpl trigger New Chart?"""
import os, time, ctypes, sys

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32

APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'D0E8209F77C8CF37AD8BF550E51FF075')
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')

tpl_path = os.path.join(TPL_DIR, 'ADX_Trend_EURUSD_H1.tpl')
print(f"Template exists: {os.path.exists(tpl_path)}")
print(f"Template path: {tpl_path}")

# Check .tpl file association
# Read the file to verify it's valid
with open(tpl_path, 'rb') as f:
    data = f.read()
print(f"File size: {len(data)} bytes")
print(f"BOM: {data[:4].hex()}")
print(f"First 200 chars: {data[:400].decode('utf-16-le', errors='replace')[:200]}")

# Try ShellExecuteW differently
print("\n--- Trying ShellExecuteW ---")
# Get associated executable for .tpl
# Use AssocQueryString to find the program
try:
    from ctypes import wintypes
    SHAssoc = ctypes.windll.shlwapi.AssocQueryStringW
    SHAssoc.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    
    flags = 0  # ASSOCF_INIT_DEFAULTTOSTAR
    assoc_str = 2  # ASSOCSTR_EXECUTABLE
    ext = '.tpl'
    buf = ctypes.create_unicode_buffer(512)
    bufsize = wintypes.DWORD(512)
    
    result = SHAssoc(flags, assoc_str, ext, None, buf, ctypes.byref(bufsize))
    if result == 0:  # S_OK
        print(f"Associated program for .tpl: {buf.value}")
    else:
        print(f"AssocQueryString failed: {result}")
except Exception as e:
    print(f"AssocQueryString error: {e}")

# Check registry for .tpl association
print("\n--- Checking registry ---")
import winreg
try:
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, '.tpl') as key:
        value, _ = winreg.QueryValueEx(key, '')
        print(f".tpl default value: '{value}'")
        
        # Check command
        cmd_key = f'{value}\\shell\\open\\command'
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, cmd_key) as cmd:
                cmd_val, _ = winreg.QueryValueEx(cmd, '')
                print(f"Open command: '{cmd_val}'")
        except:
            print(f"No command found at {cmd_key}")
except Exception as e:
    print(f"Registry error: {e}")

# Try ShellExecute with specific parameters
print("\n--- Trying ShellExecute with 'open' verb ---")
# Method 1: just path
result = shell32.ShellExecuteW(None, "open", tpl_path, None, None, 1)
print(f"ShellExecuteW(open): {result}")

# Check if a new window or dialog appeared
time.sleep(3)

# Check for any new dialogs in MT5
mt5_pid = None
import psutil
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
        mt5_pid = proc.info['pid']
        break

CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
pid_buf = ctypes.c_ulong()
dialogs = []
def find_dlg(hwnd, _):
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
    if pid_buf.value == mt5_pid:
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if cls.value == '#32770':
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
            if title.value:
                dialogs.append((hwnd, title.value))
    return True
user32.EnumWindows(CB(find_dlg), 0)
print(f"Dialogs after ShellExecute: {len(dialogs)}")
for h, t in dialogs:
    print(f"  {h:08X}: '{t}'")

# Also check MDIClient for charts
main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
if main_hwnd:
    mdi = user32.FindWindowExW(ctypes.c_void_p(main_hwnd), None, 'MDIClient', None)
    if mdi:
        chart_count = [0]
        def _count(h, _):
            chart_count[0] += 1
            return True
        user32.EnumChildWindows(ctypes.c_void_p(mdi), CB(_count), 0)
        print(f"MDIClient charts: {chart_count[0]}")

print("\nDone")
