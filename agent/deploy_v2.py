"""
MT5 EA Deployer v2 — right-click context menu method.
Uses pyautogui for mouse + keyboard (works when window is foregrounded).
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
    """Find dialog windows with title containing target"""
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

def show_nav_panel(mt5_pid):
    """Show Navigator panel"""
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
    main_hwnd = get_main_hwnd()
    if main_hwnd:
        user32.SendMessageW(ctypes.c_void_p(main_hwnd), 0x0111, 32808, 0)
        time.sleep(2)
    return None

def get_ea_pos(ea_name, mt5_pid):
    """Find EA in Navigator and return screen (x, y)"""
    from pywinauto import Application
    try:
        app = Application(backend='win32').connect(process=mt5_pid)
    except:
        return None, None
    
    # Show Navigator
    show_nav_panel(mt5_pid)
    time.sleep(1)
    
    # Find TreeView
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
                if any(x in t.value for x in ['導航', 'Navigator', 'ナビゲーター', 'Навигатор']):
                    nav_hwnd = hwnd
        return True
    user32.EnumWindows(CB(find_nav), 0)
    
    # Search for TreeView
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
        print("  No TreeView found")
        return None, None
    
    tv_rect = tv.rectangle()
    print(f"  TreeView: ({tv_rect.left},{tv_rect.top})-({tv_rect.right},{tv_rect.bottom})")
    
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
            print("  EA section not found")
            return None, None
        
        ea_sec.expand()
        time.sleep(2)
        
        for ea in ea_sec.children():
            if ea.text() == ea_name:
                try:
                    pr = ea.client_rect()
                    cx = tv_rect.left + (pr.left + pr.right)//2
                    cy = tv_rect.top + (pr.top + pr.bottom)//2
                    print(f"  Found {ea_name} at ({cx}, {cy})")
                    return cx, cy
                except:
                    cx = tv_rect.left + 66
                    cy = tv_rect.top + 10
                    return cx, cy
        print(f"  {ea_name} not found in Navigator")
    except Exception as e:
        print(f"  Nav error: {e}")
    return None, None

def open_new_chart(mt5_pid):
    """Open new EURUSD chart using pyautogui hotkeys"""
    main_hwnd = get_main_hwnd()
    user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
    time.sleep(1)
    
    # Alt+F → File menu
    pyautogui.press('f', interval=0.3)
    time.sleep(0.5)
    # N → New Chart
    pyautogui.press('n', interval=0.3)
    time.sleep(2)
    
    # Check for symbol dialog
    dialogs = find_dialog('', mt5_pid)
    if dialogs:
        print(f"  Symbol dialog: {[d[1] for d in dialogs]}")
        pyautogui.write('EURUSD', interval=0.05)
        time.sleep(0.5)
        pyautogui.press('enter')
        time.sleep(3)
        print("  Chart created")
        return True
    else:
        time.sleep(3)
        print("  Chart opened (or attempted)")
        return True

def attach_ea_rightclick(ea_name, mt5_pid):
    """Attach EA via right-click context menu"""
    # Step 1: Open new chart
    open_new_chart(mt5_pid)
    
    # Step 2: Show Navigator and find EA position
    cx, cy = get_ea_pos(ea_name, mt5_pid)
    if cx is None:
        return False, "EA not found"
    
    # Step 3: Focus Navigator panel
    pid_buf = ctypes.c_ulong()
    nav_rect = [None]
    def find_nav_r(hwnd, _):
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
    user32.EnumWindows(CB(find_nav_r), 0)
    
    if nav_rect[0]:
        r = nav_rect[0]
        nc = (r.left + r.right)//2
        ny = (r.top + r.bottom)//2
        pyautogui.moveTo(nc, ny)
        time.sleep(0.2)
        pyautogui.click()
        time.sleep(0.5)
        print(f"  Navigator focused at ({nc}, {ny})")
    
    # Bring MT5 main window to foreground
    main_hwnd = get_main_hwnd()
    user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
    time.sleep(0.5)
    
    # Step 4: Right-click on EA
    print(f"  Right-click at ({cx}, {cy})")
    pyautogui.moveTo(cx, cy)
    time.sleep(0.3)
    pyautogui.click(button='right')
    time.sleep(1.5)
    
    # Verify context menu appeared
    menu_found = [False]
    def check_m(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if '#32768' in cls.value:
                menu_found[0] = True
        return True
    user32.EnumWindows(CB(check_m), 0)
    
    if not menu_found[0]:
        print("  ⚠️ Right-click context menu did not appear")
        return False, "No context menu"
    
    print("  ✅ Context menu appeared")
    
    # Step 5: Click "Attach to Chart" (first menu item)
    item_x = cx + 40
    item_y = cy + 12
    pyautogui.moveTo(item_x, item_y)
    time.sleep(0.3)
    pyautogui.click()
    time.sleep(3)
    
    # Step 6: Check for EA Properties dialog
    dialogs = find_dialog(ea_name, mt5_pid)
    if dialogs:
        print(f"  ✅ Properties dialog: {[d[1] for d in dialogs]}")
        pyautogui.press('enter')
        time.sleep(2)
        pyautogui.hotkey('ctrl', 'e')
        time.sleep(1)
        return True, "EA dialog confirmed"
    
    # Step 7: Check for Replace dialog
    for h, title in find_dialog('', mt5_pid):
        if '代替' in title or 'replace' in title.lower() or title == 'MetaTrader 5':
            print(f"  Replace dialog: '{title}' -> Yes")
            pyautogui.press('y')
            time.sleep(2)
            dialogs = find_dialog(ea_name, mt5_pid)
            if dialogs:
                pyautogui.press('enter')
                time.sleep(2)
                pyautogui.hotkey('ctrl', 'e')
                time.sleep(1)
                return True, "Replace + EA confirmed"
    
    return False, "No dialog appeared"

def check_heartbeat(name):
    hb = os.path.join(COMMON_FILES, f'hb_{name}.txt')
    if os.path.exists(hb):
        age = time.time() - os.path.getmtime(hb)
        return age < 60
    return False

def main():
    # List EAs
    all_ex5 = [f for f in os.listdir(EXPERT_DIR) if f.endswith('.ex5')]
    ea_names = sorted([f[:-4] for f in all_ex5 if f not in SYSTEM_EAS])
    print(f"Found {len(ea_names)} EAs")
    
    # Check heartbeats
    to_deploy = []
    for name in ea_names:
        if check_heartbeat(name):
            print(f"  ✅ {name}: heartbeat fresh, skip")
        else:
            hb = os.path.join(COMMON_FILES, f'hb_{name}.txt')
            if os.path.exists(hb):
                age = time.time() - os.path.getmtime(hb)
                print(f"  🚀 {name}: heartbeat {round(age)}s old → DEPLOY")
            else:
                print(f"  🚀 {name}: no heartbeat → DEPLOY")
            to_deploy.append(name)
    
    if not to_deploy:
        print("All EAs have fresh heartbeats.")
        return
    
    # Get MT5
    mt5_pid = None
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            mt5_pid = proc.info['pid']
            break
    
    if not mt5_pid:
        print("Starting MT5...")
        subprocess.Popen([MT5_PATH])
        hwnd = wait_mt5()
        if not hwnd:
            log("ERROR: Could not start MT5")
            return
        mt5_pid = None
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
                mt5_pid = proc.info['pid']
                break
    
    print(f"MT5 PID={mt5_pid}")
    
    log(f"Batch deploy: {len(to_deploy)} EAs")
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
        time.sleep(2)
    
    print(f"\n{'='*50}")
    print(f"  RESULTS: {ok} success, {fail} failed, {len(to_deploy)} total")
    print(f"{'='*50}")
    
    # Heartbeat check
    print("\nHeartbeats:")
    for name in ea_names:
        hb = os.path.join(COMMON_FILES, f'hb_{name}.txt')
        if os.path.exists(hb):
            age = time.time() - os.path.getmtime(hb)
            print(f"  {'✅' if age < 120 else '⚠️'} {name}: {round(age)}s")
        else:
            print(f"  ❌ {name}: no heartbeat")
    
    log(f"SUMMARY: {ok} success, {fail} failed, {len(to_deploy)} total")

if __name__ == '__main__':
    main()
