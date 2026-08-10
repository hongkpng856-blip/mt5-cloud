# 部署 4 個 EA 去 4 個唔同圖表（平鋪 → click 圖表 → 熱鍵）
import sys, subprocess, time, ctypes
sys.path.insert(0, 'agent')
import pyautogui
pyautogui.FAILSAFE = False
from pywinauto import Application
from pywinauto.keyboard import send_keys
user32 = ctypes.windll.user32

out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
lines = out.stdout.decode('utf-8', errors='replace').strip().splitlines()
pid = None
for line in lines:
    parts = [p.strip().strip('"') for p in line.split(',')]
    if len(parts) >= 2 and parts[0] == 'terminal64.exe' and parts[1].isdigit():
        pid = int(parts[1]); break
app = Application(backend='win32').connect(process=pid, timeout=8)
win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
win.set_focus()
time.sleep(1)

# 平鋪圖表（Alt+R）
send_keys('%r')
time.sleep(3)

# 攞主視窗 rect（圖表區）
r = win.rectangle()
print(f'主視窗: {r}')
cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
print(f'圖表區中央: ({cx}, {cy})')

# 部署 4 個 EA（click 圖表中央 4 個位置 → 熱鍵）
# 平鋪後 29 個圖表 — 揀左上 4 個（大概位置）
EAS = [('Swing_Trader', '^1'), ('TestRunner', '^2'), ('Trend_Follow', '^3'), ('Volume_Spike', '^4')]
chart_w, chart_h = 400, 300  # 大概每個圖表大細
for i, (ea, combo) in enumerate(EAS):
    # 每個圖表位置（左上角開始 — 網格）
    col = i % 4
    row = i // 4
    x = r.left + 100 + col * 250
    y = r.top + 120 + row * 200
    print(f'\n=== {ea} → click ({x},{y}) + {combo} ===')
    pyautogui.click(x, y)
    time.sleep(1)
    send_keys(combo)
    time.sleep(3)
    # 處理 dialog（代替確認/Properties）
    for _ in range(3):
        dlg = None
        for w in app.windows():
            try:
                if w.class_name() == '#32770':
                    dlg = w
                    break
            except Exception:
                pass
        if dlg:
            t = dlg.window_text()
            print(f'  Dialog: [{t[:40]}]')
            # 代替確認 → 撳「是」；Properties → 撳「確定」
            if '代替' in t:
                for b in dlg.descendants():
                    try:
                        if b.class_name() == 'Button' and ('是' in b.window_text() or 'Yes' in b.window_text()):
                            b.click(); print('  撳「是」'); break
                    except Exception:
                        pass
            else:
                for b in dlg.descendants():
                    try:
                        if b.class_name() == 'Button' and ('確定' in b.window_text() or 'OK' in b.window_text()):
                            b.click(); print('  撳「確定」'); break
                    except Exception:
                        pass
            time.sleep(2)
        else:
            break
    time.sleep(2)

print('\n完成 — 檢查心跳')
