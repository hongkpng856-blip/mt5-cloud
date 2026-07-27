import os, subprocess, time

# Start on port 5001
server_dir = r'C:\Users\hongk\Desktop\mt5-cloud\server'
env = os.environ.copy()
env['PORT'] = '5001'
proc = subprocess.Popen(['python', 'app.py'], cwd=server_dir, env=env)
print(f'Server started on port 5001 (PID {proc.pid})')
