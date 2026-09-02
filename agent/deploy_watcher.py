#!/usr/bin/env python3
"""
Tradotcom Deploy Watcher — 自動 detect deploy 指令，用 terminal desktop access 進行 GUI attach

Background: agent.py 嘅 auto_attach_ea() spawn subprocess 冇 desktop access → pyautogui 唔 work ❌
Solution: deploy_watcher.py 長行喺 terminal(background=true) — 有 desktop access ✅

流程：
1. 監控 Common/Files/deploy_cmd_*.json (由 agent.py write)
2. detect 到新 file → 行 auto_attach.py (pyautogui 得!)
3. 回報結果俾 server
4. 清理 command file
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys
import time
import json
import glob
import queue
import shutil
import threading
import subprocess
import requests

# 🚨 2026-08-20：auto_attach 一律用 python.exe 絕對path（唔可以用 pythonw — pyautogui/pywinauto 無 console hang 5min timeout）
_PY_EXE = r"C:\Users\hongk\AppData\Local\Programs\Python\Python311\python.exe"
if not os.path.isfile(_PY_EXE):
    _PY_EXE = shutil.which('python') or shutil.which('python3') or sys.executable

# ─── Deploy Notification (AI 控制中視窗) ───
_DEPLOY_NOTIFY_DIR = os.path.dirname(__file__)
sys.path.insert(0, _DEPLOY_NOTIFY_DIR)
import deploy_notify

# ─── Config ───
SERVER_URL = os.environ.get('MT5_CLOUD_URL', 'http://localhost:5001')
AGENT_ID = os.environ.get('MT5_CLOUD_AGENT', 'DEV00001')
POLL_INTERVAL = 3  # seconds

COMMON_FILES = os.path.join(os.environ.get('APPDATA', ''),
                            'MetaQuotes', 'Terminal', 'Common', 'Files')
AUTO_ATTACH_SCRIPT = os.path.join(os.path.dirname(__file__), 'auto_attach.py')
WATCHER_LOCK_FILE = os.path.join(os.path.dirname(__file__), '.watcher_running')
AUTO_ATTACH_LOCK = os.path.join(os.path.dirname(__file__), '.auto_attach_running')
_last_pause_time = {}  # 🚨 2026-08-31 FIX（#157）：pause_cmd 60 秒 dedupe（防重複 remove 誤剷其他 EA）

def is_auto_attach_running():
    """Check if auto_attach.py is already running (lock file or process)"""
    # Check control_guard lock 都算（AI 控制緊唔好重複）
    try:
        cg_lock = os.path.join(os.path.dirname(__file__), '.ai_control.lock')
        if os.path.exists(cg_lock):
            return True
    except:
        pass
    # Check lock file
    if os.path.exists(AUTO_ATTACH_LOCK):
        try:
            with open(AUTO_ATTACH_LOCK, 'r') as f:
                pid = int(f.read().strip())
            # Check if process is still alive（⚠️ 2026-08：lock 可能係 watcher 自己（deploy worker 用 os.getpid 寫）— 自己唔算）
            import psutil as _ps
            _self_pid = os.getpid()
            if _ps.pid_exists(pid) and pid != _self_pid:
                return True
        except:
            pass
        # Stale lock file
        try:
            os.remove(AUTO_ATTACH_LOCK)
        except:
            pass
    
    # Check running processes
    try:
        import subprocess as _sp
        out = _sp.check_output('wmic process where "name=\'python.exe\'" get commandline', 
                               shell=True, timeout=5)
        if b'auto_attach.py' in out:
            return True
    except:
        pass
    return False

# ─── Helpers ───

def get_server_url():
    """Get server URL, preferring localhost for reliability"""
    return SERVER_URL

def find_deploy_commands():
    """搵 deploy_cmd_*.json files in Common/Files"""
    cmd_dir = COMMON_FILES
    if not os.path.isdir(cmd_dir):
        return []
    pattern = os.path.join(cmd_dir, 'deploy_cmd_*.json')
    files = sorted(glob.glob(pattern), key=os.path.getmtime)
    return files

def read_command(filepath):
    """Read deploy command JSON"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"⚠️ Cannot read {filepath}: {e}")
        # Delete corrupted file
        try:
            os.remove(filepath)
        except:
            pass
        return None

def run_auto_attach(cmd_data):
    """Run auto_attach.py with given parameters"""
    ea_name = cmd_data.get('ea_name', '')
    symbol = cmd_data.get('symbol', 'EURUSD')
    tf = cmd_data.get('tf', 'H1')
    # 🚨 2026-08-20 FIX：magic 空 string → fallback default（auto_attach --magic 空 → argparse failed → 假success）
    magic = cmd_data.get('magic') or '240701'
    lot = cmd_data.get('lot', '1.00')

    # 🚨 2026-08-22（user要求：UAC 檢測機制）：deploy前檢查有冇 UAC alert（auto_attach 寫嘅 — 需要user手動撳授權）
    try:
        _uac_flag = os.path.join(os.path.dirname(AUTO_ATTACH_SCRIPT), '.uac_alert')
        if os.path.isfile(_uac_flag):
            _uac_txt = open(_uac_flag, encoding='utf-8').read().strip()
            print(f"⚠️ [WATCHER] 偵測到 UAC 授權需要處理: {_uac_txt[:80]}")
            # 通知user（activity log）
            try:
                _append_activity_log({'type': 'uac', 'message': f'MT5 需要授權 — 請喺PC撳「允許/是」({_uac_txt[:60]})'})
            except Exception:
                pass
    except Exception:
        pass

    print(f"\n{'='*50}")
    print(f"  🚀 [WATCHER] Deploying: {ea_name} → {symbol} {tf}")
    print(f"     Magic: {magic}, Lot: {lot}")
    print(f"{'='*50}")
    
    # Build auto_attach command
    # 🚨 2026-08-20：hardcode python.exe 絕對path（唔用 sys.executable — 如果 watcher 用 pythonw 起 → sys.executable=pythonw → auto_attach hang 5min timeout）
    _PYEXE = _PY_EXE
    cmd = [
        _PYEXE,
        AUTO_ATTACH_SCRIPT,
        '--ea', ea_name,
        '--symbol', symbol,
        '--tf', tf,
        '--magic', str(magic),
        '--lot', str(lot),
    ]
    
    print(f"   Running: {' '.join(cmd)}")
    sys.stdout.flush()

    # 🚨 2026-08-22 FIX（Breakout 假success — watcher 讀舊 output）：spawn 前先清 aa_debug.log
    # （auto_attach 死喺中途 → tee 覆寫唔完整 → watcher 讀到上次 SUCCESS 殘留 → 假success）
    # → 先清空，確保讀到嘅一定係今次 output
    try:
        _dbg_clear = os.path.join(os.path.dirname(AUTO_ATTACH_SCRIPT), 'aa_debug.log')
        if os.path.isfile(_dbg_clear):
            with open(_dbg_clear, 'w', encoding='utf-8') as _fclr:
                _fclr.write('')
    except Exception:
        pass

    try:
        # 🚨 2026-08-20（watcher-aa-debug-tee）：auto_attach 完整 stdout tee 去 aa_debug.log
        # before capture_output 只 print keyword lines → 真實failed output（not found under / attempt x/3）被過濾
        # → 睇唔到真因。now完整 output 寫落 file，診斷時直接讀。
        import subprocess as _sp_dbg
        _dbg = os.path.join(os.path.dirname(AUTO_ATTACH_SCRIPT), 'aa_debug.log')
        # 🚨 2026-08-21 FIX：tee -a（append）累積舊 output → watcher 讀「最近 60 行」誤判（讀到上次 Breakout/Grid output → ATR_Stop 假success）
        # 🚨 2026-08-25 FIX（人手模擬測試 0/5 — auto_attach spawn 255）：before用 shell=True + tee + encoding='utf-8'
        # → auto_attach output 有 GBK 中文字節（0xb8 等）→ subprocess reader thread decode crash（即使 errors='replace' 都 crash — Windows subprocess bug）
        # → exit 255 → deploy全部failed
        # 改：唔用 shell/tee — 直接 run（bytes — 無 reader crash）+ 手動寫 output 去 aa_debug.log
        _dbg = os.path.join(os.path.dirname(AUTO_ATTACH_SCRIPT), 'aa_debug.log')
        try:
            with open(_dbg, 'wb') as _fdbg2:
                _fdbg2.write(b'')  # 清空
        except Exception:
            pass
        result = _sp_dbg.run(cmd, timeout=320, capture_output=True,
                             cwd=os.path.dirname(AUTO_ATTACH_SCRIPT))
        # 寫 output（bytes）去 aa_debug.log
        try:
            with open(_dbg, 'wb') as _fdbg3:
                _fdbg3.write(result.stdout or b'')
                _fdbg3.write(result.stderr or b'')
        except Exception:
            pass
        
        # Print output (only key lines — 讀 aa_debug.log 最新段)
        print(f"   Exit code: {result.returncode}")
        try:
            with open(_dbg, 'r', encoding='utf-8', errors='replace') as _fdbg:
                _dbg_lines = _fdbg.read().split('\n')
            # 只印最近 60 行嘅 keyword lines（避免成個 log 太長）
            for line in _dbg_lines[-60:]:
                line_s = line.strip()
                if any(kw in line_s for kw in ['🎉', '✅', '❌', '🟢', '🔴', '⚠️', '💓', '📋', '🎯', 'SUCCESS', 'FAIL', 'not found', 'attempt']):
                    print(f"   {line_s}")
        except Exception:
            pass
        
        if result.returncode == 0:
            # 🚨 2026-08-21 FIX：唔好淨靠 returncode — 確認 auto_attach output 有真 SUCCESS（return 0 都可能內部 fail — 例如open chart failed return False → argparse 都係 0）
            _aa_output = ''
            try:
                with open(_dbg, 'r', encoding='utf-8', errors='replace') as _fchk:
                    _aa_output = _fchk.read()
            except Exception:
                pass
            _aa_ok = ('SUCCESS' in _aa_output) or ('success attach' in _aa_output) or ('attach success' in _aa_output)
            if not _aa_ok and _aa_output.strip():
                print(f"   ⚠️ auto_attach output 冇 SUCCESS（可能內部 fail）— 最後幾行：")
                for _l in _aa_output.split('\\n')[-8:]:
                    if _l.strip():
                        print(f"     {_l.strip()[:90]}")
                sys.stdout.flush()
                _append_activity_log({
                    'time': time.time(),
                    'action': 'deploy_result',
                    'ea': ea_name,
                    'message': f'{ea_name} deploy未確認（auto_attach 冇 SUCCESS — 檢查 MT5）',
                    'source': 'watcher'
                })
                return False
            print(f"   🎉 {ea_name} 已success attach!")
            sys.stdout.flush()
            # 寫 deploy done activity log（前端 poll 嚟關warning視窗）
            _append_activity_log({
                'time': time.time(),
                'action': 'deploy_result',
                'ea': ea_name,
                'message': f'{ea_name} deploydone（attach success）',
                'source': 'watcher'
            })
            return True
        else:
            if result.stderr:
                print(f"   Stderr: {result.stderr[-300:]}")
            print(f"   ❌ {ea_name} attach failed (exit={result.returncode})")
            sys.stdout.flush()
            # 寫 deploy failed activity log（前端 poll 嚟關warning視窗）
            _append_activity_log({
                'time': time.time(),
                'action': 'deploy_result',
                'ea': ea_name,
                'message': f'{ea_name} deploy failed（attach failed）',
                'source': 'watcher'
            })
            return False
            
    except subprocess.TimeoutExpired:
        print(f"   ⚠️ auto_attach.py timeout (5 min)")
        sys.stdout.flush()
        _append_activity_log({
            'time': time.time(),
            'action': 'deploy_result',
            'ea': ea_name,
            'message': f'{ea_name} deploy failed（timeout）',
            'source': 'watcher'
        })
        return False
    except Exception as e:
        print(f"   ❌ auto_attach error: {e}")
        sys.stdout.flush()
        _append_activity_log({
            'time': time.time(),
            'action': 'deploy_result',
            'ea': ea_name,
            'message': f'{ea_name} deploy failed（{e}）',
            'source': 'watcher'
        })
        return False

