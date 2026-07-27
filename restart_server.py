import os, signal, time, subprocess

# Kill any python on port 5000
result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
for line in result.stdout.split('\n'):
    if ':5000' in line and 'LISTENING' in line:
        parts = line.strip().split()
        pid = parts[-1]
        if pid.isdigit():
            try:
                os.kill(int(pid), signal.SIGTERM)
                print(f'Killed PID {pid}')
            except:
                pass

time.sleep(2)

# Start new server
server_dir = r'C:\Users\hongk\Desktop\mt5-cloud\server'
os.chdir(server_dir)
subprocess.Popen(['python', 'app.py'], cwd=server_dir)
print('Server restarted!')
