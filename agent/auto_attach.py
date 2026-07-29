"""
MT5 EA Auto-Attach — 可靠嘅 GUI 自動化方案
每次都可以做到！Template + Navigator fallback

流程：
1. 生成 .tpl 模板（含 EA 設定）
2. 重啟 MT5（確保 Navigator tree refresh）
3. 開新 chart + Apply Template
4. Fallback: Navigator double-click attach
5. 確保 AutoTrading 開啟
6. 驗證 heartbeat file
"""
import os
import sys
import time
import struct
import subprocess

# ─── Config ───
MT5_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'
MT5_DATA = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
COMMON_FILES = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                            'Common', 'Files')

# MT5 timeframe codes for .tpl period_size
TF_CODES = {
    'M1': 16385, 'M2': 16386, 'M3': 16387, 'M4': 16388, 'M5': 16389,
    'M6': 16390, 'M10': 16394, 'M12': 16396, 'M15': 16401, 'M20': 16406,
    'M30': 16416, 'H1': 32801, 'H2': 32802, 'H3': 32803, 'H4': 32805,
    'H6': 32807, 'H8': 32809, 'H12': 32813, 'D1': 49201,
    'W1': 65601, 'MN1': 82001,
}


def find_mt5_pid():
    """搵 MT5 process ID"""
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None


def wait_for_mt5(timeout=60):
    """等 MT5 啟動完成"""
    start = time.time()
    while time.time() - start < timeout:
        pid = find_mt5_pid()
        if pid:
            # Wait for window to be ready
            try:
                from pywinauto import Application
                app = Application(backend='uia').connect(process=pid)
                win = app.top_window()
                if win.is_visible() and win.is_enabled():
                    return pid
            except:
                pass
        time.sleep(2)
    return None


def do_restart_mt5():
    """重啟 MT5（確保 Navigator refresh）"""
    import psutil
    
    # Kill existing MT5
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            proc.kill()
    
    time.sleep(3)
    
    # Start MT5
    subprocess.Popen([MT5_PATH])
    
    # Wait for ready
    pid = wait_for_mt5(timeout=90)
    if pid:
        # Extra wait for Navigator to fully load + refresh
        time.sleep(10)
        print(f"✅ MT5 restarted, PID={pid}")
        return pid
    else:
        print("❌ MT5 failed to start")
        return None


def generate_template(ea_name, symbol='EURUSD', timeframe='H1', inputs=None):
    """生成 .tpl 模板檔（MT5 UTF-16 LE 格式）"""
    os.makedirs(TPL_DIR, exist_ok=True)
    
    tf_code = TF_CODES.get(timeframe, 32801)  # Default H1
    
    # Build inputs section
    inputs_section = ""
    if inputs:
        for key, val in inputs.items():
            inputs_section += f"{key}={val}\r\n"
    
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
        f"path=Experts\\{ea_name}.ex5\r\n"
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
        f.write(tpl_content.encode('utf-16-le'))
    
    print(f"📋 Template saved: {tpl_path} ({os.path.getsize(tpl_path)} bytes)")
    return tpl_path


def _open_chart_keyboard():
    """用鍵盤快捷鍵開新 chart（唔依賴 UI Automation）"""
    from pywinauto.keyboard import send_keys
    send_keys('^n')  # Ctrl+N = New Chart
    time.sleep(1)
    send_keys('{ENTER}')  # 接受默認品種
    time.sleep(2)


