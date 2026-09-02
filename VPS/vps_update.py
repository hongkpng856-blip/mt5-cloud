# -*- coding: utf-8 -*-
# Tradotcom VPS one-click update (Python — reliable, no cmd parsing issues)
# Put this next to server-code-deploy-*.zip, double-click vps_update.bat
import os, sys, shutil, subprocess, time, glob, zipfile, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(BASE, 'runtime')
TEMP = os.environ.get('TEMP', BASE)

def log(msg):
    print(msg)
    sys.stdout.flush()

log('=' * 44)
log('  Tradotcom Server - One-click Update')
log('  Date: ' + time.strftime('%Y-%m-%d %H:%M:%S'))
log('=' * 44)
log('')

# 0. Find latest server-code-deploy-*.zip (in this folder)
zips = sorted(glob.glob(os.path.join(BASE, 'server-code-deploy-*.zip')),
              key=os.path.getmtime, reverse=True)
if not zips:
    log('[ERROR] Cannot find server-code-deploy-*.zip in ' + BASE)
    log('Please put server-code-deploy-YYYYMMDD-HHMM.zip in the VPS folder')
    sys.exit(1)
zip_path = zips[0]
log('Using zip: ' + zip_path)
log('')

# 1. Backup DB + remove old runtime
db_path = os.path.join(TARGET, 'instance', 'mt5cloud.db')
backup_path = os.path.join(TEMP, 'mt5cloud_backup.db')
log('[1/5] Backup DB + remove old runtime...')
if os.path.isdir(TARGET):
    if os.path.isfile(db_path):
        shutil.copy2(db_path, backup_path)
        log('       DB backed up')
    shutil.rmtree(TARGET, ignore_errors=True)
    log('       Old runtime removed')
else:
    log('       (No old runtime)')

# 2. Extract new code into runtime
log('[2/5] Extracting new code into runtime...')
try:
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(TARGET)
except Exception as e:
    log('[ERROR] Extract failed: %s' % e)
    sys.exit(1)
if os.path.isfile(backup_path):
    os.makedirs(os.path.join(TARGET, 'instance'), exist_ok=True)
    shutil.copy2(backup_path, db_path)
    log('       VPS DB restored (data kept)')
    os.remove(backup_path)
log('       OK')

# 3. Stop old server (kill python — VPS only runs the server)
log('[3/5] Stopping old server...')
subprocess.run('taskkill /IM python.exe /F', shell=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)
log('       OK')

# 4. Start new server (new console window)
log('[4/5] Starting new server...')
cmd = 'set RENDER=1&& set PORT=80&& python server\\app.py'
DETACHED_PROCESS = 0x00000010
subprocess.Popen(['cmd', '/c', cmd], cwd=TARGET, creationflags=DETACHED_PROCESS)
time.sleep(6)
log('       OK')

# 5. Verify
log('[5/5] Verifying server...')
try:
    code = urllib.request.urlopen('http://127.0.0.1:80', timeout=8).getcode()
    log('HTTP %s' % code)
except Exception as e:
    log('HTTP check failed: %s' % e)
log('')
log('=' * 44)
log('   Update complete! Server should be running')
log('   Runtime folder: ' + TARGET)
log('   Updated: ' + time.strftime('%Y-%m-%d %H:%M:%S'))
log('=' * 44)
