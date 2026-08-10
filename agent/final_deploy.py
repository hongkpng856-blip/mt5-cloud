"""
FINAL approach: Use ShellExecute on .tpl to open New Chart dialog,
interact with it via PostMessage, deploy AgentHelper, then use
AgentHelper's command file mechanism for all other EAs.
"""
import os, sys, time, ctypes, subprocess, glob
from ctypes import wintypes

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
shell32 = ctypes.windll.shell32

APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
COMMON_FILES = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')
EXPERT_DIR = os.path.join(MT5_DATA, 'MQL5', 'Experts')
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

def find_dialogs(mt5_pid, target=''):
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
                    rect = wintypes.RECT()
                    user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
                    results.append((hwnd, title.value, rect))
        return True
    user32.EnumWindows(CB(cb), 0)
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    if main_hwnd:
        user32.EnumChildWindows(ctypes.c_void_p(main_hwnd), CB(cb), 0)
    return results

def close_dialog(hwnd):
    user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)
    time.sleep(0.5)

def post_key(hwnd, vk):
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, vk, 0)
    time.sleep(0.03)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, vk, 0)
    time.sleep(0.1)

def post_text(hwnd, text):
    for ch in text:
        user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0102, ord(ch), 0)
        time.sleep(0.03)
    time.sleep(0.3)

def find_listboxes(dialog_hwnd):
    lb = []
    def enum(hwnd, _):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if 'ListBox' in cls.value:
            lb.append(hwnd)
        elif 'ComboBox' in cls.value:
            lb.append(hwnd)
        elif 'Edit' in cls.value:
            lb.append(hwnd)
        return True
    user32.EnumChildWindows(ctypes.c_void_p(dialog_hwnd), CB(enum), 0)
    return lb

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

