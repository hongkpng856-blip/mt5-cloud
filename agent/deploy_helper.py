import subprocess, os, time

# Direct attach: this is simpler than auto_attach.py's full flow
MT5_DATA = "C:/Users/hongk/AppData/Roaming/MetaQuotes/Terminal/D0E8209F77C8CF37AD8BF550E51FF075"
ex5 = os.path.join(MT5_DATA, "MQL5", "Experts", "AgentHelper.ex5")
print(f".ex5 size: {os.path.getsize(ex5)} bytes")

# Create template for AgentHelper 
tpl_dir = os.path.join(MT5_DATA, "Profiles", "Templates")
tpl = os.path.join(tpl_dir, "AgentHelper_EURUSD_H1.tpl")

if not os.path.exists(tpl):
    import shutil
    for f in os.listdir(tpl_dir):
        if f.endswith('.tpl') and 'ADX' in f:
            shutil.copy2(os.path.join(tpl_dir, f), tpl)
            print(f"Template created from {f}")
            break

# Now use the full auto_attach.py but with a timeout
print("Running auto_attach.py...")
result = subprocess.run([
    'python', 'C:/Users/hongk/Desktop/mt5-cloud/agent/auto_attach.py',
    '--ea', 'AgentHelper', '--symbol', 'EURUSD', '--tf', 'H1'
], capture_output=True, text=True, timeout=180,
   cwd='C:/Users/hongk/Desktop/mt5-cloud/agent')

print(f"Exit: {result.returncode}")
print(f"Stdout:\n{result.stdout[-1000:]}")
if result.stderr:
    print(f"Stderr:\n{result.stderr[-500:]}")