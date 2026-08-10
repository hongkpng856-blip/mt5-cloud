"""Quick deploy remaining EAs - skip heartbeat wait."""
import os, time, ctypes, sys, glob
from ctypes import wintypes

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'D0E8209F77C8CF37AD8BF550E51FF075')
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
COMMON_FILES = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')
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
                    results.append((hwnd, cls.value, title.value))
        return True
    user32.EnumWindows(CB(cb), 0)
    return results

def close_all_extra(mt5_pid):
    for h, c, t in find_dialogs(mt5_pid):
        user32.SendMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
        time.sleep(0.3)

def check_heartbeat(ea_name):
    hb = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
    return os.path.exists(hb)

def apply_template(ea_name, template_name):
    """Apply template via WM_COMMAND 32899 - FAST version without heartbeat wait."""
    mt5_pid = get_mt5_pid()
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    
    close_all_extra(mt5_pid)
    user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
    time.sleep(0.5)
    
    # Open Load Template dialog
    user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0111, 32899, 0)
    time.sleep(2)
    
    # Find file dialog
    dialogs = find_dialogs(mt5_pid)
    file_dlg = None
    for h, c, t in dialogs:
        if '開啟' in t or 'Open' in t:
            file_dlg = h
            break
    
    if not file_dlg:
        print(f"  ❌ File dialog not found")
        return False
    
    # Find Edit controls
    edits = []
    def enum(hwnd, _):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if cls.value == 'Edit':
            rect = wintypes.RECT()
            user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
            edits.append((hwnd, rect))
        return True
    user32.EnumChildWindows(ctypes.c_void_p(file_dlg), CB(enum), 0)
    
    if not edits:
        print(f"  ❌ No Edit control")
        return False
    
    # Use the LARGER Edit control (file name input, not the address bar)
    edit_hwnd = edits[0][0]
    edit_rect = edits[0][1]
    
    # Select all (Ctrl+A)
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0100, 0x11, 0)
    time.sleep(0.03)
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0100, ord('A'), 0)
    time.sleep(0.03)
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0101, ord('A'), 0)
    time.sleep(0.03)
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0101, 0x11, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0100, 0x2E, 0)  # Delete
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0101, 0x2E, 0)
    time.sleep(0.1)
    
    # Type template name
    for ch in template_name:
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0102, ord(ch), 0)
        time.sleep(0.02)
    time.sleep(0.5)
    
    # Press Enter
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0100, 0x0D, 0)
    time.sleep(0.03)
    user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0101, 0x0D, 0)
    time.sleep(2)
    
    # Check if dialog closed
    dialogs2 = find_dialogs(mt5_pid)
    if not any('開啟' in t for h, c, t in dialogs2):
        print(f"  ✅ Template applied")
        return True
    else:
        print(f"  ⚠️ Dialog still open")
        # Try Enter again
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0100, 0x0D, 0)
        time.sleep(0.03)
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0101, 0x0D, 0)
        time.sleep(2)
        dialogs3 = find_dialogs(mt5_pid)
        if not any('開啟' in t for h, c, t in dialogs3):
            print(f"  ✅ Template applied (retry)")
            return True
        return False

def main():
    print("=" * 60)
    print(f"  QUICK DEPLOY REMAINING EAs   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    mt5_pid = get_mt5_pid()
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    print(f"✅ MT5 running (PID={mt5_pid})")
    
    # Get all EA names
    EXPERT_DIR = os.path.join(MT5_DATA, 'MQL5', 'Experts')
    all_ex5 = sorted(glob.glob(os.path.join(EXPERT_DIR, '*.ex5')))
    ea_names = sorted([os.path.basename(f)[:-4] for f in all_ex5
                       if os.path.basename(f) not in SYSTEM_EAS])
    
    # Check which EAs are already done (from log)
    already_done = set()
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                for ea in ea_names:
                    if f'APPLIED: {ea}' in line or f'SUCCESS: {ea}' in line or f'ALREADY: {ea}' in line:
                        already_done.add(ea)
    
    remaining = [ea for ea in ea_names if ea not in already_done]
    print(f"📋 Total: {len(ea_names)}, Already done: {len(already_done)}, Remaining: {len(remaining)}")
    
    if not remaining:
        print("✅ All EAs already deployed!")
        return
    
    success_count = 0
    fail_count = 0
    
    for i, ea in enumerate(remaining, 1):
        if check_heartbeat(ea):
            print(f"  ✅ [{i}/{len(remaining)}] {ea}: already running")
            success_count += 1
            log(f"ALREADY: {ea}")
            continue
        
        tpl_name = f"{ea}_EURUSD_H1.tpl"
        print(f"  🚀 [{i}/{len(remaining)}] {ea}: {tpl_name}")
        
        ok = apply_template(ea, tpl_name)
        if ok:
            success_count += 1
            log(f"SUCCESS: {ea}")
            print(f"    ✅ Done")
        else:
            fail_count += 1
            log(f"FAILED: {ea}")
            print(f"    ❌ Failed")
        
        time.sleep(1)
    
    print(f"\n{'='*50}")
    print(f"  RESULTS: {success_count} success, {fail_count} failed")
    print(f"  Total: {success_count + fail_count} EAs")
    print(f"{'='*50}")
    log(f"SUMMARY: {success_count} success, {fail_count} failed, total={success_count + fail_count}")

if __name__ == '__main__':
    main()
