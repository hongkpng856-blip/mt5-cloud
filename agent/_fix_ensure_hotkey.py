# server/app.py：部署前確保熱鍵存在（MT5 重啟會覆寫 hotkeys.ini — 未經 GUI 嘅熱鍵會冇）
p = 'server/app.py'
with open(p, encoding='utf-8') as f:
    text = f.read()

# 喺 _restart_mt5 之後加 ensure_hotkey_for_ea
marker = 'def _restart_mt5():'
idx = text.index(marker)
# 搵 _restart_mt5 結尾（下一個 def）
end = text.index('\ndef ', idx + 10)

new_fn = '''

def ensure_hotkey_for_ea(ea_name):
    """部署前確保 EA 有熱鍵（2026-08：MT5 重啟會覆寫 hotkeys.ini — 未經 GUI 設定嘅新 EA 熱鍵會冇）
    冇熱鍵 → 分配 + 關 MT5 → 寫 → 開（reload）→ 返回 True（已就緒）"""
    try:
        experts, indicators, _ = _read_hotkeys_ini()
        # 已有熱鍵
        for k, v in experts.items():
            if ea_name in k:
                return True
        # 冇 → 分配 + 重啟 MT5
        combo = _alloc_hotkey(experts)
        if not combo:
            return False
        experts[f'Experts\\\\MT5Cloud_EA\\\\{ea_name}.ex5'] = combo
        if _write_hotkeys_ini(experts, indicators):
            print(f"[hotkeys] {ea_name} → {combo}（部署前補熱鍵）")
            _restart_mt5()
            import time as _t
            _t.sleep(50)  # 等 MT5 開 + load 熱鍵
            return True
        return False
    except Exception as e:
        print(f"[hotkeys] ensure 失敗: {e}")
        return False


'''
text = text[:end] + new_fn + text[end:]
print('ensure_hotkey_for_ea 加好')

# deploy 掛接：部署前 ensure_hotkey（喺熱鍵 reload 檢查附近）
old = '''    # 🎯 熱鍵 reload 檢查（2026-08：配對後 hotkeys.ini 有變 → 重啟 MT5 先 load → 部署先 work）
    try:
        if _hotkeys_need_reload():
            print(f"[deploy] hotkeys.ini 有變（未 load）— 重啟 MT5")
            _restart_mt5()
            time.sleep(50)
    except Exception:
        pass'''
new = '''    # 🎯 熱鍵確保（2026-08：MT5 重啟會覆寫 hotkeys.ini — 未經 GUI 嘅熱鍵會冇）
    # 部署前檢查 EA 有冇熱鍵 — 冇就分配 + 重啟 MT5 reload
    try:
        ensure_hotkey_for_ea(ea_name)
    except Exception:
        pass'''
if old in text:
    text = text.replace(old, new)
    print('deploy 掛接更新（ensure_hotkey）')
else:
    print('deploy 掛接位置唔啱 — 檢查')

with open(p, 'w', encoding='utf-8') as f:
    f.write(text)
print('完成')
