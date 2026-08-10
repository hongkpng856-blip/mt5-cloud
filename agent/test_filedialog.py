"""Test file dialog interaction for Load Template."""
import os, time, ctypes, sys
from ctypes import wintypes

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

def get_mt5_pid():
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None

mt5_pid = get_mt5_pid()
main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
print(f"MT5 PID={mt5_pid} HWND={main_hwnd:08X}")

# Close existing dialogs
pid_buf = ctypes.c_ulong()
def close_all(hwnd, _):
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
    if pid_buf.value == mt5_pid:
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if cls.value in ('#32770', '#32768'):
            user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)
    return True
user32.EnumWindows(CB(close_all), 0)
time.sleep(2)

# Open Load Template dialog
user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0111, 32899, 0)
time.sleep(3)

# Find dialog
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

dialogs = find_dialogs()
print(f"Dialogs: {len(dialogs)}")
for h, t in dialogs:
    print(f"  {h:08X}: '{t}'")

# Find the file dialog
file_dlg = None
for h, t in dialogs:
    if '開啟' in t or 'Open' in t:
        file_dlg = h
        break

if not file_dlg:
    print("❌ File dialog not found")
    # Try opening via different methods
    exit()

print(f"\nFile dialog: {file_dlg:08X}")

# Enumerate ALL children of the dialog
def enum_children(hwnd, indent=0):
    results = []
    def enum(hwnd2, _):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd2), cls, 256)
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(ctypes.c_void_p(hwnd2), title, 256)
        rect = wintypes.RECT()
        user32.GetWindowRect(ctypes.c_void_p(hwnd2), ctypes.byref(rect))
        results.append((hwnd2, cls.value, title.value, rect))
        return True
    user32.EnumChildWindows(ctypes.c_void_p(hwnd), CB(enum), 0)
    return results

children = enum_children(file_dlg)
print(f"\nChildren of file dialog ({len(children)}):")
for h, c, t, r in children:
    print(f"  {h:08X}: class='{c}' title='{t}' rect=({r.left},{r.top})-({r.right},{r.bottom})")

# Look for Edit controls
edits = [(h, c, t, r) for h, c, t, r in children if c == 'Edit']
print(f"\nEdit controls: {len(edits)}")
for h, c, t, r in edits:
    print(f"  {h:08X}: rect=({r.left},{r.top})-({r.right},{r.bottom})")

# Look for Button controls  
buttons = [(h, c, t, r) for h, c, t, r in children if c == 'Button']
print(f"\nButtons: {len(buttons)}")
for h, c, t, r in buttons:
    print(f"  {h:08X}: '{t}' rect=({r.left},{r.top})-({r.right},{r.bottom})")

# Look for ComboBox (file name input)
combos = [(h, c, t, r) for h, c, t, r in children if 'Combo' in c or 'List' in c]
print(f"\nCombo/List: {len(combos)}")
for h, c, t, r in combos:
    print(f"  {h:08X}: class='{c}' title='{t}' rect=({r.left},{r.top})-({r.right},{r.bottom})")

# Check what type of file dialog this is (OpenFileDialog vs Common Item Dialog)
# In Windows 10+, the file dialog might be a Common Item Dialog (modern style)
# or the older GetOpenFileName dialog.

# Check if it has a DirectUIHWND (modern file dialog)
dui = [(h, c, t, r) for h, c, t, r in children if 'DirectUI' in c or 'WorkerW' in c or 'SHELLDLL_DefView' in c]
print(f"\nModern file dialog indicators: {len(dui)}")
for h, c, t, r in dui:
    print(f"  {h:08X}: class='{c}'")

# If there are no Edit controls, it might be a modern dialog
# In that case, we need to use the file name ComboBox or a different approach

if not edits:
    print("\n⚠️ No Edit controls - modern file dialog")
    # Try sending text to the dialog directly (it might route to the right control)
    print("  Sending template name directly to dialog...")
    for ch in 'ADX_Trend_EURUSD_H1.tpl':
        user32.PostMessageW(ctypes.c_void_p(file_dlg), 0x0102, ord(ch), 0)
        time.sleep(0.03)
    time.sleep(1)
    # Press Enter
    user32.PostMessageW(ctypes.c_void_p(file_dlg), 0x0100, 0x0D, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(file_dlg), 0x0101, 0x0D, 0)
    time.sleep(3)
    print("  Submitted!")
else:
    # Use the first Edit
    edit_hwnd = edits[0][0]
    print(f"\n  Using Edit: {edit_hwnd:08X}")
    
    # Clear and type
    # Select all
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0100, 0x11, 0)  # Ctrl down
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0100, ord('A'), 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0101, ord('A'), 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0101, 0x11, 0)  # Ctrl up
    time.sleep(0.1)
    
    # Type template name
    for ch in 'ADX_Trend_EURUSD_H1.tpl':
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0102, ord(ch), 0)
        time.sleep(0.03)
    time.sleep(1)
    
    # Press Enter
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0100, 0x0D, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0101, 0x0D, 0)
    time.sleep(3)
    print("  Enter sent!")
    
    # Check if dialog closed
    dialogs2 = find_dialogs()
    print(f"\nDialogs after submission: {len(dialogs2)}")
    for h, t in dialogs2:
        print(f"  {h:08X}: '{t}'")
    
    if any('開啟' in t for h, t in dialogs2):
        print("⚠️ Dialog still open - trying to click Open button")
        # Find the Open button
        for h2, c2, t2, r2 in buttons:
            if '開' in t2 or 'Open' in t2 or '開啟' in t2:
                print(f"  Clicking '{t2}' button...")
                user32.SendMessageW(ctypes.c_void_p(h2), 0x00F5, 0, 0)  # BM_CLICK
                time.sleep(3)
                break
        
        dialogs3 = find_dialogs()
        print(f"Dialogs after button click: {len(dialogs3)}")
        for h, t in dialogs3:
            print(f"  {h:08X}: '{t}'")
        
        if any('開啟' in t for h, t in dialogs3):
            print("⚠️ Still open - trying pyautogui")
            import pyautogui
            # Click on the file name field, then type, then Enter
            if edits:
                edit_rect = edits[0][3]
                ecx = (edit_rect.left + edit_rect.right) // 2
                ecy = (edit_rect.top + edit_rect.bottom) // 2
                pyautogui.click(x=ecx, y=ecy)
                time.sleep(0.5)
                pyautogui.write('ADX_Trend_EURUSD_H1.tpl')
                time.sleep(1)
                pyautogui.press('enter')
                time.sleep(3)
                print("  Done via pyautogui!")

print("\nFinal dialogs:")
for h, t in find_dialogs():
    print(f"  {h:08X}: '{t}'")
