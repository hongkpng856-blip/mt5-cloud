# MT5 Cloud Agent — 安裝喺你部 Windows 機
# 佢會將你嘅 MT5 連接去 Cloud Server
#
# 用法：python agent.py --server https://your-server.com --agent-id YOUR_AGENT_ID

import os
import sys
import json
import time
import argparse
import threading
from datetime import datetime

# === Parse args ===
parser = argparse.ArgumentParser(description='MT5 Cloud Agent')
parser.add_argument('--server', required=True, help='Cloud server URL (e.g. https://mt5cloud.com)')
parser.add_argument('--agent-id', required=True, help='Your Agent ID from the website')
parser.add_argument('--mt5-path', help='Path to MetaTrader 5 terminal (optional)')
args = parser.parse_args()

SERVER_URL = args.server.rstrip('/')
AGENT_ID = args.agent_id

# === SocketIO client ===
try:
    import socketio
except ImportError:
    print("❌ Please install: pip install python-socketio[client] requests MetaTrader5")
    sys.exit(1)

sio = socketio.Client()

@sio.event
def connect():
    print(f"🟢 Connected to {SERVER_URL}")
    sio.emit('agent_register', {"agent_id": AGENT_ID})

@sio.event
def disconnect():
    print("🔴 Disconnected from server")

@sio.on('registered')
def on_registered(data):
    print(f"✅ Agent registered: {data}")

@sio.on('trade_command')
def on_trade_command(data):
    """收到 Server 嘅交易指令"""
    print(f"📨 Trade command received: {data}")
    # Execute via MT5
    result = execute_trade(data)
    # Report back
    sio.emit('agent_trade_result', {"agent_id": AGENT_ID, "result": result})

# === MT5 Bridge ===
mt5_available = False
try:
    import MetaTrader5 as mt5
    mt5_available = True
except ImportError:
    print("⚠️  MetaTrader5 未安裝，只可監控不可交易")
    print("   裝返：pip install MetaTrader5\n")

def connect_mt5():
    if not mt5_available:
        return False
    if not mt5.initialize():
        print(f"❌ MT5 連接失敗 ({datetime.now().strftime('%H:%M:%S')})")
        return False
    print(f"✅ MT5 已連線 ({datetime.now().strftime('%H:%M:%S')})")
    return True

def get_mt5_status():
    """同步 MT5 數據去 Server"""
    if not mt5_available or not mt5.initialize():
        return {"status": "offline", "account": {}, "positions": []}

    account = mt5.account_info()
    positions = mt5.positions_get()

    data = {
        "status": "running",
        "account": {
            "login": account.login if account else None,
            "server": account.server if account else None,
            "balance": round(account.balance, 2) if account else 0,
            "equity": round(account.equity, 2) if account else 0,
            "profit": round(account.profit, 2) if account else 0,
            "margin_free": round(account.margin_free, 2) if account else 0,
            "leverage": account.leverage if account else 0,
            "currency": account.currency if account else "",
            "trade_mode": "DEMO" if (account and account.trade_mode == 0) else "REAL",
        },
        "positions": []
    }

    if positions:
        for p in positions:
            data["positions"].append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == 0 else "SELL",
                "volume": p.volume,
                "price_open": p.price_open,
                "sl": p.sl,
                "tp": p.tp,
                "profit": round(p.profit, 2),
                "swap": round(p.swap, 2),
                "magic": p.magic,
                "comment": p.comment
            })

    # Sync 交易歷史（用嚟做分析）
    from datetime import datetime, timedelta
    since = datetime.now() - timedelta(days=365)
    deals = mt5.history_deals_get(since, datetime.now())
    data["deals"] = []
    if deals:
        for d in deals[-200:]:  # 最近 200 筆
            data["deals"].append({
                "ticket": d.ticket,
                "symbol": d.symbol,
                "type": d.type,
                "volume": d.volume,
                "price": d.price,
                "profit": round(d.profit, 2),
                "commission": round(d.commission, 2),
                "swap": round(d.swap, 2),
                "magic": d.magic,
                "time": str(datetime.fromtimestamp(d.time)),
                "comment": d.comment
            })

    mt5.shutdown()
    return data

