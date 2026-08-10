"""Try various ways to apply a .tpl template via MT5."""
import os, time, ctypes, subprocess

APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
TEMPLATES_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
MT5_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'

tpl = os.path.join(TEMPLATES_DIR, 'ADX_Trend_EURUSD_H1.tpl')
print(f"Template: {tpl}")

# Try 1: Run MT5 with template as argument
print("\n1. MT5 with template as arg...")
proc = subprocess.Popen([MT5_PATH, tpl], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(3)
proc.kill()
print("   Done (killed after 3s)")

# Reset: close any MT5 instances
subprocess.run(['taskkill.exe', '/f', '/im', 'terminal64.exe'], capture_output=True, timeout=5)
time.sleep(3)

# Try 2: Run MT5 with /template argument
print("\n2. MT5 with /template arg...")
proc = subprocess.Popen([MT5_PATH, '/template', tpl], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(3)
proc.kill()
print("   Done (killed after 3s)")

# Reset
subprocess.run(['taskkill.exe', '/f', '/im', 'terminal64.exe'], capture_output=True, timeout=5)
time.sleep(3)

# Try 3: Use MT5's portable mode with profile
print("\n3. MT5 with /portable /profile...")
proc = subprocess.Popen([MT5_PATH, '/portable'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(3)
proc.kill()
print("   Done (killed after 3s)")

# Reset
subprocess.run(['taskkill.exe', '/f', '/im', 'terminal64.exe'], capture_output=True, timeout=5)
time.sleep(3)

# Try 4: Copy template to a location where drag-drop would work
print("\n4. Start MT5 normally and check args...")
MT5_DATA_DIR = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'D0E8209F77C8CF37AD8BF550E51FF075')

# Check MT5 command line help
print("\n5. MT5 command-line help...")
proc = subprocess.run([MT5_PATH, '/help'], capture_output=True, timeout=5)
print(f"  stdout: {proc.stdout.decode('utf-8', errors='replace')[:500]}")
print(f"  stderr: {proc.stderr.decode('utf-8', errors='replace')[:500]}")

# Check if MT5 has any documented CLI args
print("\n6. MT5 /? ...")
proc = subprocess.run([MT5_PATH, '/?'], capture_output=True, timeout=5)
print(f"  stdout: {proc.stdout.decode('utf-8', errors='replace')[:500]}")
print(f"  stderr: {proc.stderr.decode('utf-8', errors='replace')[:500]}")
