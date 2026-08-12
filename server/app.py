# MT5 Cloud — Full Platform Server
# 公開網站，每人有自己的 EA 配對 + 分析 + Correlation

import os
import json
import uuid
import threading
import time
import glob
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, make_response
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from collections import defaultdict
import math

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mt5cloud.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
# Use eventlet on Render (gunicorn), threading on dev

# ─── Activity Log（持久化活動記錄，JSONL append）───
ACTIVITY_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'activity_log.jsonl')
_activity_lock = threading.Lock()


def log_activity(action, message, ea='', source='server'):
    """append 一行 JSONL 去 activity_log.jsonl（thread-safe）"""
    try:
        entry = {
            'time': time.time(),
            'action': action,
            'ea': ea,
            'message': message,
            'source': source,
        }
        line = json.dumps(entry, ensure_ascii=False) + '\n'
        with _activity_lock:
            with open(ACTIVITY_LOG_PATH, 'a', encoding='utf-8') as f:
                f.write(line)
    except Exception:
        pass


@app.route('/api/control-steps', methods=['GET', 'POST'])
@login_required
def api_control_steps():
    """🚨 2026-08-10：攞操作步驟（警告視窗顯示 — 一排排）
    POST（2026-08-12）：前端逐步更新 steps（重新整理流程 — 刷新邊一項 + 成唔成功）"""
    if request.method == 'POST':
        try:
            import time as _tw
            data = request.json or {}
            steps_in = data.get('steps')
            sig = data.get('sig', '')
            agent_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
            if sig:
                with open(os.path.join(agent_dir, '.ai_control.show'), 'w', encoding='utf-8') as _f:
                    _f.write(sig)
            if isinstance(steps_in, list):
                with open(os.path.join(agent_dir, '.ai_control.steps'), 'w', encoding='utf-8') as _f:
                    json.dump(steps_in, _f, ensure_ascii=False)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    try:
        agent_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
        steps_file = os.path.join(agent_dir, '.ai_control.steps')
        if os.path.isfile(steps_file):
            try:
                with open(steps_file, 'r', encoding='utf-8') as f:
                    steps_data = json.load(f)
                if not isinstance(steps_data, list):
                    steps_data = []
            except Exception:
                # 🚨 2026-08-12：讀唔到（多個 process 同時寫 → 檔案損壞/空）→ 唔返回 []（網頁唔會空白 — 彈嚟彈去根治）
                steps_data = [{'text': '等待操作開始…', 'status': 'pending'}]
            # 🚨 2026-08-11：返回 steps + mtime（前端用嚟判斷「舊 steps 唔顯示」— 新任務開始唔會殘留上一個操作 — 用戶投訴）
            import time as _tm
            return jsonify({"steps": steps_data, "mtime": os.path.getmtime(steps_file)})
        return jsonify({"steps": [{'text': '等待操作開始…', 'status': 'pending'}], "mtime": 0})
    except Exception:
        return jsonify([])


@app.route('/api/control-guard/stop', methods=['POST'])
@login_required
def api_control_guard_stop():
    """網站版緊急停止：寫 .ai_control.stop 標記 → watcher/compile/auto_attach 偵測到就 abort"""
    try:
        agent_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
        stop_file = os.path.join(agent_dir, '.ai_control.stop')
        with open(stop_file, 'w', encoding='utf-8') as f:
            f.write('stop|web')
        # 強制寫 ai_control.json inactive → 網站警告視窗即刻關（Bug #68：唔可以卡死）
        try:
            detector_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        'server', 'static', 'detector')
            os.makedirs(detector_dir, exist_ok=True)
            status_file = os.path.join(detector_dir, 'ai_control.json')
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump({'active': False, 'program': '', 'time': time.time()}, f, ensure_ascii=False)
        except Exception:
            pass
        log_activity('emergency_stop', '網站緊急停止已觸發（AI 操作會即刻中止）', ea='')
        return jsonify({"success": True, "message": "緊急停止已觸發"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/activity')
def api_activity():
    """讀 activity log（倒序，全部）— refresh 後依然存在（持久檔案，唔會刪除）
    ?include_db=1 → 連「已更新資料庫」恆常記錄一齊顯示（預設隱藏，因為太頻密阻礙其他資訊）
    """
    include_db = request.args.get('include_db', '0') == '1'
    entries = []
    try:
        with open(ACTIVITY_LOG_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    entries.reverse()  # 最新喺最前
    if not include_db:
        entries = [e for e in entries if e.get('action') != 'db_update']
    return jsonify({'activities': entries})  # 全部顯示 — log 唔會刪除
import os
_async_mode = 'eventlet' if os.environ.get('RENDER', '') else 'threading'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=_async_mode, logger=False, engineio_logger=False)

# === Database ===
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    agent = db.relationship('Agent', backref='user', uselist=False)
    ea_config = db.Column(db.Text, default='{}')  # EA 配對設定
    bound_account = db.Column(db.String(64), default='')  # 綁定 MT5 account

class Agent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='offline')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    account_info = db.Column(db.Text, default='{}')
    positions = db.Column(db.Text, default='[]')
    deals = db.Column(db.Text, default='[]')
    deploy_queue = db.Column(db.Text, default='')
    ea_heartbeats = db.Column(db.Text, default='{}')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()
    # 建立固定 Dev Account（如果未存在）
    if not User.query.filter_by(username='dev').first():
        dev_user = User(username='dev', email='dev@mt5cloud.com',
                        password=generate_password_hash('dev1234'))
        db.session.add(dev_user)
        dev_agent = Agent(agent_id='DEV00001', user=dev_user)
        db.session.add(dev_agent)
        db.session.commit()
        print("✅ Dev account created: dev / dev1234")

# 預設交易品種
ALL_SYMBOLS = ['EURUSD','GBPUSD','USDJPY','AUDUSD','USDCAD','NZDUSD',
               'EURJPY','GBPJPY','EURGBP','EURCHF','GBPCHF','AUDJPY',
               'GBPAUD','EURNZD','XAUUSD','XAGUSD',
               'US30','US500','DE40','UK100','JP225','AUS200',
               'BTCUSD','ETHUSD']
TIMEFRAMES = ['M1','M5','M15','M30','H1','H4','D1','W1','MN1']

# === Frontend ===
@app.route('/')
def index():
    if current_user.is_authenticated:
        # 🚨 2026-08-11：dashboard.html 唔 cache（前端 JS 一定攞最新 — 用戶硬刷新都唔夠時確保）
        resp = make_response(render_template('dashboard.html'))
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        return resp
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # 🚨 2026-08-11：dashboard.html 唔 cache
    resp = make_response(render_template('dashboard.html'))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        data = request.json if request.is_json else request.form
        if User.query.filter_by(username=data.get('username')).first():
            return jsonify({"error":"Username taken"}),400
        user = User(username=data['username'], email=data.get('email',''),
                    password=generate_password_hash(data['password']))
        db.session.add(user)
        agent = Agent(agent_id=str(uuid.uuid4())[:8], user=user)
        db.session.add(agent)
        db.session.commit()
        login_user(user)
        return jsonify({"success":True,"agent_id":agent.agent_id})
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        data = request.json if request.is_json else request.form
        user = User.query.filter_by(username=data.get('username')).first()
        if user and check_password_hash(user.password, data.get('password')):
            mt5_account = data.get('mt5_account', '').strip()
            
            # If mt5_account provided, verify it matches cached account info
            if mt5_account:
                with _auto_trade_lock:
                    cached_acc = _auto_trade_cache.get("account_info", {})
                local_login = cached_acc.get('login', '')
                
                # Skip check if cache hasn't populated yet - let them in
                if local_login and str(local_login) != str(mt5_account):
                    return jsonify({
                        "error": f"MT5 帳號不匹配：你輸入 {mt5_account}，本地 MT5 係 {local_login}",
                        "mt5_mismatch": True,
                        "local_account": local_login
                    }), 401
                
                # Account matches or cache not ready - auto-bind
                if local_login:
                    user.bound_account = mt5_account
                    db.session.commit()
            
            login_user(user)
            log_activity('login', f'{user.username} 登入', source='auth')
            return jsonify({"success": True, "bound_account": user.bound_account or mt5_account or ''})
        return jsonify({"error": "Invalid credentials"}), 401
    return render_template('login.html')

@app.route('/api/test-account', methods=['POST'])
def api_test_account():
    """建立測試帳號（一鍵生成）"""
    import string, random
    # Generate random username
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    username = f"test_{suffix}"
    password = "test1234"

    user = User(username=username, email=f"{username}@test.com",
                password=generate_password_hash(password))
    db.session.add(user)
    agent = Agent(agent_id=str(uuid.uuid4())[:8], user=user)
    db.session.add(agent)
    db.session.commit()

    return jsonify({
        "success": True,
        "username": username,
        "password": password,
        "agent_id": agent.agent_id
    })

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# === API: EA 配對表 ===
@app.route('/api/ea-config', methods=['GET','POST'])
@login_required
def api_ea_config():
    if request.method == 'GET':
        # 🚨 2026-08-11：直接 SQL 讀 DB（SQLAlchemy session 有隔離問題 — current_user.ea_config 返回舊值含已刪除 EA）
        try:
            import sqlite3 as _sq2
            _dbp2 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'mt5cloud.db')
            _c2 = _sq2.connect(_dbp2)
            _c2.row_factory = _sq2.Row
            _r2 = _c2.execute('SELECT ea_config FROM user WHERE id=?', (current_user.id,)).fetchone()
            _c2.close()
            config = json.loads(_r2['ea_config'] or '{}') if _r2 else {}
        except Exception:
            config = json.loads(current_user.ea_config or '{}')
        # ⚠️ 控制層心跳狀態（CONTROL_LAYER_DESIGN.md）：讀 Common/Files/state_<ea>.json
        # running（ts 新鮮 <30 秒）/ stopped / unknown（冇檔或過期）
        # ⚠️ 2026-08 修：config 冇 _status key（只有 ea_name/ea_lot/ea_magic/ea_tf）→ 唔可以靠 _status 尾
        runtime = {}
        try:
            common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
            ea_names = set()
            for key in config:
                base = key
                for suffix in ('_lot', '_magic', '_tf', '_status'):
                    if key.endswith(suffix):
                        base = key[:-len(suffix)]
                        break
                if base and base not in ('_lot', '_magic', '_tf', '_status'):
                    ea_names.add(base)
            for ea in ea_names:
                sf = os.path.join(common_files, f'state_{ea}.json')
                st = 'unknown'
                if os.path.isfile(sf):
                    try:
                        # ⚠️ MQL5 FileWrite 寫 UTF-16 LE（BOM \xff\xfe）— 要 fallback decode
                        with open(sf, 'rb') as f:
                            raw = f.read()
                        try:
                            sd = json.loads(raw.decode('utf-8'))
                        except Exception:
                            sd = json.loads(raw.decode('utf-16'))
                        # ⚠️ 新鮮度用檔案 mtime（MQL5 TimeCurrent 係 broker time — 同系統時差）
                        age = time.time() - os.path.getmtime(sf)
                        if sd.get('status') == 'stopped':
                            st = 'stopped'
                        elif age < 30:
                            st = 'running'
                    except Exception:
                        st = 'unknown'
                runtime[ea] = st
        except Exception:
            pass
        return jsonify({"mappings": config, "all_symbols": ALL_SYMBOLS, "timeframes": TIMEFRAMES, "runtime_status": runtime})
    else:
        data = request.json
        current_user.ea_config = json.dumps(data.get('mappings', {}))
        db.session.commit()
        return jsonify({"success": True})

