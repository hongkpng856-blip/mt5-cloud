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
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

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
               'GBPAUD','EURNZD','XAUUSD','XAGUSD','US30','SP500',
               'NAS100','DAX40','BTCUSD','ETHUSD']
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

# === API: Dashboard ===
@app.route('/api/dashboard')
@login_required
def api_dashboard():
    agent = Agent.query.filter_by(user_id=current_user.id).first()
    account = json.loads(agent.account_info or '{}')
    positions = json.loads(agent.positions or '[]')
    return jsonify({
        "status": agent.status,
        "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
        "account": account,
        "positions": positions,
        "agent_id": agent.agent_id
    })

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
    for key, info in sorted(per_ea.items()):
        total = info["wins"]+info["losses"]
        wr = round(info["wins"]/total*100,1) if total>0 else 0
        parts = key.split("_",1)
        symbol = parts[1] if len(parts)>1 else ""
        per_ea_list.append({
            "ea": f"Magic#{parts[0]}", "symbol": symbol,
            "trades": info["trades"], "profit": round(info["profit"],2),
            "wins": info["wins"], "losses": info["losses"], "win_rate": wr
        })
        # Group by symbol for frontend matching
        if symbol not in per_ea_by_symbol:
            per_ea_by_symbol[symbol] = {"trades":0,"profit":0,"wins":0,"losses":0}
        per_ea_by_symbol[symbol]["trades"] += info["trades"]
        per_ea_by_symbol[symbol]["profit"] += info["profit"]
        per_ea_by_symbol[symbol]["wins"] += info["wins"]
        per_ea_by_symbol[symbol]["losses"] += info["losses"]
    # Add win_rate to per_ea_by_symbol
    for sym in per_ea_by_symbol:
        info = per_ea_by_symbol[sym]
        total = info["wins"]+info["losses"]
        info["win_rate"] = round(info["wins"]/total*100,1) if total>0 else 0
        info["profit"] = round(info["profit"],2)

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
        "correlation_matrix": corr_matrix,
        "correlation_keys": ea_keys
    })

# === API: EA 庫 ===
EA_LIBRARY_DIR = os.path.join(os.path.dirname(__file__), 'static', 'ea_library')
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'static', 'user_ea')

# 確保目錄存在
os.makedirs(EA_LIBRARY_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.route('/api/ea-library')
def api_ea_library():
    """返回 EA 庫列表（平台提供 + 用戶上傳）"""
    files = []
    # 平台提供嘅 EA
    if os.path.isdir(EA_LIBRARY_DIR):
        for f in sorted(os.listdir(EA_LIBRARY_DIR)):
            if f.endswith('.mq5'):
                path = os.path.join(EA_LIBRARY_DIR, f)
                size = os.path.getsize(path)
                files.append({"name": f, "size": f"{size/1024:.1f} KB", "type": "official", "author": "Platform"})
    # 用戶上傳嘅 EA
    if current_user.is_authenticated:
        user_dir = os.path.join(UPLOAD_DIR, current_user.username)
        if os.path.isdir(user_dir):
            for f in sorted(os.listdir(user_dir)):
                if f.endswith(('.mq5','.ex5')):
                    path = os.path.join(user_dir, f)
                    size = os.path.getsize(path)
                    files.append({"name": f, "size": f"{size/1024:.1f} KB", "type": "user", "author": current_user.username})
    return jsonify({"files": files, "count": len(files)})

@app.route('/api/ea-library/<path:filename>')
def api_ea_download(filename):
    """下載 EA 檔案（先睇用戶目錄，再睇官方目錄）"""
    # 先睇用戶上傳目錄
    if current_user.is_authenticated:
        user_dir = os.path.join(UPLOAD_DIR, current_user.username)
        user_path = os.path.join(user_dir, filename)
        if os.path.isfile(user_path):
            return send_from_directory(user_dir, filename)
    # 再睇官方目錄
    return send_from_directory(EA_LIBRARY_DIR, filename)

@app.route('/api/ea-library/upload', methods=['POST'])
@login_required
def api_ea_upload():
    """用戶上傳自己嘅 EA"""
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
                ea_names = [k for k in config.keys() if not k.endswith('_tf') and not k.endswith('_lot') and k != '_default_lot']
                if ea_names:
                    emit('install_ea_command', {
                        "ea_name": "all",
                        "ea_list": ea_names,
                        "download_url": f"{request.host_url}api/ea-library/"
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
        # 叫 Agent 下載並安裝
        emit('install_ea_command', {
            "ea_name": ea_name,
            "download_url": f"{request.host_url}api/ea-library/{ea_name}"
        }, room=agent.agent_id)
        emit('install_result', {"status": "sent", "ea": ea_name})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"☁️  MT5 Cloud Server :{port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
