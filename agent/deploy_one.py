"""
Deploy EA using pywinauto tree nav + TVM_HITTEST + pyautogui double-click.
Avoids pywinauto's select() which requires mouse cursor movement.
"""
import time
import sys
import os
import ctypes
import subprocess
import psutil
import pyautogui
from pywinauto import Application
from pywinauto.keyboard import send_keys

user32 = ctypes.windll.user32
MT5_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class TVHITTESTINFO(ctypes.Structure):
    _fields_ = [
        ('pt_x', ctypes.c_long),
        ('pt_y', ctypes.c_long),
        ('flags', ctypes.c_uint),
        ('hItem', ctypes.c_size_t),
    ]


class TVITEM(ctypes.Structure):
    _fields_ = [
        ('mask', ctypes.c_uint),
        ('hItem', ctypes.c_size_t),
        ('state', ctypes.c_uint),
        ('stateMask', ctypes.c_uint),
        ('pszText', ctypes.c_size_t),
        ('cchTextMax', ctypes.c_int),
        ('iImage', ctypes.c_int),
        ('iSelectedImage', ctypes.c_int),
        ('cChildren', ctypes.c_int),
        ('lParam', ctypes.c_size_t),
    ]


def find_dialog(pid, target_name):
    results = []
    pid_buf = ctypes.c_ulong()

    def cb(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if target_name in title.value:
                    results.append(title.value)
        return True

    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    user32.EnumWindows(CB(cb), 0)
    return results


def find_mt5():
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None


def restart_mt5():
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            proc.kill()
    time.sleep(3)

    subprocess.Popen([MT5_PATH])

    start = time.time()
    while time.time() - start < 90:
        pid = find_mt5()
        if pid:
            try:
                app = Application(backend='uia').connect(process=pid)
                win = app.top_window()
                if win.is_visible() and win.is_enabled():
                    print(f'MT5 ready, PID={pid}')
                    return pid
            except:
                pass
        time.sleep(2)

    print('MT5 failed to start')
    return None


def deploy_ea(ea_name, pid):
    """Deploy EA using pywinauto navigation + pyautogui double-click."""
    app = Application(backend='win32').connect(process=pid)
    win = app.window(class_name='MetaQuotes::MetaTrader::5.00')

    # Open Navigator panel
    user32.SendMessageW(ctypes.c_void_p(win.element_info.handle), 0x0111, 32808, 0)
    time.sleep(1.5)

    # Find TreeView
    tree_view = None
    for d in win.descendants():
        if d.element_info.class_name == 'SysTreeView32':
            tree_view = d
            break

    if not tree_view:
        print('No TreeView found')
        return False

    hwnd = tree_view.element_info.handle
    tr = tree_view.rectangle()
    print(f'TreeView: ({tr.left},{tr.top})-({tr.right},{tr.bottom})')

    # Use pywinauto to navigate the tree (this doesn't require mouse movement)
    root = tree_view.roots()[0]
    ea_trading = root.children()[2]
    ea_trading.expand()
    time.sleep(2)

    # Find the EA node - just read its text, don't select it
    target = None
    for child in ea_trading.children():
        if child.text() == ea_name:
            target = child
            break

    if not target:
        print(f'{ea_name} not found in tree')
        return False

    print(f'Found {ea_name}')

    # Now use TVM_HITTEST to find where the EA is on screen
    TVM_HITTEST = 0x1100 + 17

    for row in range(0, tr.bottom - tr.top, 18):
        test_y = tr.top + row + 9

        # Convert to client coords
        pt = (ctypes.c_long * 2)(50, test_y)
        user32.ScreenToClient(ctypes.c_void_p(hwnd), ctypes.byref(pt))

        hi = TVHITTESTINFO()
        hi.pt_x = pt[0]
        hi.pt_y = pt[1]

        h_item = user32.SendMessageW(ctypes.c_void_p(hwnd), TVM_HITTEST, 0, ctypes.byref(hi))
        if h_item:
            buf = ctypes.create_unicode_buffer(256)
            item = TVITEM()
            item.mask = 0x0001  # TVIF_TEXT
            item.hItem = h_item
            item.pszText = ctypes.addressof(buf)
            item.cchTextMax = 256
            item.cchTextMax = 256

            TVM_GETITEM = 0x1100 + 12
            result = user32.SendMessageW(ctypes.c_void_p(hwnd), TVM_GETITEM, 0, ctypes.byref(item))
            if result:
                text = buf.value.strip()
                if ea_name in text:
                    print(f'Found {ea_name} at screen y={test_y} (row {row})')
                    
                    # Double-click at this position
                    pyautogui.doubleClick(x=50, y=test_y)
                    time.sleep(3)

                    dialogs = find_dialog(pid, ea_name)
                    if dialogs:
                        print(f'Properties dialog found: {dialogs[0]}')
                        send_keys('{ENTER}')
                        time.sleep(2)
                        
                        # AutoTrading check
                        send_keys('^e')
                        time.sleep(1)
                        send_keys('^e')
                        time.sleep(1)
                        print('AutoTrading toggled')
                        
                        return True
                    else:
                        print('No dialog appeared')
                        return False

    print(f'{ea_name} not found via HITTEST scan')
    return False


def main():
    ea_name = sys.argv[1] if len(sys.argv) > 1 else 'Correlation'

    print(f'\n=== Deploying {ea_name} ===\n')

    pid = restart_mt5()
    if not pid:
        print('FAILED: MT5 restart')
        return False

    # Open new chart
    send_keys('^n')
    time.sleep(1)
    send_keys('{ENTER}')
    time.sleep(3)
    print('New chart opened')

    result = deploy_ea(ea_name, pid)
    print(f'\nResult: {"SUCCESS" if result else "FAILED"}')
    return result


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
