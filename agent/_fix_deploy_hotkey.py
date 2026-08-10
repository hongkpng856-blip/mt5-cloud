# server/app.py 加熱鍵 reload 檢查 + 部署掛接
p = 'server/app.py'
with open(p, encoding='utf-8') as f:
    text = f.read()

# 1. 加 _hotkeys_need_reload + _restart_mt5 函數（喺 get_hotkey 之後）
marker = 'def get_hotkey(ea_name):'
anchor = marker
idx = text.index(anchor)
# 搵 get_hotkey 函數結尾（下一個 @app.route）
end_marker = text.index('@app.route', idx)

new_fns = '''def _mt5_start_time():
    """MT5 進程啟動時間（epoch）— 用 wmic"""
    import subprocess as _sp
    try:
        out = _sp.run('wmic process where "name=terminal64.exe" get CreationDate /value',
                      shell=True, capture_output=True)
        for line in out.stdout.decode('utf-8', errors='replace').splitlines():
            if 'CreationDate' in line:
                v = line.split('=')[1].strip()
                # YYYYMMDDHHMMSS.mmmmmm+000
                import datetime as _dt
                return _dt.datetime.strptime(v[:14], '%Y%m%d%H%M%S').timestamp()
    except Exception:
        pass
    return 0


def _hotkeys_need_reload():
    """hotkeys.ini 有冇新過 MT5 啟動（有 = 熱鍵未 load — 要重啟 MT5）"""
    try:
        p = _mt5_hotkeys_ini()
        if not p or not os.path.isfile(p):
            return False
        ini_mtime = os.path.getmtime(p)
        mt5_start = _mt5_start_time()
        # MT5 未開 → 唔需要 reload（開嗰陣會 load）
        if mt5_start == 0:
            return False
        return ini_mtime > mt5_start + 5
    except Exception:
        return False


def _restart_mt5():
    """重啟 MT5（關 → 開 — reload hotkeys.ini）— 2026-08 用戶實測：熱鍵要重啟先 load"""
    try:
        import subprocess as _sp
        _sp.run('taskkill -f -im terminal64.exe', shell=True, capture_output=True)
        time.sleep(3)
        mt5_exe = os.environ.get('MT5_EXE_PATH', r'C:\\Program Files\\MetaTrader 5\\terminal64.exe')
        _sp.Popen([mt5_exe])
        print("[hotkeys] MT5 已重啟（reload 熱鍵）")
        return True
    except Exception as e:
        print(f"[hotkeys] 重啟 MT5 失敗: {e}")
        return False


'''
text = text[:end_marker] + new_fns + text[end_marker:]

# 2. deploy 掛接（寫 deploy_cmd 之前 — 檢查熱鍵需唔需要 reload）
old_deploy = '''    # Write deploy command file (watcher will pick it up)'''
new_deploy = '''    # 🎯 熱鍵 reload 檢查（2026-08：配對後 hotkeys.ini 有變 → 重啟 MT5 先 load → 部署先 work）
    try:
        if _hotkeys_need_reload():
            print(f"[deploy] hotkeys.ini 有變（未 load）— 重啟 MT5")
            _restart_mt5()
            time.sleep(50)
    except Exception:
        pass

    # Write deploy command file (watcher will pick it up)'''
if old_deploy in text:
    text = text.replace(old_deploy, new_deploy)
    print('deploy 掛接成功')
else:
    print('deploy 掛接位置唔啱 — 檢查')

with open(p, 'w', encoding='utf-8') as f:
    f.write(text)
print('完成')