def execute_trade(command):
    """執行 Server 發過嚟嘅交易指令"""
    if not mt5_available:
        return {"error": "MetaTrader5 not installed"}

    if not mt5.initialize():
        return {"error": "Cannot connect to MT5"}

    action = command.get('action')
    symbol = command.get('symbol')
    volume = float(command.get('volume', 0.01))
    order_type = command.get('order_type')
    sl = command.get('sl')
    tp = command.get('tp')

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        mt5.shutdown()
        return {"error": f"Symbol {symbol} not found"}

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "deviation": 10,
        "magic": 240701,
        "comment": "cloud_trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    if action == 'buy' or order_type == 'buy':
        request["type"] = mt5.ORDER_TYPE_BUY
        request["price"] = tick.ask
        if sl: request["sl"] = sl
        if tp: request["tp"] = tp
    elif action == 'sell' or order_type == 'sell':
        request["type"] = mt5.ORDER_TYPE_SELL
        request["price"] = tick.bid
        if sl: request["sl"] = sl
        if tp: request["tp"] = tp
    else:
        mt5.shutdown()
        return {"error": f"Unknown action: {action}"}

    result = mt5.order_send(request)
    mt5.shutdown()

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        return {"success": True, "ticket": result.order, "price": request["price"]}
    else:
        return {"error": f"Order failed: {result.comment} (code: {result.retcode})"}

# === Main Loop ===
def sync_loop():
    """每 10 秒同步 MT5 數據上 Server"""
    while True:
        try:
            if sio.connected:
                data = get_mt5_status()
                data['agent_id'] = AGENT_ID
                sio.emit('agent_sync', data)
        except Exception as e:
            print(f"Sync error: {e}")
        time.sleep(10)  # 10 seconds

print()
print("=" * 56)
print("  ☁️  MT5 Cloud Agent")
print("=" * 56)
print(f"  Server:   {SERVER_URL}")
print(f"  Agent ID: {AGENT_ID}")
print(f"  MT5:      {'✅ Available' if mt5_available else '❌ Not installed'}")
print("=" * 56)
print("  Connecting...\n")

# Connect to server
try:
    sio.connect(f"{SERVER_URL}", transports=['websocket', 'polling'])
except Exception as e:
    print(f"❌ Cannot connect to server: {e}")
    print(f"   Make sure {SERVER_URL} is running")
    sys.exit(1)

# Start sync loop
sync_thread = threading.Thread(target=sync_loop, daemon=True)
sync_thread.start()

@sio.on('install_ea_command')
def on_install_ea(data):
    """收到 Server 指令：下載並安裝 EA 去 MT5"""
    ea_name = data.get('ea_name', '')
    ea_list = data.get('ea_list', [])
    url = data.get('download_url', '')

    # 如果係 'all'，就處理 ea_list
    ea_config = data.get('ea_config', {})
    if ea_name == 'all' and ea_list:
        print(f"📥 Bulk install: {len(ea_list)} EAs")
        for name in ea_list:
            download_and_install(name + '.mq5', url + name + '.mq5', ea_config)
        return

    download_and_install(ea_name, url, ea_config)

def download_and_install(ea_name, url, ea_config=None):
    print(f"📥 Installing EA: {ea_name}")
    print(f"   Downloading from: {url}")
    try:
        import requests
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            # 搵 MT5 Experts 目錄
            experts_dir = None
            appdata = os.environ.get('APPDATA', '')
            terminal_dir = os.path.join(appdata, 'MetaQuotes', 'Terminal')
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
                filepath = os.path.join(experts_dir, ea_name)
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
                print(f"✅ Installed: {filepath}")

                # 嘗試 Compile
                metaeditor = None
                for prog in ['C:\\Program Files\\MetaTrader 5\\metaeditor64.exe',
                             'C:\\Program Files (x86)\\MetaTrader 5\\metaeditor64.exe']:
                    if os.path.isfile(prog):
                        metaeditor = prog
                        break
                if metaeditor and ea_name.endswith('.mq5'):
                    import subprocess
                    subprocess.run([metaeditor, f'/compile:"{filepath}"', '/s'],
                                 capture_output=True, timeout=30)
                    print(f"⚙️  Compiled: {ea_name}")

                # 生成 .set 參數檔
                base_name = ea_name.replace('.mq5', '').replace('.ex5', '')
                if ea_config:
                    sym = ea_config.get(base_name, 'EURUSD')
                    magic = str(ea_config.get(base_name + '_magic', '240701'))
                    lot = str(ea_config.get(base_name + '_lot', '1.00'))
                    tf = ea_config.get(base_name + '_tf', 'H1')
                    presets_dir = os.path.join(os.path.dirname(experts_dir), 'Presets')
                    os.makedirs(presets_dir, exist_ok=True)
                    set_content = '; MT5 Cloud Preset for ' + base_name + '\n'
                    set_content += '; Symbol=' + sym + '  Magic=' + magic + '  Lot=' + lot + '  TF=' + tf + '\n'
                    set_content += '[Common]\n[Inputs]\n'
                    set_content += 'MagicNumber=' + magic + '\n'
                    set_content += 'LotSize=' + lot + '\n'
                    set_path = os.path.join(presets_dir, base_name + '.set')
                    with open(set_path, 'w') as f:
                        f.write(set_content)
                    print(f"📋 Preset: {set_path}")

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

