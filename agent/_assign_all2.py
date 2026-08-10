# 為所有已配對 EA 分配熱鍵（關 MT5 → 寫 → 開）
import os

p = r'C:\Users\hongk\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\config\hotkeys.ini'
with open(p, 'rb') as f:
    raw = f.read()
text = raw.decode('utf-16')
experts = {}
section = None
for line in text.splitlines():
    ls = line.strip().replace(chr(13), '')
    if ls.startswith('<') and ls.endswith('>'):
        section = ls[1:-1]
    elif '=' in ls and section == 'experts':
        k, v = ls.split('=', 1)
        experts[k] = v

# 已配對 EA（有 .ex5）
ea_list = ['Bollinger_Band', 'Breakout', 'Divergence', 'EMA_Cross', 'Grid_Trading', 'Heikin_Ashi', 'SMA_Cross']
used = set(experts.values())
candidates = [f'Ctrl+{i}' for i in range(1, 10)] + ['Ctrl+0'] + \
             [f'Ctrl+Alt+{i}' for i in range(1, 10)] + ['Ctrl+Alt+0']

print(f'而家熱鍵: {experts}')
for ea in ea_list:
    if any(ea in k for k in experts):
        print(f'  {ea}: 已有（保留）')
        continue
    for c in candidates:
        if c not in used:
            experts[f'Experts\\MT5Cloud_EA\\{ea}.ex5'] = c
            used.add(c)
            print(f'  {ea} → {c}')
            break

# 寫（用戶格式：只有 <experts> + 乾淨 CRLF）
lines = ['<experts>']
for k, v in experts.items():
    lines.append(f'{k}={v}')
lines.append('</experts>')
text = '\r\n'.join(lines) + '\r\n'
with open(p, 'wb') as f:
    f.write(text.encode('utf-16'))
print('已寫入（關 MT5 後開會 load）')
