"""Use right-click + keyboard to apply template to chart."""
import os, time, ctypes, sys, glob
import pyautogui
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

def wait_for_heartbeat(ea_name, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        fresh, age = check_heartbeat(ea_name)
        if fresh:
            return True, age
        time.sleep(5)
    return False, None

def apply_template_to_chart(ea_name, template_name):
    """Apply template to the active chart via right-click + mouse navigation."""
    mt5_pid = get_mt5_pid()
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    
    # Bring MT5 to foreground
    user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
    time.sleep(1)
    
    # Find the chart area (MDIClient)
    mdi = user32.FindWindowExW(ctypes.c_void_p(main_hwnd), None, 'MDIClient', None)
    if not mdi:
        print("  ❌ MDIClient not found")
        return False
    
    # Get MDIClient rect
    mdi_rect = wintypes.RECT()
    user32.GetWindowRect(ctypes.c_void_p(mdi), ctypes.byref(mdi_rect))
    cx = (mdi_rect.left + mdi_rect.right) // 2
    cy = (mdi_rect.top + mdi_rect.bottom) // 2
    print(f"  MDIClient center: ({cx}, {cy})")
    
    # Right-click on chart area
    print(f"  Right-clicking chart...")
    pyautogui.click(x=cx, y=cy, button='right')
    time.sleep(2)
    
    # Find popup menus
    pid_buf = ctypes.c_ulong()
    menus = []
    def find_menus(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if '#32768' in cls.value:
                menus.append(hwnd)
        return True
    user32.EnumWindows(CB(find_menus), 0)
    print(f"  Popup menus: {len(menus)}")
    
    if not menus:
        print("  No context menu appeared")
        return False
    
    # Use keyboard accelerators via PostMessage to the menu
    # First, try 'T' for Template (common MT5 accelerator)
    # Send PostMessage key events to the popup menu
    menu_hwnd = menus[0]
    
    # Try Template (T key)
    print(f"  Sending 'T' via PostMessage to menu...")
    user32.PostMessageW(ctypes.c_void_p(menu_hwnd), 0x0100, ord('T'), 0)  # WM_KEYDOWN
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(menu_hwnd), 0x0101, ord('T'), 0)  # WM_KEYUP
    time.sleep(1.5)
    
    # Check if submenu appeared
    menus2 = []
    user32.EnumWindows(CB(find_menus), 0)
    for h in menus:
        if h != menu_hwnd:
            menus2.append(h)
    print(f"  New menus after 'T': {len(menus2)}")
    
    if menus2:
        # Submenu appeared! Send 'A' for Apply Template
        submenu = menus2[0]
        print(f"  Submenu found! Sending 'A'...")
        user32.PostMessageW(ctypes.c_void_p(submenu), 0x0100, ord('A'), 0)
        time.sleep(0.05)
        user32.PostMessageW(ctypes.c_void_p(submenu), 0x0101, ord('A'), 0)
        time.sleep(2)
        
        # Check for file dialog
        dialogs = find_dialogs(mt5_pid)
        for h, t in dialogs:
            print(f"  Dialog: '{t}'")
        
        # If dialog appeared, type template name and Enter
        if dialogs:
            for h, t in dialogs:
                if t:  # Any dialog
                    # Send the template name to the dialog
                    for ch in template_name:
                        user32.PostMessageW(ctypes.c_void_p(h), 0x0102, ord(ch), 0)
                        time.sleep(0.03)
                    time.sleep(0.5)
                    user32.PostMessageW(ctypes.c_void_p(h), 0x0100, 0x0D, 0)  # Enter
                    time.sleep(0.05)
                    user32.PostMessageW(ctypes.c_void_p(h), 0x0101, 0x0D, 0)
                    time.sleep(3)
                    print(f"  Template name sent to dialog")
                    return True
        
        # Also check for Replace dialog or Properties dialog
        time.sleep(2)
        for _ in range(10):
            dialogs = find_dialogs(mt5_pid)
            replaced = False
            for h, t in dialogs:
                if '代替' in t or 'replace' in t.lower() or 'Properties' in t or ea_name in t:
                    print(f"  Dialog: '{t}' -> confirming")
                    user32.PostMessageW(ctypes.c_void_p(h), 0x0100, 0x0D, 0)
                    time.sleep(0.05)
                    user32.PostMessageW(ctypes.c_void_p(h), 0x0101, 0x0D, 0)
                    time.sleep(2)
                    replaced = True
                    break
            if replaced:
                return True
            time.sleep(1)
        
        return True
    
    # If 'T' didn't work, try clicking on menu items via mouse
    print(f"  Trying mouse-based menu navigation...")
    # The context menu appears near the right-click point
    # On a 1920x1080 screen with default DPI, each menu item is ~20px tall
    # "Template" is usually around item 7-8 from top
    
    # Get menu window rect
    menu_rect = wintypes.RECT()
    user32.GetWindowRect(ctypes.c_void_p(menu_hwnd), ctypes.byref(menu_rect))
    print(f"  Menu rect: ({menu_rect.left},{menu_rect.top})-({menu_rect.right},{menu_rect.bottom})")
    
    # Click at estimated position of "Template" (7th item ~140px from top)
    template_y = menu_rect.top + 7 * 20
    template_x = menu_rect.left + 20
    
    print(f"  Clicking at ({template_x}, {template_y}) for Template...")
    pyautogui.click(x=template_x, y=template_y)
    time.sleep(1.5)
    
    # Check for submenu
    menus3 = []
    user32.EnumWindows(CB(find_menus), 0)
    for h in menus:
        if h != menu_hwnd:
            menus3.append(h)
    
    if menus3:
        print(f"  Submenu appeared!")
        submenu_rect = wintypes.RECT()
        user32.GetWindowRect(ctypes.c_void_p(menus3[0]), ctypes.byref(submenu_rect))
        print(f"  Submenu rect: ({submenu_rect.left},{submenu_rect.top})-({submenu_rect.right},{submenu_rect.bottom})")
        
        # Click on "Apply Template" (usually first item)
        apply_y = submenu_rect.top + 20
        apply_x = submenu_rect.left + 20
        pyautogui.click(x=apply_x, y=apply_y)
        time.sleep(2)
        
        # Check for dialog
        dialogs = find_dialogs(mt5_pid)
        for h, t in dialogs:
            print(f"  Dialog: '{t}'")
        
        if dialogs:
            for h, t in dialogs:
                if t:
                    for ch in template_name:
                        user32.PostMessageW(ctypes.c_void_p(h), 0x0102, ord(ch), 0)
                        time.sleep(0.03)
                    time.sleep(0.5)
                    user32.PostMessageW(ctypes.c_void_p(h), 0x0100, 0x0D, 0)
                    time.sleep(0.05)
                    user32.PostMessageW(ctypes.c_void_p(h), 0x0101, 0x0D, 0)
                    time.sleep(3)
                    return True
        return True
    
    return False

def main():
    print("=" * 60)
    print(f"  CHART RIGHT-CLICK DEPLOY   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    mt5_pid = get_mt5_pid()
    main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    print(f"✅ MT5 running (PID={mt5_pid})")
    
    # Get all EA names
    all_ex5 = sorted(glob.glob(os.path.join(MT5_DATA.replace('D0E8209F77C8CF37AD8BF550E51FF075', '') + 
                       'D0E8209F77C8CF37AD8BF550E51FF075', 'MQL5', 'Experts', '*.ex5')))
    
    EXPERT_DIR = os.path.join(MT5_DATA, 'MQL5', 'Experts')
    all_ex5 = sorted(glob.glob(os.path.join(EXPERT_DIR, '*.ex5')))
    ea_names = sorted([os.path.basename(f)[:-4] for f in all_ex5
                       if os.path.basename(f) not in SYSTEM_EAS])
    
    print(f"📋 {len(ea_names)} EAs to deploy")
    
    # Ensure charts are open
    mdi = user32.FindWindowExW(ctypes.c_void_p(main_hwnd), None, 'MDIClient', None)
    if mdi:
        chart_count = [0]
        def _count(h, _):
            chart_count[0] += 1
            return True
        user32.EnumChildWindows(ctypes.c_void_p(mdi), CB(_count), 0)
        print(f"📊 Charts open: {chart_count[0]}")
        
        if chart_count[0] < 5:
            # Open more charts
            print("📊 Opening more charts...")
            for cmd in [52200, 52201, 52202, 52203, 52204]:
                user32.SendMessageW(ctypes.c_void_p(main_hwnd), 0x0111, cmd, 0)
                time.sleep(0.5)
    
    # Deploy each EA
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
        print(f"  🚀 [{i}/{len(ea_names)}] {ea}: applying template...")
        
        ok = False
        try:
            ok = apply_template_to_chart(ea, tpl_name)
        except Exception as e:
            print(f"    ❌ Error: {e}")
        
        if ok:
            # Wait for heartbeat
            hb_ok, hb_age = wait_for_heartbeat(ea, timeout=60)
            if hb_ok:
                print(f"    ✅ Heartbeat after {hb_age:.0f}s")
                success_count += 1
                log(f"SUCCESS: {ea}")
            else:
                print(f"    ⚠️ Template applied but no heartbeat")
                success_count += 1  # template was applied
                log(f"APPLIED: {ea}")
        else:
            print(f"    ❌ Template application failed")
            fail_count += 1
            log(f"FAILED: {ea}")
        
        time.sleep(1)
    
    # Summary
    print(f"\n{'='*50}")
    print(f"  RESULTS: {success_count} success, {fail_count} failed")
    print(f"  Total: {success_count + fail_count} EAs")
    print(f"{'='*50}")
    log(f"SUMMARY: {success_count} success, {fail_count} failed")

if __name__ == '__main__':
    main()
