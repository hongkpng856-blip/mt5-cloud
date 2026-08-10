import os, sys
sys.path.insert(0, 'server')

def _read_ini():
    data_dir = os.path.join(os.environ['APPDATA'], 'MetaQuotes', 'Terminal')
    for d in os.listdir(data_dir):
        p = os.path.join(data_dir, d, 'config', 'hotkeys.ini')
        if os.path.isfile(p):
            return p
    return None

def _parse():
    p = _read_ini()
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

# 正確分配：Bollinger = Ctrl+1（用戶設過），SMA_Cross = Ctrl+2
experts, indicators = _parse()
experts['Experts\\MT5Cloud_EA\\Bollinger_Band.ex5'] = 'Ctrl+1'
experts['Experts\\MT5Cloud_EA\\SMA_Cross.ex5'] = 'Ctrl+2'
_write(experts, indicators)
print(f'最終 experts: {experts}')