# Keep running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Agent stopped")
    sio.disconnect()

# === Auto Deploy: 將 EA attach 去 MT5 chart ===
@sio.on('deploy_ea_command')
def on_deploy_ea(data):
    """收到 Server 指令：將 EA 自動部署到 MT5 chart"""
    ea_name = data.get('ea_name', '')
    symbol = data.get('symbol', 'EURUSD')
    tf = data.get('tf', 'H1')
    magic = str(data.get('magic', '240701'))
    lot = str(data.get('lot', '1.00'))

    print(f"🚀 Deploying {ea_name} to {symbol} {tf}")

    def report(status, msg):
        sio.emit('install_result', {"status": status, "ea": ea_name, "msg": msg})

    try:
        # Find MT5 terminal path
        mt5_terminal = None
        for prog in ['C:\\\\Program Files\\\\MetaTrader 5\\\\terminal64.exe',
                     'C:\\\\Program Files (x86)\\\\MetaTrader 5\\\\terminal64.exe']:
            if os.path.isfile(prog):
                mt5_terminal = prog
                break

        if not mt5_terminal:
            report('error', 'MT5 not found')
            return

        # 方法：用 MT5 嘅 /config 參數直接開 chart + EA
        # MT5 支援 terminal64.exe /config:<path> 去載入設定檔
        # Build a temporary config file
        import tempfile
        config_dir = os.path.join(tempfile.gettempdir(), 'mt5cloud_deploy')
        os.makedirs(config_dir, exist_ok=True)

        # Open chart using MT5 command line
        # MT5 supports: terminal64.exe /profile:<name>  and we can send chart open command
        import subprocess
        import ctypes

        # Activate MT5 window
        hwnd = ctypes.windll.user32.FindWindowW(None, "MetaTrader 5")
        if hwnd:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            print(f"   🖥️  MT5 window activated")
            report('info', '🖥️ MT5 已連接，正在部署...')
            time.sleep(0.5)

            # Ctrl+M → Market Watch, type symbol, Enter to open chart
            import pyautogui
            pyautogui.hotkey('ctrl', 'm')
            time.sleep(0.3)
            pyautogui.write(symbol)
            time.sleep(0.2)
            pyautogui.press('enter')
            time.sleep(0.5)

            # Ctrl+N → Navigator, navigate to EA
            pyautogui.hotkey('ctrl', 'n')
            time.sleep(0.5)
            # Type EA name to search
            pyautogui.write(ea_name.replace('.mq5','').replace('.ex5',''))
            time.sleep(0.3)
            # Double-click to attach
            pyautogui.press('enter')
            time.sleep(1)

            # In the EA properties dialog, set parameters via Tab
            # Tab to Inputs tab, then set magic/lot
            pyautogui.press('tab', presses=3)
            time.sleep(0.3)
            pyautogui.hotkey('ctrl', 'right')  # Go to Inputs tab
            time.sleep(0.3)
            # Tab to first input, set Magic
            pyautogui.press('tab')
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.write(magic)
            # Tab to Lot
            pyautogui.press('tab')
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.write(lot)
            # Press OK
            pyautogui.press('enter')
            time.sleep(0.3)
            pyautogui.press('enter')

            print(f"   ✅ {ea_name} deployed to {symbol} {tf}")
            report('ok', f'✅ {ea_name} → {symbol} {tf} 部署完成！')
        else:
            # MT5 not running, launch it
            subprocess.Popen([mt5_terminal])
            time.sleep(3)
            report('ok', f'{ea_name} — MT5 已啟動，請手動 drag EA 去 chart')

    except Exception as e:
        print(f"   ❌ Deploy error: {e}")
        report('error', str(e))
