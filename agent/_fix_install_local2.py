# 徹底修復 install-local 區塊（955-1154）
p = 'server/app.py'
with open(p, encoding='utf-8') as f:
    text = f.read()

# 搵 955 開始（route）+ 真正內容開始（import shutil）
route_marker = "@app.route('/api/ea-library/install-local/<filename>', methods=['POST'])\n@login_required\ndef api_ea_install_local(filename):"
first_route = text.index(route_marker)
content_marker = '    import shutil as _sh'
content_start = text.index(content_marker)

# 提取熱鍵函數（nested 嗰堆 — _mt5_hotkeys_ini 到 _restart_mt5 結尾）
hk_start = text.index('def _mt5_hotkeys_ini():', first_route)
# _restart_mt5 結尾 = 第二個 route 之前
second_route = text.index("@app.route('/api/ea-library/install-local/<filename>', methods=['POST'])", content_start)
hk_block = text[hk_start:second_route].rstrip() + '\n\n\n'

# 真正 install-local 內容（import shutil 之後 — 到函數結尾）
# 函數結尾 = 熱鍵 assign 之後嘅 return jsonify（搵「"installed": installed」之後嘅下一個 def/@app.route）
inst_marker = '"installed": installed,'
inst_pos = text.index(inst_marker, content_start)
# 搵下一個 @app.route（install-local 之後）
next_route = text.index('@app.route', inst_pos)
install_body = text[content_start:next_route].rstrip() + '\n'

# 重建
new_block = """@app.route('/api/ea-library/install-local/<filename>', methods=['POST'])
@login_required
def api_ea_install_local(filename):
    \"\"\"將 EA 倉庫（官方/社群/用戶）嘅 EA 複製去本機 MT5 Experts 目錄 — 配對庫即刻見到
    聯動：EA 倉庫「移去配對」/ 上傳自己 EA 之後自動安裝落本機
    \"\"\"
""" + install_body + '\n' + hk_block

text = text[:first_route] + new_block + text[next_route:]
with open(p, 'w', encoding='utf-8') as f:
    f.write(text)
print('重建完成')
