"""Debug version — prints every dialog found during scan."""
import os, sys, time, ctypes, subprocess, psutil
user32 = ctypes.windll.user32

def find_mt5_pid():
    for p in psutil.process_iter(['pid', 'name']):
        if p.info['name'] and 'terminal64' in p.info['name'].lower():
            return p.info['pid']
    return None

pid = find_mt5_pid()
from pywinauto import Application
from pywinauto.keyboard import send_keys

app = Application(backend='win32').connect(process=pid)
win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
user32.SetForegroundWindow(ctypes.c_void_p(win.element_info.handle))
time.sleep(0.5)

# Close dialogs
pid_buf = ctypes.c_ulong()
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
def _close(hwnd, _):
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
    if pid_buf.value == pid:
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if cls.value == '#32770':
            user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)
    return True
user32.EnumWindows(CB(_close), 0)

# Open nav
send_keys('^n')
time.sleep(2)

# Navigate
tree_view = None
for d in win.descendants():
    if d.element_info.class_name == 'SysTreeView32':
        tree_view = d
        break

hwnd_tree = tree_view.element_info.handle
tv_rect = tree_view.rectangle()
root = tree_view.roots()[0]
ea_trading = root.children()[2]
ea_trading.expand()
time.sleep(2)

# Select ATR_Stop
ea_item = None
for child in ea_trading.children():
    if child.text() == 'ATR_Stop':
        ea_item = child
        break

h_item = ea_item.item().hItem
TVM_S = 0x1100 + 11
TVGN_C = 9
TVM_EV = 0x1100 + 20
user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_S, TVGN_C, ctypes.c_size_t(h_item))
user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_EV, 0, ctypes.c_size_t(h_item))
time.sleep(0.5)

import pyautogui

def get_dialogs():
    """Return all dialog titles for our MT5 process."""
    results = []
    CB2 = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    def _cb(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if title.value:
                    results.append(title.value)
        return True
    user32.EnumWindows(CB2(_cb), 0)
    return results

click_x = tv_rect.left + 60
ea_name = 'ATR_Stop'

for y_offset in range(0, 80, 4):
    click_y = tv_rect.top + y_offset
    print('y_offset={}, click_y={}'.format(y_offset, click_y))
    
    pyautogui.doubleClick(x=click_x, y=click_y)
    time.sleep(0.8)
    
    dialogs = get_dialogs()
    print('  Dialogs: {}'.format(dialogs))
    
    # Check for our EA
    if any(ea_name in d for d in dialogs):
        print('  >>> FOUND ATR_Stop at y={}!'.format(click_y))
        break
    
    # Close unwanted dialogs
    for d in dialogs:
        if ea_name not in d and d != 'MetaTrader 5 - Netting - EURUSD,H1':
            print('  Closing: {}'.format(d))
            send_keys('{ESC}')
            time.sleep(0.3)
            break  # Only close one at a time

print('\nFinal dialogs: {}'.format(get_dialogs()))
