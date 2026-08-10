"""
MT5 EA Deployer v3 — right-click with context menu scan.
"""
import os, sys, time, ctypes, ctypes.wintypes
import subprocess

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
COMMON_FILES = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')
EXPERT_DIR = os.path.join(MT5_DATA, 'MQL5', 'Experts')
MT5_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach_log.txt')
SYSTEM_EAS = {'TestBlank.ex5', 'TemplateLoader.ex5', 'AgentHelper.ex5'}

import pyautogui
pyautogui.FAILSAFE = False

def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def get_mt5_pid():
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None

def get_main_hwnd():
    return user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)

def wait_mt5(timeout=90):
    start = time.time()
    while time.time() - start < timeout:
        h = get_main_hwnd()
        if h and user32.IsWindowVisible(h):
            return h
        time.sleep(2)
    return None

def find_dialog(target, mt5_pid):
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

def click_menu_item_at(click_x, click_y, mt5_pid):
    """Try to click 'Attach to Chart' by scanning offsets."""
    offsets = [
        (40, 12),   # orchestrate_v2.py
        (10, 22),   # rightclick_attach.py
        (30, 18),   # midpoint
        (20, 24),   # wider
        (50, 10),   # right
        (0, 20),    # direct below
        (40, 20),   # 
        (60, 14),   #
        (80, 10),   #
    ]
    
    for dx, dy in offsets:
        x = click_x + dx
        y = click_y + dy
        pyautogui.moveTo(x, y)
        time.sleep(0.1)
        pyautogui.click()
        time.sleep(2)
        
        dialogs = find_dialog('', mt5_pid)
        for h, title in dialogs:
            # Check for any EA Properties-type dialog (title contains common EA chars)
            if any(x in title for x in [' - ', ' Properties', '参数', '設定', '设置']):
                print(f"  ✅ Properties dialog at offset ({dx},{dy}): '{title}'")
                pyautogui.press('enter')
                time.sleep(2)
                return True
            if '代替' in title or 'replace' in title.lower() or title == 'MetaTrader 5':
                print(f"  Replace dialog at ({dx},{dy}): '{title}'")
                pyautogui.press('y')
                time.sleep(2)
                return True
        
        # Close any opened dialogs
        for h, title in dialogs:
            user32.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
        time.sleep(0.3)
    
    return False

def show_nav_panel(mt5_pid):
    pid_buf = ctypes.c_ulong()
    nav_win = [None]
    def find(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if 'MiniFrame' in cls.value:
                t = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), t, 256)
                if any(x in t.value for x in ['導航', 'Navigator', 'ナビゲーター', 'Навигатор']):
                    nav_win[0] = hwnd
        return True
    user32.EnumWindows(CB(find), 0)
    if nav_win[0]:
        user32.ShowWindow(ctypes.c_void_p(nav_win[0]), 5)
        user32.SetWindowPos(ctypes.c_void_p(nav_win[0]), -1, 0, 0, 0, 0, 0x0002 | 0x0001)
        time.sleep(1)
        return nav_win[0]
    h = get_main_hwnd()
    if h:
        user32.SendMessageW(ctypes.c_void_p(h), 0x0111, 32808, 0)
        time.sleep(2)
    return None

def get_ea_pos(ea_name, mt5_pid):
    from pywinauto import Application
    try:
        app = Application(backend='win32').connect(process=mt5_pid)
    except:
        return None, None
    show_nav_panel(mt5_pid)
    time.sleep(1)
    tv = None
    nav_hwnd = None
    pid_buf = ctypes.c_ulong()
    def find_nav(hwnd, _):
        nonlocal nav_hwnd
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if 'MiniFrame' in cls.value:
                t = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), t, 256)
                if any(x in t.value for x in ['導航','Navigator','ナビゲーター','Навигатор']):
                    nav_hwnd = hwnd
        return True
    user32.EnumWindows(CB(find_nav), 0)
    win = app.top_window()
    search = [win.element_info.handle]
    if nav_hwnd:
        search.append(nav_hwnd)
    for h in search:
        try:
            w = app.window(handle=h)
            for d in w.descendants():
                if d.element_info.class_name == 'SysTreeView32' and d.is_visible():
                    tv = d
                    break
        except:
            pass
        if tv:
            break
    if not tv:
        return None, None
    tv_rect = tv.rectangle()
    try:
        root = tv.roots()[0]
        kids = root.children()
        ea_sec = kids[2] if len(kids) > 2 else None
        if not ea_sec:
            for c in kids:
                t = c.text()
                if any(x in t for x in ['EA交易','Expert Advisors','Experts','EA']):
                    ea_sec = c
                    break
        if not ea_sec:
            return None, None
        ea_sec.expand()
        time.sleep(2)
        for ea in ea_sec.children():
            if ea.text() == ea_name:
                try:
                    pr = ea.client_rect()
                    cx = tv_rect.left + (pr.left + pr.right)//2
                    cy = tv_rect.top + (pr.top + pr.bottom)//2
                    return cx, cy, tv_rect
                except:
                    return tv_rect.left + 66, tv_rect.top + 10, tv_rect
    except:
        pass
    return None, None, None

