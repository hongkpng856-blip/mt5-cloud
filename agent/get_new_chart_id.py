"""Get submenu items for File → New Chart (新圖)."""
import os, time, ctypes, struct
from ctypes import wintypes

user32 = ctypes.windll.user32

main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
menu_hwnd = user32.GetMenu(ctypes.c_void_p(main_hwnd))
print(f"Main menu: 0x{menu_hwnd:08X}")

if menu_hwnd:
    # File menu is [0]
    file_menu = user32.GetSubMenu(ctypes.c_void_p(menu_hwnd), 0)
    print(f"File submenu: 0x{file_menu:08X}")
    
    if file_menu:
        count = user32.GetMenuItemCount(ctypes.c_void_p(file_menu))
        print(f"File menu items: {count}")
        
        for i in range(count):
            buf = ctypes.create_unicode_buffer(256)
            ret = user32.GetMenuStringW(ctypes.c_void_p(file_menu), i, buf, 255, 0x0400)  # MF_BYPOSITION
            mid = user32.GetMenuItemID(ctypes.c_void_p(file_menu), i)
            
            # Check if this item has a submenu
            sub = user32.GetSubMenu(ctypes.c_void_p(file_menu), i)
            is_separator = (mid == 0) and (sub is None) and (ret == 0 or buf.value == '')
            if is_separator or (mid == -1 and sub is None):
                print(f"  [{i}] SEPARATOR")
            elif sub:
                sub_count = user32.GetMenuItemCount(ctypes.c_void_p(sub))
                print(f"  [{i}] '{buf.value}' → SUBMENU ({sub_count} items)")
                if sub:
                    for j in range(min(sub_count, 50)):
                        sbuf = ctypes.create_unicode_buffer(256)
                        sret = user32.GetMenuStringW(ctypes.c_void_p(sub), j, sbuf, 255, 0x0400)
                        smid = user32.GetMenuItemID(ctypes.c_void_p(sub), j)
                        ssub = user32.GetSubMenu(ctypes.c_void_p(sub), j)
                        if ssub:
                            print(f"    [{j}] '{sbuf.value}' → SUBSUBMENU")
                        elif smid == 0 and (sret == 0 or sbuf.value == ''):
                            print(f"    [{j}] SEPARATOR")
                        elif smid == -1 and ssub is None:
                            print(f"    [{j}] '{sbuf.value}' (no id)")
                        else:
                            print(f"    [{j}] '{sbuf.value}' ID={smid}")
            else:
                print(f"  [{i}] '{buf.value}' ID={mid}")
        
        # Also try to open New Chart submenu to see more by sending Alt+F
        print("\n--- Simulating Alt+F to open File menu... ---")
        # Send Alt+F
        user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0104, ord('F'), 0)  # WM_SYSKEYDOWN Alt+F
        time.sleep(0.1)
        user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0105, ord('F'), 0)  # WM_SYSKEYUP
        time.sleep(1.5)
        
        # Now press 'N' for New Chart (first item with &N)
        user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0100, ord('N'), 0)  # WM_KEYDOWN
        time.sleep(0.05)
        user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0101, ord('N'), 0)  # WM_KEYUP
        time.sleep(1.5)
        
        # Check for popup menus
        pid_buf = ctypes.c_ulong()
        import psutil
        mt5_pid = None
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
                mt5_pid = proc.info['pid']
                break
        
        if mt5_pid:
            CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
            menus = []
            _mt5pid = mt5_pid
            def find_menu(hwnd, _):
                user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
                if pid_buf.value == _mt5pid:
                    cls = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                    if '#32768' in cls.value:
                        menus.append((hwnd, cls.value))
                return True
            user32.EnumWindows(CB(find_menu), 0)
            print(f"  Popup menus found: {len(menus)}")
            for h, c in menus:
                print(f"    0x{h:08X}: {c}")
                # Try to get items from this menu
                item_count = user32.GetMenuItemCount(ctypes.c_void_p(h))
                print(f"    Items: {item_count}")
                for k in range(min(item_count or 0, 30)):
                    sbuf = ctypes.create_unicode_buffer(256)
                    ret = user32.GetMenuStringW(ctypes.c_void_p(h), k, sbuf, 255, 0x0400)
                    sid = user32.GetMenuItemID(ctypes.c_void_p(h), k)
                    if sbuf.value:
                        print(f"      [{k}] '{sbuf.value}' ID={sid}")
        
        # Escape to close menus
        user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0100, 0x1B, 0)
        user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0101, 0x1B, 0)
