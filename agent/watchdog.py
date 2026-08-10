"""Watchdog — 檢查 watcher/server/detector 有冇行 — 冇就自動重啟（2026-08 用戶要求穩定）
用嚟配合 Hermes cron 每分鐘跑一次"""
import os
import sys
import time
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mt5_watchdog.log')


def _log(msg):
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}\n')
    except Exception:
        pass


def _find_project():
    """向上搵 mt5-cloud 目錄（agent/deploy_watcher.py 存在）"""
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isfile(os.path.join(d, 'agent', 'deploy_watcher.py')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


PROJECT = _find_project() or BASE


def _py_cmdlines():
    """攞所有 python process 嘅 cmdline（wmic CSV）"""
    procs = []
    try:
        out = subprocess.run(
            "wmic process where \"name='python.exe'\" get processid,commandline /format:csv",
            shell=True, capture_output=True, timeout=10)
        for line in out.stdout.decode('utf-8', errors='replace').splitlines():
            line = line.strip()
            if not line or line.startswith('Node'):
                continue
            idx = line.rfind(',')
            if idx <= 0:
                continue
            cmd = line[line.find(',') + 1:idx].strip()
            pid = line[idx + 1:].strip()
            if cmd and pid.isdigit():
                procs.append((int(pid), cmd))
    except Exception as e:
        _log(f'wmic error: {e}')
    return procs


def _is_running(procs, keyword):
    return any(keyword in cmd for _, cmd in procs)


def _start(cmd_list, name):
    try:
        # 🚨 2026-08-10：watcher 輸出寫 log 檔（死前有記錄 — 查死因）
        log_f = None
        if name == 'watcher':
            log_f = open(os.path.join(PROJECT, 'agent', 'deploy_watcher.log'), 'a', encoding='utf-8')
            log_f.write(f'\n===== [{time.strftime("%Y-%m-%d %H:%M:%S")}] watcher 啟動 =====\n')
            log_f.flush()
        subprocess.Popen(cmd_list, cwd=PROJECT, creationflags=subprocess.CREATE_NO_WINDOW,
                         stdout=log_f, stderr=log_f)
        _log(f'✅ {name} 已啟動（缺失自動重啟）')
        print(f'✅ {name} 已啟動')
        return True
    except Exception as e:
        _log(f'❌ {name} 啟動失敗: {e}')
        print(f'❌ {name} 啟動失敗: {e}')
        return False


def main():
    quiet = '--verbose' not in sys.argv
    procs = _py_cmdlines()
    status = {}
    for name, kw in [('watcher', 'deploy_watcher'), ('server', 'server/app.py'), ('detector', 'auto_trade_detector'),
                     ('alert_worker', 'alert_worker')]:  # 🚨 2026-08-10：加警告視窗 process（死咗自動重啟 — 唔使手動）
        if _is_running(procs, kw):
            status[name] = 'OK'
        else:
            status[name] = 'MISSING'
    _log(f'檢查: {status}（python 進程 {len(procs)} 個）')
    if not quiet:
        print(status)
    # 重啟缺失
    if status['watcher'] == 'MISSING':
        _start([sys.executable, '-u', 'agent/deploy_watcher.py'], 'watcher')
    if status['server'] == 'MISSING':
        _start([sys.executable, '-u', 'server/app.py'], 'server')
    if status['detector'] == 'MISSING':
        _start([sys.executable, '-u', 'agent/auto_trade_detector.py'], 'detector')
    if status['alert_worker'] == 'MISSING':
        # 🚨 2026-08-10：單實例保護（已行就唔起 — 防重複警告視窗 — 用戶報「兩個相同嘅嘢」）
        if not _is_running(_py_cmdlines(), 'alert_worker'):
            _start([sys.executable, '-u', 'agent/alert_worker.py'], 'alert_worker')
    # 🚨 2026-08-10：MT5 檢查 — 冇開就自動開（確保 EA 一直行 — 閒置唔會失效）
    try:
        mt5 = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH',
                             shell=True, capture_output=True, timeout=10)
        if 'terminal64' not in mt5.stdout.decode('utf-8', errors='replace'):
            subprocess.Popen([r'C:\Program Files\MetaTrader 5\terminal64.exe'])
            _log('✅ MT5 已啟動（缺失自動開啟）')
            print('✅ MT5 已啟動')
    except Exception as e:
        _log(f'MT5 檢查失敗: {e}')


if __name__ == '__main__':
    main()
