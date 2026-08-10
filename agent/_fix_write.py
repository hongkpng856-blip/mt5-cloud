# 修 server/app.py 嘅 _write_hotkeys_ini（用戶實測格式）
p = 'server/app.py'
with open(p, encoding='utf-8') as f:
    lines = f.readlines()

start = None
end = None
for i, l in enumerate(lines):
    if l.startswith('def _write_hotkeys_ini('):
        start = i
    if start is not None and i > start and (l.startswith('def ') or l.startswith('@app.route')):
        end = i
        break
if end is None:
    end = len(lines)
print(f'函數範圍: {start}-{end}')

CRLF = chr(13) + chr(10)
new_fn = f'''def _write_hotkeys_ini(experts, indicators):
    """寫回 hotkeys.ini（UTF-16 LE — 用戶實測格式 2026-08-06：
    只有 <experts> section（冇 <indicators>）+ 乾淨 CRLF — MT5 先 load）"""
    p = _mt5_hotkeys_ini()
    if not p:
        return False
    lines = []
    if indicators:
        lines.append('<indicators>')
        for k, v in indicators.items():
            lines.append(f'{{k}}={{v}}')
        lines.append('</indicators>')
        lines.append('')
    lines.append('<experts>')
    for k, v in experts.items():
        lines.append(f'{{k}}={{v}}')
    lines.append('</experts>')
    text = {CRLF!r}.join(lines) + {CRLF!r}
    try:
        with open(p, 'wb') as f:
            f.write(text.encode('utf-16'))
        print(f"[hotkeys] 已寫入 {{p}}")
        return True
    except Exception as e:
        print(f"[hotkeys] 寫入失敗: {{e}}")
        return False


'''

if start is not None:
    lines = lines[:start] + [new_fn] + lines[end:]
    with open(p, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print('已替換')
else:
    print('搵唔到函數')
