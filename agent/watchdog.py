"""Watchdog — 檢查 watcher/server/detector 有冇行 — 冇就自動重啟（2026-08 用戶要求穩定）
用嚟配合 Hermes cron 每分鐘跑一次"""
import os
import sys
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))

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
    """攞所有 python process 嘅 cmdline（wmic CSV — 正確格式）"""
    procs = []
    try:
        out = subprocess.run(
            "wmic process where \"name='python.exe'\" get processid,commandline /format:csv",
            shell=True, capture_output=True, timeout=10)
        for line in out.stdout.decode('utf-8', errors='replace').splitlines():
            line = line.strip()
            if not line or line.startswith('Node'):
                continue
            # 格式: Node,CommandLine,ProcessId — cmdline 可能有逗號，由最後一個逗號分開 PID
            idx = line.rfind(',')
            if idx <= 0:
                continue
            cmd = line[line.find(',') + 1:idx].strip()
            pid = line[idx + 1:].strip()
            if cmd and pid.isdigit():
                procs.append((int(pid), cmd))
    except Exception:
        pass
    return procs


def _is_running(procs, keyword):
    return any(keyword in cmd for _, cmd in procs)


def _start(cmd_list, name):
    try:
        subprocess.Popen(cmd_list, cwd=PROJECT, creationflags=subprocess.CREATE_NO_WINDOW)
        print(f'✅ {name} 已啟動')
        return True
    except Exception as e:
        print(f'❌ {name} 啟動失敗: {e}')
        return False


def main():
    quiet = '--verbose' not in sys.argv
    procs = _py_cmdlines()
    if not quiet:
        print(f'python process: {len(procs)} 個')
    # 1. Watcher
    if not _is_running(procs, 'deploy_watcher'):
        _start([sys.executable, '-u', 'agent/deploy_watcher.py'], 'watcher')
    elif not quiet:
        print('watcher OK')
    # 2. Server（:5001 — app.py）
    if not _is_running(procs, 'server/app.py'):
        _start([sys.executable, '-u', 'server/app.py'], 'server')
    elif not quiet:
        print('server OK')
    # 3. Detector（:5003）
    if not _is_running(procs, 'auto_trade_detector'):
        _start([sys.executable, '-u', 'agent/auto_trade_detector.py'], 'detector')
    elif not quiet:
        print('detector OK')


if __name__ == '__main__':
    main()
