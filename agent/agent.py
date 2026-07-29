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
import threading

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

def disconnect():
    print("❌ Disconnected")

def on_registered(data):
    print(f"🆔 Registered: {data}")

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
    
    # Step 3: Attach via Navigator
    attached = attach_ea_navigator(ea_name, symbol, mt5_pid)
    
    if not attached:
        # Fallback: restart MT5 and try again
        print("⚠️ Navigator attach failed, restarting MT5...")
        mt5_pid = do_restart_mt5()
        if mt5_pid:
            attached = attach_ea_navigator(ea_name, symbol, mt5_pid)
    
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
    """用 Navigator double-click attach EA（可靠方法，含重試）
    
    關鍵步驟：
    1. 先開一個新 chart（確保有活躍 chart 可以 attach）
    2. Expand Navigator EA交易 節點
    3. Double-click EA → 彈出 Properties dialog → 確定
    4. 確保 AutoTrading ON（先 check log 再 toggle）
    """
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    
    for attempt in range(max_retries):
        app = Application(backend='uia').connect(process=mt5_pid)
        win = app.top_window()
        win.set_focus()
        time.sleep(0.5)
        
        # Step 0: Open a new chart (Alt+F → 新圖 → EURUSD)
        send_keys('%f')
        time.sleep(0.5)
        menu_items = win.descendants(control_type='MenuItem')
        for mi in menu_items:
            if '新圖' in mi.window_text():
                mi.click_input()
                time.sleep(0.5)
                sub_items = win.descendants(control_type='MenuItem')
                for si in sub_items:
                    if symbol in si.window_text():
                        si.click_input()
                        time.sleep(2)
                        break
                break
        send_keys('{ESC}')
        time.sleep(0.3)
        
        # Step 1: Find Navigator tree
        trees = win.descendants(control_type='Tree')
        if not trees:
            print(f"⚠️ No Navigator tree (attempt {attempt+1}/{max_retries})")
            time.sleep(5)
            continue
        
        tree = trees[0]
        items = tree.descendants(control_type='TreeItem')
        
        ea_node = None
        for item in items:
            if item.window_text() == ea_name:
                ea_node = item
                break
        
        if not ea_node:
            for item in items:
                if item.window_text() == 'EA交易':
                    item.double_click_input()
                    time.sleep(3)
                    break
            items2 = tree.descendants(control_type='TreeItem')
            for item in items2:
                if item.window_text() == ea_name:
                    ea_node = item
                    break
        
        if not ea_node:
            print(f"⚠️ {ea_name} not found in Navigator (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                print(f"   Waiting 10s...")
                time.sleep(10)
            continue
        
        # Step 2: Double-click to attach
        print(f"🎯 Found {ea_name}, attaching...")
        ea_node.double_click_input()
        time.sleep(3)
        
        # Step 3: Handle properties dialog
        try:
            dialogs = win.descendants(control_type='Window')
            for d in dialogs:
                if ea_name in d.window_text():
                    print(f"📋 Dialog: {d.window_text()}")
                    buttons = d.descendants(control_type='Button')
                    clicked = False
                    for btn in buttons:
                        if btn.window_text() in ('確定', 'OK'):
                            btn.click_input()
                            clicked = True
                            break
                    if not clicked:
                        send_keys('{ENTER}')
                    print(f"✅ Confirmed EA properties")
                    time.sleep(2)
                    break
        except:
            send_keys('{ENTER}')
            print("No dialog - pressed Enter")
        
        # Step 4: Ensure AutoTrading ON (check log state first)
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
        
        return True
    
    print(f"❌ {ea_name} not found after {max_retries} attempts")
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
                    f"   int hb_fh=FileOpen(\"{hb_file}\",FILE_WRITE|FILE_TXT|FILE_COMMON);\r\n"
                    f"   if(hb_fh!=INVALID_HANDLE){{FileWrite(hb_fh,TimeCurrent());FileClose(hb_fh);}}\r\n"
                )
                ontick_inject = (
                    f"   GlobalVariableSet(\"{hb_var}\",TimeCurrent());\r\n"
                    f"   int hb_fh=FileOpen(\"{hb_file}\",FILE_WRITE|FILE_TXT|FILE_COMMON);\r\n"
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
                
                # === Compile ===
                import subprocess
                metaeditor = r"C:\Program Files\MetaTrader 5\metaeditor64.exe"
                log_file = os.path.join(experts_dir, f'{base_name}_compile.log')
                
                result = subprocess.run([
                    metaeditor, '/compile', mq5_path,
                    f'/log:{log_file}'
                ], capture_output=True, timeout=60)
                
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
                    
                    # === Auto-attach EA to MT5 chart ===
                    try:
                        inputs = {'LotSize': lot, 'MagicNumber': magic}
                        result = auto_attach_ea(base_name, symbol=sym, 
                                                timeframe=tf, inputs=inputs)
                        if result:
                            print(f"   🎉 {base_name} → {sym} {tf} 🟢 ALIVE")
                        else:
                            print(f"   ⚠️  Auto-attach failed for {base_name}")
                    except Exception as attach_err:
                        print(f"   ⚠️  Auto-attach error: {attach_err}")

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
        if ea_name.startswith('_'):
            continue
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
        # Use auto_attach_ea for reliable deployment
        inputs = {'LotSize': lot, 'MagicNumber': magic}
        result = auto_attach_ea(ea_name, symbol=mt5_symbol, timeframe=tf, inputs=inputs)
        
        if result:
            report(f'✅ {ea_name} → {symbol} {tf} 已啟動！🟢', 'ok')
        else:
            # Auto-attach failed — check AutoTrading state
            import MetaTrader5 as mt5
            if not mt5.initialize():
                report('❌ MT5 無法連接', 'error')
                return
            
            # Try enabling AutoTrading first
            report('⚠️ Auto-attach failed, checking AutoTrading...')
            info = mt5.account_info()
            if info and not info.trade_allowed:
                report('🔴 AutoTrading is OFF — 請在 MT5 按 Ctrl+E 開啟', 'error')
            else:
                report('⚠️ Auto-attach failed，請重試 Deploy', 'error')
            mt5.shutdown()

    except Exception as e:
        report(f'❌ {str(e)[:80]}', 'error')


# ================================================================
#  Main Sync Loop
# ================================================================

def sync_loop():
    """每 2 秒 poll deploy + 每 10 秒 sync + 每 30 秒 auto-trade"""
    last_sync = 0
    last_trade = 0
    while True:
        try:
            # Poll deploy queue
            import requests as req
            poll_url = f"http://localhost:5002/api/agent-poll-deploy?agent_id={AGENT_ID}"
            resp = req.get(poll_url, timeout=5)
            if resp.status_code == 200:
                deploy_data = resp.json()
                if deploy_data and 'ea_name' in deploy_data:
                    print(f"🚀 [POLL] Deploy: {deploy_data}")
                    sys.stdout.flush()
                    execute_deploy(deploy_data)

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
                except Exception as e:
                    print(f'   [HB] Error: {e}')
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
    sio.connect(f"{SERVER_URL}", transports=['websocket'])
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
