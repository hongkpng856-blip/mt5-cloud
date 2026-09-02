# Tradotcom — Full Platform Server
# 公開網站，每人有自己的 EA 配對 + 分析 + Correlation

# 🚨 2026-08-31 FIX（#148 Server 靜默 crash — MSVCP140.dll 0xc0000005）：
# eventlet async_mode 需要 monkey_patch()（將 blocking I/O 變 green thread）
# 冇 patch → eventlet hub + 原生 thread（彈返監察 threading.Thread）併發 → 底層 C 擴展崩潰
# [WARN] monkey_patch 必須喺 import socketio/flask 之前（否則 patch 唔到佢哋用嘅 socket）
import os
if os.environ.get('RENDER', ''):
    try:
        import eventlet
        eventlet.monkey_patch()
    except Exception:
        pass
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
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

def _bounce_back_watchdog():
    """[ALERT] 2026-08-15：彈返定期監察（background thread — 每 30 秒）
    user：配對庫彈出「F 字頭」等 EA（localfile彈返 — 環境層面 — 源頭未明）
    → 定期 check Experts：非 config EA + ctime 新（<180 秒）→ 自動delete（彈返immediately清 — 配對庫唔會見到）+ 記錄 bounce_back_log（追蹤源頭）"""
    import time as _tbb2, threading as _th2
    def _run():
        while True:
            try:
                import sqlite3 as _sq2, json as _j2, os as _o2, glob as _g2
                _tbb2.sleep(30)
                # 搵 Experts + Scripts 根dir（都監察 — script 類 EA 都會彈返）
                _tdir2 = _o2.path.join(_o2.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
                _ea_dirs2 = []
                for _d2 in _o2.listdir(_tdir2) if _o2.path.isdir(_tdir2) else []:
                    _pe2 = _o2.path.join(_tdir2, _d2, 'MQL5', 'Experts')
                    if _o2.path.isdir(_pe2):
                        _ea_dirs2.append(_pe2)
                    _ps2 = _o2.path.join(_tdir2, _d2, 'MQL5', 'Scripts')
                    if _o2.path.isdir(_ps2):
                        _ea_dirs2.append(_ps2)
                if not _ea_dirs2:
                    continue
                # 讀 config（EA 名集合）— [ALERT] 2026-08-27 FIX：全部 user 嘅 config（multi-user — agent 模式deploy唔係 dev）
                _cfg2 = set()
                try:
                    _db2 = _o2.path.join(_o2.path.dirname(_o2.path.abspath(__file__)), '..', 'instance', 'mt5cloud.db')
                    _db2 = _o2.path.abspath(_db2)
                    _conn2 = _sq2.connect(_db2)
                    for _row2 in _conn2.execute("SELECT ea_config FROM user").fetchall():
                        try:
                            _c2 = _j2.loads(_row2[0] or '{}')
                            for _k2 in _c2:
                                if not _k2.startswith('_') and not _k2.endswith(('_tf', '_lot', '_magic', '_status')):
                                    _cfg2.add(_k2)
                        except Exception:
                            pass
                    _conn2.close()
                except Exception:
                    pass
                # check file（.mq5/.ex5 — 非 config + ctime 新 → delete + 記錄）
                _now2 = _tbb2.time()
                _bounced2 = []
                for _ed2 in _ea_dirs2:
                    for _fn2 in _o2.listdir(_ed2):
                        if not _fn2.endswith(('.mq5', '.ex5')):
                            continue
                        _base2 = _o2.path.splitext(_fn2)[0]
                        if _base2 in _cfg2:
                            continue  # config 有（正常配對）
                        _fp2 = _o2.path.join(_ed2, _fn2)
                        _ctime2 = _o2.path.getctime(_fp2)
                        # [ALERT] 保險：ctime < 10 秒（啱啱出現 — 可能 install-local 配對中 — config 未寫）→ 唔刪（下一個 tick 再睇）
                        if _now2 - _ctime2 < 10:
                            continue
                        if _now2 - _ctime2 < 180:  # 3 分鐘內出現 = 彈返（config 冇）
                            try:
                                _o2.remove(_fp2)
                                _bounced2.append(_fn2)
                                print(f"[彈返監察] [DEL] 定期自癒delete彈返: {_fn2} ({_o2.path.basename(_ed2)})", flush=True)
                            except Exception:
                                pass
                if _bounced2:
                    try:
                        from . import _log_bounce_back  # 唔會 — 直接記錄
                    except Exception:
                        pass
                    try:
                        _entry2 = {'time': _tbb2.strftime('%Y-%m-%d %H:%M:%S'), 'trigger': 'periodic', 'files': _bounced2}
                        _logp2 = _o2.path.join(_o2.path.dirname(_o2.path.abspath(__file__)), 'bounce_back_log.jsonl')
                        with open(_logp2, 'a', encoding='utf-8') as _f2:
                            _f2.write(_j2.dumps(_entry2, ensure_ascii=False) + '\n')
                    except Exception:
                        pass
            except Exception:
                pass
    _th2.Thread(target=_run, daemon=True).start()
    print("[彈返監察] 定期自癒已start（每 30 秒）", flush=True)


# [ALERT] 2026-08-15：start彈返定期監察（background thread）
try:
    _bounce_back_watchdog()
except Exception as _ebw:
    print(f"[彈返監察] [WARN] startfailed: {_ebw}", flush=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me')
# [ALERT] 2026-08-29 FIX：SQLALCHEMY_DATABASE_URI 改絕對path（before相對 sqlite:///mt5cloud.db →
# resolve 去 server/instance/mt5cloud.db 舊 DB — ORM write同 raw SQL 讀（repo/instance/mt5cloud.db）分家
# → install-local config write去錯 DB → 配對庫唔見新 EA；v0.9.67 修過但after被 revert）
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'mt5cloud.db').replace('\\', '/')
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
        # [ALERT] 2026-08-26（multi-user）：加 user 欄（每account獨立活動記錄 — 唔好全局共享）
        _u_n = ''
        try:
            if 'current_user' in globals() and current_user and not current_user.is_anonymous:
                _u_n = current_user.username
        except Exception:
            try:
                from flask_login import current_user as _cu2
                if _cu2 and not _cu2.is_anonymous:
                    _u_n = _cu2.username
            except Exception:
                pass
        entry = {
            'time': time.time(),
            'action': action,
            'ea': ea,
            'message': message,
            'source': source,
            'user': _u_n,
        }
        line = json.dumps(entry, ensure_ascii=False) + '\n'
        with _activity_lock:
            with open(ACTIVITY_LOG_PATH, 'a', encoding='utf-8') as f:
                f.write(line)
    except Exception:
        pass


def _write_ai_flags(sig, steps):
    """[ALERT] 2026-08-28 FIX（PC版 + 網頁版warning視窗要一致）：雙寫 show/steps flag
    開發dir（server 讀 — 網頁 modal）+ TradotcomAgent（alert_worker 讀 — PC版視窗）
    → 兩個位置都寫 → PC版 + 網頁版都見到 → 一致
    [ALERT] 2026-09-03（VPS 搬遷）：server 喺 VPS — agent 喺 A/B 電腦 — 本地雙寫唔通
    → 加 SocketIO emit（推俾 current_user 嘅 agent）— agent 收到寫自己機 flag → alert_worker 彈窗
    """
    _dirs = []
    # 1. 開發dir（agent/）
    _adir_dev = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
    _dirs.append(_adir_dev)
    # 2. TradotcomAgent（alert_worker 讀）
    _adir_inst = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TradotcomAgent')
    if os.path.isdir(_adir_inst):
        _dirs.append(_adir_inst)
    for _d in _dirs:
        try:
            os.makedirs(_d, exist_ok=True)
            if sig:
                with open(os.path.join(_d, '.ai_control.show'), 'w', encoding='utf-8') as _f:
                    _f.write(sig)
            if isinstance(steps, list):
                with open(os.path.join(_d, '.ai_control.steps'), 'w', encoding='utf-8') as _f:
                    json.dump(steps, _f, ensure_ascii=False)
        except Exception:
            pass
    # [ALERT] 2026-09-03（VPS 搬遷）：SocketIO push 俾遠端 agent（agent 收到寫自己機 flag → alert_worker 彈）
    try:
        _tgt = None
        try:
            from flask_login import current_user as _cu
            if _cu is not None and getattr(_cu, 'is_authenticated', False):
                _a_q = Agent.query.filter_by(user_id=_cu.id).first()
                if _a_q:
                    _tgt = _a_q.agent_id
        except Exception:
            _tgt = None
        if _tgt:
            socketio.emit('control_alert', {'sig': sig or '', 'steps': steps if isinstance(steps, list) else []},
                          room=_tgt)
        else:
            socketio.emit('control_alert', {'sig': sig or '', 'steps': steps if isinstance(steps, list) else []})
    except Exception as _e_push:
        print(f"[WARN] _write_ai_flags socketio push failed: {_e_push}", flush=True)

def _push_alert_socket(sig, steps):
    """[ALERT] 2026-09-03（VPS 搬遷）：SocketIO push 警告視窗俾 current_user 嘅 agent
    （server 喺 VPS — agent 喺 A/B 電腦 — 本地寫檔唔通 — 要 SocketIO push）"""
    try:
        from flask_login import current_user as _cu2
        _tgt2 = None
        if _cu2 is not None and getattr(_cu2, 'is_authenticated', False):
            _a2 = Agent.query.filter_by(user_id=_cu2.id).first()
            if _a2:
                _tgt2 = _a2.agent_id
        _payload = {'sig': sig or '', 'steps': steps if isinstance(steps, list) else []}
        if _tgt2:
            socketio.emit('control_alert', _payload, room=_tgt2)
        else:
            socketio.emit('control_alert', _payload)
    except Exception as _e2:
        print(f"[WARN] _push_alert_socket failed: {_e2}", flush=True)




@app.route('/api/control-steps', methods=['GET', 'POST'])
@login_required
def api_control_steps():
    """[ALERT] 2026-08-10：攞操作步驟（warning視窗顯示 — 一排排）
    POST（2026-08-12）：前端逐步更新 steps（重新整理流程 — 刷新邊一項 + 成唔success）"""
    if request.method == 'POST':
        try:
            import time as _tw
            data = request.json or {}
            steps_in = data.get('steps')
            sig = data.get('sig', '')
            # [ALERT] 2026-08-29 FIX（PC版warning視窗冇彈 — 重新整理流程）：改用 _write_ai_flags 雙寫
            # before淨寫開發dir（agent_dir）→ alert_worker（讀 TradotcomAgent）冇 flag → PC版唔彈
            _write_ai_flags(sig, steps_in)
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
                # [ALERT] 2026-08-12：讀唔到（多個 process 同時寫 → file損壞/空）→ 唔返回 []（網頁唔會空白 — 彈嚟彈去根治）
                steps_data = [{'text': 'Waiting for operation to start...', 'status': 'pending'}]
            # [ALERT] 2026-08-11：返回 steps + mtime（前端用嚟判斷「舊 steps 唔顯示」— 新任務start唔會殘留上一個操作 — user投訴）
            import time as _tm
            return jsonify({"steps": steps_data, "mtime": os.path.getmtime(steps_file)})
    except Exception:
        return jsonify([])


@app.route('/api/control-guard/stop', methods=['POST'])
@login_required
def api_control_guard_stop():
    """網站版緊急stop：寫 .ai_control.stop 標記 → watcher/compile/auto_attach 偵測到就 abort"""
    try:
        agent_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
        stop_file = os.path.join(agent_dir, '.ai_control.stop')
        with open(stop_file, 'w', encoding='utf-8') as f:
            f.write('stop|web')
        # 強制寫 ai_control.json inactive → 網站warning視窗immediately關（Bug #68：唔可以卡死）
        try:
            detector_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        'server', 'static', 'detector')
            os.makedirs(detector_dir, exist_ok=True)
            status_file = os.path.join(detector_dir, 'ai_control.json')
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump({'active': False, 'program': '', 'time': time.time()}, f, ensure_ascii=False)
        except Exception:
            pass
        log_activity('emergency_stop', '網站緊急stop已觸發（AI 操作會immediately中止）', ea='')
        return jsonify({"success": True, "message": "緊急stop已觸發"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/activity')
def api_activity():
    """讀 activity log（倒序，全部）— refresh 後依然exists（持久file，唔會delete）
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
    # [ALERT] 2026-08-26（multi-user）：只顯示「自己account」嘅活動（per-user 獨立）
    # 舊條目（冇 user 欄）→ 只喺單機（dev）時顯示返（向後兼容）；新條目按 user 過濾
    try:
        _cur_u = current_user.username
        entries = [e for e in entries if not e.get('user') or e.get('user') == _cur_u]
    except Exception:
        pass
    # [ALERT] 2026-09-01 FIX（dropdown lag — 用戶實測）：server 返回 limit 500 條（之前全部 10117 條 → 前端 render 10000+ <tr> → Chrome 卡）
    # 活動記錄永久保存（唔刪）— 但 API 只返回最新 500 條（前端 render 200）— 效能優先
    return jsonify({'activities': entries[:500], 'total': len(entries)})
import os
_async_mode = 'eventlet' if os.environ.get('RENDER', '') else 'threading'
# [ALERT] 2026-09-01 FIX（agent 每 60 秒 reconnect — socket 斷）：threading mode 下 SocketIO 長連接唔穩定
# → 加 ping_interval/ping_timeout（server 主動發 ping — 唔會 60 秒 idle 斷）
# （default ping_interval=25, ping_timeout=20 — 但 threading mode 可能唔work — 明確設定）
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=_async_mode, logger=False, engineio_logger=False,
                    ping_interval=25, ping_timeout=60)

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
    # [ALERT] 2026-08-26（multi-user Phase 1）：Agent 上報「local MT5 file快照」（heartbeats/trades_stats/log_last/hotkeys）
    # → server 優先讀呢個（每機獨立）— 唔再直接讀localfile（支持第二部機接入）
    files_snapshot = db.Column(db.Text, default='{}')
    # [ALERT] 2026-08-26（multi-user Phase 4）：Agent token — 註冊時生成，上報/connection時驗證（防冒認）
    agent_token = db.Column(db.String(64), default='')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()
    # [ALERT] 2026-08-26（multi-user Phase 1）：migration — agent 表加 files_snapshot 欄（create_all 唔會加去現有表）
    try:
        import sqlite3 as _sq_m
        _dbm = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'instance', 'mt5cloud.db')
        _cm = _sq_m.connect(_dbm)
        _agent_cols = [r[1] for r in _cm.execute('PRAGMA table_info(agent)')]
        if 'files_snapshot' not in _agent_cols:
            _cm.execute("ALTER TABLE agent ADD COLUMN files_snapshot TEXT DEFAULT '{}'")
            _cm.commit()
            print("[OK] migration: agent.files_snapshot 欄加咗")
        if 'agent_token' not in _agent_cols:
            _cm.execute("ALTER TABLE agent ADD COLUMN agent_token TEXT DEFAULT ''")
            _cm.commit()
            print("[OK] migration: agent.agent_token 欄加咗")
        _cm.close()
    except Exception as _e_mig:
        print(f"[WARN] migration files_snapshot failed（唔阻start）: {_e_mig}")
    # create固定 Dev Account（如果未exists）
    if not User.query.filter_by(username='dev').first():
        dev_user = User(username='dev', email='dev@mt5cloud.com',
                        password=generate_password_hash('dev1234'))
        db.session.add(dev_user)
        import secrets as _sec_d
        dev_agent = Agent(agent_id='DEV00001', user=dev_user, agent_token=_sec_d.token_hex(16))
        db.session.add(dev_agent)
        db.session.commit()
        print("[OK] Dev account created: dev / dev1234")

# 預設交易品種
ALL_SYMBOLS = ['EURUSD','GBPUSD','USDJPY','AUDUSD','USDCAD','NZDUSD',
               'EURJPY','GBPJPY','EURGBP','EURCHF','GBPCHF','AUDJPY',
               'GBPAUD','EURNZD','XAUUSD','XAGUSD',
               'US30','US500','DE40','UK100','JP225','AUS200',
               'BTCUSD','ETHUSD']
TIMEFRAMES = ['M1','M5','M15','M30','H1','H4','D1','W1','MN1']

def get_account_symbols():
    """攞帳號實際可用 symbols
    user要求（2026-08-21）：網頁 symbol picker 只顯示帳號實際有嘅 symbol（揀到冇嘅 → deploy fail）
    來源：bases/<account>/History dir（account伺服器實際支援過嘅 symbol — 比 symbols.sel 可靠）
    [WARN] symbols.sel 只係「市場報價顯示嘅 symbol」（user可以自己加/remove — 唔係權威）
    [WARN] 揀account：優先搵「有最多 History symbol」嗰個（now登入account通常係最新用嘅）"""
    # [ALERT] 2026-09-03（VPS 搬遷 — 方案2）：server（VPS）冇 MT5 — 優先讀 agent 上報嘅 symbols
    try:
        if current_user.is_authenticated:
            _agt_sy = Agent.query.filter_by(user_id=current_user.id).first()
            if _agt_sy and _agt_sy.files_snapshot:
                _snap_sy = json.loads(_agt_sy.files_snapshot or '{}')
                _syms_up = _snap_sy.get('symbols')
                if isinstance(_syms_up, list) and _syms_up:
                    print(f"[symbols] agent 上報 symbols ({len(_syms_up)}): {_syms_up[:8]}...")
                    return _syms_up
    except Exception:
        pass
    try:
        _mt5d = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        for _d_s in os.listdir(_mt5d):
            _bases_s = os.path.join(_mt5d, _d_s, 'bases')
            if not os.path.isdir(_bases_s):
                continue
            _best_syms = []
            _best_acct = None
            for _a_s in os.listdir(_bases_s):
                _h_s = os.path.join(_bases_s, _a_s, 'History')
                if os.path.isdir(_h_s):
                    _syms_s = [s for s in os.listdir(_h_s)
                               if os.path.isdir(os.path.join(_h_s, s)) and not s.startswith('_')]
                    if len(_syms_s) > len(_best_syms):
                        _best_syms = _syms_s
                        _best_acct = _a_s
            if _best_syms:
                print(f"[symbols] 帳號 {_best_acct} symbols ({len(_best_syms)}): {_best_syms}")
                return _best_syms
    except Exception as _e_s:
        print(f"[symbols] 讀帳號 symbols failed: {_e_s}")
    # fallback：symbols.sel（市場報價顯示）
    try:
        for _d_s2 in os.listdir(os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')):
            _sp_s2 = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', _d_s2, 'symbols.sel')
            if os.path.isfile(_sp_s2):
                _raw_s2 = open(_sp_s2, 'rb').read()
                _txt_s2 = None
                for _enc_s2 in ('utf-8', 'utf-16'):
                    try:
                        _txt_s2 = _raw_s2.decode(_enc_s2)
                        break
                    except Exception:
                        continue
                if _txt_s2:
                    _syms_s2 = [l.split('=')[0].strip() for l in _txt_s2.splitlines() if '=' in l]
                    if _syms_s2:
                        return _syms_s2
    except Exception:
        pass
    return ALL_SYMBOLS

# === Frontend ===
@app.route('/')
def index():
    if current_user.is_authenticated:
        # [ALERT] 2026-08-11：dashboard.html 唔 cache（前端 JS 一定攞最新 — user硬刷新都唔夠時確保）
        resp = make_response(render_template('dashboard.html'))
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        return resp
    # [ALERT] 2026-08-28：Landing page（介紹網站 — tradotcom.com 首頁）— 未登入顯示
    return render_template('landing.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # [ALERT] 2026-08-11：dashboard.html 唔 cache
    # [ALERT] 2026-08-28：傳當前登入user（sidebar 顯示「登入：username」）
    resp = make_response(render_template('dashboard.html', user=current_user))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp

@app.route('/home')
def home():
    # [ALERT] 2026-08-28：返回主頁（landing — 已登入都顯示 — 唔 redirect dashboard）
    # 登入後想去返介紹頁（比較/特點）用 — 唔同 /（已登入 redirect dashboard）
    resp = make_response(render_template('landing.html'))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp

@app.route('/register', methods=['GET','POST'])
def register():
    # [ALERT] 2026-08-31（user要求：網上唔好俾人註冊 — 淨係內部account做到嘢）：
    # 關閉公開註冊 — 需要內部邀請碼先註冊到
    _REGISTER_CLOSED = True  # [LOCK] 公開註冊closed（內部限定）
    _INVITE_CODE = os.environ.get('TRADOTCOM_INVITE_CODE', '') or 'tradotcom-internal-2026'  # 內部邀請碼（可改環境變數）
    if _REGISTER_CLOSED:
        if request.method == 'POST':
            data = request.json if request.is_json else request.form
            invite = (data.get('invite_code') or '').strip()
            if invite != _INVITE_CODE:
                return jsonify({"error": "註冊closed（內部限定）— 需要有效邀請碼", "register_closed": True}), 403
            # 有邀請碼 → 繼續註冊
            if User.query.filter_by(username=data.get('username')).first():
                return jsonify({"error":"Username taken"}),400
            user = User(username=data['username'], email=data.get('email',''),
                        password=generate_password_hash(data['password']))
            db.session.add(user)
            # [ALERT] 2026-08-26（Phase 4）：Agent token — 註冊時生成（防冒認）
            import secrets as _sec_r
            _tok_r = _sec_r.token_hex(16)
            agent = Agent(agent_id=str(uuid.uuid4())[:8], user=user, agent_token=_tok_r)
            db.session.add(agent)
            db.session.commit()
            login_user(user)
            return jsonify({"success":True,"agent_id":agent.agent_id,"agent_token":_tok_r})
        # GET → render register 頁（顯示「內部限定」+ 邀請碼欄位）
        return render_template('register.html', register_closed=True)
    if request.method == 'POST':
        data = request.json if request.is_json else request.form
        if User.query.filter_by(username=data.get('username')).first():
            return jsonify({"error":"Username taken"}),400
        user = User(username=data['username'], email=data.get('email',''),
                    password=generate_password_hash(data['password']))
        db.session.add(user)
        # [ALERT] 2026-08-26（Phase 4）：Agent token — 註冊時生成（防冒認）
        import secrets as _sec_r
        _tok_r = _sec_r.token_hex(16)
        agent = Agent(agent_id=str(uuid.uuid4())[:8], user=user, agent_token=_tok_r)
        db.session.add(agent)
        db.session.commit()
        login_user(user)
        return jsonify({"success":True,"agent_id":agent.agent_id,"agent_token":_tok_r})
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
    """create測試帳號（一鍵生成）"""
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

def _market_closed_for_symbol(symbol):
    """[ALERT] 2026-08-21：偵測 symbol 係咪非交易時間（休市）
    - 用 MT5 symbol_info_tick 最後 tick 時間（tick.time 係 UTC+3 伺服器時間 — 正規化）
    - 最後 tick > 5 分鐘 = 冇報價 = 休市/非交易時間
    - 回傳 None（攞唔到資料）/ True（休市）/ False（開市）
    """
    try:
        import MetaTrader5 as _mt5
        # [ALERT] 2026-09-01 FIX（用戶實測：冇操作都開 MT5 — 網頁 poll /api/ea-config → _market_closed_for_symbol → mt5.initialize 自動開 terminal64）：
        # → 先檢查 terminal64 有冇開（tasklist）— 未開 → 唔 initialize（返回 None — 唔自動開）
        try:
            import subprocess as _sp_mc
            _r_mc = _sp_mc.run('tasklist /FI "IMAGENAME eq terminal64.exe" /NH', shell=True, capture_output=True, timeout=5)
            if b'terminal64' not in _r_mc.stdout:
                return None
        except Exception:
            pass
        # 唔 initialize 新connection — 用 agent 已有嘅？唔得，呢度獨立。輕量 initialize + shutdown
        if not _mt5.initialize(timeout=4000):
            return None
        try:
            _tick = _mt5.symbol_info_tick(symbol)
            if _tick is None:
                return None
            # tick.time 係 UTC+3（EET 夏令）— 正規化做 UTC
            _tick_utc = _tick.time - 3 * 3600
            _age = time.time() - _tick_utc
            _mt5.shutdown()
            return _age > 300  # > 5 分鐘no tick = 休市
        except Exception:
            try: _mt5.shutdown()
            except Exception: pass
            return None
    except Exception:
        return None

def _current_agent_snapshot():
    """[ALERT] 2026-08-26（multi-user Phase 1）：攞當前user agent 上報嘅file快照（每機獨立）
    有 snapshot（agent 上報過）→ 用佢（支持多機）; 冇 → None（server fallback 讀local — 單機向後兼容）
    """
    try:
        agent = Agent.query.filter_by(user_id=current_user.id).first()
        if agent and agent.files_snapshot:
            _snap = json.loads(agent.files_snapshot or '{}')
            if _snap and isinstance(_snap, dict) and _snap.get('ts'):
                return _snap
    except Exception:
        pass
    return None


@app.route('/api/ea-config', methods=['GET', 'POST'])
@login_required
def api_ea_config():
    if request.method == 'GET':
        # 直接讀 DB（繞過 ORM 隔離）
        try:
            import sqlite3 as _sq3
            _db3 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'instance', 'mt5cloud.db')
            _c3 = _sq3.connect(_db3)
            _r2 = _c3.execute('SELECT ea_config FROM user WHERE id=?', (current_user.id,)).fetchone()
            _c3.close()
            config = json.loads(_r2['ea_config'] or '{}') if _r2 else {}
        except Exception:
            config = json.loads(current_user.ea_config or '{}')
        # [WARN] 控制層心跳狀態（CONTROL_LAYER_DESIGN.md）：讀 Common/Files/state_<ea>.json
        # running（ts 新鮮 <30 秒）/ stopped / unknown（冇檔或過期）
        # [WARN] 2026-08 修：config 冇 _status key（只有 ea_name/ea_lot/ea_magic/ea_tf）→ 唔可以靠 _status 尾
        # [ALERT] 2026-08-26（multi-user Phase 1）：agent 上報 snapshot 優先（每機獨立 — 支持多機）
        # → 有 agent 上報 → 用佢嘅 heartbeats/log_last/hotkeys；冇 → 讀local（單機向後兼容）
        _snap_s = _current_agent_snapshot()
        _use_snapshot = _snap_s is not None
        _snap_hb = (_snap_s or {}).get('heartbeats') or {}
        _snap_log = (_snap_s or {}).get('log_last') or {}
        _snap_hk = (_snap_s or {}).get('hotkeys') or []
        runtime = {}
        # [ALERT] 2026-08-14：讀 MT5 log — 每隻 EA 最後一條記錄（已start/已stop/removed — 圖表實際狀態）
        _log_last = dict(_snap_log) if _use_snapshot else {}
        try:
            import glob as _gl2
            _lg2 = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
            _latest2 = None
            for _d3 in os.listdir(_lg2):
                # [ALERT] 2026-08-21 FIX：優先讀 terminal Logs（<hash>/Logs/ — 英文「loaded successfully/removed」）
                # before讀 MQL5/Logs（MetaEditor 編譯日誌 — 中文「已启动/已stop」）→ 誤判 chart_removed（RSI_Over 掛住但顯示 removed）
                _lgd3 = os.path.join(_lg2, _d3, 'Logs')
                if os.path.isdir(_lgd3):
                    for _f3 in _gl2.glob(os.path.join(_lgd3, '2026*.log')):
                        if _latest2 is None or os.path.getmtime(_f3) > os.path.getmtime(_latest2):
                            _latest2 = _f3
            # fallback: MQL5/Logs（MetaEditor 日誌）
            if not _latest2:
                for _d3 in os.listdir(_lg2):
                    _lgd3 = os.path.join(_lg2, _d3, 'MQL5', 'Logs')
                    if os.path.isdir(_lgd3):
                        for _f3 in _gl2.glob(os.path.join(_lgd3, '2026*.log')):
                            if _latest2 is None or os.path.getmtime(_f3) > os.path.getmtime(_latest2):
                                _latest2 = _f3
            if _latest2:
                _raw2 = open(_latest2, 'rb').read()
                _txt2 = None
                for _enc2 in ('utf-16', 'utf-8', 'cp1252'):
                    try:
                        _txt2 = _raw2.decode(_enc2); break
                    except Exception:
                        continue
                if _txt2:
                    import re as _re2
                    for _line2 in _txt2.splitlines():
                        # [ALERT] 2026-08-21 FIX：加「loaded successfully」（英文 log — before淨 match 中文 已启动/已stop + removed → 英文 log 嘅 loaded 唔 match → 淨係 match 到 removed → 誤判 chart_removed）
                        _m2 = _re2.search(r'([A-Za-z_][A-Za-z0-9_]*) \([A-Za-z0-9._]+,[A-Z0-9]+\)\s+[^\n]*(已启动|已start|已stop|removed|loaded successfully)', _line2)
                        if _m2:
                            _log_last[_m2.group(1)] = _m2.group(2)
        except Exception:
            pass
        try:
            common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
            # [ALERT] 2026-08-13：讀熱鍵（hotkeys.ini — deploy記錄 — 判斷「啱啱deploy等心跳」vs「冇心跳機制」）
            _hk_has = set()
            _hk_mtime = 0
            try:
                import re as _re_hk
                _hk_path = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
                for _d2 in os.listdir(_hk_path):
                    _hkf = os.path.join(_hk_path, _d2, 'config', 'hotkeys.ini')
                    if os.path.isfile(_hkf):
                        _hk_mtime = os.path.getmtime(_hkf)
                        _hk_c = open(_hkf, 'r', encoding='utf-16-le', errors='ignore').read()
                        for _m2 in _re_hk.finditer(r'Experts\\([A-Za-z_][A-Za-z0-9_]*)\.ex5\s*=', _hk_c):
                            _hk_has.add(_m2.group(1))
                        break
            except Exception:
                pass
            ea_names = set()
            for key in config:
                base = key
                for suffix in ('_lot', '_magic', '_tf', '_status'):
                    if key.endswith(suffix):
                        base = key[:-len(suffix)]
                        break
                # [ALERT] 2026-08-13：過濾 `_` 開頭（_default_lot / _removed — 唔係 EA）
                if base.startswith('_'):
                    continue
                if base and base not in ('_lot', '_magic', '_tf', '_status'):
                    ea_names.add(base)
            for ea in ea_names:
                sf = os.path.join(common_files, f'state_{ea}.json')
                hb_txt = os.path.join(common_files, f'hb_{ea}.txt')
                # [ALERT] 2026-08-26（multi-user Phase 1）：snapshot 模式 — 心跳判斷用 agent 上報（每機獨立）
                _sn_hb_info = _snap_hb.get(ea) if _use_snapshot else None
                _sn_hb_fresh = bool(_sn_hb_info and (_sn_hb_info.get('age_sec', 999) < 300))
                _sn_hk_has = (ea in _snap_hk) if _use_snapshot else None
                # [ALERT] 2026-08-13：冇任何心跳file（state/hb 都not exist）
                # 判斷：有熱鍵（deploy過）→ 啱啱deploy（hotkeys.ini 新 — <10 分鐘）→ 'starting'（等心跳）；deploy好耐都冇心跳 → 'no_hb'（冇心跳設定 — Ichimoku 案例）
                #       冇熱鍵（未deploy）→ 'unpaired'（未配對 — 未deploy唔知有冇心跳 — Seasonal 案例）
                _has_hb_file = _sn_hb_info is not None if _use_snapshot else (os.path.isfile(sf) or os.path.isfile(hb_txt))
                _in_hk = _sn_hk_has if _use_snapshot else (ea in _hk_has)
                if not _has_hb_file:
                    if _in_hk:
                        # [ALERT] 2026-08-31 FIX（用戶實測：配對完嘅 EA 短暫顯示「等待心跳」）：
                        # starting 只限「hotkeys.ini 有呢個 EA」+「hotkeys 新」— 但配對（install-local）會寫 hotkeys？
                        # → 加「EA 名要 match hotkeys 嗰個」（_in_hk 已 check）— 但 hotkeys.ini 可能殘留舊 EA（Fibonacci）
                        # → 再加「config 有 EA 但未部署過（無心跳 + 無 loaded log）」→ 唔好當 starting — 睇 log 有冇 loaded 過
                        # （未部署過嘅 EA 唔應該顯示「等待心跳」— 誤導 — 應該「未配對」）
                        runtime[ea] = 'starting' if (time.time() - _hk_mtime < 600) else 'no_hb'
                    else:
                        runtime[ea] = 'unpaired'
                    continue
                # [ALERT] 2026-08-14：有 state/hb file但冇熱鍵（未deploy — 歷史殘留心跳file — MACD_Cross 案例）→ unpaired（未配對）
                # （before只判斷「冇file」→ 有file + 冇熱鍵 → unknown → 前端誤顯示 Magic/Symbol — user質疑「冇配對嘅都有 magic」）
                # [ALERT] 2026-08-26 FIX（問題 1：deploy第二隻 EA 後第一隻心跳 check 唔到）— 熱鍵now Ctrl+1 重用
                # （每次deploy清空舊 mapping + 只寫新 EA）→ hotkeys.ini 只反映最後deploy嗰隻 → 舊 EA 唔喺 _hk_has → 誤判 unpaired
                # → 修正：有心跳檔 + 心跳新鮮（<300s）= 真係running緊（唔理熱鍵）— 淨係「有檔但心跳舊」先當殘留
                _hb_fresh_ea = _sn_hb_fresh if _use_snapshot else False
                if not _use_snapshot:
                    try:
                        _sf_hb = os.path.join(common_files, f'state_{ea}.json')
                        _hb_txt_hb = os.path.join(common_files, f'hb_{ea}.txt')
                        for _hfp_hb in (_sf_hb, _hb_txt_hb):
                            if os.path.isfile(_hfp_hb) and time.time() - os.path.getmtime(_hfp_hb) < 300:
                                _hb_fresh_ea = True
                                break
                    except Exception:
                        pass
                _in_hk2 = _sn_hk_has if _use_snapshot else (ea in _hk_has)
                if not _in_hk2 and not _hb_fresh_ea:
                    runtime[ea] = 'unpaired'
                    continue
                st = 'unknown'
                if _use_snapshot:
                    # snapshot 模式：心跳新鮮（age<300）= running（agent 上報 status=alive）
                    if _sn_hb_info and _sn_hb_info.get('age_sec', 999) < 300:
                        st = 'running'
                    elif _sn_hb_info and _sn_hb_info.get('status') == 'stopped':
                        st = 'stopped'
                else:
                    if os.path.isfile(sf):
                        try:
                            # [WARN] MQL5 FileWrite 寫 UTF-16 LE（BOM \xff\xfe）— 要 fallback decode
                            with open(sf, 'rb') as f:
                                raw = f.read()
                            try:
                                sd = json.loads(raw.decode('utf-8'))
                            except Exception:
                                sd = json.loads(raw.decode('utf-16'))
                            # [ALERT] 2026-08-13：心跳running = status=running + 心跳新鮮（mtime <300 秒 — EA now寫緊心跳（market close心跳疏 — 300 秒寬限 cover；關圖表後心跳停 >5 分鐘 → 「沒有心跳」））
                            # （before淨睇 status → 歷史殘留（EA 最後一次寫嘅 running — after停咗）→ 全部誤顯示「心跳running」— user質疑）
                            age = time.time() - os.path.getmtime(sf)
                            if sd.get('status') == 'running' and age < 30:
                                st = 'running'
                            elif sd.get('status') == 'stopped':
                                st = 'stopped'
                        except Exception:
                            st = 'unknown'
                    # [ALERT] 2026-08-13 FIX：AgentHelper 案例 — 心跳用 hb_<EA>.txt（舊版 EA 格式）— state_*.json 揾唔到 → 檢查 hb_*.txt
                    if st != 'running':
                        if os.path.isfile(hb_txt) and time.time() - os.path.getmtime(hb_txt) < 30:
                            st = 'running'
                # [ALERT] 2026-08-14：log 圖表狀態（最優先 — 圖表實際有冇 EA — 關圖表immediately「圖表remove」— 唔使等心跳停 30 秒）
                # （log 最後「已stop/removed」= 圖表冇 EA — 心跳新鮮都只係 EA stop前殘留 → chart_removed）
                if _log_last.get(ea) in ('已stop', 'removed'):
                    st = 'chart_removed'
                # [ALERT] 2026-08-14 定案：user要求「統一 — 冇pause」— 取消「已pause」狀態（paused 判斷remove — 心跳停 → unknown「心跳pause」）
                runtime[ea] = st
        except Exception:
            pass
        # [ALERT] 2026-08-21：讀 EA 自寫統計（state_<ea>.json 入面 trades/wins/losses/profit — TestTrades 測試 EA 寫）
        # 原因：MT5 Python history API 讀唔到新 deals（build 6120 caching）→ EA 自己 track 寫檔 → 呢度讀
        ea_stats = {}
        _snap_ts2 = (_snap_s or {}).get('trades_stats') or {}
        try:
            _cf2 = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
            for _ea in ea_names:
                # [ALERT] 2026-08-26 FIX（問題 3：未deploy嘅 EA 顯示舊 trades stats — TestTrades 殘留 substituted running緊 EA）
                # → 只有「running緊/啱啱deploy」先顯示 stats（runtime status = running/starting）— 未deploy/已remove → 唔顯示
                try:
                    _ea_rt = runtime.get(_ea, '')
                except Exception:
                    _ea_rt = ''
                if _ea_rt not in ('running', 'starting'):
                    continue
                # [ALERT] 2026-08-26（multi-user Phase 1）：snapshot 模式 — 直接用 agent 上報嘅 trades_stats（每機獨立）
                if _use_snapshot and _ea in _snap_ts2:
                    ea_stats[_ea] = _snap_ts2[_ea]
                    continue
                # [ALERT] 2026-08-21 FIX：優先讀 trades_<EA>.json（EA AppendTrade/RebuildTradesFile 寫嘅逐單明細 — 完整歷史）
                # state json 會被系統心跳覆寫（得 ea/status/ts — 冇 stats）→ 唔可靠
                _tf2 = os.path.join(_cf2, f'trades_{_ea}.json')
                _trade_stats = None
                if os.path.isfile(_tf2):
                    try:
                        with open(_tf2, 'rb') as _f2:
                            _raw2 = _f2.read()
                        _txt2 = None
                        for _enc2 in ('utf-8', 'utf-16'):
                            try:
                                _txt2 = _raw2.decode(_enc2)
                                break
                            except Exception:
                                continue
                        if _txt2:
                            _tlist = []
                            for _line2 in _txt2.splitlines():
                                _line2 = _line2.strip()
                                if not _line2:
                                    continue
                                try:
                                    _td2 = json.loads(_line2)
                                    if 'profit' in _td2:
                                        _tlist.append(_td2)
                                except Exception:
                                    continue
                            if _tlist:
                                _profits = [_t2.get('profit', 0) for _t2 in _tlist]
                                _grossP = sum(p for p in _profits if p > 0)
                                _grossL = sum(-p for p in _profits if p < 0)
                                _wins2 = sum(1 for p in _profits if p > 0)
                                _losses2 = sum(1 for p in _profits if p < 0)
                                _avgW = round(_grossP / _wins2, 2) if _wins2 > 0 else 0
                                _avgL = round(_grossL / _losses2, 2) if _losses2 > 0 else 0
                                # max drawdown（累積曲線）
                                _cum2 = 0.0; _peak2 = 0.0; _maxdd2 = 0.0
                                for _p2 in _profits:
                                    _cum2 += _p2
                                    if _cum2 > _peak2: _peak2 = _cum2
                                    _dd2 = _peak2 - _cum2
                                    if _dd2 > _maxdd2: _maxdd2 = round(_dd2, 2)
                                _wr2 = (_wins2 + _losses2) > 0 and _wins2 / (_wins2 + _losses2) or 0
                                _exp2 = round(_wr2 * _avgW - (1 - _wr2) * _avgL, 2)
                                _trade_stats = {
                                    "trades": len(_profits),
                                    "wins": _wins2,
                                    "losses": _losses2,
                                    "profit": round(sum(_profits), 2),
                                    "gross_profit": round(_grossP, 2),
                                    "gross_loss": round(_grossL, 2),
                                    "avg_win": _avgW,
                                    "avg_loss": _avgL,
                                    "max_dd": _maxdd2,
                                    "expectancy": _exp2,
                                    "profit_factor": round(_grossP / _grossL, 2) if _grossL > 0 else (float('inf') if _grossP > 0 else 0),
                                }
                    except Exception:
                        pass
                if _trade_stats:
                    ea_stats[_ea] = _trade_stats
                    continue
                # fallback: state json（如果有 stats）
                _sf2 = os.path.join(_cf2, f'state_{_ea}.json')
                if os.path.isfile(_sf2):
                    try:
                        with open(_sf2, 'rb') as _f2:
                            _raw2 = _f2.read()
                        try:
                            _sd2 = json.loads(_raw2.decode('utf-8'))
                        except Exception:
                            _sd2 = json.loads(_raw2.decode('utf-16'))
                        if isinstance(_sd2, dict) and ('trades' in _sd2 or 'profit' in _sd2):
                            ea_stats[_ea] = {
                                "trades": _sd2.get('trades', 0),
                                "wins": _sd2.get('wins', 0),
                                "losses": _sd2.get('losses', 0),
                                "profit": _sd2.get('profit', 0),
                            }
                    except Exception:
                        pass
        except Exception:
            pass
        # [ALERT] 2026-08-21：非交易時間偵測（休市）— 對每隻 EA 嘅 symbol 檢查最後 tick
        # 心跳pause + market_closed → 前端顯示「休市」而唔係「心跳pause」（唔係 EA 故障）
        market_closed = {}
        try:
            for _ea in ea_names:
                _sym2 = config.get(_ea)
                if not _sym2 or not isinstance(_sym2, str):
                    continue
                _mc = _market_closed_for_symbol(_sym2)
                if _mc is not None:
                    market_closed[_ea] = _mc
        except Exception:
            pass
        # [ALERT] 2026-08-26（multi-user）：agent_eas — 各自 agent 上報嘅 EA（每機獨立 — 前端 localEA 用呢個唔再用全局 detector inventory）
        _agent_eas = []
        try:
            _snap_e = _current_agent_snapshot()
            if _snap_e:
                # [ALERT] 2026-08-29 FIX：heartbeats 都要 alive 過濾（同 log_last 一致）
                # before _hb_e = heartbeats.keys() 冇過濾 → 死 agent 嘅舊 snapshot（殘留心跳檔上報）
                # 包含已remove EA → 前端 agentEasCache 有殘留 → 配對庫顯示「已加入」（user：PC冇 EA 但配對庫有）
                _hb_alive = set(k for k, v in (_snap_e.get('heartbeats') or {}).items()
                                if isinstance(v, dict) and v.get('status') == 'alive')
                _hb_e = _hb_alive
                _log_e = set((_snap_e.get('log_last') or {}).keys())
                _hk_e = set(_snap_e.get('hotkeys') or [])
                # [ALERT] 2026-08-28 FIX：log_last 包含殘留（MT5 log 舊「loaded successfully」記錄 — 新 account 安裝後顯示唔belongs to佢嘅 EA）
                # → log_last 只計「心跳 alive」嘅 EA（有新鮮心跳 = 真running）；冇心跳 = 舊記錄殘留 — 唔上報
                _log_e = _log_e & _hb_alive
                # [ALERT] 2026-09-03（VPS 搬遷 — user要求：配對庫 check 到 MT5 有嘅 EA）：加 local_eas
                # （本機 Experts/Scripts 有檔案嘅 EA — 唔止部署過/有心跳嗰啲 — 配對庫顯示全部本機 EA）
                _local_e = set(_snap_e.get('local_eas') or [])
                _agent_eas = sorted(set(list(_hb_e) + list(_log_e) + list(_hk_e) + list(_local_e)))
            else:
                # fallback：config EA（冇 agent 上報 — 單機向後兼容）
                _agent_eas = [k for k in config if not k.startswith('_') and not k.endswith(('_tf','_lot','_magic','_status')) and isinstance(config[k], str)]
        except Exception:
            pass
        return jsonify({"mappings": config, "all_symbols": get_account_symbols(), "timeframes": TIMEFRAMES, "runtime_status": runtime, "ea_stats": ea_stats, "market_closed": market_closed, "agent_eas": _agent_eas})
    else:
        data = request.json
        current_user.ea_config = json.dumps(data.get('mappings', {}))
        db.session.commit()
        return jsonify({"success": True})

@app.route('/api/ea-config/<ea_name>', methods=['DELETE'])
@login_required
def api_ea_config_delete(ea_name):
    """delete一個 EA 嘅配對
    [WARN] user要求（2026-08）：delete配對庫 EA = 連埋 MT5 圖表嘅 EA 一齊remove
    → 寫 pause_cmd 俾 watcher（auto_attach --remove remove圖表 EA）"""
    # [ALERT] 2026-08-22（user要求：UAC 檢測機制）：delete前檢查 UAC
    try:
        _uac_del = _detect_uac_server()
        if _uac_del:
            print(f"[ea-config-delete] [WARN] 偵測到 UAC 授權窗口: {_uac_del[0]} — delete會等 auto_attach UAC Gate 處理")
    except Exception:
        pass
    # [WARN] 系統file保護（Controller — 唔可以delete）
    if ea_name == 'Controller':
        return jsonify({"success": False, "error": "系統file（Controller）唔可以delete"}), 403
    # 確保 MT5 開住（remove圖表需要）
    ensure_mt5_running()
    # 寫 pause_cmd（watcher 用現有 process_pause_cmd remove圖表 EA — 重用機制）
    try:
        common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
        os.makedirs(common_files, exist_ok=True)
        cmd_path = os.path.join(common_files, f'pause_cmd_{ea_name}_{int(time.time())}.json')
        with open(cmd_path, 'w', encoding='utf-8') as f:
            json.dump({
                'ea_name': ea_name,
                'action': 'delete',
                # [FP] fingerprint（2026-08-31）：pause_cmd 帶 account
                'fingerprint': {
                    'account': current_user.username if (current_user and not current_user.is_anonymous) else 'unknown',
                    'created_by': f"{current_user.username if (current_user and not current_user.is_anonymous) else 'unknown'}/{ea_name}"
                }
            }, f, ensure_ascii=False)  # [ALERT] 2026-08-14：action=delete（watcher 顯示「delete」文字）
        print(f"[ea-config-delete] 圖表remove指令已排隊: {os.path.basename(cmd_path)}")
    except Exception as e:
        print(f"[ea-config-delete] pause_cmd writefailed: {e}")
    config = json.loads(current_user.ea_config or '{}')
    # 加去 _removed 列表
    removed = config.get('_removed', [])
    if ea_name not in removed:
        removed.append(ea_name)
    config['_removed'] = removed
    # delete相關 key
    for key in list(config.keys()):
        if key == ea_name or key.startswith(ea_name + '_'):
            del config[key]
    current_user.ea_config = json.dumps(config)
    db.session.commit()
    # [TARGET] delete → 釋放快捷鍵（2026-08 user設計：delete後快捷鍵一齊remove + 位置放返）
    try:
        release_hotkey(ea_name)
    except Exception:
        pass
    log_activity('ea_delete', f'{ea_name} 配對已delete（圖表 EA 已排隊remove）', ea=ea_name)
    return jsonify({"success": True})


@app.route('/api/ea-config/<ea_name>/purge', methods=['POST'])
def api_ea_config_purge(ea_name):
    """Watcher 專用：PC（MT5）delete EA 後，自動remove配對 config（配對庫immediately消失）
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
    log_activity('ea_delete', f'{ea_name} 已於PCdelete（配對已自動remove）', ea=ea_name)
    return jsonify({"success": True, "removed": ea_name})

@app.route('/api/ea-config/<ea_name>/status', methods=['POST'])
@login_required
def api_ea_config_status(ea_name):
    """[ALERT] 2026-08-14：設定 EA config 狀態（pausefailed時前端還原 — 唔好誤導「已pause」）"""
    try:
        config = json.loads(current_user.ea_config or '{}')
        new_status = (request.json or {}).get('status', 'running')
        config[ea_name + '_status'] = new_status
        current_user.ea_config = json.dumps(config)
        db.session.commit()
        return jsonify({"success": True, "status": new_status})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ea-config/<ea_name>/toggle', methods=['POST'])
@login_required
def api_ea_config_toggle(ea_name):
    """Toggle EA status：running ↔ paused
    pause = 真pause（remove圖表 EA — 寫 pause_cmd 俾 watcher 處理）
    恢復 = 重新deploy（寫 deploy_cmd）"""
    # [WARN] 系統file保護（Controller — 唔可以pause/恢復）
    if ea_name == 'Controller':
        return jsonify({"success": False, "error": "系統file（Controller）唔可以pause"}), 403
    # [WARN] user要求（2026-08）：每次操作 MT5 相關嘢，先偵測 MT5 有冇開 — 冇就開返
    ensure_mt5_running()
    config = json.loads(current_user.ea_config or '{}')
    current_status = config.get(ea_name + '_status', 'running')
    new_status = 'paused' if current_status == 'running' else 'running'
    config[ea_name + '_status'] = new_status
    current_user.ea_config = json.dumps(config)
    db.session.commit()
    log_activity('ea_toggle', f'{ea_name} {"pause" if new_status == "paused" else "恢復running"}', ea=ea_name)

    # 真pause/恢復：寫指令俾 watcher（watcher 有 desktop access 操作 MT5 GUI）
    try:
        import time as _ct
        common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
        os.makedirs(common_files, exist_ok=True)
        # [ALERT] 2026-08-14 FIX：pause/恢復都要彈warning視窗（before冇 — user投訴「網頁冇顯示warning視窗」）
        try:
            import json as _jtg
            _adir_tg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
            with open(os.path.join(_adir_tg, '.ai_control.show'), 'w', encoding='utf-8') as _f:
                _f.write(f'{"pause" if new_status == "paused" else "恢復"} {ea_name}')
            with open(os.path.join(_adir_tg, '.ai_control.steps'), 'w', encoding='utf-8') as _f:
                if new_status == 'paused':
                    _jtg.dump([
                        {'text': f'startpause {ea_name}', 'status': 'doing'},
                        {'text': 'Check chart (EA running?)', 'status': 'pending'},
                        {'text': 'Remove EA from chart (stop trading)', 'status': 'pending'},
                        {'text': 'Done — paused (config kept, can resume)', 'status': 'pending'},
                    ], _f, ensure_ascii=False)
                else:
                    _jtg.dump([
                        {'text': f'Start resume {ea_name}', 'status': 'doing'},
                        {'text': 'Create new chart', 'status': 'pending'},
                        {'text': f'Attach {ea_name}', 'status': 'pending'},
                        {'text': 'Verify running status', 'status': 'pending'},
                    ], _f, ensure_ascii=False)
        except Exception:
            pass
        # [ALERT] 2026-09-03（VPS 搬遷）：SocketIO push 俾遠端 agent
        try:
            _push_alert_socket(f'{"pause" if new_status == "paused" else "resume"} {ea_name}', [
                {'text': f'{"Pause" if new_status == "paused" else "Resume"} {ea_name}', 'status': 'doing'},
                {'text': 'Check chart (EA running?)', 'status': 'pending'},
            ])
        except Exception:
            pass
        if new_status == 'paused':
            # [WARN] 控制層方案（CONTROL_LAYER_DESIGN.md）：pause → 寫 ctrl_<ea>.json {"cmd":"stop"}
            # EA（已注入控制層）讀到 → ExpertRemove() 自己remove → 寫 stopped 心跳
            # [OK] 唔使 watcher / GUI 操作（MT5 唔會死）
            cmd_path = os.path.join(common_files, f'ctrl_{ea_name}.json')
            with open(cmd_path, 'w', encoding='utf-8') as f:
                json.dump({'cmd': 'stop'}, f, ensure_ascii=False)
            # 保留 pause_cmd 做後備（如果 EA 冇控制層 — watcher GUI remove）
            pause_path = os.path.join(common_files, f'pause_cmd_{ea_name}_{int(_ct.time())}.json')
            with open(pause_path, 'w', encoding='utf-8') as f:
                json.dump({'ea_name': ea_name, 'action': 'pause'}, f, ensure_ascii=False)  # [ALERT] 2026-08-14：action=pause（watcher 顯示「pause」文字）
        else:
            # 恢復 → 重新deploy（auto_attach attach）
            symbol = config.get(ea_name, 'EURUSD')
            tf = config.get(ea_name + '_tf', 'H1')
            magic = config.get(ea_name + '_magic', '240701')
            lot = config.get(ea_name + '_lot', 1.0)
            cmd_path = os.path.join(common_files, f'deploy_cmd_{ea_name}_{int(_ct.time())}.json')
            with open(cmd_path, 'w', encoding='utf-8') as f:
                json.dump({'ea_name': ea_name, 'symbol': symbol, 'tf': tf, 'magic': magic, 'lot': lot}, f, ensure_ascii=False)
    except Exception as e:
        print(f"[DEBUG] toggle cmd writefailed: {e}")

    # [ALERT] 2026-08-14 FIX：pause後確認 — EA 真係remove先話success（心跳停 + log「已stop」= remove）
    # （before只用心跳停判斷 — market close心跳都停 → 誤判success — user投訴「顯示pause但 MT5 冇pause」）
    if new_status == 'paused':
        try:
            import time as _tp
            _tp.sleep(4)  # 等 EA 讀 ctrl_（ExpertRemove）
            _sf_p = os.path.join(common_files, f'state_{ea_name}.json')
            _hb_p = os.path.join(common_files, f'hb_{ea_name}.txt')
            _hb_age = None
            if os.path.isfile(_sf_p):
                _hb_age = time.time() - os.path.getmtime(_sf_p)
            elif os.path.isfile(_hb_p):
                _hb_age = time.time() - os.path.getmtime(_hb_p)
            # log 確認（EA remove → log「已stop」）
            _log_stopped = False
            try:
                import glob as _glp
                _lgp = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
                _latp = None
                for _d4 in os.listdir(_lgp):
                    _lgd4 = os.path.join(_lgp, _d4, 'MQL5', 'Logs')
                    if os.path.isdir(_lgd4):
                        for _f4 in _glp.glob(os.path.join(_lgd4, '2026*.log')):
                            if _latp is None or os.path.getmtime(_f4) > os.path.getmtime(_latp):
                                _latp = _f4
                if _latp:
                    import re as _rep
                    _rawp = open(_latp, 'rb').read()
                    _txtp = None
                    for _encp in ('utf-16', 'utf-8', 'cp1252'):
                        try:
                            _txtp = _rawp.decode(_encp)
                            break
                        except Exception:
                            continue
                    if _txtp:
                        _log_stopped = any(
                            _rep.search(rf'{re.escape(ea_name)} \([A-Za-z0-9._]+,[A-Z0-9]+\)\s+[^\n]*(已stop|removed)', _ln)
                            for _ln in _txtp.splitlines())
            except Exception:
                pass
            _hb_stopped = _hb_age is not None and _hb_age >= 30
            if not _hb_stopped or not _log_stopped:
                # 心跳仲新鮮 或 log 冇「已stop」（market close心跳停 — EA 可能仲running）→ pausefailed
                print(f"[toggle] [WARN] pause {ea_name} 確認failed（心跳停={_hb_stopped} log已stop={_log_stopped}）", flush=True)
                return jsonify({"success": False, "status": "paused_failed", "error": f"pausefailed — EA 仍在圖表（可能未更新pause支援）。請重新deploy {ea_name} 後再試。"}), 409
            print(f"[toggle] [OK] pause {ea_name} 確認success（心跳停 + log 已stop）", flush=True)
        except Exception as _te:
            print(f"[toggle] [WARN] pause確認exception（照返回success）: {_te}", flush=True)

    return jsonify({"success": True, "status": new_status})

# === API: Dashboard ===
# [WARN] user要求（2026-08）：每次操作 MT5 相關嘢，先偵測 MT5 有冇開 — 冇就開返
MT5_EXE_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"

def ensure_mt5_running():
    """確保 MT5 開住 — 冇就開返（等最多 30 秒 process 出現）
    所有會操作 MT5 嘅 API（install-local / deploy / toggle / remove-local / retry-compile）開頭 call"""
    import subprocess as _sp
    try:
        # [WARN] 用 bytes 檢查（唔好 text=True）— tasklist 輸出係 GBK/中文，MSYS UTF-8 locale decode 會炸
        r = _sp.run('tasklist /FI "IMAGENAME eq terminal64.exe" /NH', shell=True, capture_output=True, timeout=5)
        if b'terminal64' in r.stdout:
            return True
        # [ALERT] 2026-09-01 DEBUG：記錄邊個 call（搵「冇操作都開 MT5」源頭）
        import traceback as _tb_dbg
        print(f"[ensure_mt5] MT5 未開啟 — 自動start...（caller: {_tb_dbg.format_stack(limit=6)[-2].strip()}）", flush=True)
        try:
            _sp.Popen([MT5_EXE_PATH])
        except Exception as e:
            print(f"[ensure_mt5] startfailed: {e}")
            return False
        # 等最多 30 秒 MT5 process 出現（登入由 MT5 自動處理）
        for _ in range(30):
            time.sleep(1)
            try:
                r2 = _sp.run('tasklist /FI "IMAGENAME eq terminal64.exe" /NH', shell=True, capture_output=True, timeout=5)
                if b'terminal64' in r2.stdout:
                    print("[ensure_mt5] MT5 已start（登入中）")
                    return True
            except Exception:
                pass
        print("[ensure_mt5] MT5 startwaittimeout（30 秒）")
        return False
    except Exception as e:
        print(f"[ensure_mt5] 偵測failed: {e}")
        return False


# Auto-trade status: background thread refresh so dashboard never blocks
_auto_trade_cache = {"result": [], "timestamp": 0}
_auto_trade_lock = threading.Lock()
_last_deploy_time = {}  # [ALERT] 2026-08-12：防重複deploy（同一 EA 30 秒內唔可以再 deploy）

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
    
    # Also refresh account info（[ALERT] 2026-08-12 修：唔直接 init MT5 — detector 已持connect → read 佢嘅 auto_trade_status.json）
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
                # [ALERT] 2026-08-26 FIX（多機污染）：唔好再寫 agent.account_info！
                # before save server local account 落「觸發 refresh 嗰個 user」嘅 agent → 新account被write 5053721681 → 顯示返舊機
                # → agent.account_info 只可以由「自己部機嘅 agent 上報」（SocketIO agent_sync）寫 — 每機獨立
    except Exception as e:
        print(f"[DEBUG] auto_trade_status read failed: {e}")
        pass

def _agent_live_status(agent):
    """[ALERT] 2026-08-27：Agent 真實狀態（last_seen 新鮮 = online — 唔淨係睇 status 欄）
    agent 被 kill → socket 斷 → 冇 sync → last_seen 舊 → offline（防假綠燈）
    [ALERT] FIX：last_seen 係 datetime.utcnow()（naive UTC）— timestamp() 會當本地時區 → 錯 8 小時
    → 用 datetime.utcnow() 直接比較（都係 naive UTC — 無歧義）
    """
    try:
        if agent and agent.status in ('connected', 'online'):
            if agent.last_seen:
                from datetime import datetime as _dt_ls, timezone as _tz_ls
                _now_utc = _dt_ls.utcnow()
                _ls = agent.last_seen
                # 兼容：如果 last_seen 係 aware（有 tzinfo）→ 轉 UTC；naive → 直接當 UTC
                if _ls.tzinfo is not None:
                    _ls = _ls.astimezone(_tz_ls.utc).replace(tzinfo=None)
                if (_now_utc - _ls).total_seconds() < 60:
                    return 'connected'
            return 'offline'
    except Exception:
        pass
    return agent.status if agent else 'offline'


@app.route('/api/dashboard')
@login_required
def api_dashboard():
    agent = Agent.query.filter_by(user_id=current_user.id).first()
    # [ALERT] 2026-08-28 FIX：user 可能冇 agent（網站remove咗）→ 唔 crash — 返回空資料（前端顯示「未安裝」）
    if agent is None:
        return jsonify({
            "agent_id": None, "agent_token": None, "status": "offline",
            "account": {}, "positions": [], "ea_heartbeats": {},
            "auto_trade_ea_count": 0, "auto_trade_status": [], "last_seen": None
        })
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
        # [ALERT] 2026-08-12：first call → sync（background thread fails silently）
        if _auto_trade_cache["timestamp"] == 0:
            _refresh_auto_trade_cache(current_user)
        else:
            import threading as _th
            _th.Thread(target=_refresh_auto_trade_cache, args=(current_user,), daemon=True).start()
    
    with _auto_trade_lock:
        cache_result = _auto_trade_cache["result"]
        _global_acc = _auto_trade_cache.get("account_info", {})
    
    # [ALERT] 2026-08-26 FIX v2（user實測：新 account 依然見到 5053721681）：
    # → 唔可以 fallback 全局 cache（_global_acc = server local MT5 — 永遠係舊機帳號）
    # → 只顯示「自己 agent 上報嘅 account_info」（每機獨立）— 未上報 → 空（前端顯示「未connect」）
    _acc_dis = account if account.get('login') else {}
    return jsonify({
        "status": _agent_live_status(agent),
        "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
        "account": _acc_dis,
        "bound_account": current_user.bound_account or '',
        "account_matched": bool(current_user.bound_account and _acc_dis.get('login') == current_user.bound_account),
        "positions": positions,
        "agent_id": agent.agent_id,
        "agent_token": agent.agent_token or '',
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
def _agent_trades_raw():
    """[ALERT] 2026-08-26（multi-user Phase 3）：攞當前user agent 上報嘅逐單交易（每機獨立）
    有 snapshot → 用 trades_raw; 冇 → None（server fallback 讀local）
    """
    try:
        agent = Agent.query.filter_by(user_id=current_user.id).first()
        if agent and agent.files_snapshot:
            _snap = json.loads(agent.files_snapshot or '{}')
            _tr = _snap.get('trades_raw') if isinstance(_snap, dict) else None
            if _tr:
                return _tr
    except Exception:
        pass
    return None


@app.route('/api/analysis')
@login_required
def api_analysis():
    agent = Agent.query.filter_by(user_id=current_user.id).first()
    deals_data = json.loads(agent.deals or '[]')

    # [ALERT] 2026-08-26（multi-user Phase 3）：agent 上報 trades_raw 優先（每機獨立 — 支持多機）
    # → 有 snapshot trades_raw → 直接用（唔讀local Common/Files）
    _snap_trades = _agent_trades_raw()
    _use_snap_tr = _snap_trades is not None
    if _use_snap_tr:
        try:
            _cfg_tr = json.loads(current_user.ea_config or '{}')
            for _ea_tr, _recs_tr in _snap_trades.items():
                _m_tr = str(_cfg_tr.get(_ea_tr + '_magic', ''))
                for _r_tr in _recs_tr:
                    if 'profit' in _r_tr:
                        deals_data.append({
                            "magic": int(_m_tr) if str(_m_tr).isdigit() else (_r_tr.get('magic') or 0),
                            "symbol": _r_tr.get('symbol', ''),
                            "profit": _r_tr.get('profit', 0),
                            "time": _r_tr.get('time', 0),
                        })
        except Exception:
            pass

    # [ALERT] 2026-08-21：合併 EA 自寫逐單明細（trades_<EA>.json — 完整歷史）
    # MT5 Python history API 讀唔到新 deals（build 6120 caching）→ agent.deals 得舊嘢
    # → 讀 trades_<EA>.json（EA AppendTrade/RebuildTradesFile 寫）合併做分析數據源
    # [ALERT] 2026-08-26（Phase 3）：agent 已上報 trades_raw → 唔再讀local（避免雙重）
    if not _use_snap_tr:
        try:
            import glob as _gl_a
            _cf_a = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
            # 搵返 EA 名 → magic 對應
            _ea_magic_map = {}
            try:
                import sqlite3 as _sq_a
                _db_a = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'instance', 'mt5cloud.db')
                _c_a = _sq_a.connect(_db_a)
                _r_a = _c_a.execute('SELECT ea_config FROM user WHERE id=?', (current_user.id,)).fetchone()
                _c_a.close()
                if _r_a:
                    _cfg_a = json.loads(_r_a[0] or '{}')
                    for _k_a, _v_a in _cfg_a.items():
                        if not _k_a.startswith('_') and not _k_a.endswith(('_tf', '_lot', '_magic', '_status')) and isinstance(_v_a, str):
                            _ea_magic_map[_k_a] = str(_cfg_a.get(_k_a + '_magic', ''))
            except Exception:
                pass
            for _f_a in _gl_a.glob(os.path.join(_cf_a, 'trades_*.json')):
                _ea_a = os.path.basename(_f_a)[7:-5]  # trades_<EA>.json → <EA>
                _magic_a = _ea_magic_map.get(_ea_a, '')
                if not _magic_a:
                    continue
                try:
                    with open(_f_a, 'rb') as _fh_a:
                        _raw_a = _fh_a.read()
                    _txt_a = None
                    for _enc_a in ('utf-8', 'utf-16'):
                        try:
                            _txt_a = _raw_a.decode(_enc_a)
                            break
                        except Exception:
                            continue
                    if _txt_a:
                        for _line_a in _txt_a.splitlines():
                            _line_a = _line_a.strip()
                            if not _line_a:
                                continue
                            try:
                                _td_a = json.loads(_line_a)
                                if 'profit' in _td_a:
                                    deals_data.append({
                                        "magic": int(_magic_a),
                                        "symbol": _cfg_a.get(_ea_a, ''),
                                        "profit": _td_a.get('profit', 0),
                                        "time": _td_a.get('time', 0),
                                    })
                            except Exception:
                                continue
                except Exception:
                    pass
        except Exception:
            pass

    if not deals_data:
        return jsonify({"error":"No data yet"})

    # Per-EA by (magic, symbol)
    per_ea = defaultdict(lambda: {"trades":0,"profit":0,"wins":0,"losses":0})
    for d in deals_data:
        # [ALERT] 2026-08-21：過濾 magic 0（平台手動交易/存款 — 唔係 EA 交易，唔應該顯示喺 EA 統計）
        if not d.get('magic') or d.get('magic') == 0:
            continue
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

    # [ALERT] 2026-08-21：EA 名對應（correlation matrix 顯示 EA 名 — user易睇）
    # [ALERT] 2026-08-26 FIX v3（user：「點解仲顯示 Magic#240701 而唔係 EA 名」）：
    # v0.10.78 行內人做法 magic=EA 身份 → (magic,symbol) match 唔到（舊 symbol 記錄）都應該顯示 EA 名
    # → 雙層對應：①精確 (magic,symbol) ②fallback 淨 magic（搵 config 第一隻用呢個 magic 嘅 EA）
    ea_name_by_key = {}
    _magic_to_ea = {}
    try:
        import sqlite3 as _sq_c
        _db_c = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'instance', 'mt5cloud.db')
        _c_c = _sq_c.connect(_db_c)
        _r_c = _c_c.execute('SELECT ea_config FROM user WHERE id=?', (current_user.id,)).fetchone()
        _c_c.close()
        if _r_c:
            _cfg_c = json.loads(_r_c[0] or '{}')
            for _k_c, _v_c in _cfg_c.items():
                if not _k_c.startswith('_') and not _k_c.endswith(('_tf', '_lot', '_magic', '_status')) and isinstance(_v_c, str):
                    _mag_c = str(_cfg_c.get(_k_c + '_magic', ''))
                    _mk_c = f"{_mag_c}_{_v_c}"
                    ea_name_by_key[_mk_c] = _k_c
                    # fallback 表：magic → EA 名（第一次遇到嗰隻 — config 順序）
                    if _mag_c and _mag_c not in _magic_to_ea:
                        _magic_to_ea[_mag_c] = _k_c
        # 對 matrix keys 補 fallback（淨 magic match）
        for _ek_n in list(ea_name_by_key.keys()):
            pass
    except Exception:
        pass
    # 處理：所有 possible key（magic_symbol）都試 exact，唔得就用 magic fallback → 喺 matrix build 前 resolve
    def _resolve_ea_name(_ek_raw):
        if _ek_raw in ea_name_by_key:
            return ea_name_by_key[_ek_raw]
        _m_part = _ek_raw.split('_')[0]
        return _magic_to_ea.get(_m_part, '')

    # Correlation
    daily_pnl = defaultdict(lambda: defaultdict(float))
    for d in deals_data:
        if not d.get('magic') or d.get('magic') == 0:
            continue
        # [ALERT] 2026-08-21：trades json 嘅 time 係 epoch（數字）— 轉做 YYYY-MM-DD
        _t_val = d.get('time', '')
        if isinstance(_t_val, (int, float)) and _t_val > 1000000000:
            try:
                _date_key = datetime.fromtimestamp(_t_val).strftime('%Y-%m-%d')
            except Exception:
                _date_key = str(_t_val)[:10]
        else:
            _date_key = str(_t_val)[:10]
        key = f"{d['magic']}_{d['symbol']}"
        daily_pnl[key][_date_key] += d['profit']

    ea_keys = sorted(daily_pnl.keys())
    all_dates = sorted(set(d for dates in daily_pnl.values() for d in dates.keys()))
    matrix = {ek:[daily_pnl[ek].get(dt,0) for dt in all_dates] for ek in ea_keys}

    def pearson(x,y):
        n=len(x); 
        if n<3: return 0
        sx=sum(x);sy=sum(y);sxx=sum(v*v for v in x);syy=sum(v*v for v in y);sxy=sum(x[i]*y[i] for i in range(n))
        d=math.sqrt((n*sxx-sx*sx)*(n*syy-sy*sy))
        return (n*sxy-sx*sy)/d if d!=0 else 0

    # [ALERT] 2026-08-21：correlation keys 用 EA 名（前端顯示）
    # [ALERT] 2026-08-26 FIX v2（user要求：「名 + Magic Number」— 方便 cross-check MT5）：EA 名 + (magic) 括號
    corr_keys_display = []
    for _ek in ea_keys:
        _ea_nm = _resolve_ea_name(_ek)
        if _ea_nm:
            _mag_part = _ek.split('_')[0]
            corr_keys_display.append(f"{_ea_nm} ({_mag_part})")
        else:
            # [ALERT] 2026-08-26：冇 EA 名（歷史 trades 同 config 唔 match）→ 顯示 Magic#<magic> (<symbol>)
            _mk_part = _ek.split('_')[0] if '_' in _ek else _ek
            _sym_part = _ek.split('_', 1)[1] if '_' in _ek else ''
            corr_keys_display.append(f"Magic#{_mk_part} ({_sym_part})" if _sym_part else f"Magic#{_mk_part}")

    corr_matrix = []
    for i1, ek1 in enumerate(ea_keys):
        row = {"ea": corr_keys_display[i1]}
        for i2, ek2 in enumerate(ea_keys):
            row[corr_keys_display[i2]] = round(pearson(matrix[ek1], matrix[ek2]), 2)
        corr_matrix.append(row)

    # Filter magic 0 for summary too (platform trades, not EA)
    ea_deals = [d for d in deals_data if d.get('magic') and d.get('magic') != 0]
    total_profit = sum(d['profit'] for d in ea_deals)
    wins = sum(1 for d in ea_deals if d['profit']>0)
    losses = sum(1 for d in ea_deals if d['profit']<0)
    wr = round(wins/(wins+losses)*100,2) if (wins+losses)>0 else 0

    return jsonify({
            "summary":{"total_trades":len(ea_deals),"wins":wins,"losses":losses,
                       "win_rate":wr,"total_profit":round(total_profit,2)},
            "per_ea": per_ea_list,
            "per_ea_by_symbol": per_ea_by_symbol,
            "per_ea_by_magic_symbol": per_ea_by_magic_symbol,
            "all_magics": all_magics,
            "correlation_matrix": corr_matrix,
            "correlation_keys": corr_keys_display,
            "daily_pnl": {disp: dict(daily_pnl[k]) for k, disp in zip(ea_keys, corr_keys_display)}
        })


@app.route('/api/trade-report')
@login_required
def api_trade_report():
    """交易歷史報告（account層面 — 全部交易 + 統計）
    [ALERT] 2026-08-26 新增（user要求：下載 MT5 交易歷史報告 HTML / popup 睇）
    — 數據源：agent.deals（MT5 API 收集）+ trades_<EA>.json（EA 逐單）合併
    """
    agent = Agent.query.filter_by(user_id=current_user.id).first()
    deals_data = json.loads(agent.deals or '[]')

    # [ALERT] 2026-08-26（multi-user Phase 3）：agent 上報 trades_raw 優先（每機獨立）
    try:
        _snap_tr2 = _agent_trades_raw()
        if _snap_tr2:
            _cfg_tr2 = json.loads(current_user.ea_config or '{}')
            for _ea2, _recs2 in _snap_tr2.items():
                _m2 = str(_cfg_tr2.get(_ea2 + '_magic', ''))
                for _r2 in _recs2:
                    if 'profit' in _r2:
                        deals_data.append({
                            "time": _r2.get('time', 0),
                            "symbol": _r2.get('symbol', ''),
                            "profit": _r2.get('profit', 0),
                            "magic": _r2.get('magic') or _m2,
                            "type": _r2.get('type', ''),
                            "volume": _r2.get('volume', 0),
                            "price": _r2.get('price', 0),
                            "ticket": f"{_ea2}_{len(deals_data)}",
                            "comment": f"(EA {_ea2})",
                            "ea_name": _ea2
                        })
    except Exception:
        pass

    # EA 名對應（magic → EA 名）
    ea_name_map = {}
    try:
        import sqlite3 as _sq_t
        _db_t = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'instance', 'mt5cloud.db')
        _c_t = _sq_t.connect(_db_t)
        _r_t = _c_t.execute('SELECT ea_config FROM user WHERE id=?', (current_user.id,)).fetchone()
        _c_t.close()
        if _r_t:
            _cfg_t = json.loads(_r_t[0] or '{}')
            for _k_t, _v_t in _cfg_t.items():
                if not _k_t.startswith('_') and not _k_t.endswith(('_tf', '_lot', '_magic', '_status')) and isinstance(_v_t, str):
                    _m_t = str(_cfg_t.get(_k_t + '_magic', ''))
                    if _m_t and _m_t not in ea_name_map:
                        ea_name_map[_m_t] = _k_t
    except Exception:
        pass

    # 合併 trades_<EA>.json（EA 自寫逐單 — 補充 agent.deals 冇嘅新交易）
    merged = []
    seen_tickets = set()
    try:
        import glob as _gl_t
        _cf_t = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
        for _f_t in _gl_t.glob(os.path.join(_cf_t, 'trades_*.json')):
            _ea_t = os.path.basename(_f_t)[7:-5]
            try:
                with open(_f_t, 'rb') as _fh_t:
                    _raw_t = _fh_t.read()
                _txt_t = None
                for _enc_t in ('utf-8', 'utf-16'):
                    try:
                        _txt_t = _raw_t.decode(_enc_t); break
                    except Exception:
                        continue
                if _txt_t:
                    for _line_t in _txt_t.splitlines():
                        _line_t = _line_t.strip()
                        if not _line_t: continue
                        try:
                            _td_t = json.loads(_line_t)
                            if 'profit' in _td_t:
                                _tk = _td_t.get('ticket') or _td_t.get('time') or f"{_ea_t}_{len(merged)}"
                                seen_tickets.add(str(_tk))
                                merged.append({
                                    "time": _td_t.get('time') or _td_t.get('ts') or 0,
                                    "symbol": _td_t.get('symbol', ''),
                                    "profit": _td_t.get('profit', 0),
                                    "magic": _td_t.get('magic', ''),
                                    "type": _td_t.get('type', ''),
                                    "volume": _td_t.get('volume', 0),
                                    "price": _td_t.get('price', 0),
                                    "ticket": _tk,
                                    "comment": f"(EA {_ea_t})",
                                    "ea_name": _ea_t
                                })
                        except Exception:
                            continue
            except Exception:
                continue
    except Exception:
        pass

    # agent.deals（跳過已見 ticket）
    for d in deals_data:
        _tk_d = d.get('ticket') or d.get('time') or 0
        if str(_tk_d) in seen_tickets:
            continue
        merged.append({
            "time": d.get('time', 0),
            "symbol": d.get('symbol', ''),
            "profit": d.get('profit', 0),
            "magic": d.get('magic', ''),
            "type": d.get('type', ''),
            "volume": d.get('volume', 0),
            "price": d.get('price', 0),
            "ticket": _tk_d,
            "comment": d.get('comment', ''),
            "ea_name": ea_name_map.get(str(d.get('magic', '')), '')
        })

    # 排序（時間）
    merged.sort(key=lambda x: x.get('time', 0))

    # 統計
    valid = [d for d in merged if d.get('profit') != 0]
    total_profit = round(sum(d.get('profit', 0) for d in valid), 2)
    wins = sum(1 for d in valid if d.get('profit', 0) > 0)
    losses = sum(1 for d in valid if d.get('profit', 0) < 0)
    win_rate = round(wins / (wins + losses) * 100, 2) if (wins + losses) > 0 else 0

    return jsonify({
        "trades": merged,
        "summary": {
            "total": len(merged),
            "valid": len(valid),
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_profit": total_profit
        }
    })


@app.route('/api/ea-report')
@login_required
def api_ea_report():
    """EA 診斷報告：equity curve + 詳細 stats
    [ALERT] 2026-08-21：加 EA 自寫統計 fallback（MT5 Python history API 讀唔到新 deals → agent.deals 得舊嘢）
    → 讀 state_<EA>.json（TestTrades 自己 track 真實 trades/wins/losses/profit）
    """
    magic = request.args.get('magic', '')
    symbol = request.args.get('symbol', '')
    if not magic:
        return jsonify({"error": "需要 magic"}), 400

    agent = Agent.query.filter_by(user_id=current_user.id).first()
    deals_data = json.loads(agent.deals or '[]')

    # 過濾指定 EA（by magic — 唔理 symbol，EA config 冇存 symbol）
    ea_deals = [d for d in deals_data
                if str(d.get('magic', '')) == str(magic)
                and d.get('profit', 0) != 0]

    # [ALERT] 2026-08-21：讀 EA 自寫統計（state_<EA>.json — TestTrades 寫真實 trades/wins/losses/profit）
    # 因為 MT5 Python history API 讀唔到新 deals（build 6120 caching）→ agent.deals 冇最新數據
    ea_stats = {}
    try:
        import glob as _gl
        _cf = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
        for _f in _gl.glob(os.path.join(_cf, 'state_*.json')):
            try:
                with open(_f, 'rb') as _fh:
                    _raw = _fh.read()
                try:
                    _sd = json.loads(_raw.decode('utf-8'))
                except Exception:
                    _sd = json.loads(_raw.decode('utf-16'))
                if isinstance(_sd, dict) and _sd.get('status') == 'running' and 'trades' in _sd:
                    ea_stats[_sd.get('ea', '')] = _sd
            except Exception:
                pass
    except Exception:
        pass

    # 搵返 EA 名（by magic — 從 config）
    ea_name = ''
    try:
        import sqlite3 as _sq
        _db = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'instance', 'mt5cloud.db')
        _c = _sq.connect(_db)
        _r = _c.execute('SELECT ea_config FROM user WHERE id=?', (current_user.id,)).fetchone()
        _c.close()
        if _r:
            _cfg = json.loads(_r[0] or '{}')
            for _k, _v in _cfg.items():
                if not _k.startswith('_') and not _k.endswith(('_tf', '_lot', '_magic', '_status')) and isinstance(_v, str):
                    if str(_cfg.get(_k + '_magic', '')) == str(magic):
                        ea_name = _k
                        break
    except Exception:
        pass

    # 如果 agent.deals 冇數據 → 用 EA 自寫統計（真實數據）
    # [ALERT] 2026-08-21 FIX：唔好靠 state json 嘅 stats（系統心跳注入覆寫咗 state json 格式 — 得 ea/status/ts）
    # → 用 trades_<EA>.json（AppendTrade 寫嘅逐單明細 — 冇衝突）計全部統計
    stat = ea_stats.get(ea_name) if ea_name else None

    # [ALERT] 2026-08-21：讀 trades_<EA>.json（EA 寫嘅逐單明細 — JSONL）→ 畫 equity curve / distribution / monthly
    # [WARN] MQL5 FileWriteString 寫 UTF-16 LE（BOM）— 要 fallback decode
    trade_list = []
    try:
        _tf = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files', f'trades_{ea_name}.json')
        if os.path.isfile(_tf):
            with open(_tf, 'rb') as _fh:
                _raw_bytes = _fh.read()
            _txt = None
            for _enc in ('utf-8', 'utf-16'):
                try:
                    _txt = _raw_bytes.decode(_enc)
                    break
                except Exception:
                    continue
            if _txt:
                for _line in _txt.splitlines():
                    _line = _line.strip()
                    if not _line:
                        continue
                    try:
                        _td = json.loads(_line)
                        if 'profit' in _td:
                            trade_list.append(_td)
                    except Exception:
                        continue
    except Exception:
        pass

    # [ALERT] 2026-08-26 FIX v2（報告顯示舊數據問題）：優先 trades_<EA>.json（EA 逐單真實記錄 — 最準）
    # → before `if not ea_deals`（agent.deals 冇數據先行詳細計算）— 但 agent.deals 有舊記錄（舊 symbol/magic）→ 報告顯示舊嘢
    # → 改：只要有 trade_list（trades_<EA>.json 有記錄）→ 一定用佢計（唔理 agent.deals）
    if trade_list or (not ea_deals and stat):

        # Equity curve（cumulative）+ distribution + monthly
        equity_curve = []
        dist = {"bins": ["0-50", "50-100", "100-200", "200-500", "500+"], "wins": [0]*5, "losses": [0]*5}
        monthly_pnl = {}
        cum = 0.0
        # [ALERT] 2026-08-21 FIX：trade_list 有數據 → 用逐單明細計全部統計（最準確）；冇 → fallback state stats
        if trade_list:
            trade_list.sort(key=lambda x: x.get('time', 0))
            for _t in trade_list:
                _p = _t.get('profit', 0)
                cum += _p
                equity_curve.append({
                    "time": datetime.fromtimestamp(_t.get('time', 0)).strftime('%Y-%m-%d %H:%M') if _t.get('time') else '',
                    "profit": round(_p, 2),
                    "cumulative": round(cum, 2)
                })
                # distribution
                amt = abs(_p)
                idx = 4 if amt >= 500 else (3 if amt >= 200 else (2 if amt >= 100 else (1 if amt >= 50 else 0)))
                if _p > 0: dist['wins'][idx] += 1
                else: dist['losses'][idx] += 1
                # monthly
                if _t.get('time'):
                    ym = datetime.fromtimestamp(_t['time']).strftime('%Y-%m')
                    monthly_pnl[ym] = monthly_pnl.get(ym, 0) + round(_p, 2)
            # stats from trades
            profits = [_t.get('profit', 0) for _t in trade_list]
            total = len(profits)
            wins = sum(1 for p in profits if p > 0)
            losses = sum(1 for p in profits if p < 0)
            total_profit = sum(profits)
            win_sum = sum(p for p in profits if p > 0)
            loss_sum = sum(p for p in profits if p < 0)
            win_rate = round(wins / (wins + losses) * 100, 2) if (wins + losses) > 0 else 0
            avg_win = round(win_sum / wins, 2) if wins > 0 else 0
            avg_loss = round(loss_sum / losses, 2) if losses > 0 else 0
            pf = round(abs(win_sum / loss_sum), 2) if loss_sum != 0 else float('inf')
            # max drawdown
            peak = -float('inf')
            max_dd = 0
            max_dd_pct = 0
            for _e in equity_curve:
                if _e['cumulative'] > peak:
                    peak = _e['cumulative']
                dd = peak - _e['cumulative']
                if dd > max_dd:
                    max_dd = round(dd, 2)
                    max_dd_pct = round(dd / peak * 100, 2) if peak > 0 else 0
        elif stat:
            total = stat.get('trades', 0)
            wins = stat.get('wins', 0)
            losses = stat.get('losses', 0)
            total_profit = stat.get('profit', 0)
            win_sum = stat.get('win_sum', 0)
            loss_sum = stat.get('loss_sum', 0)
            win_rate = round(wins / (wins + losses) * 100, 2) if (wins + losses) > 0 else 0
            avg_win = round(win_sum / wins, 2) if wins > 0 else 0
            avg_loss = round(loss_sum / losses, 2) if losses > 0 else 0
            pf = round(abs(win_sum / loss_sum), 2) if loss_sum != 0 else float('inf')
            max_dd = 0
            max_dd_pct = 0
        else:
            total = 0; wins = 0; losses = 0; total_profit = 0
            win_rate = 0; avg_win = 0; avg_loss = 0; pf = 0
            max_dd = 0; max_dd_pct = 0

        return jsonify({
            "magic": magic,
            "symbol": symbol or '—',
            "ea_name": ea_name,
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_profit": round(total_profit, 2),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": pf,
            "max_drawdown": max_dd,
            "max_drawdown_pct": max_dd_pct,
            "equity_curve": equity_curve[-100:],
            "distribution": dist,
            "monthly_pnl": monthly_pnl,
            "source": "ea_stats",
            "note": "數據來自 EA 自寫統計（MT5 history API 讀唔到新 deals — 已知限制）"
        })

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
    """deploy監控器回報 deploy 結果"""
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
EA_LIBRARY_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'ea_library'))
def _ea_magic_from_source(mq5_path):
    """[ALERT] 2026-09-01 FIX（user實測：配對庫 magic 亂 — install-local default 240701 冇讀 EA 內部）：
    掃 .mq5 源碼攞 InpMagic（input int InpMagic = XXXX）→ 配對時用正確 magic"""
    try:
        if not os.path.isfile(mq5_path):
            return '240701'
        txt = open(mq5_path, encoding='utf-8', errors='replace').read()
        m = re.search(r'InpMagic\s*=\s*(\d+)', txt)
        if m:
            return m.group(1)
    except Exception:
        pass
    return '240701'


UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'user_ea'))
COMMUNITY_EA_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'community_ea'))

# 確保direxists
os.makedirs(EA_LIBRARY_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(COMMUNITY_EA_DIR, exist_ok=True)

@app.route('/api/ea-library')
def api_ea_library():
    """返回 EA 庫列表（平台提供 + 社群提供 + user上傳）+ local有冇 .ex5（即時判斷，唔靠 detector）"""
    # [ALERT] 2026-08-19 FIX：加 local_has — server 直接 check local MT5 Experts/ 有冇 <base>.ex5
    # before前端靠 detector ea_inventory.json（延遲）→ 配對後「local冇file」殘留，要 refresh 先啱
    # 呢度直接 filesystem check → 配對done後即時準確
    # [ALERT] 2026-09-03（VPS 搬遷 — 方案2）：server（VPS）冇 MT5 — 改讀 agent 上報嘅 files_snapshot.local_eas
    local_bases = set()
    try:
        if current_user.is_authenticated:
            _agt_lib = Agent.query.filter_by(user_id=current_user.id).first()
            if _agt_lib and _agt_lib.files_snapshot:
                _snap_lib = json.loads(_agt_lib.files_snapshot)
                _le_lib = _snap_lib.get('local_eas', [])
                if isinstance(_le_lib, list):
                    local_bases = set(_le_lib)
    except Exception:
        pass
    # fallback：如果冇 agent snapshot（本機模式 — server 有 MT5）→ 直接 filesystem
    if not local_bases:
        _mt5dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        try:
            for _td in os.listdir(_mt5dir) if os.path.isdir(_mt5dir) else []:
                for _sub in ('MQL5\\Experts', 'MQL5\\Scripts'):
                    _d = os.path.join(_mt5dir, _td, *_sub.split('\\'))
                    if os.path.isdir(_d):
                        for _fn in os.listdir(_d):
                            if _fn.endswith('.ex5'):
                                local_bases.add(os.path.splitext(_fn)[0])
        except Exception:
            pass
    files = []
    # 平台提供嘅 EA
    if os.path.isdir(EA_LIBRARY_DIR):
        for f in sorted(os.listdir(EA_LIBRARY_DIR)):
            if f.endswith('.mq5'):
                path = os.path.join(EA_LIBRARY_DIR, f)
                size = os.path.getsize(path)
                base = os.path.splitext(f)[0]
                files.append({"name": f, "size": f"{size/1024:.1f} KB", "type": "official", "author": "Platform", "local_has": base in local_bases})
    # 社群提供嘅 EA（Developer 上傳，所有人都睇到）
    if os.path.isdir(COMMUNITY_EA_DIR):
        for f in sorted(os.listdir(COMMUNITY_EA_DIR)):
            if f.endswith('.mq5'):
                path = os.path.join(COMMUNITY_EA_DIR, f)
                size = os.path.getsize(path)
                base = os.path.splitext(f)[0]
                files.append({"name": f, "size": f"{size/1024:.1f} KB", "type": "community", "author": "Dev", "local_has": base in local_bases})
    # user上傳嘅 EA（只有自己睇到）
    if current_user.is_authenticated:
        user_dir = os.path.join(UPLOAD_DIR, current_user.username)
        if os.path.isdir(user_dir):
            for f in sorted(os.listdir(user_dir)):
                if f.endswith(('.mq5','.ex5')):
                    path = os.path.join(user_dir, f)
                    size = os.path.getsize(path)
                    base = os.path.splitext(f)[0]
                    files.append({"name": f, "size": f"{size/1024:.1f} KB", "type": "user", "author": current_user.username, "local_has": base in local_bases})
    return jsonify({"files": files, "count": len(files)})


@app.route('/api/ea-library/refresh', methods=['POST'])
@login_required
def api_ea_library_refresh():
    """[ALERT] 2026-08-11：配對庫「重新整理」— warning視窗流程（重新整理緊 → success確定 / failed紅色+原因+確定）
    重新整理唔係危險操作 → failed都係「確定」（唔需要緊急stop）
    用 control_guard acquire/release（寫 .ai_control.show + ai_control.json active — 網頁+PC版都彈）"""
    import json as _jrf
    _adir_rf = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
    # acquire（warning視窗彈 — 網頁 modal + PC版）
    _cg = None
    try:
        sys.path.insert(0, _adir_rf)
        import control_guard as _cg
        _cg.acquire('重新整理配對庫')
    except Exception:
        _cg = None
    try:
        # [ALERT] 2026-08-29 FIX（PC版warning視窗冇彈 — 重新整理流程）：改用 _write_ai_flags 雙寫
        # before淨寫開發dir（_adir_rf）→ alert_worker（讀 TradotcomAgent）冇 flag → PC版唔彈
        _write_ai_flags('重新整理配對庫', [
            {'text': 'Start refresh', 'status': 'doing'},
            {'text': 'Scan local EA files', 'status': 'pending'},
            {'text': 'Clean up stale pairing settings', 'status': 'pending'},
            {'text': 'Sync pairing settings', 'status': 'pending'},
            {'text': 'Refresh local running status', 'status': 'pending'},
            {'text': 'Refresh EA library', 'status': 'pending'},
            {'text': 'Done — refresh complete', 'status': 'pending'},
        ])
    except Exception:
        pass
    # [ALERT] 2026-08-12：步驟 1 done + 步驟 2 doing（掃描local EA — 停留 0.8s user見到）
    try:
        import time as _tw2
        _tw2.sleep(0.8)
        _st2 = _jrf.load(open(os.path.join(_adir_rf, '.ai_control.steps'), 'r', encoding='utf-8'))
        for _s2 in _st2:
            if _s2.get('text') == 'Start refresh':
                _s2['status'] = 'done'
            elif _s2.get('text') == 'Scan local EA files':
                _s2['status'] = 'doing'
        # [ALERT] 2026-08-29 FIX：雙寫（開發dir + TradotcomAgent — PC版一致）
        _write_ai_flags(None, _st2)
    except Exception:
        pass
    try:
        files = []
        # [ALERT] 2026-08-11：掃描local Experts 實際file（.mq5/.ex5 — base name 集合 — 用嚟對比網頁 config）
        local_bases = set()
        try:
            data_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
            if os.path.isdir(data_dir):
                for d in os.listdir(data_dir):
                    exp = os.path.join(data_dir, d, 'MQL5', 'Experts')
                    for sub in (exp,):
                        if os.path.isdir(sub):
                            for fn in os.listdir(sub):
                                if fn.endswith(('.mq5', '.ex5')):
                                    local_bases.add(os.path.splitext(fn)[0])
        except Exception:
            pass
        # [ALERT] 自動清殘留 config：網頁已配對 + local完全冇file（冇 .mq5 冇 .ex5）→ 刪 config（PCdelete後自動同步）
        # [ALERT] 2026-08-11 修：清所有user（唔止 current_user — 殘留喺其它帳號）
        try:
            # [ALERT] 獨立 sqlite3 connect（SQLAlchemy session 喺 request 內有隔離問題 — 直接 sqlite3 最穩陣）
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
                    print(f"[refresh] 自動清理 {cleaned_total} 個殘留 config key（local已delete）", flush=True)
                _conn.close()
        except Exception as _ce:
            print(f"[refresh] 自動清理failed: {_ce}", flush=True)
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
        # success → steps done（done重新整理）
        try:
            # [ALERT] 2026-08-29 FIX：雙寫（開發dir + TradotcomAgent — PC版一致）
            _write_ai_flags(None, [
                {'text': 'Refreshing pairing library in progress...', 'status': 'done'},
                {'text': 'Done — refresh complete', 'status': 'done'},
            ])
            # [ALERT] 2026-08-29 FIX：雙刪 show flag（開發dir + TradotcomAgent）
            for _sf_dir in [_adir_rf, os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TradotcomAgent')]:
                _sf_show = os.path.join(_sf_dir, '.ai_control.show')
                try:
                    if os.path.exists(_sf_show):
                        os.remove(_sf_show)
                except Exception:
                    pass
        except Exception:
            pass
        # release（done — 網頁 modal 唔自動關 — 確定撳先關）
        try:
            if _cg is not None:
                _cg.release()
        except Exception:
            pass
        return jsonify({"success": True, "files": files, "count": len(files)})
    except Exception as e:
        # failed → steps 顯示failed原因（紅色）+ 確定（唔需要緊急stop）
        try:
            # [ALERT] 2026-08-29 FIX：雙寫（開發dir + TradotcomAgent — PC版一致）
            _write_ai_flags(None, [
                {'text': 'Refreshing pairing library in progress...', 'status': 'done'},
                {'text': f'Refresh failed ({str(e)[:80]})', 'status': 'done'},
            ])
            # [ALERT] 2026-08-29 FIX：雙刪 show flag（開發dir + TradotcomAgent）
            for _sf_dir in [_adir_rf, os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TradotcomAgent')]:
                _sf_show = os.path.join(_sf_dir, '.ai_control.show')
                try:
                    if os.path.exists(_sf_show):
                        os.remove(_sf_show)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if _cg is not None:
                _cg.release()
        except Exception:
            pass
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/refresh-status', methods=['POST'])
@login_required
def api_refresh_status():
    """[ALERT] 2026-08-14：重新整理按鈕 → 即時檢查PC狀態（心跳/熱鍵/localfile）→ 返回網頁更新
    唔等 detector 週期 — 撳「重新整理」immediately掃描（user要求：「向PC發送訊息 check now所有狀態」）"""
    import re as _rrs
    common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
    # 1. 觸發 detector immediately重掃（rescan.flag — detector 睇到immediately掃描 EA file — 唔等 5 秒週期）
    try:
        with open(os.path.join(common_files, 'rescan.flag'), 'w', encoding='utf-8') as _f:
            _f.write(str(time.time()))
    except Exception:
        pass
    # 2. 熱鍵（已deploy集合）
    _hk_has = set()
    _hk_mtime = 0
    try:
        _hk_path = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        for _d2 in os.listdir(_hk_path):
            _hkf = os.path.join(_hk_path, _d2, 'config', 'hotkeys.ini')
            if os.path.isfile(_hkf):
                _hk_mtime = os.path.getmtime(_hkf)
                _hk_c = open(_hkf, 'r', encoding='utf-16-le', errors='ignore').read()
                for _m2 in _rrs.finditer(r'Experts\\([A-Za-z_][A-Za-z0-9_]*)\.ex5\s*=', _hk_c):
                    _hk_has.add(_m2.group(1))
                break
    except Exception:
        pass
    # 3. 即時心跳掃描（state/hb — 30 秒新鮮 = running）
    runtime = {}
    # [ALERT] 2026-08-14：讀 MT5 log — 每隻 EA 最後一條記錄（圖表實際狀態）
    _log_last = {}
    try:
        import glob as _gl2
        _lg2 = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        _latest2 = None
        for _d3 in os.listdir(_lg2):
            # [ALERT] 2026-08-21 FIX：優先讀 terminal Logs（<hash>/Logs/ — 英文「loaded successfully/removed」）
            # before讀 MQL5/Logs（MetaEditor 編譯日誌 — 中文「已启动/已stop」）→ 誤判 chart_removed（RSI_Over 掛住但顯示 removed）
            _lgd3 = os.path.join(_lg2, _d3, 'Logs')
            if os.path.isdir(_lgd3):
                for _f3 in _gl2.glob(os.path.join(_lgd3, '2026*.log')):
                    if _latest2 is None or os.path.getmtime(_f3) > os.path.getmtime(_latest2):
                        _latest2 = _f3
        # fallback: MQL5/Logs（MetaEditor 日誌）
        if not _latest2:
            for _d3 in os.listdir(_lg2):
                _lgd3 = os.path.join(_lg2, _d3, 'MQL5', 'Logs')
                if os.path.isdir(_lgd3):
                    for _f3 in _gl2.glob(os.path.join(_lgd3, '2026*.log')):
                        if _latest2 is None or os.path.getmtime(_f3) > os.path.getmtime(_latest2):
                            _latest2 = _f3
        if _latest2:
            _raw2 = open(_latest2, 'rb').read()
            _txt2 = None
            for _enc2 in ('utf-16', 'utf-8', 'cp1252'):
                try:
                    _txt2 = _raw2.decode(_enc2); break
                except Exception:
                    continue
            if _txt2:
                import re as _re2
                for _line2 in _txt2.splitlines():
                    _m2 = _re2.search(r'([A-Za-z_][A-Za-z0-9_]*) \([A-Za-z0-9._]+,[A-Z0-9]+\)\s+[^\n]*(已启动|已start|已stop|removed)', _line2)
                    if _m2:
                        _log_last[_m2.group(1)] = _m2.group(2)
    except Exception:
        pass
    try:
        config = json.loads(current_user.ea_config or '{}')
        for key in config:
            base = key
            for suffix in ('_lot', '_magic', '_tf', '_status'):
                if key.endswith(suffix):
                    base = key[:-len(suffix)]
                    break
            if base.startswith('_') or base in ('_lot', '_magic', '_tf', '_status'):
                continue
            if not base:
                continue
            sf = os.path.join(common_files, f'state_{base}.json')
            hb_txt = os.path.join(common_files, f'hb_{base}.txt')
            has_hb_file = os.path.isfile(sf) or os.path.isfile(hb_txt)
            if not has_hb_file:
                if base in _hk_has:
                    runtime[base] = 'starting' if (time.time() - _hk_mtime < 600) else 'no_hb'
                else:
                    runtime[base] = 'unpaired'
                continue
            if base not in _hk_has:
                runtime[base] = 'unpaired'
                continue
            st = 'unknown'
            if os.path.isfile(sf):
                try:
                    with open(sf, 'rb') as f:
                        raw = f.read()
                    try:
                        sd = json.loads(raw.decode('utf-8'))
                    except Exception:
                        sd = json.loads(raw.decode('utf-16'))
                    if sd.get('status') == 'running' and time.time() - os.path.getmtime(sf) < 30:
                        st = 'running'
                    elif sd.get('status') == 'stopped':
                        st = 'stopped'
                except Exception:
                    st = 'unknown'
            if st != 'running':
                if os.path.isfile(hb_txt) and time.time() - os.path.getmtime(hb_txt) < 30:
                    st = 'running'
            # [ALERT] 2026-08-14：log 圖表狀態（最優先 — 圖表實際有冇 EA — 關圖表immediately「圖表remove」）
            # [ALERT] 2026-08-21 FIX：英文 log「loaded successfully」= EA 掛住 chart → running（before淨 match removed → 誤判 chart_removed）
            if _log_last.get(base) in ('已stop', 'removed'):
                st = 'chart_removed'
            elif _log_last.get(base) == 'loaded successfully':
                st = 'running'
            if st == 'unknown' and config.get(base + '_status') == 'paused':
                st = 'paused'
            runtime[base] = st
    except Exception:
        pass
    # 4. [ALERT] 2026-08-14 自癒 + 2026-08-18 擴展：重新整理 → 自動清殘留
    # （除 config EA 外，所有唔喺配對庫 + 唔係系統保留嘅 .mq5/.ex5 都當殘留清 — 根治累積/彈返）
    # [ALERT] 2026-09-01 FIX（user實測：EA 倉庫 10 隻新 EA 被「清殘留」誤刪 — 因為唔喺配對庫 config）：
    # → EA 倉庫有嘅 .mq5（static/ea_library）都保留（唔好刪倉庫 EA — 用戶可隨時加入配對庫）
    _SYSTEM_KEEP = {'ApplyTemplate', 'BatchApplyTemplates', 'StartAgentHelper', 'AgentHelper', 'SMA_Cross', 'TestRunner', 'OpenChart', 'OpenChart_Helper'}  # [ALERT] 2026-08-18：OpenChart 系列係系統 Script tool — 唔喺配對庫都要保留（唔會被「清殘留」誤刪）
    try:
        # EA 倉庫嘅 .mq5 base（保留 — 唔刪）
        _lib_dir_rs = os.path.join(os.path.dirname(__file__), 'static', 'ea_library')
        if os.path.isdir(_lib_dir_rs):
            for _lf_rs in os.listdir(_lib_dir_rs):
                if _lf_rs.endswith('.mq5'):
                    _SYSTEM_KEEP.add(os.path.splitext(_lf_rs)[0])
        _data_dir_rs = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        _cfg_rs = json.loads(current_user.ea_config or '{}')
        _cfg_rs_eas = set()
        for _k_rs in _cfg_rs:
            _b_rs = _k_rs
            for _suf_rs in ('_lot', '_magic', '_tf', '_status'):
                if _k_rs.endswith(_suf_rs):
                    _b_rs = _k_rs[:-len(_suf_rs)]
                    break
            if _b_rs.startswith('_'):
                continue
            _cfg_rs_eas.add(_b_rs)
        # 掃 Experts 根 + Scripts 根（v0.9.76 起唔用 MT5Cloud_EA subfolder）
        for _d_rs in os.listdir(_data_dir_rs):
            for _rel_rs in ('MQL5\\Experts', 'MQL5\\Scripts'):
                _scan_dir_rs = os.path.join(_data_dir_rs, _d_rs, *_rel_rs.split('\\'))
                if not os.path.isdir(_scan_dir_rs):
                    continue
                for _fn_rs in sorted(os.listdir(_scan_dir_rs)):
                    if not _fn_rs.endswith(('.mq5', '.ex5')):
                        continue
                    _b_rs2 = os.path.splitext(_fn_rs)[0]
                    if _b_rs2 in _cfg_rs_eas or _b_rs2 in _SYSTEM_KEEP:
                        continue
                    _fp_rs = os.path.join(_scan_dir_rs, _fn_rs)
                    try:
                        os.remove(_fp_rs)
                        print(f"[API] 重新整理自癒: 已delete殘留 {_fn_rs} ({_rel_rs.split(chr(92))[1]})", flush=True)
                    except Exception:
                        pass
    except Exception:
        pass
    return jsonify({'success': True, 'runtime_status': runtime, 'deployed': sorted(_hk_has)})


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
    """下載 EA file（先睇community→user→官方）"""
    # 先睇社群dir
    community_path = os.path.join(COMMUNITY_EA_DIR, filename)
    if os.path.isfile(community_path):
        return send_from_directory(COMMUNITY_EA_DIR, filename)
    # 再睇user上傳dir
    if current_user.is_authenticated:
        user_dir = os.path.join(UPLOAD_DIR, current_user.username)
        user_path = os.path.join(user_dir, filename)
        if os.path.isfile(user_path):
            return send_from_directory(user_dir, filename)
    # 最後睇官方dir
    return send_from_directory(EA_LIBRARY_DIR, filename)

@app.route('/api/ea-library/remove-local/<filename>', methods=['POST'])
@login_required
def api_ea_remove_local(filename):
    """deletelocal MT5 已安裝嘅 EA file（MQL5/Experts/*.ex5 + *.mq5）"""
    # [WARN] 系統file保護（Controller — 唔可以delete）
    base_only = filename.split('.')[0]
    if base_only == 'Controller':
        return jsonify({"success": False, "error": "系統file（Controller）唔可以delete"}), 403
    # [WARN] user要求（2026-08）：每次操作 MT5 相關嘢，先偵測 MT5 有冇開 — 冇就開返
    ensure_mt5_running()
    # [ALERT] 2026-08-10：網頁 delete 唔經 watcher → 要喺呢度寫 steps（唔會殘留上一個操作字眼 — user投訴）
    try:
        import json as _jdel
        _adir_del = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
        with open(os.path.join(_adir_del, '.ai_control.show'), 'w', encoding='utf-8') as _f:
            _f.write(f'delete {base_only}')
        with open(os.path.join(_adir_del, '.ai_control.steps'), 'w', encoding='utf-8') as _f2:
            # [ALERT] 2026-08-12：詳細步驟（同 watcher 一致 — 活動記錄式 — 唔會 1 行覆蓋）
            _jdel.dump([
                {'text': f'Start delete {base_only}', 'status': 'doing'},
                {'text': 'Check chart (EA running?)', 'status': 'pending'},
                {'text': 'Remove EA from chart', 'status': 'pending'},
                {'text': 'Delete local files (.mq5/.ex5)', 'status': 'pending'},
                {'text': 'Clean up settings and release hotkey', 'status': 'pending'},
                {'text': 'Done — delete complete', 'status': 'pending'},
            ], _f2, ensure_ascii=False)
            # [ALERT] 2026-09-03（VPS 搬遷）：SocketIO push 俾遠端 agent
            try:
                _push_alert_socket(f'delete {base_only}', [
                    {'text': f'Start delete {base_only}', 'status': 'doing'},
                    {'text': 'Check chart (EA running?)', 'status': 'pending'},
                    {'text': 'Remove EA from chart', 'status': 'pending'},
                    {'text': 'Delete local files (.mq5/.ex5)', 'status': 'pending'},
                    {'text': 'Clean up settings and release hotkey', 'status': 'pending'},
                    {'text': 'Done — delete complete', 'status': 'pending'},
                ])
            except Exception:
                pass
            # [ALERT] 2026-08-12 FIX：直接寫 .steps（唔加 .tmp）— 唔可以 os.replace（會將 .steps rename 成 .st → fi
    except Exception as e_del:
        print(f"[DEBUG] remove-local steps write failed: {e_del}")
    # [ALERT] 2026-08-12 FIX：寫完 steps 先停留 1.5 秒（視窗彈出 + user見到「startdeletein progress」先startdelete — 步驟唔會瞬間done）
    try:
        import time as _tdel
        _tdel.sleep(1.5)
    except Exception:
        pass
    # 安全檢查：檔名只可以係字母數字底線（防 path traversal）
    # [ALERT] 2026-08-08：接受帶 .mq5/.ex5 副檔名（前端可能傳帶副檔名嘅名）
    import re as _re
    if not _re.fullmatch(r'[A-Za-z0-9_]+(\.[A-Za-z0-9]+)?', filename):
        return jsonify({"success": False, "error": "Invalid filename"}), 400

    # [ALERT] 2026-09-03（VPS 搬遷 — 方案2 遠端執行）：剷除 = server 發指令 → agent 喺自己機刪
    # server（VPS）冇 MT5 → 唔可以刪 A/B 電腦嘅 EA 檔案 — 要 agent 做
    # agent 收到 ea_remove_command → 刪自己機 Experts/Scripts 檔案 + 寫 pause_cmd（watcher remove chart EA）
    _agt_rm = Agent.query.filter_by(user_id=current_user.id).first()
    _agent_online_rm = bool(_agt_rm and _agt_rm.status == 'connected')
    if _agent_online_rm:
        try:
            import time as _trm
            # 寫 config（刪除配對記錄）
            try:
                _cfg_rm = json.loads(current_user.ea_config or '{}')
                for _k_rm in [k for k in list(_cfg_rm.keys()) if k == base_only or k.startswith(base_only + '_')]:
                    _cfg_rm.pop(_k_rm, None)
                _rem_rm = _cfg_rm.get('_removed', [])
                if base_only not in _rem_rm:
                    _rem_rm.append(base_only)
                _cfg_rm['_removed'] = _rem_rm
                current_user.ea_config = json.dumps(_cfg_rm)
                db.session.commit()
                print(f"[remove-local] [REMOTE] config 已刪: {base_only}", flush=True)
            except Exception as _ecfg_rm:
                print(f"[remove-local] [REMOTE] config delete warning: {_ecfg_rm}", flush=True)
            # 發指令俾 agent（刪自己機檔案 + remove chart）
            socketio.emit('ea_remove_command', {
                "ea_name": base_only,
                "filename": filename,
            }, room=_agt_rm.agent_id)
            print(f"[remove-local] [REMOTE] ea_remove_command sent to agent {_agt_rm.agent_id}: {base_only}", flush=True)
            log_activity('ea_remove', f'{base_only} 剷除指令已發送俾 Agent（遠端刪除）', ea=base_only)
            return jsonify({"success": True, "message": f"剷除指令已發送俾 Agent（{_agt_rm.agent_id} 遠端刪除）", "removed": [base_only]})
        except Exception as _e_rm2:
            print(f"[remove-local] [REMOTE] send failed: {_e_rm2}", flush=True)
            # fallthrough 去本機模式
    # 本機模式（server 同 agent 同一部機）— 原有邏輯

    experts_dirs = []
    data_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
    if os.path.isdir(data_dir):
        for d in os.listdir(data_dir):
            exp = os.path.join(data_dir, d, 'MQL5', 'Experts')
            if os.path.isdir(exp):
                experts_dirs.append(exp)

    removed = []
    # [ALERT] 2026-08-18 FIX：remove要完整 — 除咗 Experts 根，仲要刪 Scripts 根
    # （OpenChart 呢類 script 放 Scripts 根 — before冇刪 → 殘留 → after彈返）
    # scripts_dirs: 搵返 MQL5/Scripts 根
    scripts_dirs = []
    for d in os.listdir(data_dir) if os.path.isdir(data_dir) else []:
        scr = os.path.join(data_dir, d, 'MQL5', 'Scripts')
        if os.path.isdir(scr):
            scripts_dirs.append(scr)

    for exp_dir in experts_dirs:
        # [WARN] 2026-08：EA 喺 Experts 根dir
        search_dirs = [exp_dir]
        for search_dir in search_dirs:
            for ext in ('.ex5', '.mq5'):
                # [ALERT] 2026-08-08：用 base_only（filename 可能帶 .mq5 — 唔可以 filename+ext）
                target = os.path.join(search_dir, base_only + ext)
                if os.path.isfile(target):
                    try:
                        os.remove(target)
                        removed.append(target)
                    except Exception as e:
                        return jsonify({"success": False, "error": str(e)}), 500
    # 刪 Scripts 根（script 類 EA — 例如 OpenChart）
    for scr_dir in scripts_dirs:
        for ext in ('.ex5', '.mq5', '.log'):
            target = os.path.join(scr_dir, base_only + ext)
            if os.path.isfile(target):
                try:
                    os.remove(target)
                    removed.append(target)
                    print(f"[remove-local] 刪 Scripts: {target}", flush=True)
                except Exception as e:
                    print(f"[remove-local] [WARN] 刪 Scripts failed: {target} ({e})", flush=True)

    # [ALERT] 2026-08-14 FIX（user案例：delete後localfile「彈返」）：delete後 Double-check — 確認file真係delete
    # （before淨係刪完就話success — user發現「安裝 Fibonacci → 全部 EA 彈返」— 加確認 + 記錄）
    _residual = []
    for exp_dir in experts_dirs:
        for search_dir in (exp_dir,):
            for ext in ('.ex5', '.mq5'):
                target = os.path.join(search_dir, base_only + ext)
                if os.path.isfile(target):
                    _residual.append(target)
    # Scripts 殘留 double-check
    for scr_dir in scripts_dirs:
        for ext in ('.ex5', '.mq5'):
            target = os.path.join(scr_dir, base_only + ext)
            if os.path.isfile(target):
                _residual.append(target)
    if _residual:
        print(f"[remove-local] [WARN] delete後偵測到殘留file（可能被鎖/自動恢復）: {_residual}", flush=True)
        # 再試一次（MT5 可能鎖住 — 稍等再刪）
        import time as _rtry
        _rtry.sleep(1.5)
        for t2 in _residual:
            try:
                os.remove(t2)
                print(f"[remove-local] 重試deletesuccess: {os.path.basename(t2)}", flush=True)
            except Exception as e2:
                print(f"[remove-local] [FAIL] 重試deletefailed（file仍exists — user要手動刪或重啟 MT5）: {t2} ({e2})", flush=True)

    if removed:
        # [ALERT] 2026-08-10：網頁 delete done → steps 全部 done（warning視窗顯示「donedelete」+ 確定）
        # [ALERT] 2026-08-12：讀現有 steps（6 步）→ 全部 done（唔覆蓋 2 行 — 活動記錄式保持）
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
            # [ALERT] 2026-08-12 修：唔寫 done（DELETE config 會寫 pause_cmd → watcher 接手逐步 — 雙重寫 steps → 覆蓋 → 網頁彈嚟彈去）
            # 只係確保 steps 有內容（等 watcher 接手逐步done）
            if not _del_steps:
                _del_steps = [{'text': f'Start delete {base_only}', 'status': 'doing'},
                              {'text': 'Check chart (EA running?)', 'status': 'pending'},
                              {'text': 'Remove EA from chart', 'status': 'pending'},
                              {'text': 'Delete local files (.mq5/.ex5)', 'status': 'pending'},
                              {'text': 'Clean up settings and release hotkey', 'status': 'pending'},
                              {'text': 'Done — delete complete', 'status': 'pending'}]
            with open(_sf_del, 'w', encoding='utf-8') as _f:
                _jdel2.dump(_del_steps, _f, ensure_ascii=False)
        except Exception:
            pass
        # 寫「網頁delete」標記 → watcher 偵測到delete時知道來源（唔會誤判做PCdelete）
        try:
            common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
            os.makedirs(common_files, exist_ok=True)
            flag_path = os.path.join(common_files, f'web_delete_{filename}.flag')
            with open(flag_path, 'w') as f:
                f.write('1')
        except Exception:
            pass
        # [ALERT] 2026-08-28 FIX（user實錘：配對庫「delete」只刪file+config — 唔remove chart EA → EA 仲行緊 + 心跳仲寫）：
        # remove-local 加寫 pause_cmd（action=delete）→ watcher process_pause_cmd → auto_attach --remove（remove圖表 EA — 同 ea-config/delete 一樣）
        try:
            _pcmd_path = os.path.join(common_files, f'pause_cmd_{base_only}_{int(__import__("time").time())}.json')
            with open(_pcmd_path, 'w', encoding='utf-8') as _fpc:
                json.dump({'ea_name': base_only, 'action': 'delete'}, _fpc, ensure_ascii=False)
            print(f"[remove-local] pause_cmd 已寫（remove圖表 EA）: {os.path.basename(_pcmd_path)}", flush=True)
        except Exception as _epc:
            print(f"[remove-local] [WARN] 寫 pause_cmd failed: {_epc}", flush=True)
        # [ALERT] 2026-08-15 FIX（user：Magic/Symbol 剸除後再配對返嚟）：remove-local 都要刪 config + 釋放快捷鍵
        # （before只刪localfile — config 殘留 → 重新配對 setdefault 舊值返嚟）
        try:
            config_del = json.loads(current_user.ea_config or '{}')
            removed_del = config_del.get('_removed', [])
            if base_only not in removed_del:
                removed_del.append(base_only)
            config_del['_removed'] = removed_del
            for key in list(config_del.keys()):
                if key == base_only or key.startswith(base_only + '_'):
                    del config_del[key]
            current_user.ea_config = json.dumps(config_del)
            db.session.commit()
            print(f"[remove-local] [OK] 已刪 config: {base_only}（Magic/Symbol 清除）", flush=True)
        except Exception as _ecfg:
            print(f"[remove-local] [WARN] 刪 config failed: {_ecfg}", flush=True)
        # 釋放快捷鍵（hotkeys.ini — 唔殘留）
        try:
            release_hotkey(base_only)
            print(f"[remove-local] [OK] 已釋放快捷鍵: {base_only}", flush=True)
        except Exception:
            pass
        # [ALERT] 2026-08-15 FIX（user：剸除 EA 後 MT5 彈「導航熱鍵」視窗殘留）：自動關閉「導航熱鍵」dialog
        # （熱鍵 reload / MT5 重啟後 MT5 會彈「導航熱鍵」視窗 — 自動偵測 + 關閉）
        try:
            import time as _tclose
            _tclose.sleep(1.5)
            import ctypes as _ctclose
            import subprocess as _spclose
            _uclose = _ctclose.windll.user32
            _app_close = None
            try:
                from pywinauto import Application as _AppClose
                _out_c = _spclose.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True, text=True).stdout
                _pid_c = None
                for _lnc in _out_c.splitlines():
                    _pc = [p.strip().strip('"') for p in _lnc.split(',')]
                    if len(_pc) >= 2 and _pc[0] == 'terminal64.exe' and _pc[1].isdigit():
                        _pid_c = int(_pc[1])
                        break
                if _pid_c:
                    _app_close = _AppClose(backend='win32').connect(process=_pid_c, timeout=8)
            except Exception:
                _app_close = None
            def _cb_close(_h, _x):
                if _uclose.IsWindowVisible(_h):
                    _cc = _ctclose.create_unicode_buffer(64)
                    _uclose.GetClassNameW(_h, _cc, 64)
                    if '#32770' in _cc.value:
                        _lt = _uclose.GetWindowTextLengthW(_h)
                        _bt = _ctclose.create_unicode_buffer(_lt + 1)
                        _uclose.GetWindowTextW(_h, _bt, _lt + 1)
                        if '熱鍵' in _bt.value or '快捷' in _bt.value:
                            try:
                                _dw_close = _app_close.window(handle=_h)
                            except Exception:
                                _dw_close = None
                            # 搵「關閉/取消/確定」按鈕 — click
                            if _dw_close:
                                for _b2 in _dw_close.children(class_name='Button'):
                                    try:
                                        _t2 = _b2.window_text()
                                        if '關閉' in _t2 or 'Close' in _t2 or '取消' in _t2 or 'Cancel' in _t2:
                                            _b2.click()
                                            print(f"[remove-local] [OK] closed「導航熱鍵」視窗", flush=True)
                                            break
                                    except Exception:
                                        pass
                return True
            _uclose.EnumWindows(_ctclose.WINFUNCTYPE(_ctclose.c_bool, _ctclose.c_void_p, _ctclose.c_void_p)(_cb_close), None)
        except Exception as _eclose:
            print(f"[remove-local] [WARN] 關閉導航熱鍵視窗failed: {_eclose}", flush=True)
        log_activity('ea_delete', f'{filename} 已於網頁delete（localfile已delete）', ea=filename)
        return jsonify({"success": True, "removed": removed})
    return jsonify({"success": False, "error": "EA not found in local Experts dir"}), 404

def _log_bounce_back(filenames, ea_dir):
    """[ALERT] 2026-08-15：彈返監察日誌 — 記錄彈返事件（時間/file/內容特徵 — 追蹤源頭）
    user要求：彈返 EA 要搵核心原因（唔可以由得佢出現）— 呢個日誌下次彈返時記錄線索"""
    try:
        import time as _tbb
        entry = {
            'time': _tbb.strftime('%Y-%m-%d %H:%M:%S'),
            'files': [],
        }
        for fn in filenames:
            fp = os.path.join(ea_dir, fn)
            info = {'name': fn}
            if os.path.isfile(fp):
                st = os.stat(fp)
                info['ctime'] = _tbb.strftime('%Y-%m-%d %H:%M:%S', _tbb.localtime(st.st_ctime))
                info['size'] = st.st_size
                try:
                    c = open(fp, encoding='utf-8', errors='ignore').read(2000)
                    info['has_heartbeat'] = '__mt5c_process' in c
                    info['has_InpSymbol'] = 'InpSymbol' in c
                    info['head'] = c[:80].replace('\n', ' ')
                except Exception:
                    pass
            entry['files'].append(info)
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bounce_back_log.jsonl')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        print(f"[彈返監察] 已記錄: {entry['time']} {filenames}", flush=True)
    except Exception as e:
        print(f"[彈返監察] [WARN] 記錄failed: {e}")


@app.route('/api/ea-library/install-local/<filename>', methods=['POST'])
@login_required
def api_ea_install_local(filename):
    """將 EA 倉庫（官方/社群/user）嘅 EA 複製去local MT5 Experts dir — 配對庫immediately見到
    聯動：EA 倉庫「移去配對」/ 上傳自己 EA after自動安裝落local
    """
    # [ALERT] 2026-08-22（user要求：UAC 檢測機制）：配對前檢查 UAC
    try:
        _uac_inst = _detect_uac_server()
        if _uac_inst:
            print(f"[install-local] [WARN] 偵測到 UAC 授權窗口: {_uac_inst[0]} — 配對/編譯可能被擋")
    except Exception:
        pass
    import shutil as _sh
    import re as _re
    if not _re.fullmatch(r'[A-Za-z0-9_.]+', filename):
        return jsonify({"success": False, "error": "Invalid filename"}), 400

    # [WARN] user要求（2026-08）：每次操作 MT5 相關嘢，先偵測 MT5 有冇開 — 冇就開返
    ensure_mt5_running()

    # 0. 寫「處理中」log — user想知系統有冇處理緊
    _base0 = os.path.splitext(filename)[0]
    log_activity('ea_install', f'{_base0} 配對處理中...', ea=_base0)
    # [ALERT] 2026-08-10：配對（install-local）warning視窗流程（同deploy/delete一致 — MODULE_INDEX 規範）
    try:
        import json as _jin
        _adir_in = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
        # [ALERT] 2026-08-28 FIX（PC版warning視窗冇彈）：雙寫 show + steps（開發dir + TradotcomAgent — alert_worker 讀自己dir）
        _steps_new = [
            {'text': f'Start pairing {_base0}', 'status': 'doing'},
            {'text': 'Copy file to local (Experts root)', 'status': 'pending'},
            {'text': f'Compile {_base0}.mq5 → .ex5', 'status': 'pending'},
            {'text': 'Done — pairing complete', 'status': 'pending'},
        ]
        for _wdir in [_adir_in, os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TradotcomAgent')]:
            try:
                os.makedirs(_wdir, exist_ok=True)
                with open(os.path.join(_wdir, '.ai_control.show'), 'w', encoding='utf-8') as _f:
                    _f.write(f'配對 {_base0}')
                with open(os.path.join(_wdir, '.ai_control.steps') + '.tmp', 'w', encoding='utf-8') as _f2:
                    _jin.dump(_steps_new, _f2, ensure_ascii=False)
                # [ALERT] 2026-08-12 FIX：os.replace 移出 with block（WinError 32 — source 被自己開住）
                os.replace(os.path.join(_wdir, '.ai_control.steps') + '.tmp',
                           os.path.join(_wdir, '.ai_control.steps'))
            except Exception:
                pass
        # [ALERT] 2026-09-03（VPS 搬遷）：SocketIO push 俾遠端 agent
        try:
            _push_alert_socket(f'pairing {_base0}', _steps_new)
        except Exception:
            pass
    except Exception as _ein_err:
        print(f"[DEBUG] install-local steps write failed: {_ein_err}", flush=True)

    # [ALERT] 2026-08-12 FIX：寫完 steps 先停留 1.5 秒（視窗彈出 + user見到「start配對in progress」先start複製 — 步驟唔會瞬間done）
    try:
        import time as _td
        _td.sleep(1.5)
    except Exception:
        pass

    # 1. 搵file喺邊個dir（社群 → user → 官方）
    # [WARN] filename 可能冇副檔名（前端傳 baseName）→ 自動試 .mq5 / .ex5
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

    # [ALERT] 2026-09-03（VPS 搬遷 — 方案2 遠端執行）：配對 = server 發指令 → agent 喺自己機安裝
    # server（VPS）冇 MT5 → 唔可以自己複製/編譯 — 要 agent（A/B 電腦）做
    # agent 收到 install_ea_command → download_and_install（下載 EA 庫 .mq5 → 心跳注入 → 編譯 → 本地 Experts）
    _agt = Agent.query.filter_by(user_id=current_user.id).first()
    _agent_online = bool(_agt and _agt.status == 'connected')
    if _agent_online:
        try:
            import time as _ta
            _dl_url = f"{request.host_url}api/ea-library/"
            _ea_cfg_send = json.loads(current_user.ea_config or '{}')
            _ba_send = os.path.splitext(filename)[0]
            # 預先寫 config（配對記錄 — magic 由 EA 庫 src 讀）
            try:
                _cfg_send = json.loads(current_user.ea_config or '{}')
                _cfg_send.setdefault(_ba_send, 'EURUSD')
                _cfg_send.setdefault(_ba_send + '_tf', 'H1')
                _cfg_send.setdefault(_ba_send + '_magic', _ea_magic_from_source(src_path) if src_path.endswith('.mq5') else '240701')
                _cfg_send.setdefault(_ba_send + '_lot', 1.00)
                _rem_send = _cfg_send.get('_removed', [])
                if _ba_send in _rem_send:
                    _rem_send.remove(_ba_send)
                    _cfg_send['_removed'] = _rem_send
                current_user.ea_config = json.dumps(_cfg_send)
                db.session.commit()
                print(f"[install-local] [REMOTE] config 已寫: {_ba_send}", flush=True)
            except Exception as _ecfg_s:
                print(f"[install-local] [REMOTE] config write warning: {_ecfg_s}", flush=True)
            # 發指令俾 agent（安裝到自己機）
            socketio.emit('install_ea_command', {
                "ea_name": _ba_send,
                "ea_list": [],
                "download_url": _dl_url,
                "ea_config": _ea_cfg_send,
            }, room=_agt.agent_id)
            print(f"[install-local] [REMOTE] install_ea_command sent to agent {_agt.agent_id}: {_ba_send}", flush=True)
            log_activity('ea_install', f'{_ba_send} 配對指令已發送俾 Agent（遠端安裝）', ea=_ba_send)
            # Steps：配對開始（agent 完成會經 install_result → watcher 更新後續）
            try:
                _write_ai_flags(None, [
                    {'text': f'Start pairing {_ba_send}', 'status': 'done'},
                    {'text': 'Send install command to agent', 'status': 'done'},
                    {'text': f'Agent installing {_ba_send} on local MT5', 'status': 'doing'},
                    {'text': 'Done — pairing complete', 'status': 'pending'},
                ])
            except Exception:
                pass
            return jsonify({
                "success": True,
                "filename": filename,
                "base": _ba_send,
                "compile_ok": None,
                "message": f"配對指令已發送俾 Agent（{_agt.agent_id} 遠端安裝）"
            })
        except Exception as _e_rem:
            print(f"[install-local] [REMOTE] send failed: {_e_rem}", flush=True)
            # fallthrough 去本機模式（如果 send 失敗）
    # 本機模式（server 同 agent 同一部機 — 冇遠端 agent / send 失敗）— 原有邏輯

    # 2. 搵local MT5 Experts dir
    experts_dirs = []
    data_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
    if os.path.isdir(data_dir):
        for d in os.listdir(data_dir):
            exp = os.path.join(data_dir, d, 'MQL5', 'Experts')
            if os.path.isdir(exp):
                experts_dirs.append(exp)

    if not experts_dirs:
        return jsonify({"success": False, "error": "not foundlocal MT5 Experts dir"}), 500

    # 3. 複製去 Experts 根dir（user要求：取消 MT5Cloud_EA folder）
    installed = []
    compiled = False
    # [WARN] 用 src_path 嘅 basename（保留副檔名）— filename 可能冇 .mq5（前端傳 baseName）
    # 唔可以淨用 filename — 會複製錯名 + 唔會寫 compile_cmd（endswith('.mq5') False）
    dest_name = os.path.basename(src_path)
    # [ALERT] 2026-08-18 FIX（user要求：Script 類型 EA 配對）：偵測 .mq5 係 Script 定 EA
    # Script（#property script_show_inputs / 有 void OnStart() 無 OnInit）→ 放 MQL5/Scripts/ + 唔注入心跳
    # EA（有 OnInit/OnTick）→ 放 MQL5/Experts/ + 注入心跳
    _is_script = False
    if dest_name.lower().endswith('.mq5'):
        try:
            _src_c = open(src_path, encoding='utf-8', errors='ignore').read()
            _is_script = ('#property script_show_inputs' in _src_c) or \
                         ('void OnStart()' in _src_c and 'int OnInit()' not in _src_c)
        except Exception:
            _is_script = False
    # 選擇目標dir（Script → Scripts/，EA → Experts/）
    _target_dirs = []
    for _td_d in os.listdir(data_dir) if os.path.isdir(data_dir) else []:  # data_dir = APPDATA\MetaQuotes\Terminal（上面已定義）
        _rel = 'MQL5\\Scripts' if _is_script else 'MQL5\\Experts'
        _tgt = os.path.join(data_dir, _td_d, *_rel.split('\\'))
        if os.path.isdir(_tgt):
            _target_dirs.append(_tgt)
    if not _target_dirs:
        _target_dirs = experts_dirs  # fallback
    for target_dir in _target_dirs:
        target = os.path.join(target_dir, dest_name)
        if os.path.abspath(target) == os.path.abspath(src_path):
            continue  # 已經喺度
        try:
            _sh.copy2(src_path, target)
            # [ALERT] 2026-08-14：核心模板 — 複製後自動注入心跳 code（1 秒心跳 — 新 EA 自動有 — 唔使手動加）
            # （EA 庫版本冇心跳 code → deploy後永遠「沒有心跳設定」— 自動注入解決）
            if dest_name.endswith('.mq5') and not _is_script:  # [ALERT] 2026-08-18：心跳只注入 EA（Script 唔適用 — script 一嚟就跑）
                try:
                    import re as _re_hb
                    _c_hb = open(target, encoding='utf-8', errors='ignore').read()
                    if '__mt5c_process' not in _c_hb and 'EventSetTimer' not in _c_hb:
                        _hb_mod = '''
// ---- Tradotcom 心跳（自動注入 2026-08-14 — 每秒寫心跳 + pause指令檢查）----
// [ALERT] 2026-08-15：交易品種參數（deploy時自動write揀好嘅 symbol — EA 用呢個 symbol 交易/開圖表 — 唔理圖表本身）
input string InpSymbol = "";
string __mt5c_ctrl_file = "";
string __mt5c_state_file = "";
void __mt5c_process() {
   if(__mt5c_ctrl_file == "") {
      __mt5c_ctrl_file = "ctrl_" + MQLInfoString(MQL_PROGRAM_NAME) + ".json";
      __mt5c_state_file = "state_" + MQLInfoString(MQL_PROGRAM_NAME) + ".json";
   }
   // [ALERT] 2026-08-15 FIX：開目標圖表（只開一次 — static flag — 唔可以每次心跳都開！）
   static bool __mt5c_chart_done = false;
   if(!__mt5c_chart_done) {
      __mt5c_chart_done = true;
      if(InpSymbol != "" && Symbol() != InpSymbol) {
         long _cid = ChartOpen(InpSymbol, PERIOD_CURRENT);
         if(_cid > 0) { ChartSetInteger(_cid, CHART_BRING_TO_TOP, 0, true); Print("[UPCHART] 已開目標圖表: ", InpSymbol); }
      }
   }
   if(FileIsExist(__mt5c_ctrl_file, FILE_COMMON)) {
      int h = FileOpen(__mt5c_ctrl_file, FILE_READ|FILE_TXT|FILE_COMMON);
      if(h != INVALID_HANDLE) {
         string c = FileReadString(h);
         FileClose(h);
         FileDelete(__mt5c_ctrl_file, FILE_COMMON);
         if(StringFind(c, "stop") >= 0) {
            int h2 = FileOpen(__mt5c_state_file, FILE_WRITE|FILE_TXT|FILE_COMMON);
            if(h2 != INVALID_HANDLE) { FileWrite(h2, "{\\"status\\":\\"stopped\\"}"); FileClose(h2); }
            ExpertRemove();
            return;
         }
      }
   }
   int h = FileOpen(__mt5c_state_file, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(h != INVALID_HANDLE) {
      FileWrite(h, StringFormat("{\\"ea\\":\\"%s\\",\\"status\\":\\"running\\",\\"ts\\":%d}", MQLInfoString(MQL_PROGRAM_NAME), (int)TimeCurrent()));
      FileClose(h);
   }
}
// [ALERT] 2026-08-21：逐單記錄（trades_<EA>.json — 報告/correlation 真實數據）
// deploy時user可選注入（default 注入）— 每次平倉記錄一單（ticket/time/profit）
string __mt5c_trades_file = "";
void __mt5c_append_trade() {
   if(__mt5c_trades_file == "")
      __mt5c_trades_file = "trades_" + MQLInfoString(MQL_PROGRAM_NAME) + ".json";
   // 掃最近一筆已平倉嘅 deal（OnTradeTransaction 後由 history 攞）
   if(HistorySelect(TimeCurrent() - 3600, TimeCurrent())) {
      int _tot = HistoryDealsTotal();
      for(int _i = _tot - 1; _i >= 0; _i--) {
         ulong _t = HistoryDealGetTicket(_i);
         if(_t <= 0) continue;
         if((long)HistoryDealGetInteger(_t, DEAL_MAGIC) == 0) continue;
         if(HistoryDealGetInteger(_t, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
         double _p = HistoryDealGetDouble(_t, DEAL_PROFIT);
         if(_p == 0) continue;
         // write（append — FILE_READ|FILE_WRITE + SEEK_END）
         int _fh = FileOpen(__mt5c_trades_file, FILE_READ|FILE_WRITE|FILE_TXT|FILE_COMMON);
         if(_fh != INVALID_HANDLE) {
            FileSeek(_fh, 0, SEEK_END);
            FileWriteString(_fh, StringFormat("{\\"ticket\\":%I64d,\\"time\\":%I64d,\\"profit\\":%.2f}\\n", _t, (long)TimeCurrent(), _p));
            FileClose(_fh);
         }
         break;  // 每次 transaction 只記一筆
      }
   }
}
// ---- 心跳end ----
'''
                        _c_hb = _c_hb.rstrip() + '\n' + _hb_mod + '\n'
                        # OnInit 掛鉤（EventSetTimer — return(INIT_SUCCEEDED) 前）
                        _c_hb2 = _re_hb.sub(r'(\s*)return\s*\(\s*INIT_SUCCEEDED\s*\)\s*;', r'\1   EventSetTimer(1);\n\1   return(INIT_SUCCEEDED);', _c_hb, count=1)
                        # OnTimer 掛鉤（調用 __mt5c_process — OnDeinit 前）
                        _c_hb2 = _c_hb2.replace('void OnDeinit(const int reason)', 'void OnTimer()\n{\n   __mt5c_process();\n}\n\nvoid OnDeinit(const int reason)', 1)
                        # [ALERT] 2026-08-21：OnTradeTransaction 掛鉤（逐單記錄 — 平倉時 append trades json）
                        # 冇 OnTradeTransaction 就加；有就喺入面加 call
                        if 'OnTradeTransaction' not in _c_hb2:
                            _c_hb2 = _c_hb2.replace('void OnDeinit(const int reason)',
                                'void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)\n{\n   __mt5c_append_trade();\n}\n\nvoid OnDeinit(const int reason)', 1)
                        # OnDeinit EventKillTimer（Print 已stop 前）
                        _c_hb2 = _re_hb.sub(r'(\s*)if\(EnableLog\) Print\("[STOP]', r'\1   EventKillTimer();\n\1   if(EnableLog) Print("[STOP]', _c_hb2, count=1)
                        if _c_hb2 != _c_hb:
                            open(target, 'w', encoding='utf-8').write(_c_hb2)
                            print(f"[API] [PWR] 已注入 1 秒心跳 code: {dest_name}", flush=True)
                except Exception as _ehb:
                    print(f"[API] [WARN] 心跳注入failed（唔影響配對）: {_ehb}", flush=True)
            installed.append(target)
            # [ALERT] 2026-08-12 FIX：複製done → 更新 steps（start配對 done + 複製file done — 活動記錄式）
            try:
                import json as _jc3
                _adir_ic = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
                _sf_ic = os.path.join(_adir_ic, '.ai_control.steps')
                # [ALERT] 2026-08-12 FIX：複製done前停留 1 秒（「複製in progress」顯示耐啲 — user睇到工作過程 — 唔會瞬間done）
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
                    if isinstance(_s, dict) and _s.get('text') in (f'Start pairing {_base0}', 'Copy file to local (Experts root)'):
                        _s['status'] = 'done'
                # [ALERT] 2026-08-12 FIX：如果唔使編譯（.ex5 已exists且新過 .mq5）→ immediatelydone「編譯」+「done配對」（唔停留 pending — 「兩步就停」根治）
                try:
                    _ex5_ic = os.path.join(target_dir, os.path.splitext(dest_name)[0] + '.ex5')
                    _mq5_ic = target
                    _need_compile = dest_name.lower().endswith('.mq5') and (
                        not os.path.exists(_ex5_ic) or os.path.getmtime(_ex5_ic) < os.path.getmtime(_mq5_ic))
                    if not _need_compile:
                        for _s2 in _cur_ic:
                            if isinstance(_s2, dict) and _s2.get('text') in (f'編譯 {os.path.splitext(dest_name)[0]}.mq5 → .ex5', 'Done — pairing complete'):
                                _s2['status'] = 'done'
                except Exception:
                    pass
                # [ALERT] 2026-08-29 FIX：雙寫（開發dir + TradotcomAgent — PC版warning視窗一致）
                _write_ai_flags(None, _cur_ic)
            except Exception:
                pass
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

        # 3b. 如果係 .mq5 → 寫 compile 指令俾 watcher（watcher 有 desktop access 先 compile 到）
        if dest_name.lower().endswith('.mq5'):
            try:
                base = os.path.splitext(dest_name)[0]
                ex5_target = os.path.join(target_dir, base + '.ex5')
                mq5_target = target
                if not os.path.exists(ex5_target) or os.path.getmtime(ex5_target) < os.path.getmtime(mq5_target):
                    # 寫 compile_cmd 俾 deploy_watcher（MetaEditor 需要 desktop access）
                    import time as _ct
                    common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
                    os.makedirs(common_files, exist_ok=True)
                    # [ALERT] 2026-08-12 FIX：寫前刪已有嘅同 EA compile_cmd（唔好排隊多個 → watcher 逐個處理 → 「自動再撈」）
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
                print(f"[install-local] compile 指令writefailed: {e}")
        break  # 只複製去第一個 Experts dir

    # [ALERT] 2026-08-14 FIX（user案例：安裝 Fibonacci → 全部 EA「彈返」）：複製監察
    # 偵測「install-local after有冇非預期 EA file出現」（ctime 08:19:55 批量複製 — 源頭未明 — 加監察下次捉到）
    try:
        import time as _tmon
        _mon_ea_dir = experts_dirs[0] if experts_dirs else None
        if _mon_ea_dir and os.path.isdir(_mon_ea_dir):
            _before = set(os.listdir(_mon_ea_dir))
            # 等 3 秒（watcher 可能immediately處理 compile — 期間有冇額外複製）
            _tmon.sleep(3)
            _after = set(os.listdir(_mon_ea_dir))
            _unexpected = sorted(_after - _before - {dest_name, os.path.splitext(dest_name)[0] + '.ex5'})
            if _unexpected:
                print(f"[install-local] [WARN] 複製監察: 安裝 {dest_name} 後偵測到非預期 EA 出現: {_unexpected}", flush=True)
                _log_bounce_back(_unexpected, _mon_ea_dir)
            else:
                print(f"[install-local] 複製監察: 安裝 {dest_name} 後冇額外 EA（正常）", flush=True)
    except Exception as _eme:
        print(f"[install-local] [WARN] 複製監察failed: {_eme}", flush=True)

    # [ALERT] 2026-08-14 自癒：偵測「彈返」— ctime 新（120 秒內出現）+ config 冇（已delete）→ 自動delete
    # （user案例：delete晒 EA → 安裝 Fibonacci → 全部「彈返」— 源頭未明（環境層面）— 自癒自動清理彈返file）
    try:
        import time as _thb
        _cfg_hb = json.loads(current_user.ea_config or '{}')
        _cfg_hb_eas = set(k.rsplit('_', 1)[0] for k in _cfg_hb if not k.startswith('_'))
        _ea_dir_hb = experts_dirs[0] if experts_dirs else None
        if _ea_dir_hb and os.path.isdir(_ea_dir_hb):
            for _fn_hb in sorted(os.listdir(_ea_dir_hb)):
                if not _fn_hb.endswith(('.mq5', '.ex5')):
                    continue
                # [ALERT] 2026-08-14 FIX：排除「今次安裝嘅 EA」（自癒喺 config write前執行 — 誤刪啱啱安裝嘅 → compile「找不到file」→ user見 Windows error）
                if _fn_hb == dest_name or _fn_hb == os.path.splitext(dest_name)[0] + '.ex5':
                    continue
                _b_hb = os.path.splitext(_fn_hb)[0]
                if _b_hb in _cfg_hb_eas:
                    continue  # config 有（正常配對 — 唔好亂刪）
                _fp_hb = os.path.join(_ea_dir_hb, _fn_hb)
                if time.time() - os.path.getctime(_fp_hb) < 120:  # 2 分鐘內出現 = 彈返
                    try:
                        os.remove(_fp_hb)
                        print(f"[install-local] 自癒: 已delete彈返嘅 {_fn_hb}（config 冇 + 啱啱出現）", flush=True)
                    except Exception as _ehb2:
                        print(f"[install-local] [WARN] 自癒deletefailed: {_fn_hb} ({_ehb2})", flush=True)
    except Exception as _ehb3:
        print(f"[install-local] [WARN] 自癒檢查failed: {_ehb3}", flush=True)

    # 4. 寫 config（預設值 — 前端會覆蓋）
    try:
        config = json.loads(current_user.ea_config or '{}')
        base = os.path.splitext(filename)[0]
        config.setdefault(base, 'EURUSD')
        config.setdefault(base + '_tf', 'H1')
        # [ALERT] 2026-09-01 FIX（user實測：magic 亂）：讀 EA 內部 InpMagic（唔係 default 240701）
        _ea_src1 = None
        for _ed1 in experts_dirs:
            _cand1 = os.path.join(_ed1, filename)
            if os.path.isfile(_cand1):
                _ea_src1 = _cand1
                break
        if _ea_src1:
            config.setdefault(base + '_magic', _ea_magic_from_source(_ea_src1))
        else:
            config.setdefault(base + '_magic', '240701')
        config.setdefault(base + '_lot', 1.00)
        # 重新配對 → 由 _removed remove（Bug #64：beforedelete過嘅 EA 重新配對後唔顯示）
        removed = config.get('_removed', [])
        if base in removed:
            removed.remove(base)
            config['_removed'] = removed
        current_user.ea_config = json.dumps(config)
        db.session.commit()
    except Exception as e:
        print(f"[install-local] config writefailed: {e}")

    # 5. Double-check：等 compile done（最多 45 秒）— 唔可以假success
    #    .mq5 需要 watcher compile → poll .ex5 出現
    compile_ok = None  # None=唔需要 compile, True=success, False=failed
    if filename.lower().endswith('.mq5'):
        compile_ok = False
        exp_dir = experts_dirs[0] if experts_dirs else None
        if exp_dir:
            # [WARN] 2026-08：EA 喺 Experts 根dir
            ex5_target = None
            for _d in (exp_dir,):
                _p = os.path.join(_d, os.path.splitext(filename)[0] + '.ex5')
                if os.path.isfile(_p):
                    ex5_target = _p
                    break
            if ex5_target is None:
                ex5_target = os.path.join(exp_dir, os.path.splitext(filename)[0] + '.ex5')
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
                    # compile cmd 已處理但 .ex5 未生成 → failed
                    compile_ok = False
                    break
                time.sleep(1.5)

    log_activity('ea_install', f'{os.path.splitext(filename)[0]} 已安裝到local MT5' + (
        '（compile success）' if compile_ok else '（compile failed）' if compile_ok is False and filename.lower().endswith('.mq5') else ''), ea=os.path.splitext(filename)[0])
    # [TARGET] 配對 → 分配快捷鍵（2026-08 user設計：添加時 set 快捷鍵 — 唔重複）
    try:
        _hk = assign_hotkey(os.path.splitext(filename)[0])
        if _hk:
            print(f"[install-local] {os.path.splitext(filename)[0]} 快捷鍵: {_hk}")
    except Exception:
        pass
    # [ALERT] 2026-08-10：配對done → steps（檢查 compile_ok — failed唔好話success — user投訴）
    # [ALERT] 2026-08-10 修：compile_ok null（compile_cmd 已寫 — watcher 處理緊）→ 唔immediately寫「done」— 等 watcher（唔好「假done」→ 網頁兩個按鈕）
    # [ALERT] 2026-08-31 FIX：compile_ok True/None → 都寫「完成配對 done」（之前淨係 False 先寫 steps — True/None 永遠 pending — user 投訴「等待完成配對冇完成」）
    if compile_ok is False:
        try:
            import json as _jin2
            _adir_in2 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
            _sf_in = os.path.join(_adir_in2, '.ai_control.steps')
            # [ALERT] 2026-08-29 FIX：雙寫（開發dir + TradotcomAgent — PC版warning視窗一致）
            _write_ai_flags(None, [
                {'text': f'Pairing {os.path.splitext(filename)[0]} in progress...', 'status': 'done'},
                {'text': 'Pairing failed (compile failed)', 'status': 'done'},
            ])
            # [ALERT] 清 show flag（done → 唔會再「不停彈」— 視窗保持顯示（確定 — user撳先關））
            for _sf_dir2 in [_adir_in2, os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TradotcomAgent')]:
                _sf_show2 = os.path.join(_sf_dir2, '.ai_control.show')
                try:
                    if os.path.exists(_sf_show2):
                        os.remove(_sf_show2)
                except Exception:
                    pass
        except Exception:
            pass
    else:
        # ✅ 2026-08-31 FIX：compile success（或唔使 compile）→ 寫「完成配對 done」— 唔再卡 pending
        try:
            _adir_ok = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
            _write_ai_flags(None, [
                {'text': f'Pairing {os.path.splitext(filename)[0]} in progress...', 'status': 'done'},
                {'text': 'Copy file to local (Experts root)', 'status': 'done'},
                {'text': f'Compile {filename} → .ex5', 'status': 'done'},
                {'text': 'Pairing complete', 'status': 'done'},
            ])
            # 清 show flag（配對完成 → 唔會再「不停彈」）
            for _sf_dir_ok in [_adir_ok, os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TradotcomAgent')]:
                _sf_show_ok = os.path.join(_sf_dir_ok, '.ai_control.show')
                try:
                    if os.path.exists(_sf_show_ok):
                        os.remove(_sf_show_ok)
                except Exception:
                    pass
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
        "message": f"{filename} 已安裝到local MT5" + (
            '（已編譯 [OK]）' if compile_ok else '（[WARN] compile failed，MT5 可能未顯示 — 檢查 MetaEditor）' if compile_ok is False and filename.lower().endswith('.mq5') else '')
    })

def _mt5_hotkeys_ini():
    """搵 hotkeys.ini path"""
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
        # [WARN] hotkeys.ini 用尖括號 <experts>（唔係方括號）— 2026-08-06 bug 修復
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
    """寫回 hotkeys.ini（UTF-16 LE — user實測格式 2026-08-06：
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
        print(f"[hotkeys] 已write {p}")
        return True
    except Exception as e:
        print(f"[hotkeys] writefailed: {e}")
        return False


def _alloc_hotkey(experts):
    """分配下一個可用快捷鍵（Ctrl+1..9, Ctrl+0, Ctrl+Alt+1..9, Ctrl+Alt+0 — 唔重複）
    [ALERT] 2026-08-17：Ctrl+9 預留俾 OpenChart script（一體化deploy用）— EA 唔可以攞 Ctrl+9"""
    used = set(experts.values())
    used.add('Ctrl+9')  # [ALERT] 預留 Ctrl+9（OpenChart script 一體化）
    # candidates 排除 Ctrl+9（EA 用其它數字）
    candidates = [f'Ctrl+{i}' for i in range(1, 10) if i != 9] + ['Ctrl+0'] + \
                 [f'Ctrl+Alt+{i}' for i in range(1, 10)] + ['Ctrl+Alt+0']
    for c in candidates:
        if c not in used:
            return c
    return None


def assign_hotkey(ea_name):
    """配對時分配快捷鍵 + write hotkeys.ini（MT5 立即認得 — 唔使 GUI）"""
    try:
        experts, indicators, _ = _read_hotkeys_ini()
        # 已exists就保留（唔重複分配）
        for k, v in experts.items():
            if ea_name in k:
                return v
        combo = _alloc_hotkey(experts)
        if not combo:
            print(f"[hotkeys] 冇可用快捷鍵（太多 EA）")
            return None
        # path：Experts\<EA>.ex5
        experts[f'Experts\\{ea_name}.ex5'] = combo
        if _write_hotkeys_ini(experts, indicators):
            print(f"[hotkeys] {ea_name} → {combo}")
            return combo
        return None
    except Exception as e:
        print(f"[hotkeys] assign failed: {e}")
        return None


def release_hotkey(ea_name):
    """delete時remove快捷鍵（釋放位置）"""
    try:
        experts, indicators, _ = _read_hotkeys_ini()
        removed = False
        for k in list(experts.keys()):
            if ea_name in k:
                del experts[k]
                removed = True
        if removed:
            _write_hotkeys_ini(experts, indicators)
            print(f"[hotkeys] {ea_name} 快捷鍵已remove（位置釋放）")
        return removed
    except Exception as e:
        print(f"[hotkeys] release failed: {e}")
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
    """MT5 進程start時間（epoch）— 用 wmic"""
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
    """hotkeys.ini 有冇新過 MT5 start（有 = 快捷鍵未 load — 要重啟 MT5）"""
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
    """重啟 MT5（關 → 開 — reload hotkeys.ini）— 2026-08 user實測：快捷鍵要重啟先 load
    [ALERT] 2026-08-10：重啟期間顯示warning視窗（MT5 關閉都有 — user要知道操作緊）"""
    try:
        import subprocess as _sp
        import json as _j
        # warning視窗（PC版 — 寫 flag）— [ALERT] 2026-08-12 FIX：累積模式（唔覆蓋現有 steps — deploy前重啟 MT5 唔會洗走deploy流程）+ done後唔刪 steps（spec：steps 永不delete）
        try:
            _ad = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
            with open(os.path.join(_ad, '.ai_control.show'), 'w', encoding='utf-8') as _f:
                _f.write('[RETRY] 重啟 MT5 中（載入快捷鍵）— 請稍候約 1 分鐘')
            _sf_rt = os.path.join(_ad, '.ai_control.steps')
            _cur_rt = []
            try:
                if os.path.isfile(_sf_rt):
                    _cur_rt = _j.load(open(_sf_rt, 'r', encoding='utf-8'))
                    if not isinstance(_cur_rt, list):
                        _cur_rt = []
            except Exception:
                _cur_rt = []
            _cur_rt = [s for s in _cur_rt if isinstance(s, dict) and s.get('text') != 'Waiting for operation to start...']
            # append 重啟 MT5 3 步（同名更新）
            for _rstep in [{"text": "關閉 MT5", "status": "doing"},
                           {"text": "載入快捷鍵設定", "status": "pending"},
                           {"text": "重新start MT5", "status": "pending"}]:
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
        # [ALERT] 2026-08-12 FIX：done → 唔delete steps（spec：steps 永不delete — delete → 網頁空白/彈）— 只更新 3 步全部 done
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
                if isinstance(_s, dict) and _s.get('text') in ('關閉 MT5', '載入快捷鍵設定', '重新start MT5'):
                    _s['status'] = 'done'
            if _cur_rt2:
                with open(_sf_rt2, 'w', encoding='utf-8') as _f:
                    _j.dump(_cur_rt2, _f, ensure_ascii=False)
        except Exception:
            pass
        print("[hotkeys] MT5 已重啟（reload 快捷鍵）")
        return True
    except Exception as e:
        print(f"[hotkeys] 重啟 MT5 failed: {e}")
        return False


@app.route('/api/ea-library/retry-compile/<name>', methods=['POST'])
@login_required

def ensure_hotkey_for_ea(ea_name):
    """deploy前確保 EA 有快捷鍵（2026-08：MT5 重啟會覆寫 hotkeys.ini — 未經 GUI 設定嘅新 EA 快捷鍵會冇）
    冇快捷鍵 → 分配 + 關 MT5 → 寫 → 開（reload）→ 返回 True（已就緒）"""
    try:
        experts, indicators, _ = _read_hotkeys_ini()
        # 已有快捷鍵
        for k, v in experts.items():
            if ea_name in k:
                return True
        # 冇 → 分配（[ALERT] 2026-08-10 優化：唔同步 reload — 改「deploy前一次過 reload」（watcher/auto_attach 檢查 mtime — 唔好每次deploy卡 105 秒））
        combo = _alloc_hotkey(experts)
        if not combo:
            return False
        experts[f'Experts\\{ea_name}.ex5'] = combo
        if _write_hotkeys_ini(experts, indicators):
            print(f"[hotkeys] {ea_name} → {combo}（已分配 — deploy時 reload）")
            return True
        return False
    except Exception as e:
        print(f"[hotkeys] ensure failed: {e}")
        return False



def api_ea_retry_compile(name):
    """重試編譯（MetaEditor GUI compile — watcher 有 desktop access）
    手動重試 compile：檢查 .mq5 喺local → 重新寫 compile_cmd → 等 compile done（double-check）
    用喺：before compile failed（假success）after，user撳「重試」再觸發
    """
    import re as _re
    import time as _ct
    if not _re.fullmatch(r'[A-Za-z0-9_]+', name):
        return jsonify({"success": False, "error": "Invalid name"}), 400

    # [WARN] user要求（2026-08）：每次操作 MT5 相關嘢，先偵測 MT5 有冇開 — 冇就開返
    ensure_mt5_running()

    # 1. 搵local .mq5
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
        return jsonify({"success": False, "error": f"{name}.mq5 唔喺local MT5 Experts dir"}), 404

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

    # 3. Double-check：等 compile done（最多 45 秒）
    compile_ok = False
    deadline = time.time() + 45
    while time.time() < deadline:
        cmd_left = glob.glob(os.path.join(common_files, f'compile_cmd_{name}_*.json'))
        if os.path.exists(ex5_path) and os.path.getmtime(ex5_path) > os.path.getmtime(mq5_path):
            compile_ok = True
            break
        if not cmd_left:
            compile_ok = False  # compile cmd 已處理但 .ex5 未生成 → failed
            break
        time.sleep(1.5)

    log_activity('ea_retry_compile', f'{name} 重試 compile ' + ('success' if compile_ok else 'failed'), ea=name)
    return jsonify({
        "success": True,
        "compile_ok": compile_ok,
        "message": f"{name} 重試 compile " + ('success [OK]' if compile_ok else 'failed — 檢查源碼或 MetaEditor')
    })


@app.route('/api/ea-library/upload', methods=['POST'])
@login_required
def api_ea_upload():
    """user上傳自己嘅 EA（只有自己睇到）+ 自動安裝落local MT5（聯動配對庫）"""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    if not file.filename.endswith(('.mq5', '.ex5')):
        return jsonify({"error": "Only .mq5 and .ex5 files allowed"}), 400

    # 寫「處理中」log — user想知系統有冇處理緊
    _ubase = os.path.splitext(file.filename)[0]
    log_activity('ea_upload', f'{_ubase} 上傳處理中...', ea=_ubase)

    # 儲存去user專屬dir
    user_dir = os.path.join(UPLOAD_DIR, current_user.username)
    os.makedirs(user_dir, exist_ok=True)
    filename = secure_filename(file.filename)
    filepath = os.path.join(user_dir, filename)
    file.save(filepath)

    # 聯動：自動安裝落local MT5 Experts dir（配對庫immediately見到）
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
        # [ALERT] 2026-09-01 FIX（user實測：magic 亂）：讀 EA 內部 InpMagic
        _ea_src2 = None
        for _ed2 in experts_dirs:
            _cand2 = os.path.join(_ed2, filename)
            if os.path.isfile(_cand2):
                _ea_src2 = _cand2
                break
        if _ea_src2:
            config.setdefault(base + '_magic', _ea_magic_from_source(_ea_src2))
        else:
            config.setdefault(base + '_magic', '240701')
        config.setdefault(base + '_lot', 1.00)
        # 重新配對 → 由 _removed remove（Bug #64）
        removed = config.get('_removed', [])
        if base in removed:
            removed.remove(base)
            config['_removed'] = removed
        current_user.ea_config = json.dumps(config)
        db.session.commit()
    except Exception as e:
        print(f"[upload] config writefailed: {e}")

    # Double-check：等 compile done（最多 45 秒）— 唔可以假success
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
                    compile_ok = False  # compile cmd 已處理但 .ex5 未生成 → failed
                    break
                time.sleep(1.5)

    log_activity('ea_upload', f'{base} 上傳 + 安裝到local MT5' + (
        '（compile success）' if compile_ok else '（compile failed）' if compile_ok is False and filename.lower().endswith('.mq5') else ''), ea=base)
    return jsonify({
        "success": True,
        "filename": filename,
        "size": f"{os.path.getsize(filepath)/1024:.1f} KB",
        "installed_local": bool(install_result),
        "compiled": bool(compile_ok),
        "compile_ok": compile_ok,
        "message": f"{base} 已上傳 + 安裝到local MT5" + (
            '（已編譯 [OK]）' if compile_ok else '（[WARN] compile failed，MT5 可能未顯示）' if compile_ok is False and filename.lower().endswith('.mq5') else '')
    })


@app.route('/api/agent-download')
def api_agent_download():
    """下載 Windows Agent start器（.bat — double-click 一定開到）— 自動下載 + 執行桌面版安裝程式"""
    # [ALERT] 2026-09-02 FIX（VPS 404）：用絕對路徑（abspath 消走 '..'）— 新版 werkzeug safe_join 拒絕相對 '..' 路徑 → 404
    agent_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'agent'))
    # [ALERT] 2026-08-26 v2：.bat start器（.pyw double-click 冇關聯唔開）→ bat 自動搵 pythonw + 下載 pyw + 執行
    _bat = os.path.join(agent_dir, 'tradotcom_launcher.bat')
    if os.path.isfile(_bat):
        return send_from_directory(agent_dir, 'tradotcom_launcher.bat', as_attachment=True, download_name='Tradotcom-Agent-Setup.bat')
    return send_from_directory(agent_dir, 'install_agent.bat')

@app.route('/api/agent-pyw')
def api_agent_pyw():
    """下載桌面版安裝程式（tradotcom_agent.pyw）"""
    agent_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'agent'))
    _f = os.path.join(agent_dir, 'tradotcom_agent.pyw')
    if os.path.isfile(_f):
        return send_from_directory(agent_dir, 'tradotcom_agent.pyw', as_attachment=True, download_name='Tradotcom-Agent-Setup.pyw')
    return jsonify({"error": "not found"}), 404


@app.route('/api/agent-py')
def api_agent_py():
    """下載 agent.py"""
    agent_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'agent'))
    return send_from_directory(agent_dir, 'agent.py')


@app.route('/api/agent-service/<name>')
def api_agent_service(name):
    """[ALERT] 2026-08-28（user要求：安裝 = 全部裝返）：下載平台服務腳本（deploy_watcher/alert_worker/auto_trade_detector）
    agent start時缺file → 從 server 下載 → 開返
    """
    _allowed = {'deploy_watcher.py', 'alert_worker.py', 'auto_trade_detector.py', 'deploy_notify.py',
                'auto_attach.py', 'refresh_navigator.py', 'control_guard.py'}
    if name not in _allowed:
        return jsonify({"error": "not allowed"}), 403
    agent_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'agent'))
    _f = os.path.join(agent_dir, name)
    if os.path.isfile(_f):
        return send_from_directory(agent_dir, name)
    return jsonify({"error": "not found"}), 404


# === WebSocket: Agent ===
@socketio.on('connect')
def handle_connect():
    print(f"[WS] Connected: {request.sid}")

# Debounce auto-send — avoid re-sending EA config on rapid reconnections
_last_config_send = {}

@socketio.on('agent_register')
def handle_register(data):
    agent = Agent.query.filter_by(agent_id=data.get('agent_id')).first()
    if not agent:
        # [ALERT] 2026-09-02 FIX（B 電腦 fef654c3 情況）：agent 唔存在（剷除咗/從未註冊/錯 ID）
        # → 明確回覆 error — agent 收到後會清 config + 彈安裝精靈（唔好靜默 — 用戶以為裝咗）
        print(f"[WS] [WARN] Agent {data.get('agent_id')} 唔存在（refusedconnection）")
        emit('registered', {"status": "error", "msg": "unknown_agent"})
        return
    if agent:
        # [ALERT] 2026-08-26（Phase 4）：Token 驗證 — 防冒認（agent 有 token 先驗證；DEV00001 舊版冇 token → 放行向後兼容）
        _tk_in = str(data.get('token') or '')
        _tk_real = str(agent.agent_token or '')
        if _tk_real and _tk_in != _tk_real:
            print(f"[WS] [WARN] Agent {agent.agent_id} token 唔啱（refusedconnection）")
            emit('registered', {"status": "error", "msg": "invalid token"})
            return
        join_room(agent.agent_id)
        agent.status = 'connected'
        agent.last_seen = datetime.utcnow()
        db.session.commit()
        emit('registered', {"status":"ok"})
        # [ALERT] 2026-08-26（安裝驗證）：Agent 連上 → 通知前端（toast「[OK] Agent 已connection」）
        try:
            socketio.emit('agent_connected', {"agent_id": agent.agent_id, "msg": f"[OK] Agent {agent.agent_id} 已connection"}, room=agent.agent_id)
        except Exception:
            pass
        # 自動推送 EA 配置俾 Agent（debounce: 每 60 秒最多一次）
        # [ALERT] 2026-09-01 FIX（用戶實測：冇操作都開 MT5 + refresh 導航頁）：
        # agent 每 60 秒 reconnect → 每次 reconnect 都過咗 60 秒 debounce → 每次 auto-sent EA config
        # → agent 心跳注入 touch .mq5 → watcher 偵測變化 → refresh Navigator + 開 MT5
        # → debounce 加長（60 → 300 秒）— 就算 agent 每 60 秒 reconnect 都唔會每次 auto-sent
        user = agent.user
        if user and user.ea_config and user.ea_config != '{}':
            try:
                import time as _t
                now = _t.time()
                last = _last_config_send.get(agent.agent_id, 0)
                if now - last < 300:
                    print(f"[WS] Skip auto-send (debounce 300s): {agent.agent_id} ({now-last:.0f}s ago)")
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
        # [ALERT] 2026-08-26（Phase 4）：sync 都驗證 token（防冒名上報）
        try:
            _tk_s = str(data.get('token') or '')
            _tk_sr = str(agent.agent_token or '')
            if _tk_sr and _tk_s != _tk_sr:
                print(f"[WS] [WARN] Agent {agent.agent_id} sync token 唔啱（忽略）")
                return
        except Exception:
            pass
        agent.account_info = json.dumps(data.get('account',{}))
        agent.positions = json.dumps(data.get('positions',[]))
        agent.deals = json.dumps(data.get('deals',[]))
        agent.ea_heartbeats = json.dumps(data.get('heartbeats', {}))
        # [ALERT] 2026-08-26（multi-user Phase 1）：儲存 agent 上報嘅file快照（每機獨立 — server 唔再直接讀local）
        if data.get('files_snapshot'):
            agent.files_snapshot = json.dumps(data.get('files_snapshot'))
            # [ALERT] 2026-08-27 FIX：agent 心跳實際喺 files_snapshot.heartbeats（build_files_snapshot 收集）
            # → 合併入 ea_heartbeats（網頁心跳顯示用）— 唔好得 files_snapshot 有
            _snap_hb = data.get('files_snapshot', {}).get('heartbeats') or {}
            if _snap_hb:
                _merged_hb = dict(data.get('heartbeats', {}))
                for _k_hb, _v_hb in _snap_hb.items():
                    _merged_hb[_k_hb] = _v_hb
                agent.ea_heartbeats = json.dumps(_merged_hb)
        agent.last_seen = datetime.utcnow()
        agent.status = data.get('status','connected')
        # [ALERT] 2026-09-03（VPS 搬遷）：agent 上報嘅 steps → 寫 server 自己 .ai_control.steps（網頁 modal 讀）
        # （agent 喺 A/B 電腦做操作 — steps 喺 agent 本地 — 要上報 server 網頁先同步）
        try:
            _steps_sync = data.get('control_steps')
            if isinstance(_steps_sync, list) and _steps_sync:
                _dev_dir_sync = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
                _sf_sync = os.path.join(_dev_dir_sync, '.ai_control.steps')
                with open(_sf_sync, 'w', encoding='utf-8') as _f_sy:
                    json.dump(_steps_sync, _f_sy, ensure_ascii=False)
        except Exception:
            pass
        db.session.commit()
        emit('agent_update', {}, room=agent.agent_id)

@socketio.on('agent_install_ea')
def handle_install_ea(data):
    """user㩒 Install EA，通知 Agent 去下載同安裝"""
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
        # 亦write DB（fallback）
        agent.deploy_queue = json.dumps({
            "ea_name": data.get('ea_name'),
            "symbol": data.get('symbol'),
            "tf": data.get('tf'),
            "magic": data.get('magic'),
            "lot": data.get('lot')
        })
        db.session.commit()
        emit('install_result', {"status": "sent", "ea": data.get('ea_name')})

def _detect_uac_server():
    """[ALERT] 2026-08-22（user要求：UAC 檢測機制）：server 端偵測 UAC/授權窗口
    deploy/delete/配對前檢查 — 有 UAC → 返回 True（前端可顯示warning）
    用 ctypes EnumWindows 掃「授權/Client Terminal/要求」窗口"""
    try:
        import ctypes as _ct_u
        _u_u = _ct_u.windll.user32
        _found = []
        def _cb_u(h, _):
            try:
                _l = _u_u.GetWindowTextLengthW(h)
                if _l > 0:
                    _b = _ct_u.create_unicode_buffer(_l + 1)
                    _u_u.GetWindowTextW(h, _b, _l + 1)
                    _t = _b.value
                    _c = _ct_u.create_unicode_buffer(128)
                    _u_u.GetClassNameW(h, _c, 128)
                    _cl = _c.value
                    if ('授權' in _t or 'Client Terminal' in _t or '要求' in _t or '允許' in _t) or ('Secure UAP' in _cl or 'consent' in _cl.lower()):
                        _found.append(_t[:50])
            except Exception:
                pass
            return True
        _u_u.EnumWindows(_ct_u.WINFUNCTYPE(_ct_u.c_bool, _ct_u.c_size_t, _ct_u.c_size_t)(_cb_u), 0)
        return _found
    except Exception:
        return []

def _cleanup_local_agent():
    """[ALERT] 2026-08-28（user要求：remove Agent = 清晒nowPCrunning緊嘅 agent 嘢）：
    殺平台服務（watcher/detector/alert — local agent dir）+ 刪 lock + 刪安裝dir
    """
    import subprocess, shutil
    print("[API] [CLEAN] 清理local Agent（平台服務 + lock + 安裝dir）...")
    # 1. 殺平台服務（agent dir嘅 python process — 唔好殺自己/server/hermes）
    try:
        _ps = subprocess.run(
            'powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq \'python.exe\' -and ($_.CommandLine -match \'TradotcomAgent|agent/(deploy_watcher|auto_trade_detector|alert_worker|auto_attach|deploy_notify|control_guard)\') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"',
            shell=True, capture_output=True, timeout=30)
        print(f"   [OK] 平台服務已殺（{_ps.returncode}）")
    except Exception as e:
        print(f"   [WARN] 殺平台服務failed: {e}")
    time.sleep(2)
    # 2. 刪 lock + 安裝dir
    _agent_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TradotcomAgent')
    try:
        if os.path.isdir(_agent_dir):
            shutil.rmtree(_agent_dir, ignore_errors=True)
            print(f"   [OK] 安裝dir已刪: {_agent_dir}")
        else:
            print(f"   ℹ️ 安裝dirnot exist: {_agent_dir}")
    except Exception as e:
        print(f"   [WARN] 刪安裝dirfailed: {e}")
    # 3. 刪桌面捷徑
    try:
        _desktop = os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop')
        for _f in os.listdir(_desktop):
            if 'Tradotcom' in _f or '交易點' in _f:
                os.remove(os.path.join(_desktop, _f))
                print(f"   [OK] 桌面捷徑已刪: {_f}")
    except Exception:
        pass
    print("[API] [CLEAN] local清理done")

@app.route('/api/agent/remove', methods=['POST'])
@login_required
def api_agent_remove():
    """[ALERT] 2026-08-28（user要求：網站可以removelocal agent）：
    發 shutdown 指令俾 agent → agent 自己清理（lock/config/捷徑）+ 退出
    """
    agent = Agent.query.filter_by(user_id=current_user.id).first()
    if not agent:
        return jsonify({"success": False, "error": "no agent"}), 404
    try:
        print(f"[API] 🚫 remove Agent {agent.agent_id}（網站操作）")
        # 發 shutdown 指令俾 agent（SocketIO room=agent_id）
        socketio.emit('shutdown', {'reason': 'web_remove'}, room=agent.agent_id)
        # [ALERT] 2026-08-28 FIX：寫remove標記落 DB（agent disconnect收唔到 emit → poll /api/agent-poll-deploy 時檢查）
        # （同 deploy_queue 一樣機制 — tunnel disconnect窗口 fallback）
        try:
            _rm_flag = json.loads(agent.deploy_queue) if agent.deploy_queue else {}
        except Exception:
            _rm_flag = {}
        _rm_flag['_remove_agent'] = True
        _rm_flag['_remove_ts'] = time.time()
        agent.deploy_queue = json.dumps(_rm_flag)
        # [ALERT] 2026-08-28 FIX：agent offline（disconnect/冇行）→ 唔刪 DB（user要求：remove = 清local agent — DB 記錄保留 — after可重新安裝connect返）
        # 只清local（平台服務 + lock + 安裝dir）
        if agent.status != 'connected':
            print(f"[API] [WARN] Agent {agent.agent_id} 已 offline — 清理local（保留 DB 記錄）")
            _cleanup_local_agent()
            return jsonify({"success": True, "message": f"Agent {agent.agent_id}（offline）local已清理（DB 記錄保留）"})
        # 標記 agent 已remove（status=offline — 等 agent 回報 remove-complete 再刪）
        agent.status = 'offline'
        db.session.commit()
        return jsonify({"success": True, "message": f"remove指令已發俾 Agent {agent.agent_id}"})
    except Exception as e:
        print(f"[API] [WARN] remove Agent failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/agent/remove-complete', methods=['POST'])
def api_agent_remove_complete():
    """Agent removedone回報（agent 自己清理完 call）— [ALERT] 2026-08-28 FIX：唔刪 DB（user要求：remove = 清local — DB 記錄保留 — after可重新安裝connect返）— 只標記 offline"""
    agent_id = request.args.get('agent_id') or (request.get_json(silent=True) or {}).get('agent_id')
    if not agent_id:
        return jsonify({"success": False, "error": "no agent_id"}), 400
    agent = Agent.query.filter_by(agent_id=agent_id).first()
    if agent:
        print(f"[API] [OK] Agent {agent_id} 已remove（agent 回報）— 標記 offline（DB 記錄保留）")
        agent.status = 'offline'
        db.session.commit()
    return jsonify({"success": True})


@app.route('/api/deploy', methods=['POST'])
@login_required
def api_deploy():
    """HTTP deploy (唔靠 Socket.IO，更可靠)"""
    # [ALERT] 2026-08-22（user要求：UAC 檢測機制）：deploy前檢查 UAC — 有授權窗口 → warning（唔阻deploy — 等 auto_attach 處理）
    try:
        _uac_now = _detect_uac_server()
        if _uac_now:
            print(f"[deploy] [WARN] 偵測到 UAC 授權窗口: {_uac_now[0]} — deploy會等 auto_attach UAC Gate 處理")
            log_activity('deploy', f'[WARN] MT5 需要授權（{_uac_now[0][:40]}）— 請確認', ea='MT5')
    except Exception:
        pass
    # [ALERT] 2026-08-12 FIX：防重複deploy（同一 EA 30 秒內唔可以再 deploy — 前端 double-click / 重複觸發 → 兩個 deploy_cmd → 「done又彈又執行」）
    global _last_deploy_time
    try:
        _now_dp = time.time()
        if _last_deploy_time.get(ea_name_cached := request.json.get('ea_name', ''), 0) and _now_dp - _last_deploy_time.get(ea_name_cached, 0) < 30:
            return jsonify({"success": False, "error": f"{ea_name_cached} 30 秒內已deploy過（防重複）"}), 429
    except Exception:
        pass
    # [WARN] user要求（2026-08）：每次操作 MT5 相關嘢，先偵測 MT5 有冇開 — 冇就開返
    ensure_mt5_running()
    data = request.json
    ea_name = data.get('ea_name', '')
    symbol = data.get('symbol', 'EURUSD')
    tf = data.get('tf', 'H1')
    # [ALERT] 2026-08-21 FIX（user要求：揀咗冇嘅 symbol → 偵測 → warning — 唔可以deploy）：
    # deploy前驗證 symbol exists（account實際 symbols — get_account_symbols）
    try:
        _avail_syms = get_account_symbols()
        if symbol.upper() not in [s.upper() for s in _avail_syms]:
            print(f"[deploy] [WARN] {ea_name} → {symbol}：symbol 唔喺account（可用: {_avail_syms[:10]}...）")
            return jsonify({"success": False, "error": f"symbol {symbol} not exist（account可用: {', '.join(_avail_syms[:8])}）"}), 400
    except Exception as _e_sym:
        print(f"[deploy] symbol verify failed（唔阻deploy）: {_e_sym}")
    # [ALERT] 2026-08-20 FIX：magic 空 string（前端未 alive EA 傳 ''）→ fallback default（否則 auto_attach --magic 空 → argparse failed → 假success）
    magic = data.get('magic') or '240701'
    # [ALERT] 2026-08-26 FIX v2（行內人做法 — user要求）：Magic = EA 固定身份 — 一生唔變
    # ① 每個 EA 首次deploy分配固定 magic（存 config['_magic_assignments'] — _開頭 DELETE 唔會清）
    # ② remove後再deploy → 沿用返舊 magic（歷史連貫 — Correlation/統計完整）
    # ③ user指定特別 magic（777/888 等）→ 尊重user（唔覆寫）
    # ④ 只有「首次deploy + 有user冇指定」先自動分配
    try:
        _cfg_m = json.loads(current_user.ea_config or '{}')
        _assign_tbl = _cfg_m.get('_magic_assignments') or {}
        if not isinstance(_assign_tbl, dict):
            _assign_tbl = {}
        _req_magic = str(data.get('magic') or '').strip()
        # ① EA 已有分配 → 沿用（行內人：歷史連貫 — 就算remove再deploy都用返同一個）
        if ea_name in _assign_tbl:
            magic = _assign_tbl[ea_name]
            print(f"[deploy] [KEY] {ea_name} 沿用固定 Magic {magic}（歷史連貫）")
        # ② user明確指定（唔係 240701 default）→ 尊重 + 記錄
        elif _req_magic and _req_magic != '240701':
            magic = _req_magic
            _assign_tbl[ea_name] = magic
            print(f"[deploy] [KEY] {ea_name} user指定 Magic {magic}")
        # ③ 首次deploy + 用 default → 自動分配未用嘅固定 magic
        else:
            _used_all = set()
            for _k_m2, _v_m2 in _cfg_m.items():
                if _k_m2.endswith('_magic') and str(_v_m2).isdigit():
                    _used_all.add(str(_v_m2))
            for _v_m3 in _assign_tbl.values():
                _used_all.add(str(_v_m3))
            _new_m = 240701
            while str(_new_m) in _used_all:
                _new_m += 1
            magic = str(_new_m)
            _assign_tbl[ea_name] = magic
            print(f"[deploy] [KEY] {ea_name} 首次分配固定 Magic {magic}")
        # 同步分配表返 config（_開頭 — DELETE 唔會清 — 持久保留）
        try:
            _cfg_m['_magic_assignments'] = _assign_tbl
            current_user.ea_config = json.dumps(_cfg_m)
            db.session.commit()
        except Exception:
            pass
    except Exception:
        pass
    lot = data.get('lot', '1.00')
    # [ALERT] 2026-08-21：數據注入選擇（userdeploy時揀 — 注入逐單記錄 / 唔注入）
    # 預設 true（注入）— 前端 modal 可選「唔注入」+「不再顯示」
    inject_trades = data.get('inject_trades', True)
    _last_deploy_time[ea_name] = time.time()
    
    # Save EA config first
    config = json.loads(current_user.ea_config or '{}')
    # [ALERT] 2026-08-22 FIX（配對庫消失 bug）：重新deploy = 唔再係「已delete」→ 由 _removed remove
    # （beforedelete加 _removed，但重新deploy冇清 → 前端過濾走晒 → 配對庫空）
    try:
        _rm_dp = config.get('_removed', [])
        if ea_name in _rm_dp:
            _rm_dp.remove(ea_name)
            config['_removed'] = _rm_dp
            print(f"[deploy] [OK] {ea_name} 已由 _removed remove（重新配對）")
    except Exception:
        pass
    config[ea_name] = symbol
    config[f'{ea_name}_tf'] = tf
    config[f'{ea_name}_magic'] = str(magic)
    config[f'{ea_name}_lot'] = float(lot)
    current_user.ea_config = json.dumps(config)

    # [ALERT] 2026-08-19：Script 類型暫時唔支援deploy（唔嘗試 deploy — 直接話「不支援」）
    try:
        _is_scr = False
        for _d_sc_dir in (EA_LIBRARY_DIR, os.path.join(UPLOAD_DIR, current_user.username), COMMUNITY_EA_DIR):
            _mq5_sc = os.path.join(_d_sc_dir, ea_name + '.mq5')
            if os.path.isfile(_mq5_sc):
                _sc_c = open(_mq5_sc, encoding='utf-8', errors='ignore').read()
                _is_scr = ('#property script_show_inputs' in _sc_c) or ('void OnStart()' in _sc_c and 'int OnInit()' not in _sc_c)
            if _is_scr:
                break
        # local已 install 嗰個做 backup 判斷
        if not _is_scr:
            _ml5t = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
            for _td in os.listdir(_ml5t) if os.path.isdir(_ml5t) else []:
                for _rel in ('MQL5\\Scripts', 'MQL5\\Experts'):
                    _mc = os.path.join(_ml5t, _td, *_rel.split('\\'), ea_name + '.mq5')
                    if os.path.isfile(_mc):
                        _mc_c = open(_mc, encoding='utf-8', errors='ignore').read()
                        _is_scr = ('#property script_show_inputs' in _mc_c) or ('void OnStart()' in _mc_c and 'int OnInit()' not in _mc_c)
                        break
                if _is_scr:
                    break
        if _is_scr:
            return jsonify({"success": False, "error": f"{ea_name} 係 Script 類型，暫不支援deploy（只支援長駐EA）"}), 400
    except Exception:
        pass
    # [WARN] Controller deploy（今日版本功能）：心跳 running → 已running；否則手動提示（+ 標記 → watcher 自動確定）
    if ea_name == 'Controller':
        try:
            sf = os.path.join(common_files, 'state_controller.json')
            if os.path.isfile(sf):
                with open(sf, 'r', encoding='utf-8') as _f:
                    _sd = json.load(_f)
                if _sd.get('status') == 'running' and int(time.time()) - int(_sd.get('ts', 0)) < 30:
                    return jsonify({"success": True, "message": "[OK] Controller 已running中（系統中樞正常）"})
        except Exception:
            pass
        log_activity('deploy', f'Controller 首次deploy：請手動 double-click（MT5Cloud folder）', ea='Controller')
        try:
            agent_dir = os.path.join(os.path.dirname(__file__), '..', 'agent')
            with open(os.path.join(agent_dir, '.manual_deploy_pending'), 'w', encoding='utf-8') as _f:
                json.dump({'ea': 'Controller', 'ts': time.time()}, _f)
        except Exception:
            pass
        return jsonify({
            "success": True,
            "manual_action": True,
            "message": "請手動done首次deploy（1 秒）：MT5 導航 → EA交易 → MT5Cloud → 雙擊 Controller。確定會自動撳！"
        })

    # [TARGET] 快捷鍵確保（2026-08：MT5 重啟會覆寫 hotkeys.ini — 未經 GUI 嘅快捷鍵會冇）
    # deploy前檢查 EA 有冇快捷鍵 — 冇就分配 + 重啟 MT5 reload
    try:
        ensure_hotkey_for_ea(ea_name)
    except Exception:
        pass

    # [ALERT] 2026-08-12 FIX：immediately寫 SHOW_FLAG + steps（deploy XXX doing）— 唔好等 auto_attach（watcher poll 3 秒 + start）
    # （否則視窗顯示舊任務殘留 steps → 1 秒後先變新 — user投訴「一start顯示舊步驟」）
    try:
        import json as _jdp
        _adir_dp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent')
        os.makedirs(_adir_dp, exist_ok=True)
        # [ALERT] 2026-08-28 FIX（PC版warning視窗冇彈）：雙寫 show + steps（開發dir + TradotcomAgent）
        _write_ai_flags(f'deploy {ea_name}', [
            {'text': f'Deploy {ea_name} ({symbol.upper()})', 'status': 'doing'},
            {'text': f'Create new chart ({symbol.upper()})', 'status': 'pending'},
            {'text': f'Attach {ea_name}', 'status': 'pending'},
            {'text': 'Verify running status', 'status': 'pending'},
        ])
    except Exception:
        pass

    # [ALERT] 2026-08-26（multi-user Phase 2）：deploy指令路由 — 優先經「user嘅 agent」（SocketIO room）
    # → agent 收到 deploy_ea → 喺自己部機寫 deploy_cmd → watcher 執行（每機獨立）
    # → 冇 agent connection（offline）→ fallback 直接寫local（單機向後兼容）
    _agent_dp = Agent.query.filter_by(user_id=current_user.id).first()
    # [ALERT] 2026-08-27 FIX：agent online 判斷用「真係上報緊」（last_seen 新鮮）— 唔係 status 欄（舊 status 會誤判 → emit 去冇人接嘅 room → deploy卡死）
    _agent_online = bool(_agent_dp and _agent_live_status(_agent_dp) == 'connected')
    if _agent_online:
        try:
            _dp_payload = {
                'agent_id': _agent_dp.agent_id,
                'ea_name': ea_name,
                'symbol': symbol,
                'tf': tf,
                'magic': str(magic),
                'lot': str(lot),
                'inject_trades': inject_trades,
                # [ALERT] 2026-09-01 FIX（用戶實測：代替 dialog 阻住部署 — 想取代其他 EA 但 auto_attach 硬性撳「否」）：
                # allow_replace: true = 用戶確認取代目標 chart 已有 EA（代替 dialog 撳「是」）；冇/false = 撳「否」保護
                'allow_replace': bool(request.json.get('allow_replace')) if request.json else False,
                'source': 'api_deploy'
            }
            socketio.emit('deploy_ea', _dp_payload, room=_agent_dp.agent_id)
            print(f"[API] 📡 Deploy 指令已路由俾 Agent {_agent_dp.agent_id}: {ea_name} -> {symbol} {tf}")
            # 亦write deploy_queue（fallback — agent 可能 reconnect 後 poll）
            _agent_dp.deploy_queue = json.dumps(_dp_payload)
            db.session.commit()
        except Exception as _e_dp:
            print(f"[API] [WARN] Agent 路由failed（fallback local）: {_e_dp}")
            _agent_online = False

    # [ALERT] 2026-08-26（multi-user Phase 2）：已路由俾 agent → 唔寫local（避免雙重執行）
    if _agent_online:
        db.session.commit()
        print(f"[API] Deploy routed via Agent: {ea_name} -> {symbol} {tf}")
        log_activity('deploy', f'{ea_name} deploy → {symbol} {tf}（經 Agent）', ea=ea_name)
        return jsonify({"success": True, "message": f"[GO] Deploying {ea_name} -> {symbol} {tf}"})

    # Write deploy command file (watcher will pick it up)
    import time as _wt
    common_files = os.path.join(os.environ.get('APPDATA', ''),
                                 'MetaQuotes', 'Terminal', 'Common', 'Files')
    os.makedirs(common_files, exist_ok=True)

    # [ALERT] 2026-08-28 FIX：delete舊 Controller fallback（generate_template + ctrl_controller.json — stable 前概念 — Controller EA 已冇行 → 死 code）
    # deploy統一經：Agent 路由（online）→ watcher deploy_cmd（fallback local）— Controller 模式已淘汰
    # 寫 deploy command file（watcher will pick it up）
    import time as _wt
    cmd_path = os.path.join(common_files, f'deploy_cmd_{ea_name}_{int(_wt.time())}.json')
    # [FP] 2026-08-31 fingerprint：deploy_cmd 帶 account + agent fingerprint（方便追蹤邊個 account create）
    _fp_account = current_user.username if (current_user and not current_user.is_anonymous) else 'unknown'
    _fp_agent = _agent_dp.agent_id if '_agent_dp' in dir() and _agent_dp else ''
    with open(cmd_path, 'w') as f:
        json.dump({
            'ea_name': ea_name,
            'symbol': symbol,
            'tf': tf,
            'magic': str(magic),
            'lot': str(lot),
            'inject_trades': inject_trades,  # [ALERT] 2026-08-21：數據注入選擇
            'allow_replace': bool(request.json.get('allow_replace')) if request.json else False,  # [ALERT] 2026-09-01：允許取代（代替 dialog 撳「是」）
            'timestamp': _wt.strftime('%Y-%m-%dT%H:%M:%S'),
            'source': 'api_deploy',
            # [FP] fingerprint（2026-08-31）
            'fingerprint': {
                'account': _fp_account,
                'agent_id': _fp_agent,
                'created_by': f"{_fp_account}/{_fp_agent}"
            }
        }, f)

    db.session.commit()
    print(f"[API] Deploy: {ea_name} -> {symbol} {tf} (command file written)")
    log_activity('deploy', f'{ea_name} deploy → {symbol} {tf}', ea=ea_name)

    # [ALERT] 2026-08-14 自癒（deploy後）：deploy都可能觸發「其他 EA 彈返」（user案例：deploy Hedge → 其他 EA 彈返）
    # deploy後清「彈返」—— ctime 新（120 秒內）+ config 冇（已delete）→ 自動delete（排除今次deploy嘅 EA）
    try:
        import time as _tdh
        _data_dir_h = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        _cfg_h = json.loads(current_user.ea_config or '{}')
        _cfg_h_eas = set(k.rsplit('_', 1)[0] for k in _cfg_h if not k.startswith('_'))
        for _d_h in os.listdir(_data_dir_h):
            _ea_dir_h = os.path.join(_data_dir_h, _d_h, 'MQL5', 'Experts')
            if not os.path.isdir(_ea_dir_h):
                continue
            for _fn_h in sorted(os.listdir(_ea_dir_h)):
                if not _fn_h.endswith(('.mq5', '.ex5')):
                    continue
                if _fn_h == ea_name + '.mq5' or _fn_h == ea_name + '.ex5':
                    continue  # 今次deploy嘅 EA — 唔好刪
                _b_h = os.path.splitext(_fn_h)[0]
                if _b_h in _cfg_h_eas:
                    continue  # config 有（正常 — 唔好亂刪）
                _fp_h = os.path.join(_ea_dir_h, _fn_h)
                if time.time() - os.path.getctime(_fp_h) < 120:  # 2 分鐘內出現 = 彈返
                    try:
                        os.remove(_fp_h)
                        print(f"[API] deploy後自癒: 已delete彈返嘅 {_fn_h}", flush=True)
                    except Exception:
                        pass
    except Exception as _edh:
        print(f"[API] [WARN] deploy後自癒failed: {_edh}", flush=True)

    return jsonify({"success": True, "message": f"[GO] Deploying {ea_name} -> {symbol} {tf}"})

@app.route('/api/clean-blank-charts', methods=['POST'])
def api_clean_blank_charts():
    """[ALERT] 2026-09-01（user要求 — 網頁「清理空白」按鈕）：清空白冇部署 EA 嘅 chart
    流程：寫 clean_cmd（watcher 處理）→ auto_attach.clean_blank_charts（關 MT5 → 清 .chr + order.wnd → 開 MT5）"""
    if current_user.is_anonymous:
        return jsonify({"error": "login required"}), 401
    try:
        import time as _wt_clean
        common_files = os.path.join(os.environ.get('APPDATA', ''),
                                     'MetaQuotes', 'Terminal', 'Common', 'Files')
        os.makedirs(common_files, exist_ok=True)
        # 寫 clean_cmd（watcher 處理）
        cmd_path = os.path.join(common_files, f'clean_cmd_{int(_wt_clean.time())}.json')
        _fp_account = current_user.username if (current_user and not current_user.is_anonymous) else 'unknown'
        with open(cmd_path, 'w') as f:
            json.dump({
                'action': 'clean_blank',
                'timestamp': _wt_clean.strftime('%Y-%m-%dT%H:%M:%S'),
                'source': 'api_clean',
                'fingerprint': {'account': _fp_account},
                'account': f'account:{_fp_account}',
            }, f)
        print(f"[API] Clean blank charts command written: {os.path.basename(cmd_path)}")
        log_activity('clean', '清空白冇 EA 嘅 chart（Clean blank charts）', ea='MT5')
        # 警告視窗（.ai_control.show + steps — alert_worker + 網頁 modal 同步）
        # [ALERT] 2026-09-01 FIX（user實測：警告視窗唔彈 — server 寫開發目錄但 alert_worker 讀安裝目錄）：
        # → 雙寫（開發 + 安裝 — 同 deploy/pause 一致）
        try:
            _dirs_cl = [
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TradotcomAgent'),
            ]
            _clean_steps_cl = [
                {'text': 'Clean blank charts', 'status': 'doing'},
                {'text': 'Remove blank charts (no EA)', 'status': 'pending'},
                {'text': 'Restart MT5', 'status': 'pending'},
                {'text': 'Verify running charts', 'status': 'pending'},
            ]
            for _dcl in _dirs_cl:
                try:
                    with open(os.path.join(_dcl, '.ai_control.show'), 'w', encoding='utf-8') as _f:
                        _f.write('clean blank charts')
                    with open(os.path.join(_dcl, '.ai_control.steps'), 'w', encoding='utf-8') as _f2:
                        json.dump(_clean_steps_cl, _f2, ensure_ascii=False)
                except Exception:
                    pass
            # [ALERT] 2026-09-03（VPS 搬遷）：SocketIO push 俾遠端 agent
            try:
                _push_alert_socket('clean blank charts', _clean_steps_cl)
            except Exception:
                pass
        except Exception as _e_clw:
            print(f"[WARN] clean steps write failed: {_e_clw}")
        return jsonify({"success": True, "message": "Clean blank charts command sent"})
    except Exception as e:
        print(f"[API] Clean blank charts error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/bind-account', methods=['POST'])
@login_required
def api_bind_account():
    """綁定當前 MT5 account 到user"""
    data = request.json
    action = data.get('action', 'bind')
    
    if action == 'bind':
        # Get current MT5 account from cache
        with _auto_trade_lock:
            acc = _auto_trade_cache.get("account_info", {})
        login = acc.get('login', '')
        if not login:
            return jsonify({"success": False, "error": "MT5 未登入或cannot獲取 account info"})
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
    """健康檢查 — single-instance guard + 監控用"""
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

    # ─── single-instance guard：如果 :port 已經有 healthy server，退出唔重複start ───
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
        print(f"[WARN]  :{port} 已經有 healthy server running緊，this instance exits（single-instance guard）")
        sys.exit(0)

    # Bind 測試：確保我哋先霸到 port（防止 race condition）
    # [WARN] 唔可以用 SO_REUSEADDR — Windows 上呢個 flag 允許兩個 process bind 同一 port（before duplicates 根源）
    try:
        _probe = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        _probe.bind(('0.0.0.0', port))
        _probe.close()
    except OSError:
        print(f"[WARN]  :{port} 被佔用，this instance exits")
        sys.exit(0)

    print(f"☁️  Tradotcom Server :{port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=True, use_reloader=False)