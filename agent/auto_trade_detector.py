#!/usr/bin/env python3
"""獨立 Auto-Trade Detector — 避開 Hermes server respawn + mt5 singleton 問題
- 獨佔 MT5 Python API（唯一使用者，冇衝突）
- 每 30 秒計算 SMA10/SMA30 crossover 信號
- 直接讀 SQLite DB 攞 EA config（唔靠 server API）
- Port 5003 提供 HTTP endpoint + CORS
"""
import json
import time
import threading
import sqlite3
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'server', 'instance', 'mt5cloud.db')
DB_PATH = os.path.normpath(DB_PATH)
TF_MAP = {'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60, 'H4': 240, 'D1': 1440, 'W1': 10080, 'MN1': 43200}

status_cache = {
    "timestamp": 0,
    "results": [],
    "error": "",
    "account": "",
}


def load_ea_config():
    """直接讀 SQLite DB 攞 EA config（🚨 2026-08-12 修：合併所有用戶 config — 之前 hardcode 'dev' 得 0 keys）"""
    cfg = {}
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT ea_config FROM user")
        for row in c.fetchall():
            try:
                user_cfg = json.loads(row['ea_config'] or '{}')
                for k, v in user_cfg.items():
                    if k not in cfg:
                        cfg[k] = v
            except Exception:
                pass
        conn.close()
    except Exception as e:
        status_cache["error"] = f"DB read error: {e}"
    return cfg


def compute_signals():
    """每 30 秒: 用 MT5 計算所有 EA 嘅 SMA 信號"""
    import MetaTrader5 as mt5

    cfg = load_ea_config()
    eas = [k for k in cfg if not k.startswith('_') and not k.endswith(('_tf', '_lot', '_magic', '_status')) and isinstance(cfg[k], str)]

    if not eas:
        status_cache["results"] = []
        status_cache["error"] = "No EAs configured"
        status_cache["timestamp"] = time.time()
        return

    # 檢查 MT5 是否運行（唔自動開！）
    import subprocess as sp
    r = sp.run('tasklist /FI "IMAGENAME eq terminal64.exe" /NH', shell=True, capture_output=True, text=True, timeout=5)
    if 'terminal64' not in r.stdout:
        status_cache["results"] = []
        status_cache["error"] = "MT5 not running"
        status_cache["timestamp"] = time.time()
        return

    if not mt5.initialize(timeout=10000):
        status_cache["error"] = f"mt5.initialize failed: {mt5.last_error()}"
        status_cache["timestamp"] = time.time()
        return

    # 🚨 2026-08-12：initialize 完即刻攞 account info（EA 計算後可能 disconnect — account_info 返回 None）
    account = ""
    account_info_full = {}
    try:
        info = mt5.account_info()
        if info:
            account = str(info.login)
            account_info_full = {
                'login': str(info.login), 'server': info.server, 'name': info.name,
                'balance': info.balance, 'equity': info.equity,
                'currency': info.currency, 'leverage': info.leverage
            }
    except Exception:
        pass

    results = []
    for ea in eas:
        try:
            # 檢查暫停狀態 — 暫停咗嘅 EA 唔計算信號
            ea_status = cfg.get(ea + '_status', 'running')
            if ea_status != 'running':
                results.append({
                    'ea': ea,
                    'symbol': cfg.get(ea, ''),
                    'tf': cfg.get(ea + '_tf', 'H1'),
                    'sma10': 0, 'sma30': 0,
                    'signal': 'PAUSED', 'alive': False
                })
                continue

            symbol = cfg[ea]
            if symbol in ('DE40', 'US500', 'US100', 'JP225'):
                continue
            tf_str = cfg.get(ea + '_tf', 'H1')
            tf = TF_MAP.get(tf_str, 60)
            mul = tf  # M1 -> TF resample factor

            mt5.symbol_select(symbol, True)
            need = max(2000, 40 * mul)
            rates = mt5.copy_rates_from_pos(symbol, 1, 0, need)
            if rates is None or len(rates) < need:
                continue

            closes = [float(rates[i][4]) for i in range(len(rates))]
            tf_closes = [closes[i] for i in range(mul - 1, len(closes), mul)]
            n = len(tf_closes)
            if n < 35:
                continue

            fast = [sum(tf_closes[i:i + 10]) / 10.0 for i in range(n - 9)]
            slow = [sum(tf_closes[i:i + 30]) / 30.0 for i in range(n - 29)]

            cross_buy = fast[-1] > slow[-1] and fast[-2] <= slow[-2]
            cross_sell = fast[-1] < slow[-1] and fast[-2] >= slow[-2]

            if cross_buy:
                signal = 'BUY'
            elif cross_sell:
                signal = 'SELL'
            else:
                signal = 'WAIT'

            results.append({
                'ea': ea,
                'symbol': symbol,
                'tf': tf_str,
                'sma10': round(fast[-1], 5),
                'sma30': round(slow[-1], 5),
                'signal': signal,
                'alive': True
            })
        except Exception as e:
            results.append({'ea': ea, 'symbol': cfg.get(ea, ''), 'tf': cfg.get(ea + '_tf', 'H1'),
                            'sma10': 0, 'sma30': 0, 'signal': 'ERROR', 'alive': False, 'error': str(e)})

    # 🚨 2026-08-12：account_info 已喺 initialize 後攞（上面）— 唔使再攞
    mt5.shutdown()

    status_cache["results"] = results
    status_cache["account"] = account
    status_cache["account_info"] = account_info_full
    status_cache["error"] = ""
    status_cache["timestamp"] = time.time()


# ============================================================
# EA Inventory — 掃描電腦 MT5 入面所有 EA + 詳細狀態
# ============================================================

def scan_ea_inventory():
    """掃描 MQL5/Experts/*.ex5 + MT5 log → 所有 EA 及其狀態"""
    # 搵 MT5 data 目錄
    data_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
    experts_dirs = []
    if os.path.isdir(data_dir):
        for d in os.listdir(data_dir):
            exp = os.path.join(data_dir, d, 'MQL5', 'Experts')
            if os.path.isdir(exp):
                experts_dirs.append(exp)

    # 掃描 .ex5 文件（⚠️ 2026-08：只掃根目錄 + MT5Cloud_EA folder — 唔掃 MT5 內建 folder
    # （Free Robots/Examples/Advisors — 樣本 EA 唔應該顯示）
    eas = {}
    for exp_dir in experts_dirs:
        scan_dirs = [exp_dir, os.path.join(exp_dir, 'MT5Cloud_EA')]
        for scan_dir in scan_dirs:
            if not os.path.isdir(scan_dir):
                continue
            for f in os.listdir(scan_dir):
                if f.lower().endswith('.ex5'):
                    path = os.path.join(scan_dir, f)
                    try:
                        stat = os.stat(path)
                    except Exception:
                        continue
                    eas[f[:-4]] = {
                        'name': f[:-4],
                        'file': f,
                        'size': stat.st_size,
                        'modified': time.strftime('%Y-%m-%d %H:%M', time.localtime(stat.st_mtime)),
                        'path': path
                    }

    # 讀最近 MT5 log 搵部署中（attach）記錄 — 用最近修改嘅 log 檔
    attached = {}
    try:
        log_dir = os.path.join(data_dir, 'D0E8209F77C8CF37AD8BF550E51FF075', 'MQL5', 'Logs')
        import re
        if os.path.isdir(log_dir):
            # 搵最近 3 個 log 檔（今日/昨日/前日）
            log_files = sorted(
                [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.endswith('.log')],
                key=os.path.getmtime, reverse=True
            )[:3]
            for log_file in log_files:
                try:
                    with open(log_file, encoding='utf-16-le', errors='ignore') as f:
                        content = f.read()
                    # 格式: EA_NAME (SYMBOL,TF) 或 EA_NAME (SYMBOL,TF,MAGIC)
                    for m in re.finditer(r'([A-Za-z_][A-Za-z0-9_]*)\s*\(([A-Za-z0-9._]+),([A-Za-z0-9]+)', content):
                        ea_name, symbol, tf = m.group(1), m.group(2), m.group(3)
                        attached[ea_name] = {'symbol': symbol, 'tf': tf}
                except Exception:
                    continue
    except Exception as e:
        attached = {'_error': str(e)}

    # 讀 DB config 攞配對/暫停狀態
    cfg = load_ea_config()
    config_status = {}
    for k, v in cfg.items():
        if not k.startswith('_') and not k.endswith(('_tf', '_lot', '_magic', '_status')) and isinstance(v, str):
            config_status[k] = {
                'symbol': v,
                'tf': cfg.get(k + '_tf', 'H1'),
                'lot': cfg.get(k + '_lot', 1),
                'magic': cfg.get(k + '_magic', ''),
                'status': cfg.get(k + '_status', 'running')
            }

    # 合併狀態
    inventory = []
    for name, info in sorted(eas.items()):
        is_attached = name in attached
        is_configured = name in config_status
        cfg_st = config_status.get(name, {})
        inventory.append({
            'name': name,
            'size': info['size'],
            'modified': info['modified'],
            'deployed': is_attached,
            'deploy_info': attached.get(name, {}),
            'configured': is_configured,
            'config_status': cfg_st.get('status', ''),
            'symbol': cfg_st.get('symbol', attached.get(name, {}).get('symbol', '')),
            'tf': cfg_st.get('tf', attached.get(name, {}).get('tf', '')),
            'lot': cfg_st.get('lot', 1),
            'magic': cfg_st.get('magic', ''),
        })

    return {
        'total': len(inventory),
        'deployed_count': len([e for e in inventory if e['deployed']]),
        'configured_count': len([e for e in inventory if e['configured']]),
        'eas': inventory,
        'scanned_at': time.strftime('%Y-%m-%d %H:%M:%S')
    }


class DetectorHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

        if self.path == '/api/auto-trade-status':
            payload = {
                "timestamp": status_cache["timestamp"],
                "account": status_cache["account"],
                "error": status_cache["error"],
                "results": status_cache["results"]
            }
        elif self.path == '/api/ea-inventory':
            try:
                payload = scan_ea_inventory()
            except Exception as e:
                payload = {"error": str(e)}
        elif self.path == '/health':
            payload = {"ok": True, "uptime": time.time() - start_time}
        else:
            payload = {"error": "Not found"}

        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, fmt, *args):
        pass  # 靜音


