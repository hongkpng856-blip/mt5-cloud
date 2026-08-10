"""
Deploy AgentHelper EA to bootstrap all other EAs.
Strategy:
1. Use WM_COMMAND (works from background) to open a new chart
2. Create AgentHelper_EURUSD_H1.tpl if not exists
3. Apply the template via ChartApplyTemplate functionality
4. Write command files for all 30 EAs
5. Wait for heartbeats
"""
import os, sys, time, ctypes, struct, glob

APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
COMMON_FILES = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')
EXPERT_DIR = os.path.join(MT5_DATA, 'MQL5', 'Experts')
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach_log.txt')
MT5_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'
PYTHON = r'C:\Users\hongk\AppData\Local\Programs\Python\Python311\python.exe'

SYSTEM_EAS = {'TestBlank.ex5', 'TemplateLoader.ex5', 'AgentHelper.ex5'}
TF_CODES = {
    'M1': 16385, 'M5': 16389, 'M15': 16401, 'M30': 16416,
    'H1': 32801, 'H4': 32805, 'D1': 49201, 'W1': 65601, 'MN1': 82001,
}

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)


def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def get_mt5_hwnd():
    return user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)


def get_mt5_pid():
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None


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
    main_hwnd = get_mt5_hwnd()
    if main_hwnd:
        user32.EnumChildWindows(ctypes.c_void_p(main_hwnd), CB(cb), 0)
    return results


def post_key(hwnd, vk):
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, vk, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, vk, 0)
    time.sleep(0.15)


def post_text(hwnd, text):
    for ch in text:
        user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0102, ord(ch), 0)
        time.sleep(0.03)
    time.sleep(0.3)


def post_ctrl_key(hwnd, vk):
    VK_CONTROL = 0x11
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, VK_CONTROL, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, vk, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, vk, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, VK_CONTROL, 0)
    time.sleep(0.3)


def send_wm_command(hwnd, cmd_id):
    """Send WM_COMMAND to main window - works from background."""
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0111, cmd_id, 0)
    time.sleep(1.5)


def open_new_chart_pm(hwnd):
    """Open chart using PostMessage Ctrl+N - more reliable from background."""
    print("  Opening new chart via PostMessage Ctrl+N...")
    
    # Try Ctrl+N
    post_ctrl_key(hwnd, ord('N'))
    mt5_pid = get_mt5_pid()
    dialogs = find_dialog(mt5_pid, 'MetaTrader')
    if dialogs:
        print(f"  Symbol dialog appeared: {dialogs[0][1]}")
        # Send EURUSD
        for h, title in dialogs:
            post_text(h, 'EURUSD')
            time.sleep(0.5)
            post_key(h, 0x0D)  # Enter
            time.sleep(3)
            print("  Chart created via Ctrl+N")
            return True
    
    # Try WM_COMMAND 57600 (File → New Chart)
    print("  Trying WM_COMMAND 57600 (File → New Chart)...")
    send_wm_command(hwnd, 57600)
    # Wait for symbol dialog
    time.sleep(3)
    mt5_pid = get_mt5_pid()
    dialogs = find_dialog(mt5_pid, 'MetaTrader')
    if dialogs:
        print(f"  Symbol dialog via WM_COMMAND: {dialogs[0][1]}")
        # Enter EURUSD and confirm
        for h, title in dialogs:
            post_text(h, 'EURUSD')
            time.sleep(0.5)
            post_key(h, 0x0D)
            time.sleep(3)
            print("  Chart created via WM_COMMAND")
            return True
    
    # Try WM_COMMAND 57601 or 57602 (other chart commands)
    for cmd in [57601, 57602, 33000, 33001]:
        send_wm_command(hwnd, cmd)
        time.sleep(2)
        dialogs = find_dialog(mt5_pid, 'MetaTrader')
        if dialogs:
            for h, title in dialogs:
                post_text(h, 'EURUSD')
                time.sleep(0.5)
                post_key(h, 0x0D)
                time.sleep(3)
                print(f"  Chart created via WM_COMMAND {cmd}")
                return True
    
    print("  ⚠️ Could not create new chart")
    return False