def report_to_server(ea_name, success, message=''):
    """報告 deploy 結果俾 server"""
    try:
        url = f"{get_server_url()}/api/watcher-report"
        payload = {
            'agent_id': AGENT_ID,
            'ea_name': ea_name,
            'status': 'ok' if success else 'error',
            'message': message,
        }
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            print(f"   📡 Server report: {'✅' if success else '❌'} {ea_name}")
        else:
            print(f"   ⚠️ Server report failed: {resp.status_code}")
    except Exception as e:
        print(f"   ⚠️ Cannot report to server: {e}")
    sys.stdout.flush()

def process_deploy(filepath):
    """處理一個 deploy command file"""
    cmd_data = read_command(filepath)
    if not cmd_data:
        return
    ea_name = cmd_data.get('ea_name', 'unknown')

    # 🚨 2026-08-31 FIX（舊 deploy_cmd 殘留觸發 — 用戶實測「未話開始就開始」）：
    # deploy_cmd 帶 fingerprint（account + agent_id — server 寫）— 檢查係咪屬於「當前本機 agent」
    # 舊 account 殘留嘅 deploy_cmd（Common/Files 冇清乾淨）→ 新 agent 啟動會誤執行 → 自動部署（用戶投訴）
    # → fingerprint.account != 當前 agent_config account → 跳過 + 刪除（唔執行）
    try:
        import json as _jfp
        _cfg_fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_config.json')
        _cur_acct = None
        if os.path.isfile(_cfg_fp):
            try:
                _cfg_fp_d = _jfp.load(open(_cfg_fp, 'r', encoding='utf-8'))
                _cur_acct = _cfg_fp_d.get('account')
            except Exception:
                pass
        _fp_fp = cmd_data.get('fingerprint') or {}
        _cmd_acct = _fp_fp.get('account') if isinstance(_fp_fp, dict) else None
        if _cur_acct and _cmd_acct and _cmd_acct != _cur_acct:
            print(f"   ⛔ [WATCHER] deploy_cmd 屬於 account {_cmd_acct}（當前本機係 {_cur_acct}）— 舊殘留 — 跳過 + 刪除")
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass
            return
    except Exception:
        pass

    # 🚨 2026-08-31 FIX（#152）：auto_attach running 檢查**喺刪 deploy_cmd before**
    # before：讀完immediately刪 cmd → 偵測到 running → return → cmd 冇咗 + 冇人排隊 → deploy卡死（Mean_Reversion 案例）
    # now：running → 唔刪 cmd（留返）→ return → watcher 下次 poll 再試（deploy_cmd 仲喺度）
    if is_auto_attach_running():
        print(f"   ⚠️ auto_attach.py already running — 保留 deploy_cmd 等下次 poll（唔刪 — #152 FIX）")
        deploy_notify.hide()
        sys.stdout.flush()
        return  # deploy_cmd 保留 — watcher 下次 poll 會再處理

    # 🚨 2026-08-10：確認冇 auto_attach running 先刪 deploy_cmd（防interrupted殘留 — 重複處理）
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"   🗑️ 已刪 command file（處理前 — 防interrupted殘留）: {os.path.basename(filepath)}")
    except Exception:
        pass
    
    # === 通知：Web log + 本地視窗 ===
    print(f"🤖 AI 正在deploy {ea_name} 到 MT5，請勿使用滑鼠及鍵盤...")
    sys.stdout.flush()
    
    # 1. 通知 Server → Dashboard log 顯示
    try:
        url = f"{get_server_url()}/api/watcher-report"
        requests.post(url, json={
            'agent_id': AGENT_ID,
            'ea_name': ea_name,
            'status': 'info',
            'message': f'🤖 AI startdeploy {ea_name} → MT5，請勿操作PC...'
        }, timeout=3)
    except:
        pass
    
    # 2. 顯示本地通知視窗（AI 控制中）
    deploy_notify.show()
    
    # 3. 檢查有冇其他 auto_attach 已經行緊（防止重複）
    if is_auto_attach_running():
        print(f"   ⚠️ auto_attach.py already running, queuing {ea_name}")
        deploy_notify.hide()
        return  # 等下次 poll 再試
    
    # 寫 lock file
    try:
        with open(AUTO_ATTACH_LOCK, 'w') as f:
            f.write(str(os.getpid()))
    except:
        pass
    
    try:
        # 🚨 2026-08-27 FIX（user要求方案二）：deploy前收返已掛嘅 EA（防止「愈deploy愈多 chart」）
        # 檢查 EA 心跳（state_<EA>.json 新鮮 = 已經running on chart）→ 有就 auto_attach --remove 收返
        _ea_ck = cmd_data.get('ea_name', '')
        _hb_ck = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files', f'state_{_ea_ck}.json')
        _already_running = False
        try:
            if os.path.isfile(_hb_ck):
                _hb_age = time.time() - os.path.getmtime(_hb_ck)
                if _hb_age < 120:  # 2 分鐘內更新 = running緊
                    _already_running = True
        except Exception:
            pass
        if _already_running:
            print(f"🔁 [WATCHER] {_ea_ck} 已經running on（心跳新鮮）→ 先收返舊 chart 再deploy（防累積）")
            sys.stdout.flush()
            try:
                _rm_cmd = [_PY_EXE, '-u', AUTO_ATTACH_SCRIPT, '--remove', '--ea', _ea_ck]
                _rm_res = subprocess.run(_rm_cmd, capture_output=True, text=True, timeout=180, encoding='utf-8', errors='replace')
                print(f"   ✅ 收返 {_ea_ck} done（returncode={_rm_res.returncode}）")
                sys.stdout.flush()
            except Exception as _e_rm:
                print(f"   ⚠️ 收返 {_ea_ck} failed（繼續deploy）: {_e_rm}")
                sys.stdout.flush()
        # Run auto_attach
        success = run_auto_attach(cmd_data)
    finally:
        # 3. 無論successfailed，都關閉通知視窗 + 清除 lock
        deploy_notify.hide()
        try:
            if os.path.exists(AUTO_ATTACH_LOCK):
                os.remove(AUTO_ATTACH_LOCK)
        except:
            pass
        # 🚨 2026-08：刪 deploy_cmd 搬入 finally（防 Tcl crash 漏刪 — 重複處理卡死）
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"   🗑️ Deleted command file: {os.path.basename(filepath)}")
        except Exception:
            pass
    
    # Report to server
    try:
        report_to_server(ea_name, success, 
                         f"{ea_name} {'attached ✅' if success else 'attach failed ❌'}")
    except Exception:
        pass
    
    # Brief pause before next command
    time.sleep(2)
    sys.stdout.flush()

# ─── Experts dir監控 ───

MT5_EXPERTS_DIR = os.path.join(os.environ.get('APPDATA', ''),
                               'MetaQuotes', 'Terminal',
                               'D0E8209F77C8CF37AD8BF550E51FF075', 'MQL5', 'Experts')
REFRESH_NAV_SCRIPT = os.path.join(os.path.dirname(__file__), 'refresh_navigator.py')
_last_experts_snapshot = None
_last_refresh_time = 0
_refresh_cooldown = 300  # 秒 — 防連環觸發（2026-08-28：3 秒太短 — refresh Navigator 會令 MT5 touch .mq5 → 又偵測變化 → 無限循環 right click；改 60 秒俾 MT5 穩定；2026-09-01：改 300 秒 — 冇操作都唔好成日 refresh）


def get_experts_snapshot():
    """攞 Experts dirfile清單（name + size + mtime）做 fingerprint
    ⚠️ 2026-08：只掃根dir — 唔掃 MT5 內建 folder（Free Robots/Examples 等樣本）"""
    try:
        if not os.path.isdir(MT5_EXPERTS_DIR):
            return None
        snap = {}
        scan_dirs = [MT5_EXPERTS_DIR]
        for scan_dir in scan_dirs:
            if not os.path.isdir(scan_dir):
                continue
            for f in os.listdir(scan_dir):
                if f.endswith(('.mq5', '.ex5')):
                    p = os.path.join(scan_dir, f)
                    try:
                        st = os.stat(p)
                        rel = os.path.relpath(p, MT5_EXPERTS_DIR).replace('\\', '/')
                        snap[rel] = (st.st_size, int(st.st_mtime))
                    except Exception:
                        continue
        return snap
    except Exception:
        return None


