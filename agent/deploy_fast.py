"""
Fast EA deployment: select EA in Navigator, double-click, handle dialogs.
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
COMMON_FILES = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\Common\Files'


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


def find_dialog(pid, target_name=""):
    """Find #32770 dialogs belonging to MT5 process."""
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
                if not target_name or target_name in title.value:
                    results.append((hwnd, title.value))
        return True
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    user32.EnumWindows(CB(cb), 0)
    return results


def get_child_text(parent_hwnd):
    """Get text from Static children of a dialog."""
    texts = []
    def cb(child, _):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(child), cls, 256)
        if cls.value == 'Static':
            buf = ctypes.create_unicode_buffer(1024)
            user32.GetWindowTextW(ctypes.c_void_p(child), buf, 1024)
            if buf.value:
                texts.append(buf.value)
        return True
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    user32.EnumChildWindows(ctypes.c_void_p(parent_hwnd), CB(cb), 0)
    return texts


def click_button(dialog_hwnd, button_text_contains):
    """Find and click a button in a dialog."""
    def cb(child, _):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(child), cls, 256)
        if cls.value == 'Button':
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(child), buf, 256)
            if button_text_contains in buf.value:
                user32.SendMessageW(ctypes.c_void_p(child), 0x00F5, 0, 0)  # BM_CLICK
                return False
        return True
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    user32.EnumChildWindows(ctypes.c_void_p(dialog_hwnd), CB(cb), 0)


def main():
    ea_name = sys.argv[1] if len(sys.argv) > 1 else 'ADX_Trend'

    print(f'\n=== Deploying {ea_name} ===')

    # Kill any MT5 and wait for ALL to die
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            proc.kill()
    # Wait until no more terminal64 processes
    for _w in range(20):
        found = False
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
                found = True
                break
        if not found:
            break
        time.sleep(1)
    time.sleep(2)
    print('All MT5 processes killed')

    # Start MT5
    subprocess.Popen([MT5_PATH])
    pid = None
    start = time.time()
    while time.time() - start < 90:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
                pid = proc.info['pid']
                break
        if pid:
            try:
                app = Application(backend='uia').connect(process=pid)
                win = app.top_window()
                if win.is_visible() and win.is_enabled():
                    print(f'MT5 ready, PID={pid}')
                    break
            except:
                pass
        time.sleep(2)
    else:
        print('MT5 failed to start')
        return False

    time.sleep(3)

    # Open new chart with EURUSD
    send_keys('^n')
    time.sleep(1)
    send_keys('EURUSD')
    time.sleep(0.5)
    send_keys('{ENTER}')
    time.sleep(3)
    print('Chart opened')

    # Connect win32
    app = Application(backend='win32').connect(process=pid)
    win = app.window(class_name='MetaQuotes::MetaTrader::5.00')

    # Open Navigator
    user32.SendMessageW(ctypes.c_void_p(win.element_info.handle), 0x0111, 32808, 0)
    time.sleep(1.5)

    # Find TreeView
    tree_view = None
    for d in win.descendants():
        if d.element_info.class_name == 'SysTreeView32':
            tree_view = d
            break

    if not tree_view:
        print('No TreeView')
        return False

    hwnd = tree_view.element_info.handle
    tr = tree_view.rectangle()

    # Navigate
    root = tree_view.roots()[0]
    ea_trading = root.children()[2]
    ea_trading.expand()
    time.sleep(2)

    # Find EA
    target = None
    for child in ea_trading.children():
        if child.text() == ea_name:
            target = child
            break

    if not target:
        print(f'{ea_name} not found')
        return False

    # Select via Win32
    TVM_SELECTITEM = 0x1100 + 11
    TVGN_CARET = 9
    h_item = target.item().hItem
    user32.SendMessageW(ctypes.c_void_p(hwnd), TVM_SELECTITEM, TVGN_CARET, ctypes.c_size_t(h_item))
    time.sleep(0.5)

    # Click chart for focus
    mdi = None
    for d in win.descendants():
        if d.element_info.class_name == 'MDIClient':
            mdi = d
            break
    if mdi:
        mr = mdi.rectangle()
        pyautogui.click(x=(mr.left + mr.right) // 2, y=(mr.top + mr.bottom) // 2)
        time.sleep(1)

    # Double-click scan (quick: 18px step, 1s wait)
    print('Scanning...')
    found = False
    for y_step in range(0, tr.bottom - tr.top, 18):
        click_y = tr.top + y_step + 9
        pyautogui.doubleClick(x=60, y=click_y)
        time.sleep(1.5)

        # Check for Properties dialog
        dialogs = find_dialog(pid, ea_name)
        if dialogs:
            print(f'Properties dialog at ({60},{click_y})')
            send_keys('{ENTER}')  # Confirm
            time.sleep(2)
            print('Confirmed!')
            found = True
            break

        # Check for Replace dialog
        all_dialogs = find_dialog(pid)
        for dh, title in all_dialogs:
            if title == 'MetaTrader 5':
                texts = get_child_text(dh)
                for t in texts:
                    if '代替' in t or 'replace' in t.lower():
                        print(f'Replace dialog at ({60},{click_y}), clicking Yes')
                        click_button(dh, '是')
                        time.sleep(2)
                        # Now check for Properties
                        dialogs2 = find_dialog(pid, ea_name)
                        if dialogs2:
                            print(f'Properties dialog after Replace')
                            send_keys('{ENTER}')
                            time.sleep(2)
                            found = True
                        break
                if found:
                    break
        if found:
            break

    if not found:
        print(f'{ea_name}: Not found via scan')
        # Try one more scan with 9px step
        print('Trying finer scan...')
        for y_step in range(0, tr.bottom - tr.top, 9):
            click_y = tr.top + y_step + 9
            pyautogui.doubleClick(x=60, y=click_y)
            time.sleep(1)
            dialogs = find_dialog(pid, ea_name)
            if dialogs:
                send_keys('{ENTER}')
                time.sleep(2)
                found = True
                break
            # Also check Replace
            for dh, title in find_dialog(pid):
                if title == 'MetaTrader 5':
                    texts = get_child_text(dh)
                    for t in texts:
                        if '代替' in t:
                            click_button(dh, '是')
                            time.sleep(2)
                            if find_dialog(pid, ea_name):
                                send_keys('{ENTER}')
                                time.sleep(2)
                                found = True
                            break
                if found:
                    break
            if found:
                break

    # Verify heartbeat
    if found:
        hb_path = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
        print('Waiting for heartbeat...')
        for _ in range(20):
            if os.path.exists(hb_path):
                age = time.time() - os.path.getmtime(hb_path)
                print(f'Heartbeat found! Age={age:.0f}s')
                return True
            time.sleep(3)
        print('Heartbeat not detected')
        return False
    else:
        print(f'{ea_name}: Deployment failed')
        return False


if __name__ == '__main__':
    result = main()
    sys.exit(0 if result else 1)
