"""Auto-deploy all EAs using ShellExecute to open .tpl files.
When a .tpl file is opened, MT5 shows the "New Chart" dialog.
We send the symbol name via WM_CHAR and press Enter to create the chart with EA attached.
"""
import os, sys, time, ctypes, subprocess, glob
from ctypes import wintypes

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
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


def get_mt5_pid():
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None


def find_dialogs(mt5_pid, target=''):
    """Find all visible dialog windows belonging to MT5."""
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
                    results.append((hwnd, cls.value, title.value, rect))
        return True
    user32.EnumWindows(CB(cb), 0)
    return results


def close_dialog(hwnd, title=""):
    """Close a dialog via WM_CLOSE."""
    print(f"  Closing dialog: '{title}' 0x{hwnd:08X}")
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


def find_listbox_in_dialog(dialog_hwnd):
    """Find ListBox child of a dialog."""
    pid_buf = ctypes.c_ulong()
    listboxes = []
    def enum(hwnd, _):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if 'ListBox' in cls.value:
            listboxes.append(hwnd)
        return True
    user32.EnumChildWindows(ctypes.c_void_p(dialog_hwnd), CB(enum), 0)
    return listboxes


def find_button_in_dialog(dialog_hwnd, title_text):
    """Find a Button child by title."""
    pid_buf = ctypes.c_ulong()
    buttons = []
    def enum(hwnd, _):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if cls.value == 'Button':
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
            if title_text.lower() in title.value.lower():
                buttons.append(hwnd)
        return True
    user32.EnumChildWindows(ctypes.c_void_p(dialog_hwnd), CB(enum), 0)
    return buttons