# 最近網頁操作記錄（base -> timestamp）— 網頁安裝/delete會產生多個file變化（.mq5 + .ex5），
# 用 60 秒窗口令後續變化都計做同一來源
_web_action_window = {}


def _purge_config(ea_name):
    """PC（MT5）delete EA 後，自動remove配對 config → 配對庫immediately消失"""
    try:
        import urllib.request as _ur
        agent_id = os.environ.get('AGENT_ID', 'DEV00001')
        url = f"{SERVER_URL}/api/ea-config/{ea_name}/purge?agent_id={agent_id}"
        req = _ur.Request(url, method='POST')
        with _ur.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if data.get('success'):
            print(f"🗑️ [WATCHER] 已自動remove {ea_name} 配對（PCdelete）")
        else:
            print(f"   ⚠️ purge config failed: {data.get('error')}")
    except Exception as e:
        print(f"   ⚠️ purge config failed: {e}")
    sys.stdout.flush()


def _notify_ea_change(change_type, ea_name):
    """寫 EA 變化通知去 server/static/detector/notifications.json（Dashboard read顯示 toast）
    同時write持久化 activity log（server/activity_log.jsonl）
    change_type: 'added' | 'deleted' | 'modified'
    來源分辨：server 寫 web_add_<name>.flag / web_delete_<name>.flag → 網頁操作；
              flag 消費後 60 秒內嘅變化（例如 .ex5 compile 產物）都計網頁；
              冇 flag → PC（MT5）直接操作
    """
    global _web_action_window
    try:
        notify_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), '..', 'server', 'static', 'detector', 'notifications.json'))
        os.makedirs(os.path.dirname(notify_path), exist_ok=True)

        # 分辨來源：網頁操作（server 寫咗 flag）vs PC直接操作
        common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
        source = 'PC'
        now = time.time()

        if change_type in ('deleted', 'added'):
            flag_name = 'web_delete' if change_type == 'deleted' else 'web_add'
            flag = os.path.join(common_files, f'{flag_name}_{ea_name}.flag')
            if os.path.exists(flag):
                source = '網頁'
                try:
                    os.remove(flag)  # 消費 flag
                except Exception:
                    pass

        # 統一去重窗口：同一 base + 同 type 60 秒內只出一次通知
        # （網頁安裝 .mq5 + .ex5 兩次 added；PCdelete .mq5 + .ex5 兩次 deleted）
        win_key = f'{ea_name}|{change_type}'
        last = _web_action_window.get(win_key)
        if last is not None and now - last < 60:
            print(f"🔔 [WATCHER]（{ea_name} {change_type} 後續變化 — 窗口內已通知過，skip）")
            sys.stdout.flush()
            return  # 唔重複出通知
        _web_action_window[win_key] = now

        # message 純文字（0 emoji — 前端 toast 用 Lucide icon 顯示類型）+ 講明來源（書面語）
        if change_type == 'added':
            msg = f'{ea_name} 已於{source}新增至 MT5'
        elif change_type == 'deleted':
            msg = f'{ea_name} 已於{source}delete'
            # PCdelete → 自動remove配對 config（配對庫immediately消失）
            # 🚨 2026-08-27 FIX：deploy/編譯流程會短暫刪 .ex5（metaeditor 重編譯 — 先刪舊再寫新）
            # → flag 可能已消費（added 時）→ deleted 冇 flag → 誤判PCdelete → purge 錯配對
            # → 三重檢查先 purge：①冇 web_add flag ②config 冇 EA（真係delete — 有 EA = deploy中）
            _flag_purge_check = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files', f'web_add_{ea_name}.flag')
            _deploying = os.path.isfile(_flag_purge_check)
            # check config 有冇 EA（server 端 — 有 EA = 唔係真delete）
            _cfg_has_ea = False
            try:
                import urllib.request as _ur2
                _url2 = f"{SERVER_URL}/api/ea-config?t={int(time.time()*1000)}"
                with _ur2.urlopen(_url2, timeout=8) as _r2:
                    _d2 = json.loads(_r2.read().decode('utf-8'))
                # 🚨 2026-08-28 FIX：check agent_eas（配對庫名單 — 有 EA = 唔係真delete）
                # before check mappings（deploy咗先有）→ deploy中途（未done）mappings 冇 → 誤判delete → purge 打斷deploy
                _cfg_has_ea = ea_name in _d2.get('agent_eas', []) or ea_name in _d2.get('mappings', {})
            except Exception:
                pass
            if source == 'PC' and not _deploying and not _cfg_has_ea:
                _purge_config(ea_name)
            elif source == 'PC' and (_deploying or _cfg_has_ea):
                print(f"🔔 [WATCHER] {ea_name} deleted 但deploy中/有 config（flag={_deploying} cfg={_cfg_has_ea}）→ 唔 purge（防誤判）")
        else:
            msg = f'{ea_name} 已更新'
        notif = {
            'id': f'{int(time.time())}_{ea_name}_{change_type}',
            'type': change_type,
            'ea': ea_name,
            'source': source,
            'time': time.time(),
            'message': msg,
        }

        # 讀現有 + append + 保留最近 20 條
        existing = []
        try:
            with open(notify_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                existing = data.get('notifications', [])
        except Exception:
            pass
        existing.insert(0, notif)
        existing = existing[:20]

        with open(notify_path, 'w', encoding='utf-8') as f:
            json.dump({'notifications': existing}, f, ensure_ascii=False)
        print(f"🔔 [WATCHER] 通知已寫: {notif['message']}")
        sys.stdout.flush()

        # 同時write持久化 activity log（append JSONL，原子write）
        _append_activity_log(notif)
    except Exception as e:
        print(f"   ⚠️ 寫通知failed: {e}")


def _append_activity_log(notif):
    """append 一行 JSONL 去 server/activity_log.jsonl（持久保存，server /api/activity read）"""
    try:
        log_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), '..', 'server', 'activity_log.jsonl'))
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        entry = {
            'time': notif.get('time', time.time()),
            'action': notif.get('action', notif.get('type', 'unknown')),  # 🚨 2026-08-19 FIX：caller 用 'action' key（deploy_result 等）— before只讀 'type' → deploy_result 寫成 unknown → 前端等唔到 → modal 卡
            'ea': notif.get('ea', ''),
            'message': notif.get('message', ''),
            'source': 'watcher',
        }
        line = json.dumps(entry, ensure_ascii=False) + '\n'
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(line)
        print(f"📜 [WATCHER] activity log 已寫: {entry['message']}")
        sys.stdout.flush()
    except Exception as e:
        print(f"   ⚠️ 寫 activity log failed: {e}")


_refresh_lock = threading.Lock()  # 同一時間只允許一個 refresh 跑（pyautogui 搶滑鼠會互卡）
_refresh_queue = queue.Queue(maxsize=1)  # single-slot queue：有變化就觸發，重複變化 coalesce


def _refresh_worker_loop():
    """永遠行緊嘅 refresh worker：queue 有訊號 → refresh 直到 queue 清空（coalesce）"""
    while True:
        try:
            _refresh_queue.get()  # block 等第一個訊號
        except Exception:
            break
        # 處理所有 pending：refresh 一次 → 再檢查 queue 有冇新訊號 → 有就再 refresh
        # 🚨 2026-08-27 FIX：加最大次數（3 次）— 防止無限 refresh 循環（卡死主 loop → deploy poll 餓死）
        _refresh_max = 3
        _refresh_done = 0
        while _refresh_done < _refresh_max:
            _refresh_done += 1
            # 直接喺 watcher process 入面 call（唔 spawn subprocess — subprocess 環境
            # 冇 desktop access 會令 pyautogui 卡死 timeout）
            try:
                import importlib.util as _ilu
                # 同 compile 共用互斥鎖 — 兩個 pywinauto 唔可以同時操作 GUI（會搶滑鼠打架）
                with _refresh_lock:
                    _spec = _ilu.spec_from_file_location("refresh_navigator", REFRESH_NAV_SCRIPT)
                    _mod = _ilu.module_from_spec(_spec)
                    _spec.loader.exec_module(_mod)
                    _ok = _mod.refresh_navigator()
                print(f"   {'✅' if _ok else '⚠️'} Navigator refreshed (in-process)")
            except Exception as e:
                print(f"   ⚠️ Navigator refresh failed: {e}")
            sys.stdout.flush()
            # 有 pending 訊號 → 再 refresh 一次（coalesce 期間嘅所有變化）— 但最多 3 次
            try:
                _refresh_queue.get_nowait()
                if _refresh_done < _refresh_max:
                    print("   🔄 有 pending 變化，繼續 refresh...")
                    sys.stdout.flush()
                    continue
                else:
                    print("   ⚠️ refresh 循環超過上限（3 次）— stop（防卡死）")
                    sys.stdout.flush()
                    break
            except Exception:
                break  # queue 空 — done
        time.sleep(2)  # 防連環觸發


def _notify_refresh_needed():
    """dir變化 → 觸發 refresh（queue 已滿 = 已有 pending，唔使再加）"""
    try:
        _refresh_queue.put_nowait(1)
    except Exception:
        pass  # queue 已滿 — 已有 pending，coalesce


