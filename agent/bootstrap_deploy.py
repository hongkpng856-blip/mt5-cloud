"""
Direct approach: use Alt+F → N to open chart, deploy AgentHelper via command file.
All keyboard via PostMessage (works from background).
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
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach_log.txt')

SYSTEM_EAS = {'TestBlank.ex5', 'TemplateLoader.ex5', 'AgentHelper.ex5'}


def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def close_all_dialogs(mt5_pid):
    """Close any open dialogs in MT5."""
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
                    print(f"  Closing dialog: '{title.value}' 0x{hwnd:08X}")
                    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)
                    closed += 1
        return True
    user32.EnumWindows(CB(enum), 0)
    time.sleep(1)
    return closed


def get_mt5_pid():
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None


def post_key(hwnd, vk):
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, vk, 0)
    time.sleep(0.03)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, vk, 0)
    time.sleep(0.1)


def post_syskey(hwnd, vk):
    """Send Alt+Key via WM_SYSKEYDOWN/UP"""
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0104, vk, 0)  # WM_SYSKEYDOWN
    time.sleep(0.1)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0105, vk, 0)  # WM_SYSKEYUP
    time.sleep(0.3)


def post_text(hwnd, text):
    for ch in text:
        user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0102, ord(ch), 0)
        time.sleep(0.03)
    time.sleep(0.3)


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


def open_chart_alt_f_n(main_hwnd, mt5_pid):
    """Open chart using Alt+F → N (File → New Chart) via PostMessage"""
    print("  Opening chart via Alt+F, N...")
    
    # Alt+F
    post_syskey(main_hwnd, ord('F'))
    time.sleep(1)
    
    # Check for dialog after Alt+F (File menu opened)
    # Press N for New Chart
    post_key(main_hwnd, ord('N'))
    time.sleep(2)
    
    # Check for symbol dialog
    dialogs = find_dialog(mt5_pid, 'MetaTrader 5')
    if dialogs:
        print(f"  'New Chart' dialog appeared: '{dialogs[0][1]}'")
        # Type EURUSD
        post_text(dialogs[0][0], 'EURUSD')
        time.sleep(0.5)
        post_key(dialogs[0][0], 0x0D)  # Enter
        time.sleep(3)
        print("  ✅ Chart opened via Alt+F → N")
        return True
    
    # Try with direct WM_CHAR for the 'n' on the menu
    print("  Alt+F didn't work, trying Alt+F, Down, Enter...")
    user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0112, 0xF100, 0)  # SC_KEYMENU
    time.sleep(0.5)
    post_key(main_hwnd, ord('F'))
    time.sleep(1)
    # N is New Chart
    post_key(main_hwnd, ord('N'))
    time.sleep(2)
    
    dialogs = find_dialog(mt5_pid, 'MetaTrader 5')
    if dialogs:
        post_text(dialogs[0][0], 'EURUSD')
        time.sleep(0.5)
        post_key(dialogs[0][0], 0x0D)
        time.sleep(3)
        print("  ✅ Chart opened via SC_KEYMENU + F + N")
        return True
    
    print("  ⚠️ Could not open chart via Alt+F+N")
    return False


def open_chart_via_market_watch():
    """Try opening chart via Market Watch right-click (mouse only)."""
    import pyautogui
    from pywinauto import Application
    
    mt5_pid = get_mt5_pid()
    app = Application(backend='win32').connect(process=mt5_pid)
    
    # Find Market Watch window
    mw = None
    for w in app.windows(class_name_re='.*MiniFrame.*'):
        try:
            t = w.window_text()
            if '市場報價' in t or 'Market Watch' in t or 'Market' in t:
                mw = w
                break
        except:
            pass
    
    if not mw:
        print("  Market Watch not found")
        return False
    
    rect = mw.rectangle()
    cx = rect.left + 50
    cy = rect.top + 30
    print(f"  Market Watch at ({rect.left},{rect.top})-({rect.right},{rect.bottom})")
    
    # Right-click on Market Watch
    pyautogui.click(x=cx, y=cy, button='right')
    time.sleep(1.5)
    
    # Click "Chart Window" option in context menu
    # The context menu should appear near the click position
    # "Chart Window" is typically the first item
    pyautogui.click(x=cx, y=cy)
    time.sleep(3)
    
    # Check for symbol dialog
    dialogs = find_dialog(mt5_pid, 'MetaTrader 5')
    if dialogs:
        print(f"  Chart window opened via Market Watch")
        return True
    return False


def attach_ea_via_template(ea_name, symbol='EURUSD', tf='H1'):
    """
    Use the chart's context menu (right-click → Template → Apply Template)
    to attach an EA. This is all mouse-based (works from background).
    """
    import pyautogui
    from pywinauto import Application
    
    mt5_pid = get_mt5_pid()
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    app = Application(backend='win32').connect(process=mt5_pid)
    
    # Step 1: Open a new chart first
    if not open_chart_alt_f_n(main_hwnd, mt5_pid):
        if not open_chart_via_market_watch():
            print("  ⚠️ Cannot open new chart")
            return False
    
    # Step 2: Find the chart area and right-click
    chart_rect = None
    for d in app.top_window().descendants():
        cn = d.element_info.class_name
        if cn == 'MDIClient' and d.is_visible():
            chart_rect = d.rectangle()
            break
    
    if not chart_rect:
        print("  ⚠️ No chart area found")
        return False
    
    cx = chart_rect.mid_point().x
    cy = chart_rect.mid_point().y
    print(f"  Chart area at ({cx}, {cy})")
    
    # Right-click on chart
    user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
    time.sleep(0.3)
    pyautogui.click(x=cx, y=cy, button='right')
    time.sleep(1.5)
    
    # Step 3: Navigate context menu → Template → Apply Template
    # The context menu appears near the click point
    # Menu items are at known offsets from the click point
    
    # In MT5 English, the context menu has "Template" option
    # The menu items are spaced ~20px apart
    # "Template" is typically around the 8th item from top (scroll position dependent)
    
    # Try using keyboard to navigate the menu (PostMessage to active menu)
    # Find popup menu window
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
    
    if menus:
        menu_hwnd = menus[0]
        print(f"  Context menu found: 0x{menu_hwnd:08X}")
        
        # The context menu has keyboard accelerators:
        # In Chinese MT5, the chart context menu items might be:
        # T = 範本 (Template)
        # Then in Template submenu: A = 套用範本 (Apply Template)
        
        # Try 'T' for Template
        post_key(menu_hwnd, ord('T'))
        time.sleep(1.5)
        
        # Now Type 'A' for Apply Template
        post_key(menu_hwnd, ord('A'))
        time.sleep(2)
    else:
        print("  No context menu found, trying mouse click approach...")
        # Fallback: click at estimated menu positions
        
        # Try clicking on "Template" option (approximately 7-8 items down, ~20px each)
        # First click offset: cx+50, cy+20 (first menu item)
        # Template is roughly at offset cy+140
        pyautogui.moveTo(cx + 80, cy + 140)
        time.sleep(0.5)
        
        # Check if a submenu appeared
        menus2 = []
        def find_menu2(hwnd, _):
            user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
            if pid_buf.value == mt5_pid:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                if '#32768' in cls.value:
                    menus2.append(hwnd)
            return True
        user32.EnumWindows(CB(find_menu2), 0)
        
        if len(menus2) > 1:
            print(f"  Submenu appeared ({len(menus2)} menus)")
            # Click on second menu's "Apply Template" item
            # Apply Template is usually the first item in Template submenu
            pyautogui.click(x=cx + 150, y=cy + 140)
            time.sleep(1)
    
    # Step 4: Check for file dialog
    time.sleep(2)
    dialogs = find_dialog(mt5_pid)
    for h, title in dialogs:
        print(f"  Dialog: '{title}'")
    
    # Look for file open dialog (Open Template)
    file_dlg = None
    for h, title in dialogs:
        if 'Open' in title or '開' in title:
            file_dlg = h
            break
    
    if file_dlg:
        print(f"  File Open dialog found! Typing template name...")
        # Type template name
        tpl_name = f"{ea_name}_{symbol}_{tf}.tpl"
        post_text(file_dlg, tpl_name)
        time.sleep(0.5)
        post_key(file_dlg, 0x0D)  # Enter
        time.sleep(3)
        
        # Handle Replace dialog if needed
        for _ in range(10):
            d = find_dialog(mt5_pid)
            replaced = False
            for h, title in d:
                if '代替' in title or 'replace' in title.lower():
                    print(f"  Replace dialog: '{title}' -> Yes")
                    post_key(h, ord('Y'))
                    time.sleep(2)
                    replaced = True
                    break
                if ea_name in title or 'Properties' in title:
                    print(f"  Properties dialog: '{title}' -> Confirm")
                    post_key(h, 0x0D)
                    time.sleep(2)
                    replaced = True
                    break
            if replaced:
                break
            time.sleep(1)
        
        print(f"  ✅ Template applied for {ea_name}")
        return True
    
    # If no file dialog, try another approach - use the template list
    # In MT5, the Apply Template menu might show a template list directly
    # Try clicking on the template in the menu
    
    print("  ⚠️ No File Open dialog detected")
    return False


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


def write_agent_helper_cmd(ea_name, symbol='EURUSD', tf='H1'):
    cmd_path = os.path.join(COMMON_FILES, 'agent_helper.txt')
    with open(cmd_path, 'w') as f:
        f.write(f"{ea_name},{symbol},{tf}")
    print(f"  📝 Wrote: {ea_name},{symbol},{tf}")


def main():
    print("=" * 60)
    print(f"  BOOTSTRAP DEPLOY   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    mt5_pid = get_mt5_pid()
    if not mt5_pid:
        print("❌ MT5 not running")
        return
    
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    print(f"✅ MT5 PID={mt5_pid}, HWND=0x{main_hwnd:08X}")
    
    # Close any lingering dialogs first
    closed = close_all_dialogs(mt5_pid)
    if closed:
        print(f"  Closed {closed} dialog(s)")
    
    # Get EA list
    all_ex5 = sorted(glob.glob(os.path.join(EXPERT_DIR, '*.ex5')))
    ea_names = sorted([os.path.basename(f)[:-4] for f in all_ex5
                       if os.path.basename(f) not in SYSTEM_EAS])
    print(f"📋 Found {len(ea_names)} EAs")
    
    # Check which need deployment
    to_deploy = []
    for ea in ea_names:
        fresh, age = check_heartbeat(ea)
        if fresh:
            print(f"  ✅ {ea}: running (heartbeat {age:.0f}s)")
        else:
            reason = f"no heartbeat" if age is None else f"{age:.0f}s old"
            print(f"  🚀 {ea}: {reason}")
            to_deploy.append(ea)
    
    if not to_deploy:
        print("\n✅ All EAs already running!")
        return
    
    print(f"\n📋 {len(to_deploy)} EAs need deployment")
    
    # First, deploy AgentHelper (bootstrapping)
    if check_heartbeat('AgentHelper')[0]:
        print("✅ AgentHelper already running")
    else:
        print("\n🚀 Deploying AgentHelper...")
        
        # Generate template if needed
        tpl_dir = os.path.join(MT5_DATA, 'Profiles', 'Templates')
        tpl_path = os.path.join(tpl_dir, 'AgentHelper_EURUSD_H1.tpl')
        if not os.path.exists(tpl_path):
            print("  Generating AgentHelper template via auto_attach.py...")
            import subprocess
            PYTHON = r'C:\Users\hongk\AppData\Local\Programs\Python\Python311\python.exe'
            script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach.py')
            proc = subprocess.Popen(
                [PYTHON, '-u', script, '--ea', 'AgentHelper', '--symbol', 'EURUSD', '--tf', 'H1'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                proc.communicate(timeout=10)
            except:
                proc.kill()
                proc.communicate()
        
        if not os.path.exists(tpl_path):
            print("  ❌ Failed to generate AgentHelper template")
            log("FAILED: AgentHelper template generation failed")
            return
        
        print(f"  ✅ AgentHelper template exists")
        
        # Try to deploy AgentHelper by applying template to a chart
        success = attach_ea_via_template('AgentHelper')
        
        if success:
            ok, age = wait_for_heartbeat('AgentHelper', timeout=90)
            if ok:
                print(f"  ✅ AgentHelper running!")
                log("SUCCESS: AgentHelper deployed")
            else:
                print(f"  ⚠️ AgentHelper deployed but no heartbeat yet")
        else:
            print(f"  ❌ AgentHelper deployment failed")
    
    # If AgentHelper is running, use it for all other EAs
    if check_heartbeat('AgentHelper')[0]:
        print(f"\n🚀 Using AgentHelper to deploy {len(to_deploy)} EAs...")
        
        success_count = 0
        fail_count = 0
        
        for i, ea in enumerate(to_deploy, 1):
            if ea == 'AgentHelper':
                continue
            
            # Check again (might have been deployed already)
            if check_heartbeat(ea)[0]:
                print(f"  ✅ [{i}/{len(to_deploy)}] {ea}: already running")
                success_count += 1
                continue
            
            # Write command for AgentHelper
            write_agent_helper_cmd(ea)
            
            # Wait for heartbeat
            ok, age = wait_for_heartbeat(ea, timeout=120)
            if ok:
                print(f"  ✅ [{i}/{len(to_deploy)}] {ea}: deployed (heartbeat {age:.0f}s)")
                success_count += 1
                log(f"SUCCESS: {ea} via AgentHelper")
            else:
                print(f"  ❌ [{i}/{len(to_deploy)}] {ea}: no heartbeat")
                fail_count += 1
                log(f"FAILED: {ea} via AgentHelper - no heartbeat")
        
        print(f"\n{'='*50}")
        print(f"  RESULTS: {success_count} success, {fail_count} failed")
        print(f"{'='*50}")
        log(f"SUMMARY: {success_count} success, {fail_count} failed via AgentHelper")
    else:
        print("\n❌ AgentHelper not running - cannot deploy other EAs")
        
        # Fallback: try deploying individual EAs directly
        print("\n🔄 Trying direct deployment via auto_attach.py...")
        import subprocess
        PYTHON = r'C:\Users\hongk\AppData\Local\Programs\Python\Python311\python.exe'
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach.py')
        
        success_count = 0
        fail_count = 0
        
        for i, ea in enumerate(to_deploy[:5], 1):  # First 5 only
            print(f"\n  [{i}/{min(5, len(to_deploy))}] {ea}...")
            cmd = [PYTHON, '-u', script, '--ea', ea, '--symbol', 'EURUSD', '--tf', 'H1']
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                out, _ = proc.communicate(timeout=120)
                output = out.decode('utf-8', errors='replace')
                if 'SUCCESS' in output and proc.returncode == 0:
                    print(f"  ✅ {ea}: SUCCESS")
                    success_count += 1
                    log(f"SUCCESS: {ea} direct deploy")
                else:
                    print(f"  ❌ {ea}: FAILED (returncode={proc.returncode})")
                    fail_count += 1
                    log(f"FAILED: {ea} direct deploy - returncode={proc.returncode}")
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                print(f"  ❌ {ea}: TIMEOUT")
                fail_count += 1
                log(f"FAILED: {ea} direct deploy - timeout")
        
        print(f"\n  Direct deploy: {success_count} success, {fail_count} failed")


if __name__ == '__main__':
    main()
