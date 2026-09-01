# -*- coding: utf-8 -*-
"""
Tradotcom 完整 Restore
=====================
從 backup zip 還原所有嘢（code + 配置 + DB + MT5 狀態）— 版本一致 → 唔會失效

Restore 流程：
  1. 停 server/agent/watcher/alert_worker（避免寫入衝突）
  2. Git checkout 到 backup 嘅 commit
  3. 安裝目錄還原（agent code + 配置）
  4. DB 還原
  5. MT5 狀態還原（.chr/order.wnd/EA/心跳/config）
  6. 重啟 server + agent + watcher + alert_worker
  7. 驗證（server 200 + agent Registered + EA 心跳）
"""
import os, sys, shutil, json, subprocess, time, zipfile, glob

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DEV_DIR     = r'C:\Users\hongk\Desktop\mt5-cloud'
AGENT_DIR   = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'TradotcomAgent')
DB_PATH     = os.path.join(DEV_DIR, 'instance', 'mt5cloud.db')
MT5_ROOT    = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
BACKUP_ROOT = os.path.join(DEV_DIR, 'backups')

# 搵 terminal 目錄
TERMINAL_DIR = None
if os.path.isdir(MT5_ROOT):
    for _d in os.listdir(MT5_ROOT):
        if os.path.isdir(os.path.join(MT5_ROOT, _d, 'MQL5')):
            TERMINAL_DIR = os.path.join(MT5_ROOT, _d)
            break


def _stop_services():
    """停所有 python 服務（server/agent/watcher/alert_worker）"""
    print('[1/7] 停服務...')
    subprocess.run('powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"Name=\'python.exe\'\\" | Where-Object { $_.CommandLine -match \'app.py|agent.py|alert_worker|deploy_watcher\' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"', shell=True, capture_output=True, timeout=30)
    # 清 lock
    for _lk in glob.glob(os.path.join(AGENT_DIR, '*.lock')) + glob.glob(os.path.join(AGENT_DIR, '.watcher_running')):
        try: os.remove(_lk)
        except Exception: pass
    # 清 __pycache__
    for _pc in glob.glob(os.path.join(DEV_DIR, '**', '__pycache__'), recursive=True):
        shutil.rmtree(_pc, ignore_errors=True)
    for _pc in glob.glob(os.path.join(AGENT_DIR, '__pycache__')):
        shutil.rmtree(_pc, ignore_errors=True)
    time.sleep(3)
    print('   服務已停')


def _restore_git(commit):
    """Git checkout 到 backup commit"""
    print(f'[2/7] Git checkout {commit[:8]}...')
    r = subprocess.run(['git', '-C', DEV_DIR, 'checkout', commit], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f'   ⚠️ Git checkout 失敗: {r.stderr[:200]}')
        return False
    print('   ✅ Git 已回覆')
    return True


def _restore_agent(zf):
    """還原安裝目錄（agent code + 配置 — 唔要 log/lock）"""
    print('[3/7] 還原安裝目錄...')
    os.makedirs(AGENT_DIR, exist_ok=True)
    # 清舊（保留 log 做診斷）
    for _f in os.listdir(AGENT_DIR):
        _fp = os.path.join(AGENT_DIR, _f)
        if os.path.isfile(_fp) and not _f.endswith('.log'):
            try: os.remove(_fp)
            except Exception: pass
    # 還原 agent/ 入面
    for _name in zf.namelist():
        if _name.startswith('agent/') and not _name.endswith('/'):
            _rel = _name[len('agent/'):]
            if _rel.endswith(('.log', '.pid', '.lock')):
                continue
            _dst = os.path.join(AGENT_DIR, _rel)
            os.makedirs(os.path.dirname(_dst), exist_ok=True)
            with zf.open(_name) as _src, open(_dst, 'wb') as _out:
                shutil.copyfileobj(_src, _out)
    print('   ✅ 安裝目錄還原')


def _restore_db(zf):
    """還原 DB"""
    print('[4/7] 還原 DB...')
    try:
        with zf.open('db/mt5cloud.db') as _src, open(DB_PATH, 'wb') as _out:
            shutil.copyfileobj(_src, _out)
        print('   ✅ DB 還原')
    except KeyError:
        print('   ⚠️ backup 冇 DB — skip')


