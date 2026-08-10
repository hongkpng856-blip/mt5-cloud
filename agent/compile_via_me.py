"""MetaEditor is running - use it to compile the batch script."""
import os, time, ctypes, subprocess
from ctypes import wintypes

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

# Find MetaEditor window
me_hwnd = user32.FindWindowW('MetaQuotes::MetaEditor::5.00', None)
if not me_hwnd:
    # Try with different class name
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'MetaEditor64' in proc.info['name']:
            me_pid = proc.info['pid']
            break
    
    pid_buf = ctypes.c_ulong()
    def find_me(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if hasattr(pid_buf, 'value') and pid_buf.value == me_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
            print(f"MetaEditor window: class='{cls.value}' title='{title.value}'")
            if 'MetaEditor' in title.value or 'MetaEditor' in cls.value:
                me_hwnd = hwnd
        return True
    user32.EnumWindows(CB(find_me), 0)

if me_hwnd:
    print(f"MetaEditor HWND: 0x{me_hwnd:08X}")
    
    # Bring to foreground
    user32.SetForegroundWindow(ctypes.c_void_p(me_hwnd))
    time.sleep(1)
    
    # Try to check if any file is open by looking at window title
    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(ctypes.c_void_p(me_hwnd), title, 512)
    print(f"Window title: '{title.value}'")
    
    # Send F7 (compile) or Ctrl+F7
    # In MetaEditor, F7 compiles the current file
    print("Sending F7 to compile...")
    user32.PostMessageW(ctypes.c_void_p(me_hwnd), 0x0100, 0x76, 0)  # F7
    user32.PostMessageW(ctypes.c_void_p(me_hwnd), 0x0101, 0x76, 0)
    time.sleep(3)
    
    # Close MetaEditor
    user32.PostMessageW(ctypes.c_void_p(me_hwnd), 0x0010, 0, 0)  # WM_CLOSE
    time.sleep(2)
    
    # Check if ex5 was updated
    APPDATA = os.environ.get('APPDATA', '')
    MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
                            'D0E8209F77C8CF37AD8BF550E51FF075')
    ex5_path = os.path.join(MT5_DATA, 'MQL5', 'Scripts', 'BatchApplyTemplates.ex5')
    if os.path.exists(ex5_path):
        mtime = os.path.getmtime(ex5_path)
        age = time.time() - mtime
        print(f"EX5: {ex5_path} ({age:.0f}s old)")
        
        # Check if we can find chart windows in MT5 now
        main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
        if main_hwnd:
            title2 = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(ctypes.c_void_p(main_hwnd), title2, 512)
            print(f"MT5 title: '{title2.value}'")
else:
    print("MetaEditor window not found")
