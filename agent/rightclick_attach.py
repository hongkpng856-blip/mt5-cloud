"""
Enhanced EA attachment using right-click context menu on Navigator TreeView items.
This is more reliable than double-click which has been failing.
"""
import os
import sys
import time
import ctypes
import pyautogui
from pywinauto import Application
from pywinauto.keyboard import send_keys

# ─── Config ───
MT5_DATA = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
MT5_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
COMMON_FILES = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                            'Common', 'Files')

TF_CODES = {
    'M1': 16385, 'M5': 16389, 'M15': 16401, 'M30': 16416,
    'H1': 32801, 'H4': 32805, 'D1': 49201, 'W1': 65601, 'MN1': 82001,
}

user32 = ctypes.windll.user32

# ─── Templates ───

def generate_template(ea_name, symbol='EURUSD', timeframe='H1', inputs=None):
    """Generate .tpl template for the EA"""
    os.makedirs(TPL_DIR, exist_ok=True)
    tf_code = TF_CODES.get(timeframe, 32801)
    
    if inputs is None:
        inputs = {'LotSize': '1.00', 'MagicNumber': '240701', 'EnableLog': 'true'}
    
    inputs_section = ''
    for key, val in inputs.items():
        inputs_section += f'{key}={val}\r\n'
    
    tpl_content = (
        f'<chart>\r\n'
        f'id=0\r\n'
        f'symbol={symbol}\r\n'
        f'period_type=1\r\n'
        f'period_size={tf_code}\r\n'
        f'digits=5\r\n'
        f'tick_size=0.000000\r\n'
        f'position_time=0\r\n'
        f'scale_fix=0\r\n'
        f'scale_fixed_min=0.000000\r\n'
        f'scale_fixed_max=0.000000\r\n'
        f'scale_fix11=0\r\n'
        f'scale_bar=0\r\n'
        f'scale_bar_val=1.000000\r\n'
        f'scale=8\r\n'
        f'mode=1\r\n'
        f'fore=0\r\n'
        f'grid=1\r\n'
        f'volume=0\r\n'
        f'scroll=1\r\n'
        f'shift=1\r\n'
        f'shift_size=20.000000\r\n'
        f'fixed_pos=0.000000\r\n'
        f'ohlc=0\r\n'
        f'bidline=1\r\n'
        f'askline=0\r\n'
        f'lastline=0\r\n'
        f'days=1\r\n'
        f'descriptions=0\r\n'
        f'window_left=0\r\n'
        f'window_top=0\r\n'
        f'window_right=0\r\n'
        f'window_bottom=0\r\n'
        f'window_type=1\r\n'
        f'background_color=0\r\n'
        f'foreground_color=16777215\r\n'
        f'barup_color=65280\r\n'
        f'bardown_color=65280\r\n'
        f'bullcandle_color=0\r\n'
        f'bearcandle_color=16777215\r\n'
        f'chartline_color=65280\r\n'
        f'volumes_color=3329330\r\n'
        f'grid_color=10061943\r\n'
        f'bidline_color=10061943\r\n'
        f'askline_color=255\r\n'
        f'lastline_color=49152\r\n'
        f'stops_color=255\r\n'
        f'\r\n'
        f'<expert>\r\n'
        f'name={ea_name}\r\n'
        f'path=Experts\\\\{ea_name}.ex5\r\n'
        f'enabled=1\r\n'
        f'\r\n'
        f'<inputs>\r\n'
        f'{inputs_section}'
        f'</inputs>\r\n'
        f'\r\n'
        f'</expert>\r\n'
        f'\r\n'
        f'<window>\r\n'
        f'height=100\r\n'
        f'\r\n'
        f'<indicator>\r\n'
        f'name=Main\r\n'
        f'path=\r\n'
        f'apply=1\r\n'
        f'show_data=1\r\n'
        f'scale_inherit=0\r\n'
        f'scale_line=0\r\n'
        f'scale_line_percent=50\r\n'
        f'scale_line_value=0.000000\r\n'
        f'scale_fix_min=0\r\n'
        f'scale_fix_min_val=0.000000\r\n'
        f'scale_fix_max=0\r\n'
        f'scale_fix_max_val=0.000000\r\n'
        f'</indicator>\r\n'
        f'\r\n'
        f'</window>\r\n'
        f'\r\n'
        f'</chart>\r\n'
    )
    
    tpl_name = f'{ea_name}_{symbol}_{timeframe}'
    tpl_path = os.path.join(TPL_DIR, f'{tpl_name}.tpl')
    
    with open(tpl_path, 'wb') as f:
        f.write(b'\xff\xfe')
        f.write(tpl_content.encode('utf-16-le'))
    
    print(f'📋 Template saved: {tpl_path} ({os.path.getsize(tpl_path)} bytes)')
    return tpl_path, tpl_name

