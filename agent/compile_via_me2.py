"""
Last attempt: use MetaEditor to compile via shell edit verb.
"""
import os, time, ctypes, subprocess

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32

APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
ME_PATH = r'C:\Program Files\MetaTrader 5\MetaEditor64.exe'
mq5_path = os.path.join(MT5_DATA, 'MQL5', 'Scripts', 'BatchApplyTemplates.mq5')
ex5_path = os.path.join(MT5_DATA, 'MQL5', 'Scripts', 'BatchApplyTemplates.ex5')

old_mtime = os.path.getmtime(ex5_path) if os.path.exists(ex5_path) else 0

# First, kill existing MetaEditor
subprocess.run(['taskkill', '/f', '/im', 'MetaEditor64.exe'], capture_output=True, timeout=5)
time.sleep(2)

# Open the .mq5 file with MetaEditor
print(f"Opening {mq5_path} with MetaEditor...")
proc = subprocess.Popen([ME_PATH, mq5_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Wait for MetaEditor to open
time.sleep(5)

# Check if it's running
if proc.poll() is None:
    print(f"MetaEditor opened (PID={proc.pid})")
    
    # Find the MetaEditor main window
    me_hwnd = user32.FindWindowW('MetaQuotes::MetaEditor::5.00', None)
    if me_hwnd:
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(ctypes.c_void_p(me_hwnd), title, 512)
        print(f"  Window title: '{title.value}'")
        
        # Bring to foreground
        user32.SetForegroundWindow(ctypes.c_void_p(me_hwnd))
        time.sleep(1)
        
        # Send F7 to compile
        print("  Sending F7 (compile)...")
        # Use keybd_event for more reliable key input
        ctypes.windll.user32.keybd_event(0x76, 0, 0, 0)  # F7 down
        time.sleep(0.1)
        ctypes.windll.user32.keybd_event(0x76, 0, 2, 0)  # F7 up
        time.sleep(5)
        
        # Check if ex5 updated
        new_mtime = os.path.getmtime(ex5_path) if os.path.exists(ex5_path) else 0
        print(f"  EX5 changed: {new_mtime != old_mtime}")
        
        # Close MetaEditor
        print("  Closing MetaEditor...")
        user32.PostMessageW(ctypes.c_void_p(me_hwnd), 0x0010, 0, 0)
        time.sleep(3)
        
        if proc.poll() is None:
            proc.kill()
            time.sleep(1)
        
        new_mtime2 = os.path.getmtime(ex5_path) if os.path.exists(ex5_path) else 0
        print(f"  EX5 changed: {new_mtime2 != old_mtime}")
        
        if new_mtime2 != old_mtime:
            print("✅ COMPILATION SUCCESSFUL!")
        else:
            print("❌ Compilation did not update ex5")
            
            # Try with Ctrl+F7 (also compile in some versions)
            print("  Trying Ctrl+F7...")
            proc2 = subprocess.Popen([ME_PATH, mq5_path])
            time.sleep(5)
            me_hwnd2 = user32.FindWindowW('MetaQuotes::MetaEditor::5.00', None)
            if me_hwnd2:
                ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)  # Ctrl down
                time.sleep(0.1)
                ctypes.windll.user32.keybd_event(0x76, 0, 0, 0)  # F7 down
                time.sleep(0.1)
                ctypes.windll.user32.keybd_event(0x76, 0, 2, 0)  # F7 up
                time.sleep(0.1)
                ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)  # Ctrl up
                time.sleep(5)
                
                new_mtime3 = os.path.getmtime(ex5_path) if os.path.exists(ex5_path) else 0
                print(f"  After Ctrl+F7: changed={new_mtime3 != old_mtime}")
                
                user32.PostMessageW(ctypes.c_void_p(me_hwnd2), 0x0010, 0, 0)
                time.sleep(2)
                if proc2.poll() is None:
                    proc2.kill()
else:
    stdout, stderr = proc.communicate(timeout=5)
    print(f"MetaEditor returned: {proc.returncode}")
    print(f"stdout: {stdout.decode('utf-8', errors='replace')[:200]}")
    print(f"stderr: {stderr.decode('utf-8', errors='replace')[:200]}")
