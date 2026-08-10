"""Debug script: enumerate MT5 windows and try to open a chart."""
import os, time, ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
print(f"Main MT5 HWND: {main_hwnd} (0x{main_hwnd:08X})")

if main_hwnd:
    # Get window rect
    r = wintypes.RECT()
    user32.GetWindowRect(ctypes.c_void_p(main_hwnd), ctypes.byref(r))
    print(f"Window rect: ({r.left},{r.top})-({r.right},{r.bottom}) size=({r.right-r.left}x{r.bottom-r.top})")
    
    # Get window title
    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(ctypes.c_void_p(main_hwnd), title, 512)
    print(f"Window title: '{title.value}'")
    
    # Enumerate child windows
    import psutil
    mt5_pid = None
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            mt5_pid = proc.info['pid']
            break
    print(f"MT5 PID: {mt5_pid}")
    
    if mt5_pid:
        pid_buf = ctypes.c_ulong()
        windows = []
        def enum(hwnd, _):
            user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
            if pid_buf.value == mt5_pid:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                t = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), t, 256)
                vis = user32.IsWindowVisible(ctypes.c_void_p(hwnd))
                rect = wintypes.RECT()
                user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
                windows.append((cls.value, t.value, hwnd, vis, rect))
            return True
        
        user32.EnumWindows(CB(enum), 0)
        
        print(f"\n{'='*80}")
        print(f"{'Class':30s} | {'Title':30s} | {'HWND':10s} | {'Visible':7s} | {'Rect'}")
        print(f"{'='*80}")
        for cls, title, hwnd, vis, rect in sorted(windows, key=lambda x: x[4].top if x[4] else 0):
            vis_str = 'YES' if vis else 'NO'
            rect_str = f"({rect.left},{rect.top})-({rect.right},{rect.bottom})" if rect else "N/A"
            print(f"{cls[:30]:30s} | {title[:30]:30s} | 0x{hwnd:08X} | {vis_str:7s} | {rect_str}")
        
        print(f"\n{'='*80}")
        print(f"Total MT5 windows: {len(windows)}")
        
        # Try WM_COMMAND with various IDs for File → New Chart
        print(f"\n{'='*80}")
        print("Trying various WM_COMMAND IDs to open chart...")
        for cmd_id in [57600, 57601, 57602, 32808, 33000, 33001, 57650, 57610]:
            print(f"\n  WM_COMMAND {cmd_id}...")
            user32.SendMessageW(ctypes.c_void_p(main_hwnd), 0x0111, cmd_id, 0)
            time.sleep(1)
            
            # Check for dialogs
            def check_dlg(hwnd, _):
                p = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(p))
                if p.value == mt5_pid:
                    c = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(ctypes.c_void_p(hwnd), c, 256)
                    if c.value == '#32770':
                        t = ctypes.create_unicode_buffer(256)
                        user32.GetWindowTextW(ctypes.c_void_p(hwnd), t, 256)
                        if t.value:
                            print(f"    Dialog: '{t.value}' hwnd=0x{hwnd:08X}")
                return True
            user32.EnumWindows(CB(check_dlg), 0)
            
            # Check for chart count (use ChartFirst way)
            # We can check by looking for MDIClient children
            
            # Close any dialog by pressing Enter
            user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0100, 0x1B, 0)  # ESC
            user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0101, 0x1B, 0)
            time.sleep(0.5)