def check_experts_changes():
    """偵測 Experts dir變化（EA 新增/delete/修改）→ 通知 + activity log + 自動 refresh Navigator"""
    global _last_experts_snapshot, _last_refresh_time

    snap = get_experts_snapshot()
    if snap is None:
        return
    if _last_experts_snapshot is None:
        _last_experts_snapshot = snap
        return

    # 比較有冇變化
    if snap != _last_experts_snapshot:
        old_snap = _last_experts_snapshot
        _last_experts_snapshot = snap
        now = time.time()

        # 搵出新增/delete嘅file名（喺 cooldown check before，通知一定要出）
        changed = []
        all_keys = set(snap) | set(old_snap)
        for k in all_keys:
            if snap.get(k) != old_snap.get(k):
                changed.append(k)

        # 分類：新增（before冇now有）/ delete（before有now冇）
        # 通知 + activity log 永遠寫（唔受 AI 控制守衛影響 — userdelete EA 要即時知）
        for k in changed:
            base = k.rsplit('.', 1)[0] if '.' in k else k
            if k in snap and k not in old_snap:
                _notify_ea_change('added', base)
            elif k not in snap and k in old_snap:
                _notify_ea_change('deleted', base)
            else:
                _notify_ea_change('modified', base)

        # [ALERT] 2026-09-03 FIX（配對後 Navigator 唔顯示新 EA — 用戶實錘）：
        # cooldown 300 秒擋咗「新增 .ex5」嘅 refresh（compile 期間多次 dir 變化 → 第一次 refresh 太早 →
        # 之後變化俾 cooldown 擋 → 最後 .ex5 生成冇 refresh → MT5 唔顯示）
        # → 「新增檔案」（真係有新 EA）唔受 cooldown 限制（一定要 refresh — 唔可以漏）
        # → 只有「修改」（refresh 引起嘅 touch）先受 cooldown 擋（防無限循環）
        _has_new_file = any(k in snap and k not in old_snap for k in changed)
        if now - _last_refresh_time < _refresh_cooldown and not _has_new_file:
            return  # cooldown 內 + 冇新檔案 → 唔重複 refresh（防無限循環）
        if not _has_new_file:
            _last_refresh_time = now

        # AI 控制守衛：如果已經有 AI 操控緊（auto_attach 等），唔好同時 refresh 搶 MT5
        # （淨係擋 refresh，唔擋通知/activity log）
        try:
            cg_lock = os.path.join(os.path.dirname(__file__), '.ai_control.lock')
            if os.path.exists(cg_lock):
                print(f"   ⚠️ AI 控制緊（auto_attach），skip Navigator refresh（通知已寫）")
                sys.stdout.flush()
                return
        except:
            pass

        print(f"🔄 [WATCHER] Experts dir變化: {', '.join(changed[:5]) or '?'} — 自動 refresh Navigator")
        sys.stdout.flush()
        # 觸發 refresh（single worker queue 處理，coalesce 唔會漏）
        _notify_refresh_needed()


def find_compile_commands():
    """搵 compile_cmd_*.json（server write，俾 watcher 用 desktop access compile）"""
    common_files = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
    pattern = os.path.join(common_files, 'compile_cmd_*.json')
    return sorted(glob.glob(pattern), key=os.path.getmtime)


def process_compile_cmd(fp):
    """處理 compile 指令：用 MetaEditor GUI compile .mq5 → .ex5（watcher 有 desktop access）
    ⚠️ MetaEditor CLI `/compile` 喺 background 環境唔 work（靜默failed）
    ⚠️ GUI 方式（開 file → F7）先success — 用 pywinauto 操作
    ⚠️ failed自動重試（最多 3 次）— compile_cmd 保留 + retries 計數
    ⚠️ 緊急stop（ControlAborted）→ 唔重試，直接放棄
    """
    try:
        from control_guard import ControlAborted as _CGAbort
    except ImportError:
        _CGAbort = Exception
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        mq5_path = data.get('mq5_path')
        ex5_path = data.get('ex5_path')
        base = data.get('base', os.path.splitext(os.path.basename(mq5_path or ''))[0])
        retries = data.get('retries', 0)

        if not mq5_path or not os.path.isfile(mq5_path):
            print(f"   ⚠️ compile cmd: {mq5_path} not exist")
            os.remove(fp)
            return

        # 已 compile 且新過源碼 → skip
        if os.path.exists(ex5_path) and os.path.getmtime(ex5_path) > os.path.getmtime(mq5_path):
            print(f"   ⏩ {base}.ex5 已係最新，skip compile")
            os.remove(fp)
            return

        print(f"   🔨 Compiling {base}.mq5 → .ex5（GUI 方式）{'（重試 ' + str(retries + 1) + '/3）' if retries > 0 else ''}...")
        sys.stdout.flush()
        # 🚨 2026-08-12 FIX：編譯 = 配對流程嘅一步（唔覆寫 install-local 步驟 — 改為更新「編譯」步驟 doing）
        try:
            import json as _jc
            _adir = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(_adir, '.ai_control.show'), 'w', encoding='utf-8') as _f:
                _f.write(f'配對 {base}')
            _sf = os.path.join(_adir, '.ai_control.steps')
            _cur = []
            try:
                if os.path.isfile(_sf):
                    _cur = _jc.load(open(_sf, 'r', encoding='utf-8'))
                    if not isinstance(_cur, list):
                        _cur = []
            except Exception:
                _cur = []
            # 對應 install-local 嘅步驟（冇就 append 新步驟）
            def _upd(_list, _text, _status):
                for _s in _list:
                    if isinstance(_s, dict) and _s.get('text') == _text:
                        _s['status'] = _status
                        return
                _list.append({'text': _text, 'status': _status})
            if not _cur:
                # 冇現有 steps（直接 compile — 唔經 install-local）→ 建完整流程
                _cur = [{'text': f'start配對 {base}', 'status': 'done'},
                        {'text': '複製file至local（Experts 根）', 'status': 'done'},
                        {'text': f'編譯 {base}.mq5 → .ex5', 'status': 'doing'},
                        {'text': 'done配對', 'status': 'pending'}]
            else:
                _upd(_cur, f'編譯 {base}.mq5 → .ex5', 'doing')
            with open(_sf, 'w', encoding='utf-8') as _f2:
                _jc.dump(_cur, _f2, ensure_ascii=False)
        except Exception:
            pass
        # ⚠️ 控制層注入（網頁操控 EA — CONTROL_LAYER_DESIGN.md）：
        # compile 前自動注入控制層（tick 檢查 ctrl_ 檔 + 心跳寫 state_ 檔）
        # failed（冇 OnTick）→ 用原版 compile（唔阻塞deploy）
        try:
            from inject_control_layer import inject_control_layer as _inject
            _inject(mq5_path)
        except Exception as _ie:
            print(f"   ⚠️ [注入器] 整合呼叫failed: {_ie}")
        # 同 refresh_navigator 共用互斥鎖 — 兩個 pywinauto 唔可以同時操作 GUI（會搶滑鼠打架）
        import threading as _th
        try:
            with _refresh_lock:
                ok = _compile_via_gui(mq5_path, ex5_path)
        except ControlAborted:
            # 緊急stop — 唔可以重試，直接放棄 + 刪 compile cmd（真正stop）
            print("   🛑 緊急stop — 放棄 compile，唔重試")
            try:
                os.remove(fp)
            except Exception:
                pass
            return
        except _CGAbort:
            print("   🛑 緊急stop — 放棄 compile，唔重試")
            try:
                os.remove(fp)
            except Exception:
                pass
            return
        if ok:
            print(f"   ✅ Compiled: {base}.ex5 ({os.path.getsize(ex5_path)} bytes)")
            # 🚨 2026-08-12 FIX：編譯done → 「編譯」done + 「done配對」done（累積更新 — 唔覆蓋）
            try:
                import json as _jc2
                _sf2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
                _old2 = []
                try:
                    if os.path.isfile(_sf2):
                        _old2 = _jc2.load(open(_sf2, 'r', encoding='utf-8'))
                        if not isinstance(_old2, list):
                            _old2 = []
                except Exception:
                    _old2 = []
                for _s in _old2:
                    if isinstance(_s, dict):
                        _t = _s.get('text', '')
                        if '編譯' in _t or _t == 'done配對':
                            _s['status'] = 'done'
                with open(_sf2, 'w', encoding='utf-8') as _f:
                    _jc2.dump(_old2, _f, ensure_ascii=False)
                # 🚨 2026-08-28 FIX（網頁版warning視窗冇同步 — user對比 stable-v0.10.91）：watcher 只更新自己dir（TradotcomAgent）
                # → server 讀開發dir（agent/.ai_control.steps — 網頁版）永遠 pending → 同步埋開發dir
                try:
                    import os as _os2
                    _cand2 = [
                        _os2.path.join(_os2.environ.get('USERPROFILE', ''), 'Desktop', 'mt5-cloud', 'agent'),
                        _os2.path.join(_os2.environ.get('USERPROFILE', ''), 'Desktop', 'mt5-cloud-stable', 'agent'),
                    ]
                    for _cd2 in _cand2:
                        if _os2.path.isdir(_cd2):
                            with open(_os2.path.join(_cd2, '.ai_control.steps'), 'w', encoding='utf-8') as _f3:
                                _jc2.dump(_old2, _f3, ensure_ascii=False)
                            break
                except Exception:
                    pass
            except Exception:
                pass
            os.remove(fp)  # success → 清理指令
            # immediately queue refresh（唔等 3 秒 poll）— compile 生成 .ex5 後 Navigator 要immediately更新，
            # 令 compile → refresh 動作連續，warning視窗唔會「彈出 → 關 → 又彈出」（Bug #70）
            try:
                _notify_refresh_needed()
            except Exception:
                pass
        else:
            # 🚨 2026-08-10：failed → 唔自動重試（user要求 — failed應該停 + 彈視窗「編譯failed」+ 確定/緊急stop — user決定）
            print(f"   ❌ Compile failed: {base}.ex5 未生成（stop重試 — 檢查源碼或手動重試）")
            try:
                import json as _jcf
                _adir_cf = os.path.dirname(os.path.abspath(__file__))
                _sf_cf = os.path.join(_adir_cf, '.ai_control.steps')
                _old_cf = []
                try:
                    if os.path.isfile(_sf_cf):
                        _old_cf = _jcf.load(open(_sf_cf, 'r', encoding='utf-8'))
                        if not isinstance(_old_cf, list):
                            _old_cf = []
                except Exception:
                    _old_cf = []
                # 更新「編譯」步驟 → failed
                for _s in _old_cf:
                    if isinstance(_s, dict) and '編譯' in _s.get('text', ''):
                        _s['status'] = 'done'
                if not any('編譯failed' in (s.get('text', '') if isinstance(s, dict) else '') for s in _old_cf):
                    _old_cf.append({'text': '編譯failed', 'status': 'done'})
                with open(_sf_cf, 'w', encoding='utf-8') as _f:
                    _jcf.dump(_old_cf, _f, ensure_ascii=False)
            except Exception:
                pass
            os.remove(fp)  # failed → 清理（唔重試 — user手動決定）
        sys.stdout.flush()
    except Exception as e:
        print(f"   ⚠️ compile cmd 處理failed: {e}")
        try:
            os.remove(fp)
        except:
            pass


