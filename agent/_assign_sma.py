import os

def _read_ini():
    data_dir = os.path.join(os.environ['APPDATA'], 'MetaQuotes', 'Terminal')
    for d in os.listdir(data_dir):
        p = os.path.join(data_dir, d, 'config', 'hotkeys.ini')
        if os.path.isfile(p):
            return p
    return None

p = _read_ini()
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

print(f'而家 experts: {experts}')
used = set(experts.values())
candidates = [f'Ctrl+{i}' for i in range(1, 10)] + ['Ctrl+0'] + \
             [f'Ctrl+Alt+{i}' for i in range(1, 10)] + ['Ctrl+Alt+0']
for c in candidates:
    if c not in used:
        experts['Experts\\MT5Cloud_EA\\SMA_Cross.ex5'] = c
        print(f'SMA_Cross → {c}')
        break

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
print('已寫入')
print(f'最終 experts: {experts}')