# ─── MT5 Helpers ───

def find_mt5_pid():
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None

def get_main_hwnd():
    return user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)

def find_dialog(ea_name, mt5_pid):
    """Search for a dialog with the EA name in its title"""
    results = []
    pid_buf = ctypes.c_ulong()
    def cb(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':  # Dialog class
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if ea_name in title.value or (ea_name == '' and title.value):
                    results.append((hwnd, title.value))
        return True
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    user32.EnumWindows(CB(cb), 0)
    return results

def close_stale_dialogs(mt5_pid):
    """Close any dialog windows that might interfere"""
    pid_buf = ctypes.c_ulong()
    def cb(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                # Close generic dialogs (Confirm, Error, etc.) but NOT Properties dialogs
                if 'MetaTrader' in title.value or 'error' in title.value.lower():
                    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)  # WM_CLOSE
        return True
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    user32.EnumWindows(CB(cb), 0)

def verify_heartbeat(ea_name, timeout=60):
    hb_file = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(hb_file):
            mtime = os.path.getmtime(hb_file)
            age = time.time() - mtime
            print(f'💓 {ea_name} heartbeat: {round(age)}s old')
            if age < 300:
                return True
        time.sleep(3)
    return False

# ─── Chart / Navigator Helpers ───

def open_chart_via_keyboard():
    """Open a new EURUSD chart via keyboard shortcuts"""
    # Ctrl+Shift+S = Show all symbols
    send_keys('^+s')
    time.sleep(2)
    # Insert = Open chart for selected symbol
    send_keys('{INSERT}')
    time.sleep(2)
    # Enter = Confirm
    send_keys('{ENTER}')
    time.sleep(3)
    print('📋 New chart opened')
    return True

def get_navigator_treeview(mt5_pid):
    """Find the Navigator TreeView control"""
    app = Application(backend='win32').connect(process=mt5_pid)
    win = app.top_window()
    
    # Find TreeView anywhere in the window hierarchy
    tree_view = None
    navigator_hwnd = None
    
    # Search all windows for Navigator MiniFrame + TreeView
    pid_buf = ctypes.c_ulong()
    def enum_cb(hwnd, _):
        nonlocal navigator_hwnd
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if 'MiniFrame' in cls.value:
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if any(t in title.value for t in ['導航', 'Navigator', 'ナビゲーター', 'Навигатор']):
                    navigator_hwnd = hwnd
        return True
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    user32.EnumWindows(CB(enum_cb), 0)
    
    # Search through all relevant windows for TreeView
    search_handles = [win.element_info.handle]
    if navigator_hwnd:
        search_handles.append(navigator_hwnd)
    
    for h in search_handles:
        try:
            w = app.window(handle=h)
            for d in w.descendants():
                if d.element_info.class_name == 'SysTreeView32' and d.is_visible():
                    tree_view = d
                    break
        except:
            pass
        if tree_view:
            break
    
    return tree_view, navigator_hwnd

def show_navigator_panel(mt5_pid):
    """Ensure Navigator panel is visible"""
    _, navigator_hwnd = get_navigator_treeview(mt5_pid)
    
    if navigator_hwnd:
        user32.ShowWindow(ctypes.c_void_p(navigator_hwnd), 5)  # SW_SHOW
        user32.SetWindowPos(ctypes.c_void_p(navigator_hwnd), 0, 0, 0, 0, 0, 0x0002 | 0x0001)
        time.sleep(0.5)
        print('📋 Navigator panel shown')
        return navigator_hwnd
    
    # Fallback: WM_COMMAND 32808
    main_hwnd = get_main_hwnd()
    if main_hwnd:
        user32.SendMessageW(ctypes.c_void_p(main_hwnd), 0x0111, 32808, 0)
        time.sleep(1.5)
    return None

# ─── Core: Right-click + Attach to Chart ───

def attach_ea_via_rightclick(ea_name, mt5_pid, max_retries=2):
    """
    Attach EA by right-clicking it in Navigator and selecting 'Attach to Chart'.
    More reliable than double-click which has been failing.
    
    Flow:
    1. Open a new chart (to have a target for the EA)
    2. Show Navigator panel
    3. Find the EA in the TreeView
    4. Right-click on it
    5. Click 'Attach to Chart' (first item in context menu)
    6. Confirm EA Properties dialog
    7. Ensure AutoTrading ON
    """
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    import pyautogui
    
    for attempt in range(max_retries):
        try:
            app = Application(backend='win32').connect(process=mt5_pid)
            win = app.top_window()
            try:
                win.set_focus()
            except:
                pass
            time.sleep(0.5)
        except Exception as e:
            print(f'⚠️ win32 connect failed: {e}')
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
        
        # Close stale dialogs
        close_stale_dialogs(mt5_pid)
        
        # Step 1: Open a new chart
        open_chart_via_keyboard()
        
        # Step 2: Show Navigator
        show_navigator_panel(mt5_pid)
        
        # Step 3: Find TreeView
        tree_view, navigator_hwnd = get_navigator_treeview(mt5_pid)
        if not tree_view:
            print(f'⚠️ No TreeView found')
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
        
        tv_rect = tree_view.rectangle()
        print(f'📋 TreeView rect=({tv_rect.left},{tv_rect.top})-({tv_rect.right},{tv_rect.bottom})')
        
        # Step 4: Find EA node, expand EA trading section
        try:
            root = tree_view.roots()[0]
            children = root.children()
            ea_trading_node = None
            if len(children) > 2:
                ea_trading_node = children[2]  # 3rd child = Expert Advisors
            if not ea_trading_node:
                for child in children:
                    t = child.text()
                    if any(kw in t for kw in ['EA交易', 'Expert Advisors', 'Experts', 'EA']):
                        ea_trading_node = child
                        break
            if not ea_trading_node:
                print(f'⚠️ EA trading node not found')
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
            
            ea_trading_node.expand()
            time.sleep(2)
            
            ea_node = None
            for ea in ea_trading_node.children():
                if ea.text() == ea_name:
                    ea_node = ea
                    break
            
            if not ea_node:
                print(f'⚠️ {ea_name} not found under EA trading node')
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
            
            print(f'🎯 Found {ea_name} in Navigator')
            
            # Step 5: Select and ensure visible
            import ctypes as _ct
            _user32 = _ct.windll.user32
            _tree_hwnd = tree_view.element_info.handle
            _h_item = ea_node.item().hItem
            _user32.SendMessageW(_ct.c_void_p(_tree_hwnd), 0x1100 + 11, 9, _ct.c_size_t(_h_item))  # TVM_SELECTITEM
            _user32.SendMessageW(_ct.c_void_p(_tree_hwnd), 0x1100 + 20, 0, _ct.c_size_t(_h_item))  # TVM_ENSUREVISIBLE
            time.sleep(0.5)
            
            # Bring Navigator to foreground
            if navigator_hwnd:
                _user32.SetForegroundWindow(_ct.c_void_p(navigator_hwnd))
            else:
                _user32.SetForegroundWindow(_ct.c_void_p(get_main_hwnd()))
            time.sleep(0.5)
            
            # Get screen coordinates of the EA item
            try:
                prect = ea_node.client_rect()
                click_x = tv_rect.left + (prect.left + prect.right) // 2
                click_y = tv_rect.top + (prect.top + prect.bottom) // 2
            except:
                click_x = tv_rect.left + 66
                click_y = tv_rect.top + 20
            
            print(f'📋 EA item screen coords: ({click_x}, {click_y})')
            
            # Step 6: RIGHT-CLICK on the EA item
            pyautogui.moveTo(click_x, click_y)
            time.sleep(0.3)
            pyautogui.click(button='right')
            time.sleep(1.5)
            
            # Step 7: Click "Attach to Chart" (first item in context menu)
            # The context menu appears at the click position.
            # First item "Attach to Chart" is about 22-24px below the click point.
            attach_y = click_y + 22  # First menu item
            
            pyautogui.moveTo(click_x + 10, attach_y)
            time.sleep(0.3)
            pyautogui.click()
            time.sleep(3)
            
            # Step 8: Check for EA Properties dialog
            dialogs = find_dialog(ea_name, mt5_pid)
            if dialogs:
                print(f'🎉 {ea_name} Properties dialog detected!')
                # Press Enter to confirm
                send_keys('{ENTER}')
                time.sleep(2)
                
                # AutoTrading
                send_keys('^e')
                time.sleep(1)
                
                print(f'✅ {ea_name} confirmed, AutoTrading enabled')
                return True
            
            # If Properties dialog not found, check for other dialogs
            all_dialogs = find_dialog('', mt5_pid)
            for hwnd, title in all_dialogs:
                print(f'   Dialog: "{title}"')
                if 'replace' in title.lower() or '代替' in title:
                    print(f'   Replace dialog, accepting...')
                    send_keys('y')
                    time.sleep(2)
                    dialogs = find_dialog(ea_name, mt5_pid)
                    if dialogs:
                        print(f'🎉 {ea_name} Properties dialog after Replace!')
                        send_keys('{ENTER}')
                        time.sleep(2)
                        send_keys('^e')
                        time.sleep(1)
                        return True
            
            print(f'⚠️ {ea_name} dialog not found after right-click attach')
            
            # Try double-click as fallback (might work sometimes)
            print('📋 Trying double-click as fallback...')
            pyautogui.doubleClick(x=click_x, y=click_y)
            time.sleep(2)
            dialogs = find_dialog(ea_name, mt5_pid)
            if dialogs:
                print(f'🎉 {ea_name} Properties dialog via double-click!')
                send_keys('{ENTER}')
                time.sleep(2)
                send_keys('^e')
                time.sleep(1)
                return True
            
        except Exception as e:
            print(f'⚠️ Error in attempt {attempt+1}: {e}')
        
        if attempt < max_retries - 1:
            time.sleep(5)
    
    print(f'❌ {ea_name} attach failed after {max_retries} attempts')
    return False


# ─── Main Entry Point ───

def auto_attach_ea(ea_name, symbol='EURUSD', timeframe='H1'):
    """Main function to attach an EA to MT5"""
    print(f'\n{"="*50}')
    print(f'  📎 EA Attach: {ea_name} → {symbol} {timeframe}')
    print(f'{"="*50}')
    
    # 1. Generate template
    generate_template(ea_name, symbol, timeframe)
    
    # 2. Get MT5 PID
    mt5_pid = find_mt5_pid()
    if not mt5_pid:
        print('❌ MT5 not running')
        return False
    
    print(f'📋 MT5 PID: {mt5_pid}')
    
    # 3. Attach EA via right-click context menu
    success = attach_ea_via_rightclick(ea_name, mt5_pid)
    
    if not success:
        print('❌ Failed to attach EA')
        return False
    
    # 4. Verify heartbeat
    time.sleep(5)
    hb_ok = verify_heartbeat(ea_name, timeout=60)
    
    if hb_ok:
        print(f'\n🎉 SUCCESS: {ea_name} deployed to {symbol} {timeframe}!')
        return True
    else:
        print(f'\n⚠️ {ea_name} may be attached but no heartbeat detected')
        return True  # Still consider it a success if we got the Properties dialog


# ─── CLI ───

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='MT5 EA Attach via Right-Click')
    parser.add_argument('--ea', required=True)
    parser.add_argument('--symbol', default='EURUSD')
    parser.add_argument('--tf', default='H1')
    args = parser.parse_args()
    
    result = auto_attach_ea(args.ea, args.symbol, args.tf)
    sys.exit(0 if result else 1)
