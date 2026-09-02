#!/usr/bin/env python3
"""
Tradotcom Agent — 可靠嘅 EA deploy + Auto-Attach

核心改進：
- auto_attach_ea(): 開 chart + Navigator double-click + AutoTrading check
- do_restart_mt5(): 重啟 MT5 令 Navigator refresh
- download_and_install(): inject heartbeat + compile + auto-attach + verify
- execute_deploy(): 真正 attach EA 到 chart（唔係只下單）
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys
import time
import struct
import subprocess
import threading
import json

# === Config ===
import sys as _sys0, os as _os0, traceback as _tb0
# [ALERT] 2026-08-27 FIX：強制 stdout/stderr UTF-8（pyw start時 cp950 唔支持 emoji → UnicodeEncodeError crash）
try:
    _sys0.stdout.reconfigure(encoding='utf-8', errors='replace')
    _sys0.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# [ALERT] 2026-08-27（方案 A 防雙開）：一部機一個 agent
# lock 檔（%LOCALAPPDATA%\TradotcomAgent\agent.lock）記錄local agent_id + PID
# start時：如果有其他 agent 行緊 → 阻止（唔start）→ 彈窗話user
def _check_machine_lock(_my_agent_id):
    """local防雙開：檢查有冇其他 agent 行緊（lock 檔 + PID 驗證）"""
    try:
        _lock_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TradotcomAgent')
        _lock_f = os.path.join(_lock_dir, 'agent.lock')
        if os.path.isfile(_lock_f):
            try:
                with open(_lock_f, 'r', encoding='utf-8') as _lf:
                    _lock_data = json.loads(_lf.read() or '{}')
            except Exception:
                _lock_data = {}
            _other_id = _lock_data.get('agent_id')
            _other_pid = _lock_data.get('pid')
            # 如果 lock 係自己 → 允許（重啟場景）
            if _other_id == _my_agent_id:
                return True
            # 檢查其他 agent 仲行緊（PID exists）
            if _other_pid:
                try:
                    import psutil
                    if psutil.pid_exists(_other_pid):
                        print(f"🚫 local已有 Agent {_other_id} 行緊（PID {_other_pid}）— 阻止start")
                        print(f"   （一部機一個 Agent — 如需更換請先停現有 Agent）")
                        # 寫 log + 彈窗
                        try:
                            with open(_lock_f, 'a', encoding='utf-8') as _lf:
                                pass  # 唔改 lock
                        except Exception:
                            pass
                        return False
                except ImportError:
                    # 冇 psutil → 用 tasklist 檢查
                    try:
                        _out = subprocess.check_output(['tasklist', '/FI', f'PID eq {_other_pid}'], creationflags=0x08000000 if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0).decode('utf-8', 'ignore')
                        if str(_other_pid) in _out and 'python' in _out.lower():
                            print(f"🚫 local已有 Agent {_other_id} 行緊（PID {_other_pid}）— 阻止start")
                            return False
                    except Exception:
                        pass
        # 冇 lock / 其他 agent 死咗 → 寫自己 lock
        try:
            if not os.path.isdir(_lock_dir):
                os.makedirs(_lock_dir, exist_ok=True)
            with open(_lock_f, 'w', encoding='utf-8') as _lf:
                _lf.write(json.dumps({"agent_id": _my_agent_id, "pid": os.getpid(), "ts": time.time(),
                                      # [FP] 2026-08-31 fingerprint：lock 帶 account
                                      "account": os.environ.get('MT5_CLOUD_ACCOUNT', 'unknown')}))
        except Exception:
            pass
        return True
    except Exception:
        return True  # 檢查failed → 放行（保守）
# [ALERT] 2026-08-26（安裝診斷）：agent.py start即寫 log — pythonw 靜默任何 error 都記低
try:
    _alog = os.path.join(os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd(), "agent_launcher.log")
    with open(_alog, "a", encoding="utf-8") as _lf:
        _lf.write(f"[{time.strftime('%H:%M:%S')}] AGENT START python={_sys0.executable}\n")
except Exception:
    pass

def _alog_write(msg):
    """Write to agent_launcher.log (same as pyw - visible to user/diagnosis)"""
    try:
        with open(_alog, "a", encoding="utf-8") as _lf:
            _lf.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


try:
    import MetaTrader5 as mt5
except Exception as _e_mt5:
    try:
        with open(_alog, "a", encoding="utf-8") as _lf:
            _lf.write(f"[{time.strftime('%H:%M:%S')}] [FAIL] MetaTrader5 import failed: {_e_mt5}\n{_tb0.format_exc()}\n")
    except Exception:
        pass
    _sys0.exit(2)

SERVER_URL = os.environ.get('MT5_CLOUD_URL', 'https://tradotcom.com')
AGENT_ID = os.environ.get('MT5_CLOUD_AGENT', 'DEV00001')
AGENT_TOKEN = os.environ.get('MT5_CLOUD_TOKEN', '')
_alog_write(f"init: import OK, MT5={mt5_available if 'mt5_available' in dir() else '?'}")
MT5_DATA = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                         'D0E8209F77C8CF37AD8BF550E51FF075')
MT5_EXPERTS = os.path.join(MT5_DATA, 'MQL5', 'Experts')
MT5_COMMON_FILES = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')

# === Check MT5 availability ===
mt5_available = False
try:
    # [ALERT] 2026-08-27 FIX：MT5_DATA 唔可以 hardcode（第二部機 hash 唔同）
    # → 動態搵 Terminal dir（APPDATA/MetaQuotes/Terminal/<hash> 有 MQL5/Experts 嗰個）
    _found_mt5_dir = None
    try:
        _tbase = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        if os.path.isdir(_tbase):
            for _td in os.listdir(_tbase):
                _cand = os.path.join(_tbase, _td)
                if os.path.isdir(os.path.join(_cand, 'MQL5', 'Experts')):
                    _found_mt5_dir = _cand
                    break
    except Exception:
        pass
    if _found_mt5_dir:
        MT5_DATA = _found_mt5_dir
        MT5_EXPERTS = os.path.join(MT5_DATA, 'MQL5', 'Experts')
    import MetaTrader5 as mt5
    mt5_available = True
except ImportError:
    pass
_alog_write(f"init: mt5_available={mt5_available} mt5_dir={MT5_DATA}")

# === Parse args ===
import argparse
_alog_write("parsing args...")
parser = argparse.ArgumentParser()
parser.add_argument('--server', default=SERVER_URL, help='Server URL')
parser.add_argument('--agent', default=AGENT_ID, help='Agent ID')
parser.add_argument('--token', default=AGENT_TOKEN, help='Agent token')
parser.add_argument('--account', default='', help='Account username (fingerprint — 2026-08-31)')
args, _ = parser.parse_known_args()
SERVER_URL = args.server
AGENT_ID = args.agent
AGENT_TOKEN = args.token
ACCOUNT_NAME = args.account  # [FP] fingerprint：account username
_alog_write(f"args: server={SERVER_URL} agent={AGENT_ID} account={ACCOUNT_NAME or '?'}")
if ACCOUNT_NAME:
    _alog_write(f"[FP] [FINGERPRINT] 呢個係「{ACCOUNT_NAME}」account 嘅 Agent（agent_id={AGENT_ID}）")
    print(f"[FP] [FINGERPRINT] Agent belongs to account: {ACCOUNT_NAME}（{AGENT_ID}）")

# [ALERT] 2026-08-27（方案 A 防雙開）：local已有其他 agent → 阻止start
if not _check_machine_lock(AGENT_ID):
    print(f"🚫 local已有其他 Agent 行緊 — refusedstart（一部機一個 Agent）")
    _alog_write(f"🚫 防雙開阻止：local已有其他 Agent 行緊")
    # 彈窗話user
    try:
        _show_status_popup("🚫 Agent 已exists", f"local已有另一個 Agent 行緊！\n\n一部機只可以一個 Agent。\n請先stop現有 Agent 再試。", False)
    except Exception:
        pass
    _sys0.exit(3)

# === SocketIO client ===
import socketio
# [ALERT] 2026-08-26 FIX：Cloudflare Tunnel 擋「冇 User-Agent」請求（403）
# → SocketIO client 帶瀏覽器 UA（tunnel WAF 唔俾冇 UA 嘅 polling）
# [ALERT] 2026-08-27 FIX：http_session 唔係所有 socketio 版本支援 → try/except fallback
import requests as _req_ua
_sess_ua = _req_ua.Session()
_sess_ua.headers.update({"User-Agent": "Mozilla/5.0 TradotcomAgent/1.0"})
try:
    sio = socketio.Client(logger=False, engineio_logger=False, http_session=_sess_ua)
    _alog_write("socketio.Client OK (with http_session)")
except Exception as _e_sio:
    _alog_write(f"socketio.Client http_session failed: {_e_sio} → fallback 無 session")
    sio = socketio.Client(logger=False, engineio_logger=False)
ea_config_cache = {}
ea_heartbeats = {}
_last_reconnect_attempt = 0  # [ALERT] 2026-09-01：reconnect backoff（30 秒內唔好試多過一次）
_popup_shown = False  # [ALERT] 2026-08-27：success彈窗只彈一次
_deals_cache = None  # [ALERT] 2026-08-27：deals 攞取 cache（60 秒）— 唔好每次 sync 攞全部（卡 → disconnect）
_deals_cache_ts = 0
_last_deals_sent = 0  # [ALERT] 2026-08-27：deals 傳送間隔（60 秒）— 減輕 sync payload
_last_trades_raw_sent = 0  # [ALERT] 2026-09-02：trades_raw 傳送間隔（60 秒）— 減輕 sync payload（VPS balance 斷線 fix）

def _show_status_popup(title, msg, ok):
    """[ALERT] 2026-08-26（安裝驗證）：tkinter 彈窗 — Agent startconnectionsuccess/failed顯示
    success → 綠色「[OK] Agent 已connect」；failed → 紅色「[FAIL] connectionfailed」
    background thread 唔可以整 tkinter — 要喺 main thread（用 threading queue 或者直接喺 main call）
    """
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        root.update()
        if ok:
            messagebox.showinfo("[OK] Agent 已connect", msg)
        else:
            messagebox.showerror("[FAIL] Agent connectionfailed", msg)
        root.destroy()
    except Exception:
        pass


def connect():
    print(f"[OK] Connected to {SERVER_URL}")
    _alog_write(f"Connected to {SERVER_URL}")
    # Register with server → join agent room for deploy commands
    sio.emit('agent_register', {'agent_id': AGENT_ID, 'token': AGENT_TOKEN})
    print(f"   Registering as {AGENT_ID}...")
    _alog_write(f"Registering as {AGENT_ID}...")
    # [ALERT] 2026-08-26（安裝驗證）：startsuccess → 綠色彈窗（等 registered 確認先彈 — 用 thread 延遲）
    # [ALERT] 2026-08-27 FIX：只彈一次（disconnectreconnect唔再彈 — 每次 connect 都彈 = 「成日彈」）
    global _popup_shown
    if _popup_shown:
        return
    _popup_shown = True
    import threading as _th_p
    def _pop_ok():
        time.sleep(1.5)
        if sio.connected:
            _show_status_popup("[OK] Agent 已connect", f"Tradotcom Agent 已successconnect伺服器\n\nAgent ID: {AGENT_ID}\n伺服器: {SERVER_URL}", True)
    _th_p.Thread(target=_pop_ok, daemon=True).start()

def disconnect():
    print("[FAIL] Disconnected")

def on_registered(data):
    print(f"ID Registered: {data}")
    _alog_write(f"Registered: {str(data)[:100]}")
    # [ALERT] 2026-08-26（安裝驗證）：註冊failed（token 錯等）→ 紅色彈窗
    if isinstance(data, dict) and data.get('status') == 'error':
        _show_status_popup("[FAIL] Agent connectionfailed", f"伺服器refused註冊：{data.get('msg', 'token 可能唔啱')}\n\n請檢查 Agent ID 同 Token 是否正確", False)
    # Server auto-pushes install_ea_command on register

sio.on('connect', connect)
sio.on('disconnect', disconnect)
sio.on('registered', on_registered)


# ================================================================
#  MT5 Bridge — 重啟 + wait
# ================================================================

def find_mt5_pid():
    """搵 MT5 terminal64.exe PID"""
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None

def wait_for_mt5(timeout=90):
    """等 MT5 startdone"""
    start = time.time()
    while time.time() - start < timeout:
        pid = find_mt5_pid()
        if pid:
            time.sleep(3)
            # Verify MT5 is responsive by checking log
            log_path = os.path.join(MT5_DATA, 'Logs', time.strftime('%Y%m%d') + '.log')
            if os.path.exists(log_path):
                mtime = os.path.getmtime(log_path)
                if time.time() - mtime < 30:
                    return pid
        time.sleep(2)
    return None

def do_restart_mt5():
    """重啟 MT5 — 令 Navigator tree refresh"""
    import subprocess
    
    # Kill existing MT5
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'terminal64.exe'],
                        capture_output=True, timeout=10)
    except:
        pass
    
    time.sleep(3)
    
    # MT5 auto-restarts after kill (Windows service behavior)
    # Wait for ready
    pid = wait_for_mt5(timeout=90)
    if pid:
        # Extra wait for Navigator to fully load + refresh
        time.sleep(10)
        print(f"[OK] MT5 restarted, PID={pid}")
        return pid
    else:
        print("[FAIL] MT5 failed to restart")
        # Try launching manually
        mt5_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
        if os.path.exists(mt5_path):
            subprocess.Popen([mt5_path])
            pid = wait_for_mt5(timeout=60)
            if pid:
                time.sleep(10)
                print(f"[OK] MT5 launched manually, PID={pid}")
                return pid
        return None


# ================================================================
#  Auto-Attach EA — 可靠嘅 GUI 自動化
# ================================================================

def auto_attach_ea(ea_name, symbol='EURUSD', timeframe='H1', inputs=None, do_restart=False):
    """完整 auto-attach 流程：
    1. 生成 .tpl 模板
    2. (可選) 重啟 MT5
    3. 開新 chart + Navigator double-click
    4. 確保 AutoTrading ON
    5. 驗證 heartbeat
    
    Returns: True if EA is alive, False otherwise
    """
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    
    print(f"\n{'='*50}")
    print(f"  [GO] Auto-Attach: {ea_name} → {symbol} {timeframe}")
    print(f"{'='*50}")
    
    # Step 1: Generate .tpl template
    tpl_path = generate_template(ea_name, symbol, timeframe, inputs)
    print(f"[CLIP] Template: {tpl_path} ({os.path.getsize(tpl_path)} bytes)")
    
    # Step 2: Get or restart MT5
    if do_restart:
        mt5_pid = do_restart_mt5()
        if not mt5_pid:
            return False
    else:
        mt5_pid = find_mt5_pid()
        if not mt5_pid:
            print("[FAIL] MT5 not running")
            mt5_pid = do_restart_mt5()
            if not mt5_pid:
                return False
    
    # Step 3: Attach via Navigator subprocess
    # auto_attach.py runs as a separate process with full desktop access
    auto_attach_path = os.path.join(os.path.dirname(__file__), 'auto_attach.py')
    cmd = ['python', auto_attach_path, '--ea', ea_name, '--symbol', symbol, '--tf', 'H1']
    print(f"[GO] Running auto_attach subprocess: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, timeout=300, capture_output=True, text=True, cwd=os.path.dirname(auto_attach_path), creationflags=subprocess.CREATE_NEW_CONSOLE)
        print(f"   Exit code: {result.returncode}")
        for line in result.stdout.split('\n'):
            if any(kw in line for kw in ['[DONE]', '[OK]', '[FAIL]', '[GREEN]', '[RED]', '[WARN]', '[HB]', '[CLIP]']):
                print(f"   {line}")
        if result.returncode != 0:
            if result.stderr:
                print(f"   Stderr: {result.stderr[-500:]}")
    except subprocess.TimeoutExpired:
        print(f"[WARN] auto_attach.py timed out")
        attached = False
    except Exception as e:
        print(f"[WARN] auto_attach error: {e}")
        attached = False
    else:
        attached = result.returncode == 0
    
    if not attached:
        print("[WARN] Navigator attach failed (no MT5 restart — keeping existing charts alive)")
    
    if not attached:
        print("[FAIL] Failed to attach EA")
        return False
    
    # Step 4: Verify heartbeat
    hb_path = os.path.join(MT5_COMMON_FILES, f'hb_{ea_name}.txt')
    print(f"[WAIT] Waiting for heartbeat...")
    
    start = time.time()
    old_mtime = os.path.getmtime(hb_path) if os.path.exists(hb_path) else 0
    
    for _ in range(24):  # 120 seconds
        time.sleep(5)
        if os.path.exists(hb_path):
            new_mtime = os.path.getmtime(hb_path)
            if new_mtime != old_mtime and time.time() - new_mtime < 300:
                with open(hb_path, 'rb') as f:
                    raw = f.read()
                content = raw.decode('utf-16-le', errors='replace').strip().lstrip('\ufeff')
                age = time.time() - new_mtime
                print(f"[HB] {ea_name}: {content} ({round(age)}s ago) → [GREEN] ALIVE")
                
                # Verify EA log
                mql5_log = os.path.join(MT5_DATA, 'MQL5', 'Logs', time.strftime('%Y%m%d') + '.log')
                if os.path.exists(mql5_log):
                    with open(mql5_log, 'r', encoding='utf-16-le', errors='replace') as f:
                        lines = f.readlines()
                    for line in reversed(lines[-20:]):
                        if ea_name in line and ('start' in line or 'start' in line.lower()):
                            print(f"[CLIP] EA log: {line.strip()}")
                            break
                
                return True
    
    print(f"[FAIL] No heartbeat after {round(time.time()-start)}s")
    return False


def generate_template(ea_name, symbol, timeframe, inputs=None):
    """生成 MT5 .tpl 模板檔（UTF-16 LE + BOM）"""
    TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
    os.makedirs(TPL_DIR, exist_ok=True)
    
    tf_map = {'M1':1,'M5':5,'M15':15,'M30':30,'H1':16385,'H4':16388,'D1':16389,'W1':16390,'MN1':16391}
    tf_code = tf_map.get(timeframe, 16385)
    
    # Build inputs section
    inputs_section = ""
    if inputs:
        for key, val in inputs.items():
            inputs_section += f"{key}={val}\r\n"
    
    lot = inputs.get('LotSize', '1.00') if inputs else '1.00'
    magic = inputs.get('MagicNumber', '240701') if inputs else '240701'
    inputs_section += f"LotSize={lot}\r\n"
    inputs_section += f"MagicNumber={magic}\r\n"
    
    tpl_content = (
        f"\ufeff"  # BOM will be added separately
        f"<chart>\r\n"
        f"symbol={symbol}\r\n"
        f"period={tf_code}\r\n"
        f"left=100\r\n"
        f"top=50\r\n"
        f"right=900\r\n"
        f"bottom=500\r\n"
        f"\r\n"
        f"<expert>\r\n"
        f"name={ea_name}\r\n"
        f"flags=7\r\n"
        f"enabled=1\r\n"
        f"\r\n"
        f"<inputs>\r\n"
        f"{inputs_section}"
        f"</inputs>\r\n"
        f"\r\n"
        f"</expert>\r\n"
        f"\r\n"
        f"<window>\r\n"
        f"height=100\r\n"
        f"\r\n"
        f"<indicator>\r\n"
        f"name=Main\r\n"
        f"path=\r\n"
        f"apply=1\r\n"
        f"show_data=1\r\n"
        f"scale_inherit=0\r\n"
        f"scale_line=0\r\n"
        f"scale_line_percent=50\r\n"
        f"scale_line_value=0.000000\r\n"
        f"scale_fix_min=0\r\n"
        f"scale_fix_min_val=0.000000\r\n"
        f"scale_fix_max=0\r\n"
        f"scale_fix_max_val=0.000000\r\n"
        f"</indicator>\r\n"
        f"\r\n"
        f"</window>\r\n"
        f"\r\n"
        f"</chart>\r\n"
    )
    
    tpl_name = f"{ea_name}_{symbol}_{timeframe}"
    tpl_path = os.path.join(TPL_DIR, f"{tpl_name}.tpl")
    
    # Write as UTF-16 LE with BOM
    with open(tpl_path, 'wb') as f:
        f.write(b'\xff\xfe')  # UTF-16 LE BOM
        # Remove the \ufeff from content since we add BOM separately
        content_no_bom = tpl_content.lstrip('\ufeff')
        f.write(content_no_bom.encode('utf-16-le'))
    
    return tpl_path


def attach_ea_navigator(ea_name, symbol, mt5_pid, max_retries=3):
    """用 AHK + pyautogui double-click attach EA
    
    關鍵發現：
    - MT5 Navigator TreeView 的 select() + Enter 不等同 double-click
    - Enter 只 expand/collapse 節點，不會 attach EA 到 chart
    - 開新 chart 後 Navigator panel 會自動收埋
    - 必須先開 chart，再開 Navigator，再 double-click
    
    流程：
    1. Python: 開 chart + 開 Navigator + select EA + ensure_visible
    2. AHK attach_ea.ahk: double-click scan TreeView 搵 EA Properties dialog
    3. Python fallback: pyautogui double-click scan
    """
    import pyautogui
    import ctypes
    user32 = ctypes.windll.user32
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    
    ahk_script = os.path.join(os.path.dirname(__file__), 'attach_ea.ahk')
    ahk_exe = r'C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe'
    ahk_nav = os.path.join(os.path.dirname(__file__), 'nav_on.ahk')
    
    import ctypes as _ctypes
    user32 = _ctypes.windll.user32
    
    for attempt in range(max_retries):
        try:
            app = Application(backend='win32').connect(process=mt5_pid)
            win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
            try:
                win.set_focus()
            except:
                pass  # No active desktop (background process)
            time.sleep(0.5)
        except Exception as e:
            print(f"[WARN] win32 connect failed: {e} (attempt {attempt+1}/{max_retries})")
            time.sleep(5)
            continue
        
        # Step 1: Open chart only if none exists
        mdi = None
        for d in win.descendants():
            if d.element_info.class_name == 'MDIClient':
                mdi = d
                break
        has_charts = mdi and len(mdi.children()) > 0
        
        if not has_charts:
            print("[CLIP] No chart open, opening new one...")
            send_keys('^n')
            time.sleep(1)
            send_keys('{ENTER}')
            time.sleep(3)
        else:
            print(f"[CLIP] Chart already open, skipping Ctrl+N...")
        
        # Step 2: Open Navigator panel DIRECTLY via ShowWindow
        # Much more reliable than menu clicks or keyboard shortcuts
        nav_panel = None
        for d in win.descendants():
            c = d.element_info.class_name
            if 'Afx:ControlBar' in c:
                r = d.rectangle()
                # Navigator panel has the SysTreeView32 child
                tv_child = None
                for child in d.descendants():
                    if child.element_info.class_name == 'SysTreeView32':
                        tv_child = child
                        break
                if tv_child:
                    nav_panel = d
                    break
        
        if nav_panel:
            hwnd = nav_panel.element_info.handle
            user32.ShowWindow(hwnd, 5)  # SW_SHOW
            time.sleep(1)
            print(f"[CLIP] Navigator panel shown via ShowWindow")
        else:
            # Fallback: WM_COMMAND 32808 (Navigator toggle command ID)
            print(f"[CLIP] Navigator panel not found, trying WM_COMMAND...")
            result = user32.SendMessageW(win.element_info.handle, 0x0111, 32808, 0)
            time.sleep(1.5)
        
        # Step 3: Find SysTreeView32 and verify it's visible
        tree_view = None
        for d in win.descendants():
            if d.element_info.class_name == 'SysTreeView32':
                tree_view = d
                break
        
        if not tree_view:
            print(f"[WARN] No TreeView found (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
        
        if not tree_view.is_visible():
            print(f"[WARN] TreeView not visible after ShowWindow (attempt {attempt+1}/{max_retries})")
            # Try WM_COMMAND as fallback
            user32.SendMessageW(win.element_info.handle, 0x0111, 32808, 0)
            time.sleep(1.5)
            
            for d in win.descendants():
                if d.element_info.class_name == 'SysTreeView32':
                    tree_view = d
                    break
            if not tree_view or not tree_view.is_visible():
                print(f"[WARN] TreeView still not visible")
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
        
        tv_rect = tree_view.rectangle()
        print(f"[CLIP] TreeView visible={tree_view.is_visible()} rect=({tv_rect.left},{tv_rect.top})-({tv_rect.right},{tv_rect.bottom})")
        
        # Step 4: Navigate tree → Expand EA交易 → Select + ensure_visible
        try:
            root = tree_view.roots()[0]
            
            ea_trading_node = None
            # MT5 Navigator language varies: 'EA交易', 'المستشارون المختصون', 'Expert Advisors', etc.
            # Use position (3rd child = index 2) as primary, text match as fallback
            children = root.children()
            if len(children) > 2:
                ea_trading_node = children[2]  # Always 3rd child = Expert Advisors
                print(f"[CLIP] EA node by position: '{ea_trading_node.text()}'")
            if not ea_trading_node:
                # Fallback: text match for common languages
                for child in children:
                    t = child.text()
                    if any(kw in t for kw in ['EA交易', 'Expert Advisors', 'المستشارون المختصون', 'Experts', 'EA']):
                        ea_trading_node = child
                        break
            
            if not ea_trading_node:
                print(f"[WARN] EA交易 node not found (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
            
            ea_trading_node.expand()
            time.sleep(2)
            
            ea_node = None
            for ea in ea_trading_node.children():
                if ea.text() == ea_name:
                    ea_node = ea
                    break
            
            if not ea_node:
                print(f"[WARN] {ea_name} not found under EA交易 (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
            
            print(f"[TARGET] Found {ea_name}, attaching via pyautogui double-click...")
            ea_node.select()
            time.sleep(0.3)
            ea_node.ensure_visible()
            time.sleep(0.5)
            
        except Exception as e:
            print(f"[WARN] Tree navigation error: {e} (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
        
        # Step 5: Double-click the selected EA
        # Use SendMessage (not SendInput) — works without window focus!
        found_dialog = False
        
        print(f"[MOUSE] SendMessage WM_LBUTTONDBLCLK for {ea_name}...")
        
        # Get TreeView client area for coordinate calculation
        tv_hwnd = tree_view.element_info.handle
        tv_rect = tree_view.rectangle()
        
        # Client coordinates relative to TreeView
        # After select() + ensure_visible(), EA is at the first visible row
        # First row is at client y ≈ 9 (center of ~18px row)
        client_x = 20  # Left margin with some indent
        client_y = 9   # Center of first row
        
        # WM_LBUTTONDBLCLK = 0x0203
        # wParam = MK_LBUTTON = 0x0001
        # lParam = MAKELPARAM(client_x, client_y)
        lparam = (client_y << 16) | client_x
        
        result = user32.SendMessageW(tv_hwnd, 0x0203, 0x0001, lparam)
        time.sleep(2)
        
        # Also send WM_LBUTTONUP after
        # WM_LBUTTONUP = 0x0202
        user32.SendMessageW(tv_hwnd, 0x0202, 0x0000, lparam)
        time.sleep(0.5)
        
        # Check for EA Properties dialog
        def find_ea_dialog(target_name):
            results = []
            pid_buf = ctypes.c_ulong()
            def cb(hwnd, _):
                # hwnd is c_size_t from callback, need to cast for API
                user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
                if pid_buf.value == mt5_pid:
                    cls = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                    if cls.value == '#32770':
                        title = ctypes.create_unicode_buffer(256)
                        user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                        if target_name in title.value:
                            results.append(title.value)
                return True
            CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
            user32.EnumWindows(CB(cb), 0)
            return results
        
        dialogs = find_ea_dialog(ea_name)
        if dialogs:
            print(f"[DONE] {ea_name} Properties dialog found!")
            found_dialog = True
            
            # Step 6: Confirm dialog (Enter)
            send_keys('{ENTER}')
            time.sleep(2)
            
            # Step 7: Ensure AutoTrading ON
            log_path = os.path.join(MT5_DATA, 'Logs', time.strftime('%Y%m%d') + '.log')
            auto_trading_on = False
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-16-le', errors='replace') as f:
                    log_lines = f.readlines()
                for line in reversed(log_lines[-20:]):
                    if 'automated trading' in line.lower():
                        if 'enabled' in line.lower():
                            auto_trading_on = True
                        break
            
            if not auto_trading_on:
                send_keys('^e')
                time.sleep(2)
                print("[RED] AutoTrading OFF → toggled ON")
            else:
                print("[GREEN] AutoTrading is ON")
        else:
            # Fallback: scan more positions if first click missed
            print(f"[WARN] First click didn't find {ea_name} dialog, scanning...")
            # Close any wrong dialog
            send_keys('{ESC}')
            time.sleep(0.3)
            
            for y_client in [27, 45, 63, 81]:  # Try rows 2-5
                client_y = y_client
                lparam = (client_y << 16) | client_x
                user32.SendMessageW(tv_hwnd, 0x0203, 0x0001, lparam)
                time.sleep(1.5)
                user32.SendMessageW(tv_hwnd, 0x0202, 0x0000, lparam)
                time.sleep(0.5)
                dialogs = find_ea_dialog(ea_name)
                if dialogs:
                    print(f"[DONE] {ea_name} dialog found at client_y={client_y}!")
                    found_dialog = True
                    send_keys('{ENTER}')
                    time.sleep(2)
                    send_keys('^e')
                    time.sleep(1)
                    break
                send_keys('{ESC}')
                time.sleep(0.3)
        
        if not found_dialog:
            print(f"[WARN] {ea_name} dialog not found after full scan (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
    
    print(f"[FAIL] {ea_name} attach failed after {max_retries} attempts")
    return False


# ================================================================
#  Install EA handler
# ================================================================

@sio.on('install_ea_command')
def on_install_ea(data):
    ea_name = data.get('ea_name', '')
    ea_list = data.get('ea_list', [])
    url = data.get('download_url', '')
    ea_config = data.get('ea_config', {})
    if ea_config:
        global ea_config_cache
        ea_config_cache.clear()
        ea_config_cache.update(ea_config)

    if ea_name == 'all' and ea_list:
        print(f"[IN] Bulk install: {len(ea_list)} EAs (background)")
        sys.stdout.flush()
        import threading
        def _do_install():
            for name in ea_list:
                download_and_install(name + '.mq5', url + name + '.mq5', ea_config)
        t = threading.Thread(target=_do_install, daemon=True)
        t.start()
        return

    print(f"[IN] Installing EA: {ea_name}")
    sys.stdout.flush()
    download_and_install(ea_name + '.mq5', url + ea_name + '.mq5', ea_config)


# ================================================================
#  Download + Install + Compile + Auto-Attach
# ================================================================

def download_and_install(ea_name, url, ea_config=None):
    """完整安裝流程：download → heartbeat inject → compile → preset → auto-attach"""
    print(f"[IN] Installing EA: {ea_name}")
    print(f"   Downloading from: {url}")
    try:
        import requests
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            appdata = os.environ.get('APPDATA', '')
            terminal_dir = os.path.join(appdata, 'MetaQuotes', 'Terminal')
            experts_dir = None
            if os.path.isdir(terminal_dir):
                for folder in sorted(os.listdir(terminal_dir)):
                    ep = os.path.join(terminal_dir, folder, 'MQL5', 'Experts')
                    if os.path.isdir(ep):
                        experts_dir = ep
                        break
                if not experts_dir:
                    common = os.path.join(terminal_dir, 'Common', 'MQL5', 'Experts')
                    if os.path.isdir(common):
                        experts_dir = common

            if experts_dir:
                base_name = ea_name.replace('.mq5', '')
                mq5_path = os.path.join(experts_dir, ea_name)
                
                # Write source with normalized line endings
                content = resp.text.replace('\r\n', '\n').replace('\n', '\r\n')
                
                # === Inject heartbeat code ===
                base = base_name
                hb_var = f"HB_{base}"
                hb_file = f"hb_{base}.txt"
                
                oninit_inject = (
                    f"   GlobalVariableSet(\"{hb_var}\",TimeCurrent());\r\n"
                    f"   int hb_fh=FileOpen(\"{hb_file}\",FILE_WRITE|FILE_TXT);\r\n"
                    f"   if(hb_fh!=INVALID_HANDLE){{FileWrite(hb_fh,TimeCurrent());FileClose(hb_fh);}}\r\n"
                )
                ontick_inject = (
                    f"   GlobalVariableSet(\"{hb_var}\",TimeCurrent());\r\n"
                    f"   int hb_fh=FileOpen(\"{hb_file}\",FILE_WRITE|FILE_TXT);\r\n"
                    f"   if(hb_fh!=INVALID_HANDLE){{FileWrite(hb_fh,TimeCurrent());FileClose(hb_fh);}}\r\n"
                )
                
                # Find OnInit { and inject after it
                import re
                m = re.search(r'(int\s+OnInit\s*\(\s*\)\s*\{)', content)
                _injected_any = False
                if m and hb_var not in content:
                    idx = m.end()
                    content = content[:idx] + '\r\n' + oninit_inject + content[idx:]
                    print(f"   [INJECT] Heartbeat injected (OnInit)")
                    _injected_any = True
                
                # Find OnTick { and inject after it
                m2 = re.search(r'(void\s+OnTick\s*\(\s*\)\s*\{)', content)
                if m2 and f'GlobalVariableSet("{hb_var}"' not in content.split('OnTick')[1] if 'OnTick' in content else '':
                    # Only inject if not already in OnTick section
                    if content.count(f'GlobalVariableSet("{hb_var}"') < 2:
                        idx2 = m2.end()
                        content = content[:idx2] + '\r\n' + ontick_inject + content[idx2:]
                        print(f"   [INJECT] Heartbeat injected (OnTick)")
                        _injected_any = True
                
                # [ALERT] 2026-09-01 FIX（用戶實測：冇操作都開 MT5 + refresh 導航頁）：
                # before: 心跳已注入都照寫 .mq5（touch mtime）→ watcher 偵測變化 → refresh Navigator + 開 MT5
                # now: 心跳已注入（hb_var 存在）→ 唔寫 .mq5（唔 touch — 唔觸發 watcher）
                if hb_var in content and not _injected_any:
                    print(f"   [SKIP] 心跳已注入過（{hb_var}）— 唔 touch .mq5（避免 watcher 誤觸發 refresh）")
                else:
                    with open(mq5_path, 'w', encoding='utf-8', newline='\r\n') as f:
                        f.write(content)
                    print(f"   [SAVE] Saved: {mq5_path}")
                
                # === Compile (skip if .ex5 already exists) ===
                # [ALERT] 2026-08-28 FIX：before「.ex5 mtime > .mq5 先 skip」— 但心跳注入令 .mq5 永遠新過 .ex5 → 每次 Auto-sent 都 compile → MetaEditor 周不時彈出
                # → 改為「.ex5 exists就 skip」（心跳注入只改 .mq5 內容 — .ex5 功能一樣 — 唔需要重新 compile）
                ex5_path = os.path.join(experts_dir, base_name + '.ex5')
                if os.path.exists(ex5_path):
                    print(f"   [FFWD] Skip compile: {base_name}.ex5 already exists")
                else:
                    import subprocess
                    metaeditor = r"C:\Program Files\MetaTrader 5\metaeditor64.exe"
                    log_file = os.path.join(experts_dir, f'{base_name}_compile.log')
                    
                    try:
                        result = subprocess.run([
                            metaeditor, '/compile', mq5_path,
                            f'/log:{log_file}'
                        ], capture_output=True, timeout=120)
                        # [ALERT] 2026-08-28 FIX：compile 完immediately關 MetaEditor（CLI /compile 都用 metaeditor64.exe — 留低會監察 Experts → 彈「外部修改」dialog）
                        try:
                            subprocess.run('taskkill /f /im metaeditor64.exe', shell=True, capture_output=True, timeout=10)
                        except Exception:
                            pass
                    except subprocess.TimeoutExpired:
                        print(f"   [WARN] Compile timeout (120s), but .ex5 may exist")
                        if os.path.exists(ex5_path):
                            print(f"   [OK] .ex5 found despite timeout: {os.path.getsize(ex5_path)} bytes")
                        # timeout 都關 MetaEditor
                        try:
                            subprocess.run('taskkill /f /im metaeditor64.exe', shell=True, capture_output=True, timeout=10)
                        except Exception:
                            pass
                
                # Check .ex5
                ex5_path = os.path.join(experts_dir, base_name + '.ex5')
                if os.path.exists(ex5_path):
                    print(f"   [OK] Compiled: {base_name}.ex5 ({os.path.getsize(ex5_path)} bytes)")
                else:
                    print(f"   [FAIL] Compile failed (no .ex5)")
                    # Try reading compile log for errors
                    if os.path.exists(log_file):
                        try:
                            with open(log_file, 'r', encoding='utf-16-le', errors='replace') as f:
                                log_content = f.read()
                            if 'error' in log_content.lower():
                                for line in log_content.split('\n'):
                                    if 'error' in line.lower():
                                        print(f"      {line.strip()}")
                        except:
                            pass
                
                # === Create preset ===
                if ea_config and base_name in ea_config:
                    cfg = ea_config[base_name]
                    # Handle old format (cfg=str) and new format (cfg=dict)
                    if isinstance(cfg, str):
                        cfg = {'symbol': cfg, 'timeframe': ea_config.get(base_name+'_tf', 'H1'),
                               'lot': ea_config.get(base_name+'_lot', '1.00'),
                               'magic': ea_config.get(base_name+'_magic', '240701')}
                    sym = cfg.get('symbol', 'EURUSD')
                    tf = cfg.get('timeframe', 'H1')
                    lot = cfg.get('lot', '1.00')
                    magic = str(cfg.get('magic', '240701'))
                    
                    presets_dir = os.path.join(experts_dir, 'Presets')
                    os.makedirs(presets_dir, exist_ok=True)
                    
                    set_content = f'; {base_name} preset\r\n'
                    set_content += f'MagicNumber={magic}\r\n'
                    set_content += f'LotSize={lot}\r\n'
                    set_path = os.path.join(presets_dir, base_name + '.set')
                    with open(set_path, 'w') as f:
                        f.write(set_content)
                    print(f"   [CLIP] Preset: {set_path}")
                    
                    # === Skip deploy command for auto-sync (only [GO] Deploy button writes it) ===
                    # Auto-sync just compiles & registers EA. User [GO] Deploy will trigger attach.
                    print(f"   [OK] {base_name} compiled & registered. User [GO] Deploy to attach.")

                sio.emit('install_result', {"status": "ok", "ea": ea_name})
            else:
                print("[FAIL] Cannot find MT5 Experts folder")
                sio.emit('install_result', {"status": "error", "ea": ea_name, "msg": "MT5 not found"})
        else:
            print(f"[FAIL] Download failed: {resp.status_code}")
            sio.emit('install_result', {"status": "error", "ea": ea_name, "msg": f"HTTP {resp.status_code}"})
    except Exception as e:
        print(f"[FAIL] Install error: {e}")
        sio.emit('install_result', {"status": "error", "ea": ea_name, "msg": str(e)})


# ================================================================
#  Deploy via Socket.IO
# ================================================================

@sio.on('deploy_ea')
def on_deploy_ea(data):
    print(f"[GO] [WS] Deploy: {data}")
    sys.stdout.flush()
    try:
        _alog_write(f"[WS] 收到 deploy_ea: {data.get('ea_name')} -> {data.get('symbol')}")
    except Exception:
        pass
    # [ALERT] 2026-08-27 FIX：emit 收到 = 已經執行 — immediately清 server deploy_queue（唔好俾 poll 又讀到 → 重複執行）
    try:
        import urllib.request as _ur_clr
        _poll_url_clr = 'http://localhost:5001' if 'localhost' not in SERVER_URL else SERVER_URL
        _req_clr = _ur_clr.Request(f"{_poll_url_clr}/api/agent-poll-deploy?agent_id={AGENT_ID}")
        with _ur_clr.urlopen(_req_clr, timeout=5) as _r_clr:
            _r_clr.read()
    except Exception:
        pass
    try:
        execute_deploy(data)
        _alog_write(f"[WS] execute_deploy done（冇 crash）")
    except Exception as _e_dep:
        _alog_write(f"[WS] execute_deploy crash: {str(_e_dep)[:150]}")
        import traceback
        traceback.print_exc()


# [ALERT] 2026-08-28（user要求：網站可以removelocal agent）：收 server 'shutdown' 指令 → 清理 + 退出
_shutdown_done = False  # [ALERT] 防重複執行（emit + poll 雙重觸發 → 第二次 crash → 通知 server 冇行）


@sio.on('shutdown')
def on_shutdown(data):
    """Server 要求removelocal agent：清 lock/config/捷徑 → 通知 server → 退出"""
    global _shutdown_done
    if _shutdown_done:
        print("[NEXT] [WS] shutdown 已執行過 — skip（防重複）")
        return
    _shutdown_done = True
    print("🚫 [WS] 收到 shutdown 指令 — removelocal agent...")
    sys.stdout.flush()
    try:
        _alog_write("[WS] 收到 shutdown（網站remove agent）")
    except Exception:
        pass
    try:
        _agent_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TradotcomAgent')
        # 刪 lock
        _lock_f = os.path.join(_agent_dir, 'agent.lock')
        if os.path.isfile(_lock_f):
            os.remove(_lock_f)
            print("   [OK] agent.lock 已刪")
        # 刪 config
        _cfg_f = os.path.join(_agent_dir, 'agent_config.json')
        if os.path.isfile(_cfg_f):
            os.remove(_cfg_f)
            print("   [OK] agent_config.json 已刪")
        # 刪桌面捷徑
        try:
            import glob as _gl_sh
            for _lnk in _gl_sh.glob(os.path.join(os.path.expanduser('~'), 'Desktop', '*Tradotcom*Agent*.lnk')):
                os.remove(_lnk)
                print(f"   [OK] 捷徑已刪: {os.path.basename(_lnk)}")
        except Exception:
            pass
        # [ALERT] 2026-08-28（user要求：remove = 全部清晒）：停平台服務（watcher/alert_worker/auto_trade_detector）
        # [WARN] 順序重要：先停服務（唔需要 agent.py）→ 最後先刪資料夾（rmtree 刪自己 — after code 唔可以再行）
        try:
            import subprocess as _sp_sh
            for _pat_sh in ('deploy_watcher', 'alert_worker', 'auto_trade_detector'):
                # 用 PowerShell 揾 command line 含 pattern 嘅 python process 再 kill（taskkill WINDOWTITLE 唔 work — 冇窗口）
                _kill_sh = (f"Get-CimInstance Win32_Process | Where-Object {{$_.Name -match 'python' -and "
                            f"$_.CommandLine -match '{_pat_sh}'}} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}")
                _sp_sh.run(['powershell', '-NoProfile', '-Command', _kill_sh], capture_output=True, timeout=15)
            print("   [OK] 平台服務已停（watcher/alert_worker/auto_trade_detector）")
        except Exception as _e_sp:
            print(f"   [WARN] 停平台服務failed: {_e_sp}")
        # [ALERT] 2026-08-28（user要求：remove = 全部清晒）：清測試殘留（pystray/Test tray + 其他 Tradotcom 相關 python）
        # [WARN] 唔可以 match 'TradotcomAgent' path（自己都喺嗰度 → kill 自己 → after嘅嘢冇行）
        # → 只清 pystray tray（唔係自己）— 其他 Tradotcom 相關由「刪資料夾」處理
        try:
            import subprocess as _sp_tr
            _kill_tr1 = ("Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python' -and "
                         "$_.CommandLine -match 'pystray' -and $_.ProcessId -ne $PID} | "
                         "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
            _sp_tr.run(['powershell', '-NoProfile', '-Command', _kill_tr1], capture_output=True, timeout=15)
            print("   [OK] 測試殘留已清（pystray tray）")
        except Exception as _e_tr:
            print(f"   [WARN] 清測試殘留failed: {_e_tr}")
        # [ALERT] 2026-08-28（user要求：remove = 全部清晒）：刪整個 TradotcomAgent 安裝資料夾（最後先做 — 刪自己）
        # [ALERT] 2026-08-31 FIX（#154 剷除漏清 — 用戶實測：paint_uimap/舊 Setup/ip-records 殘留）：
        # 逐個刪之前加「指定舊殘留清理」（paint_uimap*/Tradotcom-Agent-Setup*/ip-records*/*.log）
        # （呢啲檔 mtime 舊（5 月）— 之前剷除流程未清到 — 一直殘留 — 用戶要求剷除 = 全部清晒）
        try:
            import glob as _gl_old
            _old_patterns = [
                'paint_uimap*.json',
                'Tradotcom-Agent-Setup*.pyw',
                'ip-records*.json',
                '*.log',
            ]
            for _pat_old in _old_patterns:
                for _f_old in _gl_old.glob(os.path.join(_agent_dir, _pat_old)):
                    try:
                        if os.path.basename(_f_old) != os.path.basename(__file__):
                            os.remove(_f_old)
                            print(f"   [OK] 舊殘留已刪: {os.path.basename(_f_old)}")
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            import shutil as _sh_sh
            if os.path.isdir(_agent_dir):
                # [WARN] rmtree 刪唔到自己（agent.py 仲 load 緊 — 佔用）→ 逐個刪（跳過自己）+ 最後再 rmtree
                try:
                    for _f_del in os.listdir(_agent_dir):
                        _p_del = os.path.join(_agent_dir, _f_del)
                        try:
                            if os.path.basename(_p_del) != os.path.basename(__file__):
                                if os.path.isdir(_p_del):
                                    _sh_sh.rmtree(_p_del, ignore_errors=True)
                                else:
                                    os.remove(_p_del)
                        except Exception:
                            pass
                    print(f"   [OK] 安裝資料夾內容已刪（除咗自己 agent.py）: {_agent_dir}")
                except Exception as _e_del2:
                    print(f"   [WARN] 逐個刪failed: {_e_del2}")
        except Exception as _e_dir:
            print(f"   [WARN] 刪安裝資料夾failed: {_e_dir}")
        # 通知 server done（清理完先話success）
        try:
            import urllib.request as _ur_sh
            _url_sh = 'http://localhost:5001' if 'localhost' not in SERVER_URL else SERVER_URL
            _req_sh = _ur_sh.Request(f"{_url_sh}/api/agent/remove-complete?agent_id={AGENT_ID}", method='POST')
            _ur_sh.urlopen(_req_sh, timeout=5)
            print("   [OK] 已通知 server removedone")
        except Exception as _e_sh2:
            print(f"   [WARN] 通知 server failed: {_e_sh2}")
    except Exception as _e_sh:
        print(f"   [WARN] 清理failed: {_e_sh}")
    # 退出 agent
    try:
        import threading as _th_sh
        _th_sh.Timer(1.0, os._exit, args=(0,)).start()
    except Exception:
        os._exit(0)


# ================================================================
#  EA 自動交易策略
# ================================================================

def get_ma(symbol, tf, period, method=0):
    """獲取移動平均線數值"""
    import MetaTrader5 as mt5
    if not mt5.symbol_select(symbol, True):
        return None
    S_TF = {1:1, 5:5, 15:15, 30:30, 60:60, 240:240, 1440:1440, 10080:10080, 43200:43200}
    mul = S_TF.get(tf, 60)
    need_bars = (period + 2) * mul
    rates = mt5.copy_rates_from_pos(symbol, 1, 0, need_bars)
    if rates is None or len(rates) < need_bars:
        return None
    closes = [rates[i][4] for i in range(mul-1, len(rates), mul)]
    if len(closes) < period + 2:
        return None
    
    if method == 0:
        vals = []
        for i in range(len(closes) - period + 1):
            vals.append(sum(closes[i:i+period]) / period)
        return vals
    elif method == 1:
        k = 2.0 / (period + 1)
        ema = [sum(closes[:period]) / period]
        for p in closes[period:]:
            ema.append(p * k + ema[-1] * (1 - k))
        return ema
    return None

def check_sma_cross(symbol, tf, fast=10, slow=30):
    fast_ma = get_ma(symbol, tf, fast, method=0)
    slow_ma = get_ma(symbol, tf, slow, method=0)
    if not fast_ma or not slow_ma or len(fast_ma) < 2 or len(slow_ma) < 2:
        return None
    f1, f2 = fast_ma[-1], fast_ma[-2]
    s1, s2 = slow_ma[-1], slow_ma[-2]
    if f1 > s1 and f2 <= s2:
        return 'buy'
    if f1 < s1 and f2 >= s2:
        return 'sell'
    return None

def check_macd_cross(symbol, tf, fast=12, slow=26, signal=9):
    fast_ma = get_ma(symbol, tf, fast, method=1)
    slow_ma = get_ma(symbol, tf, slow, method=1)
    if not fast_ma or not slow_ma or len(fast_ma) < signal + 1 or len(slow_ma) < signal + 1:
        return None
    macd_line = [f - s for f, s in zip(fast_ma[-signal-1:], slow_ma[-signal-1:])]
    signal_line = sum(macd_line[:signal]) / signal
    if macd_line[-1] > signal_line and macd_line[-2] <= signal_line:
        return 'buy'
    if macd_line[-1] < signal_line and macd_line[-2] >= signal_line:
        return 'sell'
    return None

def _mt5_process_running():
    """[ALERT] 2026-09-01：檢查 terminal64 有冇開 — mt5.initialize() 會自動啟動 terminal！
    所有 initialize 之前 call 呢個（未開 → False — 唔 initialize — 唔自動開 MT5）"""
    try:
        import subprocess as _sp_mr
        _r_mr = _sp_mr.run('tasklist /FI "IMAGENAME eq terminal64.exe" /NH', shell=True, capture_output=True, timeout=5)
        return b'terminal64' in _r_mr.stdout
    except Exception:
        return True  # 檢查唔到 → 當開住（保守 — 唔會誤判關咗）


def run_ea_strategies(ea_config, lot_size):
    """執行 EA 策略 — 根據 config 嘅 EA 名決定用邊個策略"""
    import MetaTrader5 as mt5
    if not _mt5_process_running():
        return
    if not mt5.initialize():
        return
    
    for ea_name, cfg in ea_config.items():
        if ea_name.startswith('_') or ea_name.endswith(('_tf','_lot','_magic','_status','_source')):
            continue
        # Handle both old format (cfg=str) and new format (cfg=dict)
        if isinstance(cfg, str):
            cfg = {'symbol': cfg, 'timeframe': ea_config.get(ea_name+'_tf', 'H1'),
                   'lot': float(ea_config.get(ea_name+'_lot', str(lot_size))),
                   'magic': int(ea_config.get(ea_name+'_magic', '240701'))}
        symbol = cfg.get('symbol', 'EURUSD')
        tf_map = {'M1':1,'M5':5,'M15':15,'M30':30,'H1':60,'H4':240,'D1':1440}
        tf = tf_map.get(cfg.get('timeframe', 'H1'), 60)
        magic = int(cfg.get('magic', 240701))
        
        signal = None
        if 'SMA' in ea_name.upper() or 'MA_Cross' in ea_name:
            signal = check_sma_cross(symbol, tf)
        elif 'MACD' in ea_name.upper():
            signal = check_macd_cross(symbol, tf)
        elif 'ADX' in ea_name.upper():
            # ADX trend following — 用 SMA cross 作為輔助
            signal = check_sma_cross(symbol, tf, fast=14, slow=28)
        else:
            # Default: SMA cross
            signal = check_sma_cross(symbol, tf)
        
        if signal:
            mt5.symbol_select(symbol, True)
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                continue
            
            order_type = mt5.ORDER_TYPE_BUY if signal == 'buy' else mt5.ORDER_TYPE_SELL
            price = tick.ask if signal == 'buy' else tick.bid
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot_size,
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": magic,
                "comment": f"cloud_{ea_name}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"[UPCHART] {ea_name}: {signal.upper()} {symbol} @ {price}")
            elif result:
                print(f"[WARN] {ea_name}: retcode={result.retcode}")
            else:
                print(f"[WARN] {ea_name}: order failed")
    
    mt5.shutdown()


# ================================================================
#  Heartbeat check
# ================================================================

def check_ea_heartbeat_files():
    """檢查 EA 寫出嘅 heartbeat files"""
    appdata = os.environ.get('APPDATA', '')
    terminal_dir = os.path.join(appdata, 'MetaQuotes', 'Terminal')
    common_files = os.path.join(terminal_dir, 'Common', 'Files')
    
    candidates = [common_files]
    if os.path.isdir(terminal_dir):
        for folder in os.listdir(terminal_dir):
            ff = os.path.join(terminal_dir, folder, 'Files')
            if os.path.isdir(ff) and folder != 'Common':
                candidates.append(ff)
    
    now = time.time()
    found = {}
    for fb_dir in candidates:
        if not os.path.isdir(fb_dir):
            continue
        for fname in os.listdir(fb_dir):
            if fname.startswith('hb_') and fname.endswith('.txt'):
                ea_name = fname[3:-4]
                fpath = os.path.join(fb_dir, fname)
                mtime = os.path.getmtime(fpath)
                age = now - mtime
                if age < 300:
                    found[ea_name] = {"last_check": mtime, "status": "alive", "age_sec": round(age)}
                else:
                    found[ea_name] = {"last_check": mtime, "status": "stale", "age_sec": round(age)}
    return found


def check_ea_alive_via_trades():
    """Fallback: check recent trades"""
    import MetaTrader5 as mt5
    if not _mt5_process_running():
        return {}
    if not mt5.initialize():
        return {}
    from datetime import datetime, timedelta
    since = datetime.now() - timedelta(hours=24)
    deals = mt5.history_deals_get(since, datetime.now())
    hb = {}
    if deals:
        for d in deals:
            comment = d.comment or ''
            if comment.startswith('auto_') or comment.startswith('cloud_'):
                ea_name = comment.replace('auto_','').replace('cloud_','').split('_')[0]
                hb[ea_name] = {"last_check": d.time, "status": "alive"}
    mt5.shutdown()
    return hb


# ================================================================
#  Execute Deploy — 真正 attach EA 到 chart
# ================================================================

def execute_deploy(data):
    ea_name = data.get('ea_name', '')
    symbol = data.get('symbol', 'EURUSD')
    tf = data.get('tf', 'H1')
    magic = str(data.get('magic', '240701'))
    lot = str(data.get('lot', '1.00'))

    SYMBOL_MAP = {
        'DAX40': 'DE40',
        'SP500': 'US500',
    }
    mt5_symbol = SYMBOL_MAP.get(symbol, symbol)

    print(f"[GO] [EXEC] Deploying {ea_name} -> {symbol} ({mt5_symbol}) {tf}")

    def report(msg, status='info'):
        print(f"   {msg}")
        sio.emit('install_result', {"status": status, "ea": ea_name, "msg": msg})

    try:
        # Write command file for deploy_watcher (has desktop access for pyautogui)
        cmd_data = {
            'ea_name': ea_name,
            'symbol': mt5_symbol,
            'tf': tf,
            'magic': magic,
            'lot': lot,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'source': 'agent_deploy'
        }
        cmd_filename = f'deploy_cmd_{ea_name}_{int(time.time())}.json'
        common_files = os.path.join(os.environ.get('APPDATA', ''),
                                     'MetaQuotes', 'Terminal', 'Common', 'Files')
        os.makedirs(common_files, exist_ok=True)
        # [ALERT] 2026-08-27 FIX：寫 web_add flag（等 watcher 知道係網頁操作 — 唔會誤判「PCdelete」→ remove配對）
        try:
            with open(os.path.join(common_files, f'web_add_{ea_name}.flag'), 'w') as _f_flg:
                _f_flg.write('agent_deploy')
        except Exception:
            pass
        cmd_path = os.path.join(common_files, cmd_filename)
        
        with open(cmd_path, 'w') as f:
            json.dump(cmd_data, f)
        
        print(f"   [NOTE] Watcher command written: {cmd_path}")
        print(f"   [WAIT] deploy_watcher.py 會自動 attach {ea_name} → {symbol} {tf}")
        sys.stdout.flush()
        
        # Report as sent (deploy_watcher will do the actual attach)
        report(f'📡 Deploy 指令已交給 watcher: {ea_name} → {symbol} {tf}', 'sent')

    except Exception as e:
        report(f'[FAIL] Failed to write deploy command: {str(e)[:80]}', 'error')


# ================================================================
#  Main Sync Loop
# ================================================================

def build_files_snapshot():
    """[ALERT] 2026-08-26（multi-user Phase 1）：收集local MT5 file快照（heartbeats/trades/log_last/hotkeys）
    → 每 10 秒上報俾 server — server 讀呢個（每機獨立）而唔係直接讀local
    格式: {"heartbeats": {ea: {last_check, age_sec, status}}, "trades_stats": {ea: {trades,wins,losses,profit,...}},
           "log_last": {ea: "loaded successfully"/"removed"}, "hotkeys": [ea, ...], "ts": epoch}
    """
    snap = {"ts": time.time(), "heartbeats": {}, "trades_stats": {}, "trades_raw": {}, "log_last": {}, "hotkeys": []}
    appdata = os.environ.get('APPDATA', '')
    terminal_dir = os.path.join(appdata, 'MetaQuotes', 'Terminal')
    common_files = os.path.join(terminal_dir, 'Common', 'Files')
    now = time.time()
    # 1. heartbeats（state_*.json + hb_*.txt — 帶 age）
    try:
        import glob as _gl_s
        cf_s = common_files
        for _f_s in _gl_s.glob(os.path.join(cf_s, 'state_*.json')):
            _ea_s = os.path.basename(_f_s)[6:-5]
            _age_s = now - os.path.getmtime(_f_s)
            snap['heartbeats'][_ea_s] = {"last_check": os.path.getmtime(_f_s), "age_sec": round(_age_s), "status": "alive" if _age_s < 300 else "stale"}
        for _f_s in _gl_s.glob(os.path.join(cf_s, 'hb_*.txt')):
            _ea_s = os.path.basename(_f_s)[3:-4]
            _age_s = now - os.path.getmtime(_f_s)
            if _ea_s not in snap['heartbeats']:
                snap['heartbeats'][_ea_s] = {"last_check": os.path.getmtime(_f_s), "age_sec": round(_age_s), "status": "alive" if _age_s < 300 else "stale"}
    except Exception:
        pass
    # 2. trades stats（trades_<EA>.json — 逐單計完整指標）
    try:
        import glob as _gl_t2
        for _f_t2 in _gl_t2.glob(os.path.join(common_files, 'trades_*.json')):
            _ea_t2 = os.path.basename(_f_t2)[7:-5]
            try:
                with open(_f_t2, 'rb') as _fh_t2:
                    _raw_t2 = _fh_t2.read()
                _txt_t2 = None
                for _enc_t2 in ('utf-8', 'utf-16'):
                    try:
                        _txt_t2 = _raw_t2.decode(_enc_t2); break
                    except Exception:
                        continue
                if not _txt_t2:
                    continue
                _pl = []
                for _ln_t2 in _txt_t2.splitlines():
                    _ln_t2 = _ln_t2.strip()
                    if not _ln_t2:
                        continue
                    try:
                        _td_t2 = json.loads(_ln_t2)
                        if 'profit' in _td_t2:
                            _pl.append(_td_t2.get('profit', 0))
                    except Exception:
                        continue
                if _pl:
                    _gp = sum(p for p in _pl if p > 0)
                    _gl_v = sum(-p for p in _pl if p < 0)
                    _w = sum(1 for p in _pl if p > 0)
                    _l = sum(1 for p in _pl if p < 0)
                    _aw = round(_gp / _w, 2) if _w > 0 else 0
                    _al = round(_gl_v / _l, 2) if _l > 0 else 0
                    _cum2 = 0.0; _peak2 = 0.0; _dd2 = 0.0
                    for _p2 in _pl:
                        _cum2 += _p2
                        if _cum2 > _peak2: _peak2 = _cum2
                        _d2 = _peak2 - _cum2
                        if _d2 > _dd2: _dd2 = round(_d2, 2)
                    _wr2 = (_w + _l) > 0 and _w / (_w + _l) or 0
                    snap['trades_stats'][_ea_t2] = {
                        "trades": len(_pl), "wins": _w, "losses": _l,
                        "profit": round(sum(_pl), 2), "gross_profit": round(_gp, 2),
                        "gross_loss": round(_gl_v, 2), "avg_win": _aw, "avg_loss": _al,
                        "max_dd": _dd2, "expectancy": round(_wr2 * _aw - (1 - _wr2) * _al, 2),
                        "profit_factor": round(_gp / _gl_v, 2) if _gl_v > 0 else (99.99 if _gp > 0 else 0)
                    }
            except Exception:
                continue
    except Exception:
        pass
    # 2b. trades_raw（逐單明細 — 分析/報告/equity curve 用 — 每 EA 最多 500 筆）
    try:
        import glob as _gl_r
        for _f_r in _gl_r.glob(os.path.join(common_files, 'trades_*.json')):
            _ea_r = os.path.basename(_f_r)[7:-5]
            try:
                with open(_f_r, 'rb') as _fh_r:
                    _raw_r = _fh_r.read()
                _txt_r = None
                for _enc_r in ('utf-8', 'utf-16'):
                    try:
                        _txt_r = _raw_r.decode(_enc_r); break
                    except Exception:
                        continue
                if not _txt_r:
                    continue
                _recs_r = []
                for _ln_r in _txt_r.splitlines():
                    _ln_r = _ln_r.strip()
                    if not _ln_r:
                        continue
                    try:
                        _td_r = json.loads(_ln_r)
                        if 'profit' in _td_r:
                            _recs_r.append({
                                "time": _td_r.get('time', 0),
                                "symbol": _td_r.get('symbol', ''),
                                "profit": _td_r.get('profit', 0),
                                "type": _td_r.get('type', ''),
                                "volume": _td_r.get('volume', 0),
                                "price": _td_r.get('price', 0),
                                "magic": _td_r.get('magic', ''),
                            })
                    except Exception:
                        continue
                # 最多 500 筆（最尾 500 — 最新）
                snap['trades_raw'][_ea_r] = _recs_r[-500:]
            except Exception:
                continue
    except Exception:
        pass
    # 3. log_last（terminal Logs — 每 EA 最後狀態）
    try:
        import glob as _gl_l
        _latest_l = None
        if os.path.isdir(terminal_dir):
            for _d_l in os.listdir(terminal_dir):
                _lgd_l = os.path.join(terminal_dir, _d_l, 'Logs')
                if os.path.isdir(_lgd_l):
                    for _f_l in _gl_l.glob(os.path.join(_lgd_l, '2026*.log')):
                        if _latest_l is None or os.path.getmtime(_f_l) > os.path.getmtime(_latest_l):
                            _latest_l = _f_l
        if _latest_l:
            with open(_latest_l, 'rb') as _f_l:
                _raw_l = _f_l.read()
            _txt_l = None
            for _enc_l in ('utf-16-le', 'utf-8'):
                try:
                    _txt_l = _raw_l.decode(_enc_l, errors='ignore'); break
                except Exception:
                    continue
            if _txt_l:
                import re as _re_l
                for _ln_l in _txt_l.splitlines()[-80:]:
                    _m_l = _re_l.search(r'([A-Za-z_][A-Za-z0-9_]*) \([A-Za-z0-9._]+,[A-Z0-9]+\)\s+[^\n]*(removed|loaded successfully)', _ln_l)
                    if _m_l:
                        snap['log_last'][_m_l.group(1)] = _m_l.group(2)
    except Exception:
        pass
    # 4. hotkeys（config/hotkeys.ini — 有deploy過嘅 EA）
    try:
        if os.path.isdir(terminal_dir):
            import re as _re_h
            for _d_h in os.listdir(terminal_dir):
                _hkf_h = os.path.join(terminal_dir, _d_h, 'config', 'hotkeys.ini')
                if os.path.isfile(_hkf_h):
                    _c_h = open(_hkf_h, 'r', encoding='utf-16-le', errors='ignore').read()
                    for _m_h in _re_h.finditer(r'Experts\\([A-Za-z_][A-Za-z0-9_]*)\.ex5\s*=', _c_h):
                        if _m_h.group(1) not in snap['hotkeys']:
                            snap['hotkeys'].append(_m_h.group(1))
                    break
    except Exception:
        pass
    return snap


def _start_tray_icon():
    """[ALERT] 2026-08-26（user要求：success明顯啲）：Windows 系統匣圖示
    綠色 = Agent 連住 server；紅色 = disconnect。hover 顯示狀態。
    """
    try:
        import pystray
        from PIL import Image, ImageDraw

        def _make_icon(color):
            img = Image.new("RGB", (64, 64), color)
            d = ImageDraw.Draw(img)
            d.ellipse([8, 8, 56, 56], fill=color)
            d.text((20, 22), "T", fill="white")
            return img

        _tray_icons = {"green": _make_icon((0, 180, 60)), "red": _make_icon((220, 50, 50))}
        _tray_state = {"color": "green"}

        def _on_click(icon, item):
            if str(item) == "Exit":
                icon.stop()
                os._exit(0)

        def _tray_update_loop():
            while True:
                try:
                    if sio.connected:
                        if _tray_state["color"] != "green":
                            _tray_state["color"] = "green"
                            _tray.icon = _tray_icons["green"]
                            _tray.title = "Tradotcom Agent - Online"
                    else:
                        if _tray_state["color"] != "red":
                            _tray_state["color"] = "red"
                            _tray.icon = _tray_icons["red"]
                            _tray.title = "Tradotcom Agent - Offline"
                except Exception:
                    pass
                time.sleep(3)

        _tray = pystray.Icon("TradotcomAgent", _tray_icons["green"], "Tradotcom Agent",
                             menu=pystray.Menu(pystray.MenuItem("Exit", _on_click)))
        threading.Thread(target=_tray_update_loop, daemon=True).start()
        _tray.run_detached()
        print("[GREEN] Tray icon started (green = online)")
        return True
    except Exception as e:
        print(f"[WARN] Tray icon unavailable (no pystray?): {e}")
        return False


def _ensure_connected():
    """[ALERT] 2026-08-26（multi-user Phase 1）：確保 SocketIO connection（connect() failed但背景未連 → 重試）
    [ALERT] 2026-09-01 FIX（agent 每 60 秒 reconnect 循環）：加 reconnect backoff —
    連唔到先等 30 秒再試（唔好每 5 秒即刻重連 — 會令 server 每次 reconnect auto-sent EA config → 開 MT5）"""
    global _last_reconnect_attempt
    if sio.connected:
        _last_reconnect_attempt = 0
        return True
    try:
        # 唔好太密重連（30 秒內唔好試多過一次）
        _now_rc = time.time()
        if _last_reconnect_attempt and _now_rc - _last_reconnect_attempt < 30:
            return False
        _last_reconnect_attempt = _now_rc
        # [ALERT] 2026-08-27 FIX：改 websocket（polling 喺 threading async_mode 下唔穩定 — 成日disconnect/BadNamespace）
        sio.connect(f"{SERVER_URL}", transports=['websocket', 'polling'], wait=False)
        return True
    except Exception:
        return False


def sync_loop():
    """每 2 秒 poll deploy + 每 10 秒 sync + 每 30 秒 auto-trade"""
    last_sync = 0
    last_trade = 0
    last_reconn = 0
    last_poll_dq = 0
    while True:
        try:
            # [ALERT] 2026-08-27 FIX（deploy收唔到 — tunnel disconnect窗口）：poll server deploy_queue（fallback）
            # [ALERT] 2026-08-28 FIX（deploy卡住 — 根據 stable 版本結構）：poll 唔依賴 sio.connected（agent 每分鐘reconnect → sio.connected False → poll 唔行 → deploy_queue 冇被讀 → deploy卡死）
            # → disconnect都照 poll（deploy_queue 係 fallback — disconnect時更需要 poll）
            if time.time() - last_poll_dq >= 5:
                last_poll_dq = time.time()
                try:
                    import urllib.request as _ur_dq
                    # [ALERT] 2026-08-27 FIX：poll 用 localhost（agent 喺local — 直接連 server 快 — 唔經 tunnel 慢/timeout）
                    _poll_url = SERVER_URL
                    if 'mt5cloud.esgov.org' in _poll_url or 'http' in _poll_url and 'localhost' not in _poll_url:
                        try:
                            _poll_url = 'http://localhost:5001'
                        except Exception:
                            pass
                    _req_dq = _ur_dq.Request(f"{_poll_url}/api/agent-poll-deploy?agent_id={AGENT_ID}")
                    with _ur_dq.urlopen(_req_dq, timeout=10) as _r_dq:
                        _dq = json.loads(_r_dq.read().decode('utf-8'))
                    # [ALERT] 2026-08-28 FIX：poll 讀到「remove agent」標記（server 寫 — emit 收唔到時 fallback）
                    if _dq.get('_remove_agent'):
                        print(f"🚫 [POLL] 讀到remove標記 — 執行remove（emit 收唔到 fallback）")
                        sys.stdout.flush()
                        _alog_write("[POLL] remove agent（server 標記 fallback）")
                        on_shutdown({'reason': 'web_remove_poll'})
                        break
                    if _dq.get('ea_name'):
                        _ddq = _dq
                        print(f"[IN] [POLL] 讀到 deploy_queue: {_ddq.get('ea_name')} -> {_ddq.get('symbol')}（emit 收唔到 fallback）")
                        sys.stdout.flush()
                        _alog_write(f"[POLL] deploy_queue fallback: {_ddq.get('ea_name')}")
                        execute_deploy(_ddq)
                except Exception as _e_dq:
                    pass
            # [ALERT] 2026-08-26：未connection → 每 5 秒嘗試reconnect（唔好永遠斷）
            if not sio.connected:
                if time.time() - last_reconn >= 5:
                    _ensure_connected()
                    last_reconn = time.time()
            # Sync MT5 data every 10 seconds
            now = time.time()
            if sio.connected and now - last_sync >= 10:
                data = get_mt5_status()
                data['agent_id'] = AGENT_ID
                data['token'] = AGENT_TOKEN
                # [ALERT] 2026-08-26 FIX：server handle_sync 讀 data['account']（login/balance 等）— 唔係 status 散 key
                data['account'] = {k: data.get(k) for k in ('login','balance','equity','margin','server','currency','leverage','name') if k in data}
                data['heartbeats'] = dict(ea_heartbeats)
                try:
                    hb_files = check_ea_heartbeat_files()
                    hb_trades = check_ea_alive_via_trades()
                    for ea, info in hb_files.items():
                        data['heartbeats'][ea] = info
                    for ea, info in hb_trades.items():
                        if ea not in data['heartbeats']:
                            data['heartbeats'][ea] = info
                    if hb_files:
                        print(f"[HB] Heartbeats: {hb_files}")
                        sys.stdout.flush()
                except Exception as e:
                    print(f'   [HB] Error: {e}')
                    import traceback
                    traceback.print_exc()
                # [ALERT] 2026-08-26（multi-user Phase 1）：上報「local MT5 file快照」
                # → server 讀呢個（每機獨立）— 唔再直接讀localfile
                try:
                    data['files_snapshot'] = build_files_snapshot()
                except Exception as _e_snap:
                    print(f'   [SNAP] Error: {_e_snap}')
                # [ALERT] 2026-08-27 FIX：payload 太大（1.2MB deals）→ socket disconnect
                # → deals 只每 60 秒傳一次（減輕 sync payload — 避免disconnect）
                global _last_deals_sent
                if _deals_cache is not None and time.time() - _last_deals_sent > 60:
                    data['deals'] = _deals_cache
                    _last_deals_sent = time.time()
                else:
                    data.pop('deals', None)  # 輕量 sync（唔帶 deals）
                # [ALERT] 2026-09-02 FIX（VPS balance 未顯示 — agent 每幾秒斷線）：trades_raw 太大（500 筆×4 EA ≈ 400KB）→ 每 10 秒帶 → socket 斷
                # → trades_raw 都只每 60 秒帶一次（輕量 sync 唔帶 trades_raw）
                global _last_trades_raw_sent
                if time.time() - _last_trades_raw_sent > 60:
                    _last_trades_raw_sent = time.time()
                    # 帶 trades_raw（原有）
                else:
                    data.pop('trades_raw', None)  # 輕量 sync（唔帶 trades_raw）
                    if 'files_snapshot' in data and isinstance(data['files_snapshot'], dict):
                        data['files_snapshot'].pop('trades_raw', None)
                try:
                    sio.emit('agent_sync', data)
                    last_sync = now
                    # [ALERT] 2026-09-02 DEBUG（VPS balance 未顯示）：print sync 有冇行
                    print(f"[SYNC] sent: account={data.get('account',{}).get('balance')} hb={len(data.get('heartbeats',{}))} files_snap={bool(data.get('files_snapshot'))}")
                    sys.stdout.flush()
                except Exception as _e_sync_emit:
                    print(f"   [SYNC-EMIT] {_e_sync_emit} → force reconnect")
                    sys.stdout.flush()
                    try:
                        sio.disconnect()
                    except Exception:
                        pass
                    time.sleep(1)
                    try:
                        sio.connect(f"{SERVER_URL}", transports=['websocket', 'polling'], wait=False)
                    except Exception:
                        pass
                    last_reconn = time.time()

            # Auto-trade every 30 seconds
            if now - last_trade >= 30:
                last_trade = now
                if ea_config_cache:
                    run_ea_strategies(ea_config_cache, float(ea_config_cache.get('_default_lot', 1.00)))
        except ImportError:
            pass
        except Exception as e:
            import traceback
            print(f"   [SYNC] Error: {e}")
            traceback.print_exc()
        time.sleep(2)


def connect_mt5():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        return False
    return True

def get_mt5_status():
    import MetaTrader5 as mt5
    # [ALERT] 2026-09-01 FIX（用戶實測：一刪咗 MT5 就自動開返）：mt5.initialize() 會自動啟動 terminal64！
    # → 先檢查 MT5 有冇開（tasklist）— 未開 → 唔 initialize（返回 not available — 唔自動開）
    if not _mt5_process_running():
        return {"error": "MT5 not available (not running)", "mt5_auto_launch": False}
    if not mt5.initialize():
        return {"error": "MT5 not available"}
    
    account = mt5.account_info()
    status = {
        "login": account.login if account else 0,
        "balance": account.balance if account else 0,
        "equity": account.equity if account else 0,
        "margin": account.margin if account else 0,
        "server": account.server if account else "",
        "positions": len(mt5.positions_get() or []),
    }
    # [ALERT] 2026-08-21：收集 history deals（Trades/Win/P&L 真實數據）
    # before冇收集 → agent.deals 永遠空 → /api/analysis「No data yet」→ 前端 Trades/Win/P&L 全部「—」
    # [ALERT] 2026-08-21 FIX：history_deals_get(since, now) 有 caching 問題 — 用 (0, now) 攞全部（實測攞到全部 deals）
    # [ALERT] 2026-08-27 FIX：deals 攞取好重（每次 sync 攞全部 → 卡 >25s → socketio timeout disconnect）
    # → 加 cache（60 秒內唔重攞 — 輕量 sync 唔卡）
    global _deals_cache, _deals_cache_ts
    try:
        from datetime import datetime, timedelta
        _now_c = time.time()
        if _deals_cache is None or (_now_c - _deals_cache_ts) > 60:
            deals = mt5.history_deals_get(0, datetime.now())
            deal_list = []
            if deals:
                for d in deals:
                    # 只收集有 profit 嘅 closed deals（成交記錄 — 開倉冇 profit）
                    if d.profit != 0 or d.entry == mt5.DEAL_ENTRY_OUT:
                        deal_list.append({
                            "ticket": d.ticket,
                            "magic": d.magic,
                            "symbol": d.symbol,
                            "profit": d.profit,
                            "time": d.time,
                            "entry": d.entry,
                            "type": d.type,
                            "volume": d.volume,
                            "price": d.price,
                            "comment": d.comment or '',
                        })
            _deals_cache = deal_list
            _deals_cache_ts = _now_c
        status["deals"] = _deals_cache if _deals_cache is not None else []
        status["deals_count"] = len(status["deals"])
        if status["deals"]:
            print(f"[STATS] Synced {len(status['deals'])} deals to server")
            sys.stdout.flush()
    except Exception as e:
        print(f"   [DEALS] Error: {e}")
        status["deals"] = []
    mt5.shutdown()
    return status


# ================================================================
#  Startup
# ================================================================

# [ALERT] 2026-08-27 FIX：console 視窗標題改做「Tradotcom Agent」（唔好顯示 python.exe path — 全黑冇品牌）
try:
    import ctypes as _ct
    _ct.windll.kernel32.SetConsoleTitleW("Tradotcom Agent")
except Exception:
    try:
        os.system("title Tradotcom Agent")
    except Exception:
        pass

print()
print("=" * 56)
print("  ☁️  Tradotcom Agent")
print("  ══════════════════")
print(f"  Server:   {SERVER_URL}")
print(f"  Agent ID: {AGENT_ID}")
print(f"  MT5:      {'[OK] Available' if mt5_available else '[FAIL] Not installed'}")
print("=" * 56)
print("  Connecting...\n")
_alog_write(f"Connecting to {SERVER_URL}...")

try:
    # [ALERT] 2026-08-27 FIX：wait=False（非阻塞 — 唔會掛死）+ 短 timeout
    # before blocking connect 連唔到 → 永遠卡住 → 冇 log → user「冇綠燈」
    sio.connect(f"{SERVER_URL}", transports=['websocket', 'polling'], wait=False, retry=False)
except Exception as e:
    # [ALERT] 2026-08-26 FIX（multi-user Phase 1）：python-socketio 5.x connect() 有時 raise
    # 「One or more namespaces failed to connect」— 但背景 namespace 已connect（polling ack 時序）
    # → 唔好 exit — 繼續跑（sync_loop 會 check sio.connected + 自動reconnect）
    print(f"[WARN] connect() warning（可能已連 — 背景再接）: {e}")
    _alog_write(f"[WARN] connect() warning: {str(e)[:120]}")
    try:
        sio.connect(f"{SERVER_URL}", transports=['websocket', 'polling'], retry=True)
    except Exception as e2:
        print(f"[WARN] retry connect 都warning: {e2}")
        _alog_write(f"[WARN] retry connect 都warning: {str(e2)[:120]}")

sync_thread = threading.Thread(target=sync_loop, daemon=True)
sync_thread.start()


# [ALERT] 2026-08-28（user要求：安裝 = 全部裝返）：agent start時自動開平台服務（watcher/alert_worker/auto_trade_detector）
# remove agent 時會停晒呢啲 → 重新安裝 agent start → 自動開返（完整 cycle）
def _ensure_platform_services():
    """檢查 + start平台服務（如果未行）— 用 agent 同dir嘅 deploy_watcher.py 等"""
    try:
        _base = os.path.dirname(os.path.abspath(__file__))
        # 平台服務dir（agent 安裝位置 — 同 agent.py 一齊）
        _svc_dir = _base
        _py_exe = sys.executable
        _svcs = {
            'deploy_watcher': [os.path.join(_svc_dir, 'deploy_watcher.py'), os.path.join(_svc_dir, 'deploy_notify.py')],
            'alert_worker': [os.path.join(_svc_dir, 'alert_worker.py')],
            'auto_trade_detector': [os.path.join(_svc_dir, 'auto_trade_detector.py')],
        }
        # [ALERT] 2026-08-28 FIX：額外依賴（auto_attach/refresh_navigator/control_guard — watcher deploy/refresh 要 — 全新環境實測漏咗）
        _extra_deps = [
            os.path.join(_svc_dir, 'auto_attach.py'),
            os.path.join(_svc_dir, 'refresh_navigator.py'),
            os.path.join(_svc_dir, 'control_guard.py'),
        ]
        for _dep in _extra_deps:
            if not os.path.isfile(_dep):
                try:
                    import urllib.request as _ur_dep
                    _dl_url_dep = 'http://localhost:5001' if 'localhost' not in SERVER_URL else SERVER_URL
                    _dl_url_dep = f"{_dl_url_dep}/api/agent-service/{os.path.basename(_dep)}"
                    _req_dep = _ur_dep.Request(_dl_url_dep, headers={'User-Agent': 'TradotcomAgent/1.0'})
                    with _ur_dep.urlopen(_req_dep, timeout=20) as _r_dep:
                        _data_dep = _r_dep.read()
                    os.makedirs(os.path.dirname(_dep), exist_ok=True)
                    with open(_dep, 'wb') as _f_dep:
                        _f_dep.write(_data_dep)
                    print(f"   [OK] [SVC] 額外依賴已下載: {os.path.basename(_dep)}")
                except Exception as _e_dep:
                    print(f"   [WARN] [SVC] 額外依賴下載failed（{os.path.basename(_dep)}）: {_e_dep}")
        import subprocess as _sp_svc
        for _name, _args in _svcs.items():
            _script = _args[0]
            # [ALERT] 2026-08-28：缺file → 從 server 下載（安裝 = 全部裝返 — remove刪咗 → 重新安裝自動下載返）
            # [ALERT] 2026-08-28 FIX：下載全部依賴（_args 可能有多個 — 如 deploy_watcher + deploy_notify）— 但只 Popen 第一個（script）
            for _dl_script in _args:
                if not os.path.isfile(_dl_script):
                    try:
                        import urllib.request as _ur_svc
                        # [ALERT] 用 localhost（local agent 直接連 server 快 — tunnel 可能 407/慢）
                        _dl_url_svc = 'http://localhost:5001' if 'localhost' not in SERVER_URL else SERVER_URL
                        _dl_url_svc = f"{_dl_url_svc}/api/agent-service/{os.path.basename(_dl_script)}"
                        _req_svc = _ur_svc.Request(_dl_url_svc, headers={'User-Agent': 'TradotcomAgent/1.0'})
                        with _ur_svc.urlopen(_req_svc, timeout=20) as _r_svc:
                            _data_svc = _r_svc.read()
                        os.makedirs(os.path.dirname(_dl_script), exist_ok=True)
                        with open(_dl_script, 'wb') as _f_svc:
                            _f_svc.write(_data_svc)
                        print(f"   [OK] [SVC] {_name} 已下載（{os.path.basename(_dl_script)}）")
                    except Exception as _e_dl:
                        print(f"   [WARN] [SVC] {_name} 下載failed（{os.path.basename(_dl_script)}）: {_e_dl}")
            if not os.path.isfile(_script):
                print(f"   [WARN] [SVC] {_name} 腳本not exist: {_script}（skip）")
                continue
            # 檢查係咪已經行緊（command line 含 script 名）
            # [ALERT] 2026-08-28 FIX：加 $_.Name -eq 'python.exe' 過濾（before淨 CommandLine -match 會 match 到自己 session 嘅 bash/powershell → count>0 → 誤判「已行緊」→ 永遠唔開真服務）
            _chk = _sp_svc.run(
                ['powershell', '-NoProfile', '-Command',
                 f"Get-CimInstance Win32_Process | Where-Object {{$_.Name -eq 'python.exe' -and $_.CommandLine -match '{_name}'}} | Measure-Object | Select-Object -ExpandProperty Count"],
                capture_output=True, timeout=10)
            _count = 0
            try:
                _count = int(_chk.stdout.decode(errors='ignore').strip() or '0')
            except Exception:
                pass
            if _count > 0:
                print(f"   [OK] [SVC] {_name} 已行緊（skip）")
                continue
            # 開（python.exe + redirect log — 唔好 pythonw 冇 console）
            try:
                _log_f = open(os.path.join(_svc_dir, f'{_name}.log'), 'a', encoding='utf-8')
                _sp_svc.Popen([_py_exe, '-u', _script], stdout=_log_f, stderr=_log_f,
                              creationflags=0x00000008 if hasattr(_sp_svc, 'CREATE_NO_WINDOW') else 0)
                print(f"   [OK] [SVC] {_name} 已start")
            except Exception as _e_svc:
                print(f"   [WARN] [SVC] {_name} startfailed: {_e_svc}")
    except Exception as _e_all:
        print(f"   [WARN] [SVC] 平台服務檢查failed: {_e_all}")


try:
    _ensure_platform_services()
except Exception:
    pass

# [ALERT] 2026-08-26（user要求：success明顯啲）：系統匣圖示（綠色=online 紅色=offline）
try:
    _start_tray_icon()
except Exception:
    pass

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[STOP] Agent stopped")
    sio.disconnect()