def deploy_ea_via_template(ea_name, symbol='EURUSD', tf='H1', wait_heartbeat=True):
    """
    Deploy an EA by opening its .tpl file with MT5.
    The ShellExecute approach triggers the "New Chart" dialog.
    We interact with it to create the chart with the EA attached.
    """
    tpl_name = f"{ea_name}_{symbol}_{tf}.tpl"
    tpl_path = os.path.join(TPL_DIR, tpl_name)
    
    if not os.path.exists(tpl_path):
        print(f"  ❌ Template not found: {tpl_path}")
        return False
    
    print(f"  📋 Template: {tpl_name} ({os.path.getsize(tpl_path)} bytes)")
    
    # Check for existing dialogs before we start
    mt5_pid = get_mt5_pid()
    before_dialogs = find_dialogs(mt5_pid)
    for h, cls, title, rect in before_dialogs:
        if 'New' in title or '新' in title or 'Print' in title or '列印' in title:
            close_dialog(h, title)
    time.sleep(1)
    
    # Open the .tpl file with ShellExecute
    print(f"  Opening template with MT5...")
    shell32 = ctypes.windll.shell32
    result = shell32.ShellExecuteW(None, "open", tpl_path, None, None, 1)
    print(f"  ShellExecute result: {result}")
    
    # Wait for dialog to appear
    time.sleep(2)
    
    # Find the "New" dialog
    dialogs = find_dialogs(mt5_pid)
    new_dlg = None
    other_dlgs = []
    for h, cls, title, rect in dialogs:
        if 'New' in title or '新圖' in title:
            new_dlg = h
            print(f"  Found 'New Chart' dialog: 0x{h:08X} at ({rect.left},{rect.top})-({rect.right},{rect.bottom})")
        elif title:  # Any other dialog (like Print Setup)
            other_dlgs.append((h, title))
    
    # Close any irrelevant dialogs
    for h, title in other_dlgs:
        print(f"  Closing unrelated dialog: '{title}'")
        close_dialog(h, title)
    
    if not new_dlg:
        # Maybe the template was applied directly without dialog
        print("  No 'New' dialog appeared - checking if EA deployed directly...")
        time.sleep(5)
        if wait_heartbeat:
            ok, age = check_heartbeat(ea_name, timeout=30)
            if ok:
                print(f"  ✅ {ea_name} already running!")
                return True
        return False
    
    # The dialog has a ListBox. Send the symbol name to select it.
    print(f"  Interacting with New Chart dialog...")
    
    # Find ListBox
    listboxes = find_listbox_in_dialog(new_dlg)
    if listboxes:
        listbox_hwnd = listboxes[0]
        print(f"  ListBox found: 0x{listbox_hwnd:08X}")
        
        # Send symbol name to select it in the list
        for ch in symbol:
            user32.PostMessageW(ctypes.c_void_p(listbox_hwnd), 0x0102, ord(ch), 0)
            time.sleep(0.05)
        time.sleep(1)
        
        # Press Enter to confirm
        post_key(listbox_hwnd, 0x0D)
    else:
        # Send to dialog directly
        print(f"  No ListBox found, sending to dialog...")
        for ch in symbol:
            user32.PostMessageW(ctypes.c_void_p(new_dlg), 0x0102, ord(ch), 0)
            time.sleep(0.05)
        time.sleep(1)
        post_key(new_dlg, 0x0D)
    
    time.sleep(4)
    
    # Check if dialog is closed
    dialogs_after = find_dialogs(mt5_pid)
    new_still_open = any('New' in title or '新圖' in title for h, cls, title, rect in dialogs_after)
    
    if new_still_open:
        print(f"  Dialog still open, trying OK button...")
        # Find and click OK button
        ok_buttons = find_button_in_dialog(new_dlg, 'OK')
        if ok_buttons:
            print(f"  Clicking OK button: 0x{ok_buttons[0]:08X}")
            # Send BN_CLICKED
            user32.SendMessageW(ctypes.c_void_p(ok_buttons[0]), 0x00F5, 0, 0)  # BM_CLICK
            time.sleep(3)
        else:
            # Just press Enter
            post_key(new_dlg, 0x0D)
            time.sleep(3)
        
        # Check again
        dialogs_final = find_dialogs(mt5_pid)
        new_final = any('New' in title or '新圖' in title for h, cls, title, rect in dialogs_final)
        if new_final:
            print(f"  Dialog still open after OK, pressing Enter again...")
            post_key(new_dlg, 0x0D)
            time.sleep(3)
    
    # Check for Replace dialog
    time.sleep(2)
    repl_dialogs = find_dialogs(mt5_pid)
    for h, cls, title, rect in repl_dialogs:
        if '代替' in title or 'replace' in title.lower():
            print(f"  Replace dialog: '{title}' -> Accepting")
            ok_buttons = find_button_in_dialog(h, 'Yes') or find_button_in_dialog(h, '是')
            if ok_buttons:
                user32.SendMessageW(ctypes.c_void_p(ok_buttons[0]), 0x00F5, 0, 0)
            else:
                post_key(h, ord('Y'))
            time.sleep(3)
    
    # Wait for heartbeat
    if wait_heartbeat:
        ok, age = check_heartbeat(ea_name, timeout=90)
        if ok:
            print(f"  ✅ {ea_name}: heartbeat detected ({age:.0f}s old)")
            return True
        else:
            print(f"  ❌ {ea_name}: no heartbeat detected")
            return False
    
    print(f"  ✅ Template applied for {ea_name}")
    return True


def check_heartbeat(ea_name, timeout=0):
    hb = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
    start = time.time()
    while timeout > 0 and time.time() - start < timeout:
        if os.path.exists(hb):
            age = time.time() - os.path.getmtime(hb)
            if age < 60:
                return True, age
        time.sleep(3)
    if os.path.exists(hb):
        age = time.time() - os.path.getmtime(hb)
        return age < 60, age
    return False, None


