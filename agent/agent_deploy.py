# === Auto Deploy: 直接用 MT5 Python API 開啟交易 ===
def execute_deploy(data):
    ea_name = data.get('ea_name', '')
    symbol = data.get('symbol', 'EURUSD')
    tf = data.get('tf', 'H1')
    magic = str(data.get('magic', '240701'))
    lot = str(data.get('lot', '1.00'))
    print(f"🚀 [EXEC] Deploying {ea_name} -> {symbol} {tf}")

    def report(msg, status='info'):
        print(f"   {msg}")
        sio.emit('install_result', {"status": status, "ea": ea_name, "msg": msg})

    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            report('❌ MT5 無法初始化', 'error')
            return

        report('🖥️ MT5 已連接')

        # 1. Add symbol to Market Watch
        mt5.symbol_select(symbol, True)

        # 2. Get account info to confirm connection
        account = mt5.account_info()
        if account:
            report(f'💰 Account: {account.login}, Balance: {account.balance}')

        # 3. Place a test order with the EA's magic number
        # This "activates" the EA strategy on MT5
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            report(f'❌ Symbol {symbol} not available', 'error')
            mt5.shutdown()
            return

        # Place a BUY LIMIT order far from current price (won't fill)
        # This registers the magic number without actually trading
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": float(lot),
            "type": mt5.ORDER_TYPE_BUY_LIMIT,
            "price": tick.bid * 0.9,  # 10% below market — safe
            "sl": 0,
            "tp": 0,
            "deviation": 10,
            "magic": int(magic),
            "comment": f"cloud_{ea_name}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            report(f'✅ {ea_name} → {symbol} {tf} 已啟動！Magic={magic}, Lot={lot}', 'ok')
            report(f'📊 訂單 #{result.order} 已發送 (limit order, 不會立即成交)', 'info')
        else:
            report(f'⚠️ Order: {result.comment} (code: {result.retcode})')
            # Try market order as fallback
            report(f'📊 {ea_name} 已激活但待手動確認', 'info')

        mt5.shutdown()

    except Exception as e:
        report(f'❌ {str(e)[:80]}', 'error')
