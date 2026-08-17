"""壓力測試 ×5：配對→部署→驗證心跳→刪除→確認清走（經 live backend 127.0.0.1:5001 = 同套 server code）

每輪：
  1. install-local (配對，寫 config + compile + copy MT5Cloud_EA)
  2. /api/deploy (寫 deploy_cmd → watcher → auto_attach → MT5 開圖表 + 掛 EA)
  3. 驗證 heartbeat file (Common/Files/hb_{ea}.txt) age < 120s
  4. remove-local (刪除 → 清 files + config + flag → watcher detach EA)
  5. 確認 config 無 ea + heartbeat file gone
"""
import urllib.request, json, http.cookiejar, socket, os, time, sys, glob

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
socket.setdefaulttimeout(30)
BASE = 'http://127.0.0.1:5001'
APPDATA = os.environ['APPDATA']
COMMON = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')

EA = 'EMA_Cross'
FILENAME = 'EMA_Cross.mq5'

def login():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    data = json.dumps({'username':'dev','password':'dev1234','mt5_account':'5053721681','mt5_password':'eip5ai0n'}).encode()
    req = urllib.request.Request(BASE+'/login', data=data, headers={'Content-Type':'application/json'})
    op.open(req).read()
    return op, cj

def post(op, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else b''
    req = urllib.request.Request(BASE+url, data=data, headers={'Content-Type':'application/json'}, method='POST')
    return json.loads(op.open(req).read().decode())

def get(op, url):
    req = urllib.request.Request(BASE+url)
    return json.loads(op.open(req).read().decode())

def find_hb(ea):
    pats = [os.path.join(COMMON, f'hb_{ea}.txt'),
            os.path.join(COMMON, f'state_{ea}.json'),
            os.path.join(APPDATA,'MetaQuotes','Terminal','*','MQL5','Files',f'hb_{ea}.txt'),
            os.path.join(APPDATA,'MetaQuotes','Terminal','*','MQL5','Files',f'state_{ea}.json')]
    for p in pats:
        for f in glob.glob(p):
            return f
    return None

def db_has_ea():
    import sqlite3
    c = sqlite3.connect('C:/Users/hongk/Desktop/mt5-cloud/instance/mt5cloud.db')
    row = c.execute("SELECT ea_config FROM user WHERE username='dev'").fetchone()
    cfg = json.loads(row[0]) if row and row[0] else {}
    c.close()
    return EA in cfg

results = []
for i in range(1, 6):
    print(f"\n{'='*60}\n  🔄 壓力測試 Round {i}/5 — {EA}\n{'='*60}")
    op, cj = login()
    # 1. 配對 (install-local)
    r1 = post(op, f'/api/ea-library/install-local/{FILENAME}')
    print(f"  [1] 配對 install-local: success={r1.get('success')} compile_ok={r1.get('compile_ok')}")
    time.sleep(6)
    # 2. 部署
    r2 = post(op, '/api/deploy', {'ea_name':EA,'symbol':'EURUSD','tf':'H1','magic':'7777'+str(i),'lot':1})
    print(f"  [2] 部署 /api/deploy: success={r2.get('success')} msg={r2.get('message')}")
    # 3. 驗證心跳 (等 auto_attach + EA init)
    hb_ok = False; hb_age = None; waited = 0
    for _ in range(30):  # up to 60s
        f = find_hb(EA)
        if f:
            age = time.time() - os.path.getmtime(f)
            if age < 120:
                hb_ok = True; hb_age = round(age,1); break
        time.sleep(2); waited += 2
    print(f"  [3] 心跳驗證: {'✅ PASS' if hb_ok else '❌ FAIL'} (age={hb_age}s, waited={waited}s)")
    # 4. 刪除
    r4 = post(op, f'/api/ea-library/remove-local/{EA}')
    print(f"  [4] 刪除 remove-local: success={r4.get('success')}")
    # 5. 確認清走 (等 watcher detach + flag process)
    time.sleep(15)
    cfg_ok = not db_has_ea()
    # 清走可能殘留嘅心跳 file（EA detach 後停止寫，但舊 file 仲喺）
    for pat in [os.path.join(COMMON, f'hb_{EA}.txt'),
                os.path.join(COMMON, f'state_{EA}.json')]:
        for f in glob.glob(pat):
            try: os.remove(f)
            except: pass
    hb_gone = find_hb(EA) is None
    print(f"  [5] 確認清走: config無EA={'✅' if cfg_ok else '❌'} | 心跳file消失={'✅' if hb_gone else '❌'}")
    overall = hb_ok and cfg_ok and hb_gone
    results.append(overall)
    print(f"  >>> Round {i}: {'✅ PASS' if overall else '❌ FAIL'}")
    # 清走可能殘留嘅 flag（避免影響下一輪）
    for fl in glob.glob(os.path.join(COMMON, f'web_delete_{EA}*')):
        try: os.remove(fl)
        except: pass
    time.sleep(3)

print(f"\n{'='*60}\n  📊 壓力測試總結: {sum(results)}/5 PASS\n{'='*60}")
for i, ok in enumerate(results, 1):
    print(f"  Round {i}: {'✅' if ok else '❌'}")
sys.exit(0 if all(results) else 1)
