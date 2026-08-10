"""Deploy AgentHelper via ShellExecute on .tpl file.
This triggers MT5 to open New Chart dialog with the template pre-loaded.
Then we send EURUSD + Enter via PostMessage."""
import os, sys, time, ctypes, glob

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'D0E8209F77C8CF37AD8BF550E51FF075')
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
COMMON_FILES = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')
EXPERT_DIR = os.path.join(MT5_DATA, 'MQL5', 'Experts')
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach_log.txt')
SYSTEM_EAS = {'TestBlank.ex5', 'TemplateLoader.ex5', 'AgentHelper.ex5'}

TF_CODES = {
    'M1': 16385, 'M5': 16389, 'M15': 16401, 'M30': 16416,
    'H1': 32801, 'H4': 32805, 'D1': 49201, 'W1': 65601, 'MN1': 82001,
}

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
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
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
    time.sleep(0.5)

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

def generate_template(ea_name, symbol='EURUSD', tf='H1'):
    """Generate .tpl template for an EA."""
    os.makedirs(TPL_DIR, exist_ok=True)
    tf_code = TF_CODES.get(tf, 32801)
    
    tpl_content = (
        f"<chart>\r\n"
        f"id=0\r\n"
        f"symbol={symbol}\r\n"
        f"period_type=1\r\n"
        f"period_size={tf_code}\r\n"
        f"digits=5\r\n"
        f"tick_size=0.000000\r\n"
        f"position_time=0\r\n"
        f"scale_fix=0\r\n"
        f"scale_fixed_min=0.000000\r\n"
        f"scale_fixed_max=0.000000\r\n"
        f"scale_fix11=0\r\n"
        f"scale_bar=0\r\n"
        f"scale_bar_val=1.000000\r\n"
        f"scale=8\r\n"
        f"mode=1\r\n"
        f"fore=0\r\n"
        f"grid=1\r\n"
        f"volume=0\r\n"
        f"scroll=1\r\n"
        f"shift=1\r\n"
        f"shift_size=20.000000\r\n"
        f"fixed_pos=0.000000\r\n"
        f"ohlc=0\r\n"
        f"bidline=1\r\n"
        f"askline=0\r\n"
        f"lastline=0\r\n"
        f"days=1\r\n"
        f"descriptions=0\r\n"
        f"window_left=0\r\n"
        f"window_top=0\r\n"
        f"window_right=0\r\n"
        f"window_bottom=0\r\n"
        f"window_type=1\r\n"
        f"background_color=0\r\n"
        f"foreground_color=16777215\r\n"
        f"barup_color=65280\r\n"
        f"bardown_color=65280\r\n"
        f"bullcandle_color=0\r\n"
        f"bearcandle_color=16777215\r\n"
        f"chartline_color=65280\r\n"
        f"volumes_color=3329330\r\n"
        f"grid_color=10061943\r\n"
        f"bidline_color=10061943\r\n"
        f"askline_color=255\r\n"
        f"lastline_color=49152\r\n"
        f"stops_color=255\r\n"
        f"\r\n"
        f"<expert>\r\n"
        f"name={ea_name}\r\n"
        f"path=Experts\\{ea_name}.ex5\r\n"
        f"enabled=1\r\n"
        f"\r\n"
        f"<inputs>\r\n"
        f"LotSize=1.00\r\n"
        f"MagicNumber=240701\r\n"
        f"EnableLog=true\r\n"
        f"</inputs>\r\n"
        f"\r\n"
        f"</expert>\r\n"
        f"\r\n"
        f"<window>\r\n"
        f"height=100\r\n"
        f"\r\n"
        f"<indicator>\r\n"
        f"name=Main\r\n"
        f"path=\r\n"
        f"apply=1\r\n"
        f"show_data=1\r\n"
        f"scale_inherit=0\r\n"
        f"scale_line=0\r\n"
        f"scale_line_percent=50\r\n"
        f"scale_line_value=0.000000\r\n"
        f"scale_fix_min=0\r\n"
        f"scale_fix_min_val=0.000000\r\n"
        f"scale_fix_max=0\r\n"
        f"scale_fix_max_val=0.000000\r\n"
        f"</indicator>\r\n"
        f"\r\n"
        f"</window>\r\n"
        f"\r\n"
        f"</chart>\r\n"
    )
    
    tpl_name = f"{ea_name}_{symbol}_{tf}"
    tpl_path = os.path.join(TPL_DIR, f"{tpl_name}.tpl")
    with open(tpl_path, 'wb') as f:
        f.write(b'\xff\xfe')  # UTF-16 LE BOM
        f.write(tpl_content.encode('utf-16-le'))
    print(f"  ✅ Template: {tpl_name}.tpl ({os.path.getsize(tpl_path)} bytes)")
    return tpl_path

def open_tpl_via_shellexec(tpl_path):
    """Open .tpl file via ShellExecute - triggers MT5 New Chart dialog."""
    print(f"  Opening via ShellExecute: {tpl_path}")
    result = shell32.ShellExecuteW(
        None, "open", tpl_path, None, None, 1  # SW_SHOWNORMAL
    )
    # ShellExecute returns a value > 32 on success
    if result <= 32:
        print(f"  ShellExecute returned {result} (might have failed)")
        return False
    return True

def find_new_chart_dialog(mt5_pid, timeout=10):
    """Find the New Chart / MetaTrader symbol dialog."""
    start = time.time()
    while time.time() - start < timeout:
        dialogs = find_dialog(mt5_pid, 'MetaTrader')
        if dialogs:
            return dialogs[0]
        # Also check for any dialog at all
        dialogs = find_dialog(mt5_pid)
        if dialogs:
            for h, t in dialogs:
                if t and ('EURUSD' in t or 'MetaTrader' in t or '新' in t or 'Chart' in t):
                    return (h, t)
        time.sleep(1)
    return None

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
        time.sleep(5)
    return False, None

