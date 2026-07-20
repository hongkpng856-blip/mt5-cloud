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
        return {"status": "offline", "account": {}, "positions": [], "deals": []}

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
                "ticket": p.ticket, "symbol": p.symbol,
                "type": "BUY" if p.type == 0 else "SELL",
                "volume": p.volume, "price_open": p.price_open,
                "sl": p.sl, "tp": p.tp,
                "profit": round(p.profit, 2), "swap": round(p.swap, 2),
                "magic": p.magic, "comment": p.comment
            })

    from datetime import datetime as dt, timedelta
    since = dt.now() - timedelta(days=365)
    deals = mt5.history_deals_get(since, dt.now())
    data["deals"] = []
    if deals:
        for d in deals[-200:]:
            data["deals"].append({
                "ticket": d.ticket, "symbol": d.symbol,
                "type": d.type, "volume": d.volume,
                "price": d.price, "profit": round(d.profit, 2),
                "commission": round(d.commission, 2), "swap": round(d.swap, 2),
                "magic": d.magic,
                "time": str(dt.fromtimestamp(d.time)),
                "comment": d.comment
            })

    # Don't shutdown — keep MT5 connected for deploy
    return data

# === Install EA handler ===
@sio.on('install_ea_command')
def on_install_ea(data):
    ea_name = data.get('ea_name', '')
    ea_list = data.get('ea_list', [])
    url = data.get('download_url', '')
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
                filepath = os.path.join(experts_dir, ea_name)
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
                print(f"✅ Installed: {filepath}")

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

# === Deploy via Socket.IO (instead of polling) ===
@sio.on('deploy_ea')
def on_deploy_ea(data):
    print(f"🚀 [WS] Deploy command: {data}")
    sys.stdout.flush()
    execute_deploy(data)

# === Main Loop ===
def sync_loop():
    """每 10 秒 sync MT5 data (唔再 poll deploy)"""
    last_sync = 0
    while True:
        try:
            now = time.time()
            if sio.connected and now - last_sync >= 10:
                data = get_mt5_status()
                data['agent_id'] = AGENT_ID
                sio.emit('agent_sync', data)
                last_sync = now
        except Exception as e:
            print(f"   Sync error: {e}")
        time.sleep(2)

def execute_deploy(data):
    ea_name = data.get('ea_name', '')
    symbol = data.get('symbol', 'EURUSD')
    tf = data.get('tf', 'H1')
    magic = str(data.get('magic', '240701'))
    lot = str(data.get('lot', '1.00'))

    # Broker symbol mapping (IC Markets 用嘅名)
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
        import MetaTrader5 as mt5
        if not mt5.initialize():
            report('❌ MT5 無法連接', 'error')
            return

        report('🖥️ MT5 已連接')

        # Add symbol to Market Watch
        mt5.symbol_select(mt5_symbol, True)

        # Get account info
        account = mt5.account_info()
        if account:
            report(f'💰 Account: {account.login}')

        # Place a limit order with the EA's magic number
        # Far from market price = won't fill, just registers the magic
        tick = mt5.symbol_info_tick(mt5_symbol)
        if not tick:
            report(f'❌ {mt5_symbol} not available', 'error')
            mt5.shutdown()
            return

        # Get symbol info for digits
        info = mt5.symbol_info(mt5_symbol)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": mt5_symbol,
            "volume": float(lot),
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "deviation": 20,
            "magic": int(magic),
            "comment": f"cloud_{ea_name}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            report(f'✅ {ea_name} → {symbol} ({mt5_symbol}) {tf} 已啟動！', 'ok')
        elif result:
            report(f'⚠️ retcode={result.retcode}', 'info')
        else:
            report(f'⚠️ {mt5.last_error()}', 'info')

        mt5.shutdown()

    except Exception as e:
        report(f'❌ {str(e)[:80]}', 'error')

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
