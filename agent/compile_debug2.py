"""
Debug MetaEditor compilation.
"""
import os, subprocess, time

MT5_DIR = r'C:\Program Files\MetaTrader 5'
ME_EXE = os.path.join(MT5_DIR, 'MetaEditor64.exe')
APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
SCRIPTS_DIR = os.path.join(MT5_DATA, 'MQL5', 'Scripts')
mq5_path = os.path.join(SCRIPTS_DIR, 'BatchApplyTemplates.mq5')
ex5_path = os.path.join(SCRIPTS_DIR, 'BatchApplyTemplates.ex5')

# Also set a simple environment variable for MQL5 includes
my_env = os.environ.copy()
my_env['MQL5_INCLUDE_PATH'] = os.path.join(MT5_DIR, 'MQL5', 'Include')
my_env['MQL5_DATA_PATH'] = MT5_DATA

print(f"MQ5: {mq5_path}")
print(f"EX5: {ex5_path}")
print(f"ME: {ME_EXE}")
print(f"Include: {os.path.join(MT5_DIR, 'MQL5', 'Include')}")

# Try all known MetaEditor compilation flags
approaches = [
    (['/compile', mq5_path, '/s'], "space"),
    ([f'/compile:{mq5_path}', '/s'], "colon"),
    (['/compile', f'"{mq5_path}"', '/s'], "space-quoted"),
    ([f'/compile:"{mq5_path}"', '/s'], "colon-quoted"),
    (['-compile:' + mq5_path, '-s'], "dash-colon"),
    (['compile:' + mq5_path, 's'], "no-dash"),
    # Try running in the scripts directory
]

for args, label in approaches:
    print(f"\n--- {label} ---")
    print(f"  Args: {args}")
    
    # Save old mtime
    old_mtime = os.path.getmtime(ex5_path) if os.path.exists(ex5_path) else 0
    
    # Run with working directory set
    result = subprocess.run(
        [ME_EXE] + args,
        capture_output=True, timeout=30,
        cwd=SCRIPTS_DIR,
        env=my_env
    )
    
    stdout = result.stdout.decode('utf-8', errors='replace').strip()
    stderr = result.stderr.decode('utf-8', errors='replace').strip()
    
    new_mtime = os.path.getmtime(ex5_path) if os.path.exists(ex5_path) else 0
    changed = new_mtime != old_mtime
    
    print(f"  returncode: {result.returncode}")
    if stdout: print(f"  stdout: {stdout[:200]}")
    if stderr: print(f"  stderr: {stderr[:200]}")
    print(f"  ex5 changed: {changed} (old={old_mtime} new={new_mtime})")
    
    # Check if error log was created
    me_log = os.path.join(MT5_DATA, 'MQL5', 'Logs', 'compile.log')
    if os.path.exists(me_log):
        with open(me_log, 'rb') as f:
            content = f.read().decode('utf-16-le', errors='replace')
        if content.strip():
            print(f"  Compile log ({len(content)} chars): {content[:300]}")
    
    if changed:
        print("  ✅ COMPILED SUCCESSFULLY!")
        break

# If none worked, let's try running MetaEditor interactively to see what it can do
# Try to start MetaEditor briefly (just to see if it opens)
print("\n\n--- Trying to open MetaEditor briefly ---")
proc = subprocess.Popen([ME_EXE], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(5)
if proc.poll() is None:
    print("MetaEditor opened (PID={})".format(proc.pid))
    proc.kill()
    time.sleep(1)
    print("Killed")
else:
    stdout, stderr = proc.communicate()
    print(f"Returned immediately: {proc.returncode}")
    print(f"stdout: {stdout.decode('utf-8', errors='replace')[:200]}")
    print(f"stderr: {stderr.decode('utf-8', errors='replace')[:200]}")