def _compile_via_gui(mq5_path, ex5_path, max_retries=3):
    """用 MetaEditor GUI compile（開 file → F7）— CLI /compile 喺 background 唔 work
    用 control_guard 彈warning視窗（GUI 操作緊要話俾user知）
    """
    import subprocess as _sp
    import time as _t
    from pywinauto import Application
    from pywinauto.keyboard import send_keys

    # AI 控制守衛 — 彈warning視窗 + 支援緊急stop
    try:
        from control_guard import acquire, check_abort, release, ControlAborted
        acquire(f"編譯 {os.path.splitext(os.path.basename(mq5_path))[0]}")
    except ImportError:
        check_abort = lambda: None
        release = lambda: None
        ControlAborted = Exception
        acquire = lambda *a, **k: None

    try:
        metaeditor = r"C:\Program Files\MetaTrader 5\metaeditor64.exe"
        exp_dir = os.path.dirname(mq5_path)

        # 🚨 2026-08-18 FIX（user要求：OpenChart 配對 compile failed根治）：先試 CLI /compile
        # （GUI F7 自動化間歇性failed — CLI /compile 100% 可靠 — metaeditor64 /compile:file /log:log）
        # success（.ex5 生成）→ immediately返 True，唔使 GUI
        try:
            _log_path = os.path.join(exp_dir, f'_cli_compile_{os.path.splitext(os.path.basename(mq5_path))[0]}.log')
            if os.path.exists(_log_path):
                try: os.remove(_log_path)
                except Exception: pass
            _p_cli = _sp.Popen([metaeditor, f'/compile:{mq5_path}', f'/log:{_log_path}'], shell=False)
            _cli_ok = False
            for _cc in range(10):
                _t.sleep(2)
                if _p_cli.poll() is not None:
                    break
                if os.path.exists(ex5_path):
                    _cli_ok = True
                    break
            if os.path.exists(ex5_path) and os.path.getsize(ex5_path) > 0:
                _cli_ok = True
            if _cli_ok:
                print(f"   ✅ CLI Compiled: {os.path.basename(ex5_path)} ({os.path.getsize(ex5_path)} bytes)")
                # 🚨 2026-08-28 FIX：CLI compile 完都immediately關 MetaEditor（CLI /compile 都用 metaeditor64.exe — 會留低 process → 監察 Experts → 彈「外部修改」dialog）
                try:
                    _sp.run('taskkill /f /im metaeditor64.exe', shell=True, capture_output=True, timeout=10)
                except Exception:
                    pass
                return True
            else:
                print("   ⚠️ CLI compile 未確認，fallback 去 GUI...")
        except Exception as _ce:
            print(f"   ⚠️ CLI compile failed（fallback GUI）: {_ce}")

        # 記錄 MetaEditor before係咪已經開住（如果係我哋開嘅 → 用完自動關閉）
        out_before = _sp.check_output(
                    'tasklist /FI "IMAGENAME eq metaeditor64.exe" /FO CSV /NH',
                    shell=True, timeout=5).decode(errors='ignore')
        was_running = 'MetaEditor64.exe' in out_before

        for attempt in range(max_retries):
            check_abort()  # 每步檢查緊急stop
            try:
                # 確保 MetaEditor 開住（唔開就開）
                out = _sp.check_output(
                    'tasklist /FI "IMAGENAME eq metaeditor64.exe" /FO CSV /NH',
                    shell=True, timeout=5).decode(errors='ignore')
                pid = None
                for line in out.splitlines():
                    parts = [p.strip().strip('"') for p in line.split(',')]
                    if len(parts) >= 2 and parts[0] == 'MetaEditor64.exe' and parts[1].isdigit():
                        pid = int(parts[1])
                        break
                if not pid:
                    # 🚨 2026-08-27 FIX：唔好開 metaeditor GUI（佢監察 Experts dir → 自動重編譯 → 刪舊 .ex5 但寫唔返 → deploy failed）
                    # → CLI /compile 已經可靠（line 849）— 唔需要 GUI fallback
                    print("   ⚠️ MetaEditor 未開 — 用 CLI compile（唔開 GUI — 避免佢搞亂 .ex5）")
                    _t.sleep(1)

                app = Application(backend='win32').connect(process=pid) if pid else None

                # 🚨 2026-08-27 FIX：metaeditor 未開（CLI compile 已處理）→ 跳過 GUI 段（唔 crash）
                if app is None:
                    print("   ℹ️ MetaEditor 未開 — 跳過 GUI 編譯段（CLI 已處理）")
                    return True

                # 關閉可能嘅舊 dialog（「外部修改」提示 → click 是；其他 dialog → close）
                # ⚠️ 唔可以用 w.close() 對「外部修改」dialog — 會卡死（timed out）→ 一定要 click 是
                try:
                    for w in app.windows():
                        if w.class_name() == '#32770':
                            clicked = False
                            for c in w.children():
                                try:
                                    if '是' in c.window_text() and c.class_name() == 'Button':
                                        c.click()
                                        clicked = True
                                        _t.sleep(1)
                                        break
                                except:
                                    pass
                            if not clicked:
                                try:
                                    w.close()
                                except:
                                    pass
                                _t.sleep(1)
                except:
                    pass

                win = app.window(class_name='MetaQuotes::MetaEditor::5.00')
                # 固定 MetaEditor 位置 + 大小（每次彈出都鎖定 — 唔會漂移）
                try:
                    import ctypes as _ct
                    from ctypes import wintypes as _wt
                    _ct.windll.user32.SetWindowPos(_ct.c_void_p(int(win.element_info.handle)), 0,
                                                   300, 150, 900, 700, 0x0004 | 0x0040)
                    _t.sleep(0.5)
                except Exception:
                    pass
                win.set_focus()
                _t.sleep(0.8)

                # 確保 MetaEditor 係 active window（warning視窗可能搶 focus）→ 唔係就再 focus
                try:
                    from pywinauto import Desktop as _Desktop
                    _active = _Desktop(backend='win32').window(active_only=True)
                    if _active.class_name() != 'MetaQuotes::MetaEditor::5.00':
                        win.set_focus()
                        _t.sleep(0.8)
                except Exception:
                    pass

                # Ctrl+O 開 file dialog
                send_keys('^o')
                _t.sleep(1.5)
                dlg = None
                for w in app.windows():
                    if w.class_name() == '#32770' and '打開' in w.window_text():
                        dlg = w
                        break
                if dlg is None:
                    print(f"   ⚠️ not found打開 dialog (attempt {attempt+1})")
                    continue

                # 喺 filename edit 輸入path
                edits = dlg.children(class_name='Edit')
                if len(edits) >= 2:
                    edits[0].set_text(mq5_path)
                elif len(edits) == 1:
                    edits[0].set_text(mq5_path)
                _t.sleep(0.5)
                # 按「開啟」
                try:
                    dlg.child_window(class_name='Button', title='開啟(&O)').click()
                except:
                    try:
                        dlg.child_window(class_name='Button', title_re='.*開.*').click()
                    except:
                        send_keys('{ENTER}')
                _t.sleep(3)
                check_abort()

                # 開 file after可能彈「外部修改」dialog（.mq5 被外部改過）→ immediately click 是
                # ⚠️ 一定要喺 F7 before處理 — 唔係 F7 會落咗去 dialog（compile failed）
                try:
                    for w in app.windows():
                        if w.class_name() == '#32770':
                            for c in w.children():
                                try:
                                    if '是' in c.window_text() and c.class_name() == 'Button':
                                        c.click()
                                        _t.sleep(2)
                                        print("   ✅ 已處理「外部修改」dialog（click 是）")
                                        break
                                except:
                                    pass
                except:
                    pass

                # F7 compile
                send_keys('{F7}')
                # 🚨 2026-08-12 FIX：編譯wait期間每 2 秒 check_abort（緊急stop即時中止 — before等 8 秒 block → 冇反應）
                _compile_done = False
                for _cc in range(8):  # 最多 16 秒（8 次 × 2 秒）
                    check_abort()  # 🚨 緊急stop → immediately raise
                    _t.sleep(2)
                    if os.path.exists(ex5_path):
                        _compile_done = True
                        break

                if _compile_done or os.path.exists(ex5_path):
                    return True

                # 可能仲有「外部修改」dialog → 處理後再試
                try:
                    for w in app.windows():
                        if w.class_name() == '#32770':
                            for c in w.children():
                                try:
                                    if '是' in c.window_text() and c.class_name() == 'Button':
                                        c.click()
                                        _t.sleep(2)
                                except:
                                    pass
                except:
                    pass
            except Exception as e:
                print(f"   ⚠️ GUI compile attempt {attempt+1} error: {e}")
                _t.sleep(2)
        return False
    except ControlAborted:
        print("🚨 compile 被user緊急stop！")
        raise  # 傳俾 caller — 唔當普通failed重試（緊急stop要真正stop後續動作）
    finally:
        # 如果 MetaEditor 係我哋開嘅 → 自動關閉（唔儲存 — 我哋冇改過源碼）
        # 如果係user原本開住嘅 → 唔好閂（尊重user）
        try:
            if not was_running:
                _t.sleep(1)
                out_now = _sp.check_output(
                    'tasklist /FI "IMAGENAME eq metaeditor64.exe" /FO CSV /NH',
                    shell=True, timeout=5).decode(errors='ignore')
                if 'MetaEditor64.exe' in out_now:
                    print("   🗑️ MetaEditor 係自動開嘅，用完自動關閉...")
                    try:
                        from pywinauto import Application as _App
                        out_pid = _sp.check_output(
                            'tasklist /FI "IMAGENAME eq metaeditor64.exe" /FO CSV /NH',
                            shell=True, timeout=5).decode(errors='ignore')
                        for line in out_pid.splitlines():
                            parts = [p.strip().strip('"') for p in line.split(',')]
                            if len(parts) >= 2 and parts[0] == 'MetaEditor64.exe' and parts[1].isdigit():
                                me_pid = int(parts[1])
                                # timeout=5 防 blocking 卡死（connect 卡住 → 緊急stop都冇反應）
                                _App(backend='win32').connect(process=me_pid, timeout=5).window(
                                    class_name='MetaQuotes::MetaEditor::5.00').close()
                                break
                    except Exception:
                        # fallback：直接 kill（冇改源碼，唔使儲存）
                        _sp.run('taskkill /f /im metaeditor64.exe', shell=True)
                    _t.sleep(2)
                    print("   ✅ MetaEditor 已自動關閉")
        except Exception:
            pass
        try:
            release()  # 關warning視窗 + 清 lock
        except Exception:
            pass


