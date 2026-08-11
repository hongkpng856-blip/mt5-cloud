# 監察 steps 檔案（錄 log — 搵「彈嚟彈去」真正根源）
import json
import os
import time

STEPS = r'C:\Users\hongk\Desktop\mt5-cloud\agent\.ai_control.steps'
LOG = r'C:\Users\hongk\Desktop\mt5-cloud\agent\steps_monitor.log'

last_content = None
last_mtime = 0

with open(LOG, 'w', encoding='utf-8') as logf:
    logf.write(f"[{time.strftime('%H:%M:%S')}] 監察開始\n")
    logf.flush()
    while True:
        try:
            if os.path.isfile(STEPS):
                mtime = os.path.getmtime(STEPS)
                with open(STEPS, 'r', encoding='utf-8') as f:
                    raw = f.read()
                if raw != last_content or mtime != last_mtime:
                    last_content = raw
                    last_mtime = mtime
                    try:
                        d = json.loads(raw)
                        brief = [(s.get('text', '')[:14], s.get('status', '?')) for s in d]
                    except Exception:
                        brief = f'JSON 損壞: {raw[:60]}'
                    logf.write(f"[{time.strftime('%H:%M:%S')}] mtime={mtime} 內容: {brief}\n")
                    logf.flush()
            else:
                if last_content is not None:
                    last_content = None
                    logf.write(f"[{time.strftime('%H:%M:%S')}] ⚠️ steps 檔案被刪除\n")
                    logf.flush()
        except Exception as e:
            pass
        time.sleep(0.15)
