"""Start MT5 Cloud server on port 5001 with new code"""
import os, sys, subprocess, time

# Set port
env = os.environ.copy()
env['PORT'] = '5001'

server_dir = r'C:\Users\hongk\Desktop\mt5-cloud\server'
os.chdir(server_dir)

proc = subprocess.Popen(
    [sys.executable, 'app.py'],
    cwd=server_dir,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT
)

# Wait for startup
time.sleep(3)
print(f'Server PID={proc.pid} on port 5001')