# ─── Main Loop ───

_deploy_queue = queue.Queue(maxsize=50)  # deploy 指令 queue（single worker 順序處理）— 🚨 2026-08-10：10→50（防滿阻塞）


def _deploy_worker_loop():
    """永遠行緊嘅 deploy worker：攞指令 → process_deploy（唔 block 主 loop）"""
    _last_ea_time = {}  # 🚨 2026-08-31 FIX（#152 雙保險重複）：同一 EA 60 秒內只處理一次（emit+poll 雙 cmd → 兩個 file → 雙重deploy）
    while True:
        try:
            fp = _deploy_queue.get()
        except Exception:
            break
        try:
            # 讀 cmd 攞 ea_name（dedupe 用）
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    _dd_fp = json.load(f)
                _ea_fp = _dd_fp.get('ea_name', '')
                _now_fp = time.time()
                if _ea_fp and _now_fp - _last_ea_time.get(_ea_fp, 0) < 60:
                    print(f"   ⏭️ [WATCHER] {_ea_fp} 60 秒內已deploy過（#152 dedupe）— 跳過重複 cmd: {os.path.basename(fp)}")
                    sys.stdout.flush()
                    # 刪重複 cmd（唔留殘留）
                    try:
                        if os.path.exists(fp):
                            os.remove(fp)
                    except Exception:
                        pass
                    continue
                _last_ea_time[_ea_fp] = _now_fp
            except Exception:
                pass
            print(f"\n📥 [WATCHER] Deploy worker: {os.path.basename(fp)}")
            sys.stdout.flush()
            # 🚨 2026-08-10：處理前檢查 .ex5 exists（not exist skip + 刪 — 唔好 auto_attach failed循環）
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    _dd = json.load(f)
                _ea = _dd.get('ea_name', '')
                _exp_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
                _found = False
                for _d in os.listdir(_exp_dir):
                    _ex5 = os.path.join(_exp_dir, _d, 'MQL5', 'Experts', _ea + '.ex5')
                    if os.path.isfile(_ex5):
                        _found = True
                        break
                if not _found:
                    # 🚨 2026-08-27 FIX：.ex5 not exist（可能remove時刪咗）→ 自動 compile（metaeditor CLI）
                    # before直接 skip — userremove後再deploy同一 EA 就永遠deploy唔到
                    print(f"   ⚠️ {_ea}.ex5 not exist — 嘗試自動 compile...")
                    _compiled = False
                    try:
                        _me_dir = r'C:\Program Files\MetaTrader 5\metaeditor64.exe'
                        _mq5_p = None
                        for _d2 in os.listdir(_exp_dir):
                            _mq5p = os.path.join(_exp_dir, _d2, 'MQL5', 'Experts', _ea + '.mq5')
                            if os.path.isfile(_mq5p):
                                _mq5_p = _mq5p
                                break
                        if _mq5_p and os.path.isfile(_me_dir):
                            _log_p = os.path.join(os.path.dirname(_mq5_p), f'_cli_compile_{_ea}.log')
                            subprocess.run([_me_dir, f'/compile:{_mq5_p}', f'/log:{_log_p}'], timeout=60)
                            time.sleep(2)
                            # 🚨 2026-08-27 FIX：compile 完immediately關 MetaEditor（唔關 → 佢監察 Experts dir → 見 .mq5 變化 → 彈一堆「外部修改」dialog）
                            try:
                                subprocess.run('taskkill /f /im metaeditor64.exe', shell=True, capture_output=True, timeout=10)
                            except Exception:
                                pass
                            for _d2 in os.listdir(_exp_dir):
                                if os.path.isfile(os.path.join(_exp_dir, _d2, 'MQL5', 'Experts', _ea + '.ex5')):
                                    _compiled = True
                                    break
                    except Exception as _e_cmp:
                        print(f"   ⚠️ 自動 compile failed: {_e_cmp}")
                    if not _compiled:
                        print(f"   ⚠️ {_ea}.ex5 自動 compile 後仍然not exist（skip — 防止failed循環）")
                        try:
                            os.remove(fp)
                        except Exception:
                            pass
                        continue
                    else:
                        print(f"   ✅ 自動 compile success: {_ea}.ex5")
            except Exception:
                pass
            process_deploy(fp)
        except Exception as e:
            print(f"   ⚠️ deploy worker error: {e}")
        time.sleep(2)


