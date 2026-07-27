import os, subprocess, sys, time

server_dir = r'C:\Users\hongk\Desktop\mt5-cloud\server'
os.chdir(server_dir)
env = os.environ.copy()
env['PORT'] = '5002'

proc = subprocess.Popen(
    [sys.executable, '-c', '''
import os
os.environ["PORT"] = "5002"
from app import app, socketio
socketio.run(app, host="0.0.0.0", port=5002, debug=True)
'''],
    cwd=server_dir,
    env=env
)
time.sleep(3)
print(f'Server PID={proc.pid} on port 5002')
