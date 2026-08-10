"""
Deploy all EAs using auto_attach.py for each one.
Processes EAs sequentially, skipping those with fresh heartbeats.
"""
import os, sys, time, subprocess, ctypes

MT5_DATA = os.path.join(os.environ.get('APPDATA', ''),
    'MetaQuotes', 'Terminal', 'D0E8209F77C8CF37AD8BF550E51FF075')
COMMON_FILES = os.path.join(os.environ.get('APPDATA', ''),
    'MetaQuotes', 'Terminal', 'Common', 'Files')
EXPERT_DIR = os.path.join(MT5_DATA, 'MQL5', 'Experts')
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach_log.txt')
AUTO_ATTACH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach.py')
SYSTEM_EAS = {'TestBlank.ex5', 'TemplateLoader.ex5', 'AgentHelper.ex5'}

def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def check_heartbeat(ea_name):
    """Check if EA heartbeat exists and is fresh (<60s)"""
    hb_file = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
    if not os.path.exists(hb_file):
        return False
    age = time.time() - os.path.getmtime(hb_file)
    return age < 60

def deploy_ea(ea_name):
    """Deploy a single EA, return (success, output)"""
    cmd = [
        sys.executable, AUTO_ATTACH,
        '--ea', ea_name,
        '--symbol', 'EURUSD',
        '--tf', 'H1'
    ]
    print(f"  Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, cwd=os.path.dirname(AUTO_ATTACH),
            capture_output=True, text=True, timeout=130
        )
        output = result.stdout + result.stderr
        success = 'SUCCESS' in result.stdout
        return success, output
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT (130s)"
    except Exception as e:
        return False, str(e)

def main():
    # List all EAs
    all_ex5 = [f for f in os.listdir(EXPERT_DIR) if f.endswith('.ex5')]
    ea_names = sorted([f[:-4] for f in all_ex5 if f not in SYSTEM_EAS])
    
    print(f"Found {len(ea_names)} EAs")
    
    # Ensure MT5 is running (start if not)
    import psutil
    mt5_running = False
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            mt5_running = True
            break
    
    if not mt5_running:
        print("Starting MT5...")
        MT5_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'
        subprocess.Popen([MT5_PATH])
        time.sleep(60)
        print("MT5 started")
    
    results = {}
    
    for i, ea_name in enumerate(ea_names, 1):
        print(f"\n[{i}/{len(ea_names)}] {ea_name}")
        
        # Check heartbeat
        if check_heartbeat(ea_name):
            print(f"  ✅ Heartbeat fresh, skipping")
            results[ea_name] = ('SKIPPED', 'heartbeat fresh')
            continue
        
        # Deploy
        print(f"  ⏳ Deploying...")
        success, output = deploy_ea(ea_name)
        
        if success:
            print(f"  ✅ SUCCESS")
            results[ea_name] = ('SUCCESS', '')
        else:
            print(f"  ❌ FAILED")
            results[ea_name] = ('FAILED', output[-200:])
        
        # Small pause
        time.sleep(2)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  DEPLOYMENT SUMMARY")
    print(f"{'='*60}")
    
    success_count = sum(1 for v in results.values() if v[0] == 'SUCCESS')
    skip_count = sum(1 for v in results.values() if v[0] == 'SKIPPED')
    fail_count = sum(1 for v in results.values() if v[0] == 'FAILED')
    
    print(f"  SUCCESS: {success_count}")
    print(f"  SKIPPED: {skip_count}")
    print(f"  FAILED:  {fail_count}")
    print(f"  TOTAL:   {len(results)}")
    
    if fail_count > 0:
        print(f"\n  Failed EAs:")
        for name, (status, err) in results.items():
            if status == 'FAILED':
                print(f"    - {name}: {err[:100]}")
    
    # Heartbeat check
    print(f"\n  Final Heartbeat Status:")
    for ea_name in ea_names:
        hbf = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
        if os.path.exists(hbf):
            age = time.time() - os.path.getmtime(hbf)
            icon = '✅' if age < 120 else '⚠️'
            print(f"    {icon} {ea_name}: {round(age)}s old")
        else:
            print(f"    ❌ {ea_name}: no heartbeat")
    
    log(f"SUMMARY: {success_count} success, {skip_count} skipped, {fail_count} failed")

if __name__ == '__main__':
    main()
