"""
Strategy:
1. Open Navigator panel via WM_COMMAND 32845 (View → Navigator)
2. Navigate to EA node
3. Right-click → context menu → WM_CHAR for menu items
4. Apply template
"""
import os, sys, time, ctypes, glob
from ctypes import wintypes

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
COMMON_FILES = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')
EXPERT_DIR = os.path.join(MT5_DATA, 'MQL5', 'Experts')
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach_log.txt')
SYSTEM_EAS = {'TestBlank.ex5', 'TemplateLoader.ex5', 'AgentHelper.ex5'}

PYTHON = r'C:\Users\hongk\AppData\Local\Programs\Python\Python311\python.exe'

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


def close_all_dialogs(mt5_pid):
    pid_buf = ctypes.c_ulong()
    closed = 0
    def enum(hwnd, _):
        nonlocal closed
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if title.value:
                    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)
                    closed += 1
        return True
    user32.EnumWindows(CB(enum), 0)
    time.sleep(0.5)
    return closed


def find_dialogs(mt5_pid):
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
                if title.value:
                    results.append((hwnd, title.value))
        return True
    user32.EnumWindows(CB(cb), 0)
    return results


def check_heartbeat(ea_name):
    hb = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
    if os.path.exists(hb):
        age = time.time() - os.path.getmtime(hb)
        return age < 60, age
    return False, None


def wait_for_heartbeat(ea_name, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        fresh, age = check_heartbeat(ea_name)
        if fresh:
            return True, age
        time.sleep(3)
    return False, None


def post_key(hwnd, vk):
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, vk, 0)
    time.sleep(0.03)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, vk, 0)
    time.sleep(0.1)


def post_char(hwnd, ch):
    """Send WM_CHAR for accelerator navigation in menus."""
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0102, ord(ch), 0)
    time.sleep(0.3)


def post_syskey(hwnd, vk):
    """Send Alt+Key"""
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0104, vk, 0)
    time.sleep(0.1)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0105, vk, 0)
    time.sleep(0.3)


def send_wm_command(hwnd, cmd_id):
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0111, cmd_id, 0)
    time.sleep(1.5)


