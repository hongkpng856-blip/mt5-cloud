# -*- coding: utf-8 -*-
# VPS diagnostic checker - writes result to vps_check_log.txt
import os, subprocess, sys, glob

BASE = r'C:\Users\Administrator\Desktop\VPS'
OLD = r'C:\Users\Administrator\Desktop\server-code-deploy'
out = []

def log(m):
    out.append(m)
    print(m)

log('=' * 50)
log('VPS Diagnostic Check')
log('=' * 50)
log('')

# 1. Which python processes are running (server location)
log('[1] Running python processes:')
r = subprocess.run(['wmic', 'process', 'where', "name='python.exe'",
                    'get', 'ProcessId,CommandLine', '/format:list'],
                   capture_output=True, text=True)
for line in (r.stdout or '').splitlines():
    line = line.strip()
    if line and '=' in line:
        log('   ' + line[:200])
log('')

# 2. Does runtime/agent have the launcher?
log('[2] runtime\\agent files:')
ag = os.path.join(BASE, 'runtime', 'agent')
if os.path.isdir(ag):
    for f in sorted(os.listdir(ag)):
        log('   ' + f)
else:
    log('   [MISSING] ' + ag)
log('')

# 3. Does runtime/server/app.py exist?
log('[3] runtime\\server:')
sv = os.path.join(BASE, 'runtime', 'server')
if os.path.isdir(sv):
    log('   app.py exists: ' + str(os.path.isfile(os.path.join(sv, 'app.py'))))
else:
    log('   [MISSING] ' + sv)
log('')

# 4. Old location still there?
log('[4] Old server-code-deploy:')
if os.path.isdir(OLD):
    log('   exists: True')
    log('   agent launcher exists: ' + str(os.path.isfile(os.path.join(OLD, 'agent', 'tradotcom_launcher.bat'))))
else:
    log('   exists: False')
log('')

# 5. HTTP check
log('[5] HTTP checks:')
for url in ('http://127.0.0.1:80/', 'http://127.0.0.1:80/api/agent-download'):
    try:
        import urllib.request
        code = urllib.request.urlopen(url, timeout=5).getcode()
        log('   %s -> %s' % (url, code))
    except Exception as e:
        log('   %s -> ERROR: %s' % (url, e))
log('')
log('=' * 50)

# write log
logpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vps_check_log.txt')
with open(logpath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('')
print('Log written to: ' + logpath)
