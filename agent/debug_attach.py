"""
Debug: Try different attach approaches and report exactly what works.
"""
import os, sys, time, ctypes, ctypes.wintypes, pyautogui
from pywinauto import Application

pyautogui.FAILSAFE = False
user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

APPDATA = os.environ.get('APPDATA', '')
MT5_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'
COMMON_FILES = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')
LOG_FILE = r'C:\Users\hongk\Desktop\mt5-cloud\agent\auto_attach_log.txt'

def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def find_dialog(mt5_pid, target=''):
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

import psutil
mt5_pid = None
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
        mt5_pid = proc.info['pid']
        break
print(f'MT5 PID: {mt5_pid}')

app = Application(backend='win32').connect(process=mt5_pid)
win = app.top_window()

# Find TreeView
tv = None
hawk = None
pid_buf = ctypes.c_ulong()
def fn(hwnd, _):
    global hawk
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
    if pid_buf.value == mt5_pid:
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if 'MiniFrame' in cls.value:
            t = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), t, 256)
            if any(x in t.value for x in ['導航', 'Navigator', 'ナビゲーター', 'Навигатор']):
                hawk = hwnd
    return True
user32.EnumWindows(CB(fn), 0)
print(f'Navigator hwnd: {hex(hawk) if hawk else "N/A"}')

for w in app.windows(class_name_re='.*MiniFrame.*'):
    try:
        for d in w.descendants():
            if d.element_info.class_name == 'SysTreeView32':
                tv = d
                break
    except:
        pass
    if tv:
        break

if not tv:
    for d in app.top_window().descendants():
        if d.element_info.class_name == 'SysTreeView32' and d.is_visible():
            tv = d
            break

if not tv:
    print('NO TREEVIEW')
    exit()

tr = tv.rectangle()
print(f'TreeView: ({tr.left},{tr.top})-({tr.right},{tr.bottom}) width={tr.width()} height={tr.height()}')

# Find ADX_Trend
root = tv.roots()[0]
kids = root.children()
ea_sec = kids[2] if len(kids) > 2 else None
if ea_sec:
    ea_sec.expand()
    time.sleep(2)
    for ea in ea_sec.children():
        if ea.text() == 'ADX_Trend':
            print(f'Found ADX_Trend')
            pr = ea.client_rect()
            print(f'  client_rect: L{pr.left}, T{pr.top}, R{pr.right}, B{pr.bottom}')
            cx = tr.left + (pr.left + pr.right)//2
            cy = tr.top + (pr.top + pr.bottom)//2
            print(f'  Screen coords: ({cx}, {cy})')
            
            # Also try item rectangle
            try:
                ir = ea.rectangle()
                print(f'  rectangle(): L{ir.left}, T{ir.top}, R{ir.right}, B{ir.bottom}')
            except Exception as e:
                print(f'  rectangle() error: {e}')
            
            # Try ensure_visible
            try:
                ea.ensure_visible()
                time.sleep(0.5)
                pr2 = ea.client_rect()
                print(f'  After ensure_visible: L{pr2.left}, T{pr2.top}, R{pr2.right}, B{pr2.bottom}')
            except Exception as e:
                print(f'  ensure_visible error: {e}')
            
            # Now try to attach
            th = tv.element_info.handle
            hi = ea.item().hItem
            
            # Method 1: pyautogui double-click at calculated position
            print('\nMethod 1: pyautogui.doubleClick at (cx, cy)')
            pyautogui.moveTo(cx, cy)
            time.sleep(0.3)
            pyautogui.doubleClick()
            time.sleep(3)
            d = find_dialog(mt5_pid, '')
            for h, t in d:
                print(f'  Dialog after dc: "{t}"')
            d2 = find_dialog(mt5_pid, 'ADX_Trend')
            print(f'  ADX_Trend dialogs: {[t for h,t in d2]}')
            
            # Close any open dialogs
            for h, t in d:
                user32.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
            time.sleep(1)
            
            # Method 2: Select + SendMessage Enter
            print('\nMethod 2: SendMessage TVM_SELECTITEM + Enter')
            user32.SendMessageW(ctypes.c_void_p(th), 0x1100+11, 9, ctypes.c_size_t(hi))
            user32.SendMessageW(ctypes.c_void_p(th), 0x1100+20, 0, ctypes.c_size_t(hi))
            time.sleep(0.5)
            user32.SendMessageW(ctypes.c_void_p(th), 0x0100, 0x0D, 0)  # WM_KEYDOWN Enter
            time.sleep(0.05)
            user32.SendMessageW(ctypes.c_void_p(th), 0x0101, 0x0D, 0)  # WM_KEYUP Enter
            time.sleep(3)
            d = find_dialog(mt5_pid, '')
            for h, t in d:
                print(f'  Dialog after Send Enter: "{t}"')
            
            # Close dialogs
            for h, t in d:
                user32.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
            time.sleep(1)
            
            # Method 3: PostMessage double-click
            print('\nMethod 3: PostMessage double-click')
            user32.SendMessageW(ctypes.c_void_p(th), 0x1100+11, 9, ctypes.c_size_t(hi))
            user32.SendMessageW(ctypes.c_void_p(th), 0x1100+20, 0, ctypes.c_size_t(hi))
            time.sleep(0.5)
            lparam = (cy << 16) | (cx & 0xFFFF)
            # WM_LBUTTONDBLCLK at client coords
            clx = cx - tr.left
            cly = cy - tr.top
            lp = (cly << 16) | (clx & 0xFFFF)
            user32.PostMessageW(ctypes.c_void_p(th), 0x0203, 0x0001, lp)  # WM_LBUTTONDBLCLK
            time.sleep(3)
            d = find_dialog(mt5_pid, '')
            for h, t in d:
                print(f'  Dialog after PostMessage DC: "{t}"')
            
            # Close dialogs
            for h, t in d:
                user32.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
            time.sleep(1)
            
            # Method 4: Right-click + scan menu click
            print('\nMethod 4: Right-click + click menu items')
            pyautogui.moveTo(cx, cy)
            time.sleep(0.2)
            pyautogui.click(button='right')
            time.sleep(2)
            
            # Check for menu
            def ck(hwnd, _):
                p = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(p))
                if p.value == mt5_pid:
                    cls = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                    if '#32768' in cls.value:
                        t = ctypes.create_unicode_buffer(256)
                        user32.GetWindowTextW(ctypes.c_void_p(hwnd), t, 256)
                        print(f'  Menu: hwnd={hex(hwnd)} text="{t.value}"')
            user32.EnumWindows(CB(ck), 0)
            
            # Try clicking at various offsets
            for dx, dy in [(40, 12), (10, 22), (20, 20), (0, 20), (50, 10), (30, 18), (10, 30)]:
                mx = cx + dx
                my = cy + dy
                pyautogui.moveTo(mx, my)
                time.sleep(0.1)
                pyautogui.click()
                time.sleep(1)
                d = find_dialog(mt5_pid, '')
                if d:
                    print(f'  👉 Click at ({dx},{dy}) found dialog: {[t for h,t in d]}')
                    for h, t in d:
                        user32.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
                    time.sleep(0.5)
                    break
                else:
                    print(f'  No dialog at ({dx},{dy})')
            
            print('\nDone debugging')
            break
