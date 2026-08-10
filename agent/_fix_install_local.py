# 修：install-local 函數頭 + 搬熱鍵函數出嚟（module 級）
p = 'server/app.py'
with open(p, encoding='utf-8') as f:
    text = f.read()

# 1. 搵 decorator + 熱鍵 comment 位置
marker = """@app.route('/api/ea-library/install-local/<filename>', methods=['POST'])
@login_required
# ═══════════════════════════════════════════════════════════
# 🎯 熱鍵管理"""

if marker not in text:
    print('❌ marker 唔啱')
else:
    # 2. 喺 decorator 後插入函數頭
    fixed = """@app.route('/api/ea-library/install-local/<filename>', methods=['POST'])
@login_required
def api_ea_install_local(filename):
    \"\"\"將 EA 倉庫（官方/社群/用戶）嘅 EA 複製去本機 MT5 Experts 目錄 — 配對庫即刻見到
    聯動：EA 倉庫「移去配對」/ 上傳自己 EA 之後自動安裝落本機
    \"\"\"
# ═══════════════════════════════════════════════════════════
# 🎯 熱鍵管理"""
    text = text.replace(marker, fixed)
    print('已插入函數頭')

    # 3. 搬熱鍵函數出嚟（module 級 — 喺 install-local 之前定義）
    # 熱鍵函數區塊（# ═══熱鍵管理 到 get_hotkey 結尾）
    hk_start = text.index('# ═══════════════════════════════════════════════════════════\n# 🎯 熱鍵管理')
    # get_hotkey 結尾 = install-local docstring 之前（"\"\"\"將 EA 倉庫"）
    doc_marker = '    """將 EA 倉庫（官方/社群/用戶）'
    hk_end = text.index(doc_marker)
    hk_block = text[hk_start:hk_end]
    # 移除原位置（留空）
    text = text[:hk_start] + text[hk_end:]
    # 插入去 install-local 函數之後（module 級）— 搵 install-local 結尾（下一個 @app.route 或者 def）
    # 搵「return jsonify({"success": True, "filename": filename」之後嘅下一個 @app.route
    ret_marker = 'return jsonify({\n        "success": True,\n        "filename": filename'
    ri = text.index(ret_marker)
    # 搵呢個 return 嘅函數結尾（下一個 @app.route）
    next_route = text.index('@app.route', ri)
    text = text[:next_route] + hk_block + '\n\n' + text[next_route:]
    print('已搬熱鍵函數')

    with open(p, 'w', encoding='utf-8') as f:
        f.write(text)
    print('完成')