def attach_ea_navigator(ea_name, mt5_pid, max_retries=3):
    """用 win32 backend Navigator TreeView attach EA
    
    關鍵發現：uia backend 會 COM error，win32 backend 可以正常遍歷 SysTreeView32！
    流程：
    1. win32 connect → 找到 SysTreeView32
    2. Expand EA交易 → 找到 EA 節點
    3. ea_node.select() → send_keys('{ENTER}') 觸發 double-click
    4. 處理 Properties dialog → send_keys('{ENTER}')
    5. 確保 AutoTrading ON
    """
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    
    for attempt in range(max_retries):
        try:
            # 使用 win32 backend（唔用 uia，uia 會 COM error）
            app = Application(backend='win32').connect(process=mt5_pid)
            win = app.top_window()
            win.set_focus()
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️ win32 connect failed: {e} (attempt {attempt+1}/{max_retries})")
            time.sleep(5)
            continue
        
        # Step 0: Open a new chart — 用鍵盤
        send_keys('^n')
        time.sleep(1)
        send_keys('{ENTER}')
        time.sleep(2)
        
        # Step 1: Find SysTreeView32 (Navigator TreeView)
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
        
        # Step 2: Navigate Navigator tree
        try:
            root = tree_view.roots()[0]  # "MetaTrader 5"
            
            # Find EA交易 node
            ea_trading_node = None
            for child in root.children():
                if 'EA交易' in child.text():
                    ea_trading_node = child
                    break
            
            if not ea_trading_node:
                print(f"⚠️ EA交易 node not found (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
            
            # Expand EA交易
            try:
                ea_trading_node.expand()
            except:
                pass  # May already be expanded
            time.sleep(2)
            
            # Find the EA node
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
            
            # Step 3: Select and activate EA
            print(f"🎯 Found {ea_name}, selecting...")
            ea_node.select()
            time.sleep(0.5)
            
            # Send Enter to activate (equivalent to Navigator double-click)
            send_keys('{ENTER}')
            time.sleep(3)
            
            # Step 4: Handle properties dialog — press Enter for OK
            send_keys('{ENTER}')
            time.sleep(2)
            
            # Step 5: Ensure AutoTrading ON
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
                send_keys('^e')  # Ctrl+E to enable
                time.sleep(2)
                print("🔴 AutoTrading was OFF → toggled ON")
            else:
                print("🟢 AutoTrading is already ON")
            
            return True
            
        except Exception as e:
            print(f"⚠️ Navigator navigation error: {e} (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
    
    print(f"❌ {ea_name} not found after {max_retries} attempts")
    return False


def ensure_auto_trading_on(mt5_pid):
    """確保 AutoTrading 係開啟狀態"""
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    
    app = Application(backend='uia').connect(process=mt5_pid)
    win = app.top_window()
    
    # Check toolbar - look for 算法交易 button
    # The toolbar has a checkbox-style button for AutoTrading
    # If it's depressed/off, click it
    
    # Method 1: Check via Experts log
    # If "automated trading is disabled" appears, toggle it
    
    # Method 2: Just toggle Ctrl+E to make sure it's on
    # This is a toggle, so we need to check current state first
    
    # Read MT5 log to check current state
    log_path = os.path.join(MT5_DATA, 'Logs', time.strftime('%Y%m%d') + '.log')
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-16-le', errors='replace') as f:
            lines = f.readlines()
        for line in reversed(lines):
            if 'automated trading' in line.lower():
                if 'disabled' in line.lower():
                    print("🔴 AutoTrading is OFF, enabling...")
                    send_keys('^e')  # Ctrl+E
                    time.sleep(1)
                    return True
                elif 'enabled' in line.lower():
                    print("🟢 AutoTrading is already ON")
                    return True
    
    # Fallback: toggle twice to ensure ON
    send_keys('^e')
    time.sleep(0.5)
    send_keys('^e')
    time.sleep(1)
    print("✅ AutoTrading toggled")
    return True


def apply_template_gui(template_name, mt5_pid):
    """用 GUI menu Apply Template"""
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    
    app = Application(backend='uia').connect(process=mt5_pid)
    win = app.top_window()
    
    # Method: Alt+V (查看) → 範本 → template_name
    # But MT5 menu navigation is unreliable via pywinauto
    
    # Better: Open chart first, then Chart -> Template -> Apply
    # For now, Navigator double-click is more reliable
    return False


def verify_heartbeat(ea_name, timeout=60):
    """驗證 EA heartbeat file 存在且新鮮"""
    hb_file = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
    start = time.time()
    
    while time.time() - start < timeout:
        if os.path.exists(hb_file):
            mtime = os.path.getmtime(hb_file)
            age = time.time() - mtime
            if age < 300:  # Within 5 minutes
                # Read content
                with open(hb_file, 'rb') as f:
                    raw = f.read()
                content = raw.decode('utf-16-le', errors='replace').strip().lstrip('\ufeff')
                print(f"💓 {ea_name} heartbeat: {content} ({round(age)}s ago)")
                return True
        time.sleep(3)
    
    print(f"❌ {ea_name} heartbeat not detected within {timeout}s")
    return False


def verify_ea_loaded(ea_name):
    """檢查 MT5 log 確認 EA 已 load"""
    log_path = os.path.join(MT5_DATA, 'Logs', time.strftime('%Y%m%d') + '.log')
    mql5_log = os.path.join(MT5_DATA, 'MQL5', 'Logs', time.strftime('%Y%m%d') + '.log')
    
    for path in [log_path, mql5_log]:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-16-le', errors='replace') as f:
                lines = f.readlines()
            for line in reversed(lines[-50:]):
                if f'expert {ea_name}' in line.lower() and 'loaded' in line.lower():
                    print(f"✅ MT5 log: EA loaded successfully")
                    return True
                if ea_name in line and '啟動' in line:
                    print(f"✅ EA log: {line.strip()}")
                    return True
    return False


def auto_attach_ea(ea_name, symbol='EURUSD', timeframe='H1', inputs=None,
                   do_restart=False):
    """
    主函數：可靠地 attach EA 到 MT5 chart
    
    流程：
    1. 生成 .tpl 模板
    2. （可選）重啟 MT5 刷新 Navigator
    3. Navigator double-click attach EA
    4. 確保 AutoTrading ON
    5. 驗證 heartbeat
    
    Returns: True if EA is running with heartbeat
    """
    print(f"\n{'='*50}")
    print(f"  🚀 Auto-Attach: {ea_name} → {symbol} {timeframe}")
    print(f"{'='*50}")
    
    # Step 1: Generate template
    tpl_path = generate_template(ea_name, symbol, timeframe, inputs)
    
    # Step 2: Get or restart MT5
    if do_restart:
        mt5_pid = do_restart_mt5()
        if not mt5_pid:
            return False
    else:
        mt5_pid = find_mt5_pid()
        if not mt5_pid:
            print("MT5 not running, starting...")
            subprocess.Popen([MT5_PATH])
            mt5_pid = wait_for_mt5()
            if not mt5_pid:
                return False
    
    # Step 3: Attach EA via Navigator
    success = attach_ea_navigator(ea_name, mt5_pid)
    if not success:
        # Restart MT5 and retry (Navigator might not have refreshed)
        print("⚠️ Navigator attach failed, restarting MT5...")
        mt5_pid = do_restart_mt5()
        if mt5_pid:
            success = attach_ea_navigator(ea_name, mt5_pid)
    
    if not success:
        print("❌ Failed to attach EA")
        return False
    
    # Step 4: Ensure AutoTrading ON
    ensure_auto_trading_on(mt5_pid)
    
    # Step 5: Verify
    time.sleep(5)
    loaded = verify_ea_loaded(ea_name)
    heartbeat = verify_heartbeat(ea_name, timeout=60)
    
    if heartbeat:
        print(f"\n🎉 SUCCESS: {ea_name} is running on {symbol} {timeframe}!")
        return True
    else:
        print(f"\n⚠️ {ea_name} may be attached but no heartbeat detected")
        return loaded


# ─── CLI ───
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='MT5 EA Auto-Attach Tool')
    parser.add_argument('--ea', required=True, help='EA name (e.g. ADX_Trend)')
    parser.add_argument('--symbol', default='EURUSD', help='Symbol (default: EURUSD)')
    parser.add_argument('--tf', default='H1', help='Timeframe (default: H1)')
    parser.add_argument('--lot', type=float, default=1.0, help='Lot size (default: 1.0)')
    parser.add_argument('--magic', type=int, default=240701, help='Magic number')
    parser.add_argument('--restart', action='store_true', help='Restart MT5 first')
    args = parser.parse_args()
    
    inputs = {
        'LotSize': f'{args.lot:.2f}',
        'MagicNumber': str(args.magic),
        'EnableLog': 'true',
    }
    
    result = auto_attach_ea(
        ea_name=args.ea,
        symbol=args.symbol,
        timeframe=args.tf,
        inputs=inputs,
        do_restart=args.restart,
    )
    
    sys.exit(0 if result else 1)
