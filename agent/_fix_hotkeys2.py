import os

p = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\config\hotkeys.ini'
with open(p, 'rb') as f:
    raw = f.read()
text = raw.decode('utf-16')
experts, indicators = {}, {}
section = None
for line in text.splitlines():
    ls = line.strip().replace('\r', '')
    if ls.startswith('[') and ls.endswith(']'):
        section = ls[1:-1]
    elif '=' in ls and section:
        k, v = ls.split('=', 1)
        if section == 'experts':
            experts[k] = v
        elif section == 'indicators':
            indicators[k] = v

print(f'而家: {experts}')
used = set(experts.values())
candidates = [f'Ctrl+{i}' for i in range(1, 10)] + ['Ctrl+0'] + \
             [f'Ctrl+Alt+{i}' for i in range(1, 10)] + ['Ctrl+Alt+0']

# Divergence + Heikin_Ashi（已配對有 .ex5）
for ea in ('Divergence', 'Heikin_Ashi'):
    if any(ea in k for k in experts):
        print(f'{ea}: 已有熱鍵（保留）')
        continue
    for c in candidates:
        if c not in used:
            experts[f'Experts\\MT5Cloud_EA\\{ea}.ex5'] = c
            used.add(c)
            print(f'{ea} → {c}')
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
print(f'最終: {experts}')