def open_navigator(main_hwnd):
    """Open Navigator panel using WM_COMMAND 32845 (View → Navigator)."""
    print("  Opening Navigator panel...")
    # From our earlier menu scan: ID=32845 for View → Navigator
    send_wm_command(main_hwnd, 32845)
    time.sleep(2)
    
    # Check if Navigator appeared
    import psutil
    mt5_pid = get_mt5_pid()
    pid_buf = ctypes.c_ulong()
    navs = []
    def find_nav(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if 'MiniFrame' in cls.value:
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if '導航' in title.value or 'Navigator' in title.value:
                    navs.append((hwnd, title.value))
        return True
    user32.EnumWindows(CB(find_nav), 0)
    
    if navs:
        print(f"  Navigator panel visible")
        return True
    else:
        print(f"  Navigator not visible after WM_COMMAND")
        return False


def get_ea_position(ea_name):
    """Find the screen position of an EA in the Navigator TreeView."""
    mt5_pid = get_mt5_pid()
    from pywinauto import Application
    
    try:
        app = Application(backend='win32').connect(process=mt5_pid)
    except:
        return None, None
    
    # Ensure Navigator is visible
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    open_navigator(main_hwnd)
    
    # Find TreeView
    tv = None
    pid_buf = ctypes.c_ulong()
    nav_hwnd = None
    
    def find_nav(hwnd, _):
        nonlocal nav_hwnd
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if 'MiniFrame' in cls.value:
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if '導航' in title.value or 'Navigator' in title.value:
                    nav_hwnd = hwnd
        return True
    user32.EnumWindows(CB(find_nav), 0)
    
    # Search for TreeView
    search_handles = []
    search_handles.append(app.top_window().element_info.handle)
    if nav_hwnd:
        search_handles.append(nav_hwnd)
    
    for h in search_handles:
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
    
    # Find EA node
    try:
        root = tv.roots()[0]
        kids = root.children()
        ea_section = kids[2] if len(kids) > 2 else None
        if not ea_section:
            for c in kids:
                t = c.text()
                if any(x in t for x in ['EA交易', 'Expert Advisors', 'Experts', 'EA']):
                    ea_section = c
                    break
        if not ea_section:
            print("  EA section not found")
            return None, None
        
        ea_section.expand()
        time.sleep(1.5)
        
        for ea in ea_section.children():
            if ea.text() == ea_name:
                try:
                    pr = ea.client_rect()
                    cx = tv_rect.left + (pr.left + pr.right) // 2
                    cy = tv_rect.top + (pr.top + pr.bottom) // 2
                    print(f"  Found {ea_name} at ({cx}, {cy})")
                    return cx, cy
                except:
                    print(f"  Found {ea_name} but no rect")
                    return tv_rect.left + 66, tv_rect.top + 10
        print(f"  {ea_name} not found in EA section")
        return None, None
    except Exception as e:
        print(f"  TreeView error: {e}")
        return None, None


def right_click_and_deploy(ea_name, cx, cy):
    """Right-click on EA and navigate context menu to deploy."""
    import pyautogui
    mt5_pid = get_mt5_pid()
    
    # Ensure main window has some focus
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    
    # Right-click at the EA position
    print(f"  Right-click at ({cx}, {cy})")
    pyautogui.click(x=cx, y=cy, button='right')
    time.sleep(2)
    
    # Find context menu
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
    
    if not menus:
        print("  No context menu found")
        return False
    
    menu_hwnd = menus[0]
    print(f"  Context menu: 0x{menu_hwnd:08X}")
    
    # Get menu items to see what's available
    item_count = user32.GetMenuItemCount(ctypes.c_void_p(menu_hwnd))
    print(f"  Menu items: {item_count}")
    for i in range(min(item_count, 20)):
        buf = ctypes.create_unicode_buffer(256)
        ret = user32.GetMenuStringW(ctypes.c_void_p(menu_hwnd), i, buf, 255, 0x0400)
        if ret > 0:
            mid = user32.GetMenuItemID(ctypes.c_void_p(menu_hwnd), i)
            sub = user32.GetSubMenu(ctypes.c_void_p(menu_hwnd), i)
            sub_str = " → SUB" if sub else ""
            print(f"    [{i}] '{buf.value}' ID={mid}{sub_str}")
    
    # Strategy: In Chinese MT5, right-click on EA in Navigator shows:
    # In our Chinese MT5: 附加到圖表 (Attach to Chart), 屬性 (Properties), 刪除 (Delete), etc.
    # Let's try pressing Enter for the first item (usually "Attach to Chart")
    
    # First, try WM_CHAR with the accelerator.
    # In the Chinese menu, the accelerators are shown with &:
    # 附加到圖表(&A) -> 'A'
    # Let's try a few common accelerators
    
    success = False
    for char_to_try in ['A', 'a', 'T', 't', 'P', 'p', 'E', 'e']:
        print(f"  Trying '{char_to_try}'...")
        post_char(menu_hwnd, char_to_try)
        time.sleep(2)
        
        dialogs = find_dialogs(mt5_pid)
        for h, title in dialogs:
            if ea_name in title or '代替' in title or 'replace' in title.lower() or 'Properties' in title:
                print(f"  ✅ Dialog after '{char_to_try}': '{title}'")
                success = True
                break
        if success:
            break
    
    if not success:
        # Try Enter (first item)
        print("  Trying Enter (first menu item)...")
        post_key(menu_hwnd, 0x0D)
        time.sleep(2)
        dialogs = find_dialogs(mt5_pid)
        for h, title in dialogs:
            if ea_name in title or '代替' in title or 'replace' in title.lower() or 'Properties' in title:
                print(f"  ✅ Dialog after Enter: '{title}'")
                success = True
                break
    
    if success:
        # Handle dialog: confirm properties or replace
        for _ in range(10):
            dialogs = find_dialogs(mt5_pid)
            handled = False
            for h, title in dialogs:
                if '代替' in title or 'replace' in title.lower():
                    print(f"  Replace dialog: Yes")
                    # Click Yes button
                    ok_btns = []
                    def find_btn(chwnd, _):
                        ccls = ctypes.create_unicode_buffer(256)
                        user32.GetClassNameW(ctypes.c_void_p(chwnd), ccls, 256)
                        if ccls.value == 'Button':
                            ctitle = ctypes.create_unicode_buffer(256)
                            user32.GetWindowTextW(ctypes.c_void_p(chwnd), ctitle, 256)
                            if 'Yes' in ctitle.value or '是' in ctitle.value:
                                ok_btns.append(chwnd)
                        return True
                    user32.EnumChildWindows(ctypes.c_void_p(h), CB(find_btn), 0)
                    if ok_btns:
                        user32.SendMessageW(ctypes.c_void_p(ok_btns[0]), 0x00F5, 0, 0)
                    else:
                        post_key(h, ord('Y'))
                    time.sleep(2)
                    handled = True
                    break
                if ea_name in title or 'Properties' in title:
                    print(f"  Properties dialog: OK")
                    ok_btns = []
                    def find_btn2(chwnd, _):
                        ccls = ctypes.create_unicode_buffer(256)
                        user32.GetClassNameW(ctypes.c_void_p(chwnd), ccls, 256)
                        if ccls.value == 'Button':
                            ctitle = ctypes.create_unicode_buffer(256)
                            user32.GetWindowTextW(ctypes.c_void_p(chwnd), ctitle, 256)
                            if 'OK' in ctitle.value or '確定' in ctitle.value:
                                ok_btns2.append(chwnd)
                        return True
                    ok_btns2 = []
                    user32.EnumChildWindows(ctypes.c_void_p(h), CB(find_btn2), 0)
                    if ok_btns2:
                        user32.SendMessageW(ctypes.c_void_p(ok_btns2[0]), 0x00F5, 0, 0)
                    else:
                        post_key(h, 0x0D)
                    time.sleep(2)
                    handled = True
                    break
            if not handled:
                break
            time.sleep(1)
        
        print(f"  ✅ {ea_name} deployed via right-click")
        return True
    
    print(f"  ❌ Could not deploy {ea_name}")
    return False


def generate_template(ea_name, symbol='EURUSD', tf='H1'):
    """Generate .tpl template if needed."""
    import subprocess
    tpl_path = os.path.join(TPL_DIR, f"{ea_name}_{symbol}_{tf}.tpl")
    if os.path.exists(tpl_path):
        return tpl_path
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach.py')
    proc = subprocess.Popen([PYTHON, '-u', script, '--ea', ea_name, '--symbol', symbol, '--tf', tf],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        proc.communicate(timeout=10)
    except:
        proc.kill()
        proc.communicate()
    return tpl_path if os.path.exists(tpl_path) else None


def main():
    print("=" * 60)
    print(f"  DEPLOY VIA RIGHT-CLICK  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    mt5_pid = get_mt5_pid()
    if not mt5_pid:
        print("❌ MT5 not running")
        return
    
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    print(f"✅ MT5 PID={mt5_pid} HWND=0x{main_hwnd:08X}")
    
    # Close dialogs
    closed = close_all_dialogs(mt5_pid)
    if closed:
        print(f"  Closed {closed} dialog(s)")
    
    # Get EA list
    all_ex5 = sorted(glob.glob(os.path.join(EXPERT_DIR, '*.ex5')))
    ea_names = sorted([os.path.basename(f)[:-4] for f in all_ex5
                       if os.path.basename(f) not in SYSTEM_EAS])
    print(f"📋 {len(ea_names)} EAs")
    
    # Check heartbeats
    to_deploy = []
    for ea in ea_names:
        fresh, age = check_heartbeat(ea)
        if fresh:
            print(f"  ✅ {ea}: running")
        else:
            reason = "no heartbeat" if age is None else f"{age:.0f}s"
            print(f"  🚀 {ea}: {reason}")
            to_deploy.append(ea)
    
    if not to_deploy:
        print("\n✅ All running!")
        return
    
    print(f"\n📋 Deploying {len(to_deploy)} EAs")
    
    # Try deploying each EA
    success_count = 0
    fail_count = 0
    
    for i, ea in enumerate(to_deploy, 1):
        print(f"\n--- [{i}/{len(to_deploy)}] {ea} ---")
        
        # Generate template if needed
        generate_template(ea)
        
        # Find EA position
        cx, cy = get_ea_position(ea)
        if cx is None or cy is None:
            print(f"  ❌ Cannot find {ea} in Navigator")
            fail_count += 1
            log(f"FAILED: {ea} - not found in Navigator")
            continue
        
        # Deploy via right-click
        result = right_click_and_deploy(ea, cx, cy)
        
        if result:
            ok, age = wait_for_heartbeat(ea, timeout=60)
            if ok:
                print(f"  ✅ {ea}: DEPLOYED (heartbeat {age:.0f}s)")
                success_count += 1
                log(f"SUCCESS: {ea} deployed via right-click")
            else:
                print(f"  ⚠️ {ea}: attached but no heartbeat yet")
                success_count += 1
                log(f"SUCCESS: {ea} attached (no heartbeat)")
        else:
            print(f"  ❌ {ea}: FAILED")
            fail_count += 1
            log(f"FAILED: {ea} via right-click")
        
        # Brief pause
        time.sleep(2)
    
    # Summary
    print(f"\n{'='*50}")
    print(f"  RESULTS: {success_count} success, {fail_count} failed")
    print(f"{'='*50}")
    
    # Final heartbeat check
    running = sum(1 for ea in ea_names if check_heartbeat(ea)[0])
    log(f"SUMMARY: {success_count} success, {fail_count} failed")
    log(f"Running with heartbeat: {running}/{len(ea_names)}")


if __name__ == '__main__':
    main()
