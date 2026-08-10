"""
Auto-attach all EAs that are registered but not running.
Checks heartbeat freshness, deploys via auto_attach.py, and logs results.
"""
import os
import sys
import time
import subprocess
import psutil
from pywinauto import Application
from pywinauto.keyboard import send_keys

# ── Config ──
MT5_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'
EXPERTS_DIR = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts'
COMMON_FILES = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\Common\Files'
LOG_FILE = r'C:\Users\hongk\Desktop\mt5-cloud\agent\auto_attach_log.txt'
ATTACH_SCRIPT = r'C:\Users\hongk\Desktop\mt5-cloud\agent\auto_attach.py'

SYSTEM_EAS = {'TestBlank.ex5', 'TemplateLoader.ex5', 'AgentHelper.ex5'}
HEARTBEAT_MAX_AGE = 60  # seconds


def log(msg):
    """Append to log file."""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f'[{timestamp}] {msg}\n')
    print(f'[{timestamp}] {msg}')


def get_eas():
    """List all .ex5 files in Experts dir, excluding system files."""
    eas = []
    for f in os.listdir(EXPERTS_DIR):
        if f.endswith('.ex5') and f not in SYSTEM_EAS:
            eas.append(f[:-4])  # Remove .ex5
    return sorted(eas)


def check_heartbeat(ea_name):
    """Check if heartbeat file exists and is fresh (<60s old)."""
    hb_file = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
    if os.path.exists(hb_file):
        age = time.time() - os.path.getmtime(hb_file)
        if age < HEARTBEAT_MAX_AGE:
            # Try to read content
            try:
                with open(hb_file, 'rb') as f:
                    raw = f.read()
                content = raw.decode('utf-16-le', errors='replace').strip().lstrip('\ufeff')
            except:
                content = '?'
            return True, age, content
        return False, age, 'stale'
    return False, None, 'missing'


def start_mt5():
    """Start MT5 and wait for it to be ready (no blocking dialogs)."""
    subprocess.Popen([MT5_PATH])
    
    start = time.time()
    while time.time() - start < 120:
        pid = None
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
                pid = proc.info['pid']
                break
        
        if pid:
            try:
                app = Application(backend='uia').connect(process=pid)
                win = app.top_window()
                if win.is_visible():
                    # Check for blocking dialogs
                    if not win.is_enabled():
                        # Try to close dialogs
                        send_keys('{ESC}')
                        time.sleep(0.5)
                        send_keys('%{F4}')
                        time.sleep(0.5)
                    else:
                        print(f'MT5 ready, PID={pid}')
                        return pid
            except:
                pass
        time.sleep(2)
    
    print('MT5 failed to become ready')
    return None


def main():
    log('=' * 60)
    log('Starting auto-attach job')
    log('=' * 60)
    
    # Get all EAs
    all_eas = get_eas()
    log(f'Found {len(all_eas)} EAs: {", ".join(all_eas)}')
    
    # Check heartbeats
    to_deploy = []
    alive = []
    for ea in all_eas:
        has_hb, age, content = check_heartbeat(ea)
        if has_hb:
            alive.append((ea, age, content))
            log(f'  ✓ {ea}: heartbeat {age:.0f}s old → SKIP')
        else:
            to_deploy.append(ea)
            if content == 'missing':
                log(f'  ✗ {ea}: no heartbeat → DEPLOY')
            else:
                log(f'  ✗ {ea}: heartbeat {age:.0f}s old (stale) → DEPLOY')
    
    log(f'\n{alive} EAs running, {len(to_deploy)} need deployment')
    
    if not to_deploy:
        log('All EAs are running. Nothing to do.')
        return
    
    # Start MT5 if not running
    pid = None
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            pid = proc.info['pid']
            break
    
    if not pid:
        log('Starting MT5...')
        pid = start_mt5()
        if not pid:
            log('FATAL: Could not start MT5')
            return
    
    log(f'MT5 running (PID={pid})')
    
    # Deploy each EA
    success_count = 0
    fail_count = 0
    
    for i, ea in enumerate(to_deploy):
        log(f'\n--- Deploying {ea} ({i+1}/{len(to_deploy)}) ---')
        
        # Run auto_attach.py
        attach_script = ATTACH_SCRIPT
        python_exe = sys.executable
        
        cmd = f'"{python_exe}" -u "{attach_script}" --ea {ea} --symbol EURUSD --tf H1 --restart'
        
        log(f'Running: {cmd}')
        
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=250,
            cwd=r'C:\Users\hongk\Desktop\mt5-cloud'
        )
        
        output = result.stdout + result.stderr
        
        # Check for success
        if 'SUCCESS' in output:
            log(f'  ✅ {ea}: SUCCESS (heartbeat detected)')
            success_count += 1
        elif 'heartbeat not detected' in output:
            log(f'  ⚠️ {ea}: Script ran but no heartbeat (may need manual check)')
            fail_count += 1
        else:
            log(f'  ❌ {ea}: FAILED')
            log(f'     Output: {output[-500:]}')
            fail_count += 1
        
        # Brief delay between deployments
        time.sleep(2)
    
    # Summary
    log(f'\n{"=" * 60}')
    log(f'Summary: {success_count} deployed, {fail_count} failed out of {len(to_deploy)} needed')
    log(f'{"=" * 60}')


if __name__ == '__main__':
    main()
