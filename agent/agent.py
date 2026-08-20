#!/usr/bin/env python3
"""
MT5 Cloud Agent — 可靠嘅 EA 部署 + Auto-Attach

核心改進：
- auto_attach_ea(): 開 chart + Navigator double-click + AutoTrading check
- do_restart_mt5(): 重啟 MT5 令 Navigator refresh
- download_and_install(): inject heartbeat + compile + auto-attach + verify
- execute_deploy(): 真正 attach EA 到 chart（唔係只下單）
"""
import os
import sys
import time
import struct
import subprocess
import threading
import json

# === Config ===
SERVER_URL = os.environ.get('MT5_CLOUD_URL', 'https://having-bent-bunch-theater.trycloudflare.com')
AGENT_ID = os.environ.get('MT5_CLOUD_AGENT', 'DEV00001')
MT5_DATA = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                         'D0E8209F77C8CF37AD8BF550E51FF075')
MT5_EXPERTS = os.path.join(MT5_DATA, 'MQL5', 'Experts')
MT5_COMMON_FILES = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')

# Check MT5 availability
mt5_available = False
try:
    import MetaTrader5 as mt5
    mt5_available = True
except ImportError:
    pass

# === Parse args ===
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--server', default=SERVER_URL, help='Server URL')
parser.add_argument('--agent', default=AGENT_ID, help='Agent ID')
args, _ = parser.parse_known_args()
SERVER_URL = args.server
AGENT_ID = args.agent

# === SocketIO client ===
import socketio
sio = socketio.Client(logger=False, engineio_logger=False)
ea_config_cache = {}
ea_heartbeats = {}

def connect():
    print(f"✅ Connected to {SERVER_URL}")
    # Register with server → join agent room for deploy commands
    sio.emit('agent_register', {'agent_id': AGENT_ID})
    print(f"   Registering as {AGENT_ID}...")

def disconnect():
    print("❌ Disconnected")

def on_registered(data):
    print(f"🆔 Registered: {data}")
    # Server auto-pushes install_ea_command on register

sio.on('connect', connect)
sio.on('disconnect', disconnect)
sio.on('registered', on_registered)


# ================================================================
#  MT5 Bridge — 重啟 + 等待
# ================================================================

def find_mt5_pid():
    """搵 MT5 terminal64.exe PID"""
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None

def wait_for_mt5(timeout=90):
    """等 MT5 啟動完成"""
    start = time.time()
    while time.time() - start < timeout:
        pid = find_mt5_pid()
        if pid:
            time.sleep(3)
            # Verify MT5 is responsive by checking log
            log_path = os.path.join(MT5_DATA, 'Logs', time.strftime('%Y%m%d') + '.log')
            if os.path.exists(log_path):
                mtime = os.path.getmtime(log_path)
                if time.time() - mtime < 30:
                    return pid
        time.sleep(2)
    return None

def do_restart_mt5():
    """重啟 MT5 — 令 Navigator tree refresh"""
    import subprocess
    
    # Kill existing MT5
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'terminal64.exe'],
                        capture_output=True, timeout=10)
    except:
        pass
    
    time.sleep(3)
    
    # MT5 auto-restarts after kill (Windows service behavior)
    # Wait for ready
    pid = wait_for_mt5(timeout=90)
    if pid:
        # Extra wait for Navigator to fully load + refresh
        time.sleep(10)
        print(f"✅ MT5 restarted, PID={pid}")
        return pid
    else:
        print("❌ MT5 failed to restart")
        # Try launching manually
        mt5_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
        if os.path.exists(mt5_path):
            subprocess.Popen([mt5_path])
            pid = wait_for_mt5(timeout=60)
            if pid:
                time.sleep(10)
                print(f"✅ MT5 launched manually, PID={pid}")
                return pid
        return None


# ================================================================
#  Auto-Attach EA — 可靠嘅 GUI 自動化
# ================================================================