def main():
    print("=" * 60)
    print(f"  SHELLEXECUTE DEPLOY   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    mt5_pid = get_mt5_pid()
    if not mt5_pid:
        log("FAILED: MT5 not running")
        return
    
    print(f"✅ MT5 running (PID={mt5_pid})")
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    
    # Step 1: Generate all EA templates + AgentHelper template
    all_ex5 = sorted(glob.glob(os.path.join(EXPERT_DIR, '*.ex5')))
    ea_names = sorted([os.path.basename(f)[:-4] for f in all_ex5
                       if os.path.basename(f) not in SYSTEM_EAS])
    
    print(f"📋 Generating templates for {len(ea_names)} EAs + AgentHelper...")
    generate_template('AgentHelper', 'EURUSD', 'H1')
    for ea in ea_names:
        generate_template(ea, 'EURUSD', 'H1')
    print(f"✅ All templates generated")
    
    # Step 2: Open AgentHelper template via ShellExecute
    tpl_path = os.path.join(TPL_DIR, 'AgentHelper_EURUSD_H1.tpl')
    if not os.path.exists(tpl_path):
        log("FAILED: AgentHelper template not found")
        return
    
    # Close any existing dialogs
    def close_all_dialogs():
        pid_buf = ctypes.c_ulong()
        closed = 0
        def enum(hwnd, _):
            user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
            if pid_buf.value == mt5_pid:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                if cls.value == '#32770':
                    title = ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                    if title.value:
                        print(f"  Closing dialog: '{title.value}'")
                        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)
                        closed += 1
            return True
        user32.EnumWindows(CB(enum), 0)
        time.sleep(1)
        return closed
    
    close_all_dialogs()
    
    # Open the .tpl file
    print(f"📋 Opening AgentHelper template...")
    open_tpl_via_shellexec(tpl_path)
    
    # Wait for New Chart dialog
    dialog = find_new_chart_dialog(mt5_pid, timeout=15)
    if dialog:
        h, title = dialog
        print(f"  ✅ New Chart dialog appeared: '{title}'")
        
        # The dialog has a symbol ComboBox - send EURUSD
        post_text(h, 'EURUSD')
        time.sleep(1)
        
        # Press Enter to confirm
        post_key(h, 0x0D)  # VK_RETURN
        time.sleep(3)
        
        # Check if Properties dialog appeared (for EA settings)
        dialogs = find_dialog(mt5_pid, 'AgentHelper')
        if dialogs:
            print(f"  ✅ Properties dialog: '{dialogs[0][1]}'")
            post_key(dialogs[0][0], 0x0D)  # Enter to confirm
            time.sleep(2)
        
        # Check for Replace dialog
        for _ in range(10):
            dialogs = find_dialog(mt5_pid)
            replaced = False
            for h2, t2 in dialogs:
                if '代替' in t2 or 'replace' in t2.lower():
                    print(f"  Replace dialog: '{t2}' -> Accepting")
                    post_key(h2, ord('Y'))
                    time.sleep(2)
                    replaced = True
                    break
                if 'Properties' in t2 or 'AgentHelper' in t2:
                    print(f"  Properties: '{t2}' -> Confirming")
                    post_key(h2, 0x0D)
                    time.sleep(2)
                    replaced = True
                    break
            if replaced:
                break
            time.sleep(1)
        
        # Wait for heartbeat
        print("  Waiting for AgentHelper heartbeat...")
        ok, age = wait_for_heartbeat('AgentHelper', timeout=90)
        if ok:
            print(f"  ✅ AgentHelper heartbeat detected ({age:.0f}s)")
            log("SUCCESS: AgentHelper deployed")
        else:
            print(f"  ⚠️ No AgentHelper heartbeat")
            log("FAILED: AgentHelper no heartbeat")
    else:
        print(f"  ⚠️ No New Chart dialog appeared")
        log("FAILED: No dialog after ShellExecute")
    
    # Step 3: Use AgentHelper to deploy all EAs
    print(f"\n{'='*60}")
    print(f"  DEPLOYING ALL EAs VIA AGENTHELPER")
    print(f"{'='*60}")
    
    # Check if AgentHelper is running
    fresh, _ = check_heartbeat('AgentHelper')
    if not fresh:
        log("FAILED: AgentHelper not running, cannot deploy other EAs")
        return
    
    success_count = 0
    fail_count = 0
    
    for i, ea in enumerate(ea_names, 1):
        fresh, age = check_heartbeat(ea)
        if fresh:
            print(f"  ✅ [{i}/{len(ea_names)}] {ea}: already running ({age:.0f}s)")
            success_count += 1
            log(f"ALREADY: {ea}")
            continue
        
        print(f"  🚀 [{i}/{len(ea_names)}] {ea}: writing command...")
        cmd_path = os.path.join(COMMON_FILES, 'agent_helper.txt')
        content = f"{ea},EURUSD,H1"
        with open(cmd_path, 'w') as f:
            f.write(content)
        
        ok, hb_age = wait_for_heartbeat(ea, timeout=120)
        if ok:
            print(f"    ✅ Heartbeat after {hb_age:.0f}s")
            success_count += 1
            log(f"SUCCESS: {ea}")
        else:
            print(f"    ❌ No heartbeat")
            fail_count += 1
            log(f"FAILED: {ea}")
        
        time.sleep(1)
    
    print(f"\n{'='*50}")
    print(f"  RESULTS: {success_count} success, {fail_count} failed")
    print(f"  Total: {success_count + fail_count} EAs")
    print(f"{'='*50}")
    log(f"SUMMARY: {success_count} success, {fail_count} failed")

if __name__ == '__main__':
    main()