def process_pause_cmd(fp):
    """真pause：處理 pause_cmd（remove圖表 EA — auto_attach --remove）
    網頁撳「pause」→ server 寫 pause_cmd → watcher 執行remove"""
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        ea_name = data.get('ea_name', '')
        action = data.get('action', 'pause')  # 🚨 2026-08-14：pause=pause / delete=delete（文字唔同 — user投訴「delete顯示pause」）
        if not ea_name:
            os.remove(fp)
            return
        # 🚨 2026-08-31 FIX（#157 剷除誤傷其他 EA — 重複 pause_cmd）：同一 EA 60 秒內只處理一次
        # （emit+poll 雙保險雙 pause_cmd → 兩個 remove 操作 → 第二個揀 chart [0]（其他 symbol）→ Ctrl+W 關錯 → 誤剷其他 EA — Multi_TimeFrame 案例）
        _now_pc = time.time()
        if _now_pc - _last_pause_time.get(ea_name, 0) < 60:
            print(f"   ⏭️ [WATCHER] {ea_name} 60 秒內已pause過（#157 dedupe）— 跳過重複 cmd: {os.path.basename(fp)}")
            sys.stdout.flush()
            try:
                if os.path.exists(fp):
                    os.remove(fp)
            except Exception:
                pass
            return
        _last_pause_time[ea_name] = _now_pc
        _act_word = 'pause' if action != 'delete' else 'delete'
        print(f"⏸️ [WATCHER] {_act_word} {ea_name}（remove圖表 EA）...")
        sys.stdout.flush()
        # 🚨 2026-08-14 FIX：pause/delete用唔同字眼（before統一「pause」— delete顯示錯）
        try:
            import json as _jp
            _adir = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(_adir, '.ai_control.show'), 'w', encoding='utf-8') as _f:
                _f.write(f'{_act_word} {ea_name}')
            _sf = os.path.join(_adir, '.ai_control.steps')
            if action == 'delete':
                # delete流程（完整delete — file+設定）
                _old = [{'text': f'startdelete {ea_name}', 'status': 'doing'},
                        {'text': '檢查圖表（是否有 EA running）', 'status': 'pending'},
                        {'text': 'remove圖表 EA（stop交易）', 'status': 'pending'},
                        {'text': 'donedelete', 'status': 'pending'}]
            else:
                # pause流程（保留配置）
                _old = [{'text': f'startpause {ea_name}', 'status': 'doing'},
                        {'text': '檢查圖表（是否有 EA running）', 'status': 'pending'},
                        {'text': 'remove圖表 EA（stop交易）', 'status': 'pending'},
                        {'text': 'donepause（配置保留 — 可隨時恢復）', 'status': 'pending'}]
            with open(_sf, 'w', encoding='utf-8') as _f2:
                _jp.dump(_old, _f2, ensure_ascii=False)
        except Exception:
            pass

        # 🚨 2026-08-12：真逐步（每步延遲 — 網頁捕到「in progress」— user要求「成個過程好似活動記錄」）
        def _prog_steps(done_texts, doing_text=None):
            """逐步更新 steps：指定 steps done + 可選下一個 doing"""
            try:
                import json as _jp3
                _sf3 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
                _st3 = []
                if os.path.isfile(_sf3):
                    _st3 = _jp3.load(open(_sf3, 'r', encoding='utf-8'))
                for _s3 in _st3:
                    if isinstance(_s3, dict) and _s3.get('text') in done_texts:
                        _s3['status'] = 'done'
                    elif isinstance(_s3, dict) and _s3.get('text') == doing_text:
                        _s3['status'] = 'doing'
                with open(_sf3, 'w', encoding='utf-8') as _f3:
                    _jp3.dump(_st3, _f3, ensure_ascii=False)
            except Exception:
                pass
            time.sleep(0.8)  # 每步停留（網頁 poll 捕到「in progress」）

        # 🚨 2026-08-12 FIX：步驟順序反映實際動作 — auto_attach --remove（remove圖表）期間顯示「remove圖表 EA in progress」（唔係「檢查圖表」）
        _prog_steps([f'startpause {ea_name}'], 'remove圖表 EA（stop交易）')
        try:
            # 🚨 2026-08-21 FIX：_PYEXE 未定義（run_auto_attach 入面先定義 — process_pause_cmd 唔同 scope）→ NameError → remove卡住
            _PYEXE = _PY_EXE
            result = subprocess.run(
                [_PYEXE, AUTO_ATTACH_SCRIPT, '--ea', ea_name, '--remove'],
                timeout=90, capture_output=True, encoding='utf-8', errors='replace',  # ⚠️ GBK 修
                cwd=os.path.dirname(AUTO_ATTACH_SCRIPT),
            )
            print(f"   Exit: {result.returncode}")
            for line in result.stdout.split('\n'):
                ls = line.strip()
                if any(kw in ls for kw in ['✅', '❌', '⚠️', 'ℹ️', 'remove', 'pause']):
                    print(f"   {ls}")
        except subprocess.TimeoutExpired:
            print(f"   ⚠️ pause {ea_name} timeout")
        # 🚨 2026-08-22 FIX（user實測「delete咗但圖表仲掛住 EA」— remove假success）：
        # before冇 check auto_attach returncode/output → removefailed都照寫「已pause」假success
        # → now check：returncode + output 有冇「✅ pause/removedone」— 冇 → 寫「removefailed」+ 通知user
        _remove_ok = False
        try:
            if 'result' in dir() and result.returncode == 0:
                _out_txt = (result.stdout or '')
                if '已pause' in _out_txt or 'remove' in _out_txt or 'done' in _out_txt or 'removesuccess' in _out_txt or '唔使remove' in _out_txt:
                    _remove_ok = True
                elif 'cannot confirm removal' in _out_txt or 'failed' in _out_txt:
                    _remove_ok = False
                else:
                    # 冇明確success/failed — 用 exit code 0 當success（但 warn）
                    _remove_ok = True
                    print(f"   ⚠️ pause {ea_name} output 冇明確success標記（exit 0 — 當success）")
        except Exception:
            _remove_ok = False
        # 🚨 2026-08-12：逐步（auto_attach done → remove done → 刪檔 doing → …）
        _prog_steps(['remove圖表 EA'], 'deletelocalfile（.mq5/.ex5）')
        # 🚨 2026-08-27 FIX：action=delete → 實際deletelocal .mq5/.ex5（user要求「remove = 完整remove」— before只刪 config + remove chart — file留低！）
        if action == 'delete' and _remove_ok:
            try:
                _exp_dir_del = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
                for _d_del in os.listdir(_exp_dir_del):
                    for _ext_del in ('.mq5', '.ex5'):
                        _fp_del = os.path.join(_exp_dir_del, _d_del, 'MQL5', 'Experts', ea_name + _ext_del)
                        if os.path.isfile(_fp_del):
                            os.remove(_fp_del)
                            print(f"   ✅ 已deletelocalfile: {os.path.basename(_fp_del)}")
            except Exception as _e_del:
                print(f"   ⚠️ deletelocalfilefailed: {_e_del}")
            sys.stdout.flush()
        _prog_steps(['deletelocalfile（.mq5/.ex5）'], '清理設定並釋放快捷鍵')
        _prog_steps(['清理設定並釋放快捷鍵'], 'donedelete')
        _prog_steps(['donedelete'])
        # 🚨 2026-08-21 FIX（user實測「removesuccess但 MT5 Navigator 仲殘留 — 要自己 refresh」）：
        # removedone → 觸發 refresh Navigator。⚠️ v0.10.38 用 _refresh_queue.put() 會疊加「Experts dir變化」觸發
        # → refresh 兩次（第二次又撳右鍵做多餘動作）→ user實測「第一次successafter第二次又撳右鍵」
        # → 唔好 put — remove刪 .mq5/.ex5 已經觸發 file-watch「Experts dir變化 → 自動 refresh Navigator」
        # 通知 server
        try:
            if _remove_ok:
                _append_activity_log({'time': time.time(), 'action': 'pause_result', 'ea': ea_name,
                                      'message': f'{ea_name} 已pause（EA 已從圖表remove）', 'source': 'watcher'})
                print(f"   ✅ pause {ea_name} success")
            else:
                _append_activity_log({'time': time.time(), 'action': 'pause_result', 'ea': ea_name,
                                      'message': f'❌ {ea_name} removefailed（EA 可能仲掛住圖表 — 請檢查 MT5 或再試）', 'source': 'watcher'})
                print(f"   ❌ pause {ea_name} failed（auto_attach 冇確認remove）")
        except Exception:
            pass
        # 🚨 2026-08-10：deletedone → 步驟全部 done（累積更新）
        try:
            import json as _jp2
            _sf2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
            _old2 = []
            try:
                if os.path.isfile(_sf2):
                    _old2 = _jp2.load(open(_sf2, 'r', encoding='utf-8'))
                    if not isinstance(_old2, list):
                        _old2 = []
            except Exception:
                _old2 = []
            for _s in _old2:
                if isinstance(_s, dict):
                    _s['status'] = 'done'
            with open(_sf2, 'w', encoding='utf-8') as _f:
                _jp2.dump(_old2, _f, ensure_ascii=False)
            # 🚨 2026-08-28 FIX（網頁版warning視窗卡「remove緊」— 同編譯done一樣）：同步埋開發dir steps
            try:
                import os as _os3
                _cand3 = [
                    _os3.path.join(_os3.environ.get('USERPROFILE', ''), 'Desktop', 'mt5-cloud', 'agent'),
                    _os3.path.join(_os3.environ.get('USERPROFILE', ''), 'Desktop', 'mt5-cloud-stable', 'agent'),
                ]
                for _cd3 in _cand3:
                    if _os3.path.isdir(_cd3):
                        with open(_os3.path.join(_cd3, '.ai_control.steps'), 'w', encoding='utf-8') as _f3:
                            _jp2.dump(_old2, _f3, ensure_ascii=False)
                        break
            except Exception:
                pass
        except Exception:
            pass
        os.remove(fp)
    except Exception as e:
        print(f"   ⚠️ pause cmd error: {e}")
        try:
            os.remove(fp)
        except Exception:
            pass



def process_clean_cmd(fp):
    """[ALERT] 2026-09-01（user要求 — 網頁「清理空白」按鈕）：處理 clean_cmd（清空白冇 EA 嘅 chart）"""
    print(f"\n🧹 [WATCHER] Clean command: {os.path.basename(fp)}")
    sys.stdout.flush()
    try:
        with open(fp, 'r') as f:
            cmd = json.load(f)
    except Exception as e:
        print(f"   ⚠️ Cannot read clean cmd {fp}: {e}")
        try:
            os.remove(fp)
        except Exception:
            pass
        return
    # fingerprint 檢查（同 deploy_cmd 一致 — 確保屬於當前 agent）
    # [ALERT] 2026-09-01 FIX（user實測：clean_cmd 被誤判舊殘留 — server 寫 account:hongkpng857 vs config account:hongkpng857|agent:xxx → 唔等 → 跳過）：
    # → 只比 account 部分（|agent: 之前 — 唔好全個 fingerprint 比較）
    try:
        _cmd_acct = cmd.get('account', '')
        _cur_acct = 'account:'
        try:
            import json as _jcfg
            _cfg_p = os.path.join(os.path.dirname(AUTO_ATTACH_SCRIPT), 'agent_config.json')
            if os.path.isfile(_cfg_p):
                _cfg = _jcfg.load(open(_cfg_p, encoding='utf-8'))
                _cur_acct = _cfg.get('fingerprint', 'account:')
        except Exception:
            pass
        # 只比 account 部分（拆 |agent: 前）
        _cmd_acct_base = str(_cmd_acct).split('|')[0].strip()
        _cur_acct_base = str(_cur_acct).split('|')[0].strip()
        if _cmd_acct_base and _cur_acct_base and _cmd_acct_base != _cur_acct_base:
            print(f"   ⛔ [WATCHER] clean_cmd 屬於 account {_cmd_acct_base}（當前 {_cur_acct_base}）— 舊殘留 — 跳過 + 刪除")
            try:
                os.remove(fp)
            except Exception:
                pass
            return
    except Exception:
        pass
    # 防重入（auto_attach running 就留返）
    if is_auto_attach_running():
        print("   ⚠️ auto_attach.py already running — 保留 clean_cmd 等下次 poll")
        return
    try:
        # 刪 command file（處理前 — 防殘留）
        try:
            os.remove(fp)
        except Exception:
            pass
        # 執行清理（call auto_attach.clean_blank_charts）
        import subprocess
        _py = sys.executable
        _script = os.path.join(os.path.dirname(AUTO_ATTACH_SCRIPT), 'auto_attach.py')
        _cmd_args = [_py, '-u', _script, '--clean-blank']
        # 警告視窗（.ai_control.show — alert_worker 彈）
        try:
            import time as _t
            _show_f = os.path.join(os.path.dirname(AUTO_ATTACH_SCRIPT), '.ai_control.show')
            with open(_show_f, 'w', encoding='utf-8') as _f:
                _f.write('clean blank charts')
            _steps_f = os.path.join(os.path.dirname(AUTO_ATTACH_SCRIPT), '.ai_control.steps')
            with open(_steps_f, 'w', encoding='utf-8') as _f2:
                json.dump([
                    {'text': 'Clean blank charts', 'status': 'doing'},
                    {'text': 'Remove blank charts (no EA)', 'status': 'pending'},
                    {'text': 'Restart MT5', 'status': 'pending'},
                    {'text': 'Verify running charts', 'status': 'pending'},
                ], _f2, ensure_ascii=False)
        except Exception:
            pass
        print(f"   Running: {_script} --clean-blank")
        result = subprocess.run(_cmd_args, capture_output=True, text=True, timeout=300)
        print(f"   Exit code: {result.returncode}")
        if result.stdout:
            print(f"   stdout: {result.stdout[-500:]}")
        if result.stderr:
            print(f"   stderr: {result.stderr[-500:]}")
        if result.returncode == 0:
            print(f"   ✅ Clean blank charts success")
        else:
            print(f"   ❌ Clean blank charts failed (exit={result.returncode})")
    except Exception as e:
        print(f"   ❌ Clean cmd processing error: {e}")
        import traceback
        traceback.print_exc()