def _restore_mt5(zf):
    """還原 MT5 狀態（.chr/order.wnd/EA/心跳/config）"""
    print('[5/7] 還原 MT5 狀態...')
    if not TERMINAL_DIR:
        print('   ⚠️ 搵唔到 terminal 目錄 — skip')
        return
    restored = 0
    for _name in zf.namelist():
        if _name.startswith('mt5/') and not _name.endswith('/'):
            _rel = _name[len('mt5/'):]
            if _rel.startswith('charts/'):
                _dst = os.path.join(TERMINAL_DIR, 'MQL5', 'Profiles', 'Charts', _rel[len('charts/'):])
            elif _rel.startswith('experts/'):
                _dst = os.path.join(TERMINAL_DIR, 'MQL5', 'Experts', _rel[len('experts/'):])
            elif _rel.startswith('common/'):
                _dst = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files', _rel[len('common/'):])
            elif _rel.startswith('config/'):
                _dst = os.path.join(TERMINAL_DIR, 'config', _rel[len('config/'):])
            else:
                continue
            os.makedirs(os.path.dirname(_dst), exist_ok=True)
            with zf.open(_name) as _src, open(_dst, 'wb') as _out:
                shutil.copyfileobj(_src, _out)
            restored += 1
    print(f'   ✅ MT5 狀態還原（{restored} 個檔案）')


def _start_services():
    """重啟 server + agent + watcher + alert_worker"""
    print('[6/7] 重啟服務...')
    # server
    subprocess.Popen(
        f'cd /d {DEV_DIR} && set RENDER=1&& set PORT=5001&& python -u server/app.py > server_run.log 2>&1',
        shell=True, cwd=DEV_DIR)
    time.sleep(8)
    # agent（讀 agent_config.json — 攞 agent_id + token）
    agent_id = ''
    token = ''
    try:
        cfg = json.load(open(os.path.join(AGENT_DIR, 'agent_config.json'), encoding='utf-8'))
        agent_id = cfg.get('agent_id', '')
        token = cfg.get('token', '')
    except Exception:
        pass
    if agent_id and token:
        subprocess.Popen(
            f'cd /d {AGENT_DIR} && python -u agent.py --server https://tradotcom.com --agent {agent_id} --token {token}',
            shell=True, cwd=AGENT_DIR)
    # alert_worker
    subprocess.Popen(f'cd /d {AGENT_DIR} && python -u alert_worker.py', shell=True, cwd=AGENT_DIR)
    time.sleep(10)
    print('   服務已啟動')


def _verify():
    """驗證還原成功"""
    print('[7/7] 驗證...')
    # server
    try:
        r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', 'http://localhost:5001/'], capture_output=True, text=True, timeout=10)
        print(f'   Server: {r.stdout} {"✅" if r.stdout=="200" else "❌"}')
    except Exception as e:
        print(f'   Server: ❌ {e}')
    # agent
    try:
        r = subprocess.run(['tail', '-2', os.path.join(AGENT_DIR, 'agent_launcher.log')], capture_output=True, text=True, timeout=10)
        print(f'   Agent: {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "?"}')
    except Exception:
        pass
    # EA 心跳
    _cf = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
    fresh = []
    if os.path.isdir(_cf):
        for _f in os.listdir(_cf):
            if _f.startswith('state_') and _f.endswith('.json'):
                _p = os.path.join(_cf, _f)
                _age = time.time() - os.path.getmtime(_p)
                if _age < 300:
                    fresh.append(_f.replace('state_', '').replace('.json', ''))
    print(f'   EA 心跳 FRESH: {fresh if fresh else "冇（EA 未部署）"}')


def restore(backup_file):
    """執行完整 restore"""
    print(f'=== Restore: {backup_file} ===')
    if not os.path.isfile(backup_file):
        print(f'❌ backup 唔存在: {backup_file}')
        return False
    with zipfile.ZipFile(backup_file) as zf:
        # 讀 info
        try:
            info = json.loads(zf.read('info.json'))
            print(f'   Backup 日期: {info.get("created")}')
            print(f'   Git commit: {info.get("git_commit")} ({info.get("git_branch")})')
            print(f'   Label: {info.get("label")}')
        except Exception:
            print('   ⚠️ backup 冇 info.json')

        _stop_services()
        _restore_git(info.get('git_commit', 'HEAD'))
        _restore_agent(zf)
        _restore_db(zf)
        _restore_mt5(zf)
    _start_services()
    _verify()
    print('\n=== Restore 完成 ===')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Tradotcom 完整 Restore')
    parser.add_argument('--restore', help='backup zip 路徑（backups/ 入面）')
    parser.add_argument('--list', action='store_true', help='列出所有 backup')
    args = parser.parse_args()

    if args.list:
        if os.path.isdir(BACKUP_ROOT):
            for b in sorted(os.listdir(BACKUP_ROOT), reverse=True):
                if b.endswith('.zip'):
                    print(f'  {b}')
        else:
            print('冇 backup')
    elif args.restore:
        # 支援相對路徑（backups/xxx.zip）
        if not os.path.isabs(args.restore):
            args.restore = os.path.join(BACKUP_ROOT, args.restore)
        restore(args.restore)
    else:
        print('用法: python backup_restore.py --restore <backup.zip> 或 --list')