def apply_template_via_gui(ea_name, symbol='EURUSD', tf='H1'):
    """
    Apply EA template to a chart using GUI automation.
    Returns True if template applied successfully.
    """
    mt5_pid = get_mt5_pid()
    main_hwnd = get_mt5_hwnd()
    if not main_hwnd or not mt5_pid:
        print("  MT5 not found")
        return False
    
    # Generate template name
    tpl_name = f"{ea_name}_{symbol}_{tf}.tpl"
    tpl_path = os.path.join(TPL_DIR, tpl_name)
    if not os.path.exists(tpl_path):
        print(f"  Template not found: {tpl_path}")
        return False
    
    print(f"  Template exists: {tpl_name}")
    
    # Step 1: Open a new chart
    if not open_new_chart_pm(main_hwnd):
        print("  ⚠️ Cannot open new chart, trying existing...")
    
    # Step 2: Find the chart window and drop template on it
    # The chart window is typically an MDIClient class
    import pyautogui
    from pywinauto import Application
    
    try:
        app = Application(backend='win32').connect(process=mt5_pid)
        
        # Find chart area - look for MDIClient window
        chart_area = None
        for d in app.top_window().descendants():
            cn = d.element_info.class_name
            if 'MDIClient' in cn:
                chart_area = d
                break
        
        if not chart_area:
            # Try finding any visible chart-like window
            for d in app.top_window().descendants():
                cn = d.element_info.class_name
                if cn == '#32770' and d.is_visible():
                    continue
                rect = d.rectangle()
                # Chart windows are typically large (main area)
                if rect.width() > 400 and rect.height() > 200:
                    chart_area = d
                    break
        
        if chart_area:
            rect = chart_area.rectangle()
            cx = (rect.left + rect.right) // 2
            cy = (rect.top + rect.bottom) // 2
            print(f"  Chart area at ({cx}, {cy}) size={rect.width()}x{rect.height()}")
            
            # Right-click on chart to open context menu
            user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
            time.sleep(0.5)
            pyautogui.click(x=cx, y=cy, button='right')
            time.sleep(1.5)
            
            # Find popup menu (#32768)
            menus = []
            pid_buf = ctypes.c_ulong()
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
                print(f"  Chart context menu found: {[hex(m) for m in menus]}")
                menu_hwnd = menus[0]
                
                # Press 'T' for Template (standard MT5 accelerator)
                post_key(menu_hwnd, ord('T'))
                time.sleep(1)
                
                # Now look for submenu... Template menu might open a submenu
                # Press 'A' for Apply Template
                post_key(menu_hwnd, ord('A'))
                time.sleep(2)
                
                # Check for file dialog
                dialogs = find_dialog(mt5_pid)
                for h, title in dialogs:
                    print(f"  Dialog: '{title}'")
                
                # If a file dialog appeared, type template name and enter
                file_dialogs = []
                def find_file_dlg(hwnd, _):
                    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
                    if pid_buf.value == mt5_pid:
                        cls = ctypes.create_unicode_buffer(256)
                        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                        if cls.value in ['#32770', 'ComboBox', 'Edit']:
                            title = ctypes.create_unicode_buffer(256)
                            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                            if 'Open' in title.value or 'Apply' in title.value or 'Template' in title.value:
                                file_dialogs.append((hwnd, title.value, cls.value))
                    return True
                time.sleep(1)
                user32.EnumWindows(CB(find_file_dlg), 0)
                
                if file_dialogs:
                    print(f"  File dialog: {file_dialogs}")
                    # Type template name
                    for h, title, cls in file_dialogs:
                        if cls == '#32770':
                            post_text(h, tpl_name)
                            time.sleep(0.5)
                            post_key(h, 0x0D)  # Enter to open
                            time.sleep(3)
                            print(f"  Template dialog submitted")
                            break
                
                # Handle Replace dialog
                time.sleep(2)
                for _ in range(10):
                    dialogs = find_dialog(mt5_pid)
                    replaced = False
                    for h, title in dialogs:
                        if '代替' in title or 'replace' in title.lower():
                            print(f"  Replace dialog: '{title}' -> Accepting")
                            post_key(h, ord('Y'))  # Yes
                            time.sleep(2)
                            replaced = True
                            break
                        if 'Properties' in title or ea_name in title:
                            print(f"  Properties dialog: '{title}' -> Confirming")
                            post_key(h, 0x0D)  # Enter
                            time.sleep(2)
                            replaced = True
                            break
                    if replaced:
                        break
                    time.sleep(1)
                else:
                    print("  No dialog detected after template apply")
                
                # Try toggling AutoTrading
                post_ctrl_key(main_hwnd, ord('E'))
                time.sleep(1)
                print("  Template application sequence completed")
                return True
            else:
                print("  No context menu found")
                # Fallback: try drag-and-drop of .tpl file onto chart
                # This uses shell drag-drop which is complex
        else:
            print("  No chart area found")
    except Exception as e:
        print(f"  Error: {e}")
    
    return False