@app.route('/api/ea-config/<ea_name>', methods=['DELETE'])
@login_required
def api_ea_config_delete(ea_name):
    """刪除一個 EA 嘅配對
    ⚠️ 用戶要求（2026-08）：刪除配對庫 EA = 連埋 MT5 圖表嘅 EA 一齊移除
    → 寫 pause_cmd 俾 watcher（auto_attach --remove 移除圖表 EA）"""
    # ⚠️ 系統檔案保護（Controller — 唔可以刪除）
    if ea_name == 'Controller':
        return jsonify({"success": False, "error": "系統檔案（Controller）唔可以刪除"}), 403
    # 確保 MT5 開住（移除圖表需要）
    ensure_mt5_running()
    # 寫 pause_cmd（watcher 用現有 process_pause_cmd 移除圖表 EA — 重用機制）
    try:
        common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
        os.makedirs(common_files, exist_ok=True)
        cmd_path = os.path.join(common_files, f'pause_cmd_{ea_name}_{int(time.time())}.json')
        with open(cmd_path, 'w', encoding='utf-8') as f:
            json.dump({'ea_name': ea_name, 'action': 'remove'}, f, ensure_ascii=False)
        print(f"[ea-config-delete] 圖表移除指令已排隊: {os.path.basename(cmd_path)}")
    except Exception as e:
        print(f"[ea-config-delete] pause_cmd 寫入失敗: {e}")
    config = json.loads(current_user.ea_config or '{}')
    # 加去 _removed 列表
    removed = config.get('_removed', [])
    if ea_name not in removed:
        removed.append(ea_name)
    config['_removed'] = removed
    # 刪除相關 key
    for key in list(config.keys()):
        if key == ea_name or key.startswith(ea_name + '_'):
            del config[key]
    current_user.ea_config = json.dumps(config)
    db.session.commit()
    # 🎯 刪除 → 釋放快捷鍵（2026-08 用戶設計：刪除後快捷鍵一齊移除 + 位置放返）
    try:
        release_hotkey(ea_name)
    except Exception:
        pass
    log_activity('ea_delete', f'{ea_name} 配對已刪除（圖表 EA 已排隊移除）', ea=ea_name)
    return jsonify({"success": True})


@app.route('/api/ea-config/<ea_name>/purge', methods=['POST'])
def api_ea_config_purge(ea_name):
    """Watcher 專用：電腦（MT5）刪除 EA 後，自動移除配對 config（配對庫即刻消失）
    認證：agent_id 參數（DEV00001）— watcher 用
    """
    import re as _re
    if not _re.fullmatch(r'[A-Za-z0-9_]+', ea_name):
        return jsonify({"success": False, "error": "Invalid name"}), 400
    agent_id = request.args.get('agent_id', '')
    agent = Agent.query.filter_by(agent_id=agent_id).first()
    if not agent:
        return jsonify({"success": False, "error": "Unauthorized agent"}), 401

    user = agent.user
    config = json.loads(user.ea_config or '{}')
    removed = config.get('_removed', [])
    if ea_name not in removed:
        removed.append(ea_name)
    config['_removed'] = removed
    for key in list(config.keys()):
        if key == ea_name or key.startswith(ea_name + '_'):
            del config[key]
    user.ea_config = json.dumps(config)
    db.session.commit()
    log_activity('ea_delete', f'{ea_name} 已於電腦刪除（配對已自動移除）', ea=ea_name)
    return jsonify({"success": True, "removed": ea_name})

@app.route('/api/ea-config/<ea_name>/toggle', methods=['POST'])
@login_required
def api_ea_config_toggle(ea_name):
    """Toggle EA status：running ↔ paused
    暫停 = 真暫停（移除圖表 EA — 寫 pause_cmd 俾 watcher 處理）
    恢復 = 重新部署（寫 deploy_cmd）"""
    # ⚠️ 系統檔案保護（Controller — 唔可以暫停/恢復）
    if ea_name == 'Controller':
        return jsonify({"success": False, "error": "系統檔案（Controller）唔可以暫停"}), 403
    # ⚠️ 用戶要求（2026-08）：每次操作 MT5 相關嘢，先偵測 MT5 有冇開 — 冇就開返
    ensure_mt5_running()
    config = json.loads(current_user.ea_config or '{}')
    current_status = config.get(ea_name + '_status', 'running')
    new_status = 'paused' if current_status == 'running' else 'running'
    config[ea_name + '_status'] = new_status
    current_user.ea_config = json.dumps(config)
    db.session.commit()
    log_activity('ea_toggle', f'{ea_name} {"暫停" if new_status == "paused" else "恢復運行"}', ea=ea_name)

    # 真暫停/恢復：寫指令俾 watcher（watcher 有 desktop access 操作 MT5 GUI）
    try:
        import time as _ct
        common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
        os.makedirs(common_files, exist_ok=True)
        if new_status == 'paused':
            # ⚠️ 控制層方案（CONTROL_LAYER_DESIGN.md）：暫停 → 寫 ctrl_<ea>.json {"cmd":"stop"}
            # EA（已注入控制層）讀到 → ExpertRemove() 自己移除 → 寫 stopped 心跳
            # ✅ 唔使 watcher / GUI 操作（MT5 唔會死）
            cmd_path = os.path.join(common_files, f'ctrl_{ea_name}.json')
            with open(cmd_path, 'w', encoding='utf-8') as f:
                json.dump({'cmd': 'stop'}, f, ensure_ascii=False)
            # 保留 pause_cmd 做後備（如果 EA 冇控制層 — watcher GUI 移除）
            pause_path = os.path.join(common_files, f'pause_cmd_{ea_name}_{int(_ct.time())}.json')
            with open(pause_path, 'w', encoding='utf-8') as f:
                json.dump({'ea_name': ea_name, 'action': 'remove'}, f, ensure_ascii=False)
        else:
            # 恢復 → 重新部署（auto_attach 附加）
            symbol = config.get(ea_name, 'EURUSD')
            tf = config.get(ea_name + '_tf', 'H1')
            magic = config.get(ea_name + '_magic', '240701')
            lot = config.get(ea_name + '_lot', 1.0)
            cmd_path = os.path.join(common_files, f'deploy_cmd_{ea_name}_{int(_ct.time())}.json')
            with open(cmd_path, 'w', encoding='utf-8') as f:
                json.dump({'ea_name': ea_name, 'symbol': symbol, 'tf': tf, 'magic': magic, 'lot': lot}, f, ensure_ascii=False)
    except Exception as e:
        print(f"[DEBUG] toggle cmd 寫入失敗: {e}")

    return jsonify({"success": True, "status": new_status})

# === API: Dashboard ===
# ⚠️ 用戶要求（2026-08）：每次操作 MT5 相關嘢，先偵測 MT5 有冇開 — 冇就開返
MT5_EXE_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"

def ensure_mt5_running():
    """確保 MT5 開住 — 冇就開返（等最多 30 秒 process 出現）
    所有會操作 MT5 嘅 API（install-local / deploy / toggle / remove-local / retry-compile）開頭 call"""
    import subprocess as _sp
    try:
        # ⚠️ 用 bytes 檢查（唔好 text=True）— tasklist 輸出係 GBK/中文，MSYS UTF-8 locale decode 會炸
        r = _sp.run('tasklist /FI "IMAGENAME eq terminal64.exe" /NH', shell=True, capture_output=True, timeout=5)
        if b'terminal64' in r.stdout:
            return True
        print("[ensure_mt5] MT5 未開啟 — 自動啟動...")
        try:
            _sp.Popen([MT5_EXE_PATH])
        except Exception as e:
            print(f"[ensure_mt5] 啟動失敗: {e}")
            return False
        # 等最多 30 秒 MT5 process 出現（登入由 MT5 自動處理）
        for _ in range(30):
            time.sleep(1)
            try:
                r2 = _sp.run('tasklist /FI "IMAGENAME eq terminal64.exe" /NH', shell=True, capture_output=True, timeout=5)
                if b'terminal64' in r2.stdout:
                    print("[ensure_mt5] MT5 已啟動（登入中）")
                    return True
            except Exception:
                pass
        print("[ensure_mt5] MT5 啟動等待超時（30 秒）")
        return False
    except Exception as e:
        print(f"[ensure_mt5] 偵測失敗: {e}")
        return False


# Auto-trade status: background thread refresh so dashboard never blocks
_auto_trade_cache = {"result": [], "timestamp": 0}
_auto_trade_lock = threading.Lock()
_last_deploy_time = {}  # 🚨 2026-08-12：防重複部署（同一 EA 30 秒內唔可以再 deploy）

def _refresh_auto_trade_cache(user):
    """background thread: update auto_trade_cache without blocking dashboard"""
    global _auto_trade_cache
    try:
        result = compute_auto_trade_status(user)
        with _auto_trade_lock:
            _auto_trade_cache["result"] = result
            _auto_trade_cache["timestamp"] = time.time()
    except Exception as e:
        print(f"[DEBUG] compute_auto_trade_status failed: {e}")
        pass
    
    # Also refresh account info（🚨 2026-08-12 修：唔直接 init MT5 — detector 已持連接 → read 佢嘅 auto_trade_status.json）
    try:
        status_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    'server', 'static', 'detector', 'auto_trade_status.json')
        if os.path.isfile(status_file):
            with open(status_file, 'r', encoding='utf-8') as f:
                status_data = json.load(f)
            status_account = status_data.get('account', '').strip()
            if status_account:
                with _auto_trade_lock:
                    _auto_trade_cache["account_info"] = status_data.get("account_info", {'login': status_account})
                # 🚨 2026-08-12：save to DB agent.account_info（dashboard HTML template needs it）
                try:
                    agent = Agent.query.filter_by(user_id=user.id).first()
                    if agent and not agent.account_info or agent.account_info == '{}':
                        agent.account_info = json.dumps(status_data.get("account_info", {'login': status_account}))
                        db.session.commit()
                except Exception:
                    pass
    except Exception as e:
        print(f"[DEBUG] auto_trade_status read failed: {e}")
        pass

@app.route('/api/dashboard')
@login_required
def api_dashboard():
    agent = Agent.query.filter_by(user_id=current_user.id).first()
    account = json.loads(agent.account_info or '{}')
    positions = json.loads(agent.positions or '[]')
    # Count auto-traded EAs
    try:
        ea_cfg = json.loads(current_user.ea_config or '{}')
        auto_count = len([k for k in ea_cfg if not k.startswith('_') and not k.endswith(('_tf','_lot','_magic','_status')) and isinstance(ea_cfg[k], str)])
    except:
        auto_count = 0
    
    # Always return cache instantly. Refresh in background thread every 30s.
    import time as _t
    now = _t.time()
    global _auto_trade_cache
    if now - _auto_trade_cache["timestamp"] > 30:
        # 🚨 2026-08-12：first call → sync（background thread fails silently）
        if _auto_trade_cache["timestamp"] == 0:
            _refresh_auto_trade_cache(current_user)
        else:
            import threading as _th
            _th.Thread(target=_refresh_auto_trade_cache, args=(current_user,), daemon=True).start()
    
    with _auto_trade_lock:
        cache_result = _auto_trade_cache["result"]
        account_info = _auto_trade_cache.get("account_info", {})
    
    return jsonify({
        "status": agent.status,
        "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
        "account": account_info,
        "bound_account": current_user.bound_account or '',
        "account_matched": bool(current_user.bound_account and account_info.get('login') == current_user.bound_account),
        "positions": positions,
        "agent_id": agent.agent_id,
        "auto_trade_ea_count": auto_count,
        "auto_trade_status": cache_result,
        "ea_heartbeats": json.loads(agent.ea_heartbeats or '{}') if agent else {}
    })


def compute_auto_trade_status(user):
    """即時計算 Auto-Trade 嘅 market condition"""
    import MetaTrader5 as mt5
    
    TF_MAP = {'M1':1,'M5':5,'M15':15,'M30':30,'H1':60,'H4':240,'D1':1440,'W1':10080,'MN1':43200}
    MUL = {1:1, 5:5, 15:15, 30:30, 60:60, 240:240, 1440:1440, 10080:10080, 43200:43200}
    
    try:
        cfg = json.loads(user.ea_config or '{}')
        eas = [k for k in cfg if not k.startswith('_') and not k.endswith(('_tf','_lot','_magic','_status')) and isinstance(cfg[k], str)]
    except:
        return []
    
    # First check if MT5 is already running — don't auto-start it!
    import subprocess as _sp
    _mt5_running = False
    try:
        _out = _sp.check_output('tasklist /FI "IMAGENAME eq terminal64.exe" /NH', shell=True, timeout=3)
        if b'terminal64' in _out:
            _mt5_running = True
    except:
        pass
    
    if not _mt5_running:
        return []  # MT5 not running, skip auto-trade (don't pop up MT5)
    
    try:
        if not mt5.initialize(timeout=5000):  # 5s timeout — 唔好塞死 server
            return []
    except:
        return []
    
    results = []
    for ea in eas:
        symbol = cfg[ea]
        if symbol in ('DE40','US500','US100','JP225'):
            # Indexes - might not have M1 data, skip for now
            continue
        tf_str = cfg.get(ea + '_tf', 'H1')
        tf = TF_MAP.get(tf_str, 60)
        mul = MUL.get(tf, 60)
        
        mt5.symbol_select(symbol, True)
        need = max(2000, 40 * mul)
        rates = mt5.copy_rates_from_pos(symbol, 1, 0, need)
        if rates is None or len(rates) < need:
            continue
        
        closes = [float(rates[i][4]) for i in range(len(rates))]
        tf_closes = [closes[i] for i in range(mul-1, len(closes), mul)]
        n = len(tf_closes)
        if n < 35:
            continue
        
        fast = [sum(tf_closes[i:i+10])/10.0 for i in range(n-9)]
        slow = [sum(tf_closes[i:i+30])/30.0 for i in range(n-29)]
        
        cross_buy = fast[-1] > slow[-1] and fast[-2] <= slow[-2]
        cross_sell = fast[-1] < slow[-1] and fast[-2] >= slow[-2]
        
        if cross_buy:
            signal = 'BUY'
        elif cross_sell:
            signal = 'SELL'
        else:
            signal = 'WAIT'
        
        results.append({
            'ea': ea, 'symbol': symbol, 'tf': tf_str,
            'sma10': round(fast[-1], 5), 'sma30': round(slow[-1], 5),
            'signal': signal, 'alive': True
        })
    
    mt5.shutdown()
    return results

