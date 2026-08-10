"""
Safe EA Deploy — uses pywinauto for navigation + pyautogui for clicking.
No direct ctypes calls to MT5 windows to avoid crashes.
"""
import time, os, sys, psutil
import pyautogui
from pywinauto import Application
from pywinauto.keyboard import send_keys

COMMON_FILES = os.path.join(os.environ.get('APPDATA', ''),
    'MetaQuotes', 'Terminal', 'Common', 'Files')
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, 'auto_attach_log.txt')

def log_result(ea, symbol, tf, status):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        f.write(f'[{ts}] {status}: {ea} attached to {symbol} {tf}\n')

def get_mt5_pid():
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None

def wait_connection(pid, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            app = Application(backend='win32').connect(process=pid, timeout=5)
            win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
            if win.is_visible():
                return app, win
        except:
            pass
        time.sleep(1)
    return None, None

def deploy_eas(ea_names, symbol='EURUSD', tf='H1'):
    pid = get_mt5_pid()
    if not pid:
        print("MT5 not running!")
        return
    
    app, win = wait_connection(pid)
    if not app:
        print("Cannot connect to MT5!")
        return
    
    print(f"Connected to MT5 PID={pid}")
    
    for ea_idx, ea_name in enumerate(ea_names):
        print(f"\n{'='*55}")
        print(f"[{ea_idx+1}/{len(ea_names)}] Deploying {ea_name}...")
        print(f"{'='*55}")
        
        # Check if MT5 is still alive
        if not get_mt5_pid():
            print("MT5 died!")
            break
        
        # Check heartbeat already fresh
        hb_file = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
        if os.path.exists(hb_file):
            age = time.time() - os.path.getmtime(hb_file)
            if age < 120:
                print(f"  ✅ {ea_name} already running (heartbeat {age:.0f}s old)")
                continue
        
        try:
            # Reconnect each time to ensure valid handle
            app = Application(backend='win32').connect(process=pid, timeout=10)
            win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
            
            # Find TreeView
            tree_view = None
            for d in win.descendants():
                if d.element_info.class_name == 'SysTreeView32':
                    tree_view = d
                    break
            
            if not tree_view:
                print("  ❌ No TreeView!")
                continue
            
            tr = tree_view.rectangle()
            
            # Navigate to EA section
            root = tree_view.roots()[0]
            ea_section = root.children()[2]  # 3rd child = EA交易
            text = ea_section.text()
            print(f"  EA section: {text!r}")
            
            # Expand if not already
            ea_section.expand()
            time.sleep(1)
            
            # Find the EA
            target = None
            target_idx = -1
            for i, child in enumerate(ea_section.children()):
                if child.text().strip() == ea_name:
                    target = child
                    target_idx = i
                    break
            
            if not target:
                print(f"  ❌ {ea_name} not found in EA list!")
                continue
            
            print(f"  Found at index {target_idx}")
            
            # Select and ensure visible via keyboard
            # Use SendMessage for select (it's safe)
            import ctypes as _ct
            _user32 = _ct.windll.user32
            _tv_hwnd = tree_view.element_info.handle
            _h_item = target.item().hItem
            
            # Select item (this doesn't seem to crash)
            _user32.SendMessageW(_ct.c_void_p(_tv_hwnd), 0x110B, 9, _ct.c_size_t(_h_item))
            time.sleep(0.3)
            _user32.SendMessageW(_ct.c_void_p(_tv_hwnd), 0x1114, 0, _ct.c_size_t(_h_item))
            time.sleep(0.5)
            
            # Click on chart to give focus
            mdi = None
            for d in win.descendants():
                if d.element_info.class_name == 'MDIClient':
                    mdi = d
                    break
            if mdi:
                mr = mdi.rectangle()
                cx = (mr.left + mr.right) // 2
                cy = (mr.top + mr.bottom) // 2
                pyautogui.click(x=cx, y=cy)
                time.sleep(0.5)
            
            # Now the key part: open EA dialog
            # Method: Right-click on EA -> Select "Attach to chart" or double-click
            # Let's try: click on the Navigator tree to focus it, then Enter
            
            # Click on TreeView to focus it
            tree_focus_x = tr.left + 50
            tree_focus_y = tr.top + 30
            pyautogui.click(x=tree_focus_x, y=tree_focus_y)
            time.sleep(0.5)
            
            # Now the EA should be selected but Navigator might need focus
            # Send Enter to open EA Properties
            send_keys('{ENTER}')
            time.sleep(2)
            
            # Check dialog
            dlg = None
            def _find_dlg():
                results = []
                def cb(hwnd, _):
                    b = _ct.create_unicode_buffer(256)
                    c = _ct.create_unicode_buffer(256)
                    _user32.GetClassNameW(_ct.c_void_p(hwnd), c, 256)
                    if c.value == '#32770':
                        _user32.GetWindowTextW(_ct.c_void_p(hwnd), b, 256)
                        if ea_name in b.value:
                            results.append(hwnd)
                    return 1
                CB = _ct.WINFUNCTYPE(_ct.c_bool, _ct.c_size_t, _ct.c_size_t)
                _user32.EnumWindows(CB(cb), 0)
                return results[0] if results else None
            
            dlg = _find_dlg()
            
            if not dlg:
                # Try double-click on the EA position
                ea_y = tr.top + 55 + target_idx * 18 + 9
                pyautogui.doubleClick(x=tr.left + 35, y=ea_y)
                time.sleep(2)
                dlg = _find_dlg()
            
            if not dlg:
                # Try double-click scan (slow fallback)
                for y_step in range(0, tr.bottom - tr.top, 18):
                    test_y = tr.top + y_step + 9
                    pyautogui.doubleClick(x=tr.left + 50, y=test_y)
                    time.sleep(1)
                    dlg = _find_dlg()
                    if dlg:
                        break
                    send_keys('{ESC}')
                    time.sleep(0.3)
            
            if dlg:
                print(f"  🎉 Dialog opened!")
                # Confirm with Enter
                send_keys('{ENTER}')
                time.sleep(2)
                # Toggle AutoTrading
                send_keys('^e')
                time.sleep(1)
                print(f"  ✅ {ea_name} deployed!")
                log_result(ea_name, symbol, tf, 'SUCCESS')
            else:
                print(f"  ❌ Could not open dialog for {ea_name}")
                log_result(ea_name, symbol, tf, 'FAILED')
        
        except Exception as e:
            print(f"  💥 Error: {e}")
            log_result(ea_name, symbol, tf, f'ERROR: {e}')
        
        # Check MT5 health after each EA
        if not get_mt5_pid():
            print("  ⚠️ MT5 crashed during deployment!")
            # Restart
            import subprocess
            subprocess.Popen([r'C:\Program Files\MetaTrader 5\terminal64.exe'])
            time.sleep(15)
            pid = get_mt5_pid()
            if pid:
                print(f"  MT5 restarted PID={pid}")
                app, win = wait_connection(pid)
    
    print(f"\n{'='*55}")
    print(f"Deployment complete!")
    print(f"{'='*55}")

if __name__ == '__main__':
    eas = sys.argv[1:] if len(sys.argv) > 1 else ['Breakout']
    deploy_eas(eas)
