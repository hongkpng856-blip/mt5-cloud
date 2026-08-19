"""壓力測試 ×5（對應數量版）：每輪剷除全部 → 添加 N 個 EA → 部署 N 個（對應數量）→ 真實驗證 → 重複

每輪組合（數量遞增）：
  Round 1: 1 個 (EMA_Cross)
  Round 2: 2 個 (Bollinger_Band, Breakout)
  Round 3: 3 個 (ADX_Trend, Divergence, Swing_Trader)
  Round 4: 1 個 (Grid_Trading)
  Round 5: 2 個 (EMA_Cross, Bollinger_Band)

真實驗證（唔可以假成功）：
  - MT5 Terminal log 出現 'expert <EA> (<SYM>,H1) loaded successfully' 且無隨後 removed（優先）
  - 心跳檔 mtime <120s（後備 — hb_<EA>.txt OR state_<EA>.json）

前置：
  1. kill auto_trade_detector（會中途 restart MT5）
  2. 確保 fresh agent 連 127.0.0.1:5001
  3. 清舊 heartbeat / state file
  4. 清晒 MT5 圖表
"""
import urllib.request, json, http.cookiejar, socket, os, time, sys, glob

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
socket.setdefaulttimeout(30)
BASE = 'http://127.0.0.1:5001'
APPDATA = os.environ['APPDATA']
COMMON = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')
MT5ROOT = os.path.join(APPDATA, 'MetaQuotes', 'Terminal')

# 每輪組合：[(EA, symbol), ...] — 數量唔同（1/2/3/1/2）
ROUNDS = [
    [('EMA_Cross', 'EURUSD')],
    [('Bollinger_Band', 'USDJPY'), ('Breakout', 'GBPUSD')],
    [('ADX_Trend', 'AUDUSD'), ('Divergence', 'EURUSD'), ('Swing_Trader', 'USDJPY')],
    [('Grid_Trading', 'GBPUSD')],
    [('EMA_Cross', 'AUDUSD'), ('Bollinger_Band', 'EURUSD')],
]

def login():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    data = json.dumps({'username':'dev','password':'dev1234'}).encode()
    req = urllib.request.Request(BASE+'/login', data=data, headers={'Content-Type':'application/json'})
    op.open(req).read()
    return op, cj