def generate_template(ea_name, symbol='EURUSD', tf='H1'):
    """Generate .tpl template if it doesn't exist."""
    tpl_path = os.path.join(TPL_DIR, f"{ea_name}_{symbol}_{tf}.tpl")
    if os.path.exists(tpl_path):
        age = time.time() - os.path.getmtime(tpl_path)
        print(f"  Template exists ({age:.0f}s old)")
        return tpl_path
    
    print(f"  Generating template for {ea_name}...")
    PYTHON = r'C:\Users\hongk\AppData\Local\Programs\Python\Python311\python.exe'
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach.py')
    proc = subprocess.Popen(
        [PYTHON, '-u', script, '--ea', ea_name, '--symbol', symbol, '--tf', tf],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        proc.communicate(timeout=10)
    except:
        proc.kill()
        proc.communicate()
    
    if os.path.exists(tpl_path):
        print(f"  ✅ Template generated")
        return tpl_path
    return None


def main():
    print("=" * 60)
    print(f"  AUTO-DEPLOY via .tpl  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    mt5_pid = get_mt5_pid()
    if not mt5_pid:
        print("❌ MT5 not running")
        log("FAILED: MT5 not running")
        return
    
    print(f"✅ MT5 running (PID={mt5_pid})")
    
    # Get EA list
    all_ex5 = sorted(glob.glob(os.path.join(EXPERT_DIR, '*.ex5')))
    ea_names = sorted([os.path.basename(f)[:-4] for f in all_ex5
                       if os.path.basename(f) not in SYSTEM_EAS])
    print(f"📋 Found {len(ea_names)} EAs")
    
    # Check existing heartbeats
    to_deploy = []
    for ea in ea_names:
        fresh, age = check_heartbeat(ea)
        if fresh:
            print(f"  ✅ {ea}: running ({age:.0f}s)")
        else:
            reason = f"no heartbeat" if age is None else f"{age:.0f}s old"
            print(f"  🚀 {ea}: {reason}")
            to_deploy.append(ea)
    
    if not to_deploy:
        print("\n✅ All EAs already running!")
        log("All EAs running - nothing to do")
        return
    
    print(f"\n📋 Deploying {len(to_deploy)} EAs via .tpl template...")
    print(f"{'='*50}")
    
    success_count = 0
    fail_count = 0
    
    for i, ea in enumerate(to_deploy, 1):
        print(f"\n--- [{i}/{len(to_deploy)}] {ea} ---")
        
        # Generate template if needed
        tpl = generate_template(ea)
        if not tpl:
            print(f"  ❌ Cannot generate template")
            fail_count += 1
            log(f"FAILED: {ea} - template generation failed")
            continue
        
        # Deploy via ShellExecute + dialog interaction
        result = deploy_ea_via_template(ea, 'EURUSD', 'H1', wait_heartbeat=True)
        
        if result:
            print(f"  ✅ {ea}: DEPLOYED SUCCESSFULLY")
            success_count += 1
            log(f"SUCCESS: {ea} deployed via .tpl")
        else:
            print(f"  ❌ {ea}: DEPLOY FAILED")
            fail_count += 1
            log(f"FAILED: {ea} via .tpl")
        
        # Small pause between deployments
        time.sleep(2)
        
        # Heartbeat check summary
        print(f"\n  Progress: {success_count}/{success_count + fail_count}")
    
    # Final summary
    print(f"\n{'='*50}")
    print(f"  FINAL RESULTS")
    print(f"{'='*50}")
    print(f"  ✅ Success: {success_count}")
    print(f"  ❌ Failed: {fail_count}")
    print(f"  Total: {success_count + fail_count}/{len(to_deploy)}")
    
    # Final heartbeat check
    print(f"\n  Final heartbeat check:")
    for ea in ea_names:
        fresh, age = check_heartbeat(ea)
        if fresh:
            print(f"    ✅ {ea}: {age:.0f}s old")
        else:
            print(f"    ❌ {ea}: {'no heartbeat' if age is None else f'{age:.0f}s old (stale)'}")
    
    log(f"SUMMARY: {success_count} success, {fail_count} failed, total={len(to_deploy)} deployed")
    log(f"Total registered EAs: {len(ea_names)}, running with fresh heartbeat: {sum(1 for ea in ea_names if check_heartbeat(ea)[0])}")


if __name__ == '__main__':
    main()
