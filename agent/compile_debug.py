"""Try different MetaEditor compilation approaches."""
import os, subprocess, time

MT5_DIR = r'C:\Program Files\MetaTrader 5'
ME_EXE = os.path.join(MT5_DIR, 'MetaEditor64.exe')
APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
SCRIPTS_DIR = os.path.join(MT5_DATA, 'MQL5', 'Scripts')
mq5_path = os.path.join(SCRIPTS_DIR, 'BatchApplyTemplates.mq5')
ex5_path = os.path.join(SCRIPTS_DIR, 'BatchApplyTemplates.ex5')

# Save old mtime
old_mtime = os.path.getmtime(ex5_path) if os.path.exists(ex5_path) else 0

# Approach 1: /compile:
print("=== Approach 1: /compile:path /s ===")
result = subprocess.run([ME_EXE, f'/compile:{mq5_path}', '/s'], capture_output=True, timeout=30)
print(f"returncode: {result.returncode}")
out = result.stdout.decode('utf-8', errors='replace')
err = result.stderr.decode('utf-8', errors='replace')
if out.strip(): print(f"stdout: {out.strip()[:300]}")
if err.strip(): print(f"stderr: {err.strip()[:300]}")

new_mtime = os.path.getmtime(ex5_path) if os.path.exists(ex5_path) else 0
print(f"ex5 age: old={old_mtime} new={new_mtime} changed={new_mtime != old_mtime}")
if new_mtime != old_mtime:
    print("✅ Compiled successfully!")
else:
    print("❌ Not recompiled")
    
    # Approach 2: /compile (space)
    print("\n=== Approach 2: /compile path /log ===")
    result2 = subprocess.run([ME_EXE, '/compile', mq5_path, '/log'], capture_output=True, timeout=30)
    print(f"returncode: {result2.returncode}")
    out2 = result2.stdout.decode('utf-8', errors='replace')
    err2 = result2.stderr.decode('utf-8', errors='replace')
    if out2.strip(): print(f"stdout: {out2.strip()[:300]}")
    if err2.strip(): print(f"stderr: {err2.strip()[:300]}")
    
    # Check compilation log
    log_dir = os.path.join(MT5_DATA, 'MQL5', 'Logs')
    if os.path.exists(log_dir):
        logs = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')], reverse=True)
        if logs:
            latest = os.path.join(log_dir, logs[0])
            mtime = os.path.getmtime(latest)
            if time.time() - mtime < 60:  # Recent log
                with open(latest, 'r', encoding='utf-16-le', errors='replace') as f:
                    print(f"\n  Latest MQL5 log ({latest}):")
                    for line in f.readlines()[-30:]:
                        print(f"    {line.rstrip()}")
    
    new_mtime2 = os.path.getmtime(ex5_path) if os.path.exists(ex5_path) else 0
    print(f"ex5 age: old={old_mtime} new={new_mtime2} changed={new_mtime2 != old_mtime}")
    if new_mtime2 != old_mtime:
        print("✅ Compiled successfully!")
    else:
        # Approach 3: Maybe we need to specify full path differently
        print("\n=== Approach 3: /compile: with spaces in path ===")
        # The path has spaces in "Program Files" - maybe quoting issue
        result3 = subprocess.run(
            [ME_EXE, f'/compile:"{mq5_path}"', '/s'],
            capture_output=True, timeout=30)
        print(f"returncode: {result3.returncode}")
        out3 = result3.stdout.decode('utf-8', errors='replace')
        err3 = result3.stderr.decode('utf-8', errors='replace')
        if out3.strip(): print(f"stdout: {out3.strip()[:300]}")
        if err3.strip(): print(f"stderr: {err3.strip()[:300]}")
        
        new_mtime3 = os.path.getmtime(ex5_path) if os.path.exists(ex5_path) else 0
        print(f"ex5 age: old={old_mtime} new={new_mtime3} changed={new_mtime3 != old_mtime}")
