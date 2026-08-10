"""Use WM_COMMAND 32899 (Load Template) to apply template, then interact with file dialog."""
import os, time, ctypes, sys, glob
from ctypes import wintypes
import pyautogui

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

def find_popup_menus(mt5_pid):
    menus = []
    pid_buf = ctypes.c_ulong()
    def find(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if '#32768' in cls.value:
                menus.append(hwnd)
        return True
    user32.EnumWindows(CB(find), 0)
    return menus

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

def close_all_extra(mt5_pid):
    for h, c, t in find_dialogs(mt5_pid):
        print(f"  Closing dialog: '{t}'")
        user32.SendMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
        time.sleep(0.5)
    for h in find_popup_menus(mt5_pid):
        print(f"  Closing menu: {h:08X}")
        user32.SendMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
        time.sleep(0.3)

def find_child_edit(dialog_hwnd):
    """Find Edit control in a dialog."""
    edits = []
    pid_buf = ctypes.c_ulong()
    def enum(hwnd, _):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if cls.value == 'Edit':
            edits.append(hwnd)
        return True
    user32.EnumChildWindows(ctypes.c_void_p(dialog_hwnd), CB(enum), 0)
    return edits

def find_child_button(dialog_hwnd, title_text=None):
    """Find Button controls in a dialog."""
    buttons = []
    pid_buf = ctypes.c_ulong()
    def enum(hwnd, _):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if cls.value == 'Button':
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
            if title_text is None or title_text in title.value:
                buttons.append((hwnd, title.value))
        return True
    user32.EnumChildWindows(ctypes.c_void_p(dialog_hwnd), CB(enum), 0)
    return buttons

def find_child_listbox(dialog_hwnd):
    """Find ListBox/ComboBox controls in a dialog."""
    lists = []
    pid_buf = ctypes.c_ulong()
    def enum(hwnd, _):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if 'ListBox' in cls.value or 'ComboBox' in cls.value:
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
            lists.append((hwnd, cls.value, title.value))
        return True
    user32.EnumChildWindows(ctypes.c_void_p(dialog_hwnd), CB(enum), 0)
    return lists

def check_heartbeat(ea_name):
    hb = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
    if os.path.exists(hb):
        age = time.time() - os.path.getmtime(hb)
        return age < 60, age
    return False, None

def wait_for_heartbeat(ea_name, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        fresh, age = check_heartbeat(ea_name)
        if fresh:
            return True, age
        time.sleep(5)
    return False, None

def apply_template_via_command(ea_name, template_name):
    """Apply template using WM_COMMAND 32899 (Load Template)."""
    mt5_pid = get_mt5_pid()
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    
    close_all_extra(mt5_pid)
    user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
    time.sleep(1)
    
    # Send WM_COMMAND to open Load Template dialog
    print(f"  Opening Load Template dialog...")
    user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0111, 32899, 0)
    time.sleep(3)
    
    # Find the file dialog
    dialogs = find_dialogs(mt5_pid)
    file_dlg = None
    for h, c, t in dialogs:
        print(f"  Dialog: '{t}'")
        if '開啟' in t or 'Open' in t or '開' in t:
            file_dlg = h
    
    if not file_dlg:
        print(f"  ❌ File dialog not found")
        return False
    
    print(f"  File dialog found: {file_dlg:08X}")
    
    # Find Edit control (for file name)
    edits = find_child_edit(file_dlg)
    print(f"  Edit controls: {len(edits)}")
    for i, e in enumerate(edits):
        rect = wintypes.RECT()
        user32.GetWindowRect(ctypes.c_void_p(e), ctypes.byref(rect))
        print(f"    [{i}] {e:08X}: rect=({rect.left},{rect.top})-({rect.right},{rect.bottom})")
    
    # Find Button controls
    buttons = find_child_button(file_dlg)
    print(f"  Buttons: {len(buttons)}")
    for h, t in buttons:
        print(f"    {h:08X}: '{t}'")
    
    # Find ListBox/ComboBox
    lists = find_child_listbox(file_dlg)
    print(f"  List/Combo: {len(lists)}")
    for h, c, t in lists:
        print(f"    {h:08X}: class='{c}' title='{t}'")
    
    # Method 1: Send text to the first Edit control (file name)
    if edits:
        edit_hwnd = edits[0]
        print(f"  Sending template name to Edit control...")
        
        # Clear existing text first (Ctrl+A then Delete)
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0100, 0x11, 0)  # Ctrl down
        time.sleep(0.05)
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0100, ord('A'), 0)  # A
        time.sleep(0.05)
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0101, ord('A'), 0)
        time.sleep(0.05)
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0101, 0x11, 0)  # Ctrl up
        time.sleep(0.1)
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0100, 0x2E, 0)  # Delete
        time.sleep(0.05)
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0101, 0x2E, 0)
        time.sleep(0.2)
        
        # Type template name
        for ch in template_name:
            user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0102, ord(ch), 0)
            time.sleep(0.03)
        time.sleep(1)
        
        # Method A: Press Enter on Edit
        print(f"  Pressing Enter on Edit...")
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0100, 0x0D, 0)
        time.sleep(0.05)
        user32.PostMessageW(ctypes.c_void_p(edit_hwnd), 0x0101, 0x0D, 0)
        time.sleep(3)
    
    # Check for new dialogs
    def find_dlg():
        results = []
        pid_buf2 = ctypes.c_ulong()
        def cb2(hwnd, _):
            user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf2))
            if pid_buf2.value == mt5_pid:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                if cls.value == '#32770':
                    title = ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                    if title.value:
                        results.append((hwnd, title.value))
            return True
        user32.EnumWindows(CB(cb2), 0)
        return results
    
    dialogs2 = find_dlg()
    print(f"  Dialogs after Enter: {len(dialogs2)}")
    for h, t in dialogs2:
        print(f"    {h:08X}: '{t}'")
    
    # Check if file dialog is still open
    if not any('開啟' in t or 'Open' in t for h, t in dialogs2):
        print(f"  File dialog closed - template might be applied!")
        
        # Check for Properties or Replace dialogs
        for _ in range(10):
            time.sleep(1)
            dialogs3 = find_dlg()
            for h, t in dialogs3:
                if '代替' in t or 'replace' in t.lower():
                    print(f"  Replace dialog: '{t}' -> Confirming")
                    post_key(h, ord('Y'))
                    time.sleep(2)
                    return True
                if 'Properties' in t or ea_name in t:
                    print(f"  Properties dialog: '{t}' -> Confirming")
                    post_key(h, 0x0D)
                    time.sleep(2)
                    return True
            if len(dialogs3) <= 1:  # Only main window still visible
                break
        
        # Check for heartbeat
        ok, age = check_heartbeat(ea_name)
        if ok:
            print(f"  ✅ Heartbeat detected! ({age:.0f}s)")
            return True
        
        return True  # Template was applied, even without heartbeat
    
    else:
        # File dialog still open, try clicking Open button
        buttons2 = find_child_button(file_dlg)
        open_btn = None
        for h, t in buttons2:
            if '開' in t or 'Open' in t:
                open_btn = h
                break
        
        if open_btn:
            print(f"  Clicking 'Open' button...")
            # Use BM_CLICK message
            user32.SendMessageW(ctypes.c_void_p(open_btn), 0x00F5, 0, 0)
            time.sleep(3)
            
            dialogs3 = find_dlg()
            print(f"  Dialogs after button click: {len(dialogs3)}")
            for h, t in dialogs3:
                print(f"    {h:08X}: '{t}'")
            
            if not any('開啟' in t for h, t in dialogs3):
                return True
        
        # Last resort: try pyautogui to click on the Open button
        print(f"  Trying pyautogui to click Open button...")
        pyautogui.write(template_name)
        time.sleep(1)
        pyautogui.press('enter')
        time.sleep(3)
        
        dialogs4 = find_dlg()
        if not any('開啟' in t for h, t in dialogs4):
            return True
    
    return False

