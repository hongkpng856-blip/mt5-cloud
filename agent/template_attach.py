"""
Template-apply approach for MT5 EA attachment.
Instead of Navigator double-click, use right-click → Template → Apply Template.
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
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
COMMON_FILES = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                            'Common', 'Files')

TF_CODES = {
    'M1': 16385, 'M5': 16389, 'M15': 16401, 'M30': 16416,
    'H1': 32801, 'H4': 32805, 'D1': 49201, 'W1': 65601, 'MN1': 82001,
}

user32 = ctypes.windll.user32

def find_mt5_pid():
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None

def get_mt5_window_rect():
    hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
    if not hwnd:
        return None, None
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return hwnd, rect

def get_chart_area_rect(mt5_pid):
    """Find the MDIClient area (chart area) of MT5"""
    app = Application(backend='uia').connect(process=mt5_pid)
    win = app.top_window()
    for d in win.descendants():
        if d.element_info.class_name == 'MDIClient':
            r = d.rectangle()
            return r
    # Fallback: center of main window right of Navigator
    _, rect = get_mt5_window_rect()
    if rect:
        # Chart area is typically right of Navigator (approx x=270 to right-10)
        return type('Rect', (), {
            'left': rect.left + 270,
            'top': rect.top + 50,
            'right': rect.right - 10,
            'bottom': rect.bottom - 50
        })()
    return None

def generate_template(ea_name, symbol='EURUSD', timeframe='H1'):
    """Generate .tpl template (same as auto_attach.py)"""
    os.makedirs(TPL_DIR, exist_ok=True)
    tf_code = TF_CODES.get(timeframe, 32801)
    
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
        f"path=Experts\\\\{ea_name}.ex5\r\n"
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
    
    tpl_name = f"{ea_name}_{symbol}_{timeframe}"
    tpl_path = os.path.join(TPL_DIR, f"{tpl_name}.tpl")
    
    with open(tpl_path, 'wb') as f:
        f.write(b'\xff\xfe')  # UTF-16 LE BOM
        f.write(tpl_content.encode('utf-16-le'))
    
    print(f"📋 Template saved: {tpl_path} ({os.path.getsize(tpl_path)} bytes)")
    return tpl_path, tpl_name

def open_chart(symbol='EURUSD'):
    """Open new chart via keyboard shortcut"""
    from pywinauto.keyboard import send_keys
    
    # Ctrl+Shift+S to show all symbols (opens Symbol dialog)
    send_keys('^+s')
    time.sleep(2)
    
    # Insert to select + open chart
    send_keys('{INSERT}')
    time.sleep(2)
    
    # Enter to confirm
    send_keys('{ENTER}')
    time.sleep(3)
    print(f"📋 New chart opened for {symbol}")

def apply_template_via_context_menu(tpl_name, mt5_pid):
    """
    Apply template via right-click → Template → Apply Template → template name.
    Uses pyautogui to navigate the context menu.
    """
    import pyautogui
    
    # Get chart area center
    chart_rect = get_chart_area_rect(mt5_pid)
    if not chart_rect:
        print("❌ Cannot find chart area")
        return False
    
    cx = (chart_rect.left + chart_rect.right) // 2
    cy = (chart_rect.top + chart_rect.bottom) // 2
    
    print(f"📋 Chart area center: ({cx}, {cy})")
    
    # Step 1: Bring MT5 to foreground
    hwnd, _ = get_mt5_window_rect()
    if hwnd:
        user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
        time.sleep(0.5)
    
    # Step 2: Right-click on chart
    pyautogui.moveTo(cx, cy)
    time.sleep(0.3)
    pyautogui.click(button='right')
    time.sleep(0.5)
    
    # Step 3: The context menu appears at the click position.
    # "Template" is typically 7-8 items down (Expert Advisors, Indicators, Objects, 
    # Grid, Volume, OneClick Trading, Period, Template...)
    # At 100% DPI, each menu item is ~20px tall.
    # Offset for "Template": 8 items * 20px = 160px below right-click
    
    menu_x = cx
    menu_y = cy
    
    # Template submenu position (approximately 8 items down)
    template_y = menu_y + 8 * 22
    pyautogui.moveTo(cx + 20, template_y, duration=0.2)
    time.sleep(1.0)
    
    # Step 4: Apply Template submenu (appears to the right)
    apply_template_y = template_y + 2 * 22  # Save Template, Apply Template
    # Move to submenu
    pyautogui.moveTo(cx + 200, apply_template_y, duration=0.2)
    time.sleep(0.5)
    
    # Step 5: Find our template in the list
    # Templates appear in alphabetical order, the most recent one might be at bottom
    # Move to the bottom of the submenu where new templates appear
    pyautogui.moveTo(cx + 200, apply_template_y + 10 * 22, duration=0.2)
    time.sleep(0.3)
    pyautogui.click()
    time.sleep(2)
    
    # Check for dialog (EA might need confirming)
    dialogs = find_dialog("", mt5_pid)
    for d in dialogs:
        print(f"   Dialog found: '{d}'")
    
    return True

def find_dialog(target, mt5_pid):
    """Find dialog windows belonging to MT5"""
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
                    results.append(title.value)
        return True
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    user32.EnumWindows(CB(cb), 0)
    return results

def verify_heartbeat(ea_name, timeout=30):
    hb_file = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(hb_file):
            mtime = os.path.getmtime(hb_file)
            age = time.time() - mtime
            print(f"💓 {ea_name} heartbeat: {round(age)}s old")
            if age < 300:
                return True
        time.sleep(2)
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python template_attach.py --ea EA_NAME [--symbol SYMBOL] [--tf TF]")
        return
    
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--ea', required=True)
    parser.add_argument('--symbol', default='EURUSD')
    parser.add_argument('--tf', default='H1')
    args = parser.parse_args()
    
    ea_name = args.ea
    symbol = args.symbol
    timeframe = args.tf
    
    print(f"\n{'='*50}")
    print(f"  📎 Template-Attach: {ea_name} → {symbol} {timeframe}")
    print(f"{'='*50}")
    
    # 1. Generate template
    tpl_path, tpl_name = generate_template(ea_name, symbol, timeframe)
    
    # 2. Get MT5 PID
    mt5_pid = find_mt5_pid()
    if not mt5_pid:
        print("❌ MT5 not running")
        sys.exit(1)
    print(f"📋 MT5 PID: {mt5_pid}")
    
    # 3. Open a chart for the symbol
    open_chart(symbol)
    
    # 4. Apply the template via context menu
    success = apply_template_via_context_menu(tpl_name, mt5_pid)
    
    # 5. Verify
    time.sleep(5)
    hb_ok = verify_heartbeat(ea_name, timeout=30)
    
    if hb_ok:
        print(f"\n🎉 SUCCESS: {ea_name} deployed to {symbol} {timeframe}!")
        sys.exit(0)
    else:
        print(f"\n❌ FAILED: {ea_name} — heartbeat not detected")
        sys.exit(1)

if __name__ == '__main__':
    main()