def main():
    # single-instance guard：如果已有另一個 watcher 行緊就退出（防兩個 watcher 搶滑鼠/彈兩個視窗）
    if os.path.exists(WATCHER_LOCK_FILE):
        try:
            with open(WATCHER_LOCK_FILE) as f:
                content = f.read()
            import re as _re
            m = _re.search(r'pid=(\d+)', content)
            if m:
                old_pid = int(m.group(1))
                out = subprocess.run(
                    ['wmic', 'process', 'where', f'processid={old_pid}', 'get', 'commandline'],
                    capture_output=True, encoding='utf-8', errors='replace', timeout=5  # ⚠️ GBK 修
                ).stdout
                if 'deploy_watcher' in out and str(old_pid) not in ('', '0'):
                    print(f"⚠️ 已有 watcher 行緊 (PID {old_pid}) — 退出（single-instance guard）")
                    sys.exit(0)
        except Exception:
            pass
    print()
    print("=" * 56)
    print("  👀 Tradotcom Deploy Watcher")
    print("=" * 56)
    print(f"  Server:      {SERVER_URL}")
    print(f"  Agent ID:    {AGENT_ID}")
    print(f"  Watching:    {COMMON_FILES}/deploy_cmd_*.json")
    print(f"  Auto-attach: {AUTO_ATTACH_SCRIPT}")
    print(f"  Interval:    {POLL_INTERVAL}s")
    print("=" * 56)
    print("  Starting watcher...")
    sys.stdout.flush()

    # 預先起動warning視窗（常駐 — 建好隱藏）— 動作startimmediately顯示，唔會「動作完先彈出」（Bug #71）
    try:
        from control_guard import init_window
        ok = init_window()
        print(f"  {'✓' if ok else '⚠️'} AI 控制warning視窗已預先就緒{'（隱藏）' if ok else '（createfailed — 用時先建）'}")
        sys.stdout.flush()
    except Exception as e:
        print(f"  ⚠️ warning視窗預建failed（唔影響功能）: {e}")

    # start Navigator refresh worker（single worker + queue — 永遠行緊，等訊號）
    try:
        threading.Thread(target=_refresh_worker_loop, daemon=True).start()
        print("  ✓ Navigator refresh worker 已start")
        sys.stdout.flush()
    except Exception as e:
        print(f"  ⚠️ refresh worker startfailed: {e}")

    # start deploy worker（single worker — auto_attach 唔可以 block 主 loop）
    try:
        threading.Thread(target=_deploy_worker_loop, daemon=True).start()
        print("  ✓ Deploy worker 已start")
        sys.stdout.flush()
    except Exception as e:
        print(f"  ⚠️ deploy worker startfailed: {e}")
    
    # Write lock file to show we're alive
    try:
        with open(WATCHER_LOCK_FILE, 'w') as f:
            f.write(f"pid={os.getpid()}\nstarted={time.time()}\n")
    except:
        pass
    
    processed = set()  # Avoid re-processing same file
    
    # 🚨 2026-08-10：deploy worker thread 監察（死咗自動重生 — 根治 watcher 掛起）
    _worker_thread = None
    
    def _ensure_worker():
        nonlocal _worker_thread
        try:
            if _worker_thread is None or not _worker_thread.is_alive():
                _worker_thread = threading.Thread(target=_deploy_worker_loop, daemon=True)
                _worker_thread.start()
                print("🔄 [WATCHER] deploy worker 已重生（死咗自動開返）")
                sys.stdout.flush()
        except Exception as e:
            print(f"   ⚠️ worker 重生failed: {e}")
    
    while True:
        try:
            _ensure_worker()
            cmds = find_deploy_commands()
            for fp in cmds:
                if fp in processed:
                    continue
                processed.add(fp)
                print(f"\n📥 [WATCHER] New deploy command: {os.path.basename(fp)}")
                sys.stdout.flush()
                # 🚨 2026-08-10：put 唔可以阻塞（queue 滿 → 主 loop 卡死 → 新 deploy_cmd 唔處理 — deploy冇反應）
                try:
                    _deploy_queue.put(fp, timeout=2)
                except queue.Full:
                    print(f"   ⚠️ deploy queue 滿 — 留低下次再試（唔阻塞主 loop）")
                    processed.discard(fp)

            # ─── Compile 指令（.mq5 → .ex5，用 watcher 嘅 desktop access）───
            compile_cmds = find_compile_commands()
            for ccmd in compile_cmds:
                print(f"\n🔨 [WATCHER] Compile command: {os.path.basename(ccmd)}")
                sys.stdout.flush()
                process_compile_cmd(ccmd)
            
            # ─── Pause 指令（真pause — remove圖表 EA）───
            try:
                pause_cmds = sorted(glob.glob(os.path.join(COMMON_FILES, 'pause_cmd_*.json')), key=os.path.getmtime)
                for pcmd in pause_cmds:
                    print(f"\n⏸️ [WATCHER] Pause command: {os.path.basename(pcmd)}")
                    sys.stdout.flush()
                    process_pause_cmd(pcmd)
            except Exception as e:
                print(f"   ⚠️ pause scan error: {e}")
            
            # ─── Clean 指令（清空白冇 EA 嘅 chart — 2026-09-01 user要求）───
            try:
                clean_cmds = sorted(glob.glob(os.path.join(COMMON_FILES, 'clean_cmd_*.json')), key=os.path.getmtime)
                for clcmd in clean_cmds:
                    print(f"\n🧹 [WATCHER] Clean command: {os.path.basename(clcmd)}")
                    sys.stdout.flush()
                    process_clean_cmd(clcmd)
            except Exception as e:
                print(f"   ⚠️ clean scan error: {e}")
            
            # Clean processed set (keep only files that still exist)
            processed = {p for p in processed if os.path.exists(p)}
            
            # ─── Experts dir監控：EA file新增/delete → 自動 refresh Navigator ───
            check_experts_changes()
            
            # ─── Controller 自動恢復（系統file — 心跳冇 → 自動重新deploy）───
            # Controller 係網頁控制中樞 — 一定要running — 心跳停咗就寫 deploy_cmd 重新attach
            # ⚠️ 開關：agent/.controller_recover exists先恢復（deploy success前保持關 — 唔會無限循環）
            _recover_flag = os.path.join(os.path.dirname(__file__), '.controller_recover')
            if os.path.isfile(_recover_flag):
                try:
                    _cf = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
                    _sf = os.path.join(_cf, 'state_controller.json')
                    _controller_alive = False
                    if os.path.isfile(_sf):
                        try:
                            with open(_sf, 'r', encoding='utf-8') as _f:
                                _sd = json.load(_f)
                            if _sd.get('status') == 'running' and int(time.time()) - int(_sd.get('ts', 0)) < 30:
                                _controller_alive = True
                        except Exception:
                            pass
                    if not _controller_alive:
                        # Controller 心跳冇 — 但係 ⚠️ 只有 MT5 開住先恢復（MT5 死咗就唔好試 —
                        # before無限循環：寫 deploy_cmd → auto_attach → 彈warning窗 → 殺 MT5 → 又寫）
                        _mt5_running = False
                        try:
                            import subprocess as _sp2
                            _r2 = _sp2.run('tasklist /FI "IMAGENAME eq terminal64.exe" /NH', shell=True, capture_output=True)
                            _mt5_running = b'terminal64' in _r2.stdout
                        except Exception:
                            pass
                        if not _mt5_running:
                            print("ℹ️ [WATCHER] Controller 心跳停咗，但 MT5 未開 — 等 MT5 開返先恢復（唔循環）")
                            sys.stdout.flush()
                        else:
                            # 檢查有冇 pending deploy_cmd（避免重複寫）
                            _has_pending = any(f.startswith('deploy_cmd_Controller') for f in os.listdir(_cf)) if os.path.isdir(_cf) else False
                            if not _has_pending:
                                # 寫 deploy_cmd（auto_attach 重新attach Controller — 保持系統中樞running）
                                _dp = os.path.join(_cf, f'deploy_cmd_Controller_{int(time.time())}.json')
                                with open(_dp, 'w', encoding='utf-8') as _f:
                                    json.dump({'ea_name': 'Controller', 'symbol': 'EURUSD', 'tf': 'H1',
                                               'magic': '240701', 'lot': '0.01', 'source': 'watcher_auto_recover'}, _f, ensure_ascii=False)
                                print("🔄 [WATCHER] Controller 心跳停咗（MT5 開住）— 自動重新deploy（系統中樞恢復）")
                                sys.stdout.flush()
                except Exception as _ce:
                    print(f"   ⚠️ Controller auto-recover error: {_ce}")
            
            # ─── 手動deploy監測（Controller）：user double-click 後 Properties dialog 彈出 →
            # 自動撳「確定」（唔使佢再操作）— 標記喺 server deploy Controller 時寫
            try:
                _pending_fp = os.path.join(os.path.dirname(__file__), '.manual_deploy_pending')
                if os.path.isfile(_pending_fp):
                    _mt5pid2 = None
                    try:
                        import subprocess as _sp3
                        _r3 = _sp3.run('tasklist /FI "IMAGENAME eq terminal64.exe" /NH', shell=True, capture_output=True)
                        import re as _re3
                        _m3 = _re3.search(rb'terminal64\.exe\",\"(\d+)\"', _r3.stdout)
                        if _m3:
                            _mt5pid2 = int(_m3.group(1))
                    except Exception:
                        pass
                    if _mt5pid2:
                        try:
                            from pywinauto import Application as _App2
                            _app2 = _App2(backend='win32').connect(process=_mt5pid2, timeout=5)
                            for _w2 in _app2.windows():
                                try:
                                    if _w2.class_name() == '#32770' and 'Controller' in _w2.window_text():
                                        for _b2 in _w2.children(class_name='Button'):
                                            _bt2 = _b2.window_text()
                                            if '確定' in _bt2 or 'OK' in _bt2:
                                                _b2.click()
                                                print("✅ [WATCHER] 偵測到 Controller Properties — 已自動撳「確定」（attachdone）")
                                                sys.stdout.flush()
                                                try:
                                                    os.remove(_pending_fp)
                                                except Exception:
                                                    pass
                                                break
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception as _pe:
                print(f"   ⚠️ manual deploy monitor error: {_pe}")
            
            time.sleep(POLL_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n🛑 Watcher stopped by user")
            break
        except Exception as e:
            print(f"\n⚠️ Watcher error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(POLL_INTERVAL)
    
    # Cleanup
    if os.path.exists(WATCHER_LOCK_FILE):
        try:
            os.remove(WATCHER_LOCK_FILE)
        except:
            pass
    print("👋 Watcher exited")

if __name__ == '__main__':
    main()
