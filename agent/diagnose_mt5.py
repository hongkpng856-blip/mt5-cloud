"""Diagnose MT5 window state for Navigator troubleshooting."""
import os
import sys
import time
import ctypes
import subprocess

MT5_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'

def find_mt5_window():
    user32 = ctypes.windll.user32
    # Try different class names
    class_names = [
        'MetaQuotes::MetaTrader::5.00',
        'MetaTrader::5.00',
        '#32770',
    ]
    
    print("=== Looking for MT5 main window ===")
    for cls in class_names:
        hwnd = user32.FindWindowW(cls, None)
        if hwnd:
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
            print(f"  Found window: class='{cls}' hwnd={hwnd} title='{title.value}'")
            break
        else:
            print(f"  Not found: class='{cls}'")
    
    if not hwnd:
        print("  MT5 main window NOT FOUND!")
        return None
    return hwnd

def enum_windows_of_mt5(mt5_pid):
    """Enumerate all windows belonging to MT5 process."""
    user32 = ctypes.windll.user32
    windows = []
    
    def _enum(hwnd, _):
        pid_buf = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
            rect = ctypes.RECT()
            user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
            visible = user32.IsWindowVisible(ctypes.c_void_p(hwnd))
            windows.append({
                'hwnd': hwnd,
                'class': cls.value,
                'title': title.value,
                'visible': bool(visible),
                'rect': (rect.left, rect.top, rect.right, rect.bottom),
            })
        return True
    
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    user32.EnumWindows(CB(_enum), 0)
    
    # Also enumerate child windows
    def _enum_child(parent_hwnd):
        results = []
        def _cb(hwnd, _):
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
            rect = ctypes.RECT()
            user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
            results.append({
                'hwnd': hwnd,
                'class': cls.value,
                'title': title.value,
                'rect': (rect.left, rect.top, rect.right, rect.bottom),
            })
            return True
        user32.EnumChildWindows(ctypes.c_void_p(parent_hwnd), CB(_cb), 0)
        return results
    
    print(f"\n=== All MT5 top-level windows (PID={mt5_pid}) ===")
    for w in windows:
        print(f"  hwnd={w['hwnd']} visible={w['visible']} class='{w['class']}' title='{w['title']}' rect={w['rect']}")
        if w['visible']:
            children = _enum_child(w['hwnd'])
            for c in children:
                print(f"    child hwnd={c['hwnd']} class='{c['class']}' title='{c['title']}' rect={c['rect']}")
    
    return windows

def check_pywinauto_connection(mt5_pid):
    print(f"\n=== Checking pywinauto connection (PID={mt5_pid}) ===")
    try:
        from pywinauto import Application
        app = Application(backend='win32').connect(process=mt5_pid)
        print("  Connection OK")
        try:
            win = app.top_window()
            print(f"  top_window: handle={win.element_info.handle} class={win.element_info.class_name} visible={win.is_visible()}")
        except Exception as e:
            print(f"  top_window failed: {e}")
        
        try:
            main_win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
            print(f"  main_window: handle={main_win.element_info.handle} visible={main_win.is_visible()}")
            # Check descendants
            for d in main_win.descendants():
                cls = d.element_info.class_name
                if 'TreeView' in cls or 'ControlBar' in cls or 'MiniFrame' in cls:
                    print(f"    descendant: class='{cls}' visible={d.is_visible()}")
        except Exception as e:
            print(f"  main window lookup failed: {e}")
    except Exception as e:
        print(f"  Connection failed: {e}")

def try_different_approach(mt5_pid):
    """Try SendKeys approach to toggle Navigator"""
    print(f"\n=== Trying alternative Navigator toggle ===")
    try:
        from pywinauto.keyboard import send_keys
        from pywinauto import Application
        import ctypes as ct
        
        user32 = ct.windll.user32
        app = Application(backend='win32').connect(process=mt5_pid)
        
        # Try different approaches to show Navigator
        # Approach 1: View menu - Ctrl+N is for new chart, not Navigator
        # Navigator is typically Alt+V, then N (查看 > 导航)
        # Or Ctrl+Shift+N (custom shortcut)
        # Or click the Navigator toolbar button
        
        # Let's try the WM_COMMAND approach with different IDs
        main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
        if main_hwnd:
            # Common Navigator toggle command IDs: 32808, 32800, 32801, 32786, 32787
            for cmd_id in [32808, 32800, 32801, 32786, 32787, 32799]:
                print(f"  Trying WM_COMMAND {cmd_id}...")
                user32.SendMessageW(ct.c_void_p(main_hwnd), 0x0111, cmd_id, 0)
                time.sleep(1)
                
                # Check if Navigator appeared
                found_nav = False
                def _find_nav(hwnd, _):
                    nonlocal found_nav
                    pid_buf = ct.c_ulong()
                    user32.GetWindowThreadProcessId(ct.c_void_p(hwnd), ct.byref(pid_buf))
                    if pid_buf.value == mt5_pid:
                        cls = ct.create_unicode_buffer(256)
                        user32.GetClassNameW(ct.c_void_p(hwnd), cls, 256)
                        title = ct.create_unicode_buffer(256)
                        user32.GetWindowTextW(ct.c_void_p(hwnd), title, 256)
                        if 'TreeView' in cls.value or ('Navigator' in title.value or '導航' in title.value):
                            print(f"    -> Found: hwnd={hwnd} class='{cls.value}' title='{title.value}'")
                            found_nav = True
                    return True
                CB = ct.WINFUNCTYPE(ct.c_bool, ct.c_size_t, ct.c_size_t)
                user32.EnumWindows(CB(_find_nav), 0)
                if found_nav:
                    break
        
        # Approach 2: Use keyboard shortcuts
        # Try to bring MT5 to foreground first
        print("\n  Trying keyboard shortcuts...")
        try:
            win = app.top_window()
            win.set_focus()
            time.sleep(0.5)
        except:
            pass
        
        # Alt+V, N (View > Navigator)
        send_keys('%vn')
        time.sleep(2)
        
        # Check for TreeView
        found_tv = False
        for _w in [app.top_window()]:
            try:
                for d in _w.descendants():
                    if d.element_info.class_name == 'SysTreeView32':
                        print(f"  TreeView found! visible={d.is_visible()} rect={d.rectangle()}")
                        found_tv = True
                        break
            except:
                pass
        
        if not found_tv:
            print("  TreeView still not found after keyboard shortcuts")
            
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == '__main__':
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            pid = proc.info['pid']
            print(f"Found MT5 PID={pid}")
            hwnd = find_mt5_window()
            enum_windows_of_mt5(pid)
            check_pywinauto_connection(pid)
            try_different_approach(pid)
            break
    else:
        print("MT5 not running!")
        # Start MT5
        print("Starting MT5...")
        subprocess.Popen([MT5_PATH])
        time.sleep(30)
        # Check again
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
                pid = proc.info['pid']
                print(f"Started MT5 PID={pid}")
                hwnd = find_mt5_window()
                enum_windows_of_mt5(pid)
                check_pywinauto_connection(pid)
                try_different_approach(pid)
                break
