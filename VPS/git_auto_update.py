# -*- coding: utf-8 -*-
"""
Tradotcom VPS Git Auto-Update Watcher
=====================================
- Checks GitHub for new commits every N seconds
- On new commit: git pull + restart server
- Writes log to git_watch_log.txt

Risk (user acknowledged):
  1. Pulled broken code -> server down (no human watching)
  2. git pull conflict if local changes exist
  3. DB not in git (safe - .gitignore *.db)
"""
import os, sys, subprocess, time, datetime, json

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(BASE, 'tradotcom')  # git clone folder
LOG = os.path.join(BASE, 'git_watch_log.txt')
CHECK_INTERVAL = 60  # seconds

def log(msg):
    line = '[%s] %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    print(line)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def run(cmd, cwd=None, timeout=60):
    r = subprocess.run(cmd, cwd=cwd or REPO, capture_output=True, text=True, timeout=timeout)
    return r

def git_current():
    r = run(['git', 'rev-parse', 'HEAD'])
    return r.stdout.strip() if r.returncode == 0 else None

def git_remote():
    r = run(['git', 'fetch', 'origin', 'master'])
    if r.returncode != 0:
        log('fetch failed: ' + r.stderr.strip()[:200])
        return None
    r2 = run(['git', 'rev-parse', 'origin/master'])
    return r2.stdout.strip() if r2.returncode == 0 else None

def git_pull():
    r = run(['git', 'pull', 'origin', 'master'])
    if r.returncode != 0:
        log('pull failed: ' + r.stderr.strip()[:300])
        return False
    log('pull OK: ' + (r.stdout.strip()[:200] or '(up to date)'))
    return True

def find_python():
    candidates = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python', 'Python38', 'python.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python', 'Python311', 'python.exe'),
        r'C:\Python38\python.exe', r'C:\Python311\python.exe',
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return 'python'

def restart_server():
    """Kill old server + start from repo folder"""
    log('restarting server...')
    # kill python running app.py (not self - this is git_watch.py)
    r = run(['wmic', 'process', 'where', "name='python.exe'", 'get', 'ProcessId,CommandLine', '/format:csv'],
            shell=True, timeout=30)
    for line in (r.stdout or '').splitlines():
        if 'app.py' in line and 'git_watch' not in line and 'vps_' not in line:
            parts = [p.strip() for p in line.split(',')]
            for p in parts:
                if p.isdigit():
                    subprocess.run('taskkill /PID %s /F' % p, shell=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    log('   killed PID %s' % p)
    time.sleep(3)
    # start new server from repo
    py = find_python()
    env = dict(os.environ)
    env['RENDER'] = '1'
    env['PORT'] = '80'
    CREATE_NEW_CONSOLE = 0x00000010
    subprocess.Popen([py, 'server', 'app.py'], cwd=REPO, env=env, creationflags=CREATE_NEW_CONSOLE)
    log('   server started from ' + REPO)
    time.sleep(6)
    # verify
    import urllib.request
    try:
        code = urllib.request.urlopen('http://127.0.0.1:80/', timeout=8).getcode()
        log('   verify website: HTTP %s' % code)
    except Exception as e:
        log('   verify website FAILED: %s' % e)

def main():
    log('=' * 50)
    log('Git Auto-Update Watcher STARTED (check every %ds)' % CHECK_INTERVAL)
    log('Repo: ' + REPO)
    log('Current: ' + str(git_current()))
    log('=' * 50)
    last_local = git_current()
    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            remote = git_remote()
            if remote is None:
                continue
            local = git_current()
            if remote != local:
                log('NEW commit detected: %s -> %s' % (str(local)[:8], str(remote)[:8]))
                if git_pull():
                    restart_server()
                    last_local = git_current()
                    log('updated to: ' + str(last_local)[:8])
            # else: no change
        except Exception as e:
            log('watch error: %s' % e)
            time.sleep(30)

if __name__ == '__main__':
    main()
