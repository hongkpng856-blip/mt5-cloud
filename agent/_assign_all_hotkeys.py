import sys, os, json
sys.path.insert(0, 'server')
sys.path.insert(0, '.')
os.environ.setdefault('APPDATA', os.environ.get('APPDATA', ''))

# 直接 import app 嘅熱鍵函數（唔起 server）
import importlib.util
spec = importlib.util.spec_from_file_location('app_mod', 'server/app.py')
app_mod = importlib.util.module_from_spec(spec)

# 偷雞：直接執行熱鍵函數（複製邏輯 — 避免 import 成個 Flask app）
def _read_ini():
    data_dir = os.path.join(os.environ['APPDATA'], 'MetaQuotes', 'Terminal')
    for d in os.listdir(data_dir):
        p = os.path.join(data_dir, d, 'config', 'hotkeys.ini')
        if os.path.isfile(p):
            return p
    return None

def _parse():
    p = _read_ini()
    if not p:
        return {}, {}
    with open(p, 'rb') as f:
        raw = f.read()
    text = raw.decode('utf-16')
    experts, indicators = {}, {}
    section = None
    for line in text.splitlines():
        ls = line.strip()
        if ls.endswith('\r'):
            ls = ls[:-1]
        if ls.startswith('[') and ls.endswith(']'):
            section = ls[1:-1]
        elif '=' in ls and section:
            k, v = ls.split('=', 1)
            if section == 'experts':
                experts[k] = v
            elif section == 'indicators':
                indicators[k] = v
    return experts, indicators

def _write(experts, indicators):
    p = _read_ini()
    lines = ['<indicators>']
    for k, v in indicators.items():
        lines.append(f'{k}={v}')
    lines.append('</indicators>')
    lines.append('')
    lines.append('<experts>')
    for k, v in experts.items():
        lines.append(f'{k}={v}')
    lines.append('</experts>')
    text = '\r\n'.join(lines) + '\r\n'
    with open(p, 'wb') as f:
        f.write(text.encode('utf-16'))
    print(f'已寫入 {p}')

# 已配對 EA（DB config）
import sqlite3
db = 'server/instance/mt5cloud.db'
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT ea_config FROM user WHERE username='dev'")
row = cur.fetchone()
config = json.loads(row[0]) if row and row[0] else {}
conn.close()

ea_names = set()
for key in config:
    base = key
    for suffix in ('_lot', '_magic', '_tf'):
        if key.endswith(suffix):
            base = key[:-len(suffix)]
            break
    if base and base not in ('_lot', '_magic', '_tf'):
        ea_names.add(base)

experts, indicators = _parse()
used = set(experts.values())
candidates = [f'Ctrl+{i}' for i in range(1, 10)] + ['Ctrl+0'] + \
             [f'Ctrl+Alt+{i}' for i in range(1, 10)] + ['Ctrl+Alt+0']

print(f'已配對 EA: {sorted(ea_names)}')
for ea in sorted(ea_names):
    if any(ea in k for k in experts):
        print(f'  {ea}: 已有熱鍵（保留）')
        continue
    for c in candidates:
        if c not in used:
            experts[f'Experts\\MT5Cloud_EA\\{ea}.ex5'] = c
            used.add(c)
            print(f'  {ea} → {c}')
            break
    else:
        print(f'  {ea}: 冇可用熱鍵！')

_write(experts, indicators)
