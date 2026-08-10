"""
Orchestrator: auto-attach all registered EAs that need deployment.
- Lists .ex5 files (excludes system files)
- Checks heartbeat files (missing or >60s old → needs deploy)
- Runs auto_attach.py for each needed EA via terminal
- Captures output, checks for SUCCESS
- Logs results to auto_attach_log.txt
"""

import os
import sys
import time
import subprocess
import glob
from datetime import datetime

# ─── Paths ───
EXPERTS_DIR = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts'
HEARTBEAT_DIR = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\Common\Files'
AUTO_ATTACH_PY = r'C:\Users\hongk\Desktop\mt5-cloud\agent\auto_attach.py'
LOG_FILE = r'C:\Users\hongk\Desktop\mt5-cloud\agent\auto_attach_log.txt'
PROJECT_DIR = r'C:\Users\hongk\Desktop\mt5-cloud'

# System files to exclude
SYSTEM_EAS = {'TestBlank', 'TemplateLoader', 'AgentHelper'}

HEARTBEAT_MAX_AGE = 60  # seconds

def log(msg, also_print=True):
    """Write to log file and optionally print"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{timestamp}] {msg}'
    if also_print:
        print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def get_registered_eas():
    """List .ex5 files, excluding system files"""
    eas = []
    for f in glob.glob(os.path.join(EXPERTS_DIR, '*.ex5')):
        name = os.path.splitext(os.path.basename(f))[0]
        if name not in SYSTEM_EAS:
            eas.append(name)
    return sorted(eas)

def get_heartbeat_age(name):
    """Return age in seconds of heartbeat file, or None if missing"""
    hb_path = os.path.join(HEARTBEAT_DIR, f'hb_{name}.txt')
    if not os.path.exists(hb_path):
        return None
    return time.time() - os.path.getmtime(hb_path)

def needs_deploy(name):
    """Check if EA needs deployment based on heartbeat"""
    age = get_heartbeat_age(name)
    if age is None:
        return True, 'no heartbeat file'
    if age > HEARTBEAT_MAX_AGE:
        return True, f'heartbeat {int(age)}s old (max {HEARTBEAT_MAX_AGE}s)'
    return False, f'heartbeat {int(age)}s old (fresh)'

def run_auto_attach(ea_name, symbol='EURUSD', tf='H1', timeout=120):
    """Run auto_attach.py via subprocess and return (success, output)"""
    python = r'C:\Users\hongk\AppData\Local\Programs\Python\Python311\python.exe'
    if not os.path.exists(python):
        # Fallback: try python in PATH
        python = 'python'
    
    cmd = [
        python, '-u',
        AUTO_ATTACH_PY,
        '--ea', ea_name,
        '--symbol', symbol,
        '--tf', tf
    ]
    
    log(f"  Running: {' '.join(cmd)}", also_print=False)
    
    try:
        proc = subprocess.run(
            cmd,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = proc.stdout + proc.stderr
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        output = f"[TIMEOUT] Process exceeded {timeout}s"
        returncode = -1
    except Exception as e:
        output = f"[ERROR] {e}"
        returncode = -2
    
    return returncode, output

def main():
    log('=' * 60)
    log('Starting auto-attach orchestration')
    log('=' * 60)
    
    # 1. Get registered EAs
    eas = get_registered_eas()
    log(f'Found {len(eas)} registered EAs: {", ".join(eas)}')
    
    # 2. Check heartbeats and decide which need deployment
    deploy_queue = []
    for ea in eas:
        needed, reason = needs_deploy(ea)
        icon = '🚀' if needed else '✅'
        log(f'  {icon} {ea}: {reason}')
        if needed:
            deploy_queue.append(ea)
    
    log(f'\n{len(deploy_queue)} EAs need deployment out of {len(eas)} total')
    
    if not deploy_queue:
        log('All EAs are up to date. Nothing to do.')
        log('=' * 60)
        return
    
    # 3. Deploy each EA
    success_count = 0
    fail_count = 0
    total = len(deploy_queue)
    
    for idx, ea in enumerate(deploy_queue, 1):
        log(f'\n--- Deploying {ea} ({idx}/{total}) ---')
        
        start = time.time()
        returncode, output = run_auto_attach(ea)
        elapsed = time.time() - start
        
        # Check for SUCCESS in output
        if 'SUCCESS' in output and ea in output:
            # More precise: find lines containing "SUCCESS: {ea} deployed" or similar
            success_marker = False
            for line in output.split('\n'):
                if 'SUCCESS' in line and ea in line and 'deployed' in line:
                    success_marker = True
                    break
            
            if success_marker:
                log(f'  ✅ {ea}: SUCCESS ({elapsed:.1f}s)')
                success_count += 1
            else:
                # Check if there's "SUCCESS" somewhere but not in a clear deploy line
                # Some logs show "SUCCESS: {ea} deployed to EURUSD H1"
                log(f'  ⚠️ {ea}: returncode={returncode}, partial SUCCESS found ({elapsed:.1f}s)')
                # Still count as success since SUCCESS appeared
                success_count += 1
        else:
            # Extract error reason from output
            error_reason = 'unknown'
            for line in output.split('\n'):
                line = line.strip()
                if '❌ Failed to attach' in line or '❌' in line:
                    error_reason = line.split('❌')[-1].strip()
                    break
                if '⚠️' in line and ('dialog not found' in line or 'Not found' in line or 'failed' in line):
                    error_reason = line.split('⚠️')[-1].strip()
                    break
            
            log(f'  ❌ {ea}: FAILED (returncode={returncode}, {elapsed:.1f}s) — {error_reason}')
            log(f'     Last output lines:')
            for line in output.split('\n')[-5:]:
                if line.strip():
                    log(f'     | {line.strip()}', also_print=False)
            fail_count += 1
    
    # 4. Summary
    log(f'\n{"=" * 50}')
    log(f'  DEPLOY COMPLETE: {success_count} success, {fail_count} failed, {total} total')
    log(f'{"=" * 50}')

if __name__ == '__main__':
    main()