def open_new_chart(mt5_pid):
    """Open new chart using SendMessage WM_COMMAND approach."""
    h = get_main_hwnd()
    user32.SetForegroundWindow(ctypes.c_void_p(h))
    time.sleep(1)
    
    # Try File menu: Alt+F, then N
    pyautogui.press('f')
    time.sleep(0.5)
    pyautogui.press('n')
    time.sleep(2)
    
    dialogs = find_dialog('', mt5_pid)
    if dialogs:
        for hwnd, title in dialogs:
            if 'MetaTrader' in title:
                pyautogui.write('EURUSD', interval=0.05)
                time.sleep(0.5)
                pyautogui.press('enter')
                time.sleep(3)
                print("  ✅ Chart created")
                return True
    time.sleep(2)
    print("  Chart opened (or attempted)")
    return True

def attach_ea_rightclick(ea_name, mt5_pid):
    """Attach EA via right-click with offset scan."""
    # Step 1: Open new chart
    open_new_chart(mt5_pid)
    
    # Step 2: Find EA
    result = get_ea_pos(ea_name, mt5_pid)
    if result[0] is None:
        return False, "EA not found"
    cx, cy, tv_rect = result
    print(f"  EA at ({cx}, {cy})")
    
    # Step 3: Focus Navigator
    pid_buf = ctypes.c_ulong()
    nav_rect = [None]
    def fn(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if 'MiniFrame' in cls.value:
                t = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), t, 256)
                if any(x in t.value for x in ['導航','Navigator','ナビゲーター','Навигатор']):
                    r = ctypes.wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(r))
                    nav_rect[0] = r
        return True
    user32.EnumWindows(CB(fn), 0)
    
    if nav_rect[0]:
        r = nav_rect[0]
        pyautogui.moveTo((r.left+r.right)//2, (r.top+r.bottom)//2)
        time.sleep(0.2)
        pyautogui.click()
        time.sleep(0.5)
    
    # Step 4: Bring MT5 to foreground
    h = get_main_hwnd()
    user32.SetForegroundWindow(ctypes.c_void_p(h))
    time.sleep(0.5)
    
    # Step 5: Right-click on EA
    print(f"  Right-click at ({cx}, {cy})")
    pyautogui.moveTo(cx, cy)
    time.sleep(0.3)
    pyautogui.click(button='right')
    time.sleep(1.5)
    
    # Verify menu
    menu_ok = [False]
    def cm(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if '#32768' in cls.value:
                menu_ok[0] = True
        return True
    user32.EnumWindows(CB(cm), 0)
    
    if menu_ok[0]:
        print("  ✅ Context menu appeared")
        if click_menu_item_at(cx, cy, mt5_pid):
            return True, "Dialog confirmed"
    else:
        print("  ⚠️ No context menu")
        
        # Try double-click as fallback
        print("  Trying double-click fallback...")
        pyautogui.doubleClick(x=cx, y=cy)
        time.sleep(2)
        dialogs = find_dialog('', mt5_pid)
        for hwnd, title in dialogs:
            if ' - ' in title or '代替' in title or 'replace' in title.lower():
                print(f"  ✅ Dialog via double-click: '{title}'")
                pyautogui.press('enter')
                time.sleep(2)
                return True, "Double-click dialog"
    
    return False, "No dialog appeared"

def check_heartbeat(name):
    hb = os.path.join(COMMON_FILES, f'hb_{name}.txt')
    if os.path.exists(hb):
        age = time.time() - os.path.getmtime(hb)
        return age < 60
    return False

def main():
    all_ex5 = [f for f in os.listdir(EXPERT_DIR) if f.endswith('.ex5')]
    ea_names = sorted([f[:-4] for f in all_ex5 if f not in SYSTEM_EAS])
    print(f"Found {len(ea_names)} EAs")
    
    to_deploy = []
    for name in ea_names:
        if check_heartbeat(name):
            print(f"  ✅ {name}: skip (fresh)")
        else:
            print(f"  🚀 {name}: need deploy")
            to_deploy.append(name)
    
    if not to_deploy:
        print("All EAs fresh. Nothing to do.")
        return
    
    mt5_pid = get_mt5_pid()
    if not mt5_pid:
        print("Starting MT5...")
        subprocess.Popen([MT5_PATH])
        h = wait_mt5()
        if not h:
            log("ERROR: MT5 start failed")
            return
        mt5_pid = get_mt5_pid()
    
    print(f"MT5 PID={mt5_pid}")
    log(f"Batch: {len(to_deploy)} EAs")
    
    ok = 0
    fail = 0
    
    for i, name in enumerate(to_deploy, 1):
        print(f"\n--- [{i}/{len(to_deploy)}] {name} ---")
        success, msg = attach_ea_rightclick(name, mt5_pid)
        if success:
            ok += 1
            log(f"SUCCESS: {name} - {msg}")
        else:
            fail += 1
            log(f"FAILED: {name} - {msg}")
        time.sleep(1)
    
    print(f"\n{'='*50}")
    print(f"  RESULTS: {ok} success, {fail} failed, {len(to_deploy)} total")
    print(f"{'='*50}")
    
    print("\nHeartbeats:")
    for name in ea_names:
        hb = os.path.join(COMMON_FILES, f'hb_{name}.txt')
        if os.path.exists(hb):
            age = time.time() - os.path.getmtime(hb)
            print(f"  {'✅' if age < 120 else '⚠️'} {name}: {round(age)}s")
        else:
            print(f"  ❌ {name}: none")
    
    log(f"SUMMARY: {ok} success, {fail} failed, {len(to_deploy)} total")

if __name__ == '__main__':
    main()
