# 徹底重組 install-local + 熱鍵區塊
p = 'server/app.py'
with open(p, encoding='utf-8') as f:
    text = f.read()

a = text.index("@app.route('/api/ea-library/install-local/<filename>', methods=['POST'])")
b = text.index('def _mt5_hotkeys_ini():')
# 第二個 route（真正 install-local）
c = text.index("@app.route('/api/ea-library/install-local/<filename>', methods=['POST'])", b)
d = text.index('def api_ea_install_local(filename):', c)
e = text.index('    import shutil as _sh', d)
# 內容結尾（install-local return 之後嘅下一個 @app.route）
inst_marker = '"installed": installed,'
inst_pos = text.index(inst_marker, e)
f = text.index('@app.route', inst_pos)

# 提取：熱鍵函數（module 級 — b 到 c）
hk_block = text[b:c].rstrip() + '\n\n\n'
# 內容（e 到 f）
body = text[e:f].rstrip() + '\n'

# 新 install-local 頭
head = """@app.route('/api/ea-library/install-local/<filename>', methods=['POST'])
@login_required
def api_ea_install_local(filename):
    \"\"\"將 EA 倉庫（官方/社群/用戶）嘅 EA 複製去本機 MT5 Experts 目錄 — 配對庫即刻見到
    聯動：EA 倉庫「移去配對」/ 上傳自己 EA 之後自動安裝落本機
    \"\"\"
"""

new_block = head + body + '\n' + hk_block
text = text[:a] + new_block + text[f:]
with open(p, 'w', encoding='utf-8') as f:
    f.write(text)
print(f'完成（區塊 {a}-{f}）')
