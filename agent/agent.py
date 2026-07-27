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
    if ea_config:
        global ea_config_cache
        ea_config_cache.clear()
        ea_config_cache.update(ea_config)

    if ea_name == 'all' and ea_list:
        print(f"📥 Bulk install: {len(ea_list)} EAs (background)")
        sys.stdout.flush()
        # Thread-safe install (唔阻塞 Socket.IO)
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


# === Deploy via Socket.IO (runs directly, install is already bg) ===
@sio.on('deploy_ea')
def on_deploy_ea(data):
    print(f"🚀 [WS] Deploy: {data}")
    sys.stdout.flush()
    execute_deploy(data)

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
                    import subprocess, tempfile
                    # metaeditor NEEDS /log: flag to output .ex5 (just /s doesn't work via subprocess)
                    log_path = os.path.join(tempfile.gettempdir(), f'mql_compile_{os.getpid()}.log')
                    subprocess.run([metaeditor, f'/compile:{filepath}', f'/log:{log_path}'],
                                 timeout=30, capture_output=True)
                    # metaeditor returns 1 even on success; check .ex5 instead
                    ex5_path = filepath.replace('.mq5', '.ex5')
                    if os.path.isfile(ex5_path):
                        print(f"⚙️  Compiled: {ea_name} ✅ {os.path.basename(ex5_path)}")
                    else:
                        print(f"⚙️  Compile attempted (checking .ex5): {ea_name}")

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

# === EA 自動交易策略 ===
ea_config_cache = {}
ea_heartbeats = {}  # ea_name -> {"last_check": time.time(), "status": "alive"}
_last_bar_checked = {}  # symbol_tf -> last bar time

def get_ma(symbol, tf, period, method=0):
    """獲取移動平均線數值（resample M1 to desired TF）
       0=SMA, 1=EMA"""
    import MetaTrader5 as mt5
    if not mt5.symbol_select(symbol, True):
        return None
    # Convert TF minutes to M1 multiplier
    S_TF = {1:1, 5:5, 15:15, 30:30, 60:60, 240:240, 1440:1440, 10080:10080, 43200:43200}
    mul = S_TF.get(tf, 60)
    # Need enough M1 bars: period * mul + extra for SMA calc
    need_bars = (period + 2) * mul
    rates = mt5.copy_rates_from_pos(symbol, 1, 0, need_bars)  # Always M1
    if rates is None or len(rates) < need_bars:
        return None
    # Resample: take close of every 'mul' bar (end of each TF candle)
    closes = [rates[i][4] for i in range(mul-1, len(rates), mul)]
    if len(closes) < period + 2:
        return None
    
    if method == 0:  # SMA
        vals = []
        for i in range(len(closes) - period + 1):
            vals.append(sum(closes[i:i+period]) / period)
        return vals
    elif method == 1:  # EMA
        k = 2.0 / (period + 1)
        ema = [sum(closes[:period]) / period]
        for p in closes[period:]:
            ema.append(p * k + ema[-1] * (1 - k))
        return ema
    return None

def check_sma_cross(symbol, tf, fast=10, slow=30):
    """黃金/死亡交叉檢測"""
    fast_ma = get_ma(symbol, tf, fast, method=0)
    slow_ma = get_ma(symbol, tf, slow, method=0)
    if not fast_ma or not slow_ma or len(fast_ma) < 2 or len(slow_ma) < 2:
        return None
    # 最新嘅兩支 K 線
    f1, f2 = fast_ma[-1], fast_ma[-2]
    s1, s2 = slow_ma[-1], slow_ma[-2]
    if f1 > s1 and f2 <= s2:
        return 'buy'
    if f1 < s1 and f2 >= s2:
        return 'sell'
    return None

def check_macd_cross(symbol, tf, fast=12, slow=26, signal=9):
    """MACD 交叉檢測"""
    fast_ema = get_ma(symbol, tf, fast, method=1)
    slow_ema = get_ma(symbol, tf, slow, method=1)
    if not fast_ema or not slow_ema or len(fast_ema) < signal + 2 or len(slow_ema) < signal + 2:
        return None
    macd = [fast_ema[i] - slow_ema[i] for i in range(min(len(fast_ema), len(slow_ema)))]
    signal_line = get_ma(symbol, tf, signal, method=1)  # 用 signal period 做 EMA of MACD
    # Simplified: compare MACD[-1] > MACD[-2]
    if len(macd) >= 3:
        if macd[-1] > macd[-2] and macd[-2] <= macd[-3]:
            return 'buy'
        if macd[-1] < macd[-2] and macd[-2] >= macd[-3]:
            return 'sell'
    return None

def run_ea_strategies(ea_config, lot_size):
    """執行所有已配對 EA 嘅自動交易策略"""
    import MetaTrader5 as mt5
    if not mt5.initialize():
        print(f'   [TRADE] MT5 init failed')
        return
    if not ea_config:
        print(f'   [TRADE] No config')
        mt5.shutdown()
        return
    print(f'   [TRADE] Running strategies for {len(ea_config)} config keys')

    TF_MAP = {'M1':1,'M5':5,'M15':15,'M30':30,'H1':60,'H4':240,'D1':1440,'W1':10080,'MN1':43200}
    active_eas = [k for k in ea_config if not k.startswith('_') and not k.endswith(('_tf','_lot','_magic','_status'))
                  and isinstance(ea_config[k], str)]

    for ea_name in active_eas:
        symbol = ea_config.get(ea_name, 'EURUSD')
        tf_str = ea_config.get(ea_name + '_tf', 'H1')
        tf = TF_MAP.get(tf_str, 60)
        magic = int(ea_config.get(ea_name + '_magic', '240701'))
        lot = float(ea_config.get(ea_name + '_lot', lot_size))
        status = ea_config.get(ea_name + '_status', 'running')
        if status != 'running':
            continue

        # Update heartbeat — EA is being actively monitored
        ea_heartbeats[ea_name] = {"last_check": time.time(), "status": "alive"}

        # 每支新 bar 先檢查
        bar_key = f'{symbol}_{tf}'
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, 2)
        if rates is None or len(rates) < 2:
            continue
        current_bar = rates[-1]['time']
        if _last_bar_checked.get(bar_key) == current_bar:
            continue
        _last_bar_checked[bar_key] = current_bar

        # 根據 EA 名行對應策略
        signal = None
        if ea_name == 'SMA_Cross':
            signal = check_sma_cross(symbol, tf)
        elif ea_name == 'MACD_Cross':
            signal = check_macd_cross(symbol, tf)
        elif ea_name in ('Trend_Follow','EMA_Cross'):
            signal = check_sma_cross(symbol, tf, 20, 50)  # slower trend
        elif ea_name == 'Scalping_M1':
            signal = check_sma_cross(symbol, 1, 5, 20)  # M1 fast

        if signal:
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                continue
            price = tick.ask if signal == 'buy' else tick.bid
            order_type = mt5.ORDER_TYPE_BUY if signal == 'buy' else mt5.ORDER_TYPE_SELL
            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': symbol, 'volume': lot,
                'type': order_type, 'price': price,
                'deviation': 20, 'magic': magic,
                'comment': f'auto_{ea_name}',
                'type_time': mt5.ORDER_TIME_GTC,
                'type_filling': mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f'🤖 {ea_name} {signal.upper()} {symbol} @ {price}')

    mt5.shutdown()


# === Main Loop ===
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
                data['heartbeats'] = dict(ea_heartbeats)  # send per-EA alive status
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