def generate_agenthelper_template():
    """Generate AgentHelper template by running auto_attach.py briefly."""
    import subprocess
    tpl_path = os.path.join(TPL_DIR, 'AgentHelper_EURUSD_H1.tpl')
    if os.path.exists(tpl_path):
        age = time.time() - os.path.getmtime(tpl_path)
        if age < 300:  # Less than 5 min old
            print(f"  AgentHelper template already exists ({round(age)}s old)")
            return tpl_path
    
    print("  Generating AgentHelper template...")
    cmd = [PYTHON, '-u', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach.py'),
           '--ea', 'AgentHelper', '--symbol', 'EURUSD', '--tf', 'H1']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            cwd=os.path.dirname(os.path.abspath(__file__)))
    try:
        out, _ = proc.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
    
    if os.path.exists(tpl_path):
        print(f"  ✅ AgentHelper template generated: {tpl_path}")
        return tpl_path
    print("  ❌ Failed to generate AgentHelper template")
    return None


def write_agent_helper_command(ea_name, symbol='EURUSD', tf='H1'):
    """Write a command file for AgentHelper to process."""
    cmd_path = os.path.join(COMMON_FILES, 'agent_helper.txt')
    content = f"{ea_name},{symbol},{tf}"
    with open(cmd_path, 'w') as f:
        f.write(content)
    print(f"  📝 Wrote command: {content}")
    return cmd_path


def check_heartbeat(ea_name):
    hb = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
    if os.path.exists(hb):
        age = time.time() - os.path.getmtime(hb)
        return age < 60, age
    return False, None


def wait_for_heartbeat(ea_name, timeout=120):
    """Wait for heartbeat file to appear and be fresh."""
    start = time.time()
    while time.time() - start < timeout:
        fresh, age = check_heartbeat(ea_name)
        if fresh:
            return True, age
        time.sleep(5)
    return False, None


def main():
    print("=" * 60)
    print(f"  DEPLOY AGENTHELPER   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    mt5_pid = get_mt5_pid()
    if not mt5_pid:
        print("❌ MT5 not running")
        log("FAILED: MT5 not running")
        return
    
    print(f"✅ MT5 running (PID={mt5_pid})")
    
    # Check if AgentHelper is already running
    fresh, age = check_heartbeat('AgentHelper')
    if fresh:
        print(f"✅ AgentHelper already running (heartbeat {age:.0f}s old)")
    else:
        print(f"🚀 AgentHelper needs deployment ({'no heartbeat' if age is None else f'{age:.0f}s old'})")
        
        # First, generate the template
        tpl = generate_agenthelper_template()
        if not tpl:
            log("FAILED: Could not generate AgentHelper template")
            return
        
        # Try to deploy AgentHelper via GUI automation
        log(f"Deploying AgentHelper...")
        success = apply_template_via_gui('AgentHelper')
        if success:
            # Wait for heartbeat
            ok, hb_age = wait_for_heartbeat('AgentHelper', timeout=90)
            if ok:
                print(f"✅ AgentHelper deployed and running (heartbeat {hb_age:.0f}s)")
                log(f"SUCCESS: AgentHelper deployed")
            else:
                print("⚠️ AgentHelper deployed but heartbeat not detected")
                log(f"WARNING: AgentHelper deployed but no heartbeat")
        else:
            print("❌ AgentHelper deployment failed")
            log("FAILED: AgentHelper deployment failed")
            return
    
    # Now use AgentHelper to deploy all other EAs
    all_ex5 = sorted(glob.glob(os.path.join(EXPERT_DIR, '*.ex5')))
    ea_names = sorted([os.path.basename(f)[:-4] for f in all_ex5
                       if os.path.basename(f) not in SYSTEM_EAS])
    
    print(f"\n📋 Deploying {len(ea_names)} EAs via AgentHelper...")
    
    success_count = 0
    fail_count = 0
    
    for i, ea in enumerate(ea_names, 1):
        # Check if already running
        fresh, age = check_heartbeat(ea)
        if fresh:
            print(f"  ✅ [{i}/{len(ea_names)}] {ea}: already running (heartbeat {age:.0f}s)")
            success_count += 1
            continue
        
        print(f"  🚀 [{i}/{len(ea_names)}] {ea}: sending to AgentHelper...")
        
        # Write command for this EA
        write_agent_helper_command(ea)
        
        # Wait for heartbeat
        ok, hb_age = wait_for_heartbeat(ea, timeout=120)
        if ok:
            print(f"    ✅ Heartbeat detected after {hb_age:.0f}s")
            success_count += 1
            log(f"SUCCESS: {ea} deployed via AgentHelper")
        else:
            print(f"    ❌ No heartbeat within timeout")
            fail_count += 1
            log(f"FAILED: {ea} via AgentHelper")
        
        time.sleep(1)
    
    # Summary
    print(f"\n{'='*50}")
    print(f"  RESULTS: {success_count} success, {fail_count} failed")
    print(f"  Total: {success_count + fail_count} EAs")
    print(f"{'='*50}")
    
    log(f"SUMMARY: {success_count} success, {fail_count} failed, total={success_count + fail_count}")


if __name__ == '__main__':
    main()
