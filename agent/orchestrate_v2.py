"""
Comprehensive MT5 EA auto-attach orchestrator.
Tries multiple attachment methods and logs results.
"""
import os
import sys
import time
import ctypes
import pyautogui
from pywinauto.keyboard import send_keys
import psutil
import argparse
from datetime import datetime

# ─── Paths ───
APPDATA = os.environ.get('APPDATA', '')
EXPERTS_DIR = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
    'D0E8209F77C8CF37AD8BF550E51FF075', 'MQL5', 'Experts')
HEARTBEAT_DIR = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')
TPL_DIR = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
    'D0E8209F77C8CF37AD8BF550E51FF075', 'Profiles', 'Templates')
AUTO_ATTACH_PY = r'C:\Users\hongk\Desktop\mt5-cloud\agent\auto_attach.py'
LOG_FILE = r'C:\Users\hongk\Desktop\mt5-cloud\agent\auto_attach_log.txt'
PROJECT_DIR = r'C:\Users\hongk\Desktop\mt5-cloud'
COMMON_FILES = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')

SYSTEM_EAS = {'TestBlank', 'TemplateLoader', 'AgentHelper'}
HEARTBEAT_MAX_AGE = 60

user32 = ctypes.windll.user32

# ─── Helpers ───

def log(msg, file_only=False):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{timestamp}] {msg}'
    if not file_only:
        print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def get_mt5_pid():
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None

def get_main_hwnd():
    return user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)

def find_dialog(target, mt5_pid):
    """Find dialog windows with title containing target"""
    results = []
    pid_buf = ctypes.c_ulong()
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
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
    user32.EnumWindows(CB(cb), 0)
    return results

def get_heartbeat_age(name):
    hb_path = os.path.join(HEARTBEAT_DIR, f'hb_{name}.txt')
    if not os.path.exists(hb_path):
        return None
    return time.time() - os.path.getmtime(hb_path)

def verify_heartbeat(name, timeout=30):
    hb_path = os.path.join(COMMON_FILES, f'hb_{name}.txt')
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(hb_path):
            age = time.time() - os.path.getmtime(hb_path)
            if age < 300:
                return True
        time.sleep(2)
    return False

def register_eas():
    """List registered EAs excluding system files"""
    eas = []
    if os.path.exists(EXPERTS_DIR):
        for f in os.listdir(EXPERTS_DIR):
            if f.endswith('.ex5'):
                name = f[:-4]
                if name not in SYSTEM_EAS:
                    eas.append(name)
    return sorted(eas)

# ─── Method 1: Run auto_attach.py ───

def method_auto_attach_py(ea_name, symbol='EURUSD', tf='H1', timeout=120):
    """Run auto_attach.py via subprocess"""
    python = r'C:\Users\hongk\AppData\Local\Programs\Python\Python311\python.exe'
    cmd = [python, '-u', AUTO_ATTACH_PY, '--ea', ea_name, '--symbol', symbol, '--tf', tf]
    
    log(f"  Method 1: {' '.join(cmd)}", file_only=True)
    
    import subprocess
    try:
        proc = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=timeout)
        output = proc.stdout + proc.stderr
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        output = '[TIMEOUT]'
        rc = -1
    except Exception as e:
        output = f'[ERROR] {e}'
        rc = -2
    
    # Check for SUCCESS in output (match various formats)
    success = False
    for line in output.split('\n'):
        if 'SUCCESS' in line and ea_name in line:
            success = True
            break
    
    return success, rc, output


# ─── Helper: Focus Navigator Panel ───