# === API: Analysis ===
@app.route('/api/analysis')
@login_required
def api_analysis():
    agent = Agent.query.filter_by(user_id=current_user.id).first()
    deals_data = json.loads(agent.deals or '[]')
    if not deals_data:
        return jsonify({"error":"No data yet"})

    # Per-EA by (magic, symbol)
    per_ea = defaultdict(lambda: {"trades":0,"profit":0,"wins":0,"losses":0})
    for d in deals_data:
        key = f"{d['magic']}_{d['symbol']}"
        per_ea[key]["trades"] += 1
        per_ea[key]["profit"] += d['profit']
        if d['profit'] > 0: per_ea[key]["wins"] += 1
        elif d['profit'] < 0: per_ea[key]["losses"] += 1

    per_ea_list = []
    per_ea_by_symbol = {}
    per_ea_by_magic_symbol = {}
    for key, info in sorted(per_ea.items()):
        total = info["wins"]+info["losses"]
        wr = round(info["wins"]/total*100,1) if total>0 else 0
        parts = key.split("_",1)
        magic = parts[0]
        symbol = parts[1] if len(parts)>1 else ""
        per_ea_list.append({
            "ea": f"Magic#{magic}", "symbol": symbol, "magic": magic,
            "trades": info["trades"], "profit": round(info["profit"],2),
            "wins": info["wins"], "losses": info["losses"], "win_rate": wr
        })
        # By symbol
        if symbol not in per_ea_by_symbol:
            per_ea_by_symbol[symbol] = {"trades":0,"profit":0,"wins":0,"losses":0}
        per_ea_by_symbol[symbol]["trades"] += info["trades"]
        per_ea_by_symbol[symbol]["profit"] += info["profit"]
        per_ea_by_symbol[symbol]["wins"] += info["wins"]
        per_ea_by_symbol[symbol]["losses"] += info["losses"]
        # By magic+symbol (precise matching)
        ms_key = f"{magic}_{symbol}"
        per_ea_by_magic_symbol[ms_key] = {
            "trades": info["trades"], "profit": round(info["profit"],2),
            "wins": info["wins"], "losses": info["losses"], "win_rate": wr,
            "magic": magic, "symbol": symbol
        }
    for sym in per_ea_by_symbol:
        info = per_ea_by_symbol[sym]
        total = info["wins"]+info["losses"]
        info["win_rate"] = round(info["wins"]/total*100,1) if total>0 else 0
        info["profit"] = round(info["profit"],2)

    # Collect unique magic numbers
    all_magics = sorted(set(str(d['magic']) for d in deals_data if d['magic'] != 0))

    # Correlation
    daily_pnl = defaultdict(lambda: defaultdict(float))
    for d in deals_data:
        date_key = str(d.get('time',''))[:10]
        key = f"{d['magic']}_{d['symbol']}"
        daily_pnl[key][date_key] += d['profit']

    ea_keys = sorted(daily_pnl.keys())
    all_dates = sorted(set(d for dates in daily_pnl.values() for d in dates.keys()))
    matrix = {ek:[daily_pnl[ek].get(dt,0) for dt in all_dates] for ek in ea_keys}

    def pearson(x,y):
        n=len(x); 
        if n<3: return 0
        sx=sum(x);sy=sum(y);sxx=sum(v*v for v in x);syy=sum(v*v for v in y);sxy=sum(x[i]*y[i] for i in range(n))
        d=math.sqrt((n*sxx-sx*sx)*(n*syy-sy*sy))
        return (n*sxy-sx*sy)/d if d!=0 else 0

    corr_matrix = []
    for ek1 in ea_keys:
        row = {"ea":ek1}
        for ek2 in ea_keys:
            row[ek2] = round(pearson(matrix[ek1],matrix[ek2]),2)
        corr_matrix.append(row)

    total_profit = sum(d['profit'] for d in deals_data)
    wins = sum(1 for d in deals_data if d['profit']>0)
    losses = sum(1 for d in deals_data if d['profit']<0)
    wr = round(wins/(wins+losses)*100,2) if (wins+losses)>0 else 0

    return jsonify({
        "summary":{"total_trades":len(deals_data),"wins":wins,"losses":losses,
                   "win_rate":wr,"total_profit":round(total_profit,2)},
        "per_ea": per_ea_list,
        "per_ea_by_symbol": per_ea_by_symbol,
        "per_ea_by_magic_symbol": per_ea_by_magic_symbol,
        "all_magics": all_magics,
        "correlation_matrix": corr_matrix,
        "correlation_keys": ea_keys
    })


@app.route('/api/ea-report')
@login_required
def api_ea_report():
    """EA 診斷報告：equity curve + 詳細 stats"""
    magic = request.args.get('magic', '')
    symbol = request.args.get('symbol', '')
    if not magic or not symbol:
        return jsonify({"error": "需要 magic + symbol"}), 400

    agent = Agent.query.filter_by(user_id=current_user.id).first()
    deals_data = json.loads(agent.deals or '[]')

    # 過濾指定 EA
    ea_deals = [d for d in deals_data
                if str(d.get('magic', '')) == str(magic)
                and d.get('symbol', '') == symbol
                and d.get('profit', 0) != 0]

    # 按時間排序
    ea_deals.sort(key=lambda x: x.get('time', ''))

    # Equity curve (cumulative P&L)
    equity = []
    cum = 0.0
    for d in ea_deals:
        cum += d['profit']
        equity.append({
            "time": d['time'],
            "profit": d['profit'],
            "cumulative": round(cum, 2)
        })

    # 基本統計
    wins = [d for d in ea_deals if d['profit'] > 0]
    losses = [d for d in ea_deals if d['profit'] < 0]
    total = len(ea_deals)
    win_rate = round(len(wins) / total * 100, 2) if total > 0 else 0
    total_profit = round(sum(d['profit'] for d in ea_deals), 2)
    avg_win = round(sum(d['profit'] for d in wins) / len(wins), 2) if wins else 0
    avg_loss = round(sum(d['profit'] for d in losses) / len(losses), 2) if losses else 0
    profit_factor = round(abs(sum(d['profit'] for d in wins) / sum(d['profit'] for d in losses)), 2) if losses else float('inf')

    # Max drawdown
    peak = -float('inf')
    max_dd = 0
    max_dd_pct = 0
    dd_start = dd_end = None
    for d in equity:
        if d['cumulative'] > peak:
            peak = d['cumulative']
        dd = peak - d['cumulative']
        if dd > max_dd:
            max_dd = round(dd, 2)
            max_dd_pct = round(dd / peak * 100, 2) if peak > 0 else 0

    # Win/Loss distribution
    dist = {
        "bins": ["0-50", "50-100", "100-200", "200-500", "500+"],
        "wins": [0]*5, "losses": [0]*5
    }
    for d in ea_deals:
        amt = abs(d['profit'])
        idx = 4 if amt >= 500 else (3 if amt >= 200 else (2 if amt >= 100 else (1 if amt >= 50 else 0)))
        if d['profit'] > 0: dist['wins'][idx] += 1
        else: dist['losses'][idx] += 1

    # Monthly P&L
    monthly = {}
    for d in ea_deals:
        ym = str(d.get('time', ''))[:7]
        monthly[ym] = monthly.get(ym, 0) + round(d['profit'], 2)

    return jsonify({
        "magic": magic,
        "symbol": symbol,
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "total_profit": total_profit,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "max_drawdown_pct": max_dd_pct,
        "equity_curve": equity[-100:],  # last 100 trades
        "distribution": dist,
        "monthly_pnl": monthly
    })


@app.route('/api/agent-poll-deploy', methods=['GET'])
def api_agent_poll_deploy():
    """Agent 每 2 秒 poll 呢個 endpoint，睇下有冇 deploy 指令"""
    agent_id = request.args.get('agent_id')
    agent = Agent.query.filter_by(agent_id=agent_id).first()
    if agent and agent.deploy_queue:
        data = json.loads(agent.deploy_queue)
        agent.deploy_queue = ''  # Clear after reading
        db.session.commit()
        return jsonify(data)
    return jsonify({})


@app.route('/api/watcher-report', methods=['POST'])
def api_watcher_report():
    """部署監控器回報 deploy 結果"""
    data = request.json
    agent_id = data.get('agent_id', '')
    ea_name = data.get('ea_name', '')
    status = data.get('status', '')  # 'ok' or 'error'
    message = data.get('message', '')
    
    print(f"[WATCHER] Report: {ea_name} -> {status} ({message})")
    
    # Broadcast to dashboard via Socket.IO
    socketio.emit('install_result', {
        "status": status,
        "ea": ea_name,
        "msg": f"[Watcher] {message}"
    })
    
    return jsonify({"success": True})


# === API: EA 庫 ===
EA_LIBRARY_DIR = os.path.join(os.path.dirname(__file__), 'static', 'ea_library')
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'static', 'user_ea')
COMMUNITY_EA_DIR = os.path.join(os.path.dirname(__file__), 'static', 'community_ea')

