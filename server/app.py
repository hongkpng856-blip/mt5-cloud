# MT5 Cloud — Full Platform Server
# 公開網站，每人有自己的 EA 配對 + 分析 + Correlation

import os
import json
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
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
        return render_template('dashboard.html')
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

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
            login_user(user)
            return jsonify({"success":True})
        return jsonify({"error":"Invalid credentials"}),401
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
        config = json.loads(current_user.ea_config or '{}')
        return jsonify({"mappings": config, "all_symbols": ALL_SYMBOLS, "timeframes": TIMEFRAMES})
    else:
        data = request.json
        current_user.ea_config = json.dumps(data.get('mappings', {}))
        db.session.commit()
        return jsonify({"success": True})

@app.route('/api/ea-config/<ea_name>', methods=['DELETE'])
@login_required
def api_ea_config_delete(ea_name):
    """刪除一個 EA 嘅配對"""
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
    return jsonify({"success": True})

@app.route('/api/ea-config/<ea_name>/toggle', methods=['POST'])
@login_required
def api_ea_config_toggle(ea_name):
    """Toggle EA status：running ↔ paused"""
    config = json.loads(current_user.ea_config or '{}')
    current_status = config.get(ea_name + '_status', 'running')
    config[ea_name + '_status'] = 'paused' if current_status == 'running' else 'running'
    current_user.ea_config = json.dumps(config)
    db.session.commit()
    return jsonify({"success": True, "status": config[ea_name + '_status']})

# === API: Dashboard ===
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
    return jsonify({
        "status": agent.status,
        "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
        "account": account,
        "positions": positions,
        "agent_id": agent.agent_id,
        "auto_trade_ea_count": auto_count,
        "auto_trade_status": compute_auto_trade_status(current_user)
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
    
    if not mt5.initialize():
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
            'signal': signal
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

@app.route('/api/ea-library/upload', methods=['POST'])
@login_required
def api_ea_upload():
    """用戶上傳自己嘅 EA（只有自己睇到）"""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    if not file.filename.endswith(('.mq5', '.ex5')):
        return jsonify({"error": "Only .mq5 and .ex5 files allowed"}), 400

    # 儲存去用戶專屬目錄
    user_dir = os.path.join(UPLOAD_DIR, current_user.username)
    os.makedirs(user_dir, exist_ok=True)
    filename = secure_filename(file.filename)
    filepath = os.path.join(user_dir, filename)
    file.save(filepath)

    return jsonify({"success": True, "filename": filename, "size": f"{os.path.getsize(filepath)/1024:.1f} KB"})

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

@socketio.on('agent_register')
def handle_register(data):
    agent = Agent.query.filter_by(agent_id=data.get('agent_id')).first()
    if agent:
        join_room(agent.agent_id)
        agent.status = 'connected'
        agent.last_seen = datetime.utcnow()
        db.session.commit()
        emit('registered', {"status":"ok"})
        # 自動推送 EA 配置俾 Agent
        user = agent.user
        if user and user.ea_config and user.ea_config != '{}':
            try:
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"☁️  MT5 Cloud Server :{port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=True, use_reloader=False)