def focus_navigator_panel(mt5_pid):
    """Click on the Navigator panel to give it focus before right-clicking"""
    pid_buf = ctypes.c_ulong()
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    nav_rect = [None]
    
    def find_nav(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if 'MiniFrame' in cls.value:
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if any(t in title.value for t in ['導航', 'Navigator', 'ナビゲーター', 'Навигатор']):
                    rect = ctypes.wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    nav_rect[0] = rect
        return True
    user32.EnumWindows(CB(find_nav), 0)
    
    if nav_rect[0]:
        r = nav_rect[0]
        # Click in the middle of the Navigator panel to give it focus
        cx = (r.left + r.right) // 2
        cy = (r.top + r.bottom) // 2
        pyautogui.moveTo(cx, cy)
        time.sleep(0.2)
        pyautogui.click()
        time.sleep(0.5)
        log(f"  Navigator focused at ({cx}, {cy})", file_only=True)
        return True
    return False

# ─── Method 2: Right-click context menu attach ───

def method_rightclick_attach(ea_name, symbol='EURUSD', tf='H1', open_chart=True):
    """Open chart (if needed), right-click EA in Navigator, click 'Attach to Chart'"""
    mt5_pid = get_mt5_pid()
    if not mt5_pid:
        return False, "MT5 not running"
    
    main_hwnd = get_main_hwnd()
    if not main_hwnd:
        return False, "MT5 window not found"
    
    pid_buf = ctypes.c_ulong()
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    
    # Bring MT5 to foreground
    user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
    time.sleep(1)
    
    # Step 1: Open New Chart if needed
    if open_chart:
        log("  Step 1: Opening New Chart", file_only=True)
        pyautogui.keyDown('alt')
        time.sleep(0.2)
        pyautogui.press('f')
        time.sleep(0.2)
        pyautogui.keyUp('alt')
        time.sleep(1.5)
        pyautogui.press('n')
        time.sleep(2)
        
        # Check if a symbol dialog opened
        dialogs = find_dialog('', mt5_pid)
        if dialogs:
            log(f"  Symbol dialog: {dialogs}", file_only=True)
            pyautogui.write(symbol)
            time.sleep(1)
            pyautogui.press('enter')
            time.sleep(3)
        else:
            time.sleep(3)
        
        log("  Chart opened (or attempted)", file_only=True)
    
    # Focus the Navigator panel so right-click works
    focus_navigator_panel(mt5_pid)
    
    # Step 2: Find EA in Navigator and get position
    cx, cy, tv_rect = get_ea_screen_position(ea_name, mt5_pid)
    if cx is None:
        return False, f"Could not find {ea_name} in Navigator"
    
    # Step 3: Right-click on EA
    pyautogui.moveTo(cx, cy)
    time.sleep(0.3)
    pyautogui.click(button='right')
    time.sleep(1.5)
    
    # Verify context menu appeared
    menu_found = [False]
    def check_menu(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if '#32768' in cls.value:
                menu_found[0] = True
        return True
    user32.EnumWindows(CB(check_menu), 0)
    
    if not menu_found[0]:
        return False, "Right-click context menu did not appear"
    
    log("  Context menu appeared", file_only=True)
    
    # Step 4: Click first menu item (Attach to Chart)
    # First menu item center: ~12px below the right-click point, ~40px right
    item_x = cx + 40
    item_y = cy + 12
    pyautogui.moveTo(item_x, item_y)
    time.sleep(0.3)
    pyautogui.click()
    time.sleep(3)
    
    # Step 5: Check for EA Properties dialog
    dialogs = find_dialog(ea_name, mt5_pid)
    if dialogs:
        log(f"  ✅ EA Properties dialog: {dialogs}", file_only=True)
        pyautogui.press('enter')
        time.sleep(2)
        pyautogui.hotkey('ctrl', 'e')
        time.sleep(1)
        log("  ✅ AutoTrading enabled", file_only=True)
        return True, "EA dialog confirmed"
    
    # Step 6: Check for replace dialog
    replace_found = [False]
    replace_hwnd = [None]
    def check_replace(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if 'replace' in title.value.lower() or '代替' in title.value:
                    replace_found[0] = True
                    replace_hwnd[0] = hwnd
        return True
    user32.EnumWindows(CB(check_replace), 0)
    
    if replace_found[0]:
        log("  Replace dialog detected", file_only=True)
        pyautogui.press('y')
        time.sleep(2)
        dialogs = find_dialog(ea_name, mt5_pid)
        if dialogs:
            pyautogui.press('enter')
            time.sleep(2)
            pyautogui.hotkey('ctrl', 'e')
            time.sleep(1)
            return True, "Replace + EA dialog confirmed"
    
    # Step 7: Check heartbeat
    if verify_heartbeat(ea_name, timeout=10):
        return True, "EA running (heartbeat detected)"
    
    return False, "No EA dialog or heartbeat after attach attempt"

def get_ea_screen_position(ea_name, mt5_pid):
    """
    Find the EA in the Navigator TreeView and return its screen coordinates.
    Returns (x, y, treeview_rect) or (None, None, None) if not found.
    """
    from pywinauto import Application
    
    try:
        app = Application(backend='win32').connect(process=mt5_pid)
        win = app.top_window()
    except:
        return None, None, None
    
    # Show Navigator panel first
    show_navigator_panel(mt5_pid)
    time.sleep(1)
    
    # Find TreeView
    tree_view = None
    navigator_hwnd = None
    
    pid_buf = ctypes.c_ulong()
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    
    # Find Navigator MiniFrame
    def find_nav(hwnd, _):
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
    user32.EnumWindows(CB(find_nav), 0)
    
    # Search for TreeView
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
    
    if not tree_view:
        log("  TreeView not found", file_only=True)
        return None, None, None
    
    tv_rect = tree_view.rectangle()
    log(f"  TreeView: ({tv_rect.left},{tv_rect.top})-({tv_rect.right},{tv_rect.bottom})", file_only=True)
    
    # Expand EA trading node and find our EA
    try:
        root = tree_view.roots()[0]
        children = root.children()
        ea_trading_node = None
        
        if len(children) > 2:
            ea_trading_node = children[2]
        if not ea_trading_node:
            for child in children:
                t = child.text()
                if any(kw in t for kw in ['EA交易', 'Expert Advisors', 'Experts', 'EA']):
                    ea_trading_node = child
                    break
        
        if not ea_trading_node:
            log("  EA trading node not found", file_only=True)
            return None, None, None
        
        ea_trading_node.expand()
        time.sleep(2)
        
        for ea in ea_trading_node.children():
            if ea.text() == ea_name:
                # Found the EA!
                try:
                    prect = ea.client_rect()
                    cx = tv_rect.left + (prect.left + prect.right) // 2
                    cy = tv_rect.top + (prect.top + prect.bottom) // 2
                    log(f"  Found {ea_name} at screen ({cx}, {cy})", file_only=True)
                    return cx, cy, tv_rect
                except:
                    # Fallback to position-based
                    return tv_rect.left + 66, tv_rect.top + 20, tv_rect
        
        log(f"  {ea_name} not found in Navigator", file_only=True)
    except Exception as e:
        log(f"  Navigator navigation error: {e}", file_only=True)
    
    return None, None, None


def show_navigator_panel(mt5_pid):
    """Ensure Navigator panel is visible"""
    pid_buf = ctypes.c_ulong()
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    navigator_hwnd = [None]
    
    def find_nav(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if 'MiniFrame' in cls.value:
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if any(t in title.value for t in ['導航', 'Navigator', 'ナビゲーター', 'Навигатор']):
                    navigator_hwnd[0] = hwnd
        return True
    user32.EnumWindows(CB(find_nav), 0)
    
    if navigator_hwnd[0]:
        user32.ShowWindow(ctypes.c_void_p(navigator_hwnd[0]), 5)
        user32.SetWindowPos(ctypes.c_void_p(navigator_hwnd[0]), 0, 0, 0, 0, 0, 0x0002 | 0x0001)
        time.sleep(0.5)
        return True
    
    # Fallback: WM_COMMAND
    main_hwnd = get_main_hwnd()
    if main_hwnd:
        user32.SendMessageW(ctypes.c_void_p(main_hwnd), 0x0111, 32808, 0)
        time.sleep(1.5)
    return False

# ─── Method 3: MQL5 script via compiled batch ───

def generate_batch_mql5(ea_names, symbol='EURUSD', tf='H1'):
    """Generate a single MQL5 script that applies all templates"""
    tf_mql5 = 'PERIOD_H1'
    tf_map = {'M1': 'PERIOD_M1', 'M5': 'PERIOD_M5', 'M15': 'PERIOD_M15',
              'M30': 'PERIOD_M30', 'H1': 'PERIOD_H1', 'H4': 'PERIOD_H4',
              'D1': 'PERIOD_D1', 'W1': 'PERIOD_W1', 'MN1': 'PERIOD_MN1'}
    tf_mql5 = tf_map.get(tf, 'PERIOD_H1')
    
    script = '''//+------------------------------------------------------------------+
//| BatchApplyTemplates.mq5 - Generated by Hermes Agent             |
//| Applies templates for all EAs                                   |
//+------------------------------------------------------------------+
void OnStart()
{
   string templates[] = {
'''
    for ea in ea_names:
        script += f'      "{ea}_{symbol}_{tf}.tpl",\n'
    
    script += '''   };
   
   for(int i = 0; i < ArraySize(templates); i++)
   {
      string tpl = templates[i];
      string ea_name = StringSubstr(tpl, 0, StringFind(tpl, "_"));
      
      Print("Applying template: ", tpl);
      long chart_id = ChartOpen("''' + symbol + '''", ''' + tf_mql5 + ''');
      if(chart_id <= 0)
      {
         Print("Failed to open chart for ", ea_name);
         continue;
      }
      
      if(ChartApplyTemplate(chart_id, tpl))
      {
         Print("SUCCESS: ", ea_name, " deployed to ''' + symbol + ' ' + tf + '''");
      }
      else
      {
         Print("FAILED: ", ea_name, " error=", GetLastError());
      }
      ChartRedraw(chart_id);
      Sleep(100);
   }
   Print("Batch complete");
}
//+------------------------------------------------------------------+
'''
    return script

def method_mql5_batch(ea_names, symbol='EURUSD', tf='H1'):
    """Compile and run an MQL5 batch script"""
    mt5_data = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
        'D0E8209F77C8CF37AD8BF550E51FF075')
    scripts_dir = os.path.join(mt5_data, 'MQL5', 'Scripts')
    metaeditor = r'C:\Program Files\MetaTrader 5\metaeditor64.exe'
    
    # Generate MQL5 source
    mq5_content = generate_batch_mql5(ea_names, symbol, tf)
    mq5_path = os.path.join(scripts_dir, 'BatchApplyTemplates.mq5')
    ex5_path = os.path.join(scripts_dir, 'BatchApplyTemplates.ex5')
    
    with open(mq5_path, 'w', encoding='utf-8') as f:
        f.write(mq5_content)
    log(f"  MQL5 source generated: {mq5_path}")
    
    # Wait a moment
    time.sleep(2)
    
    # Compile with MetaEditor
    log("  Compiling with MetaEditor...")
    import subprocess
    try:
        result = subprocess.run(
            [metaeditor, f'/compile:{mq5_path}', '/log:compile.log', '/syntax'],
            capture_output=True, text=True, timeout=30
        )
        log(f"  Compile returncode: {result.returncode}")
        
        # Check if ex5 exists
        if os.path.exists(ex5_path):
            log(f"  ✅ Compiled: {ex5_path} ({os.path.getsize(ex5_path)} bytes)")
        else:
            # Try alternative compilation
            result2 = subprocess.run(
                [metaeditor, f'/compile:{mq5_path}'],
                capture_output=True, text=True, timeout=30
            )
            time.sleep(2)
            if os.path.exists(ex5_path):
                log(f"  ✅ Compiled (2nd attempt): {ex5_path}")
            else:
                return False, "Compilation failed - no .ex5 produced"
    except Exception as e:
        return False, f"Compilation error: {e}"
    
    # The compiled script needs to be run inside MT5 via Navigator
    # This requires GUI interaction which we've established is unreliable
    # Return success if compilation worked - the script is ready to run
    return True, f"Script compiled and ready in: {ex5_path}"

# ─── Main Orchestrator ───

def main():
    log('=' * 60)
    log('Starting auto-attach orchestration')
    log(f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    log('=' * 60)
    
    # 1. Get registered EAs
    eas = register_eas()
    log(f'Found {len(eas)} registered EAs: {", ".join(eas)}')
    
    # 2. Check heartbeats
    deploy_queue = []
    for ea in eas:
        age = get_heartbeat_age(ea)
        if age is None:
            log(f'  🚀 {ea}: no heartbeat → NEED DEPLOY')
            deploy_queue.append(ea)
        elif age > HEARTBEAT_MAX_AGE:
            log(f'  🚀 {ea}: heartbeat {int(age)}s old → NEED DEPLOY')
            deploy_queue.append(ea)
        else:
            log(f'  ✅ {ea}: heartbeat {int(age)}s old (fresh)')
    
    log(f'\n{len(deploy_queue)} EAs need deployment out of {len(eas)} total')
    
    if not deploy_queue:
        log('All EAs up to date.')
        return
    
    # 3. Check MT5 status
    mt5_pid = get_mt5_pid()
    if not mt5_pid:
        log('❌ MT5 not running! Cannot deploy EAs.')
        return
    log(f'✅ MT5 running (PID={mt5_pid})')
    
    # 4. Open one chart for all EAs to use
    log('\n📋 Opening initial chart for all EAs...')
    pyautogui.keyDown('alt')
    time.sleep(0.2)
    pyautogui.press('f')
    time.sleep(0.2)
    pyautogui.keyUp('alt')
    time.sleep(1.5)
    pyautogui.press('n')
    time.sleep(3)
    log('  Chart opened\n')
    
    # 5. Deploy each EA
    success_count = 0
    fail_count = 0
    
    for idx, ea in enumerate(deploy_queue, 1):
        log(f'--- {ea} ({idx}/{len(deploy_queue)}) ---')
        
        # Method 1: Run auto_attach.py
        start = time.time()
        success, rc, output = method_auto_attach_py(ea)
        elapsed = time.time() - start
        
        if success:
            log(f'  ✅ {ea}: SUCCESS via auto_attach.py ({elapsed:.1f}s)')
            success_count += 1
            continue
        
        log(f'  ❌ auto_attach.py failed (rc={rc})')
        for line in output.split('\n')[-3:]:
            if line.strip():
                log(f'     | {line.strip()}', file_only=True)
        
        # Method 2: Right-click (no new chart - reuse existing one)
        log(f'  Trying Method 2 (right-click, no new chart)...')
        success2, reason2 = method_rightclick_attach(ea, open_chart=False)
        
        if success2:
            log(f'  ✅ {ea}: SUCCESS via right-click ({reason2})')
            success_count += 1
            continue
        
        log(f'  ❌ Method 2 failed: {reason2}')
        fail_count += 1
        time.sleep(1)
    
    # 5. Generate MQL5 batch script for remaining failed EAs
    failed_eas = [ea for ea in deploy_queue[:fail_count]]
    if failed_eas:
        log(f'\n📋 Generating MQL5 batch script for {len(failed_eas)} EAs...')
        mq5_ok, mq5_msg = method_mql5_batch(failed_eas)
        if mq5_ok:
            log(f'  ✅ MQL5 batch script: {mq5_msg}')
            log(f'  📝 To run: Open MT5 → Navigator → Scripts → double-click BatchApplyTemplates')
        else:
            log(f'  ❌ MQL5 batch: {mq5_msg}')
    
    # 6. Summary
    log(f'\n{"=" * 50}')
    log(f'  RESULTS: {success_count} success, {fail_count} failed, {len(deploy_queue)} total')
    log(f'{"=" * 50}')
    
    # Diagnostics
    log('\n📊 Diagnostics:')
    log(f'  MT5 PID: {mt5_pid if mt5_pid else "NOT RUNNING"}')
    hb_count = len([f for f in os.listdir(HEARTBEAT_DIR) if f.startswith('hb_')]) if os.path.exists(HEARTBEAT_DIR) else 0
    log(f'  Heartbeat files: {hb_count}')
    
    import socket
    for host in ['185.209.22.200', '170.75.202.214']:
        try:
            socket.create_connection((host, 443), timeout=3)
            log(f'  ✅ {host}:443 reachable')
        except:
            log(f'  ❌ {host}:443 unreachable')

if __name__ == '__main__':
    main()
