"""Try opening the .tpl file with MT5 through shell association."""
import os, time, ctypes, subprocess
from ctypes import wintypes

APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
COMMON_FILES = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
EXPERT_DIR = os.path.join(MT5_DATA, 'MQL5', 'Experts')
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach_log.txt')

SYSTEM_EAS = {'TestBlank.ex5', 'TemplateLoader.ex5', 'AgentHelper.ex5'}

def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

# Check file association for .tpl
import shutil
# Try to open .tpl file with associated program
tpl_path = os.path.join(TPL_DIR, 'AgentHelper_EURUSD_H1.tpl')
print(f"Template: {tpl_path}")
print(f"Exists: {os.path.exists(tpl_path)}")

# Try ShellExecute
user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32

# ShellExecute(hwnd, operation, file, parameters, directory, show_cmd)
result = shell32.ShellExecuteW(None, "open", tpl_path, None, None, 1)
print(f"ShellExecute open: {result} ({result <= 32})")

time.sleep(3)

# Check if any new windows appeared
import psutil
mt5_pid = None
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
        mt5_pid = proc.info['pid']
        break

if mt5_pid:
    pid_buf = ctypes.c_ulong()
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    
    # Check for dialogs
    dialogs = []
    def cb(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if title.value:
                    dialogs.append((cls.value, title.value))
        return True
    user32.EnumWindows(CB(cb), 0)
    if dialogs:
        print(f"Dialogs: {dialogs}")
    else:
        print("No dialogs after ShellExecute")

# Try with "openas" 
print("\nTrying shell command: start .tpl file...")
subprocess.run(['cmd.exe', '/c', 'start', '', tpl_path], shell=True, timeout=5)
time.sleep(3)

# Check again for dialogs
if mt5_pid:
    dialogs = []
    def cb2(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if title.value:
                    dialogs.append((cls.value, title.value))
        return True
    user32.EnumWindows(CB(cb2), 0)
    if dialogs:
        print(f"Dialogs after start: {dialogs}")
    else:
        print("No dialogs after 'start' command")

# Check heartbeats
print("\nChecking heartbeats:")
for f in sorted(os.listdir(COMMON_FILES)) if os.path.exists(COMMON_FILES) else []:
    if f.startswith('hb_'):
        hb_path = os.path.join(COMMON_FILES, f)
        age = time.time() - os.path.getmtime(hb_path)
        name = f[3:-4]
        print(f"  {name}: {age:.0f}s old")