def generate_template_if_missing(ea_name, symbol='EURUSD', tf='H1'):
    tpl_path = os.path.join(TPL_DIR, f"{ea_name}_{symbol}_{tf}.tpl")
    if not os.path.exists(tpl_path):
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach.py')
        proc = subprocess.Popen([PYTHON, '-u', script, '--ea', ea_name, '--symbol', symbol, '--tf', tf],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try: proc.communicate(timeout=10)
        except: proc.kill(); proc.communicate()
    return tpl_path if os.path.exists(tpl_path) else None

def open_new_chart_via_tpl(ea_name, symbol='EURUSD', tf='H1'):
    """Open a new chart via ShellExecute on .tpl file, interact with dialog."""
    tpl_path = os.path.join(TPL_DIR, f"{ea_name}_{symbol}_{tf}.tpl")
    if not os.path.exists(tpl_path):
        return False
    
    # Close any existing dialogs
    mt5_pid = get_mt5_pid()
    dialogs = find_dialogs(mt5_pid)
    for h, title, _ in dialogs:
        if title:
            close_dialog(h)
    time.sleep(1)
    
    # ShellExecute the .tpl file
    result = shell32.ShellExecuteW(None, "open", tpl_path, None, None, 1)
    if result <= 32:
        print(f"  ShellExecute failed: {result}")
        return False
    
    # Wait for dialog
    time.sleep(3)
    dialogs = find_dialogs(mt5_pid)
    
    # Find New Chart dialog
    new_dlg = None
    print_dlg = None
    for h, title, rect in dialogs:
        if 'New' in title or '新圖' in title:
            new_dlg = h
        elif 'Print' in title or '列印' in title:
            print_dlg = h
    
    # Close Print Setup dialog if present
    if print_dlg:
        close_dialog(print_dlg)
        time.sleep(1)
        dialogs = find_dialogs(mt5_pid)
        for h, title, _ in dialogs:
            if 'New' in title or '新圖' in title:
                new_dlg = h
    
    if not new_dlg:
        # Maybe chart was created directly without dialog?
        time.sleep(5)
        fresh, _ = check_heartbeat(ea_name)
        if fresh:
            return True
        # Try alternative: maybe template was already applied
        return True  # return True anyway to let caller check heartbeat
    
    print(f"  New Chart dialog found: 0x{new_dlg:08X}")
    
    # Find input control (ListBox or ComboBox)
    input_ctrls = find_listboxes(new_dlg)
    
    # Send symbol name
    txt_sent = False
    for ctrl in input_ctrls:
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(ctrl), cls, 256)
        if 'Edit' in cls.value or 'ComboBox' in cls.value:
            post_text(ctrl, symbol)
            txt_sent = True
            print(f"  Sent '{symbol}' to {cls.value}")
            break
    
    if not txt_sent:
        # Send to dialog directly (some dialogs auto-complete)
        for ch in symbol:
            user32.PostMessageW(ctypes.c_void_p(new_dlg), 0x0102, ord(ch), 0)
            time.sleep(0.05)
        print(f"  Sent '{symbol}' to dialog")
    
    time.sleep(1)
    
    # Press Enter to confirm
    post_key(new_dlg, 0x0D)
    time.sleep(3)
    
    # Check if dialog closed
    dialogs_after = find_dialogs(mt5_pid)
    dlg_still_open = any('New' in t or '新圖' in t for h, t, _ in dialogs_after)
    
    if dlg_still_open:
        print("  Dialog still open, trying OK button...")
        # Find OK button and click it
        ok_btns = []
        def find_ok(hwnd, _):
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == 'Button':
                t = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), t, 256)
                if 'OK' in t.value or '確定' in t.value:
                    ok_btns.append(hwnd)
            return True
        user32.EnumChildWindows(ctypes.c_void_p(new_dlg), CB(find_ok), 0)
        if ok_btns:
            user32.SendMessageW(ctypes.c_void_p(ok_btns[0]), 0x00F5, 0, 0)
            time.sleep(3)
        else:
            post_key(new_dlg, 0x0D)
            time.sleep(3)
    
    # Check for Replace dialog
    time.sleep(2)
    for _ in range(5):
        d = find_dialogs(mt5_pid)
        replaced = False
        for h, title, _ in d:
            if '代替' in title or 'replace' in title.lower():
                print(f"  Replace dialog: Yes")
                yes_btns = []
                def find_yes(chwnd, _):
                    ccls = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(ctypes.c_void_p(chwnd), ccls, 256)
                    if ccls.value == 'Button':
                        ct = ctypes.create_unicode_buffer(256)
                        user32.GetWindowTextW(ctypes.c_void_p(chwnd), ct, 256)
                        if 'Yes' in ct.value or '是' in ct.value:
                            yes_btns.append(chwnd)
                    return True
                user32.EnumChildWindows(ctypes.c_void_p(h), CB(find_yes), 0)
                if yes_btns:
                    user32.SendMessageW(ctypes.c_void_p(yes_btns[0]), 0x00F5, 0, 0)
                else:
                    post_key(h, ord('Y'))
                time.sleep(2)
                replaced = True
                break
            if ea_name in title or 'Properties' in title:
                print(f"  Properties dialog: OK")
                ok_btns = []
                def find_ok2(chwnd, _):
                    ccls = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(ctypes.c_void_p(chwnd), ccls, 256)
                    if ccls.value == 'Button':
                        ct = ctypes.create_unicode_buffer(256)
                        user32.GetWindowTextW(ctypes.c_void_p(chwnd), ct, 256)
                        if 'OK' in ct.value or '確定' in ct.value:
                            ok_btns.append(chwnd)
                    return True
                user32.EnumChildWindows(ctypes.c_void_p(h), CB(find_ok2), 0)
                if ok_btns:
                    user32.SendMessageW(ctypes.c_void_p(ok_btns[0]), 0x00F5, 0, 0)
                else:
                    post_key(h, 0x0D)
                time.sleep(2)
                replaced = True
                break
        if not replaced:
            break
        time.sleep(1)
    
    # Enable AutoTrading
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    if main_hwnd:
        user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0100, 0x11, 0)  # Ctrl down
        user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0100, ord('E'), 0)
        user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0101, ord('E'), 0)
        user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0101, 0x11, 0)  # Ctrl up
        time.sleep(1)
    
    print(f"  Chart creation via .tpl completed for {ea_name}")
    return True


def write_agenthelper_cmd(ea_name, symbol='EURUSD', tf='H1'):
    cmd_path = os.path.join(COMMON_FILES, 'agent_helper.txt')
    with open(cmd_path, 'w') as f:
        f.write(f"{ea_name},{symbol},{tf}")
    print(f"  📝 Command: {ea_name},{symbol},{tf}")


