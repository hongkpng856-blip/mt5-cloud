"""Try opening New Chart via keybd_event (hardware-level keyboard simulation)."""
import os, time, ctypes, sys
from ctypes import wintypes

user32 = ctypes.windll.user32

MT5_CLASS = 'MetaQuotes::MetaTrader::5.00'

def get_mt5_pid():
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None

def keybd_event(vk, down=True):
    """Simulate a keyboard event at hardware level."""
    flags = 0 if down else 2  # KEYEVENTF_KEYUP
    user32.keybd_event(vk, 0, flags, 0)
    time.sleep(0.05)

def alt_key(vk):
    """Send Alt+Key."""
    VK_MENU = 0x12
    keybd_event(VK_MENU, True)   # Alt down
    time.sleep(0.1)
    keybd_event(vk, True)        # Key down
    time.sleep(0.05)
    keybd_event(vk, False)       # Key up
    time.sleep(0.05)
    keybd_event(VK_MENU, False)  # Alt up
    time.sleep(0.5)

def ctrl_key(vk):
    """Send Ctrl+Key."""
    VK_CONTROL = 0x11
    keybd_event(VK_CONTROL, True)
    time.sleep(0.1)
    keybd_event(vk, True)
    time.sleep(0.05)
    keybd_event(vk, False)
    time.sleep(0.05)
    keybd_event(VK_CONTROL, False)
    time.sleep(0.5)

def send_text(hwnd, text):
    """Send text via WM_CHAR to a specific window."""
    for ch in text:
        user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0102, ord(ch), 0)
        time.sleep(0.03)
    time.sleep(0.3)

def send_enter(hwnd):
    """Send Enter key via PostMessage."""
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, 0x0D, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, 0x0D, 0)
    time.sleep(0.3)

def find_dialogs(mt5_pid, target=''):
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    results = []
    pid_buf = ctypes.c_ulong()
    def cb(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if not target or target in title.value:
                    results.append((hwnd, title.value))
        return True
    user32.EnumWindows(CB(cb), 0)
    return results

def main():
    mt5_pid = get_mt5_pid()
    if not mt5_pid:
        print("MT5 not running")
        return
    
    main_hwnd = user32.FindWindowW(MT5_CLASS, None)
    print(f"MT5 HWND={main_hwnd:08X} PID={mt5_pid}")
    
    # Method 1: Bring MT5 to foreground and use keybd_event Alt+F, N
    print("\n--- Method 1: Activate window + Alt+F+N ---")
    user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
    time.sleep(1)
    
    # Alt+F to open File menu
    alt_key(ord('F'))
    time.sleep(1.5)
    
    # Check if menu appeared (look for popup menu #32768)
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    pid_buf = ctypes.c_ulong()
    menus = []
    def find_menu(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if '#32768' in cls.value:
                menus.append(hwnd)
        return True
    user32.EnumWindows(CB(find_menu), 0)
    print(f"  Popup menus after Alt+F: {len(menus)}")
    
    # Press N for New Chart (新圖)
    keybd_event(ord('N'), True)
    time.sleep(0.1)
    keybd_event(ord('N'), False)
    time.sleep(2)
    
    # Check for dialogs
    dialogs = find_dialogs(mt5_pid)
    print(f"  Dialogs after Alt+F+N: {len(dialogs)}")
    for h, t in dialogs:
        print(f"    {h:08X}: '{t}'")
    
    # Method 2: Try keybd_event Ctrl+N (which we now know is Navigator)
    # But maybe we can access File > New Chart via a different approach
    
    # Method 3: Try using WM_SYSCOMMAND with SC_KEYMENU
    print("\n--- Method 2: SC_KEYMENU approach ---")
    # Close any open dialogs
    for h, t in dialogs:
        print(f"  Closing: '{t}'")
        user32.SendMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
    time.sleep(2)
    
    # SC_KEYMENU activates the menu bar
    user32.SendMessageW(ctypes.c_void_p(main_hwnd), 0x0112, 0xF100, 0)
    time.sleep(1)
    
    # Send 'F' to open File menu
    keybd_event(ord('F'), True)
    time.sleep(0.1)
    keybd_event(ord('F'), False)
    time.sleep(1.5)
    
    # Send 'N' for New Chart
    keybd_event(ord('N'), True)
    time.sleep(0.1)
    keybd_event(ord('N'), False)
    time.sleep(2)
    
    dialogs = find_dialogs(mt5_pid)
    print(f"  Dialogs after SC_KEYMENU+F+N: {len(dialogs)}")
    for h, t in dialogs:
        print(f"    {h:08X}: '{t}'")
    
    # Method 3: Try Ctrl+N then right-click in Navigator or something
    print("\n--- Method 3: Direct approach ---")
    for h, t in dialogs:
        user32.SendMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
    time.sleep(2)
    
    # Let's see what happens with File > New by going through the menu more carefully
    # Press Alt, then cursor to File, then Enter on New Chart
    VK_MENU = 0x12
    VK_RETURN = 0x0D
    VK_DOWN = 0x28
    
    # Alt to activate menu
    keybd_event(VK_MENU, True)
    time.sleep(0.1)
    keybd_event(VK_MENU, False)
    time.sleep(1)
    
    # Arrow keys: right to File (or press F for File accelerator)
    # The Chinese MT5 has 文件(&F), so F is the accelerator
    keybd_event(ord('F'), True)
    time.sleep(0.1)
    keybd_event(ord('F'), False)
    time.sleep(1.5)
    
    # N for 新圖 (New Chart)
    keybd_event(ord('N'), True)
    time.sleep(0.1)
    keybd_event(ord('N'), False)
    time.sleep(2)
    
    dialogs = find_dialogs(mt5_pid)
    print(f"  Dialogs: {len(dialogs)}")
    for h, t in dialogs:
        print(f"    {h:08X}: '{t}'")
    
    if dialogs:
        # Found dialog! Send EURUSD and Enter
        main_dialog = dialogs[0][0]
        print(f"\n  Found dialog! Sending EURUSD...")
        send_text(main_dialog, 'EURUSD')
        send_enter(main_dialog)
        time.sleep(3)
        
        # Check for chart
        new_dialogs = find_dialogs(mt5_pid)
        print(f"  Dialogs after EURUSD+Enter: {len(new_dialogs)}")
        for h, t in new_dialogs:
            print(f"    {h:08X}: '{t}'")
        
        # Check MDIClient
        mdi = user32.FindWindowExW(ctypes.c_void_p(main_hwnd), None, 'MDIClient', None)
        if mdi:
            chart_count = [0]
            def _count(h, _):
                chart_count[0] += 1
                return True
            user32.EnumChildWindows(ctypes.c_void_p(mdi), CB(_count), 0)
            print(f"  MDIClient child windows: {chart_count[0]}")
    else:
        print("  No dialog appeared")

if __name__ == '__main__':
    main()
