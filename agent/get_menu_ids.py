"""Get MT5 main menu structure and find New Chart command ID."""
import os, time, ctypes, struct
from ctypes import wintypes

user32 = ctypes.windll.user32

main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
print(f"Main HWND: 0x{main_hwnd:08X}")

# Get the menu handle
menu_hwnd = user32.GetMenu(ctypes.c_void_p(main_hwnd))
print(f"Menu handle: 0x{menu_hwnd:08X}")

if menu_hwnd:
    # Get menu item count
    item_count = user32.GetMenuItemCount(ctypes.c_void_p(menu_hwnd))
    print(f"Menu items: {item_count}")
    
    for i in range(item_count):
        # Get menu item text
        buf = ctypes.create_unicode_buffer(256)
        # MIIM_STRING = 0x40, MIIM_ID = 0x02, MIIM_SUBMENU = 0x04
        info = struct.pack('I', 256)  # cbSize
        info += struct.pack('I', 0x46)  # fMask = MIIM_STRING | MIIM_ID | MIIM_SUBMENU
        info += struct.pack('I', i)  # wID (for getting type)
        info += struct.pack('I', 0)  # hSubMenu
        info += struct.pack('I', 0)  # hbmpChecked
        info += struct.pack('I', 0)  # hbmpUnchecked
        info += struct.pack('I', 0)  # dwItemData
        info += ctypes.c_char_p(ctypes.addressof(buf))  # dwTypeData
        info += struct.pack('I', 256)  # cch
        
        # Actually, let's use GetMenuString instead (simpler)
        ret = user32.GetMenuStringW(ctypes.c_void_p(menu_hwnd), i, buf, 255, 0x0400)  # MF_BYPOSITION
        if ret > 0:
            # Get submenu
            submenu = user32.GetSubMenu(ctypes.c_void_p(menu_hwnd), i)
            sub_count = user32.GetMenuItemCount(ctypes.c_void_p(submenu)) if submenu else 0
            print(f"  [{i}] '{buf.value}' (sub={sub_count})")
            
            if submenu and sub_count > 0:
                for j in range(min(sub_count, 50)):
                    sbuf = ctypes.create_unicode_buffer(256)
                    sret = user32.GetMenuStringW(ctypes.c_void_p(submenu), j, sbuf, 255, 0x0400)
                    if sret > 0:
                        # Get menu item ID
                        mid = user32.GetMenuItemID(ctypes.c_void_p(submenu), j)
                        print(f"    [{j}] '{sbuf.value}' ID={mid}")