# ============================================================
# 寫 JSON 去 server/static/detector/ — 前端用同源路徑攞數據
# （避開 HTTPS tunnel fetch HTTP localhost 嘅混合內容封鎖）
# ============================================================
STATIC_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'server', 'static', 'detector'))


def write_static_json():
    """每 30 秒將 status + inventory 寫去 static 目錄"""
    try:
        os.makedirs(STATIC_DIR, exist_ok=True)
        # 寫 auto-trade status
        status_payload = {
            "timestamp": status_cache["timestamp"],
            "account": status_cache["account"],
            "account_info": status_cache.get("account_info", {}),
            "error": status_cache["error"],
            "results": status_cache["results"]
        }
        with open(os.path.join(STATIC_DIR, 'auto_trade_status.json'), 'w', encoding='utf-8') as f:
            json.dump(status_payload, f, ensure_ascii=False)

        # 寫 ea inventory
        inventory_payload = scan_ea_inventory()
        with open(os.path.join(STATIC_DIR, 'ea_inventory.json'), 'w', encoding='utf-8') as f:
            json.dump(inventory_payload, f, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] write_static_json: {e}")


start_time = time.time()
ACTIVITY_LOG_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'server', 'activity_log.jsonl'))


def log_db_update():
    """每 30 秒寫一條「已更新資料庫」到 activity log（恆常記錄，Dashboard 可以選擇顯示/隱藏）"""
    try:
        import datetime as _dt
        entry = {
            "time": time.time(),
            "action": "db_update",
            "ea": "",
            "message": "已更新資料庫",
            "source": "detector"
        }
        with open(ACTIVITY_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def loop():
    loop_count = 0
    while True:
        try:
            compute_signals()
            write_static_json()
            # 每 30 秒記錄一次「已更新資料庫」（6 次 x 5 秒掃描）
            loop_count += 1
            if loop_count % 6 == 0:
                log_db_update()
        except Exception as e:
            status_cache["error"] = str(e)
        time.sleep(5)  # 5 秒掃描一次 — EA 剷除/新增要即時反映（用戶要求即時更新）


if __name__ == '__main__':
    # ─── 單實例守衛：如果 :5003 已有 healthy detector，退出 ───
    import socket as _sock
    try:
        _probe = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        _probe.bind(('0.0.0.0', 5003))
        _probe.close()
    except OSError:
        print("⚠️  :5003 已有 detector 運行緊，呢個 instance 退出（單實例守衛）")
        sys.exit(0)

    print("📡 Auto-Trade Detector :5003")
    print(f"   DB: {DB_PATH}")
    threading.Thread(target=loop, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', 5003), DetectorHandler).serve_forever()
