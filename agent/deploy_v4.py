"""
MT5 EA Deployer v4 — right-click + keyboard navigation.
Context menu appears, so try keyboard nav instead of mouse.
"""
import os, sys, time, ctypes, ctypes.wintypes, subprocess

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
        return None, None, None
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
        return None, None, None
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
            return None, None, None
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
    """Open chart via File menu."""
    h = get_main_hwnd()
    user32.SetForegroundWindow(ctypes.c_void_p(h))
    time.sleep(1)
    
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
        print("All fresh. Nothing to do.")
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
        
        # 1. Open chart
        open_new_chart(mt5_pid)
        
        # 2. Find EA position
        cx, cy, tv_rect = get_ea_pos(name, mt5_pid)
        if cx is None:
            log(f"FAILED: {name} - not in Navigator")
            fail += 1
            continue
        
        print(f"  EA at ({cx}, {cy})")
        
        # 3. Focus Navigator panel
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
        
        # 4. Bring MT5 to foreground
        h = get_main_hwnd()
        user32.SetForegroundWindow(ctypes.c_void_p(h))
        time.sleep(0.5)
        
        # 5. Right-click
        print(f"  Right-click at ({cx}, {cy})")
        pyautogui.moveTo(cx, cy)
        time.sleep(0.3)
        pyautogui.click(button='right')
        time.sleep(1.5)
        
        # 6. Check menu appeared
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
        
        attached = False
        
        if menu_ok[0]:
            print("  ✅ Menu appeared, pressing Enter...")
            # METHOD A: Press Enter (selects first menu item in many apps)
            pyautogui.press('enter')
            time.sleep(3)
            
            dialogs = find_dialog('', mt5_pid)
            for hwnd, title in dialogs:
                if name in title or '代替' in title or 'replace' in title.lower():
                    print(f"  ✅ Dialog: '{title}'")
                    attached = True
                    break
            
            if not attached:
                # METHOD B: Press 'A' (Attach to Chart)
                print("  Trying 'A' key...")
                pyautogui.press('a')
                time.sleep(3)
                dialogs = find_dialog('', mt5_pid)
                for hwnd, title in dialogs:
                    if name in title or '代替' in title or 'replace' in title.lower() or title == 'MetaTrader 5':
                        print(f"  ✅ Dialog via 'A': '{title}'")
                        attached = True
                        break
            
            if not attached:
                # METHOD C: Try key combinations for common context menu accelerators
                for key in ['t', '1', 'n', 'c', 'd', 'e']:
                    print(f"  Trying '{key}' key...")
                    pyautogui.press(key)
                    time.sleep(2)
                    dialogs = find_dialog('', mt5_pid)
                    for hwnd, title in dialogs:
                        if name in title or '代替' in title or 'replace' in title.lower() or title == 'MetaTrader 5':
                            print(f"  ✅ Dialog via '{key}': '{title}'")
                            attached = True
                            break
                    if attached:
                        break
        else:
            print("  ⚠️ No context menu")
        
        # 7. Handle dialog if found
        if attached:
            # Check for Replace dialog
            dialogs = find_dialog('', mt5_pid)
            for hwnd, title in dialogs:
                if '代替' in title or 'replace' in title.lower():
                    print(f"  Replace dialog -> Yes")
                    pyautogui.press('y')
                    time.sleep(2)
                    break
            
            # Press Enter to confirm Properties
            pyautogui.press('enter')
            time.sleep(2)
            
            # Enable AutoTrading
            pyautogui.hotkey('ctrl', 'e')
            time.sleep(1)
            
            ok += 1
            log(f"SUCCESS: {name}")
        else:
            fail += 1
            log(f"FAILED: {name}")
        
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