# 確保目錄存在
os.makedirs(EA_LIBRARY_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(COMMUNITY_EA_DIR, exist_ok=True)

@app.route('/api/ea-library')
def api_ea_library():
    """返回 EA 庫列表（平台提供 + 社群提供 + 用戶上傳）"""
    files = []
    # 平台提供嘅 EA
    if os.path.isdir(EA_LIBRARY_DIR):
        for f in sorted(os.listdir(EA_LIBRARY_DIR)):
            if f.endswith('.mq5'):
                path = os.path.join(EA_LIBRARY_DIR, f)
                size = os.path.getsize(path)
                files.append({"name": f, "size": f"{size/1024:.1f} KB", "type": "official", "author": "Platform"})
    # 社群提供嘅 EA（Developer 上傳，所有人都睇到）
    if os.path.isdir(COMMUNITY_EA_DIR):
        for f in sorted(os.listdir(COMMUNITY_EA_DIR)):
            if f.endswith('.mq5'):
                path = os.path.join(COMMUNITY_EA_DIR, f)
                size = os.path.getsize(path)
                files.append({"name": f, "size": f"{size/1024:.1f} KB", "type": "community", "author": "Dev"})
    # 用戶上傳嘅 EA（只有自己睇到）
    if current_user.is_authenticated:
        user_dir = os.path.join(UPLOAD_DIR, current_user.username)
        if os.path.isdir(user_dir):
            for f in sorted(os.listdir(user_dir)):
                if f.endswith(('.mq5','.ex5')):
                    path = os.path.join(user_dir, f)
                    size = os.path.getsize(path)
                    files.append({"name": f, "size": f"{size/1024:.1f} KB", "type": "user", "author": current_user.username})
    return jsonify({"files": files, "count": len(files)})


@app.route('/api/ea-library/refresh', methods=['POST'])
@login_required
def api_ea_library_refresh():
    """🚨 2026-08-11：配對庫「重新整理」— 警告視窗流程（重新整理緊 → 成功確定 / 失敗紅色+原因+確定）
    重新整理唔係危險操作 → 失敗都係「確定」（唔需要緊急停止）
    用 control_guard acquire/release（寫 .ai_control.show + ai_control.json active — 網頁+電腦版都彈）"""
    import json as _jrf
    _adir_rf = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
    # acquire（警告視窗彈 — 網頁 modal + 電腦版）
    _cg = None
    try:
        sys.path.insert(0, _adir_rf)
        import control_guard as _cg
        _cg.acquire('重新整理配對庫')
    except Exception:
        _cg = None
    try:
        with open(os.path.join(_adir_rf, '.ai_control.show'), 'w', encoding='utf-8') as _f:
            _f.write('重新整理配對庫')
        # 🚨 2026-08-12：詳細步驟（刷新邊一項 + 成唔成功 — 用戶要求）
        with open(os.path.join(_adir_rf, '.ai_control.steps') + '.tmp', 'w', encoding='utf-8') as _f:
            _jrf.dump([
                {'text': '開始重新整理', 'status': 'doing'},
                {'text': '掃描本機 EA 檔案', 'status': 'pending'},
                {'text': '清理殘留配對設定', 'status': 'pending'},
                {'text': '同步配對設定', 'status': 'pending'},
                {'text': '刷新本機運行狀態', 'status': 'pending'},
                {'text': '刷新 EA 倉庫', 'status': 'pending'},
                {'text': '完成重新整理', 'status': 'pending'},
            ], _f, ensure_ascii=False)
        # 🚨 2026-08-12 FIX：os.replace 移出 with block（WinError 32 — source 被自己開住）
        os.replace(os.path.join(_adir_rf, '.ai_control.steps') + '.tmp',
                   os.path.join(_adir_rf, '.ai_control.steps'))
    except Exception:
        pass
    # 🚨 2026-08-12：步驟 1 done + 步驟 2 doing（掃描本機 EA — 停留 0.8s 用戶見到）
    try:
        import time as _tw2
        _tw2.sleep(0.8)
        _st2 = _jrf.load(open(os.path.join(_adir_rf, '.ai_control.steps'), 'r', encoding='utf-8'))
        for _s2 in _st2:
            if _s2.get('text') == '開始重新整理':
                _s2['status'] = 'done'
            elif _s2.get('text') == '掃描本機 EA 檔案':
                _s2['status'] = 'doing'
        with open(os.path.join(_adir_rf, '.ai_control.steps'), 'w', encoding='utf-8') as _f:
            _jrf.dump(_st2, _f, ensure_ascii=False)
    except Exception:
        pass
    try:
        files = []
        # 🚨 2026-08-11：掃描本機 MT5Cloud_EA 實際檔案（.mq5/.ex5 — base name 集合 — 用嚟對比網頁 config）
        local_bases = set()
        try:
            data_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
            if os.path.isdir(data_dir):
                for d in os.listdir(data_dir):
                    exp = os.path.join(data_dir, d, 'MQL5', 'Experts')
                    for sub in (exp, os.path.join(exp, 'MT5Cloud_EA')):
                        if os.path.isdir(sub):
                            for fn in os.listdir(sub):
                                if fn.endswith(('.mq5', '.ex5')):
                                    local_bases.add(os.path.splitext(fn)[0])
        except Exception:
            pass
        # 🚨 自動清殘留 config：網頁已配對 + 本機完全冇檔案（冇 .mq5 冇 .ex5）→ 刪 config（電腦刪除後自動同步）
        # 🚨 2026-08-11 修：清所有用戶（唔止 current_user — 殘留喺其它帳號）
        try:
            # 🚨 獨立 sqlite3 連接（SQLAlchemy session 喺 request 內有隔離問題 — 直接 sqlite3 最穩陣）
            import sqlite3 as _sq
            _db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'mt5cloud.db')
            if os.path.isfile(_db_path):
                _conn = _sq.connect(_db_path)
                _cur = _conn.cursor()
                _cur.execute('SELECT id, ea_config FROM user')
                cleaned_total = 0
                for _rid, _cfg_str in _cur.fetchall():
                    cfg = json.loads(_cfg_str or '{}')
                    if not isinstance(cfg, dict):
                        continue
                    to_del = []
                    for key in list(cfg.keys()):
                        base = key
                        for suffix in ('_lot', '_magic', '_tf', '_status'):
                            if key.endswith(suffix):
                                base = key[:-len(suffix)]
                                break
                        if base and base not in local_bases and base != 'Controller' and not base.startswith('_'):
                            to_del.append(key)
                    if to_del:
                        for key in to_del:
                            del cfg[key]
                        _cur.execute('UPDATE user SET ea_config=? WHERE id=?', (json.dumps(cfg), _rid))
                        cleaned_total += len(to_del)
                if cleaned_total:
                    _conn.commit()
                    print(f"[refresh] 自動清理 {cleaned_total} 個殘留 config key（本機已刪除）", flush=True)
                _conn.close()
        except Exception as _ce:
            print(f"[refresh] 自動清理失敗: {_ce}", flush=True)
            pass
        if os.path.isdir(EA_LIBRARY_DIR):
            for f in sorted(os.listdir(EA_LIBRARY_DIR)):
                if f.endswith('.mq5'):
                    path = os.path.join(EA_LIBRARY_DIR, f)
                    files.append({"name": f, "size": f"{os.path.getsize(path)/1024:.1f} KB", "type": "official", "author": "Platform"})
        if os.path.isdir(COMMUNITY_EA_DIR):
            for f in sorted(os.listdir(COMMUNITY_EA_DIR)):
                if f.endswith('.mq5'):
                    path = os.path.join(COMMUNITY_EA_DIR, f)
                    files.append({"name": f, "size": f"{os.path.getsize(path)/1024:.1f} KB", "type": "community", "author": "Dev"})
        if current_user.is_authenticated:
            user_dir = os.path.join(UPLOAD_DIR, current_user.username)
            if os.path.isdir(user_dir):
                for f in sorted(os.listdir(user_dir)):
                    if f.endswith(('.mq5', '.ex5')):
                        path = os.path.join(user_dir, f)
                        files.append({"name": f, "size": f"{os.path.getsize(path)/1024:.1f} KB", "type": "user", "author": current_user.username})
        # 成功 → steps done（完成重新整理）
        try:
            with open(os.path.join(_adir_rf, '.ai_control.steps') + '.tmp', 'w', encoding='utf-8') as _f:
                _jrf.dump([
                    {'text': '重新整理配對庫 進行中…', 'status': 'done'},
                    {'text': '完成重新整理', 'status': 'done'},
                ], _f, ensure_ascii=False)
            # 🚨 2026-08-12 FIX：os.replace 移出 with block（WinError 32）
            os.replace(os.path.join(_adir_rf, '.ai_control.steps') + '.tmp',
                       os.path.join(_adir_rf, '.ai_control.steps'))
            _sf_show = os.path.join(_adir_rf, '.ai_control.show')
            if os.path.exists(_sf_show):
                os.remove(_sf_show)
        except Exception:
            pass
        # release（完成 — 網頁 modal 唔自動關 — 確定撳先關）
        try:
            if _cg is not None:
                _cg.release()
        except Exception:
            pass
        return jsonify({"success": True, "files": files, "count": len(files)})
    except Exception as e:
        # 失敗 → steps 顯示失敗原因（紅色）+ 確定（唔需要緊急停止）
        try:
            with open(os.path.join(_adir_rf, '.ai_control.steps') + '.tmp', 'w', encoding='utf-8') as _f:
                _jrf.dump([
                    {'text': '重新整理配對庫 進行中…', 'status': 'done'},
                    {'text': f'重新整理失敗（{str(e)[:80]}）', 'status': 'done'},
                ], _f, ensure_ascii=False)
            # 🚨 2026-08-12 FIX：os.replace 移出 with block（WinError 32）
            os.replace(os.path.join(_adir_rf, '.ai_control.steps') + '.tmp',
                       os.path.join(_adir_rf, '.ai_control.steps'))
            _sf_show = os.path.join(_adir_rf, '.ai_control.show')
            if os.path.exists(_sf_show):
                os.remove(_sf_show)
        except Exception:
            pass
        try:
            if _cg is not None:
                _cg.release()
        except Exception:
            pass
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/ea-library/dev-upload', methods=['POST'])
@login_required
def api_ea_dev_upload():
    """Developer 上傳 EA 去社群庫（所有人都可以用）"""
    if current_user.username != 'dev':
        return jsonify({"error": "Only dev account can upload to community library"}), 403
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    if not file.filename.endswith('.mq5'):
        return jsonify({"error": "Only .mq5 files allowed for community EA"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(COMMUNITY_EA_DIR, filename)
    file.save(filepath)

    return jsonify({
        "success": True,
        "filename": filename,
        "size": f"{os.path.getsize(filepath)/1024:.1f} KB",
        "type": "community"
    })



@app.route('/api/ea-library/<path:filename>')
def api_ea_download(filename):
    """下載 EA 檔案（先睇community→用戶→官方）"""
    # 先睇社群目錄
    community_path = os.path.join(COMMUNITY_EA_DIR, filename)
    if os.path.isfile(community_path):
        return send_from_directory(COMMUNITY_EA_DIR, filename)
    # 再睇用戶上傳目錄
    if current_user.is_authenticated:
        user_dir = os.path.join(UPLOAD_DIR, current_user.username)
        user_path = os.path.join(user_dir, filename)
        if os.path.isfile(user_path):
            return send_from_directory(user_dir, filename)
    # 最後睇官方目錄
    return send_from_directory(EA_LIBRARY_DIR, filename)

@app.route('/api/ea-library/remove-local/<filename>', methods=['POST'])
@login_required
def api_ea_remove_local(filename):
    """刪除本機 MT5 已安裝嘅 EA 檔案（MQL5/Experts/*.ex5 + *.mq5）"""
    # ⚠️ 系統檔案保護（Controller — 唔可以刪除）
    base_only = filename.split('.')[0]
    if base_only == 'Controller':
        return jsonify({"success": False, "error": "系統檔案（Controller）唔可以刪除"}), 403
    # ⚠️ 用戶要求（2026-08）：每次操作 MT5 相關嘢，先偵測 MT5 有冇開 — 冇就開返
    ensure_mt5_running()
    # 🚨 2026-08-10：網頁 delete 唔經 watcher → 要喺呢度寫 steps（唔會殘留上一個操作字眼 — 用戶投訴）
    try:
        import json as _jdel
        _adir_del = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
        with open(os.path.join(_adir_del, '.ai_control.show'), 'w', encoding='utf-8') as _f:
            _f.write(f'刪除 {base_only}')
        with open(os.path.join(_adir_del, '.ai_control.steps'), 'w', encoding='utf-8') as _f2:
            # 🚨 2026-08-12：詳細步驟（同 watcher 一致 — 活動記錄式 — 唔會 1 行覆蓋）
            _jdel.dump([
                {'text': f'開始刪除 {base_only}', 'status': 'doing'},
                {'text': '檢查圖表（是否有 EA 運行）', 'status': 'pending'},
                {'text': '移除圖表 EA', 'status': 'pending'},
                {'text': '刪除本機檔案（.mq5/.ex5）', 'status': 'pending'},
                {'text': '清理設定並釋放快捷鍵', 'status': 'pending'},
                {'text': '完成刪除', 'status': 'pending'},
            ], _f2, ensure_ascii=False)
            # 🚨 2026-08-12 FIX：直接寫 .steps（唔加 .tmp）— 唔可以 os.replace（會將 .steps rename 成 .st → 檔案消失 → 網頁閃）
    except Exception as e_del:
        print(f"[DEBUG] remove-local steps write failed: {e_del}")
    # 🚨 2026-08-12 FIX：寫完 steps 先停留 1.5 秒（視窗彈出 + 用戶見到「開始刪除進行中」先開始刪除 — 步驟唔會瞬間完成）
    try:
        import time as _tdel
        _tdel.sleep(1.5)
    except Exception:
        pass
    # 安全檢查：檔名只可以係字母數字底線（防 path traversal）
    # 🚨 2026-08-08：接受帶 .mq5/.ex5 副檔名（前端可能傳帶副檔名嘅名）
    import re as _re
    if not _re.fullmatch(r'[A-Za-z0-9_]+(\.[A-Za-z0-9]+)?', filename):
        return jsonify({"success": False, "error": "Invalid filename"}), 400

    experts_dirs = []
    data_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
    if os.path.isdir(data_dir):
        for d in os.listdir(data_dir):
            exp = os.path.join(data_dir, d, 'MQL5', 'Experts')
            if os.path.isdir(exp):
                experts_dirs.append(exp)

    removed = []
    for exp_dir in experts_dirs:
        # ⚠️ 2026-08：EA 喺 MT5Cloud_EA folder（web 配對）— 兩邊都搵（根目錄 + folder）
        search_dirs = [exp_dir, os.path.join(exp_dir, 'MT5Cloud_EA')]
        for search_dir in search_dirs:
            for ext in ('.ex5', '.mq5'):
                # 🚨 2026-08-08：用 base_only（filename 可能帶 .mq5 — 唔可以 filename+ext）
                target = os.path.join(search_dir, base_only + ext)
                if os.path.isfile(target):
                    try:
                        os.remove(target)
                        removed.append(target)
                    except Exception as e:
                        return jsonify({"success": False, "error": str(e)}), 500

    if removed:
        # 🚨 2026-08-10：網頁 delete 完成 → steps 全部 done（警告視窗顯示「完成刪除」+ 確定）
        # 🚨 2026-08-12：讀現有 steps（6 步）→ 全部 done（唔覆蓋 2 行 — 活動記錄式保持）
        try:
            import json as _jdel2
            _sf_del = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent', '.ai_control.steps')
            _del_steps = []
            try:
                if os.path.isfile(_sf_del):
                    _del_steps = _jdel2.load(open(_sf_del, 'r', encoding='utf-8'))
                    if not isinstance(_del_steps, list):
                        _del_steps = []
            except Exception:
                _del_steps = []
            # 🚨 2026-08-12 修：唔寫 done（DELETE config 會寫 pause_cmd → watcher 接手逐步 — 雙重寫 steps → 覆蓋 → 網頁彈嚟彈去）
            # 只係確保 steps 有內容（等 watcher 接手逐步完成）
            if not _del_steps:
                _del_steps = [{'text': f'開始刪除 {base_only}', 'status': 'doing'},
                              {'text': '檢查圖表（是否有 EA 運行）', 'status': 'pending'},
                              {'text': '移除圖表 EA', 'status': 'pending'},
                              {'text': '刪除本機檔案（.mq5/.ex5）', 'status': 'pending'},
                              {'text': '清理設定並釋放快捷鍵', 'status': 'pending'},
                              {'text': '完成刪除', 'status': 'pending'}]
            with open(_sf_del, 'w', encoding='utf-8') as _f:
                _jdel2.dump(_del_steps, _f, ensure_ascii=False)
        except Exception:
            pass
        # 寫「網頁刪除」標記 → watcher 偵測到刪除時知道來源（唔會誤判做電腦刪除）
        try:
            common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
            os.makedirs(common_files, exist_ok=True)
            flag_path = os.path.join(common_files, f'web_delete_{filename}.flag')
            with open(flag_path, 'w') as f:
                f.write('1')
        except Exception:
            pass
        log_activity('ea_delete', f'{filename} 已於網頁刪除（本機檔案已刪除）', ea=filename)
        return jsonify({"success": True, "removed": removed})
    return jsonify({"success": False, "error": "EA not found in local Experts dir"}), 404

@app.route('/api/ea-library/install-local/<filename>', methods=['POST'])
@login_required
def api_ea_install_local(filename):
    """將 EA 倉庫（官方/社群/用戶）嘅 EA 複製去本機 MT5 Experts 目錄 — 配對庫即刻見到
    聯動：EA 倉庫「移去配對」/ 上傳自己 EA 之後自動安裝落本機
    """
    import shutil as _sh
    import re as _re
    if not _re.fullmatch(r'[A-Za-z0-9_.]+', filename):
        return jsonify({"success": False, "error": "Invalid filename"}), 400

    # ⚠️ 用戶要求（2026-08）：每次操作 MT5 相關嘢，先偵測 MT5 有冇開 — 冇就開返
    ensure_mt5_running()

    # 0. 寫「處理中」log — 用戶想知系統有冇處理緊
    _base0 = os.path.splitext(filename)[0]
    log_activity('ea_install', f'{_base0} 配對處理中...', ea=_base0)
    # 🚨 2026-08-10：配對（install-local）警告視窗流程（同部署/刪除一致 — MODULE_INDEX 規範）
    try:
        import json as _jin
        _adir_in = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
        with open(os.path.join(_adir_in, '.ai_control.show'), 'w', encoding='utf-8') as _f:
            _f.write(f'配對 {_base0}')
        with open(os.path.join(_adir_in, '.ai_control.steps') + '.tmp', 'w', encoding='utf-8') as _f2:
            # 🚨 2026-08-12 FIX：配對詳細步驟（活動記錄式 — 同刪除一致 — 唔會同 watcher 編譯步驟唔對應）
            _jin.dump([
                {'text': f'開始配對 {_base0}', 'status': 'doing'},
                {'text': '複製檔案至本機（MT5Cloud_EA）', 'status': 'pending'},
                {'text': f'編譯 {_base0}.mq5 → .ex5', 'status': 'pending'},
                {'text': '完成配對', 'status': 'pending'},
            ], _f2, ensure_ascii=False)
        # 🚨 2026-08-12 FIX：os.replace 移出 with block（WinError 32 — source 被自己開住）
        os.replace(os.path.join(_adir_in, '.ai_control.steps') + '.tmp',
                   os.path.join(_adir_in, '.ai_control.steps'))
    except Exception as _ein_err:
        print(f"[DEBUG] install-local steps write failed: {_ein_err}", flush=True)

    # 🚨 2026-08-12 FIX：寫完 steps 先停留 1.5 秒（視窗彈出 + 用戶見到「開始配對進行中」先開始複製 — 步驟唔會瞬間完成）
    try:
        import time as _td
        _td.sleep(1.5)
    except Exception:
        pass

    # 1. 搵檔案喺邊個目錄（社群 → 用戶 → 官方）
    # ⚠️ filename 可能冇副檔名（前端傳 baseName）→ 自動試 .mq5 / .ex5
    src_path = None
    for d in (COMMUNITY_EA_DIR,
              os.path.join(UPLOAD_DIR, current_user.username),
              EA_LIBRARY_DIR):
        for cand in (filename, filename + '.mq5', filename + '.ex5'):
            p = os.path.join(d, cand)
            if os.path.isfile(p):
                src_path = p
                break
        if src_path:
            break
    if not src_path:
        return jsonify({"success": False, "error": f"{filename} 唔喺 EA 倉庫"}), 404

    # 2. 搵本機 MT5 Experts 目錄
    experts_dirs = []
    data_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
    if os.path.isdir(data_dir):
        for d in os.listdir(data_dir):
            exp = os.path.join(data_dir, d, 'MQL5', 'Experts')
            if os.path.isdir(exp):
                experts_dirs.append(exp)

    if not experts_dirs:
        return jsonify({"success": False, "error": "搵唔到本機 MT5 Experts 目錄"}), 500

    # 3. 複製去 MT5Cloud_EA folder（2026-08 用戶要求：所有 web 配對嘅 EA 集中一個 folder）
    installed = []
    compiled = False
    # ⚠️ 用 src_path 嘅 basename（保留副檔名）— filename 可能冇 .mq5（前端傳 baseName）
    # 唔可以淨用 filename — 會複製錯名 + 唔會寫 compile_cmd（endswith('.mq5') False）
    dest_name = os.path.basename(src_path)
    for exp_dir in experts_dirs:
        ea_folder = os.path.join(exp_dir, 'MT5Cloud_EA')
        try:
            os.makedirs(ea_folder, exist_ok=True)
        except Exception:
            pass
        target = os.path.join(ea_folder, dest_name)
        if os.path.abspath(target) == os.path.abspath(src_path):
            continue  # 已經喺度
        try:
            _sh.copy2(src_path, target)
            installed.append(target)
            # 🚨 2026-08-12 FIX：複製完成 → 更新 steps（開始配對 done + 複製檔案 done — 活動記錄式）
            try:
                import json as _jc3
                _adir_ic = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
                _sf_ic = os.path.join(_adir_ic, '.ai_control.steps')
                # 🚨 2026-08-12 FIX：複製完成前停留 1 秒（「複製進行中」顯示耐啲 — 用戶睇到工作過程 — 唔會瞬間完成）
                try:
                    import time as _td2
                    _td2.sleep(1)
                except Exception:
                    pass
                _cur_ic = []
                try:
                    if os.path.isfile(_sf_ic):
                        _cur_ic = _jc3.load(open(_sf_ic, 'r', encoding='utf-8'))
                        if not isinstance(_cur_ic, list):
                            _cur_ic = []
                except Exception:
                    _cur_ic = []
                for _s in _cur_ic:
                    if isinstance(_s, dict) and _s.get('text') in (f'開始配對 {_base0}', '複製檔案至本機（MT5Cloud_EA）'):
                        _s['status'] = 'done'
                # 🚨 2026-08-12 FIX：如果唔使編譯（.ex5 已存在且新過 .mq5）→ 即刻完成「編譯」+「完成配對」（唔停留 pending — 「兩步就停」根治）
                try:
                    _ex5_ic = os.path.join(ea_folder, os.path.splitext(dest_name)[0] + '.ex5')
                    _mq5_ic = target
                    _need_compile = dest_name.lower().endswith('.mq5') and (
                        not os.path.exists(_ex5_ic) or os.path.getmtime(_ex5_ic) < os.path.getmtime(_mq5_ic))
                    if not _need_compile:
                        for _s2 in _cur_ic:
                            if isinstance(_s2, dict) and _s2.get('text') in (f'編譯 {os.path.splitext(dest_name)[0]}.mq5 → .ex5', '完成配對'):
                                _s2['status'] = 'done'
                except Exception:
                    pass
                with open(_sf_ic, 'w', encoding='utf-8') as _f:
                    _jc3.dump(_cur_ic, _f, ensure_ascii=False)
            except Exception:
                pass
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

        # 3b. 如果係 .mq5 → 寫 compile 指令俾 watcher（watcher 有 desktop access 先 compile 到）
        if dest_name.lower().endswith('.mq5'):
            try:
                base = os.path.splitext(dest_name)[0]
                ex5_target = os.path.join(ea_folder, base + '.ex5')
                mq5_target = target
                if not os.path.exists(ex5_target) or os.path.getmtime(ex5_target) < os.path.getmtime(mq5_target):
                    # 寫 compile_cmd 俾 deploy_watcher（MetaEditor 需要 desktop access）
                    import time as _ct
                    common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
                    os.makedirs(common_files, exist_ok=True)
                    # 🚨 2026-08-12 FIX：寫前刪已有嘅同 EA compile_cmd（唔好排隊多個 → watcher 逐個處理 → 「自動再撈」）
                    try:
                        for _cfn in os.listdir(common_files):
                            if _cfn.startswith(f'compile_cmd_{base}_') and _cfn.endswith('.json'):
                                try:
                                    os.remove(os.path.join(common_files, _cfn))
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    cmd_path = os.path.join(common_files, f'compile_cmd_{base}_{int(_ct.time())}.json')
                    with open(cmd_path, 'w') as f:
                        json.dump({
                            'mq5_path': mq5_target,
                            'ex5_path': ex5_target,
                            'base': base,
                            'source': 'install-local'
                        }, f)
                    print(f"[install-local] compile 指令已排隊: {os.path.basename(cmd_path)}")
                # 寫「網頁加入」標記 → watcher 偵測到新增時知道來源
                try:
                    flag_path = os.path.join(common_files, f'web_add_{base}.flag')
                    with open(flag_path, 'w') as f:
                        f.write('1')
                except Exception:
                    pass
            except Exception as e:
                print(f"[install-local] compile 指令寫入失敗: {e}")
        break  # 只複製去第一個 Experts 目錄

    # 4. 寫 config（預設值 — 前端會覆蓋）
    try:
        config = json.loads(current_user.ea_config or '{}')
        base = os.path.splitext(filename)[0]
        config.setdefault(base, 'EURUSD')
        config.setdefault(base + '_tf', 'H1')
        config.setdefault(base + '_magic', '240701')
        config.setdefault(base + '_lot', 1.00)
        # 重新配對 → 由 _removed 移除（Bug #64：之前刪除過嘅 EA 重新配對後唔顯示）
        removed = config.get('_removed', [])
        if base in removed:
            removed.remove(base)
            config['_removed'] = removed
        current_user.ea_config = json.dumps(config)
        db.session.commit()
    except Exception as e:
        print(f"[install-local] config 寫入失敗: {e}")

    # 5. Double-check：等 compile 完成（最多 45 秒）— 唔可以假成功
    #    .mq5 需要 watcher compile → poll .ex5 出現
    compile_ok = None  # None=唔需要 compile, True=成功, False=失敗
    if filename.lower().endswith('.mq5'):
        compile_ok = False
        exp_dir = experts_dirs[0] if experts_dirs else None
        if exp_dir:
            # ⚠️ 2026-08：EA 喺 MT5Cloud_EA folder — 檢查 folder（+ 根目錄 fallback）
            ex5_target = None
            for _d in (os.path.join(exp_dir, 'MT5Cloud_EA'), exp_dir):
                _p = os.path.join(_d, os.path.splitext(filename)[0] + '.ex5')
                if os.path.isfile(_p):
                    ex5_target = _p
                    break
            if ex5_target is None:
                ex5_target = os.path.join(exp_dir, 'MT5Cloud_EA', os.path.splitext(filename)[0] + '.ex5')
            deadline = time.time() + 45
            while time.time() < deadline:
                # 檢查 compile_cmd 仲喺唔喺（watcher 處理完會刪）
                cmd_left = glob.glob(os.path.join(
                    os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files',
                    f'compile_cmd_{os.path.splitext(filename)[0]}_*.json'))
                _mq5_src = os.path.join(os.path.dirname(ex5_target), filename)
                if os.path.exists(ex5_target) and os.path.getmtime(ex5_target) >= os.path.getmtime(_mq5_src):
                    compile_ok = True
                    break
                if not cmd_left and not os.path.exists(ex5_target):
                    # compile cmd 已處理但 .ex5 未生成 → 失敗
                    compile_ok = False
                    break
                time.sleep(1.5)

    log_activity('ea_install', f'{os.path.splitext(filename)[0]} 已安裝到本機 MT5' + (
        '（compile 成功）' if compile_ok else '（compile 失敗）' if compile_ok is False and filename.lower().endswith('.mq5') else ''), ea=os.path.splitext(filename)[0])
    # 🎯 配對 → 分配快捷鍵（2026-08 用戶設計：添加時 set 快捷鍵 — 唔重複）
    try:
        _hk = assign_hotkey(os.path.splitext(filename)[0])
        if _hk:
            print(f"[install-local] {os.path.splitext(filename)[0]} 快捷鍵: {_hk}")
    except Exception:
        pass
    # 🚨 2026-08-10：配對完成 → steps（檢查 compile_ok — 失敗唔好話成功 — 用戶投訴）
    # 🚨 2026-08-10 修：compile_ok null（compile_cmd 已寫 — watcher 處理緊）→ 唔即刻寫「完成」— 等 watcher（唔好「假完成」→ 網頁兩個按鈕）
    if compile_ok is False:
        try:
            import json as _jin2
            _adir_in2 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
            _sf_in = os.path.join(_adir_in2, '.ai_control.steps')
            if os.path.isfile(_sf_in):
                with open(_sf_in + '.tmp', 'w', encoding='utf-8') as _f:
                    _jin2.dump([
                        {'text': f'配對 {os.path.splitext(filename)[0]} 進行中…', 'status': 'done'},
                        {'text': '配對失敗（compile 失敗）', 'status': 'done'},
                    ], _f, ensure_ascii=False)
                # 🚨 2026-08-12 FIX：os.replace 移出 with block（WinError 32）
                os.replace(_sf_in + '.tmp', _sf_in)
            # 🚨 清 show flag（完成 → 唔會再「不停彈」— 視窗保持顯示（確定 — 用戶撳先關））
            _sf_show = os.path.join(_adir_in2, '.ai_control.show')
            if os.path.exists(_sf_show):
                os.remove(_sf_show)
        except Exception:
            pass
    return jsonify({
        "success": True,
        "filename": filename,
        "base": os.path.splitext(filename)[0],
        "installed": installed,
        "compiled": bool(compile_ok),
        "compile_queued": filename.lower().endswith('.mq5'),
        "compile_ok": compile_ok,
        "message": f"{filename} 已安裝到本機 MT5" + (
            '（已編譯 ✅）' if compile_ok else '（⚠️ compile 失敗，MT5 可能未顯示 — 檢查 MetaEditor）' if compile_ok is False and filename.lower().endswith('.mq5') else '')
    })

def _mt5_hotkeys_ini():
    """搵 hotkeys.ini 路徑"""
    data_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
    if os.path.isdir(data_dir):
        for d in os.listdir(data_dir):
            p = os.path.join(data_dir, d, 'config', 'hotkeys.ini')
            if os.path.isfile(p):
                return p
    return None


def _read_hotkeys_ini():
    """讀 hotkeys.ini → (experts dict, indicators dict, raw lines)"""
    p = _mt5_hotkeys_ini()
    if not p:
        return {}, {}, []
    try:
        with open(p, 'rb') as f:
            raw = f.read()
        text = raw.decode('utf-16')
    except Exception:
        try:
            with open(p, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception:
            return {}, {}, []
    experts = {}
    indicators = {}
    section = None
    lines = text.splitlines()
    for line in lines:
        ls = line.strip().replace(chr(13), '')
        # ⚠️ hotkeys.ini 用尖括號 <experts>（唔係方括號）— 2026-08-06 bug 修復
        if (ls.startswith('[') and ls.endswith(']')) or (ls.startswith('<') and ls.endswith('>')):
            section = ls[1:-1]
        elif '=' in ls and section:
            k, v = ls.split('=', 1)
            if section == 'experts':
                experts[k] = v
            elif section == 'indicators':
                indicators[k] = v
    return experts, indicators, lines


def _write_hotkeys_ini(experts, indicators):
    """寫回 hotkeys.ini（UTF-16 LE — 用戶實測格式 2026-08-06：
    只有 <experts> section（冇 <indicators>）+ 乾淨 CRLF — MT5 先 load）"""
    p = _mt5_hotkeys_ini()
    if not p:
        return False
    lines = []
    if indicators:
        lines.append('<indicators>')
        for k, v in indicators.items():
            lines.append(f'{k}={v}')
        lines.append('</indicators>')
        lines.append('')
    lines.append('<experts>')
    for k, v in experts.items():
        lines.append(f'{k}={v}')
    lines.append('</experts>')
    text = '\r\n'.join(lines) + '\r\n'
    try:
        with open(p, 'wb') as f:
            f.write(text.encode('utf-16'))
        print(f"[hotkeys] 已寫入 {p}")
        return True
    except Exception as e:
        print(f"[hotkeys] 寫入失敗: {e}")
        return False


def _alloc_hotkey(experts):
    """分配下一個可用快捷鍵（Ctrl+1..9, Ctrl+0, Ctrl+Alt+1..9, Ctrl+Alt+0 — 唔重複）"""
    used = set(experts.values())
    candidates = [f'Ctrl+{i}' for i in range(1, 10)] + ['Ctrl+0'] + \
                 [f'Ctrl+Alt+{i}' for i in range(1, 10)] + ['Ctrl+Alt+0']
    for c in candidates:
        if c not in used:
            return c
    return None


def assign_hotkey(ea_name):
    """配對時分配快捷鍵 + 寫入 hotkeys.ini（MT5 立即認得 — 唔使 GUI）"""
    try:
        experts, indicators, _ = _read_hotkeys_ini()
        # 已存在就保留（唔重複分配）
        for k, v in experts.items():
            if ea_name in k:
                return v
        combo = _alloc_hotkey(experts)
        if not combo:
            print(f"[hotkeys] 冇可用快捷鍵（太多 EA）")
            return None
        # 路徑：Experts\MT5Cloud_EA\<EA>.ex5
        experts[f'Experts\\MT5Cloud_EA\\{ea_name}.ex5'] = combo
        if _write_hotkeys_ini(experts, indicators):
            print(f"[hotkeys] {ea_name} → {combo}")
            return combo
        return None
    except Exception as e:
        print(f"[hotkeys] assign 失敗: {e}")
        return None


def release_hotkey(ea_name):
    """刪除時移除快捷鍵（釋放位置）"""
    try:
        experts, indicators, _ = _read_hotkeys_ini()
        removed = False
        for k in list(experts.keys()):
            if ea_name in k:
                del experts[k]
                removed = True
        if removed:
            _write_hotkeys_ini(experts, indicators)
            print(f"[hotkeys] {ea_name} 快捷鍵已移除（位置釋放）")
        return removed
    except Exception as e:
        print(f"[hotkeys] release 失敗: {e}")
        return False


def get_hotkey(ea_name):
    """攞 EA 嘅快捷鍵（auto_attach 用 — 讀 hotkeys.ini 權威來源）"""
    try:
        experts, _, _ = _read_hotkeys_ini()
        for k, v in experts.items():
            if ea_name in k:
                return v
    except Exception:
        pass
    return None


def _mt5_start_time():
    """MT5 進程啟動時間（epoch）— 用 wmic"""
    import subprocess as _sp
    try:
        out = _sp.run('wmic process where "name=terminal64.exe" get CreationDate /value',
                      shell=True, capture_output=True)
        for line in out.stdout.decode('utf-8', errors='replace').splitlines():
            if 'CreationDate' in line:
                v = line.split('=')[1].strip()
                # YYYYMMDDHHMMSS.mmmmmm+000
                import datetime as _dt
                return _dt.datetime.strptime(v[:14], '%Y%m%d%H%M%S').timestamp()
    except Exception:
        pass
    return 0


def _hotkeys_need_reload():
    """hotkeys.ini 有冇新過 MT5 啟動（有 = 快捷鍵未 load — 要重啟 MT5）"""
    try:
        p = _mt5_hotkeys_ini()
        if not p or not os.path.isfile(p):
            return False
        ini_mtime = os.path.getmtime(p)
        mt5_start = _mt5_start_time()
        # MT5 未開 → 唔需要 reload（開嗰陣會 load）
        if mt5_start == 0:
            return False
        return ini_mtime > mt5_start + 5
    except Exception:
        return False


def _restart_mt5():
    """重啟 MT5（關 → 開 — reload hotkeys.ini）— 2026-08 用戶實測：快捷鍵要重啟先 load
    🚨 2026-08-10：重啟期間顯示警告視窗（MT5 關閉都有 — 用戶要知道操作緊）"""
    try:
        import subprocess as _sp
        import json as _j
        # 警告視窗（電腦版 — 寫 flag）— 🚨 2026-08-12 FIX：累積模式（唔覆蓋現有 steps — 部署前重啟 MT5 唔會洗走部署流程）+ 完成後唔刪 steps（spec：steps 永不刪除）
        try:
            _ad = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
            with open(os.path.join(_ad, '.ai_control.show'), 'w', encoding='utf-8') as _f:
                _f.write('🔄 重啟 MT5 中（載入快捷鍵）— 請稍候約 1 分鐘')
            _sf_rt = os.path.join(_ad, '.ai_control.steps')
            _cur_rt = []
            try:
                if os.path.isfile(_sf_rt):
                    _cur_rt = _j.load(open(_sf_rt, 'r', encoding='utf-8'))
                    if not isinstance(_cur_rt, list):
                        _cur_rt = []
            except Exception:
                _cur_rt = []
            _cur_rt = [s for s in _cur_rt if isinstance(s, dict) and s.get('text') != '等待操作開始…']
            # append 重啟 MT5 3 步（同名更新）
            for _rstep in [{"text": "關閉 MT5", "status": "doing"},
                           {"text": "載入快捷鍵設定", "status": "pending"},
                           {"text": "重新啟動 MT5", "status": "pending"}]:
                _found = False
                for _s in _cur_rt:
                    if _s.get('text') == _rstep['text']:
                        _s['status'] = _rstep['status']
                        _found = True
                        break
                if not _found:
                    _cur_rt.append(_rstep)
            with open(_sf_rt, 'w', encoding='utf-8') as _f2:
                _j.dump(_cur_rt, _f2, ensure_ascii=False)
        except Exception:
            pass
        _sp.run('taskkill -f -im terminal64.exe', shell=True, capture_output=True)
        time.sleep(3)
        mt5_exe = os.environ.get('MT5_EXE_PATH', r'C:\Program Files\MetaTrader 5\terminal64.exe')
        _sp.Popen([mt5_exe])
        time.sleep(55)
        # 🚨 2026-08-12 FIX：完成 → 唔刪除 steps（spec：steps 永不刪除 — 刪除 → 網頁空白/彈）— 只更新 3 步全部 done
        try:
            _ad = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
            _sf_rt2 = os.path.join(_ad, '.ai_control.steps')
            _cur_rt2 = []
            try:
                if os.path.isfile(_sf_rt2):
                    _cur_rt2 = _j.load(open(_sf_rt2, 'r', encoding='utf-8'))
                    if not isinstance(_cur_rt2, list):
                        _cur_rt2 = []
            except Exception:
                _cur_rt2 = []
            for _s in _cur_rt2:
                if isinstance(_s, dict) and _s.get('text') in ('關閉 MT5', '載入快捷鍵設定', '重新啟動 MT5'):
                    _s['status'] = 'done'
            if _cur_rt2:
                with open(_sf_rt2, 'w', encoding='utf-8') as _f:
                    _j.dump(_cur_rt2, _f, ensure_ascii=False)
        except Exception:
            pass
        print("[hotkeys] MT5 已重啟（reload 快捷鍵）")
        return True
    except Exception as e:
        print(f"[hotkeys] 重啟 MT5 失敗: {e}")
        return False


@app.route('/api/ea-library/retry-compile/<name>', methods=['POST'])
@login_required

def ensure_hotkey_for_ea(ea_name):
    """部署前確保 EA 有快捷鍵（2026-08：MT5 重啟會覆寫 hotkeys.ini — 未經 GUI 設定嘅新 EA 快捷鍵會冇）
    冇快捷鍵 → 分配 + 關 MT5 → 寫 → 開（reload）→ 返回 True（已就緒）"""
    try:
        experts, indicators, _ = _read_hotkeys_ini()
        # 已有快捷鍵
        for k, v in experts.items():
            if ea_name in k:
                return True
        # 冇 → 分配（🚨 2026-08-10 優化：唔同步 reload — 改「部署前一次過 reload」（watcher/auto_attach 檢查 mtime — 唔好每次部署卡 105 秒））
        combo = _alloc_hotkey(experts)
        if not combo:
            return False
        experts[f'Experts\\MT5Cloud_EA\\{ea_name}.ex5'] = combo
        if _write_hotkeys_ini(experts, indicators):
            print(f"[hotkeys] {ea_name} → {combo}（已分配 — 部署時 reload）")
            return True
        return False
    except Exception as e:
        print(f"[hotkeys] ensure 失敗: {e}")
        return False



def api_ea_retry_compile(name):
    """重試編譯（MetaEditor GUI compile — watcher 有 desktop access）
    手動重試 compile：檢查 .mq5 喺本機 → 重新寫 compile_cmd → 等 compile 完成（double-check）
    用喺：之前 compile 失敗（假成功）之後，用戶撳「重試」再觸發
    """
    import re as _re
    import time as _ct
    if not _re.fullmatch(r'[A-Za-z0-9_]+', name):
        return jsonify({"success": False, "error": "Invalid name"}), 400

    # ⚠️ 用戶要求（2026-08）：每次操作 MT5 相關嘢，先偵測 MT5 有冇開 — 冇就開返
    ensure_mt5_running()

    # 1. 搵本機 .mq5
    data_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
    mq5_path = None
    exp_dir = None
    if os.path.isdir(data_dir):
        for d in os.listdir(data_dir):
            exp = os.path.join(data_dir, d, 'MQL5', 'Experts')
            if os.path.isdir(exp):
                candidate = os.path.join(exp, name + '.mq5')
                if os.path.isfile(candidate):
                    mq5_path = candidate
                    exp_dir = exp
                    break

    if not mq5_path:
        return jsonify({"success": False, "error": f"{name}.mq5 唔喺本機 MT5 Experts 目錄"}), 404

    ex5_path = os.path.join(exp_dir, name + '.ex5')
    if os.path.exists(ex5_path) and os.path.getmtime(ex5_path) > os.path.getmtime(mq5_path):
        return jsonify({"success": True, "compile_ok": True, "message": f"{name}.ex5 已係最新，唔使重編"})

    # 2. 重新寫 compile_cmd
    common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
    os.makedirs(common_files, exist_ok=True)
    cmd_path = os.path.join(common_files, f'compile_cmd_{name}_{int(_ct.time())}.json')
    with open(cmd_path, 'w') as f:
        json.dump({
            'mq5_path': mq5_path,
            'ex5_path': ex5_path,
            'base': name,
            'source': 'retry-compile'
        }, f)
    print(f"[retry-compile] compile 指令已重新排隊: {os.path.basename(cmd_path)}")

    # 3. Double-check：等 compile 完成（最多 45 秒）
    compile_ok = False
    deadline = time.time() + 45
    while time.time() < deadline:
        cmd_left = glob.glob(os.path.join(common_files, f'compile_cmd_{name}_*.json'))
        if os.path.exists(ex5_path) and os.path.getmtime(ex5_path) > os.path.getmtime(mq5_path):
            compile_ok = True
            break
        if not cmd_left:
            compile_ok = False  # compile cmd 已處理但 .ex5 未生成 → 失敗
            break
        time.sleep(1.5)

    log_activity('ea_retry_compile', f'{name} 重試 compile ' + ('成功' if compile_ok else '失敗'), ea=name)
    return jsonify({
        "success": True,
        "compile_ok": compile_ok,
        "message": f"{name} 重試 compile " + ('成功 ✅' if compile_ok else '失敗 — 檢查源碼或 MetaEditor')
    })


@app.route('/api/ea-library/upload', methods=['POST'])
@login_required
def api_ea_upload():
    """用戶上傳自己嘅 EA（只有自己睇到）+ 自動安裝落本機 MT5（聯動配對庫）"""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    if not file.filename.endswith(('.mq5', '.ex5')):
        return jsonify({"error": "Only .mq5 and .ex5 files allowed"}), 400

    # 寫「處理中」log — 用戶想知系統有冇處理緊
    _ubase = os.path.splitext(file.filename)[0]
    log_activity('ea_upload', f'{_ubase} 上傳處理中...', ea=_ubase)

    # 儲存去用戶專屬目錄
    user_dir = os.path.join(UPLOAD_DIR, current_user.username)
    os.makedirs(user_dir, exist_ok=True)
    filename = secure_filename(file.filename)
    filepath = os.path.join(user_dir, filename)
    file.save(filepath)

    # 聯動：自動安裝落本機 MT5 Experts 目錄（配對庫即刻見到）
    import shutil as _sh
    import re as _re
    install_result = None
    compiled = False
    if _re.fullmatch(r'[A-Za-z0-9_.]+', filename):
        data_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        if os.path.isdir(data_dir):
            for d in os.listdir(data_dir):
                exp = os.path.join(data_dir, d, 'MQL5', 'Experts')
                if os.path.isdir(exp):
                    try:
                        target = os.path.join(exp, filename)
                        if os.path.abspath(target) != os.path.abspath(filepath):
                            _sh.copy2(filepath, target)
                            install_result = target
                        # .mq5 → 寫 compile 指令俾 watcher（MetaEditor 需要 desktop access）
                        if filename.lower().endswith('.mq5'):
                            base = os.path.splitext(filename)[0]
                            ex5_target = os.path.join(exp, base + '.ex5')
                            if not os.path.exists(ex5_target) or os.path.getmtime(ex5_target) < os.path.getmtime(target):
                                import time as _ct
                                common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
                                os.makedirs(common_files, exist_ok=True)
                                cmd_path = os.path.join(common_files, f'compile_cmd_{base}_{int(_ct.time())}.json')
                                with open(cmd_path, 'w') as f:
                                    json.dump({
                                        'mq5_path': target,
                                        'ex5_path': ex5_target,
                                        'base': base,
                                        'source': 'upload'
                                    }, f)
                                print(f"[upload] compile 指令已排隊: {os.path.basename(cmd_path)}")
                            # 寫「網頁加入」標記 → watcher 偵測到新增時知道來源
                            try:
                                common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
                                flag_path = os.path.join(common_files, f'web_add_{base}.flag')
                                with open(flag_path, 'w') as f:
                                    f.write('1')
                            except Exception:
                                pass
                        break
                    except Exception:
                        pass

    # 寫 config（如果係 .mq5/.ex5 EA）
    base = os.path.splitext(filename)[0]
    try:
        config = json.loads(current_user.ea_config or '{}')
        config.setdefault(base, 'EURUSD')
        config.setdefault(base + '_tf', 'H1')
        config.setdefault(base + '_magic', '240701')
        config.setdefault(base + '_lot', 1.00)
        # 重新配對 → 由 _removed 移除（Bug #64）
        removed = config.get('_removed', [])
        if base in removed:
            removed.remove(base)
            config['_removed'] = removed
        current_user.ea_config = json.dumps(config)
        db.session.commit()
    except Exception as e:
        print(f"[upload] config 寫入失敗: {e}")

    # Double-check：等 compile 完成（最多 45 秒）— 唔可以假成功
    compile_ok = None
    if filename.lower().endswith('.mq5'):
        compile_ok = False
        data_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        ex5_target = None
        if os.path.isdir(data_dir):
            for d in os.listdir(data_dir):
                exp = os.path.join(data_dir, d, 'MQL5', 'Experts')
                if os.path.isdir(exp):
                    ex5_target = os.path.join(exp, base + '.ex5')
                    break
        if ex5_target:
            deadline = time.time() + 45
            while time.time() < deadline:
                cmd_left = glob.glob(os.path.join(
                    os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files',
                    f'compile_cmd_{base}_*.json'))
                if os.path.exists(ex5_target):
                    compile_ok = True
                    break
                if not cmd_left:
                    compile_ok = False  # compile cmd 已處理但 .ex5 未生成 → 失敗
                    break
                time.sleep(1.5)

    log_activity('ea_upload', f'{base} 上傳 + 安裝到本機 MT5' + (
        '（compile 成功）' if compile_ok else '（compile 失敗）' if compile_ok is False and filename.lower().endswith('.mq5') else ''), ea=base)
    return jsonify({
        "success": True,
        "filename": filename,
        "size": f"{os.path.getsize(filepath)/1024:.1f} KB",
        "installed_local": bool(install_result),
        "compiled": bool(compile_ok),
        "compile_ok": compile_ok,
        "message": f"{base} 已上傳 + 安裝到本機 MT5" + (
            '（已編譯 ✅）' if compile_ok else '（⚠️ compile 失敗，MT5 可能未顯示）' if compile_ok is False and filename.lower().endswith('.mq5') else '')
    })


@app.route('/api/agent-download')
def api_agent_download():
    """下載 Windows Agent 安裝檔"""
    agent_dir = os.path.join(os.path.dirname(__file__), '..', 'agent')
    return send_from_directory(agent_dir, 'install_agent.bat')

@app.route('/api/agent-py')
def api_agent_py():
    """下載 agent.py"""
    agent_dir = os.path.join(os.path.dirname(__file__), '..', 'agent')
    return send_from_directory(agent_dir, 'agent.py')

# === WebSocket: Agent ===
@socketio.on('connect')
def handle_connect():
    print(f"[WS] Connected: {request.sid}")

# Debounce auto-send — avoid re-sending EA config on rapid reconnections
_last_config_send = {}

@socketio.on('agent_register')
def handle_register(data):
    agent = Agent.query.filter_by(agent_id=data.get('agent_id')).first()
    if agent:
        join_room(agent.agent_id)
        agent.status = 'connected'
        agent.last_seen = datetime.utcnow()
        db.session.commit()
        emit('registered', {"status":"ok"})
        # 自動推送 EA 配置俾 Agent（debounce: 每 60 秒最多一次）
        user = agent.user
        if user and user.ea_config and user.ea_config != '{}':
            try:
                import time as _t
                now = _t.time()
                last = _last_config_send.get(agent.agent_id, 0)
                if now - last < 60:
                    print(f"[WS] Skip auto-send (debounce): {agent.agent_id} ({now-last:.0f}s ago)")
                    return
                _last_config_send[agent.agent_id] = now
                
                config = json.loads(user.ea_config)
                ea_names = [k for k in config.keys() if not k.startswith('_') and not k.endswith('_tf') and not k.endswith('_lot') and not k.endswith('_magic') and not k.endswith('_status') and k not in ('_default_lot','_removed')]
                if ea_names:
                    emit('install_ea_command', {
                        "ea_name": "all",
                        "ea_list": ea_names,
                        "download_url": f"{request.host_url}api/ea-library/",
                        "ea_config": config
                    }, room=agent.agent_id)
                    print(f"[WS] Auto-sent EA config to agent {agent.agent_id}: {len(ea_names)} EAs")
            except:
                pass

@socketio.on('agent_sync')
def handle_sync(data):
    agent = Agent.query.filter_by(agent_id=data.get('agent_id')).first()
    if agent:
        agent.account_info = json.dumps(data.get('account',{}))
        agent.positions = json.dumps(data.get('positions',[]))
        agent.deals = json.dumps(data.get('deals',[]))
        agent.ea_heartbeats = json.dumps(data.get('heartbeats', {}))
        agent.last_seen = datetime.utcnow()
        agent.status = data.get('status','connected')
        db.session.commit()
        emit('agent_update', {}, room=agent.agent_id)

@socketio.on('agent_install_ea')
def handle_install_ea(data):
    """用戶㩒 Install EA，通知 Agent 去下載同安裝"""
    agent = Agent.query.filter_by(agent_id=data.get('agent_id')).first()
    if agent:
        ea_name = data.get('ea_name')
        ea_list = data.get('ea_list', [])
        # Build download URL
        if ea_name == 'all' and ea_list:
            download_url = f"{request.host_url}api/ea-library/"
        else:
            download_url = f"{request.host_url}api/ea-library/{ea_name}"
        emit('install_ea_command', {
            "ea_name": ea_name,
            "ea_list": ea_list,
            "download_url": download_url,
            "ea_config": json.loads(agent.user.ea_config or '{}')
        }, room=agent.agent_id)
        emit('install_result', {"status": "sent", "ea": ea_name})

@socketio.on('install_result')
def handle_install_result(data):
    """Agent 回報安裝結果，forward 俾所有 browser"""
    print(f"[WS] Install result: {data}")
    emit('install_result', data, broadcast=True, include_self=False)

@socketio.on('deploy_ea')
def handle_deploy_ea(data):
    """接收 Dashboard 嘅 deploy 指令"""
    agent = Agent.query.filter_by(agent_id=data.get('agent_id')).first()
    if agent:
        # 直接 Socket.IO 發俾 Agent（更快更可靠）
        print(f"[WS] Forwarding deploy to {agent.agent_id}: {data.get('ea_name')} -> {data.get('symbol')}")
        socketio.emit('deploy_ea', data, room=agent.agent_id)
        # 亦寫入 DB（fallback）
        agent.deploy_queue = json.dumps({
            "ea_name": data.get('ea_name'),
            "symbol": data.get('symbol'),
            "tf": data.get('tf'),
            "magic": data.get('magic'),
            "lot": data.get('lot')
        })
        db.session.commit()
        emit('install_result', {"status": "sent", "ea": data.get('ea_name')})

@app.route('/api/deploy', methods=['POST'])
@login_required
def api_deploy():
    """HTTP deploy (唔靠 Socket.IO，更可靠)"""
    # 🚨 2026-08-12 FIX：防重複部署（同一 EA 30 秒內唔可以再 deploy — 前端 double-click / 重複觸發 → 兩個 deploy_cmd → 「完成又彈又執行」）
    global _last_deploy_time
    try:
        _now_dp = time.time()
        if _last_deploy_time.get(ea_name_cached := request.json.get('ea_name', ''), 0) and _now_dp - _last_deploy_time.get(ea_name_cached, 0) < 30:
            return jsonify({"success": False, "error": f"{ea_name_cached} 30 秒內已部署過（防重複）"}), 429
    except Exception:
        pass
    # ⚠️ 用戶要求（2026-08）：每次操作 MT5 相關嘢，先偵測 MT5 有冇開 — 冇就開返
    ensure_mt5_running()
    data = request.json
    ea_name = data.get('ea_name', '')
    symbol = data.get('symbol', 'EURUSD')
    tf = data.get('tf', 'H1')
    magic = data.get('magic', '240701')
    lot = data.get('lot', '1.00')
    _last_deploy_time[ea_name] = time.time()
    
    # Save EA config first
    config = json.loads(current_user.ea_config or '{}')
    config[ea_name] = symbol
    config[f'{ea_name}_tf'] = tf
    config[f'{ea_name}_magic'] = str(magic)
    config[f'{ea_name}_lot'] = float(lot)
    current_user.ea_config = json.dumps(config)
    
    # ⚠️ Controller 部署（今日版本功能）：心跳 running → 已運行；否則手動提示（+ 標記 → watcher 自動確定）
    if ea_name == 'Controller':
        try:
            sf = os.path.join(common_files, 'state_controller.json')
            if os.path.isfile(sf):
                with open(sf, 'r', encoding='utf-8') as _f:
                    _sd = json.load(_f)
                if _sd.get('status') == 'running' and int(time.time()) - int(_sd.get('ts', 0)) < 30:
                    return jsonify({"success": True, "message": "✅ Controller 已運行中（系統中樞正常）"})
        except Exception:
            pass
        log_activity('deploy', f'Controller 首次部署：請手動 double-click（MT5Cloud folder）', ea='Controller')
        try:
            agent_dir = os.path.join(os.path.dirname(__file__), '..', 'agent')
            with open(os.path.join(agent_dir, '.manual_deploy_pending'), 'w', encoding='utf-8') as _f:
                json.dump({'ea': 'Controller', 'ts': time.time()}, _f)
        except Exception:
            pass
        return jsonify({
            "success": True,
            "manual_action": True,
            "message": "請手動完成首次部署（1 秒）：MT5 導航 → EA交易 → MT5Cloud → 雙擊 Controller。確定會自動撳！"
        })

    # 🎯 快捷鍵確保（2026-08：MT5 重啟會覆寫 hotkeys.ini — 未經 GUI 嘅快捷鍵會冇）
    # 部署前檢查 EA 有冇快捷鍵 — 冇就分配 + 重啟 MT5 reload
    try:
        ensure_hotkey_for_ea(ea_name)
    except Exception:
        pass

    # 🚨 2026-08-12 FIX：即刻寫 SHOW_FLAG + steps（部署 XXX doing）— 唔好等 auto_attach（watcher poll 3 秒 + 啟動）
    # （否則視窗顯示舊任務殘留 steps → 1 秒後先變新 — 用戶投訴「一開始顯示舊步驟」）
    try:
        import json as _jdp
        _adir_dp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
        os.makedirs(_adir_dp, exist_ok=True)
        with open(os.path.join(_adir_dp, '.ai_control.show'), 'w', encoding='utf-8') as _f:
            _f.write(f'部署 {ea_name}')
        with open(os.path.join(_adir_dp, '.ai_control.steps'), 'w', encoding='utf-8') as _f:
            _jdp.dump([
                {'text': f'部署 {ea_name}（{symbol.upper()}）', 'status': 'doing'},
                {'text': f'建立新圖表（{symbol.upper()}）', 'status': 'pending'},
                {'text': f'附加 {ea_name}', 'status': 'pending'},
                {'text': '驗證運行狀態', 'status': 'pending'},
            ], _f, ensure_ascii=False)
    except Exception:
        pass

    # Write deploy command file (watcher will pick it up)
    import time as _wt
    common_files = os.path.join(os.environ.get('APPDATA', ''),
                                 'MetaQuotes', 'Terminal', 'Common', 'Files')
    os.makedirs(common_files, exist_ok=True)

    # ⚠️ 控制層方案（CONTROL_LAYER_DESIGN.md）：如果 Controller EA 心跳 running →
    # 直接寫 ctrl_controller.json（Controller 用 ChartApplyTemplate 附加 — 唔使 GUI / auto_attach）
    # 需要 template 存在（generate_template 寫 .tpl）
    controller_alive = False
    try:
        sf = os.path.join(common_files, 'state_controller.json')
        if os.path.isfile(sf):
            with open(sf, 'r', encoding='utf-8') as _f:
                _sd = json.load(_f)
            if _sd.get('status') == 'running' and int(time.time()) - int(_sd.get('ts', 0)) < 30:
                controller_alive = True
    except Exception:
        pass

    if controller_alive:
        try:
            # 1. 生成 template（<EA>_<SYMBOL>_<TF>.tpl — Controller ChartApplyTemplate 需要）
            try:
                import sys as _sys
                _sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agent'))
                from auto_attach import generate_template
                tpl_path = generate_template(ea_name, symbol, tf, {'Magic': str(magic), 'Lot': str(lot)})
                print(f"[API] Controller 模式 template: {tpl_path}")
            except Exception as _te:
                print(f"[API] ⚠️ generate_template 失敗: {_te}")
            # 2. 寫 ctrl_controller.json（Controller 執行 attach）
            cmd_path = os.path.join(common_files, 'ctrl_controller.json')
            with open(cmd_path, 'w', encoding='utf-8') as f:
                json.dump({'cmd': 'attach', 'ea': ea_name, 'symbol': symbol, 'tf': tf}, f, ensure_ascii=False)
            print(f"[API] Deploy(Controller): {ea_name} -> {symbol} {tf} (ctrl_controller.json written)")
        except Exception as _ce:
            print(f"[API] ⚠️ Controller deploy 失敗，fallback deploy_cmd: {_ce}")
            cmd_path = os.path.join(common_files, f'deploy_cmd_{ea_name}_{int(_wt.time())}.json')
            with open(cmd_path, 'w') as f:
                json.dump({
                    'ea_name': ea_name,
                    'symbol': symbol,
                    'tf': tf,
                    'magic': str(magic),
                    'lot': str(lot),
                    'timestamp': _wt.strftime('%Y-%m-%dT%H:%M:%S'),
                    'source': 'api_deploy'
                }, f)
    else:
        # 照舊：deploy_cmd → watcher → auto_attach（Controller 未運行 / 未部署）
        cmd_path = os.path.join(common_files, f'deploy_cmd_{ea_name}_{int(_wt.time())}.json')
        with open(cmd_path, 'w') as f:
            json.dump({
                'ea_name': ea_name,
                'symbol': symbol,
                'tf': tf,
                'magic': str(magic),
                'lot': str(lot),
                'timestamp': _wt.strftime('%Y-%m-%dT%H:%M:%S'),
                'source': 'api_deploy'
            }, f)
    
    db.session.commit()
    print(f"[API] Deploy: {ea_name} -> {symbol} {tf} (command file written)")
    log_activity('deploy', f'{ea_name} 部署 → {symbol} {tf}', ea=ea_name)
    
    return jsonify({"success": True, "message": f"🚀 Deploying {ea_name} -> {symbol} {tf}"})

@app.route('/api/bind-account', methods=['POST'])
@login_required
def api_bind_account():
    """綁定當前 MT5 account 到用戶"""
    data = request.json
    action = data.get('action', 'bind')
    
    if action == 'bind':
        # Get current MT5 account from cache
        with _auto_trade_lock:
            acc = _auto_trade_cache.get("account_info", {})
        login = acc.get('login', '')
        if not login:
            return jsonify({"success": False, "error": "MT5 未登入或無法獲取 account info"})
        current_user.bound_account = login
        db.session.commit()
        return jsonify({"success": True, "bound_account": login})
    
    elif action == 'unbind':
        current_user.bound_account = ''
        db.session.commit()
        return jsonify({"success": True, "message": "已解除綁定"})
    
    return jsonify({"success": False, "error": "Unknown action"})

@app.route('/health')
def health():
    """健康檢查 — 單實例守衛 + 監控用"""
    return jsonify({"ok": True, "port": int(os.environ.get('PORT', 5000))})

@app.route('/api/verify-mt5', methods=['POST'])
def api_verify_mt5():
    """Verify MT5 account (using cached account info)"""
    data = request.json
    expected = data.get('account', '').strip()
    password = data.get('password', '').strip()
    
    with _auto_trade_lock:
        cached_acc = _auto_trade_cache.get("account_info", {})
    local_login = str(cached_acc.get('login', ''))
    
    if not expected:
        return jsonify({"match": False, "error": "No account provided"})
    if not local_login:
        return jsonify({"match": False, "error": "MT5 not ready - try refreshing dashboard first", "local_account": ""})
    
    match = (local_login == expected)
    return jsonify({"match": match, "local_account": local_login})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))

    # ─── 單實例守衛：如果 :port 已經有 healthy server，退出唔重複啟動 ───
    # 解決 Hermes auto-restart 造成多個 server duplicates 搶 port 嘅問題
    import socket as _sock
    import urllib.request as _urllib
    def _port_has_healthy_server(port):
        try:
            with _urllib.urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    if _port_has_healthy_server(port):
        print(f"⚠️  :{port} 已經有 healthy server 運行緊，呢個 instance 退出（單實例守衛）")
        sys.exit(0)

    # Bind 測試：確保我哋先霸到 port（防止 race condition）
    # ⚠️ 唔可以用 SO_REUSEADDR — Windows 上呢個 flag 允許兩個 process bind 同一 port（之前 duplicates 根源）
    try:
        _probe = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        _probe.bind(('0.0.0.0', port))
        _probe.close()
    except OSError:
        print(f"⚠️  :{port} 被佔用，呢個 instance 退出")
        sys.exit(0)

    print(f"☁️  MT5 Cloud Server :{port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=True, use_reloader=False)