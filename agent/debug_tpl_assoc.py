"""Debug: check .tpl file association."""
import os, time, ctypes, subprocess

user32 = ctypes.windll.user32

APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')

tpl_path = os.path.join(TPL_DIR, 'ADX_Trend_EURUSD_H1.tpl')
print(f"Template: {tpl_path}")
print(f"Exists: {os.path.exists(tpl_path)}")

# Check file association using registry (no encoding issues)
print("\n--- Checking .tpl file association via reg ---")
result = subprocess.run(['reg', 'query', 'HKEY_CLASSES_ROOT\\.tpl', '/ve'], 
                        capture_output=True, timeout=5)
if result.returncode == 0:
    print(f"reg result: {result.stdout.decode('utf-8', errors='replace').strip()}")
else:
    print(f"reg failed: {result.stderr.decode('utf-8', errors='replace').strip()}")

# Get the default value
result2 = subprocess.run(['reg', 'query', 'HKEY_CLASSES_ROOT\\.tpl', '/ve'], 
                        capture_output=True, timeout=5)
if result2.returncode == 0:
    lines = result2.stdout.decode('utf-8', errors='replace').split('\n')
    for line in lines:
        if 'REG_SZ' in line or 'REG_EXPAND_SZ' in line:
            parts = line.strip().split('REG_SZ')
            if len(parts) > 1:
                assoc = parts[-1].strip()
                print(f"  .tpl -> {assoc}")
                
                # Check the association
                result3 = subprocess.run(['reg', 'query', f'HKEY_CLASSES_ROOT\\{assoc}\\shell\\open\\command', '/ve'],
                                        capture_output=True, timeout=5)
                if result3.returncode == 0:
                    cmd = result3.stdout.decode('utf-8', errors='replace').strip()
                    print(f"  open command: {cmd[:200]}")

# Check MT5 window state
print("\n--- MT5 State ---")
main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
if main_hwnd:
    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(ctypes.c_void_p(main_hwnd), title, 512)
    print(f"MT5 title: \"{title.value}\"")
    
    # Check for dialogs
    import psutil
    mt5_pid = None
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            mt5_pid = proc.info['pid']
            break
    
    if mt5_pid:
        CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
        pid_buf = ctypes.c_ulong()
        dialogs = []
        def cb(hwnd, _):
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
        user32.EnumWindows(CB(cb), 0)
        if dialogs:
            print(f"Dialogs: {[t for h,t in dialogs]}")
        else:
            print("No dialogs open")
        
        # Check for chart windows (MDIClient / child windows)
        print("\nVisible windows by class:")
        visible_windows = set()
        def enum_all(hwnd, _):
            user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
            if pid_buf.value == mt5_pid:
                if user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
                    cls = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                    t = ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(ctypes.c_void_p(hwnd), t, 256)
                    visible_windows.add((cls.value, t.value))
            return True
        user32.EnumWindows(CB(enum_all), 0)
        for cls, t in sorted(visible_windows, key=lambda x: x[1]):
            print(f"  '{t}' [{cls}]")