def main():
    print("=" * 60)
    print(f"  FINAL AUTO-DEPLOY  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    mt5_pid = get_mt5_pid()
    if not mt5_pid:
        print("❌ MT5 not running")
        return
    
    print(f"✅ MT5 running (PID={mt5_pid})")
    
    # Get EA list
    all_ex5 = sorted(glob.glob(os.path.join(EXPERT_DIR, '*.ex5')))
    ea_names = sorted([os.path.basename(f)[:-4] for f in all_ex5
                       if os.path.basename(f) not in SYSTEM_EAS])
    print(f"📋 {len(ea_names)} EAs registered")
    
    # Check heartbeats
    to_deploy = []
    for ea in ea_names:
        fresh, age = check_heartbeat(ea)
        if fresh:
            print(f"  ✅ {ea}: running ({age:.0f}s)")
        else:
            reason = "no heartbeat" if age is None else f"{age:.0f}s"
            print(f"  🚀 {ea}: {reason}")
            to_deploy.append(ea)
    
    if not to_deploy:
        print("\n✅ All EAs already running!")
        log("All EAs already running")
        return
    
    # Close any open dialogs
    dialogs = find_dialogs(mt5_pid)
    for h, title, _ in dialogs:
        if title:
            close_dialog(h)
            print(f"  Closed dialog: '{title}'")
    
    # Step 1: Deploy AgentHelper via .tpl ShellExecute
    print("\n📌 STEP 1: Deploy AgentHelper")
    ah_tpl = generate_template_if_missing('AgentHelper')
    if not ah_tpl:
        log("FAILED: Cannot generate AgentHelper template")
        print("❌ Cannot generate AgentHelper template")
        return
    
    if not check_heartbeat('AgentHelper')[0]:
        ok = open_new_chart_via_tpl('AgentHelper')
        if ok:
            hb_ok, hb_age = wait_for_heartbeat('AgentHelper', timeout=90)
            if hb_ok:
                print(f"✅ AgentHelper running! (heartbeat {hb_age:.0f}s)")
                log("SUCCESS: AgentHelper deployed")
            else:
                print("⚠️ AgentHelper deployed but no heartbeat")
                log("WARNING: AgentHelper deployed but no heartbeat")
        else:
            print("❌ AgentHelper deployment failed")
            log("FAILED: AgentHelper deployment")
    else:
        print("✅ AgentHelper already running")
    
    # Step 2: Use AgentHelper for all other EAs
    print(f"\n📌 STEP 2: Deploy {len(to_deploy)} EAs via AgentHelper")
    success_count = 0
    fail_count = 0
    
    for i, ea in enumerate(to_deploy, 1):
        if ea == 'AgentHelper':
            continue
        
        if check_heartbeat(ea)[0]:
            print(f"  ✅ [{i}/{len(to_deploy)}] {ea}: already running")
            success_count += 1
            continue
        
        print(f"\n  [{i}/{len(to_deploy)}] {ea}")
        
        # Ensure template exists
        generate_template_if_missing(ea)
        
        # If AgentHelper is running, use command file
        if check_heartbeat('AgentHelper')[0]:
            write_agenthelper_cmd(ea)
            hb_ok, hb_age = wait_for_heartbeat(ea, timeout=120)
            if hb_ok:
                print(f"  ✅ Heartbeat {hb_age:.0f}s → DEPLOYED")
                success_count += 1
                log(f"SUCCESS: {ea} via AgentHelper")
            else:
                print(f"  ❌ No heartbeat within 120s")
                # Fallback: Try direct .tpl approach
                print(f"  → Falling back to direct .tpl deployment...")
                ok = open_new_chart_via_tpl(ea)
                if ok:
                    hb2_ok, hb2_age = wait_for_heartbeat(ea, timeout=90)
                    if hb2_ok:
                        print(f"  ✅ Heartbeat after fallback!")
                        success_count += 1
                        log(f"SUCCESS: {ea} via .tpl")
                    else:
                        fail_count += 1
                        log(f"FAILED: {ea} - no heartbeat after both methods")
                else:
                    fail_count += 1
                    log(f"FAILED: {ea} - all methods failed")
        else:
            # Direct .tpl approach (no AgentHelper)
            print(f"  (No AgentHelper - trying direct .tpl)")
            ok = open_new_chart_via_tpl(ea)
            if ok:
                hb_ok, hb_age = wait_for_heartbeat(ea, timeout=90)
                if hb_ok:
                    print(f"  ✅ Heartbeat {hb_age:.0f}s")
                    success_count += 1
                    log(f"SUCCESS: {ea} via .tpl")
                else:
                    fail_count += 1
                    log(f"FAILED: {ea} - no heartbeat")
            else:
                fail_count += 1
                log(f"FAILED: {ea} - .tpl failed")
        
        # Brief pause
        time.sleep(2)
    
    # Summary
    print(f"\n{'='*50}")
    print(f"  FINAL RESULTS")
    print(f"{'='*50}")
    running = sum(1 for ea in ea_names if check_heartbeat(ea)[0])
    print(f"  Running now: {running}/{len(ea_names)}")
    print(f"  Deployed this run: {success_count} success, {fail_count} failed")
    
    log(f"SUMMARY: {success_count} success, {fail_count} failed this run")
    log(f"Total running: {running}/{len(ea_names)}")


if __name__ == '__main__':
    main()