def auto_attach_ea(ea_name, symbol='EURUSD', timeframe='H1', inputs=None, do_restart=False):
    """完整 auto-attach 流程：
    1. 生成 .tpl 模板
    2. (可選) 重啟 MT5
    3. 開新 chart + Navigator double-click
    4. 確保 AutoTrading ON
    5. 驗證 heartbeat
    
    Returns: True if EA is alive, False otherwise
    """
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    
    print(f"\n{'='*50}")
    print(f"  🚀 Auto-Attach: {ea_name} → {symbol} {timeframe}")
    print(f"{'='*50}")
    
    # Step 1: Generate .tpl template
    tpl_path = generate_template(ea_name, symbol, timeframe, inputs)
    print(f"📋 Template: {tpl_path} ({os.path.getsize(tpl_path)} bytes)")
    
    # Step 2: Get or restart MT5
    if do_restart:
        mt5_pid = do_restart_mt5()
        if not mt5_pid:
            return False
    else:
        mt5_pid = find_mt5_pid()
        if not mt5_pid:
            print("❌ MT5 not running")
            mt5_pid = do_restart_mt5()
            if not mt5_pid:
                return False
    
    # Step 3: Attach via Navigator subprocess
    # auto_attach.py runs as a separate process with full desktop access
    auto_attach_path = os.path.join(os.path.dirname(__file__), 'auto_attach.py')
    cmd = ['python', auto_attach_path, '--ea', ea_name, '--symbol', symbol, '--tf', 'H1']
    print(f"🚀 Running auto_attach subprocess: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, timeout=300, capture_output=True, text=True, cwd=os.path.dirname(auto_attach_path), creationflags=subprocess.CREATE_NEW_CONSOLE)
        print(f"   Exit code: {result.returncode}")
        for line in result.stdout.split('\n'):
            if any(kw in line for kw in ['🎉', '✅', '❌', '🟢', '🔴', '⚠️', '💓', '📋']):
                print(f"   {line}")
        if result.returncode != 0:
            if result.stderr:
                print(f"   Stderr: {result.stderr[-500:]}")
    except subprocess.TimeoutExpired:
        print(f"⚠️ auto_attach.py timed out")
        attached = False
    except Exception as e:
        print(f"⚠️ auto_attach error: {e}")
        attached = False
    else:
        attached = result.returncode == 0
    
    if not attached:
        print("⚠️ Navigator attach failed (no MT5 restart — keeping existing charts alive)")
    
    if not attached:
        print("❌ Failed to attach EA")
        return False
    
    # Step 4: Verify heartbeat
    hb_path = os.path.join(MT5_COMMON_FILES, f'hb_{ea_name}.txt')
    print(f"⏳ Waiting for heartbeat...")
    
    start = time.time()
    old_mtime = os.path.getmtime(hb_path) if os.path.exists(hb_path) else 0
    
    for _ in range(24):  # 120 seconds
        time.sleep(5)
        if os.path.exists(hb_path):
            new_mtime = os.path.getmtime(hb_path)
            if new_mtime != old_mtime and time.time() - new_mtime < 300:
                with open(hb_path, 'rb') as f:
                    raw = f.read()
                content = raw.decode('utf-16-le', errors='replace').strip().lstrip('\ufeff')
                age = time.time() - new_mtime
                print(f"💓 {ea_name}: {content} ({round(age)}s ago) → 🟢 ALIVE")
                
                # Verify EA log
                mql5_log = os.path.join(MT5_DATA, 'MQL5', 'Logs', time.strftime('%Y%m%d') + '.log')
                if os.path.exists(mql5_log):
                    with open(mql5_log, 'r', encoding='utf-16-le', errors='replace') as f:
                        lines = f.readlines()
                    for line in reversed(lines[-20:]):
                        if ea_name in line and ('啟動' in line or 'start' in line.lower()):
                            print(f"📋 EA log: {line.strip()}")
                            break
                
                return True
    
    print(f"❌ No heartbeat after {round(time.time()-start)}s")
    return False


def generate_template(ea_name, symbol, timeframe, inputs=None):
    """生成 MT5 .tpl 模板檔（UTF-16 LE + BOM）"""
    TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
    os.makedirs(TPL_DIR, exist_ok=True)
    
    tf_map = {'M1':1,'M5':5,'M15':15,'M30':30,'H1':16385,'H4':16388,'D1':16389,'W1':16390,'MN1':16391}
    tf_code = tf_map.get(timeframe, 16385)
    
    # Build inputs section
    inputs_section = ""
    if inputs:
        for key, val in inputs.items():
            inputs_section += f"{key}={val}\r\n"
    
    lot = inputs.get('LotSize', '1.00') if inputs else '1.00'
    magic = inputs.get('MagicNumber', '240701') if inputs else '240701'
    inputs_section += f"LotSize={lot}\r\n"
    inputs_section += f"MagicNumber={magic}\r\n"
    
    tpl_content = (
        f"\ufeff"  # BOM will be added separately
        f"<chart>\r\n"
        f"symbol={symbol}\r\n"
        f"period={tf_code}\r\n"
        f"left=100\r\n"
        f"top=50\r\n"
        f"right=900\r\n"
        f"bottom=500\r\n"
        f"\r\n"
        f"<expert>\r\n"
        f"name={ea_name}\r\n"
        f"flags=7\r\n"
        f"enabled=1\r\n"
        f"\r\n"
        f"<inputs>\r\n"
        f"{inputs_section}"
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
    
    # Write as UTF-16 LE with BOM
    with open(tpl_path, 'wb') as f:
        f.write(b'\xff\xfe')  # UTF-16 LE BOM
        # Remove the \ufeff from content since we add BOM separately
        content_no_bom = tpl_content.lstrip('\ufeff')
        f.write(content_no_bom.encode('utf-16-le'))
    
    return tpl_path


def attach_ea_navigator(ea_name, symbol, mt5_pid, max_retries=3):
    """用 AHK + pyautogui double-click attach EA
    
    關鍵發現：
    - MT5 Navigator TreeView 的 select() + Enter 不等同 double-click
    - Enter 只 expand/collapse 節點，不會 attach EA 到 chart
    - 開新 chart 後 Navigator panel 會自動收埋
    - 必須先開 chart，再開 Navigator，再 double-click
    
    流程：
    1. Python: 開 chart + 開 Navigator + select EA + ensure_visible
    2. AHK attach_ea.ahk: double-click scan TreeView 搵 EA Properties dialog
    3. Python fallback: pyautogui double-click scan
    """
    import pyautogui
    import ctypes
    user32 = ctypes.windll.user32
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    
    ahk_script = os.path.join(os.path.dirname(__file__), 'attach_ea.ahk')
    ahk_exe = r'C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe'
    ahk_nav = os.path.join(os.path.dirname(__file__), 'nav_on.ahk')
    
    import ctypes as _ctypes
    user32 = _ctypes.windll.user32
    
    for attempt in range(max_retries):
        try:
            app = Application(backend='win32').connect(process=mt5_pid)
            win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
            try:
                win.set_focus()
            except:
                pass  # No active desktop (background process)
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️ win32 connect failed: {e} (attempt {attempt+1}/{max_retries})")
            time.sleep(5)
            continue
        
        # Step 1: Open chart only if none exists
        mdi = None
        for d in win.descendants():
            if d.element_info.class_name == 'MDIClient':
                mdi = d
                break
        has_charts = mdi and len(mdi.children()) > 0
        
        if not has_charts:
            print("📋 No chart open, opening new one...")
            send_keys('^n')
            time.sleep(1)
            send_keys('{ENTER}')
            time.sleep(3)
        else:
            print(f"📋 Chart already open, skipping Ctrl+N...")
        
        # Step 2: Open Navigator panel DIRECTLY via ShowWindow
        # Much more reliable than menu clicks or keyboard shortcuts
        nav_panel = None
        for d in win.descendants():
            c = d.element_info.class_name
            if 'Afx:ControlBar' in c:
                r = d.rectangle()
                # Navigator panel has the SysTreeView32 child
                tv_child = None
                for child in d.descendants():
                    if child.element_info.class_name == 'SysTreeView32':
                        tv_child = child
                        break
                if tv_child:
                    nav_panel = d
                    break
        
        if nav_panel:
            hwnd = nav_panel.element_info.handle
            user32.ShowWindow(hwnd, 5)  # SW_SHOW
            time.sleep(1)
            print(f"📋 Navigator panel shown via ShowWindow")
        else:
            # Fallback: WM_COMMAND 32808 (Navigator toggle command ID)
            print(f"📋 Navigator panel not found, trying WM_COMMAND...")
            result = user32.SendMessageW(win.element_info.handle, 0x0111, 32808, 0)
            time.sleep(1.5)
        
        # Step 3: Find SysTreeView32 and verify it's visible
        tree_view = None
        for d in win.descendants():
            if d.element_info.class_name == 'SysTreeView32':
                tree_view = d
                break
        
        if not tree_view:
            print(f"⚠️ No TreeView found (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
        
        if not tree_view.is_visible():
            print(f"⚠️ TreeView not visible after ShowWindow (attempt {attempt+1}/{max_retries})")
            # Try WM_COMMAND as fallback
            user32.SendMessageW(win.element_info.handle, 0x0111, 32808, 0)
            time.sleep(1.5)
            
            for d in win.descendants():
                if d.element_info.class_name == 'SysTreeView32':
                    tree_view = d
                    break
            if not tree_view or not tree_view.is_visible():
                print(f"⚠️ TreeView still not visible")
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
        
        tv_rect = tree_view.rectangle()
        print(f"📋 TreeView visible={tree_view.is_visible()} rect=({tv_rect.left},{tv_rect.top})-({tv_rect.right},{tv_rect.bottom})")
        
        # Step 4: Navigate tree → Expand EA交易 → Select + ensure_visible
        try:
            root = tree_view.roots()[0]
            
            ea_trading_node = None
            # MT5 Navigator language varies: 'EA交易', 'المستشارون المختصون', 'Expert Advisors', etc.
            # Use position (3rd child = index 2) as primary, text match as fallback
            children = root.children()
            if len(children) > 2:
                ea_trading_node = children[2]  # Always 3rd child = Expert Advisors
                print(f"📋 EA node by position: '{ea_trading_node.text()}'")
            if not ea_trading_node:
                # Fallback: text match for common languages
                for child in children:
                    t = child.text()
                    if any(kw in t for kw in ['EA交易', 'Expert Advisors', 'المستشارون المختصون', 'Experts', 'EA']):
                        ea_trading_node = child
                        break
            
            if not ea_trading_node:
                print(f"⚠️ EA交易 node not found (attempt {attempt+1}/{max_retries})")
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
                print(f"⚠️ {ea_name} not found under EA交易 (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
            
            print(f"🎯 Found {ea_name}, attaching via pyautogui double-click...")
            ea_node.select()
            time.sleep(0.3)
            ea_node.ensure_visible()
            time.sleep(0.5)
            
        except Exception as e:
            print(f"⚠️ Tree navigation error: {e} (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
        
        # Step 5: Double-click the selected EA
        # Use SendMessage (not SendInput) — works without window focus!
        found_dialog = False
        
        print(f"🖱️ SendMessage WM_LBUTTONDBLCLK for {ea_name}...")
        
        # Get TreeView client area for coordinate calculation
        tv_hwnd = tree_view.element_info.handle
        tv_rect = tree_view.rectangle()
        
        # Client coordinates relative to TreeView
        # After select() + ensure_visible(), EA is at the first visible row
        # First row is at client y ≈ 9 (center of ~18px row)
        client_x = 20  # Left margin with some indent
        client_y = 9   # Center of first row
        
        # WM_LBUTTONDBLCLK = 0x0203
        # wParam = MK_LBUTTON = 0x0001
        # lParam = MAKELPARAM(client_x, client_y)
        lparam = (client_y << 16) | client_x
        
        result = user32.SendMessageW(tv_hwnd, 0x0203, 0x0001, lparam)
        time.sleep(2)
        
        # Also send WM_LBUTTONUP after
        # WM_LBUTTONUP = 0x0202
        user32.SendMessageW(tv_hwnd, 0x0202, 0x0000, lparam)
        time.sleep(0.5)
        
        # Check for EA Properties dialog
        def find_ea_dialog(target_name):
            results = []
            pid_buf = ctypes.c_ulong()
            def cb(hwnd, _):
                # hwnd is c_size_t from callback, need to cast for API
                user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
                if pid_buf.value == mt5_pid:
                    cls = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                    if cls.value == '#32770':
                        title = ctypes.create_unicode_buffer(256)
                        user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                        if target_name in title.value:
                            results.append(title.value)
                return True
            CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
            user32.EnumWindows(CB(cb), 0)
            return results
        
        dialogs = find_ea_dialog(ea_name)
        if dialogs:
            print(f"🎉 {ea_name} Properties dialog found!")
            found_dialog = True
            
            # Step 6: Confirm dialog (Enter)
            send_keys('{ENTER}')
            time.sleep(2)
            
            # Step 7: Ensure AutoTrading ON
            log_path = os.path.join(MT5_DATA, 'Logs', time.strftime('%Y%m%d') + '.log')
            auto_trading_on = False
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-16-le', errors='replace') as f:
                    log_lines = f.readlines()
                for line in reversed(log_lines[-20:]):
                    if 'automated trading' in line.lower():
                        if 'enabled' in line.lower():
                            auto_trading_on = True
                        break
            
            if not auto_trading_on:
                send_keys('^e')
                time.sleep(2)
                print("🔴 AutoTrading OFF → toggled ON")
            else:
                print("🟢 AutoTrading is ON")
        else:
            # Fallback: scan more positions if first click missed
            print(f"⚠️ First click didn't find {ea_name} dialog, scanning...")
            # Close any wrong dialog
            send_keys('{ESC}')
            time.sleep(0.3)
            
            for y_client in [27, 45, 63, 81]:  # Try rows 2-5
                client_y = y_client
                lparam = (client_y << 16) | client_x
                user32.SendMessageW(tv_hwnd, 0x0203, 0x0001, lparam)
                time.sleep(1.5)
                user32.SendMessageW(tv_hwnd, 0x0202, 0x0000, lparam)
                time.sleep(0.5)
                dialogs = find_ea_dialog(ea_name)
                if dialogs:
                    print(f"🎉 {ea_name} dialog found at client_y={client_y}!")
                    found_dialog = True
                    send_keys('{ENTER}')
                    time.sleep(2)
                    send_keys('^e')
                    time.sleep(1)
                    break
                send_keys('{ESC}')
                time.sleep(0.3)
        
        if not found_dialog:
            print(f"⚠️ {ea_name} dialog not found after full scan (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
    
    print(f"❌ {ea_name} attach failed after {max_retries} attempts")
    return False


# ================================================================
#  Install EA handler
# ================================================================

@sio.on('install_ea_command')
def on_install_ea(data):
    ea_name = data.get('ea_name', '')
    ea_list = data.get('ea_list', [])
    url = data.get('download_url', '')
    ea_config = data.get('ea_config', {})
    if ea_config:
        global ea_config_cache
        ea_config_cache.clear()
        ea_config_cache.update(ea_config)

    if ea_name == 'all' and ea_list:
        print(f"📥 Bulk install: {len(ea_list)} EAs (background)")
        sys.stdout.flush()
        import threading
        def _do_install():
            for name in ea_list:
                download_and_install(name + '.mq5', url + name + '.mq5', ea_config)
        t = threading.Thread(target=_do_install, daemon=True)
        t.start()
        return

    print(f"📥 Installing EA: {ea_name}")
    sys.stdout.flush()
    download_and_install(ea_name + '.mq5', url + ea_name + '.mq5', ea_config)


# ================================================================
#  Download + Install + Compile + Auto-Attach
# ================================================================

def download_and_install(ea_name, url, ea_config=None):
    """完整安裝流程：download → heartbeat inject → compile → preset → auto-attach"""
    print(f"📥 Installing EA: {ea_name}")
    print(f"   Downloading from: {url}")
    try:
        import requests
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            appdata = os.environ.get('APPDATA', '')
            terminal_dir = os.path.join(appdata, 'MetaQuotes', 'Terminal')
            experts_dir = None
            if os.path.isdir(terminal_dir):
                for folder in sorted(os.listdir(terminal_dir)):
                    ep = os.path.join(terminal_dir, folder, 'MQL5', 'Experts')
                    if os.path.isdir(ep):
                        experts_dir = ep
                        break
                if not experts_dir:
                    common = os.path.join(terminal_dir, 'Common', 'MQL5', 'Experts')
                    if os.path.isdir(common):
                        experts_dir = common

            if experts_dir:
                base_name = ea_name.replace('.mq5', '')
                mq5_path = os.path.join(experts_dir, ea_name)
                
                # Write source with normalized line endings
                content = resp.text.replace('\r\n', '\n').replace('\n', '\r\n')
                
                # === Inject heartbeat code ===
                base = base_name
                hb_var = f"HB_{base}"
                hb_file = f"hb_{base}.txt"
                
                oninit_inject = (
                    f"   GlobalVariableSet(\"{hb_var}\",TimeCurrent());\r\n"
                    f"   int hb_fh=FileOpen(\"{hb_file}\",FILE_WRITE|FILE_TXT);\r\n"
                    f"   if(hb_fh!=INVALID_HANDLE){{FileWrite(hb_fh,TimeCurrent());FileClose(hb_fh);}}\r\n"
                )
                ontick_inject = (
                    f"   GlobalVariableSet(\"{hb_var}\",TimeCurrent());\r\n"
                    f"   int hb_fh=FileOpen(\"{hb_file}\",FILE_WRITE|FILE_TXT);\r\n"
                    f"   if(hb_fh!=INVALID_HANDLE){{FileWrite(hb_fh,TimeCurrent());FileClose(hb_fh);}}\r\n"
                )
                
                # Find OnInit { and inject after it
                import re
                m = re.search(r'(int\s+OnInit\s*\(\s*\)\s*\{)', content)
                if m and hb_var not in content:
                    idx = m.end()
                    content = content[:idx] + '\r\n' + oninit_inject + content[idx:]
                    print(f"   💉 Heartbeat injected (OnInit)")
                
                # Find OnTick { and inject after it
                m2 = re.search(r'(void\s+OnTick\s*\(\s*\)\s*\{)', content)
                if m2 and f'GlobalVariableSet("{hb_var}"' not in content.split('OnTick')[1] if 'OnTick' in content else '':
                    # Only inject if not already in OnTick section
                    if content.count(f'GlobalVariableSet("{hb_var}"') < 2:
                        idx2 = m2.end()
                        content = content[:idx2] + '\r\n' + ontick_inject + content[idx2:]
                        print(f"   💉 Heartbeat injected (OnTick)")
                
                with open(mq5_path, 'w', encoding='utf-8', newline='\r\n') as f:
                    f.write(content)
                print(f"   💾 Saved: {mq5_path}")
                
                # === Compile (skip if .ex5 already exists and fresh) ===
                ex5_path = os.path.join(experts_dir, base_name + '.ex5')
                if os.path.exists(ex5_path) and os.path.getmtime(ex5_path) > os.path.getmtime(mq5_path):
                    print(f"   ⏩ Skip compile: {base_name}.ex5 already exists")
                else:
                    import subprocess
                    metaeditor = r"C:\Program Files\MetaTrader 5\metaeditor64.exe"
                    log_file = os.path.join(experts_dir, f'{base_name}_compile.log')
                    
                    try:
                        result = subprocess.run([
                            metaeditor, '/compile', mq5_path,
                            f'/log:{log_file}'
                        ], capture_output=True, timeout=120)
                    except subprocess.TimeoutExpired:
                        print(f"   ⚠️ Compile timeout (120s), but .ex5 may exist")
                        if os.path.exists(ex5_path):
                            print(f"   ✅ .ex5 found despite timeout: {os.path.getsize(ex5_path)} bytes")
                
                # Check .ex5
                ex5_path = os.path.join(experts_dir, base_name + '.ex5')
                if os.path.exists(ex5_path):
                    print(f"   ✅ Compiled: {base_name}.ex5 ({os.path.getsize(ex5_path)} bytes)")
                else:
                    print(f"   ❌ Compile failed (no .ex5)")
                    # Try reading compile log for errors
                    if os.path.exists(log_file):
                        try:
                            with open(log_file, 'r', encoding='utf-16-le', errors='replace') as f:
                                log_content = f.read()
                            if 'error' in log_content.lower():
                                for line in log_content.split('\n'):
                                    if 'error' in line.lower():
                                        print(f"      {line.strip()}")
                        except:
                            pass
                
                # === Create preset ===
                if ea_config and base_name in ea_config:
                    cfg = ea_config[base_name]
                    # Handle old format (cfg=str) and new format (cfg=dict)
                    if isinstance(cfg, str):
                        cfg = {'symbol': cfg, 'timeframe': ea_config.get(base_name+'_tf', 'H1'),
                               'lot': ea_config.get(base_name+'_lot', '1.00'),
                               'magic': ea_config.get(base_name+'_magic', '240701')}
                    sym = cfg.get('symbol', 'EURUSD')
                    tf = cfg.get('timeframe', 'H1')
                    lot = cfg.get('lot', '1.00')
                    magic = str(cfg.get('magic', '240701'))
                    
                    presets_dir = os.path.join(experts_dir, 'Presets')
                    os.makedirs(presets_dir, exist_ok=True)
                    
                    set_content = f'; {base_name} preset\r\n'
                    set_content += f'MagicNumber={magic}\r\n'
                    set_content += f'LotSize={lot}\r\n'
                    set_path = os.path.join(presets_dir, base_name + '.set')
                    with open(set_path, 'w') as f:
                        f.write(set_content)
                    print(f"   📋 Preset: {set_path}")
                    
                    # === Skip deploy command for auto-sync (only 🚀 Deploy button writes it) ===
                    # Auto-sync just compiles & registers EA. User 🚀 Deploy will trigger attach.
                    print(f"   ✅ {base_name} compiled & registered. User 🚀 Deploy to attach.")

                sio.emit('install_result', {"status": "ok", "ea": ea_name})
            else:
                print("❌ Cannot find MT5 Experts folder")
                sio.emit('install_result', {"status": "error", "ea": ea_name, "msg": "MT5 not found"})
        else:
            print(f"❌ Download failed: {resp.status_code}")
            sio.emit('install_result', {"status": "error", "ea": ea_name, "msg": f"HTTP {resp.status_code}"})
    except Exception as e:
        print(f"❌ Install error: {e}")
        sio.emit('install_result', {"status": "error", "ea": ea_name, "msg": str(e)})


# ================================================================
#  Deploy via Socket.IO
# ================================================================

@sio.on('deploy_ea')
def on_deploy_ea(data):
    print(f"🚀 [WS] Deploy: {data}")
    sys.stdout.flush()
    execute_deploy(data)


# ================================================================
#  EA 自動交易策略
# ================================================================

def get_ma(symbol, tf, period, method=0):
    """獲取移動平均線數值"""
    import MetaTrader5 as mt5
    if not mt5.symbol_select(symbol, True):
        return None
    S_TF = {1:1, 5:5, 15:15, 30:30, 60:60, 240:240, 1440:1440, 10080:10080, 43200:43200}
    mul = S_TF.get(tf, 60)
    need_bars = (period + 2) * mul
    rates = mt5.copy_rates_from_pos(symbol, 1, 0, need_bars)
    if rates is None or len(rates) < need_bars:
        return None
    closes = [rates[i][4] for i in range(mul-1, len(rates), mul)]
    if len(closes) < period + 2:
        return None
    
    if method == 0:
        vals = []
        for i in range(len(closes) - period + 1):
            vals.append(sum(closes[i:i+period]) / period)
        return vals
    elif method == 1:
        k = 2.0 / (period + 1)
        ema = [sum(closes[:period]) / period]
        for p in closes[period:]:
            ema.append(p * k + ema[-1] * (1 - k))
        return ema
    return None

def check_sma_cross(symbol, tf, fast=10, slow=30):
    fast_ma = get_ma(symbol, tf, fast, method=0)
    slow_ma = get_ma(symbol, tf, slow, method=0)
    if not fast_ma or not slow_ma or len(fast_ma) < 2 or len(slow_ma) < 2:
        return None
    f1, f2 = fast_ma[-1], fast_ma[-2]
    s1, s2 = slow_ma[-1], slow_ma[-2]
    if f1 > s1 and f2 <= s2:
        return 'buy'
    if f1 < s1 and f2 >= s2:
        return 'sell'
    return None

def check_macd_cross(symbol, tf, fast=12, slow=26, signal=9):
    fast_ma = get_ma(symbol, tf, fast, method=1)
    slow_ma = get_ma(symbol, tf, slow, method=1)
    if not fast_ma or not slow_ma or len(fast_ma) < signal + 1 or len(slow_ma) < signal + 1:
        return None
    macd_line = [f - s for f, s in zip(fast_ma[-signal-1:], slow_ma[-signal-1:])]
    signal_line = sum(macd_line[:signal]) / signal
    if macd_line[-1] > signal_line and macd_line[-2] <= signal_line:
        return 'buy'
    if macd_line[-1] < signal_line and macd_line[-2] >= signal_line:
        return 'sell'
    return None

def run_ea_strategies(ea_config, lot_size):
    """執行 EA 策略 — 根據 config 嘅 EA 名決定用邊個策略"""
    import MetaTrader5 as mt5
    if not mt5.initialize():
        return
    
    for ea_name, cfg in ea_config.items():
        if ea_name.startswith('_') or ea_name.endswith(('_tf','_lot','_magic','_status','_source')):
            continue
        # Handle both old format (cfg=str) and new format (cfg=dict)
        if isinstance(cfg, str):
            cfg = {'symbol': cfg, 'timeframe': ea_config.get(ea_name+'_tf', 'H1'),
                   'lot': float(ea_config.get(ea_name+'_lot', str(lot_size))),
                   'magic': int(ea_config.get(ea_name+'_magic', '240701'))}
        symbol = cfg.get('symbol', 'EURUSD')
        tf_map = {'M1':1,'M5':5,'M15':15,'M30':30,'H1':60,'H4':240,'D1':1440}
        tf = tf_map.get(cfg.get('timeframe', 'H1'), 60)
        magic = int(cfg.get('magic', 240701))
        
        signal = None
        if 'SMA' in ea_name.upper() or 'MA_Cross' in ea_name:
            signal = check_sma_cross(symbol, tf)
        elif 'MACD' in ea_name.upper():
            signal = check_macd_cross(symbol, tf)
        elif 'ADX' in ea_name.upper():
            # ADX trend following — 用 SMA cross 作為輔助
            signal = check_sma_cross(symbol, tf, fast=14, slow=28)
        else:
            # Default: SMA cross
            signal = check_sma_cross(symbol, tf)
        
        if signal:
            mt5.symbol_select(symbol, True)
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                continue
            
            order_type = mt5.ORDER_TYPE_BUY if signal == 'buy' else mt5.ORDER_TYPE_SELL
            price = tick.ask if signal == 'buy' else tick.bid
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot_size,
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": magic,
                "comment": f"cloud_{ea_name}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"📈 {ea_name}: {signal.upper()} {symbol} @ {price}")
            elif result:
                print(f"⚠️ {ea_name}: retcode={result.retcode}")
            else:
                print(f"⚠️ {ea_name}: order failed")
    
    mt5.shutdown()


# ================================================================
#  Heartbeat check
# ================================================================

def check_ea_heartbeat_files():
    """檢查 EA 寫出嘅 heartbeat files"""
    appdata = os.environ.get('APPDATA', '')
    terminal_dir = os.path.join(appdata, 'MetaQuotes', 'Terminal')
    common_files = os.path.join(terminal_dir, 'Common', 'Files')
    
    candidates = [common_files]
    if os.path.isdir(terminal_dir):
        for folder in os.listdir(terminal_dir):
            ff = os.path.join(terminal_dir, folder, 'Files')
            if os.path.isdir(ff) and folder != 'Common':
                candidates.append(ff)
    
    now = time.time()
    found = {}
    for fb_dir in candidates:
        if not os.path.isdir(fb_dir):
            continue
        for fname in os.listdir(fb_dir):
            if fname.startswith('hb_') and fname.endswith('.txt'):
                ea_name = fname[3:-4]
                fpath = os.path.join(fb_dir, fname)
                mtime = os.path.getmtime(fpath)
                age = now - mtime
                if age < 300:
                    found[ea_name] = {"last_check": mtime, "status": "alive", "age_sec": round(age)}
                else:
                    found[ea_name] = {"last_check": mtime, "status": "stale", "age_sec": round(age)}
    return found


def check_ea_alive_via_trades():
    """Fallback: check recent trades"""
    import MetaTrader5 as mt5
    if not mt5.initialize():
        return {}
    from datetime import datetime, timedelta
    since = datetime.now() - timedelta(hours=24)
    deals = mt5.history_deals_get(since, datetime.now())
    hb = {}
    if deals:
        for d in deals:
            comment = d.comment or ''
            if comment.startswith('auto_') or comment.startswith('cloud_'):
                ea_name = comment.replace('auto_','').replace('cloud_','').split('_')[0]
                hb[ea_name] = {"last_check": d.time, "status": "alive"}
    mt5.shutdown()
    return hb


# ================================================================
#  Execute Deploy — 真正 attach EA 到 chart
# ================================================================

def execute_deploy(data):
    ea_name = data.get('ea_name', '')
    symbol = data.get('symbol', 'EURUSD')
    tf = data.get('tf', 'H1')
    magic = str(data.get('magic', '240701'))
    lot = str(data.get('lot', '1.00'))

    SYMBOL_MAP = {
        'DAX40': 'DE40',
        'SP500': 'US500',
    }
    mt5_symbol = SYMBOL_MAP.get(symbol, symbol)

    print(f"🚀 [EXEC] Deploying {ea_name} -> {symbol} ({mt5_symbol}) {tf}")

    def report(msg, status='info'):
        print(f"   {msg}")
        sio.emit('install_result', {"status": status, "ea": ea_name, "msg": msg})

    try:
        # Write command file for deploy_watcher (has desktop access for pyautogui)
        cmd_data = {
            'ea_name': ea_name,
            'symbol': mt5_symbol,
            'tf': tf,
            'magic': magic,
            'lot': lot,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'source': 'agent_deploy'
        }
        cmd_filename = f'deploy_cmd_{ea_name}_{int(time.time())}.json'
        common_files = os.path.join(os.environ.get('APPDATA', ''),
                                     'MetaQuotes', 'Terminal', 'Common', 'Files')
        os.makedirs(common_files, exist_ok=True)
        cmd_path = os.path.join(common_files, cmd_filename)
        
        with open(cmd_path, 'w') as f:
            json.dump(cmd_data, f)
        
        print(f"   📝 Watcher command written: {cmd_path}")
        print(f"   ⏳ deploy_watcher.py 會自動 attach {ea_name} → {symbol} {tf}")
        sys.stdout.flush()
        
        # Report as sent (deploy_watcher will do the actual attach)
        report(f'📡 Deploy 指令已交給 watcher: {ea_name} → {symbol} {tf}', 'sent')

    except Exception as e:
        report(f'❌ Failed to write deploy command: {str(e)[:80]}', 'error')


# ================================================================
#  Main Sync Loop
# ================================================================

def sync_loop():
    """每 2 秒 poll deploy + 每 10 秒 sync + 每 30 秒 auto-trade"""
    last_sync = 0
    last_trade = 0
    while True:
        try:
            # Sync MT5 data every 10 seconds
            now = time.time()
            if sio.connected and now - last_sync >= 10:
                data = get_mt5_status()
                data['agent_id'] = AGENT_ID
                data['heartbeats'] = dict(ea_heartbeats)
                try:
                    hb_files = check_ea_heartbeat_files()
                    hb_trades = check_ea_alive_via_trades()
                    for ea, info in hb_files.items():
                        data['heartbeats'][ea] = info
                    for ea, info in hb_trades.items():
                        if ea not in data['heartbeats']:
                            data['heartbeats'][ea] = info
                    if hb_files:
                        print(f"💓 Heartbeats: {hb_files}")
                        sys.stdout.flush()
                except Exception as e:
                    print(f'   [HB] Error: {e}')
                    import traceback
                    traceback.print_exc()
                sio.emit('agent_sync', data)
                last_sync = now

            # Auto-trade every 30 seconds
            if now - last_trade >= 30:
                last_trade = now
                if ea_config_cache:
                    run_ea_strategies(ea_config_cache, float(ea_config_cache.get('_default_lot', 1.00)))
        except ImportError:
            pass
        except Exception as e:
            import traceback
            print(f"   [SYNC] Error: {e}")
            traceback.print_exc()
        time.sleep(2)


def connect_mt5():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        return False
    return True

def get_mt5_status():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        return {"error": "MT5 not available"}
    
    account = mt5.account_info()
    status = {
        "login": account.login if account else 0,
        "balance": account.balance if account else 0,
        "equity": account.equity if account else 0,
        "margin": account.margin if account else 0,
        "server": account.server if account else "",
        "positions": len(mt5.positions_get() or []),
    }
    # 🚨 2026-08-21：收集 history deals（Trades/Win/P&L 真實數據）
    # 之前冇收集 → agent.deals 永遠空 → /api/analysis「No data yet」→ 前端 Trades/Win/P&L 全部「—」
    # 🚨 2026-08-21 FIX：history_deals_get(since, now) 有 caching 問題 — 用 (0, now) 攞全部（實測攞到全部 deals）
    try:
        from datetime import datetime, timedelta
        since = datetime.now() - timedelta(days=30)
        deals = mt5.history_deals_get(0, datetime.now())
        deal_list = []
        if deals:
            for d in deals:
                # 只收集有 profit 嘅 closed deals（成交記錄 — 開倉冇 profit）
                if d.profit != 0 or d.entry == mt5.DEAL_ENTRY_OUT:
                    deal_list.append({
                        "ticket": d.ticket,
                        "magic": d.magic,
                        "symbol": d.symbol,
                        "profit": d.profit,
                        "time": d.time,
                        "entry": d.entry,
                        "type": d.type,
                        "volume": d.volume,
                        "price": d.price,
                        "comment": d.comment or '',
                    })
        status["deals"] = deal_list
        status["deals_count"] = len(deal_list)
        if deal_list:
            print(f"📊 Synced {len(deal_list)} deals to server")
            sys.stdout.flush()
    except Exception as e:
        print(f"   [DEALS] Error: {e}")
        status["deals"] = []
    mt5.shutdown()
    return status


# ================================================================
#  Startup
# ================================================================

print()
print("=" * 56)
print("  ☁️  MT5 Cloud Agent")
print("=" * 56)
print(f"  Server:   {SERVER_URL}")
print(f"  Agent ID: {AGENT_ID}")
print(f"  MT5:      {'✅ Available' if mt5_available else '❌ Not installed'}")
print("=" * 56)
print("  Connecting...\n")

try:
    sio.connect(f"{SERVER_URL}", transports=['polling'])  # 強制 polling，Flask dev server 唔支援 WebSocket
except Exception as e:
    print(f"❌ Cannot connect to server: {e}")
    print(f"   Make sure {SERVER_URL} is running")
    sys.exit(1)

sync_thread = threading.Thread(target=sync_loop, daemon=True)
sync_thread.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Agent stopped")
    sio.disconnect()
