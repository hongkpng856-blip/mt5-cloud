# MT5 Cloud — Server 主程式
# 公開網站 + WebSocket Agent 溝通

import os
import json
import time
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# === Init ===
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mt5cloud.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# === Database Models ===
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    agents = db.relationship('Agent', backref='user', lazy=True)

class Agent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(80), default='My MT5')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='offline')  # offline/connected/running
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    account_info = db.Column(db.Text, default='{}')  # JSON
    positions = db.Column(db.Text, default='[]')
    history = db.Column(db.Text, default='[]')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()

# === API Routes ===

@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('dashboard.html')
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json if request.is_json else request.form
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "Username already taken"}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already registered"}), 400

        user = User(username=username, email=email,
                    password=generate_password_hash(password))
        db.session.add(user)

        # Auto-create agent
        agent = Agent(agent_id=str(uuid.uuid4())[:8],
                      name=f"{username}'s MT5", user=user)
        db.session.add(agent)
        db.session.commit()

        login_user(user)
        if request.is_json:
            return jsonify({"success": True, "agent_id": agent.agent_id})
        return redirect(url_for('index'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json if request.is_json else request.form
        user = User.query.filter_by(username=data.get('username')).first()
        if user and check_password_hash(user.password, data.get('password')):
            login_user(user)
            if request.is_json:
                return jsonify({"success": True})
            return redirect(url_for('index'))
        return jsonify({"error": "Invalid credentials"}), 401
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# === API: Agent 配置 ===
@app.route('/api/agent/config')
@login_required
def api_agent_config():
    agent = Agent.query.filter_by(user_id=current_user.id).first()
    return jsonify({
        "agent_id": agent.agent_id,
        "server_url": request.host_url.rstrip('/')
    })

# === API: Dashboard 數據 ===
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

# === WebSocket: Agent 溝通 ===
@socketio.on('connect')
def handle_connect():
    print(f"[WS] Client connected: {request.sid}")

@socketio.on('agent_register')
def handle_agent_register(data):
    """Agent 上線時註冊自己"""
    agent_id = data.get('agent_id')
    agent = Agent.query.filter_by(agent_id=agent_id).first()
    if agent:
        join_room(agent_id)
        agent.status = 'connected'
        agent.last_seen = datetime.utcnow()
        db.session.commit()
        emit('registered', {"status": "ok", "agent_id": agent_id})
        print(f"[WS] Agent registered: {agent_id}")

@socketio.on('agent_sync')
def handle_agent_sync(data):
    """Agent 同步 MT5 數據上 Server"""
    agent_id = data.get('agent_id')
    agent = Agent.query.filter_by(agent_id=agent_id).first()
    if agent:
        agent.account_info = json.dumps(data.get('account', {}))
        agent.positions = json.dumps(data.get('positions', []))
        agent.last_seen = datetime.utcnow()
        agent.status = data.get('status', 'connected')
        db.session.commit()

@socketio.on('agent_trade_result')
def handle_trade_result(data):
    """Agent 回報交易結果"""
    agent_id = data.get('agent_id')
    print(f"[TRADE] {agent_id}: {data.get('result')}")

# === API: 發送交易指令俾 Agent ===
@app.route('/api/trade', methods=['POST'])
@login_required
def api_trade():
    data = request.json
    agent = Agent.query.filter_by(user_id=current_user.id).first()
    if agent.status != 'connected':
        return jsonify({"error": "Agent offline"}), 400

    socketio.emit('trade_command', {
        "action": data.get('action'),
        "symbol": data.get('symbol'),
        "volume": data.get('volume', 0.01),
        "order_type": data.get('order_type'),
        "sl": data.get('sl'),
        "tp": data.get('tp'),
    }, room=agent.agent_id)

    return jsonify({"success": True, "msg": "Command sent to agent"})

# === Frontend ===
if __name__ == '__main__':
    print("=" * 56)
    print("  ☁️  MT5 Cloud Server")
    print("=" * 56)
    print()
    print("  🔗  http://localhost:5000")
    print("  💡  公開版就要 deploy 去 VPS")
    print()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