def main():
    print("=" * 60)
    print(f"  WM_COMMAND TEMPLATE DEPLOY   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    mt5_pid = get_mt5_pid()
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    print(f"✅ MT5 running (PID={mt5_pid})")
    
    # Open charts if needed
    mdi = user32.FindWindowExW(ctypes.c_void_p(main_hwnd), None, 'MDIClient', None)
    chart_count = [0]
    def _count(h, _):
        chart_count[0] += 1
        return True
    user32.EnumChildWindows(ctypes.c_void_p(mdi), CB(_count), 0)
    print(f"📊 Charts open: {chart_count[0]}")
    
    if chart_count[0] < 3:
        print("📊 Opening charts...")
        user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0111, 52200, 0)
        time.sleep(2)
    
    # Get all EA names
    EXPERT_DIR = os.path.join(MT5_DATA, 'MQL5', 'Experts')
    all_ex5 = sorted(glob.glob(os.path.join(EXPERT_DIR, '*.ex5')))
    ea_names = sorted([os.path.basename(f)[:-4] for f in all_ex5
                       if os.path.basename(f) not in SYSTEM_EAS])
    
    print(f"📋 {len(ea_names)} EAs to deploy")
    
    success_count = 0
    fail_count = 0
    
    for i, ea in enumerate(ea_names, 1):
        fresh, age = check_heartbeat(ea)
        if fresh:
            print(f"  ✅ [{i}/{len(ea_names)}] {ea}: already running ({age:.0f}s)")
            success_count += 1
            log(f"ALREADY: {ea}")
            continue
        
        tpl_name = f"{ea}_EURUSD_H1.tpl"
        print(f"  🚀 [{i}/{len(ea_names)}] {ea}: applying template {tpl_name}...")
        
        ok = apply_template_via_command(ea, tpl_name)
        if ok:
            hb_ok, hb_age = wait_for_heartbeat(ea, timeout=60)
            if hb_ok:
                print(f"    ✅ Heartbeat after {hb_age:.0f}s")
                success_count += 1
                log(f"SUCCESS: {ea}")
            else:
                print(f"    ⚠️ Applied but no heartbeat yet")
                success_count += 1
                log(f"APPLIED: {ea}")
        else:
            print(f"    ❌ Failed")
            fail_count += 1
            log(f"FAILED: {ea}")
        
        time.sleep(1)
    
    print(f"\n{'='*50}")
    print(f"  RESULTS: {success_count} success, {fail_count} failed")
    print(f"{'='*50}")
    log(f"SUMMARY: {success_count} success, {fail_count} failed")

if __name__ == '__main__':
    main()
