# -*- coding: utf-8 -*-
# One-time migration: move running server from Desktop\server-code-deploy
# into Desktop\VPS\runtime (new consolidated location).
import os, sys, shutil, subprocess, time, glob, zipfile, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))          # Desktop\VPS
OLD = r'C:\Users\Administrator\Desktop\server-code-deploy'  # old location
NEW = os.path.join(BASE, 'runtime')                         # new location

def log(msg):
    print(msg)
    sys.stdout.flush()

log('=' * 44)
log('  Tradotcom VPS - Migrate to VPS\\runtime')
log('  Date: ' + time.strftime('%Y-%m-%d %H:%M:%S'))
log('=' * 44)
log('')

# 1. Stop old server (kill ONLY server app.py processes — NOT this script!)
log('[1/5] Stopping old server...')
ps = ('powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter '
      '"Name=\'python.exe\'" | Where-Object { $_.CommandLine -like \'*app.py*\' '
      '-and $_.CommandLine -notlike \'*vps_*\' } | ForEach-Object { Stop-Process '
      '-Id $_.ProcessId -Force }"')
subprocess.run(ps, shell=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)
log('       OK')

# 2. Copy old server-code-deploy -> VPS\runtime (keep DB)
log('[2/5] Copying code to ' + NEW)
os.makedirs(NEW, exist_ok=True)
for name in ('server', 'instance', 'requirements.txt'):
    src = os.path.join(OLD, name)
    dst = os.path.join(NEW, name)
    if os.path.isdir(src):
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        log('       copied %s\\' % name)
    elif os.path.isfile(src):
        shutil.copy2(src, dst)
        log('       copied %s' % name)
    else:
        log('       [WARN] %s not found in old folder' % name)

# 3. Agent folder: from old folder if exists, else extract from newest zip
src_agent = os.path.join(OLD, 'agent')
dst_agent = os.path.join(NEW, 'agent')
if os.path.isdir(src_agent):
    if os.path.isdir(dst_agent):
        shutil.rmtree(dst_agent)
    shutil.copytree(src_agent, dst_agent)
    log('[3/5] agent\\ copied from old folder')
else:
    zips = sorted(glob.glob(os.path.join(BASE, 'server-code-deploy-*.zip')),
                  key=os.path.getmtime, reverse=True)
    if zips:
        with zipfile.ZipFile(zips[0]) as zf:
            for m in zf.namelist():
                if m.startswith('agent/'):
                    zf.extract(m, NEW)
        log('[3/5] agent\\ extracted from ' + os.path.basename(zips[0]))
    else:
        log('[3/5] [WARN] no agent folder found anywhere')

# 4. Start new server
log('[4/5] Starting server from ' + NEW)
cmd = 'set RENDER=1&& set PORT=80&& python server\\app.py'
DETACHED_PROCESS = 0x00000010
subprocess.Popen(['cmd', '/c', cmd], cwd=NEW, creationflags=DETACHED_PROCESS)
time.sleep(8)
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
log('   Migration complete! Server running from:')
log('   ' + NEW)
log('   Next updates: copy server\\ + agent\\ into runtime,')
log('   then double-click restart_server.bat')
log('=' * 44)
