"""Interact with the 'New' dialog that appeared."""
import os, time, ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

import psutil
mt5_pid = None
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
        mt5_pid = proc.info['pid']
        break

print(f"MT5 PID: {mt5_pid}")

if not mt5_pid:
    exit()

pid_buf = ctypes.c_ulong()

# Find all dialogs
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
                rect = wintypes.RECT()
                user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
                dialogs.append((hwnd, cls.value, title.value, rect))
    return True
user32.EnumWindows(CB(cb), 0)

print(f"Found {len(dialogs)} dialogs:")
for hwnd, cls, title, rect in dialogs:
    print(f"  0x{hwnd:08X}: '{title}' at ({rect.left},{rect.top})-({rect.right},{rect.bottom})")

# The "New" dialog is likely the New Chart dialog
# Let's interact with it
new_dlg = None
print_hwnd = None
for hwnd, cls, title, rect in dialogs:
    if title == 'New' or '新圖' in title or 'New' in title:
        new_dlg = hwnd
    if 'Print' in title or '設定列印' in title or 'Print Setup' in title:
        print_hwnd = hwnd

# Close print setup first
if print_hwnd:
    print(f"\nClosing Print Setup dialog: 0x{print_hwnd:08X}")
    user32.SendMessageW(ctypes.c_void_p(print_hwnd), 0x0010, 0, 0)  # WM_CLOSE
    time.sleep(1)

if new_dlg:
    print(f"\nFound 'New' dialog: 0x{new_dlg:08X}")
    
    # Enumerate child windows of the dialog
    children = []
    def enum_child(hwnd, _):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
        children.append((hwnd, cls.value, title.value, rect))
        return True
    user32.EnumChildWindows(ctypes.c_void_p(new_dlg), CB(enum_child), 0)
    
    print(f"  Child windows ({len(children)}):")
    for hwnd, cls, title, rect in children:
        print(f"    0x{hwnd:08X}: class='{cls}' title='{title}' rect=({rect.left},{rect.top})-({rect.right},{rect.bottom})")
    
    # Find Edit control for symbol entry, or ComboBox
    edit_hwnd = None
    combo_hwnd = None
    for hwnd, cls, title, rect in children:
        if cls == 'Edit':
            edit_hwnd = hwnd
            print(f"  Edit control found: 0x{hwnd:08X}")
        if cls == 'ComboBox':
            combo_hwnd = hwnd
            print(f"  ComboBox found: 0x{hwnd:08X}")
    
    # Try sending WM_CHAR for EURUSD to either edit or the dialog
    if edit_hwnd:
        print(f"  Sending 'EURUSD' via WM_CHAR to Edit...")
        for ch in 'EURUSD':
            user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0102, ord(ch), 0)
            time.sleep(0.05)
        time.sleep(0.5)
        # Press Enter
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0100, 0x0D, 0)
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0101, 0x0D, 0)
        time.sleep(3)
        print("  Text sent to Edit")
    elif combo_hwnd:
        print(f"  Sending 'EURUSD' via WM_CHAR to ComboBox...")
        for ch in 'EURUSD':
            user32.PostMessageW(ctypes.c_void_p(combo_hwnd), 0x0102, ord(ch), 0)
            time.sleep(0.05)
        time.sleep(0.5)
        user32.PostMessageW(ctypes.c_void_p(combo_hwnd), 0x0100, 0x0D, 0)
        user32.PostMessageW(ctypes.c_void_p(combo_hwnd), 0x0101, 0x0D, 0)
        time.sleep(3)
        print("  Text sent to ComboBox")
    else:
        # Try sending directly to dialog
        print(f"  Sending 'EURUSD' via WM_CHAR to dialog...")
        for ch in 'EURUSD':
            user32.PostMessageW(ctypes.c_void_p(new_dlg), 0x0102, ord(ch), 0)
            time.sleep(0.05)
        time.sleep(0.5)
        user32.PostMessageW(ctypes.c_void_p(new_dlg), 0x0100, 0x0D, 0)
        user32.PostMessageW(ctypes.c_void_p(new_dlg), 0x0101, 0x0D, 0)
        time.sleep(3)
    
    # Check if dialog is still there
    time.sleep(2)
    dialogs2 = []
    def cb2(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if title.value:
                    dialogs2.append((hwnd, title.value))
        return True
    user32.EnumWindows(CB(cb2), 0)
    print(f"\nDialogs after interaction:")
    for h, t in dialogs2:
        print(f"  0x{h:08X}: '{t}'")
    
    if len(dialogs2) < len(dialogs):
        print("✅ Dialog closed - chart may have been created!")
    else:
        print("❌ Dialog still open")
        
        # Try Enter key on the dialog
        user32.PostMessageW(ctypes.c_void_p(new_dlg), 0x0100, 0x0D, 0)
        time.sleep(0.05)
        user32.PostMessageW(ctypes.c_void_p(new_dlg), 0x0101, 0x0D, 0)
        time.sleep(3)
        
        # Or try clicking the OK button
        # First try pressing Tab to focus OK, then Enter
        for _ in range(3):
            user32.PostMessageW(ctypes.c_void_p(new_dlg), 0x0100, 0x09, 0)  # Tab
            time.sleep(0.1)
            user32.PostMessageW(ctypes.c_void_p(new_dlg), 0x0101, 0x09, 0)
            time.sleep(0.3)
        
        user32.PostMessageW(ctypes.c_void_p(new_dlg), 0x0100, 0x0D, 0)  # Enter
        time.sleep(0.05)
        user32.PostMessageW(ctypes.c_void_p(new_dlg), 0x0101, 0x0D, 0)
        time.sleep(3)
        
        dialogs3 = []
        def cb3(hwnd, _):
            user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
            if pid_buf.value == mt5_pid:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                if cls.value == '#32770':
                    title = ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                    if title.value:
                        dialogs3.append((hwnd, title.value))
            return True
        user32.EnumWindows(CB(cb3), 0)
        print(f"Dialogs after Tab+Enter: {[t for h,t in dialogs3]}")

# Check for heartbeats
print("\nHeartbeat files:")
COMMON_FILES = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
if os.path.exists(COMMON_FILES):
    for f in sorted(os.listdir(COMMON_FILES)):
        if f.startswith('hb_'):
            hb_path = os.path.join(COMMON_FILES, f)
            age = time.time() - os.path.getmtime(hb_path)
            name = f[3:-4]
            print(f"  {name}: {age:.0f}s old")
else:
    print("  (no files)")