def post(op, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else b''
    req = urllib.request.Request(BASE+url, data=data, headers={'Content-Type':'application/json'}, method='POST')
    return json.loads(op.open(req).read().decode())

def find_hb(ea):
    pats = [os.path.join(COMMON, f'hb_{ea}.txt'),
            os.path.join(COMMON, f'state_{ea}.json'),
            os.path.join(MT5ROOT, '*', 'MQL5', 'Files', f'hb_{ea}.txt'),
            os.path.join(MT5ROOT, '*', 'MQL5', 'Files', f'state_{ea}.json')]
    for p in pats:
        for f in glob.glob(p):
            return f
    return None

def mt5_log_loaded(ea, symbol):
    """MT5 Terminal log 最近有 'expert <EA> (<SYM>,H1) loaded successfully' 且無隨後 removed"""
    logs = sorted(glob.glob(os.path.join(MT5ROOT, '*', 'logs', '2026*.log')), key=os.path.getmtime)
    if not logs:
        return False
    lg = logs[-1]
    try:
        raw = open(lg, 'rb').read()
        txt = None
        for enc in ('utf-16', 'utf-8'):
            try: txt = raw.decode(enc); break
            except: pass
        if not txt:
            return False
        lines = txt.splitlines()
        loaded = -1; removed = -1
        for i, ln in enumerate(lines):
            if f'expert {ea} ({symbol},H1) loaded successfully' in ln:
                loaded = i
            if f'expert {ea} ({symbol},H1) removed' in ln:
                removed = i
        return loaded >= 0 and (removed < loaded or removed == -1)
    except Exception:
        return False

def db_has_ea(ea):
    import sqlite3
    c = sqlite3.connect('C:/Users/hongk/Desktop/mt5-cloud/instance/mt5cloud.db')
    row = c.execute("SELECT ea_config FROM user WHERE username='dev'").fetchone()
    cfg = json.loads(row[0]) if row and row[0] else {}
    c.close()
    return ea in cfg

def remove_all(op):
    """剷除所有配對 EA（完整移除）"""
    removed = []
    for ea, _ in [(e, s) for e, s in sum(ROUNDS, [])]:
        try:
            r = post(op, f'/api/ea-library/remove-local/{ea}')
            removed.append((ea, r.get('success')))
        except Exception as e:
            removed.append((ea, str(e)))
        time.sleep(2)
    return removed

def clear_hb(ea):
    for pat in [os.path.join(COMMON, f'hb_{ea}.txt'), os.path.join(COMMON, f'state_{ea}.json')]:
        for f in glob.glob(pat):
            try: os.remove(f)
            except: pass
    for f in glob.glob(os.path.join(COMMON, f'web_delete_{ea}*')):
        try: os.remove(f)
        except: pass

results = []
for ri, round_ea in enumerate(ROUNDS, 1):
    n = len(round_ea)
    print(f"\n{'='*64}\n  🔄 Round {ri}/5 — 添加 {n} 個 EA  →  部署 {n} 個\n{'='*64}")
    op, cj = login()

    # 1. 剷除所有 EA（完整移除）
    print("  [1] 剷除所有 EA...")
    removed = remove_all(op)
    time.sleep(5)
    for ea, _ in [(e, s) for e, s in sum(ROUNDS, [])]:
        clear_hb(ea)

    round_ok = True
    details = []

    # 2. 添加 N 個 EA（install-local 逐個）
    for i, (ea, sym) in enumerate(round_ea, 1):
        r1 = post(op, f'/api/ea-library/install-local/{ea}.mq5')
        ok1 = r1.get('success')
        print(f"  [2.{i}] 配對 {ea}: success={ok1} compile_ok={r1.get('compile_ok')}")
        # 🚨 2026-08-20：等 .ex5 真係出現（install-local compile 有 queued/時序 — 唔可以固定 sleep）
        _ex5_wait = 0
        while _ex5_wait < 60:
            _ex5_p = os.path.join(MT5ROOT, '*', 'MQL5', 'Experts', f'{ea}.ex5')
            if glob.glob(_ex5_p):
                break
            time.sleep(2); _ex5_wait += 2
        _ex5_ok = bool(glob.glob(os.path.join(MT5ROOT, '*', 'MQL5', 'Experts', f'{ea}.ex5')))
        print(f"       .ex5 出現: {'✅' if _ex5_ok else '❌'}（等咗 {_ex5_wait}s）")
        if not ok1 or not _ex5_ok:
            round_ok = False; details.append((ea, 'install-fail'))
        time.sleep(2)

    # 3. 部署 N 個 EA（對應數量）
    # 🚨 2026-08-20 FIX：每隻 deploy 後要等佢完成先 deploy 下一隻！
    # （之前連住 POST — watcher spawn 多個 auto_attach 同時跑 → 搶 MT5 → 有一隻失敗）
    for i, (ea, sym) in enumerate(round_ea, 1):
        magic = '2407' + str(ri) + str(i)
        r2 = post(op, '/api/deploy', {'ea_name': ea, 'symbol': sym, 'tf': 'H1', 'magic': magic, 'lot': 1})
        print(f"  [3.{i}] 部署 {ea} -> {sym}: success={r2.get('success')}")
        # 等呢隻部署完成（MT5 log loaded 或心跳新鮮 — 最多 180s）先部署下一隻
        _dep_done = False
        for _d_wait in range(90):  # 180s
            if mt5_log_loaded(ea, sym):
                _dep_done = True
                break
            f = find_hb(ea)
            if f and time.time() - os.path.getmtime(f) < 120:
                _dep_done = True
                break
            time.sleep(2)
        if _dep_done:
            print(f"       ✅ {ea} 部署完成確認")
        else:
            print(f"       ⚠️ {ea} 等咗 180s 未確認完成（繼續下一隻）")
        time.sleep(2)

    # 4. 驗證（每個 EA：MT5 log loaded + 心跳新鮮）
    for i, (ea, sym) in enumerate(round_ea, 1):
        # 等部署完成（watcher + auto_attach 需要時間）
        log_ok = False; hb_ok = False; hb_age = None
        for _ in range(60):  # 120s
            if mt5_log_loaded(ea, sym):
                log_ok = True
            f = find_hb(ea)
            if f:
                age = time.time() - os.path.getmtime(f)
                if age < 120:
                    hb_ok = True; hb_age = round(age, 1)
            if log_ok and hb_ok:
                break
            time.sleep(2)
        ok = log_ok or hb_ok
        if not ok:
            round_ok = False
        details.append((ea, 'log' if log_ok else ('hb' if hb_ok else 'FAIL'), log_ok, hb_ok, hb_age))
        print(f"  [4.{i}] 驗證 {ea}({sym}): {'✅' if ok else '❌'} log={log_ok} hb={hb_ok} (age={hb_age})")

    # 5. 剷除所有 EA（下一輪乾淨）
    print("  [5] 剷除所有 EA（下一輪乾淨）...")
    remove_all(op)
    time.sleep(5)
    for ea, _ in [(e, s) for e, s in sum(ROUNDS, [])]:
        clear_hb(ea)

    results.append(round_ok)
    print(f"  >>> Round {ri}: {'✅ PASS' if round_ok else '❌ FAIL'} ({sum(1 for d in details if d[0] and not d[1].startswith('FAIL') and d[1]!='install-fail')}/{n} EA)")
    time.sleep(3)

print(f"\n{'='*64}\n  📊 壓力測試總結: {sum(results)}/5 PASS\n{'='*64}")
for i, ok in enumerate(results, 1):
    print(f"  Round {i} ({len(ROUNDS[i-1])} EA): {'✅' if ok else '❌'}")
sys.exit(0 if all(results) else 1)
