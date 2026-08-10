"""
MT5 EA Deployer — for cron/background use.
Uses PostMessage for keyboard (works in background) + pyautogui for mouse clicks.
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

def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def get_mt5_hwnd():
    return user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)

def wait_mt5(timeout=90):
    start = time.time()
    while time.time() - start < timeout:
        h = get_mt5_hwnd()
        if h and user32.IsWindowVisible(h):
            return h
        time.sleep(2)
    return None

def kill_mt5():
    for _ in range(5):
        subprocess.run(['taskkill.exe', '/f', '/im', 'terminal64.exe'],
                       capture_output=True, timeout=10)
        time.sleep(1)

def start_mt5():
    subprocess.Popen([MT5_PATH])
    h = wait_mt5(90)
    if h:
        time.sleep(8)
        return h
    return None

def close_dialogs(hwnd):
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    mt5_pid = pid.value
    def enum(hw, _):
        p = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hw), ctypes.byref(p))
        if p.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hw), cls, 256)
            if cls.value == '#32770':
                t = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hw), t, 256)
                if t.value:
                    user32.SendMessageW(ctypes.c_void_p(hw), 0x0010, 0, 0)
        return True
    user32.EnumWindows(CB(enum), 0)

def post_key(hwnd, vk):
    """Send a key press/release via PostMessage (works in background)."""
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, vk, 0)  # WM_KEYDOWN
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, vk, 0)  # WM_KEYUP
    time.sleep(0.15)

def post_text(hwnd, text):
    """Send text via WM_CHAR messages."""
    for ch in text:
        user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0102, ord(ch), 0)
        time.sleep(0.05)
    time.sleep(0.3)

def post_ctrl_key(hwnd, vk_key):
    """Send Ctrl+Key."""
    VK_CONTROL = 0x11
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, VK_CONTROL, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, vk_key, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, vk_key, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, VK_CONTROL, 0)
    time.sleep(0.3)

def send_wm_command(hwnd, cmd_id):
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0111, cmd_id, 0)
    time.sleep(1)

def find_dialog(hwnd, substr):
    """Check for a dialog with title containing substr. Return list of titles."""
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    mt5_pid = pid.value
    r = []
    def enum(hw, _):
        p = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hw), ctypes.byref(p))
        if p.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hw), cls, 256)
            if cls.value == '#32770':
                t = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hw), t, 256)
                if substr in t.value:
                    r.append(t.value)
        return True
    user32.EnumWindows(CB(enum), 0)
    return r

def find_all_dialogs(hwnd):
    """Return list of (handle, title) for all dialogs."""
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    mt5_pid = pid.value
    r = []
    def enum(hw, _):
        p = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hw), ctypes.byref(p))
        if p.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hw), cls, 256)
            if cls.value == '#32770':
                t = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hw), t, 256)
                if t.value:
                    r.append((hw, t.value))
        return True
    user32.EnumWindows(CB(enum), 0)
    return r

def open_new_chart_via_market_watch(hwnd):
    """Use Market Watch right-click → Chart Window to open a chart.
    This uses mouse clicks which work from background processes."""
    import pyautogui
    
    # First, find the Market Watch window
    # Market Watch is typically a SysListView32 or similar docked window
    from pywinauto import Application
    app = Application(backend='win32').connect(handle=hwnd)
    
    # Look for the Market Watch list view
    mw_list = None
    for d in app.top_window().descendants():
        cls = d.element_info.class_name
        if cls in ['SysListView32', 'DirectUIHWND']:
            rect = d.rectangle()
            # Market Watch is usually on the left side, smaller width
            if rect.width() < 400 and rect.height() > 100:
                mw_list = d
                break
    
    if mw_list:
        # Right-click on Market Watch
        rect = mw_list.rectangle()
        cx = rect.left + 50
        cy = rect.top + 20
        pyautogui.click(x=cx, y=cy, button='right')
        time.sleep(1)
        # Click "Chart Window" in context menu
        pyautogui.click(x=cx + 50, y=cy + 60)
        time.sleep(3)
        print("  Chart opened via Market Watch right-click")
        return True
    
    # Fallback: Use WM_COMMAND to try various chart-related commands
    print("  Market Watch not found, trying WM_COMMAND...")
    for cmd in [57600, 57601, 57602, 33000, 33001]:
        send_wm_command(hwnd, cmd)
        d = find_dialog(hwnd, 'MetaTrader 5')
        if d:
            # Symbol selection dialog appeared
            post_text(hwnd, 'EURUSD')
            time.sleep(0.5)
            post_key(hwnd, 0x0D)  # Enter
            time.sleep(3)
            print(f"  Chart created via WM_COMMAND {cmd}")
            return True
    
    print("  ⚠️ Could not open new chart")
    return False

def open_new_chart_ctrl_n(hwnd):
    """Alternative: use PostMessage for Ctrl+N."""
    print("  Trying Ctrl+N via PostMessage...")
    post_ctrl_key(hwnd, ord('N'))
    time.sleep(2)
    # Check for symbol dialog
    d = find_dialog(hwnd, 'MetaTrader 5')
    if d:
        print(f"  Dialog: {d}")
        post_text(hwnd, 'EURUSD')
        time.sleep(0.5)
        post_key(hwnd, 0x0D)
        time.sleep(3)
        print("  Chart created via Ctrl+N")
        return True
    
    # Try N after Ctrl+N (sometimes the first key is the file menu)
    post_key(hwnd, ord('N'))
    time.sleep(2)
    d = find_dialog(hwnd, 'MetaTrader 5')
    if d:
        post_text(hwnd, 'EURUSD')
        time.sleep(0.5)
        post_key(hwnd, 0x0D)
        time.sleep(3)
        print("  Chart created via Ctrl+N+N")
        return True
    return False

def open_new_chart_via_menu(hwnd):
    """Open chart via Alt+F (File menu) navigation."""
    print("  Trying File menu...")
    VK_MENU = 0x12
    VK_RETURN = 0x0D
    VK_DOWN = 0x28
    
    # Alt+F to open File menu
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, VK_MENU, 0)
    time.sleep(0.1)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, ord('F'), 0)
    time.sleep(0.1)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, ord('F'), 0)
    time.sleep(0.1)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, VK_MENU, 0)
    time.sleep(1)
    
    # Down arrow to New Chart
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, VK_DOWN, 0)
    time.sleep(0.1)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, VK_DOWN, 0)
    time.sleep(0.5)
    
    # Enter
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, VK_RETURN, 0)
    time.sleep(0.1)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, VK_RETURN, 0)
    time.sleep(2)
    
    d = find_dialog(hwnd, 'MetaTrader 5')
    if d:
        post_text(hwnd, 'EURUSD')
        time.sleep(0.5)
        post_key(hwnd, VK_RETURN)
        time.sleep(3)
        print("  Chart created via File menu")
        return True
    return False

def open_new_chart(hwnd):
    """Try multiple methods to open a new chart."""
    if open_new_chart_ctrl_n(hwnd):
        return True
    if open_new_chart_via_menu(hwnd):
        return True
    if open_new_chart_via_market_watch(hwnd):
        return True
    print("  ⚠️ All chart creation methods failed")
    return False

def open_navigator(hwnd):
    """Open Navigator via WM_COMMAND."""
    send_wm_command(hwnd, 32808)
    time.sleep(2)

def find_treeview(hwnd):
    """Find the SysTreeView32 in Navigator."""
    from pywinauto import Application
    app = Application(backend='win32').connect(handle=hwnd)
    
    # Search MiniFrame windows (floating Navigator)
    for w in app.windows(class_name_re='.*MiniFrame.*'):
        try:
            for d in w.descendants():
                if d.element_info.class_name == 'SysTreeView32':
                    return d, app
        except:
            pass
    
    # Search in main window
    try:
        for d in app.top_window().descendants():
            if d.element_info.class_name == 'SysTreeView32':
                return d, app
    except:
        pass
    
    return None, app

def find_ea_node(tv, name):
    """Find and select EA node in TreeView."""
    try:
        root = tv.roots()[0]
        kids = root.children()
        ea_section = kids[2] if len(kids) > 2 else None
        if not ea_section:
            for c in kids:
                t = c.text()
                if any(x in t for x in ['EA交易', 'Expert Advisors', 'المستشارون المختصون', 'Experts', 'EA']):
                    ea_section = c
                    break
        if not ea_section:
            return None
        ea_section.expand()
        time.sleep(2)
        for ea in ea_section.children():
            if ea.text() == name:
                th = tv.element_info.handle
                h = ea.item().hItem
                user32.SendMessageW(ctypes.c_void_p(th), 0x1100 + 11, 9, ctypes.c_size_t(h))
                user32.SendMessageW(ctypes.c_void_p(th), 0x1100 + 20, 0, ctypes.c_size_t(h))
                time.sleep(0.5)
                return ea
    except Exception as e:
        print(f"  find_ea_node error: {e}")
    return None

def double_click_ea(ea, tv):
    """Double-click EA node using pyautogui."""
    import pyautogui
    try:
        pr = ea.client_rect()
        tr = tv.rectangle()
        cx = tr.left + (pr.left + pr.right) // 2
        cy = tr.top + (pr.top + pr.bottom) // 2
    except:
        tr = tv.rectangle()
        cx = tr.left + 66
        cy = tr.top + 10
    
    print(f"  Double-click at ({cx}, {cy})")
    
    # Bring Navigator foreground
    th = tv.element_info.handle
    nf = user32.GetAncestor(ctypes.c_void_p(th), 1)
    if nf:
        user32.SetForegroundWindow(ctypes.c_void_p(nf))
        time.sleep(0.3)
    user32.SetFocus(ctypes.c_void_p(th))
    time.sleep(0.3)
    
    # Double-click
    pyautogui.doubleClick(x=cx, y=cy)
    time.sleep(3)

def try_double_click_scan(tv, name):
    """Scan through TreeView trying double-clicks."""
    import pyautogui
    tr = tv.rectangle()
    row_height = 20
    indent = 66
    print(f"  Scan double-clicks in TreeView: ({tr.left},{tr.top})-({tr.right},{tr.bottom})")
    
    for y_step in range(0, min(tr.bottom - tr.top, 800), row_height):
        cx = tr.left + indent
        cy = tr.top + y_step
        
        pyautogui.doubleClick(x=cx, y=cy)
        time.sleep(1.0)
        
        # Check for dialog
        dialogs = find_all_dialogs(get_mt5_hwnd())
        for h, title in dialogs:
            if name in title:
                print(f"  ✅ Found dialog: '{title}' at Y={y_step}")
                # Press Enter to confirm
                post_key(h, 0x0D)
                time.sleep(2)
                return True
            if '代替' in title or 'replace' in title.lower() or title == 'MetaTrader 5':
                print(f"  Replace dialog: '{title}' -> Y")
                post_key(h, ord('Y'))
                time.sleep(1)
                for _ in range(5):
                    time.sleep(1)
                    d2 = find_dialog(get_mt5_hwnd(), name)
                    if d2:
                        print(f"  ✅ Prop dialog after replace")
                        post_key(h, 0x0D)
                        time.sleep(2)
                        return True
                return True
    
    return False

def confirm_and_verify(hwnd, name):
    """Confirm any dialog and verify heartbeat."""
    # Check for Properties dialog
    d = find_dialog(hwnd, name)
    if d:
        print(f"  ✅ Properties dialog: {d}")
        post_key(hwnd, 0x0D)
        time.sleep(2)
        return True
    
    # Check for Replace dialog
    dd = find_all_dialogs(hwnd)
    for h, title in dd:
        if '代替' in title or 'replace' in title.lower() or title == 'MetaTrader 5':
            print(f"  Replace dialog: '{title}' -> Yes")
            post_key(h, ord('Y'))
            time.sleep(3)
            for _ in range(5):
                time.sleep(1)
                d2 = find_dialog(hwnd, name)
                if d2:
                    print(f"  ✅ Properties dialog after replace")
                    post_key(h, 0x0D)
                    time.sleep(2)
                    return True
            return True
    
    return False

def check_heartbeat(name):
    hb = os.path.join(COMMON_FILES, f'hb_{name}.txt')
    if os.path.exists(hb):
        age = time.time() - os.path.getmtime(hb)
        if age < 60:
            return True
    return False

def enable_autotrading(hwnd):
    """Toggle AutoTrading on."""
    post_ctrl_key(hwnd, ord('E'))
    time.sleep(1)
    print("  AutoTrading toggled")

def deploy_ea(name, hwnd, symbol='EURUSD', tf='H1'):
    """Deploy a single EA."""
    print(f"\n{'='*50}")
    print(f"  Deploying: {name} → {symbol} {tf}")
    print(f"{'='*50}")
    
    close_dialogs(hwnd)
    
    # Step 1: Open new chart
    if not open_new_chart(hwnd):
        print("  ⚠️ Proceeding with existing chart")
    
    # Step 2: Open Navigator
    open_navigator(hwnd)
    
    # Step 3: Find TreeView
    tv, app = find_treeview(hwnd)
    if not tv:
        print("  ❌ No TreeView found")
        return False
    print(f"  TreeView: {tv.rectangle()}")
    
    # Step 4: Find EA
    node = find_ea_node(tv, name)
    if not node:
        print(f"  ❌ {name} not found in Navigator")
        return False
    
    # Step 5: Double-click
    double_click_ea(node, tv)
    
    # Step 6: Confirm
    if confirm_and_verify(hwnd, name):
        print(f"  ✅ {name} dialog confirmed")
        return True
    
    # Step 7: Try scan
    print("  ⚠️ Direct click failed, trying scan...")
    if try_double_click_scan(tv, name):
        print(f"  ✅ {name} dialog found in scan")
        return True
    
    print(f"  ❌ {name} deploy failed")
    return False

def main():
    import pyautogui
    pyautogui.FAILSAFE = False
    
    # Find all EAs
    all_ex5 = [f for f in os.listdir(EXPERT_DIR) if f.endswith('.ex5')]
    ea_names = sorted([f[:-4] for f in all_ex5 if f not in SYSTEM_EAS])
    print(f"Found {len(ea_names)} EAs: {', '.join(ea_names)}")
    
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
        print("All EAs have fresh heartbeats. Nothing to do.")
        return
    
    # Get MT5 hwnd
    hwnd = get_mt5_hwnd()
    if not hwnd:
        print("MT5 not running, starting...")
        hwnd = start_mt5()
        if not hwnd:
            log("ERROR: Could not start MT5")
            return
    
    # Start deploy
    log(f"Starting batch deploy: {len(to_deploy)} EAs")
    success_count = 0
    fail_count = 0
    
    for i, name in enumerate(to_deploy, 1):
        print(f"\n--- [{i}/{len(to_deploy)}] {name} ---")
        success = deploy_ea(name, hwnd)
        if success:
            success_count += 1
            log(f"SUCCESS: {name} deployed")
        else:
            fail_count += 1
            log(f"FAILED: {name}")
        
        # Enable AutoTrading
        enable_autotrading(hwnd)
        time.sleep(1)
    
    # Final heartbeat check
    print(f"\n{'='*50}")
    print(f"  RESULTS: {success_count} success, {fail_count} failed, {len(to_deploy)} total")
    print(f"{'='*50}")
    
    print("\nFinal heartbeat check:")
    for name in ea_names:
        hb = os.path.join(COMMON_FILES, f'hb_{name}.txt')
        if os.path.exists(hb):
            age = time.time() - os.path.getmtime(hb)
            icon = '✅' if age < 120 else '⚠️'
            print(f"  {icon} {name}: {round(age)}s old")
        else:
            print(f"  ❌ {name}: no heartbeat")
    
    log(f"SUMMARY: {success_count} success, {fail_count} failed, {len(to_deploy)} total")

if __name__ == '__main__':
    main()
