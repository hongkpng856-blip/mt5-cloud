"""Scan WM_COMMAND IDs to find File → New Chart."""
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

main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
print(f"MT5 HWND=0x{main_hwnd:08X} PID={mt5_pid}")

# Close all dialogs first
pid_buf = ctypes.c_ulong()
def close_dlgs(hwnd, _):
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
    if pid_buf.value == mt5_pid:
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if cls.value == '#32770':
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
            if title.value:
                print(f"  Closing: '{title.value}'")
                user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)
    return True
user32.EnumWindows(CB(close_dlgs), 0)
time.sleep(2)

# Try a wide range of command IDs
# Standard ranges: 57600-57999 (File menu), 33000-33999 (Charts), etc.
ranges_to_try = [
    (57600, 57650, "File menu"),
    (33000, 33100, "Chart menu"),
    (32800, 32900, "View menu"),
    (57000, 57100, "Common"),
]

def find_dialogs():
    results = []
    def cb(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if title.value:
                    results.append((hwnd, title.value))
        return True
    user32.EnumWindows(CB(cb), 0)
    return results

for start, end, label in ranges_to_try:
    print(f"\n--- Scanning {label} ({start}-{end}) ---")
    for cmd in range(start, end):
        user32.SendMessageW(ctypes.c_void_p(main_hwnd), 0x0111, cmd, 0)
        time.sleep(0.2)
        dialogs = find_dialogs()
        if dialogs:
            print(f"  WM_COMMAND {cmd} → Dialogs: {[(hex(h), t) for h, t in dialogs]}")
            # Close them to avoid accumulation
            for h, t in dialogs:
                user32.PostMessageW(ctypes.c_void_p(h), 0x0100, 0x1B, 0)  # ESC
                user32.PostMessageW(ctypes.c_void_p(h), 0x0101, 0x1B, 0)
            time.sleep(0.5)

print("\nDone scanning.")
