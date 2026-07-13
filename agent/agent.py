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

# Keep running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Agent stopped")
    sio.disconnect()
