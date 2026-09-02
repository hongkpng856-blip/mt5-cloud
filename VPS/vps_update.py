# -*- coding: utf-8 -*-
# Tradotcom VPS one-click update v3 (Python)
# - Finds newest server-code-deploy-*.zip next to this script
# - Backs up VPS DB, replaces runtime, restores DB, restarts, verifies
# Put this + server-code-deploy-*.zip in Desktop\VPS, double-click vps_update.bat
import os, sys, shutil, subprocess, time, glob, zipfile, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(BASE, 'runtime')
TEMP = os.environ.get('TEMP', BASE)

def log(msg):
    print(msg)
    sys.stdout.flush()

log('=' * 44)
log('  Tradotcom Server - One-click Update v3')
log('  Date: ' + time.strftime('%Y-%m-%d %H:%M:%S'))
log('=' * 44)
log('')

# 0. Find newest zip in BASE
zips = sorted(glob.glob(os.path.join(BASE, 'server-code-deploy-*.zip')),
              key=os.path.getmtime, reverse=True)
if not zips:
    log('[ERROR] No server-code-deploy-*.zip in ' + BASE)
    log('Put server-code-deploy-YYYYMMDD-HHMM.zip in the VPS folder')
    sys.exit(1)
zip_path = zips[0]
log('Using zip: ' + zip_path)
log('')

# 1. Stop old server (kill ONLY python running app.py - not this script)
log('[1/5] Stopping old server...')
try:
    import ctypes
    # use tasklist to find pids of python.exe whose cmdline contains app.py
    r = subprocess.run('wmic process where "name=\'python.exe\'" get ProcessId,CommandLine /format:csv',
                       shell=True, capture_output=True, text=True, timeout=20)
    pids = []
    for line in (r.stdout or '').splitlines():
        if 'app.py' in line and 'vps_' not in line:
            parts = line.split(',')
            for p in parts:
                p = p.strip()
                if p.isdigit():
                    pids.append(p)
    for pid in set(pids):
        subprocess.run('taskkill /PID %s /F' % pid, shell=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log('       killed PID ' + pid)
except Exception as e:
    log('       kill error (continue): %s' % e)
time.sleep(3)
log('       OK')

# 2. Backup DB + remove old runtime
db_path = os.path.join(TARGET, 'instance', 'mt5cloud.db')
backup_path = os.path.join(TEMP, 'mt5cloud_backup.db')
log('[2/5] Backup DB + remove old runtime...')
if os.path.isdir(TARGET):
    if os.path.isfile(db_path):
        shutil.copy2(db_path, backup_path)
        log('       DB backed up: ' + str(os.path.getsize(backup_path)) + ' bytes')
    shutil.rmtree(TARGET, ignore_errors=True)
    log('       Old runtime removed')
else:
    log('       (No old runtime)')

# 3. Extract new code into runtime
log('[3/5] Extracting new code into runtime...')
try:
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(TARGET)
except Exception as e:
    log('[ERROR] Extract failed: %s' % e)
    sys.exit(1)
log('       Extracted')

# Restore VPS DB (keep VPS data)
if os.path.isfile(backup_path):
    os.makedirs(os.path.join(TARGET, 'instance'), exist_ok=True)
    shutil.copy2(backup_path, db_path)
    log('       VPS DB restored (data kept)')
    os.remove(backup_path)

# 4. Start new server
log('[4/5] Starting new server...')
# Find python.exe (full path - cmd may not have python in PATH)
python_path = None
candidates = [
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python', 'Python38', 'python.exe'),
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python', 'Python311', 'python.exe'),
    r'C:\Python38\python.exe',
    r'C:\Python311\python.exe',
    r'C:\Program Files\Python38\python.exe',
]
for c in candidates:
    if os.path.isfile(c):
        python_path = c
        break
if not python_path:
    # try PATH
    r = subprocess.run('where python', shell=True, capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        python_path = r.stdout.strip().splitlines()[0]
if not python_path:
    log('       [ERROR] Cannot find python.exe!')
    sys.exit(1)
log('       Python: ' + python_path)
# [ALERT] 2026-09-02 FIX v3：PowerShell -Environment 參數喺 PS 5.1 唔支援（VPS = Win2012）→ 直接用 Python Popen（唔經 cmd/powershell）
_env_srv = dict(os.environ)
_env_srv['RENDER'] = '1'
_env_srv['PORT'] = '80'
CREATE_NEW_CONSOLE = 0x00000010
subprocess.Popen([python_path, 'server', 'app.py'], cwd=TARGET, env=_env_srv,
                 creationflags=CREATE_NEW_CONSOLE)
time.sleep(10)
log('       OK')

# 5. Verify (python urllib - no curl needed)
log('[5/5] Verifying...')
for path, label in (('/', 'website'), ('/api/agent-download', 'agent-download'),
                    ('/api/agent-py', 'agent-py')):
    try:
        code = urllib.request.urlopen('http://127.0.0.1:80' + path, timeout=8).getcode()
        log('   %-16s HTTP %s' % (label, code))
    except Exception as e:
        log('   %-16s ERROR: %s' % (label, e))

log('')
log('=' * 44)
log('   Update complete!')
log('   Runtime: ' + TARGET)
log('   Time: ' + time.strftime('%Y-%m-%d %H:%M:%S'))
log('=' * 44)
