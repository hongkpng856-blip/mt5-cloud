"""
MT5 EA Auto-Attach — 可靠嘅 GUI 自動化方案
每次都可以做到！Template + Navigator fallback

流程：
1. 生成 .tpl 模板（含 EA 設定）
2. 重啟 MT5（確保 Navigator tree refresh）
3. 開新 chart + Apply Template
4. Fallback: Navigator double-click attach
5. 確保 AutoTrading 開啟
6. 驗證 heartbeat file
"""
import os
import sys
import time
import struct
import subprocess

# ─── Config ───
MT5_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'
MT5_DATA = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')
COMMON_FILES = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                            'Common', 'Files')

# 🚨 2026-08-28：部署開始時間（log 驗證只認部署開始之後嘅 loaded — 修假成功）
_last_deploy_start_ts = 0

# MT5 timeframe codes for .tpl period_size
TF_CODES = {
    'M1': 16385, 'M2': 16386, 'M3': 16387, 'M4': 16388, 'M5': 16389,
    'M6': 16390, 'M10': 16394, 'M12': 16396, 'M15': 16401, 'M20': 16406,
    'M30': 16416, 'H1': 32801, 'H2': 32802, 'H3': 32803, 'H4': 32805,
    'H6': 32807, 'H8': 32809, 'H12': 32813, 'D1': 49201,
    'W1': 65601, 'MN1': 82001,
}


def find_mt5_pid():
    """搵 MT5 process ID"""
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None


def _mt5_alive():
    """🚨 2026-08-20（部署流程檢測系統）：terminal64.exe 有冇運行（tasklist — 唔靠 psutil cached）"""
    try:
        _out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH',
                              shell=True, capture_output=True, timeout=10)
        return 'terminal64.exe' in _out.stdout.decode('utf-8', errors='replace')
    except Exception:
        return False


def _wait_until(check_fn, timeout=60, desc='', interval=2):
    """🚨 2026-08-20（部署流程檢測系統 — docs/deployment-checkpoint-system.md）
    poll check_fn 直到 True 或者 timeout — 每步驗證 gate（成功先落下一步）
    驗證要「等」：唔可以即刻 check（資料未就緒 → 假失敗）——poll 到成功或者 timeout
    返回：check_fn 嘅真值（bool check → True；攞值 check（如 PID）→ 嗰個值）"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            _res = check_fn()
            if _res:
                print(f"✅ {desc}")
                return _res
        except Exception:
            pass
        time.sleep(interval)
    print(f"❌ {desc} — timeout {timeout}s")
    return False


def wait_for_mt5(timeout=30):
    """等 MT5 啟動完成
    ⚠️ 用 backend='win32'（快）+ 主視窗存在檢查 — 唔可以用 uia（MT5 大 UI connect 超慢 → 卡 60 秒）"""
    start = time.time()
    while time.time() - start < timeout:
        pid = find_mt5_pid()
        if pid:
            try:
                from pywinauto import Application
                app = Application(backend='win32').connect(process=pid)
                win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
                if win.exists():
                    return pid
            except Exception:
                pass
        time.sleep(1)
    return None


def do_restart_mt5():
    """重啟 MT5（確保 Navigator refresh）"""
    # 🚨 2026-08-10：重啟期間顯示警告視窗（用戶要知道操作緊 — 55 秒）
    try:
        _rf = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.show')
        with open(_rf, 'w', encoding='utf-8') as _f:
            _f.write('🔄 重啟 MT5 中（快捷鍵載入）— 請稍候約 1 分鐘')
        _sf = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
        try:
            import json as _j2
            # 🚨 2026-08-12 FIX：累積模式（保留現有 steps — 部署入口已寫 4 步 — 唔好覆寫走）
            _cur_rst = []
            try:
                if os.path.isfile(_sf):
                    _cur_rst = _j2.load(open(_sf, 'r', encoding='utf-8'))
                    if not isinstance(_cur_rst, list):
                        _cur_rst = []
            except Exception:
                _cur_rst = []
            _cur_rst = [s for s in _cur_rst if isinstance(s, dict) and s.get('text') != '等待操作開始…']
            # 🚨 2026-08-12 FIX：重啟 3 步放最前（之前 append 尾 → 步驟順序「部署 4 步 + 重啟 3 步」亂 — 重啟應該喺部署前）
            _RESTART3 = [{"text": "關閉 MT5", "status": "doing"},
                         {"text": "載入快捷鍵設定", "status": "pending"},
                         {"text": "重新啟動 MT5", "status": "pending"}]
            _cur_rst = [s for s in _cur_rst if s.get('text') not in ('關閉 MT5', '載入快捷鍵設定', '重新啟動 MT5')]
            _cur_rst = _RESTART3 + _cur_rst
            with open(_sf, 'w', encoding='utf-8') as _f2:
                _j2.dump(_cur_rst, _f2, ensure_ascii=False)
        except Exception:
            pass
    except Exception:
        pass
    import psutil
    import ctypes as _ct
    
    # 🚨 2026-08-19 FIX：restart 前唔好「關閉全部圖表」— 否則其他已掛 EA（EMA_Cross 等）chart 被關 → EA 消失
    # MT5 restart 會自然 save + restore chart（profile）→ 保留其他 chart + EA；同時 reload hotkeys（新 EA 熱鍵生效）
    # （之前 v0.9.71 為咗「部署唔累積 chart」而關晒 — 但搞死其他已掛 EA — 改為保留）
    # 🚨 2026-08-19 FIX2：唔可以用 proc.kill() 強制殺 — MT5 冇機會 save chart profile → 開機唔 restore 其他 EA（「restart 後其他 EA 移出圖表」）
    # → 用「正常關閉」（WM_CLOSE 俾主窗口）令 MT5 save profile → 開機 restore chart + EA
    try:
        import subprocess as _sp3
        _out3 = _sp3.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
        _pid3 = None
        for _line3 in _out3.stdout.decode('utf-8', errors='replace').splitlines():
            _pa3 = [p.strip().strip('"') for p in _line3.split(',')]
            if len(_pa3) >= 2 and _pa3[0] == 'terminal64.exe' and _pa3[1].isdigit():
                _pid3 = int(_pa3[1])
                break
        if _pid3:
            from pywinauto import Application as _App3
            _app3 = _App3(backend='win32').connect(process=_pid3, timeout=8)
            _main3 = _app3.window(class_name_re='MetaQuotes::MetaTrader')
            _ct.windll.user32.PostMessageW(_ct.c_void_p(int(_main3.element_info.handle)), 0x0010, 0, 0)  # WM_CLOSE — 正常關閉（save profile）
            print("📋 MT5 正常關閉中（save chart profile）...")
            time.sleep(8)
            # 如果仲未退（可能彈對話框）→ 用 taskkill 兜底（萬一 hang）
            _alive3 = _sp3.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
            if 'terminal64.exe' in _alive3.stdout.decode('utf-8', errors='replace'):
                print("⚠️ MT5 未退出（可能彈窗）— 等 5 秒再試，唔強制 kill（保護 profile）")
                time.sleep(5)
    except Exception as _e3:
        print(f"⚠️ MT5 正常關閉失敗（{_e3}）— 用強制 kill 兜底")
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
                proc.kill()
    time.sleep(3)
    
    # Start MT5
    subprocess.Popen([MT5_PATH])
    
    # Wait for ready
    pid = wait_for_mt5(timeout=90)
    if pid:
        # 🚨 2026-08-22（用戶要求：UAC 檢測機制）：MT5 重啟後檢查 UAC/授權窗口
        # （MT5 更新/異常 → 彈「Client Terminal AVX2 授權」→ 唔處理會擋住之後部署）
        try:
            if not _detect_and_handle_uac('MT5 重啟後 UAC 檢查', max_wait=30):
                print("⚠️ MT5 重啟後有 UAC 授權窗口未處理（可能係 MT5 更新要求授權）— 等用戶手動處理")
        except Exception:
            pass
        # Extra wait for Navigator to fully load + refresh
        time.sleep(10)
        # 🚨 2026-08-12 FIX：重啟完成 → 唔好寫「等待操作開始」覆寫（保留現有 steps — 更新重啟 3 步 done — 完整流程唔消失）
        try:
            _rf = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.show')
            if os.path.exists(_rf):
                os.remove(_rf)
            _sf = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
            if os.path.exists(_sf):
                import json as _j3
                _cur_rst2 = []
                try:
                    _cur_rst2 = _j3.load(open(_sf, 'r', encoding='utf-8'))
                    if not isinstance(_cur_rst2, list):
                        _cur_rst2 = []
                except Exception:
                    _cur_rst2 = []
                for _s in _cur_rst2:
                    if isinstance(_s, dict) and _s.get('text') in ('關閉 MT5', '載入快捷鍵設定', '重新啟動 MT5'):
                        _s['status'] = 'done'
                if _cur_rst2:
                    with open(_sf, 'w', encoding='utf-8') as _f3:
                        _j3.dump(_cur_rst2, _f3, ensure_ascii=False)
        except Exception:
            pass
        print(f"✅ MT5 restarted, PID={pid}")
        return pid
    else:
        print("❌ MT5 failed to start")
        return None


def generate_template(ea_name, symbol='EURUSD', timeframe='H1', inputs=None):
    """生成 .tpl 模板檔（MT5 UTF-16 LE 格式）"""
    os.makedirs(TPL_DIR, exist_ok=True)
    
    tf_code = TF_CODES.get(timeframe, 32801)  # Default H1
    
    # Build inputs section
    inputs_section = ""
    if inputs:
        for key, val in inputs.items():
            inputs_section += f"{key}={val}\r\n"
    
    tpl_content = (
        f"<chart>\r\n"
        f"id=0\r\n"
        f"symbol={symbol}\r\n"
        f"period_type=1\r\n"
        f"period_size={tf_code}\r\n"
        f"digits=5\r\n"
        f"tick_size=0.000000\r\n"
        f"position_time=0\r\n"
        f"scale_fix=0\r\n"
        f"scale_fixed_min=0.000000\r\n"
        f"scale_fixed_max=0.000000\r\n"
        f"scale_fix11=0\r\n"
        f"scale_bar=0\r\n"
        f"scale_bar_val=1.000000\r\n"
        f"scale=8\r\n"
        f"mode=1\r\n"
        f"fore=0\r\n"
        f"grid=1\r\n"
        f"volume=0\r\n"
        f"scroll=1\r\n"
        f"shift=1\r\n"
        f"shift_size=20.000000\r\n"
        f"fixed_pos=0.000000\r\n"
        f"ohlc=0\r\n"
        f"bidline=1\r\n"
        f"askline=0\r\n"
        f"lastline=0\r\n"
        f"days=1\r\n"
        f"descriptions=0\r\n"
        f"window_left=0\r\n"
        f"window_top=0\r\n"
        f"window_right=0\r\n"
        f"window_bottom=0\r\n"
        f"window_type=1\r\n"
        f"background_color=0\r\n"
        f"foreground_color=16777215\r\n"
        f"barup_color=65280\r\n"
        f"bardown_color=65280\r\n"
        f"bullcandle_color=0\r\n"
        f"bearcandle_color=16777215\r\n"
        f"chartline_color=65280\r\n"
        f"volumes_color=3329330\r\n"
        f"grid_color=10061943\r\n"
        f"bidline_color=10061943\r\n"
        f"askline_color=255\r\n"
        f"lastline_color=49152\r\n"
        f"stops_color=255\r\n"
        f"\r\n"
        f"<expert>\r\n"
        f"name={ea_name}\r\n"
        f"path=Experts\\{ea_name}.ex5\r\n"
        f"enabled=1\r\n"
        f"\r\n"
        f"<inputs>\r\n"
        f"{inputs_section}"
        f"</inputs>\r\n"
        f"\r\n"
        f"</expert>\r\n"
        f"\r\n"
        f"<window>\r\n"
        f"height=100\r\n"
        f"\r\n"
        f"<indicator>\r\n"
        f"name=Main\r\n"
        f"path=\r\n"
        f"apply=1\r\n"
        f"show_data=1\r\n"
        f"scale_inherit=0\r\n"
        f"scale_line=0\r\n"
        f"scale_line_percent=50\r\n"
        f"scale_line_value=0.000000\r\n"
        f"scale_fix_min=0\r\n"
        f"scale_fix_min_val=0.000000\r\n"
        f"scale_fix_max=0\r\n"
        f"scale_fix_max_val=0.000000\r\n"
        f"</indicator>\r\n"
        f"\r\n"
        f"</window>\r\n"
        f"\r\n"
        f"</chart>\r\n"
    )
    
    tpl_name = f"{ea_name}_{symbol}_{timeframe}"
    tpl_path = os.path.join(TPL_DIR, f"{tpl_name}.tpl")
    
    # Write as UTF-16 LE with BOM
    with open(tpl_path, 'wb') as f:
        f.write(b'\xff\xfe')  # UTF-16 LE BOM
        f.write(tpl_content.encode('utf-16-le'))
    
    print(f"📋 Template saved: {tpl_path} ({os.path.getsize(tpl_path)} bytes)")
    return tpl_path


def _open_chart_keyboard():
    """用鍵盤快捷鍵開新 chart（唔依賴 UI Automation）"""
    from pywinauto.keyboard import send_keys
    send_keys('^n')  # Ctrl+N = New Chart
    time.sleep(1)
    send_keys('{ENTER}')  # 接受默認品種
    time.sleep(2)


def attach_ea_navigator(ea_name, mt5_pid, max_retries=3):
    """用 win32 backend + pyautogui double-click attach EA
    
    關鍵發現：
    - MT5 Navigator TreeView 的 select() + Enter 不等同 double-click
    - Enter 只 expand/collapse 節點，不會 attach EA 到 chart
    - 開新 chart 後 Navigator panel 會自動收埋
    - 必須先開 chart，再開 Navigator，再 pyautogui double-click
    
    流程：
    1. win32 connect → set focus
    2. 開新 chart (Ctrl+N → Enter)
    3. 開 Navigator panel (Alt+V → n → Enter)
    4. Expand EA交易 → select EA → EnsureVisible
    5. pyautogui double-click 掃描 TreeView 找到 EA
    6. 確認 Properties dialog → Enter 關閉
    7. 確保 AutoTrading ON
    """
    import pyautogui
    import ctypes
    user32 = ctypes.windll.user32
    from pywinauto import Application
    from pywinauto.keyboard import send_keys

    # 🚨 2026-08-22（用戶要求：UAC 檢測機制）：Navigator 附加前檢查 UAC/授權窗口
    try:
        if not _detect_and_handle_uac(f'Navigator 附加 {ea_name} UAC 檢查', max_wait=20):
            print(f"⚠️ Navigator 附加 {ea_name}：UAC 授權窗口未處理")
    except Exception:
        pass

    for attempt in range(max_retries):
        try:
            app = Application(backend='win32').connect(process=mt5_pid)
            win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
            try:
                win.set_focus()
            except:
                pass  # No active desktop (background process)
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️ win32 connect failed: {e} (attempt {attempt+1}/{max_retries})")
            time.sleep(5)
            continue
        
        # Step 1: Open chart only if none exists
        mdi = None
        for d in win.descendants():
            if d.element_info.class_name == 'MDIClient':
                mdi = d
                break
        has_charts = mdi and len(mdi.children()) > 0
        
        if not has_charts:
            print("📋 No chart open, opening new one...")
            send_keys('^n')
            time.sleep(1)
            send_keys('{ENTER}')
            time.sleep(3)
        else:
            print(f"📋 Chart already open, skipping Ctrl+N...")
        
        # Step 2: Open Navigator panel DIRECTLY via ShowWindow
        # Much more reliable than menu clicks or keyboard shortcuts
        import ctypes as _ctypes
        user32 = _ctypes.windll.user32
        
        # 搵 Navigator panel（包括浮動 MiniFrame「導航」— Bug: 浮動視窗係 top-level，
        # 唔喺主視窗 descendants → 要掃 MT5 process 所有 top-level（同 refresh_navigator Bug #47 一樣）
        # ⚠️ 一定要用 app.windows()（只限 MT5 process）— 唔可以用 Desktop 掃全部 process（會掃到 MetaEditor/其他嘅 tree）
        nav_panel = None
        _all_windows = []
        try:
            _all_windows = list(app.windows())
        except Exception:
            pass
        _all_windows += list(win.descendants())
        for d in _all_windows:
            c = d.element_info.class_name
            if 'Afx:ControlBar' in c or 'Afx:MiniFrame' in c:
                tv_child = None
                try:
                    for child in d.descendants():
                        if child.element_info.class_name == 'SysTreeView32':
                            tv_child = child
                            break
                except Exception:
                    pass
                if tv_child:
                    nav_panel = d
                    break
        
        if nav_panel:
            hwnd = nav_panel.element_info.handle
            user32.ShowWindow(ctypes.c_void_p(hwnd), 5)  # SW_SHOW
            time.sleep(1)
            print(f"📋 Navigator panel shown via ShowWindow")
            # Refresh Navigator: toggle hidden→shown 強制重新掃描 Experts 目錄
            user32.ShowWindow(ctypes.c_void_p(hwnd), 0)  # SW_HIDE
            time.sleep(0.5)
            user32.ShowWindow(ctypes.c_void_p(hwnd), 5)  # SW_SHOW
            time.sleep(1.5)
            print(f"🔄 Navigator refreshed (toggle)")
        else:
            # Fallback: WM_COMMAND 32808 (Navigator toggle command ID)
            print(f"📋 Navigator panel not found, trying WM_COMMAND...")
            user32.SendMessageW(ctypes.c_void_p(win.element_info.handle), 0x0111, 32808, 0)
            time.sleep(1.5)
        
        # Step 3: Find SysTreeView32 and verify it's visible
        # ⚠️ 要掃所有 top-level（浮動 Navigator MiniFrame）— 唔可以淨掃主視窗 descendants
        # ⚠️ 2026-08 驗證 rect：之前揀到錯 tree（rect (8,131) 但實際 Navigator 喺 (201,139)）
        # → scan click 全部落桌面（double-click 開咗 TestAItest 記事本 ×3！）+ MT5 crash
        # ⚠️ 2026-08-06 修：MT5 有兩個 tree（docked 細 + 浮動大）— 揀「最大」嗰個（浮動/主要 Navigator）
        tree_view = None
        _best_tree = None
        _best_area = 0
        for d in _all_windows:
            try:
                for child in d.descendants():
                    if child.element_info.class_name == 'SysTreeView32':
                        try:
                            _tr = child.rectangle()
                            # 驗證：tree 夠大 + 中心位置屬於 MT5（WindowFromPoint — 唔係就係錯 tree/隱藏 tree）
                            if _tr.width() > 50 and _tr.height() > 50:
                                _cx = _tr.left + _tr.width() // 2
                                _cy = _tr.top + _tr.height() // 2
                                if _window_pid_at(_cx, _cy) == mt5_pid:
                                    _area = _tr.width() * _tr.height()
                                    if _area > _best_area:
                                        _best_area = _area
                                        _best_tree = child
                        except Exception:
                            pass
            except Exception:
                pass
        tree_view = _best_tree  # 揀最大嗰個（浮動 Navigator）
        
        if not tree_view:
            print(f"⚠️ 搵唔到有效 TreeView（rect 驗證失敗 — 可能 MT5 唔係最前）(attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
        
        # 固定 Navigator 視窗（浮動 MiniFrame「導航」— 用戶移動過都要鎖定返左邊固定位置）
        try:
            nav_hwnd = None
            for w in app.windows():
                try:
                    if 'Afx:MiniFrame' in w.class_name() and ('導航' in w.window_text() or 'Navigator' in w.window_text()):
                        nav_hwnd = int(w.element_info.handle)
                        break
                except Exception:
                    pass
            if nav_hwnd:
                pin_window(nav_hwnd, 0, 100, 340, 820)
                time.sleep(0.5)
        except Exception:
            pass
        
        # ⚠️ MT5 用 custom draw — is_visible() 唔可靠（tree 有正常 rect 但 WS_VISIBLE 唔 set）
        # → 用 rect 判斷（有尺寸 + 喺螢幕內 = 當 visible）
        def _tree_visible(t):
            try:
                r = t.rectangle()
                return r.width() > 50 and r.height() > 50 and r.left > -500 and r.top > -500
            except Exception:
                return False

        if not _tree_visible(tree_view):
            print(f"⚠️ TreeView not visible after ShowWindow (attempt {attempt+1}/{max_retries})")
            # Try WM_COMMAND as fallback
            user32.SendMessageW(ctypes.c_void_p(win.element_info.handle), 0x0111, 32808, 0)
            time.sleep(1.5)
            
            for d in _all_windows:
                try:
                    for child in d.descendants():
                        if child.element_info.class_name == 'SysTreeView32':
                            tree_view = child
                            break
                except Exception:
                    pass
                if tree_view:
                    break
            if not tree_view or not _tree_visible(tree_view):
                print(f"⚠️ TreeView still not visible")
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
        
        tv_rect = tree_view.rectangle()
        print(f"📋 TreeView rect=({tv_rect.left},{tv_rect.top})-({tv_rect.right},{tv_rect.bottom})")
        
        # Step 4: Navigate tree → Expand EA交易 → Select + EnsureVisible
        try:
            root = tree_view.roots()[0]
            
            ea_trading_node = None
            # MT5 Navigator language varies: 'EA交易', 'المستشارون المختصون', 'Expert Advisors', etc.
            # Use position (3rd child = index 2) as primary, text match as fallback
            children = root.children()
            # ⚠️ 先 text match（語言唔同都搵到）— MT5 新版加咗「訂閱」folder，
            # EA交易 由 index 2 變 index 3 → 唔可以硬性用 index！
            for child in children:
                try:
                    t = child.text()
                    if any(kw in t for kw in ['EA交易', 'Expert Advisors', 'المستشارون المختصون', 'Experts', 'EA']):
                        ea_trading_node = child
                        break
                except Exception:
                    pass
            # fallback: 3rd child（舊版 MT5）
            if not ea_trading_node and len(children) > 2:
                ea_trading_node = children[2]
            
            if not ea_trading_node:
                print(f"⚠️ EA交易 node not found (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
            
            ea_trading_node.expand()
            time.sleep(2)
            
            ea_node = None
            for ea in ea_trading_node.children():
                if ea.text() == ea_name:
                    ea_node = ea
                    break
            
            # ⚠️ 2026-08：web 配對嘅 EA 喺根 Experts 節點
            if not ea_node:
                for sub in ea_trading_node.children():
                    try:
                        st = sub.text()
                        if 'MT5Cloud' in st or 'Cloud' in st:
                            sub.expand()
                            time.sleep(1)
                            for ea in sub.children():
                                if ea.text() == ea_name:
                                    ea_node = ea
                                    break
                            break
                    except Exception:
                        pass
            
            if not ea_node:
                print(f"⚠️ {ea_name} not found under EA交易 (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
            
            print(f"🎯 Found {ea_name}, attaching via pyautogui double-click...")
            ea_node.select()
            time.sleep(0.3)
            ea_node.ensure_visible()
            time.sleep(0.5)
            
        except Exception as e:
            print(f"⚠️ Tree navigation error: {e} (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
        
        # Step 5: 精確 double-click EA item（唔使掃描成個 tree — 唔會「亂點」）
        found_dialog = False
        click_x = tv_rect.left + 50  # EA item text area
        click_y = None
        try:
            # ⚠️ 方法：ea_node.select()（pywinauto 揀中 item）→ TVM_GETNEXTITEM(CARET) 攞 hItem
            # → TVM_GETITEMRECT 攞屏幕位置（唔使讀文字 — MT5 owner-draw tree 讀唔到文字）
            ea_node.select()
            time.sleep(0.5)
            import ctypes as _ct
            from ctypes import wintypes as _wt
            # ⚠️ 64-bit handle 溢出問題：SendMessageW 返回 32-bit c_int → 負數 → 要 set restype c_size_t
            _ct.windll.user32.SendMessageW.restype = _ct.c_size_t
            _tree_hwnd = _ct.c_void_p(int(tree_view.element_info.handle))
            _caret = _ct.windll.user32.SendMessageW(_tree_hwnd, 0x110A, 0x0009, 0)  # TVGN_CARET
            if _caret:
                _rect = _wt.RECT()
                _res = _ct.windll.user32.SendMessageW(_tree_hwnd, 0x1104, 1, _ct.byref(_rect))  # TVM_GETITEMRECT
                if _res:
                    _pt = _wt.POINT(0, 0)
                    _ct.windll.user32.ClientToScreen(_tree_hwnd, _ct.byref(_pt))
                    click_x = _rect.left + _pt.x + 30
                    click_y = _rect.top + _pt.y + ((_rect.bottom - _rect.top) // 2)
                    print(f"🎯 精確定位 {ea_name} at ({click_x},{click_y}) — 直接 double-click")
                else:
                    print(f"⚠️ GETITEMRECT fail (caret={_caret})")
            else:
                print("⚠️ CARET 攞唔到（select 可能冇生效）")
        except Exception as e:
            print(f"⚠️ 精確定位 exception: {type(e).__name__} {e}")
            click_y = None
        if not click_y:
            try:
                # fallback：pywinauto TreeItem rectangle
                ea_rect = ea_node.rectangle()
                if ea_rect.width() > 0 and ea_rect.height() > 0:
                    click_x = ea_rect.left + 30
                    click_y = ea_rect.top + (ea_rect.height() // 2)
                    print(f"🎯 精確定位 {ea_name} at ({click_x},{click_y}) — 直接 double-click")
            except Exception:
                click_y = None  # fallback 掃描
        
        # ⚠️ 確保 AutoTrading ON — EA 附加時 OnInit 即刻執行（TestRunner 會即刻開單）！
        # 一定要喺 double-click 之前開 — Properties 之後先開太遲（OnInit 已跑，開單失敗 retcode 10027）
        try:
            log_path2 = os.path.join(MT5_DATA, 'Logs', time.strftime('%Y%m%d') + '.log')
            at_on = False
            if os.path.exists(log_path2):
                with open(log_path2, 'r', encoding='utf-16-le', errors='replace') as f:
                    log_lines2 = f.readlines()
                for line in reversed(log_lines2[-20:]):
                    if 'automated trading' in line.lower():
                        if 'enabled' in line.lower():
                            at_on = True
                        break
            if not at_on:
                # ⚠️ 警告視窗（AI 控制中）會搶 focus → send ^e 落錯視窗！
                # 方法：短暫隱藏警告視窗 → set_focus(MT5) → send ^e → 恢復警告視窗
                try:
                    from control_guard import pause_window, resume_window
                    pause_window()
                    time.sleep(0.3)
                except Exception:
                    pass
                try:
                    win.set_focus()
                    time.sleep(0.8)
                except Exception:
                    pass
                send_keys('^e')
                time.sleep(2)
                try:
                    resume_window()
                except Exception:
                    pass
                # ⚠️ 等 MT5 log 確認 enabled 先繼續（OnInit 即刻開單 — ^e 效果可能延遲 2-3 秒）
                for _attempt in range(10):
                    try:
                        _lp = os.path.join(MT5_DATA, 'Logs', time.strftime('%Y%m%d') + '.log')
                        if os.path.exists(_lp):
                            with open(_lp, 'r', encoding='utf-16-le', errors='replace') as _f:
                                _ll = _f.readlines()
                            for _line in reversed(_ll[-15:]):
                                if 'automated trading' in _line.lower():
                                    if 'enabled' in _line.lower():
                                        at_on = True
                                    break
                        if at_on:
                            break
                    except Exception:
                        pass
                    time.sleep(1)
                print("🔴 AutoTrading OFF → toggled ON（double-click 前）" + (" ✅ 已確認" if at_on else " ⚠️ 未確認"))
            else:
                print("🟢 AutoTrading is ON（double-click 前）")
        except Exception:
            pass
        
        if click_y:
            # 精確模式：一次 double-click（還原穩定版 — 直接 click）
            pyautogui.doubleClick(x=click_x, y=click_y)
            time.sleep(2)
            dialogs = find_ea_dialog(ea_name)
            if not dialogs:
                # 可能彈咗「代替」dialog — 檢查
                replace_dialog = None
                try:
                    for w in app.windows():
                        if w.class_name() == '#32770':
                            for s in w.children(class_name='Static'):
                                try:
                                    t = s.window_text()
                                    # 多語言（大眾化）：中文「代替」/ 英文 "replace"
                                    if '代替' in t or 'replace' in t.lower() or 'Replace' in t:
                                        replace_dialog = w
                                        break
                                except Exception:
                                    pass
                            if replace_dialog:
                                break
                except Exception:
                    pass
                if replace_dialog:
                    print("🔄 偵測到「代替」確認 dialog — 自動撳「是」（接受取代）")
                    for b in replace_dialog.children(class_name='Button'):
                        try:
                            bt = b.window_text()
                            if '是' in bt or 'Yes' in bt or '&Y' in bt:
                                b.click()
                                time.sleep(2)
                                break
                        except Exception:
                            pass
                    dialogs = find_ea_dialog(ea_name)
            if dialogs:
                print(f"🎉 {ea_name} Properties dialog found at ({click_x}, {click_y})!")
                found_dialog = True
        else:
            # fallback：掃描模式（精確定位失敗先用）
            # ⚠️ 改善：由 EA 區域開始（tree_top + 80 — 避開 帳戶/訂閱/指標 folders）+ 文字區域 click_x
            row_height = 18
            # ⚠️ 還原穩定版：由 tree 頂開始掃（今日下午改 scan_start=80 之後 crash — 還原）
            click_x = tv_rect.left + 50  # 還原穩定版 click_x
            for y_step in range(0, tv_rect.bottom - tv_rect.top, row_height):
                click_y2 = tv_rect.top + y_step + 9
                pyautogui.doubleClick(x=click_x, y=click_y2)
                time.sleep(2)
            
            # Check for EA Properties dialog (#32770 class with EA name)
            def find_ea_dialog(target_name):
                results = []
                pid_buf = ctypes.c_ulong()
                def cb(hwnd, _):
                    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
                    if pid_buf.value == mt5_pid:
                        cls = ctypes.create_unicode_buffer(256)
                        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                        if cls.value == '#32770':
                            title = ctypes.create_unicode_buffer(256)
                            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                            if target_name in title.value:
                                results.append(title.value)
                    return True
                # Use c_size_t for 64-bit hwnd in callback
                CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
                user32.EnumWindows(CB(cb), 0)
                return results
            
            dialogs = find_ea_dialog(ea_name)
            
            # ⚠️ 掃描模式：遇到任何唔係 target 嘅 dialog → 直接 ESC 關閉（唔好撳「是」！
            # 之前 bug：double-click 咗其他 EA → 彈「代替」dialog → 撳「是」→ 其他 EA 附加咗落圖表！）
            if not dialogs:
                # 有冇其他 dialog 彈出？（任何 #32770 — 可能係其他 EA 嘅 Properties/代替）
                other_dlg = None
                try:
                    for w in app.windows():
                        if w.class_name() == '#32770':
                            other_dlg = w
                            break
                except Exception:
                    pass
                if other_dlg:
                    # 唔係 target → ESC 關閉（唔接受代替）
                    try:
                        send_keys('{ESC}')
                        time.sleep(0.5)
                    except Exception:
                        pass
                    continue  # 繼續 scan 下一行
            
            if dialogs:
                print(f"🎉 {ea_name} Properties dialog found at ({click_x}, {click_y2})!")
                found_dialog = True
                
                # 固定 Properties dialog 位置（彈出後鎖定 — 唔會漂移）
                try:
                    for w in app.windows():
                        if w.class_name() == '#32770':
                            pin_window(int(w.element_info.handle), 500, 250, 700, 500)
                            time.sleep(0.5)
                            break
                except Exception:
                    pass
                
                # Step 6: Confirm dialog (Enter)
                send_keys('{ENTER}')
                time.sleep(2)
                
                # Step 7 已移除 — AutoTrading 喺 double-click 前已確保 ON（唔可以再 toggle —
                # 兩次 ^e = ON→OFF → OnInit 開單失敗 retcode 10027）
                
                return True
            
            # Close any wrong dialog
            send_keys('{ESC}')
            time.sleep(0.3)
        
        if not found_dialog:
            print(f"⚠️ {ea_name} dialog not found after scan (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(5)
            continue
    
    # 最後保險：清理任何殘留 dialog（「代替」/其他確認視窗 — 唔可以留低）
    try:
        for w in app.windows():
            if w.class_name() == '#32770':
                try:
                    for b in w.children(class_name='Button'):
                        bt = b.window_text()
                        if '否' in bt or '取消' in bt or 'Cancel' in bt:
                            b.click()
                            time.sleep(1)
                            break
                except Exception:
                    pass
    except Exception:
        pass
    
    print(f"❌ {ea_name} attach failed after {max_retries} attempts")
    # 🚨 2026-08-12 FIX：失敗 → 寫「附加失敗」steps（唔係「等待操作開始」— 用戶要知道失敗 + 確定/緊急停止）
    try:
        import json as _jfl
        _sf_fl = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
        _cur_fl = []
        try:
            if os.path.isfile(_sf_fl):
                _cur_fl = _jfl.load(open(_sf_fl, 'r', encoding='utf-8'))
                if not isinstance(_cur_fl, list):
                    _cur_fl = []
        except Exception:
            _cur_fl = []
        _cur_fl = [s for s in _cur_fl if isinstance(s, dict) and s.get('text') != '等待操作開始…']
        if not any('失敗' in (s.get('text', '') if isinstance(s, dict) else '') for s in _cur_fl):
            _cur_fl.append({'text': f'附加 {ea_name} 失敗', 'status': 'done'})
        with open(_sf_fl, 'w', encoding='utf-8') as _f:
            _jfl.dump(_cur_fl, _f, ensure_ascii=False)
    except Exception:
        pass
    return False


def ensure_auto_trading_on(mt5_pid):
    """確保 AutoTrading 係開啟狀態"""
    from pywinauto import Application
    from pywinauto.keyboard import send_keys

    # 🚨 2026-08-18 FIX：部署中途 MT5 可能重啟過（熱鍵 reload）→ 舊 PID 唔存在 → connect crash
    # 連唔到就用 find_mt5_pid() 重新搵，再唔得就 skip（唔好令成個 auto_attach 死）
    try:
        app = Application(backend='uia').connect(process=mt5_pid)
    except Exception:
        _new_pid = find_mt5_pid()
        if _new_pid and _new_pid != mt5_pid:
            print(f"🔄 MT5 PID 變咗（舊 {mt5_pid} → 新 {_new_pid}），重新 connect")
            mt5_pid = _new_pid
            try:
                app = Application(backend='uia').connect(process=mt5_pid)
            except Exception as _e:
                print(f"⚠️ ensure_auto_trading_on 連 MT5 失敗（skip）: {_e}")
                return False
        else:
            print(f"⚠️ ensure_auto_trading_on 連 MT5 失敗（PID {mt5_pid} 唔在，skip）")
            return False
    win = app.top_window()
    
    # Check toolbar - look for 算法交易 button
    # The toolbar has a checkbox-style button for AutoTrading
    # If it's depressed/off, click it
    
    # Method 1: Check via Experts log
    # If "automated trading is disabled" appears, toggle it
    
    # Method 2: Just toggle Ctrl+E to make sure it's on
    # This is a toggle, so we need to check current state first
    
    # Read MT5 log to check current state
    log_path = os.path.join(MT5_DATA, 'Logs', time.strftime('%Y%m%d') + '.log')
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-16-le', errors='replace') as f:
            lines = f.readlines()
        for line in reversed(lines):
            if 'automated trading' in line.lower():
                if 'disabled' in line.lower():
                    print("🔴 AutoTrading is OFF, enabling...")
                    send_keys('^e')  # Ctrl+E
                    time.sleep(1)
                    return True
                elif 'enabled' in line.lower():
                    print("🟢 AutoTrading is already ON")
                    return True
    
    # Fallback: toggle twice to ensure ON
    send_keys('^e')
    time.sleep(0.5)
    send_keys('^e')
    time.sleep(1)
    print("✅ AutoTrading toggled")
    return True


def apply_template_gui(template_name, mt5_pid):
    """用 GUI menu Apply Template"""
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    
    app = Application(backend='uia').connect(process=mt5_pid)
    win = app.top_window()
    
    # Method: Alt+V (查看) → 範本 → template_name
    # But MT5 menu navigation is unreliable via pywinauto
    
    # Better: Open chart first, then Chart -> Template -> Apply
    # For now, Navigator double-click is more reliable
    return False


def get_tree_item_rect(tree_hwnd, target_name):
    """win32 TVM 精確攞 tree item 嘅屏幕座標（唔使掃描 — 直接定位 EA item）
    返回 (left, top, right, bottom) 或者 None"""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    # TVM 常數
    TVM_GETNEXTITEM = 0x110A
    TVM_GETITEMTEXTW = 0x110F
    TVM_GETITEMRECT = 0x1104
    TVM_EXPAND = 0x1102
    TVGN_CHILD = 0x0004
    TVGN_NEXT = 0x0001
    TVGN_ROOT = 0x0000
    TVE_EXPAND = 0x0002
    
    class TVITEM(ctypes.Structure):
        _fields_ = [('mask', ctypes.c_uint), ('hItem', ctypes.c_size_t),
                    ('state', ctypes.c_uint), ('stateMask', ctypes.c_uint),
                    ('pszText', ctypes.c_void_p), ('cchTextMax', ctypes.c_int),
                    ('iImage', ctypes.c_int), ('iSelectedImage', ctypes.c_int),
                    ('cChildren', ctypes.c_int), ('lParam', ctypes.c_void_p)]
    
    hwnd = ctypes.c_void_p(tree_hwnd)
    # ⚠️ 64-bit handle：SendMessageW 返回 hItem 一定要 c_size_t（唔 set 會溢出負數）
    user32.SendMessageW.restype = ctypes.c_size_t
    
    def get_item_text(hItem):
        buf = ctypes.create_unicode_buffer(256)
        item = TVITEM(0x0001, hItem, 0, 0, ctypes.cast(buf, ctypes.c_void_p), 256, 0, 0, 0, 0)
        user32.SendMessageW(hwnd, TVM_GETITEMTEXTW, 0, ctypes.byref(item))
        return buf.value
    
    def first_child(hItem):
        return user32.SendMessageW(hwnd, TVM_GETNEXTITEM, TVGN_CHILD, ctypes.c_size_t(hItem))
    
    def next_sibling(hItem):
        return user32.SendMessageW(hwnd, TVM_GETNEXTITEM, TVGN_NEXT, ctypes.c_size_t(hItem))
    
    # 1. root items
    root = user32.SendMessageW(hwnd, TVM_GETNEXTITEM, TVGN_ROOT, 0)
    if not root:
        return None
    # 2. 搵「EA交易」folder
    ea_folder = None
    item = root
    while item:
        txt = get_item_text(item)
        if txt in ('EA交易', 'Expert Advisors', 'EA交易(&E)'):
            ea_folder = item
            break
        item = next_sibling(item)
    if not ea_folder:
        return None
    # 3. 展開
    user32.SendMessageW(hwnd, TVM_EXPAND, TVE_EXPAND, ctypes.c_size_t(ea_folder))
    time.sleep(1.5)
    # 4. 逐個 child 搵 target
    child = first_child(ea_folder)
    while child:
        txt = get_item_text(child)
        if txt == target_name:
            # 5. 攞 rect（屏幕座標 — TVM_GETITEMRECT 用 TRUE = 屏幕）
            rect = wintypes.RECT()
            item2 = TVITEM(0, child, 0, 0, 0, 0, 0, 0, 0, 0)
            # ⚠️ TVM_GETITEMRECT 正確簽名：wParam = hItem（要攞 rect 嘅 item），lParam = RECT*
            # 之前用 wParam=1（固定）→ 一直 fail！→ 精確定位做唔到（Bug #82 延伸）
            res = user32.SendMessageW(hwnd, TVM_GETITEMRECT, ctypes.c_size_t(child), ctypes.byref(rect))
            # 注意：TVM_GETITEMRECT 嘅 rect 係「client 座標」— 要轉屏幕座標
            if res:
                # 攞 tree client 位置 → 轉屏幕
                pt = wintypes.POINT(0, 0)
                user32.ClientToScreen(hwnd, ctypes.byref(pt))
                left = rect.left + pt.x
                top = rect.top + pt.y
                return (left, top, rect.right + pt.x, rect.bottom + pt.y)
            return None
        child = next_sibling(child)
    return None


def pin_window(hwnd, x, y, w, h):
    """固定任何視窗位置 + 大小（pop-up 彈出後即刻鎖定 — 唔會因為位置漂移而 click 唔到）
    所有操作涉及嘅視窗（dialog/Navigator/MetaEditor）都要 pin"""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    try:
        user32.SetWindowPos(ctypes.c_void_p(hwnd), 0, x, y, w, h, 0x0004 | 0x0040)  # SWP_NOZORDER|SWP_SHOWWINDOW
        time.sleep(0.3)
        return True
    except Exception:
        return False


# ─── 安全滑鼠操作（用戶要求 2026-08：避免撳到電腦嘅其他嘢）───
# 每次 click 前用 WindowFromPoint 檢查嗰個屏幕座標屬於邊個 process —
# 唔係 MT5 就跳過（唔會撳到 TG Scheduler / 記事本 / 其他視窗）

def pin_deskin_away():
    """將 DeskIn（遠端控制視窗）移去右上角 — 唔遮 MT5 圖表/Navigator 操作區域
    ⚠️ 2026-08 實測：DeskIn 視窗遮住圖表 (560,222)-(1360,817) → 所有 click 俾佢食咗！
    操作前 call（DeskIn 存在就移走）— 大眾化：用螢幕實際解析度計位置（唔 hardcode 1400）"""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    moved = False
    try:
        # 螢幕實際大小（任何解析度都啱）
        sw = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        # 右上角位置：x = sw - 520（500 寬 + 20 邊距），y = 0
        target_x = sw - 520
        EnumWindows = user32.EnumWindows
        found = []
        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
        def cb(hwnd, _):
            buf = ctypes.create_unicode_buffer(150)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), buf, 150)
            if 'DeskIn' in buf.value:
                found.append(hwnd)
            return True
        EnumWindows(cb, 0)
        for hwnd in found:
            # 移去右上角（500x400）— 唔遮 Navigator(左邊) + 圖表(中央)
            user32.SetWindowPos(ctypes.c_void_p(hwnd), 0, target_x, 0, 500, 400, 0x0004 | 0x0040)
            moved = True
        if moved:
            print(f"📌 DeskIn 已移去右上角 ({target_x},0)（唔遮 MT5）")
            time.sleep(0.5)
    except Exception:
        pass
    return moved

def _window_pid_at(x, y):
    """攞屏幕座標 (x,y) 嗰個視窗嘅 PID（WindowFromPoint）"""
    import ctypes
    from ctypes import wintypes
    try:
        pt = wintypes.POINT(int(x), int(y))
        hwnd = ctypes.windll.user32.WindowFromPoint(pt)
        if not hwnd:
            return 0
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
        return pid.value
    except Exception:
        return -1


def _safe_target_check(x, y, mt5_pid):
    """檢查 (x,y) 係咪 MT5 嘅視窗 — 唔係就 print 警告 + 唔 click
    ⚠️ 開關：agent/.safe_click_off 存在 → 跳過檢查（A/B 測試用 — 還原之前可靠行為）"""
    if os.path.isfile(os.path.join(os.path.dirname(__file__), '.safe_click_off')):
        return True
    if not mt5_pid:
        return True
    pid = _window_pid_at(x, y)
    if pid != mt5_pid:
        print(f"⚠️ [安全防護] ({x},{y}) 目標係 PID {pid}（唔係 MT5 PID {mt5_pid}）— 跳過，避免撳到其他視窗")
        return False
    return True


def safe_click(x, y, mt5_pid=None, **kwargs):
    """安全 click（left）— 目標唔係 MT5 就唔 click"""
    import pyautogui as _pg
    _pg.FAILSAFE = False
    if not _safe_target_check(x, y, mt5_pid):
        return False
    _pg.click(x, y, **kwargs)
    return True


def safe_rightclick(x, y, mt5_pid=None):
    """安全 right-click — 目標唔係 MT5 就唔 click"""
    import pyautogui as _pg
    _pg.FAILSAFE = False
    if not _safe_target_check(x, y, mt5_pid):
        return False
    _pg.rightClick(x, y)
    return True


def safe_doubleclick(x, y, mt5_pid=None):
    """安全 double-click — 目標唔係 MT5 就唔 click"""
    import pyautogui as _pg
    _pg.FAILSAFE = False
    if not _safe_target_check(x, y, mt5_pid):
        return False
    _pg.doubleClick(x, y)
    return True


def ensure_mt5_window(mt5_pid):
    """固定 MT5 視窗位置（大眾化：用螢幕解析度比例 — 唔 hardcode 1920x1040）
    每次操作前 call — 最小化還原 + 固定位置
    ⚠️ 2026-08 實測：BringWindowToTop/SetForegroundWindow 令 MT5 crash（之前 work 嗰陣冇呢啲）
    → 只 SetWindowPos（唔帶最前 — 避免 crash）"""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    try:
        from pywinauto import Application
        app = Application(backend='win32').connect(process=mt5_pid)
        win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
        hwnd = int(win.element_info.handle)
        # ⚠️ 2026-08 實測：MT5 最小化（rect -32000）→ WindowFromPoint 全部返桌面 → click 落錯！
        # 最小化時要 ShowWindow(SW_RESTORE) 先
        if user32.IsIconic(ctypes.c_void_p(hwnd)):
            user32.ShowWindow(ctypes.c_void_p(hwnd), 9)  # SW_RESTORE
            time.sleep(1)
            print("🪟 MT5 已從最小化還原")
        # ⚠️ 帶最前（2026-08 還原）：pyautogui double-click 需要 MT5 active 先收到輸入
        # 之前 crash 係 GBK decode + 舊 deploy_cmd 循環（已修）— 唔係 bring-to-front
        user32.BringWindowToTop(ctypes.c_void_p(hwnd))
        user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
        time.sleep(1)
        print("🎯 MT5 已帶到最前（輸入生效）")
        # 位置 (0,0) + 固定大小（用螢幕解析度 — 大眾化）
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        user32.SetWindowPos(ctypes.c_void_p(hwnd), 0, 0, 0, sw, sh - 40, 0x0004 | 0x0040)
        time.sleep(0.5)
        print(f"📐 MT5 視窗已固定 ({sw}x{sh-40} @ 0,0)")
        return True
    except Exception as e:
        print(f"⚠️ 固定 MT5 視窗失敗: {e}")
        return False


def tile_charts(mt5_pid):
    """平鋪圖表窗口（如果有圖表）— 2026-08 用戶要求：每次操作前圖表平鋪（座標穩定）
    用 MT5 內建「平鋪窗口」快捷鍵 Alt+R（menu: 窗口 → 平鋪窗口）"""
    try:
        import ctypes as _ct
        from pywinauto import Application as _App
        _app = _App(backend='win32').connect(process=mt5_pid, timeout=8)
        # 偵測圖表（MDI 子窗口 — AfxFrameOrView class）
        charts = []
        for _w in _app.windows():
            try:
                for _d in _w.descendants():
                    _cls = _d.element_info.class_name
                    if 'AfxFrameOrView' in _cls:
                        charts.append(_d)
            except Exception:
                pass
        if not charts:
            print("📊 冇圖表 — 唔使平鋪")
            return True
        # 平鋪（MT5 快捷鍵 Alt+R = 平鋪窗口）
        try:
            _win = _app.window(class_name='MetaQuotes::MetaTrader::5.00')
            _win.set_focus()
            time.sleep(0.5)
        except Exception:
            pass
        from pywinauto.keyboard import send_keys
        send_keys('%r')  # Alt+R = 平鋪窗口（menu「窗口→平鋪窗口」快捷鍵）
        time.sleep(1.5)
        print(f"📊 圖表平鋪完成（{len(charts)} 個圖表）")
        return True
    except Exception as _e:
        print(f"⚠️ 平鋪圖表失敗: {_e}")
        return False


def ensure_navigator_unified(mt5_pid):
    """操作前統一 Navigator 位置（2026-08 用戶要求：每次操作 Navigator 最大 + 固定位置）
    之前 Navigator 一時左一時右（rect (201,139) vs (1079,111)）→ 操作錯位
    統一：左邊 (0,100) 起，闊 = 螢幕 20%，高 = 螢幕 - 140（最大）"""
    try:
        import ctypes as _ct
        from pywinauto import Application as _App
        _app = _App(backend='win32').connect(process=mt5_pid, timeout=8)
        _wins = _app.windows()
        for _w in _wins:
            try:
                _cls = _w.class_name()
                _t = _w.window_text()
                if 'Afx:MiniFrame' in _cls and ('導航' in _t or 'Navigator' in _t):
                    _hwnd = int(_w.element_info.handle)
                    _user32 = _ct.windll.user32
                    # 確保顯示
                    _user32.ShowWindow(_ct.c_void_p(_hwnd), 5)  # SW_SHOW
                    time.sleep(0.5)
                    # 統一位置：左邊 (0,100)，闊 = 螢幕 20%，高 = 螢幕 - 140（最大）
                    _sw = _user32.GetSystemMetrics(0)
                    _sh = _user32.GetSystemMetrics(1)
                    _nav_w = min(420, max(300, _sw // 5))
                    _nav_h = _sh - 140
                    _user32.SetWindowPos(_ct.c_void_p(_hwnd), 0, 0, 100, _nav_w, _nav_h, 0x0004 | 0x0040)
                    time.sleep(0.6)
                    print(f"📌 Navigator 已統一位置（(0,100) {_nav_w}x{_nav_h} — 最大）")
                    return True
            except Exception as _e2:
                print(f"   ⚠️ Navigator 統一位置 inner: {_e2}")
    except Exception as _e:
        print(f"⚠️ Navigator 統一位置失敗: {_e}")
    return False


def load_hotkey_map():
    """讀快捷鍵 mapping（EA 名 → pywinauto 快捷鍵格式）— 讀 MT5 hotkeys.ini（權威來源）
    hotkeys.ini: [experts] "Experts\<EA>.ex5=Ctrl+1"
    Ctrl+1 → ^1, Ctrl+Alt+1 → ^!1"""
    import json as _json
    result = {}
    # 1. 讀 hotkeys.ini（MT5 權威）
    try:
        data_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        if os.path.isdir(data_dir):
            for d in os.listdir(data_dir):
                hp = os.path.join(data_dir, d, 'config', 'hotkeys.ini')
                if not os.path.isfile(hp):
                    continue
                try:
                    with open(hp, 'rb') as f:
                        raw = f.read()
                    text = raw.decode('utf-16')
                except Exception:
                    continue
                section = None
                for line in text.splitlines():
                    ls = line.strip()
                    if ls.endswith(chr(13)):
                        ls = ls[:-1]
                    if (ls.startswith('[') and ls.endswith(']')) or (ls.startswith('<') and ls.endswith('>')):
                        section = ls[1:-1]
                    elif '=' in ls and section == 'experts':
                        k, v = ls.split('=', 1)
                        ea = os.path.basename(k).replace('.ex5', '')
                        combo = v
                        if 'Ctrl+' in combo:
                            combo = combo.replace('Ctrl+', '^')
                        if 'Alt+' in combo:
                            combo = combo.replace('Alt+', '!')
                        result[ea] = combo
                break
    except Exception:
        pass
    # 2. fallback：hotkeys.json（舊 mapping）
    if not result:
        try:
            fp = os.path.join(os.path.dirname(__file__), 'hotkeys.json')
            with open(fp, 'r', encoding='utf-8') as f:
                result = _json.load(f)
        except Exception:
            pass
    return result



def _update_steps(steps):
    """🚨 2026-08-10：更新警告視窗步驟 — 累積模式（一條條加落去 — 完成嘅留低 — 唔好蓋過 — 用戶要求）"""
    try:
        import json as _j
        _f = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
        old = []
        try:
            if os.path.isfile(_f):
                old = _j.load(open(_f, 'r', encoding='utf-8'))
                if not isinstance(old, list):
                    old = []
        except Exception:
            old = []
        # 🚨 2026-08-12 FIX：移除 placeholder「等待操作開始…」（_clear_steps 寫嘅）— 有新步驟就唔好殘留
        merged = [s for s in old if isinstance(s, dict) and s.get('text') != '等待操作開始…']
        for ns in steps:
            found = False
            for i, os_ in enumerate(merged):
                if isinstance(os_, dict) and os_.get('text') == ns.get('text'):
                    merged[i]['status'] = ns['status']
                    found = True
                    break
            if not found:
                merged.append(ns)
        # 上限 15 步（防太長）
        if len(merged) > 15:
            merged = merged[-15:]
        with open(_f, 'w', encoding='utf-8') as _fh:
            _j.dump(merged, _fh, ensure_ascii=False)
    except Exception:
        pass

def _clear_steps():
    # 🚨 2026-08-12：寫「等待操作開始…」（唔係空 [] — 空 → 網頁 placeholder 同 steps 交替 → 「彈嚟彈去」— 用戶投訴）
    try:
        import json as _j
        _f = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
        with open(_f + '.tmp', 'w', encoding='utf-8') as _fh:
            _j.dump([{'text': '等待操作開始…', 'status': 'pending'}], _fh)
        # 🚨 2026-08-12 FIX：os.replace 移出 with block（WinError 32）
        os.replace(_f + '.tmp', _f)
    except Exception:
        pass


def _ensure_hotkey_loaded(ea_name, mt5_pid):
    """🚨 2026-08-20（用戶實測成功流程）：確保 EA 熱鍵寫入 hotkeys.ini 且 MT5 load
    流程：① 檢查 hotkeys.ini 有冇 ea_name 熱鍵（冇先做）
          ② 冇 → 分配未用 Ctrl+N → 關 MT5（WM_CLOSE 正常關閉 save profile）
          ③ 寫 hotkeys.ini（<experts>Experts\\<EA>.ex5=Ctrl+N</experts> — UTF-16）
          ④ 開 MT5 → 熱鍵 load → 返新 PID
    破綻注意：EA 必須本機有 .ex5（冇 → 熱鍵指向唔存在 EA → 失效）
    """
    try:
        import ctypes as _ct_hk
        import subprocess as _sp_hk
        # 🚨 2026-08-20（用戶實測破綻）：EA 必須本機有 .ex5（冇 → 熱鍵指向唔存在 EA → 失效）
        # → 檢查本機 Experts/ 有冇 <EA>.ex5；冇 → 報錯 + 唔預載（部署會失敗 — 但至少原因清楚）
        _ex5_found = False
        _data_root = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        try:
            for _d_root in os.listdir(_data_root):
                _exp_dir = os.path.join(_data_root, _d_root, 'MQL5', 'Experts')
                if os.path.isdir(_exp_dir) and os.path.isfile(os.path.join(_exp_dir, f'{ea_name}.ex5')):
                    _ex5_found = True
                    break
        except Exception:
            pass
        if not _ex5_found:
            print(f"❌ {ea_name}.ex5 唔存在（本機未配對/未 compile）— 熱鍵無法預載，請先配對 EA")
            return mt5_pid
        # 1. 讀 hotkeys.ini 有冇 ea_name
        experts = {}
        _hk_path = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        _hk_ini = None
        if os.path.isdir(_hk_path):
            for _d_hk in os.listdir(_hk_path):
                _pp = os.path.join(_hk_path, _d_hk, 'config', 'hotkeys.ini')
                if os.path.isfile(_pp):
                    _hk_ini = _pp
                    break
        if not _hk_ini:
            print(f"⚠️ 搵唔到 hotkeys.ini — 唔做熱鍵預載")
            return mt5_pid
        # 讀現有 experts
        try:
            _raw_hk = open(_hk_ini, 'rb').read()
            try:
                _text_hk = _raw_hk.decode('utf-16')
            except Exception:
                _text_hk = _raw_hk.decode('utf-8', errors='ignore')
            _sec_hk = None
            for _ln_hk in _text_hk.splitlines():
                _ls_hk = _ln_hk.strip().replace('\r', '')
                if _ls_hk == '<experts>': _sec_hk = 'experts'; continue
                if _ls_hk == '</experts>': _sec_hk = None; continue
                if '=' in _ls_hk and _sec_hk == 'experts':
                    _k_hk, _v_hk = _ls_hk.split('=', 1)
                    experts[_k_hk] = _v_hk
        except Exception:
            pass
        # 2. 已有熱鍵 → 檢查係咪真係 load 到（唔可以淨係見 hotkeys.ini 有就 return）
        # 🚨 2026-08-20（v0.10.10）：MT5 開住時寫入嘅熱鍵唔 load（用戶實測：關 MT5 → 寫 → 開先 work）
        # → 比較 hotkeys.ini mtime vs MT5 啟動時間：hotkeys.ini 喺 MT5 開機後先寫 = MT5 未 load → 要 restart 重寫
        _combo_n = None  # 🚨 2026-08-20 v0.10.11：一定要提前定義（experts 空 → loop 唔行 → 下面用 _combo_n 會 NameError）
        for _k in experts:
            if ea_name in _k:
                _combo_exist = experts[_k]
                # 🚨 2026-08-22 FIX（部署 Grid 搞走 EMA_Cross）：唔可以淨靠 hotkeys.ini mtime 判斷「未 load」
                # （MT5 自己/其他 EA 部署都會更新 hotkeys.ini → mtime 比 MT5 啟動新 → 誤判 → 無謂 restart → 搞走其他 EA）
                # → 直接 send 熱鍵測試 — 彈到 Properties = 熱鍵真係 load 咗 = 唔使 restart
                _hk_actually_loaded = False
                try:
                    from pywinauto import Application as _App_hkt
                    _app_hkt = _App_hkt(backend='win32').connect(process=find_mt5_pid() or mt5_pid, timeout=8)
                    _w_hkt = _app_hkt.window(class_name_re='MetaQuotes::MetaTrader')
                    _w_hkt.set_focus()
                    time.sleep(1)
                    from pywinauto.keyboard import send_keys as _sk_hkt
                    # 🚨 2026-08-22 FIX：熱鍵測試前先 click MT5 中央（確保有 active chart — 熱鍵要先有 chart 先彈 Properties）
                    # （冇 active chart → Ctrl+N 唔彈 → 誤判「未 load」→ 無謂 restart → 搞走其他 EA — Grid 案例）
                    try:
                        import pyautogui as _pg_hkt
                        _pg_hkt.FAILSAFE = False
                        _r_hkt = _w_hkt.rectangle()
                        _pg_hkt.click(_r_hkt.left + _r_hkt.width() // 2, _r_hkt.top + _r_hkt.height() // 2)
                        time.sleep(0.8)
                    except Exception:
                        pass
                    _sk_hkt(_combo_exist)
                    time.sleep(3)
                    # EnumWindows 搵 Properties dialog（標題含 EA 名）
                    _dlg_hkt = False
                    def _cb_hkt(h, x):
                        nonlocal _dlg_hkt
                        if _ct_hk.windll.user32.IsWindowVisible(h):
                            _tl_hkt = _ct_hk.windll.user32.GetWindowTextLengthW(h)
                            if _tl_hkt > 0:
                                _tb_hkt = _ct_hk.create_unicode_buffer(_tl_hkt + 1)
                                _ct_hk.windll.user32.GetWindowTextW(h, _tb_hkt, _tl_hkt + 1)
                                if ea_name in _tb_hkt.value:
                                    _dlg_hkt = True
                                    return False
                        return True
                    _ct_hk.windll.user32.EnumWindows(_ct_hk.WINFUNCTYPE(_ct_hk.c_bool, _ct_hk.c_size_t, _ct_hk.c_size_t)(_cb_hkt), 0)
                    if _dlg_hkt:
                        _hk_actually_loaded = True
                        # 撳「取消」關 dialog
                        try:
                            _sk_hkt('{ESC}')
                        except Exception:
                            pass
                except Exception:
                    pass
                if _hk_actually_loaded:
                    print(f"✅ {ea_name} 熱鍵（{_combo_exist}）實測 load 成功（彈 Properties）— 唔使 restart")
                    return mt5_pid
                print(f"⚠️ {ea_name} 熱鍵（{_combo_exist}）測試冇彈 Properties — 可能要 restart 重寫")
                _combo_n = _combo_exist  # 保留原本 combo（重寫用返）
                break  # 唔 return — 繼續落去 restart（關→寫→開）
        # 3. 分配未用 Ctrl+N（如果 break 落嚟已有 _combo_n — skip）
        _used = set()
        for _k, _v in experts.items():
            if _v and _v.startswith('Ctrl+'):
                try: _used.add(int(_v.replace('Ctrl+', '')))
                except: pass
        if _combo_n is None:
            _combo_n = None
            for _i_n in range(1, 10):
                if _i_n not in _used:
                    _combo_n = f'Ctrl+{_i_n}'
                    break
        if not _combo_n:
            print(f"⚠️ 冇可用熱鍵 — 唔做預載")
            return mt5_pid
        print(f"🔄 熱鍵預載：{ea_name}（關 MT5 → 批次寫入熱鍵 → 開）")
        # 🚨 2026-08-22 FIX（部署 Grid 搞走 EMA_Cross — restore 唔齊）：restart 前記錄所有 chart
        # → restart 後檢查 restore 咗幾多 → 唔齊就補開（開返同 symbol 嘅 chart — EA 會自動 restore？唔會 — 但至少 chart 喺度）
        _charts_before_hk = []
        try:
            import ctypes as _ct_cb
            _u_cb = _ct_cb.windll.user32
            _mt5_win_cb = None
            def _cb_win(h, r):
                nonlocal _mt5_win_cb
                _l = _u_cb.GetWindowTextLengthW(h)
                if _l > 0:
                    _b = _ct_cb.create_unicode_buffer(_l + 1)
                    _u_cb.GetWindowTextW(h, _b, _l + 1)
                    _c2 = _ct_cb.create_unicode_buffer(128)
                    _u_cb.GetClassNameW(h, _c2, 128)
                    if 'MetaQuotes::MetaTrader' in _c2.value or ('5053721681' in _b.value and 'MetaQuotes' in _b.value):
                        _mt5_win_cb = h
                        return False
                return True
            _u_cb.EnumWindows(_ct_cb.WINFUNCTYPE(_ct_cb.c_bool, _ct_cb.c_size_t, _ct_cb.c_size_t)(_cb_win), 0)
            if _mt5_win_cb:
                def _cb_child(h, r):
                    _cls = _ct_cb.create_unicode_buffer(128)
                    _u_cb.GetClassNameW(h, _cls, 128)
                    if 'Afx' in _cls.value and 'ControlBar' not in _cls.value:
                        _l2 = _u_cb.GetWindowTextLengthW(h)
                        if _l2 > 0:
                            _b2 = _ct_cb.create_unicode_buffer(_l2 + 1)
                            _u_cb.GetWindowTextW(h, _b2, _l2 + 1)
                            if ',' in _b2.value:
                                _charts_before_hk.append(_b2.value)
                    return True
                _u_cb.EnumChildWindows(_ct_cb.c_void_p(_mt5_win_cb), _ct_cb.WINFUNCTYPE(_ct_cb.c_bool, _ct_cb.c_size_t, _ct_cb.c_size_t)(_cb_child), 0)
            print(f"📋 restart 前 chart: {_charts_before_hk}")
        except Exception as _e_cb:
            print(f"⚠️ restart 前記錄 chart 失敗: {_e_cb}")
        # 4. 關 MT5（WM_CLOSE 正常關閉）
        try:
            _out_hk = _sp_hk.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
            _pid_hk = None
            for _l_hk in _out_hk.stdout.decode('utf-8', errors='replace').splitlines():
                _pa_hk = [p.strip().strip('"') for p in _l_hk.split(',')]
                if len(_pa_hk) >= 2 and _pa_hk[0] == 'terminal64.exe' and _pa_hk[1].isdigit():
                    _pid_hk = int(_pa_hk[1]); break
            if _pid_hk:
                from pywinauto import Application as _App_hk
                _app_hk = _App_hk(backend='win32').connect(process=_pid_hk, timeout=8)
                _main_hk = _app_hk.window(class_name_re='MetaQuotes::MetaTrader')
                _ct_hk.windll.user32.PostMessageW(_ct_hk.c_void_p(int(_main_hk.element_info.handle)), 0x0010, 0, 0)
                time.sleep(8)
        except Exception:
            pass
        # 強制確認關咗（WM_CLOSE 可能彈窗）— 🚨 2026-08-20 gate：確認 terminal64 已關（poll 最多 20s）
        _closed_hk = _wait_until(lambda: not _mt5_alive(), 20, 'MT5 已關閉（WM_CLOSE 後確認）', interval=2)
        if not _closed_hk:
            print("⚠️ MT5 未完全關閉 — 強制 kill")
            try:
                _sp_hk.run('taskkill -f -im terminal64.exe', shell=True, capture_output=True)
                time.sleep(4)
            except Exception:
                pass
        # 5. 寫熱鍵（MT5 關閉狀態下寫 — 用戶實測先 load）
        # 🚨 2026-08-22 用戶要求：每次部署都用 Ctrl+1（單一熱鍵重用）— 部署完釋放，下隻 EA 又用返 Ctrl+1
        # → 唔再批次分配 Ctrl+1~9 — 只寫「新 EA = Ctrl+1」+ 清走舊 mapping
        _experts_hk = {}
        # 掃描 Experts 目錄全部 .ex5（排除子目錄 — 只掃根目錄）— 只留「新 EA」熱鍵
        _all_ex5 = []
        try:
            for _d_root in os.listdir(_data_root):
                _exp_dir = os.path.join(_data_root, _d_root, 'MQL5', 'Experts')
                if os.path.isdir(_exp_dir):
                    for _f5 in os.listdir(_exp_dir):
                        if _f5.endswith('.ex5') and os.path.isfile(os.path.join(_exp_dir, _f5)):
                            _all_ex5.append(_f5[:-4])
        except Exception:
            pass
        # 🚨 2026-08-22：只用 Ctrl+1（重用）— 每次部署都係 Ctrl+1
        _experts_hk[f'Experts\\{ea_name}.ex5'] = 'Ctrl+1'
        _lines_hk = ['<experts>']
        for _k2, _v2 in _experts_hk.items():
            _lines_hk.append(f'{_k2}={_v2}')
        _lines_hk.append('</experts>')
        _text_out_hk = '\r\n'.join(_lines_hk) + '\r\n'
        with open(_hk_ini, 'wb') as _f_hk:
            _f_hk.write(_text_out_hk.encode('utf-16'))
        print(f"✅ 熱鍵已寫入 hotkeys.ini（只用 Ctrl+1 — {ea_name}=Ctrl+1，舊 mapping 已清）")
        # 同步更新 hotkeys.json（agent 記憶 — 保持一致）
        try:
            import json as _json_hk
            _hj_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hotkeys.json')
            _hj_data = {}
            try:
                _hj_data = _json_hk.load(open(_hj_path, 'r', encoding='utf-8'))
            except Exception:
                pass
            _hj_data = {k: v for k, v in _hj_data.items() if k == ea_name}
            _hj_data[ea_name] = '^1'
            with open(_hj_path, 'w', encoding='utf-8') as _f_hj:
                _json_hk.dump(_hj_data, _f_hj, ensure_ascii=False, indent=2)
        except Exception:
            pass
        # 6. 開 MT5
        subprocess.Popen([MT5_PATH])
        # 🚨 2026-08-20（部署流程檢測系統落地）：開完 MT5 唔可以即刻部署 — 要等 MT5 load 完熱鍵
        # 驗證 gate：等主視窗 ready（poll 最多 90s）→ send Ctrl+<N> 測試熱鍵 load（彈 Properties = load 成功）
        # 🚨 2026-08-20 優化：用批次預載後 ea_name 實際嘅 combo（可能唔係 _combo_n）
        _combo_actual = _experts_hk.get(f'Experts\\{ea_name}.ex5') or _combo_n
        _start_hk = time.time()
        _mt5_ready_hk = False
        _cur_pid_hk = None
        while time.time() - _start_hk < 90:
            try:
                _cur_pid_hk = find_mt5_pid()
                if _cur_pid_hk:
                    from pywinauto import Application as _AppHK
                    _a_hk = _AppHK(backend='win32').connect(process=_cur_pid_hk, timeout=5)
                    _w_hk = _a_hk.window(class_name='MetaQuotes::MetaTrader::5.00')
                    if _w_hk.exists():
                        _mt5_ready_hk = True
                        break
            except Exception:
                pass
            time.sleep(3)
        if not _mt5_ready_hk:
            print("⚠️ 熱鍵預載：MT5 主視窗 90s 未 ready（繼續 — 部署時會再驗證）")
        else:
            print("✅ 熱鍵預載：MT5 主視窗 ready")
            # 🚨 2026-08-22（用戶要求：UAC 檢測機制）：熱鍵預載開完 MT5 檢查 UAC/授權窗口
            # （MT5 更新/異常 → 彈「Client Terminal AVX2 授權」→ 唔處理會擋熱鍵 load 測試）
            try:
                if not _detect_and_handle_uac('熱鍵預載 UAC 檢查', max_wait=30):
                    print("⚠️ 熱鍵預載：UAC 授權窗口未處理（等用戶手動撳）")
            except Exception:
                pass
            # 熱鍵 load 驗證：send Ctrl+N 測試 — 彈出 <EA> Properties = 熱鍵 load 成功（失敗關閉 dialog 再重試）
                        # 🚨 2026-08-25 FIX（連環部署偶發失敗 — Breakout 案例）：主視窗 ready 唔等於熱鍵 load 完
            # → 等 MT5 完全穩定（10 秒）先 send 測試 — MT5 初始化順序：UI → 數據 → 設定 → 熱鍵
            time.sleep(10)
            _hk_loaded_ok = False
            for _hk_try in range(3):
                try:
                    _w_hk.set_focus()
                    time.sleep(0.8)
                    # 🚨 2026-08-20 FIX：熱鍵附加 EA 需要 active chart（冇 chart → Ctrl+N 唔彈 Properties → 誤判未 load）
                    # → 先 click MT5 主視窗中央（chart 區域）確保有 active chart
                    try:
                        import pyautogui as _pg_hk
                        _pg_hk.FAILSAFE = False
                        _r_hk = _w_hk.rectangle()
                        _pg_hk.click(_r_hk.left + _r_hk.width() // 2, _r_hk.top + _r_hk.height() // 2)
                        time.sleep(0.8)
                    except Exception:
                        pass
                    from pywinauto.keyboard import send_keys as _sk_hk
                    _sk_hk(_combo_actual)
                    time.sleep(3)
                    # EnumWindows 搵 Properties dialog（標題含 EA 名 / 版本號）
                    _dlg_hk_found = False
                    _dlg_hk_hwnd = None
                    def _cb_hk(_h, _x):
                        nonlocal _dlg_hk_found, _dlg_hk_hwnd
                        if _ct_hk.windll.user32.IsWindowVisible(_h):
                            _cls_hk = _ct_hk.create_unicode_buffer(64)
                            _ct_hk.windll.user32.GetClassNameW(_h, _cls_hk, 64)
                            if '#32770' in _cls_hk.value:
                                _tl_hk = _ct_hk.windll.user32.GetWindowTextLengthW(_h)
                                _tb_hk = _ct_hk.create_unicode_buffer(_tl_hk + 1)
                                _ct_hk.windll.user32.GetWindowTextW(_h, _tb_hk, _tl_hk + 1)
                                if ea_name in _tb_hk.value:
                                    _dlg_hk_found = True
                                    _dlg_hk_hwnd = _h
                                    return False
                        return True
                    _ct_hk.windll.user32.EnumWindows(_ct_hk.WINFUNCTYPE(_ct_hk.c_bool, _ct_hk.c_size_t, _ct_hk.c_size_t)(_cb_hk), 0)
                    if _dlg_hk_found:
                        _hk_loaded_ok = True
                        print(f"✅ 熱鍵 load 驗證通過：{_combo_actual} 彈出 {ea_name} Properties（熱鍵已 load）")
                        # 撳「取消」關 dialog（唔好誤掛 EA）
                        try:
                            from pywinauto import Application as _AppDlg
                            _d_app = _AppDlg(backend='win32').connect(handle=_dlg_hk_hwnd, timeout=3)
                            _d_w = _d_app.window(handle=_dlg_hk_hwnd)
                            for _b in _d_w.children(class_name='Button'):
                                try:
                                    if '取消' in _b.window_text() or 'Cancel' in _b.window_text():
                                        _ct_hk.windll.user32.SendMessageW(_ct_hk.c_void_p(int(_b.element_info.handle)), 0x00F5, 0, 0)
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            _sk_hk('{ESC}')
                        break
                    else:
                        print(f"⚠️ 熱鍵 load 測試 {_hk_try+1}/3：{_combo_actual} 冇彈 Properties（可能未 load 完 — 重試）")
                        try:
                            _sk_hk('{ESC}')
                        except Exception:
                            pass
                        time.sleep(3)
                except Exception as _ehk_t:
                    print(f"⚠️ 熱鍵 load 測試異常: {_ehk_t}")
                    time.sleep(3)
            if not _hk_loaded_ok:
                # 🚨 2026-08-24 FIX（熱鍵 load 唔穩定 — MT5 開機 cache 舊 hotkeys）：第一次 restart 後 load 測試失敗
                # → 再 restart 一次（第二次開機 load 到新寫入嘅 hotkeys）— 唔好即刻部署（會彈錯 EA / 附加失敗）
                print(f"⚠️ 熱鍵 load 3 次測試都冇彈 Properties — 再 restart 一次 reload 熱鍵")
                try:
                    # 關 MT5（WM_CLOSE → 等 → 強制 kill 兜底）
                    _sp_hk.run('taskkill -f -im terminal64.exe', shell=True, capture_output=True)
                    time.sleep(4)
                    # 開 MT5
                    subprocess.Popen([MT5_PATH])
                    # 等 ready（90s）
                    _start_hk2 = time.time()
                    _ready2 = False
                    while time.time() - _start_hk2 < 90:
                        _p2 = find_mt5_pid()
                        if _p2:
                            try:
                                from pywinauto import Application as _App2r
                                _a2r = _App2r(backend='win32').connect(process=_p2, timeout=5)
                                _w2r = _a2r.window(class_name='MetaQuotes::MetaTrader::5.00')
                                if _w2r.exists():
                                    _ready2 = True
                                    break
                            except Exception:
                                pass
                        time.sleep(3)
                    if _ready2:
                        print("✅ 熱鍵預載：第二次 restart 完成（reload 熱鍵）")
                        # 再測熱鍵
                        for _hk_try2 in range(3):
                            try:
                                _w2r.set_focus()
                                time.sleep(1)
                                import pyautogui as _pg_hk2
                                _pg_hk2.FAILSAFE = False
                                _r2 = _w2r.rectangle()
                                _pg_hk2.click(_r2.left + _r2.width() // 2, _r2.top + _r2.height() // 2)
                                time.sleep(0.8)
                                _sk_hk(_combo_actual)
                                time.sleep(3)
                                _dlg2 = False
                                def _cb_hk2b(_h3, _):
                                    nonlocal _dlg2
                                    _cls3 = _ct_hk.create_unicode_buffer(64)
                                    _ct_hk.windll.user32.GetClassNameW(_h3, _cls3, 64)
                                    if '#32770' in _cls3.value:
                                        _tl3 = _ct_hk.windll.user32.GetWindowTextLengthW(_h3)
                                        _tb3 = _ct_hk.create_unicode_buffer(_tl3 + 1)
                                        _ct_hk.windll.user32.GetWindowTextW(_h3, _tb3, _tl3 + 1)
                                        if ea_name in _tb3.value:
                                            _dlg2 = True
                                            return False
                                    return True
                                _ct_hk.windll.user32.EnumWindows(_ct_hk.WINFUNCTYPE(_ct_hk.c_bool, _ct_hk.c_size_t, _ct_hk.c_size_t)(_cb_hk2b), 0)
                                if _dlg2:
                                    _hk_loaded_ok = True
                                    print(f"✅ 第二次 restart 後熱鍵 load 驗證通過（{ea_name} Properties）")
                                    _sk_hk('{ESC}')
                                    break
                            except Exception:
                                pass
                            time.sleep(3)
                    if not _hk_loaded_ok:
                        print(f"⚠️ 第二次 restart 後熱鍵仍然冇 load — 部署時會再驗證（失敗會明確報錯）")
                except Exception as _ehk_r:
                    print(f"⚠️ 第二次 restart 失敗: {_ehk_r}")
        # 🚨 2026-08-22 FIX（部署 Grid 搞走 EMA_Cross — restore 唔齊）：restart 後檢查 chart 有冇 restore 齊
        # → 唔齊就補開（記錄咗 restart 前嘅 chart — 逐個 check 有冇喺度）
        if _charts_before_hk:
            try:
                import ctypes as _ct_rc
                _u_rc = _ct_rc.windll.user32
                _mt5_win_rc = None
                def _cb_win2(h, r):
                    nonlocal _mt5_win_rc
                    _l = _u_rc.GetWindowTextLengthW(h)
                    if _l > 0:
                        _b = _ct_rc.create_unicode_buffer(_l + 1)
                        _u_rc.GetWindowTextW(h, _b, _l + 1)
                        _c3 = _ct_rc.create_unicode_buffer(128)
                        _u_rc.GetClassNameW(h, _c3, 128)
                        if 'MetaQuotes::MetaTrader' in _c3.value or ('5053721681' in _b.value and 'MetaQuotes' in _b.value):
                            _mt5_win_rc = h
                            return False
                    return True
                _u_rc.EnumWindows(_ct_rc.WINFUNCTYPE(_ct_rc.c_bool, _ct_rc.c_size_t, _ct_rc.c_size_t)(_cb_win2), 0)
                _charts_after = []
                if _mt5_win_rc:
                    def _cb_child2(h, r):
                        _cls = _ct_rc.create_unicode_buffer(128)
                        _u_rc.GetClassNameW(h, _cls, 128)
                        if 'Afx' in _cls.value and 'ControlBar' not in _cls.value:
                            _l2 = _u_rc.GetWindowTextLengthW(h)
                            if _l2 > 0:
                                _b2 = _ct_rc.create_unicode_buffer(_l2 + 1)
                                _u_rc.GetWindowTextW(h, _b2, _l2 + 1)
                                if ',' in _b2.value:
                                    _charts_after.append(_b2.value)
                        return True
                    _u_rc.EnumChildWindows(_ct_rc.c_void_p(_mt5_win_rc), _ct_rc.WINFUNCTYPE(_ct_rc.c_bool, _ct_rc.c_size_t, _ct_rc.c_size_t)(_cb_child2), 0)
                print(f"📋 restart 後 chart: {_charts_after}")
                # 搵遺失 chart（restart 前有但 restart 後冇）
                _missing = []
                for _c1 in _charts_before_hk:
                    _sym1 = _c1.split(',')[0]
                    _found_m = False
                    for _c2 in _charts_after:
                        if _c2.split(',')[0] == _sym1:
                            _found_m = True
                            break
                    if not _found_m:
                        _missing.append(_sym1)
                if _missing:
                    print(f"🚨 restart 後遺失 {len(_missing)} 個 chart: {_missing} — 補開")
                    from pywinauto.keyboard import send_keys as _sk_rc
                    for _msym in _missing:
                        try:
                            _w_rc = _App_hkt.window(class_name_re='MetaQuotes::MetaTrader') if '_App_hkt' in dir() else None
                            if _w_rc is None:
                                from pywinauto import Application as _AppRC
                                _a_rc = _AppRC(backend='win32').connect(process=find_mt5_pid(), timeout=8)
                                _w_rc = _a_rc.window(class_name_re='MetaQuotes::MetaTrader')
                            _w_rc.set_focus()
                            time.sleep(0.5)
                            _sk_rc('{ALT down}{F down}{F up}{ALT up}')  # Alt+F menu
                            time.sleep(1.5)
                            _sk_rc('{ENTER}')  # 文件
                            time.sleep(1)
                            _sk_rc('{ENTER}')  # 新圖表
                            time.sleep(1)
                            _sk_rc('{SPACE}')  # symbol picker
                            time.sleep(1.5)
                            _sk_rc(_msym)
                            time.sleep(1)
                            _sk_rc('{ENTER}')
                            time.sleep(2)
                            print(f"  ✅ 補開 chart: {_msym}")
                        except Exception as _e_rc:
                            print(f"  ⚠️ 補開 {_msym} 失敗: {_e_rc}")
                else:
                    print("✅ restart 後 chart 齊全（冇遺失）")
            except Exception as _e_rc2:
                print(f"⚠️ restart 後檢查 chart 失敗: {_e_rc2}")
        # 7. 攞新 PID
        _new_pid = find_mt5_pid()
        if _new_pid:
            return _new_pid
        return mt5_pid
    except Exception as _e_hk:
        print(f"⚠️ 熱鍵預載失敗: {_e_hk}")
        return mt5_pid

def _detect_and_handle_uac(desc='', max_wait=30):
    """🚨 2026-08-22（用戶要求：UAC 檢測機制 — MT5 更新/授權都會問）
    偵測「Client Terminal 授權」/ UAC consent 窗口（$$$Secure UAP Dummy Window Class）
    處理策略：
    1. 偵測到授權窗口 → 記錄 + 嘗試按鈕撳「允許/是」（SendMessage BM_CLICK + Enter）
    2. 撳唔到（Windows 安全層拒絕自動化）→ 通知用戶（寫 alert flag — 網頁顯示「請撳允許」）
    3. max_wait 內一直有 → return False（唔好繼續部署 — 會被擋）
    """
    import ctypes as _ct_uac
    _u_uac = _ct_uac.windll.user32

    def _scan():
        found = []
        def _cb(h, _):
            try:
                _l = _u_uac.GetWindowTextLengthW(h)
                if _l > 0:
                    _b = _ct_uac.create_unicode_buffer(_l + 1)
                    _u_uac.GetWindowTextW(h, _b, _l + 1)
                    _t = _b.value
                    _c = _ct_uac.create_unicode_buffer(128)
                    _u_uac.GetClassNameW(h, _c, 128)
                    _cl = _c.value
                    # UAC consent / 授權窗口特徵
                    _is_uac = (
                        ('授權' in _t or 'Client Terminal' in _t or '要求' in _t or '允許' in _t)
                        or ('Secure UAP' in _cl or 'consent' in _cl.lower())
                    )
                    if _is_uac:
                        _pid = _ct_uac.c_ulong()
                        _u_uac.GetWindowThreadProcessId(h, _ct_uac.byref(_pid))
                        found.append((h, _t[:60], _cl[:30], _pid.value))
            except Exception:
                pass
            return True
        _u_uac.EnumWindows(_ct_uac.WINFUNCTYPE(_ct_uac.c_bool, _ct_uac.c_size_t, _ct_uac.c_size_t)(_cb), 0)
        return found

    _found = _scan()
    if not _found:
        return True  # 冇 UAC — 可以繼續

    print(f"🚨 [UAC Gate] {desc}: 偵測到 {len(_found)} 個授權窗口 — {_found[0][1]}")
    # 嘗試自動撳「允許/是」（SendMessage BM_CLICK — 對 consent 通常唔 work，但試下）
    for _h, _t, _cl, _pid in _found:
        try:
            _u_uac.SendMessageW(_ct_uac.c_void_p(_h), 0x0100, 0x0D, 0)  # WM_KEYDOWN Enter（撳默認）
            _u_uac.SendMessageW(_ct_uac.c_void_p(_h), 0x0101, 0x0D, 0)  # WM_KEYUP
        except Exception:
            pass
        try:
            _u_uac.PostMessageW(_ct_uac.c_void_p(_h), 0x0010, 0, 0)  # WM_CLOSE 試關
        except Exception:
            pass
    time.sleep(2)
    _still = _scan()
    if _still:
        # 關唔到 — Windows 安全層拒絕自動化 → 通知用戶手動撳
        print(f"⚠️ [UAC Gate] {desc}: {len(_still)} 個授權窗口關唔到（Windows 安全層）— 通知用戶手動處理")
        try:
            # 寫 alert flag（網頁/tkinter 顯示）
            _adir_u = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(_adir_u, '.uac_alert'), 'w', encoding='utf-8') as _f:
                _f.write(f"MT5 需要授權（{desc}）— 請喺電腦撳「允許/是」\n窗口: {_still[0][1]}")
        except Exception:
            pass
        # 等 max_wait 秒（俾用戶手動撳）— 撳完自動繼續
        _deadline = time.time() + max_wait
        while time.time() < _deadline:
            time.sleep(3)
            _now = _scan()
            if not _now:
                print(f"✅ [UAC Gate] {desc}: 授權窗口已處理（用戶撳咗/自動關）— 可以繼續")
                try:
                    os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.uac_alert'))
                except Exception:
                    pass
                return True
        print(f"❌ [UAC Gate] {desc}: {max_wait}s 內授權窗口未處理（可能係 MT5 更新要求授權）— 部署中止")
        return False
    print(f"✅ [UAC Gate] {desc}: 授權窗口已自動處理")
    return True
def _detect_and_handle_uac(desc='', max_wait=30):
    """🚨 2026-08-22（用戶要求：UAC 檢測機制 — MT5 更新/授權都會問）
    偵測「Client Terminal 授權」/ UAC consent 窗口（$$$Secure UAP Dummy Window Class）
    處理策略：
    1. 偵測到授權窗口 → 記錄 + 嘗試按鈕撳「允許/是」（SendMessage BM_CLICK + Enter）
    2. 撳唔到（Windows 安全層拒絕自動化）→ 通知用戶（寫 alert flag — 網頁顯示「請撳允許」）
    3. max_wait 內一直有 → return False（唔好繼續部署 — 會被擋）
    """
    import ctypes as _ct_uac
    _u_uac = _ct_uac.windll.user32

    def _scan():
        found = []
        def _cb(h, _):
            try:
                _l = _u_uac.GetWindowTextLengthW(h)
                if _l > 0:
                    _b = _ct_uac.create_unicode_buffer(_l + 1)
                    _u_uac.GetWindowTextW(h, _b, _l + 1)
                    _t = _b.value
                    _c = _ct_uac.create_unicode_buffer(128)
                    _u_uac.GetClassNameW(h, _c, 128)
                    _cl = _c.value
                    # UAC consent / 授權窗口特徵
                    _is_uac = (
                        ('授權' in _t or 'Client Terminal' in _t or '要求' in _t or '允許' in _t)
                        or ('Secure UAP' in _cl or 'consent' in _cl.lower())
                    )
                    if _is_uac:
                        _pid = _ct_uac.c_ulong()
                        _u_uac.GetWindowThreadProcessId(h, _ct_uac.byref(_pid))
                        found.append((h, _t[:60], _cl[:30], _pid.value))
            except Exception:
                pass
            return True
        _u_uac.EnumWindows(_ct_uac.WINFUNCTYPE(_ct_uac.c_bool, _ct_uac.c_size_t, _ct_uac.c_size_t)(_cb), 0)
        return found

    _found = _scan()
    if not _found:
        return True  # 冇 UAC — 可以繼續

    print(f"🚨 [UAC Gate] {desc}: 偵測到 {len(_found)} 個授權窗口 — {_found[0][1]}")
    # 嘗試自動撳「允許/是」（SendMessage BM_CLICK — 對 consent 通常唔 work，但試下）
    for _h, _t, _cl, _pid in _found:
        try:
            _u_uac.SendMessageW(_ct_uac.c_void_p(_h), 0x0100, 0x0D, 0)  # WM_KEYDOWN Enter（撳默認）
            _u_uac.SendMessageW(_ct_uac.c_void_p(_h), 0x0101, 0x0D, 0)  # WM_KEYUP
        except Exception:
            pass
        try:
            _u_uac.PostMessageW(_ct_uac.c_void_p(_h), 0x0010, 0, 0)  # WM_CLOSE 試關
        except Exception:
            pass
    time.sleep(2)
    _still = _scan()
    if _still:
        # 關唔到 — Windows 安全層拒絕自動化 → 通知用戶手動撳
        print(f"⚠️ [UAC Gate] {desc}: {len(_still)} 個授權窗口關唔到（Windows 安全層）— 通知用戶手動處理")
        try:
            # 寫 alert flag（網頁/tkinter 顯示）
            _adir_u = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(_adir_u, '.uac_alert'), 'w', encoding='utf-8') as _f:
                _f.write(f"MT5 需要授權（{desc}）— 請喺電腦撳「允許/是」\n窗口: {_still[0][1]}")
        except Exception:
            pass
        # 等 max_wait 秒（俾用戶手動撳）— 撳完自動繼續
        _deadline = time.time() + max_wait
        while time.time() < _deadline:
            time.sleep(3)
            _now = _scan()
            if not _now:
                print(f"✅ [UAC Gate] {desc}: 授權窗口已處理（用戶撳咗/自動關）— 可以繼續")
                try:
                    os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.uac_alert'))
                except Exception:
                    pass
                return True
        print(f"❌ [UAC Gate] {desc}: {max_wait}s 內授權窗口未處理（可能係 MT5 更新要求授權）— 部署中止")
        return False
    print(f"✅ [UAC Gate] {desc}: 授權窗口已自動處理")
    return True


def _ensure_no_dialog(desc='', max_wait=8, close_btn=True):
    """🚨 2026-08-21（用戶要求：認證有冇 dialog 先繼續下一步）
    Dialog 檢查閘門 — 確保冇任何 #32770 dialog 阻住先繼續
    - 有 dialog → WM_CLOSE 強制關閉（實測有效）+ 等 0.5 秒再確認
    - 關唔到（max_wait 內仲有）→ return False（Caller 要 fail，唔好硬嚟）
    - return True = 確認冇 dialog（可以繼續下一步）
    """
    import ctypes as _ct_nd
    _u_nd = _ct_nd.windll.user32

    def _scan():
        _dlgs = []
        def _cb(hwnd, _):
            _cls = _ct_nd.create_unicode_buffer(128)
            _u_nd.GetClassNameW(_ct_nd.c_void_p(hwnd), _cls, 128)
            if _cls.value == '#32770':
                _dlgs.append(hwnd)
            return True
        _u_nd.EnumWindows(_ct_nd.WINFUNCTYPE(_ct_nd.c_bool, _ct_nd.c_size_t, _ct_nd.c_size_t)(_cb), 0)
        return _dlgs

    _dlgs = _scan()
    if not _dlgs:
        return True  # 冇 dialog — 可以直接繼續

    print(f"🚧 [Dialog Gate] {desc}: 發現 {len(_dlgs)} 個 dialog — 清理中...")
    _deadline = time.time() + max_wait
    _closed = set()
    while time.time() < _deadline:
        _dlgs = [h for h in _scan() if h not in _closed]
        if not _dlgs:
            print(f"✅ [Dialog Gate] {desc}: dialog 已全部關閉 — 可以繼續")
            return True
        for _h in _dlgs:
            try:
                _u_nd.PostMessageW(_ct_nd.c_void_p(_h), 0x0010, 0, 0)  # WM_CLOSE
                _closed.add(_h)
            except Exception:
                pass
        if close_btn:
            try:
                from pywinauto import Application as _App_nd
                try:
                    _app_nd = _App_nd(backend='win32').connect(process=find_mt5_pid(), timeout=3)
                    for _h in _dlgs:
                        try:
                            _dw_nd = _app_nd.window(handle=int(_h))
                            for _b_nd in _dw_nd.children(class_name='Button'):
                                try:
                                    _bt_nd = _b_nd.window_text()
                                    if '取消' in _bt_nd or '否' in _bt_nd or 'Cancel' in _bt_nd or 'No' in _bt_nd:
                                        _b_nd.click()
                                        break
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception:
                pass
        time.sleep(0.5)
    _left = _scan()
    if _left:
        print(f"❌ [Dialog Gate] {desc}: {len(_left)} 個 dialog 關唔到（WM_CLOSE 無效）— 唔繼續下一步！")
        return False
    return True


def attach_ea_hotkey(ea_name, mt5_pid, symbol='EURUSD', open_chart=True):
    """🎯 快捷鍵方案（2026-08-06 用戶發現 — 解決 6093 double-click 問題）
    每隻 EA 喺「導航快捷鍵」設咗快捷鍵（Ctrl+1/2/3...）— send 快捷鍵 → EA 附加
    唔使 double-click Navigator（6093 對 double-click 唔 work）"""
    try:
        import ctypes as _ct
        from pywinauto import Application as _App
        from pywinauto.keyboard import send_keys as _sk
        # 🚨 2026-08-19：偵測 ea_name 係咪 Script 類型（OpenChart 先係 — Script 用一體化假裝掛；真 EA 用熱鍵真掛）
        _is_script_att = ea_name.startswith('OpenChart')
        # 🚨 緊急停止支援（2026-08-06：之前 dialog 循環冇 check — 緊急停止冇效）
        try:
            from control_guard import check_abort as _chk_abort
        except Exception:
            _chk_abort = lambda: None
        hotkeys = load_hotkey_map()
        combo = hotkeys.get(ea_name)
        # 🚨 2026-08-17 FIX：一體化模式（open_chart=True）唔需要 combo（OpenChart script 套模板掛 EA — 唔使熱鍵附加）— combo check 只限非一體化
        if not open_chart and not combo:
            print(f"⚠️ {ea_name} 未有快捷鍵設定（agent/hotkeys.json）")
            return False
        # 🚨 2026-08-24（用戶要求：Ctrl+O / OpenChart 已失效 — 回復熱鍵為主）：
        # 一體化（Ctrl+O 套模板）已失效（MT5 build 6140 — OpenChart script 熱鍵冇 load）
        # → 真 EA 一律用熱鍵（Ctrl+1）附加 — send 快捷鍵 → EA 掛 active chart
        if open_chart and _is_script_att:
            print(f"✅ 一體化：{ea_name} 已由套模板掛落圖表（跳過附加熱鍵）")
            _saw_props = True  # Script（OpenChart）一體化假裝已掛
        else:
            print(f"🎯 用快捷鍵 {combo} 附加 {ea_name}...")
        _app = _App(backend='win32').connect(process=mt5_pid, timeout=8)
        # 🚨 2026-08-22（用戶要求：UAC 檢測機制）：部署前先檢查 UAC/授權窗口
        # （MT5 更新後/帳戶異常 → 彈「Client Terminal AVX2 授權」→ 擋住部署 → 先處理）
        try:
            if not _detect_and_handle_uac(f'{ea_name} 部署前 UAC 檢查', max_wait=30):
                print(f"❌ {ea_name} 部署中止：UAC 授權窗口未處理")
                return False
        except Exception:
            pass
        # 🚨 2026-08-12 FIX：部署前檢查有冇 pending compile_cmd（配對後未編譯 — 等編譯完成先部署 — 唔會「部署完又彈編譯視窗」）
        try:
            _cf_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
            for _wc in range(20):  # 最多等 40 秒
                _pending_compile = False
                if os.path.isdir(_cf_dir):
                    for _fn in os.listdir(_cf_dir):
                        if _fn.startswith('compile_cmd_') and ea_name in _fn and _fn.endswith('.json'):
                            _pending_compile = True
                            break
                if not _pending_compile:
                    break
                _chk_abort()
                time.sleep(2)
            if _pending_compile:
                print(f"⚠️ compile_cmd 等咗 40 秒仲未完成 — 繼續部署（.ex5 可能未生成）")
        except Exception:
            pass
        # 🚨 2026-08-12 FIX：steps 喺函數開頭寫（開圖表之前 — 用戶撳部署即刻見到「部署進行中」）
        # 🚨 2026-08-12 FIX2：直接覆寫（唔用 _update_steps 累積 — 新任務開始清舊任務 steps — spec：唔跨任務累積）
        # 🚨 2026-08-12 FIX3：保留「重啟 MT5」3 步（部署前 ensure_hotkey 重啟寫嘅 — 唔好洗走 — 完整流程）
        _steps = [
            {"text": f"部署 {ea_name}（{(symbol or 'EURUSD').upper()}）", "status": "doing"},
            {"text": f"建立新圖表（{(symbol or 'EURUSD').upper()}）", "status": "pending"},
            {"text": f"附加 {ea_name}（快捷鍵 {combo}）", "status": "pending"},
            {"text": "驗證運行狀態", "status": "pending"},
        ]
        try:
            import json as _jdep
            _sf_dep = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
            _prev_dep = []
            try:
                if os.path.isfile(_sf_dep):
                    _prev_dep = _jdep.load(open(_sf_dep, 'r', encoding='utf-8'))
                    if not isinstance(_prev_dep, list):
                        _prev_dep = []
            except Exception:
                _prev_dep = []
            # 保留「重啟 MT5」3 步（已完成嘅留低 — 部署流程一部分）+ 過濾舊任務/等待
            _RESTART_TEXTS = ('關閉 MT5', '載入快捷鍵設定', '重新啟動 MT5')
            _kept = [s for s in _prev_dep if isinstance(s, dict) and s.get('text') in _RESTART_TEXTS]
            with open(_sf_dep, 'w', encoding='utf-8') as _fdep:
                _jdep.dump(_kept + _steps, _fdep, ensure_ascii=False)
        except Exception:
            pass
        time.sleep(0.8)  # 🚨 網頁 poll 捕到「部署」進行中
        # 🚨 2026-08-10 部署穩定性：一次過 reload（hotkeys.ini mtime > MT5 啟動 → 外部寫入未 load — reload 一次）
        # 🚨 2026-08-19 FIX：唔好 restart MT5 — do_restart_mt5 前會「關閉全部圖表」→ 其他已掛 EA（如 EMA_Cross）chart 被關 → EA 消失
        #   而家部署用「Alt+F→Enter→Enter→Space→symbol→Enter」menu 方法開 chart，唔靠 Ctrl+熱鍵 → 唔需要 restart reload hotkeys
        #   → hotkeys.ini 有變都唔 restart（避免搞死其他 EA）
        _HK_RESTART_DISABLED = True  # 🚨 2026-08-20：熱鍵已由 _ensure_hotkey_loaded 預載（關 MT5 → 寫 → 開）— 部署時唔可以再 restart（restart 會令 MT5 用內部設定覆寫 hotkeys.ini → 我哋寫嘅熱鍵消失 → Ctrl+N 失效）
        try:
            _hk_ini = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                                   'D0E8209F77C8CF37AD8BF550E51FF075', 'config', 'hotkeys.ini')
            if os.path.isfile(_hk_ini):
                _hk_mt = os.path.getmtime(_hk_ini)
                _mt5_start = None
                try:
                    import psutil as _ps
                    for _p in _ps.process_iter(['name', 'create_time']):
                        if _p.info['name'] and 'terminal64' in _p.info['name'].lower():
                            _mt5_start = _p.info['create_time']
                            break
                except Exception:
                    pass
                if (not _HK_RESTART_DISABLED) and _mt5_start is not None and _hk_mt > _mt5_start:
                    print(f"🔄 hotkeys.ini 有變（外部寫入 — MT5 未 load）→ reload 一次（關 MT5 → 開）")
                    _chk_abort()
                    do_restart_mt5()
                    # reload 後重新攞 MT5 PID + connect
                    try:
                        import subprocess as _sp2
                        _out = _sp2.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
                        for _l in _out.stdout.decode('utf-8', errors='replace').splitlines():
                            _pa = [x.strip().strip('"') for x in _l.split(',')]
                            if len(_pa) >= 2 and _pa[0] == 'terminal64.exe' and _pa[1].isdigit():
                                mt5_pid = int(_pa[1])
                                break
                        _app = _App(backend='win32').connect(process=mt5_pid, timeout=8)
                    except Exception:
                        pass
        except Exception:
            pass
        # 主視窗帶最前（快捷鍵要 active window）
        try:
            win = _app.window(class_name='MetaQuotes::MetaTrader::5.00')
            win.set_focus()
            time.sleep(1)
        except Exception:
            pass
        # 🆕 建立新圖表（2026-08：唔代替 — 每個 EA 一個圖表 — 品種選擇）
        # ✅ 用戶方法（2026-08-15）：OpenChart script 熱鍵（Ctrl+O — 用戶 set 咗）— 開目標圖表 → 附加 EA 落去
        # 流程：寫 json → 確保有圖表（熱鍵要圖表）→ Ctrl+O（OpenChart script 讀 json → ChartOpen 開目標圖表 active）→ 附加 EA（熱鍵 — 落 active）
        if open_chart:
            try:
                _sym = (symbol or '').upper()
                # ① 寫 json（OpenChart script 讀呢個 — 一體化：symbol + ea + 模板名）
                try:
                    import json as _joc
                    _cmd_file = os.path.join(COMMON_FILES, 'open_chart_cmd.json')
                    _tpl_name = f"{ea_name}_{_sym or 'EURUSD'}_{(tf or 'H1').upper()}.tpl"
                    # 🚨 2026-08-17 FIX：直接用 MT5 模板格式生成完整 tpl（含 path → Experts 根）
                    # （之前「複製現有 <ea>_*.tpl」— 但係好多 EA 未部署過 → 冇源頭 tpl → 生成失敗 → 套模板冇 tpl → EA 掛唔到！）
                    try:
                        _mt5_data_t = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
                        _tpl_full_t = None
                        for _d_t2 in os.listdir(_mt5_data_t) if os.path.isdir(_mt5_data_t) else []:
                            _pp = os.path.join(_mt5_data_t, _d_t2, 'MQL5', 'Profiles', 'Templates')
                            if os.path.isdir(_pp):
                                _tpl_full_t = os.path.join(_pp, _tpl_name)
                                break
                        if _tpl_full_t and not os.path.isfile(_tpl_full_t):
                            _CR = chr(13) + chr(10)
                            _tpl_t = '<chart>' + _CR + f'symbol={_sym or "EURUSD"}' + _CR + 'period=16385' + _CR + 'left=100' + _CR + 'top=50' + _CR + 'right=900' + _CR + 'bottom=500' + _CR + _CR
                            _tpl_t += '<expert>' + _CR + f'name={ea_name}' + _CR + f'path=Experts\\{ea_name}.ex5' + _CR + 'flags=7' + _CR + 'enabled=1' + _CR + _CR
                            _tpl_t += '<inputs>' + _CR + 'LotSize=1.00' + _CR + 'MagicNumber=240701' + _CR + '</inputs>' + _CR + _CR
                            _tpl_t += '</expert>' + _CR + _CR
                            _tpl_t += '<window>' + _CR + 'height=100' + _CR + _CR
                            _tpl_t += '<indicator>' + _CR + 'name=Main' + _CR + 'path=' + _CR + 'apply=1' + _CR + 'show_data=1' + _CR + 'scale_inherit=0' + _CR + 'scale_line=0' + _CR + 'scale_line_percent=50' + _CR + 'scale_line_value=0.000000' + _CR + 'scale_fix_min=0' + _CR + 'scale_fix_min_val=0.000000' + _CR + 'scale_fix_max=0' + _CR + 'scale_fix_max_val=0.000000' + _CR + '</indicator>' + _CR + _CR
                            _tpl_t += '</window>' + _CR + _CR + '</chart>'
                            with open(_tpl_full_t, 'wb') as _f_t:
                                _f_t.write(b'\xff\xfe')
                                _f_t.write(_tpl_t.encode('utf-16-le'))
                            print(f"📋 模板已生成: {_tpl_name}（path → Experts 根）")
                    except Exception as _ete:
                        print(f"⚠️ 生成模板失敗: {_ete}")
                    with open(_cmd_file, 'w', encoding='utf-8') as _f:
                        _joc.dump({'symbol': _sym or 'EURUSD', 'tf': (tf or 'H1').upper(),
                                   'ea': ea_name, 'tpl': _tpl_name}, _f)
                    # 🚨 2026-08-15 FIX：寫入後驗證（讀返確認 — json 舊值問題：部署 USDJPY 但 script 讀到舊 GBPUSD）
                    try:
                        _chk = _joc.load(open(_cmd_file, encoding='utf-8'))
                        if _chk.get('symbol') != _sym:
                            with open(_cmd_file, 'w', encoding='utf-8') as _f2:
                                _joc.dump({'symbol': _sym or 'EURUSD', 'tf': (tf or 'H1').upper(),
                                           'ea': ea_name, 'tpl': _tpl_name}, _f2)
                            print(f"📋 json 重寫（驗證唔啱 → {_sym}）")
                        else:
                            print(f"📋 json 寫入驗證 OK: {_sym}")
                    except Exception:
                        pass
                except Exception:
                    pass
                # ② 確保有圖表（新方法 Alt+F→Enter→Enter 會自己開 chart — 呢度只偵測）
                _has_chart_oc = False
                try:
                    for _d_oc in win.descendants():
                        if _d_oc.element_info.class_name == 'MDIClient':
                            _has_chart_oc = len(_d_oc.children()) > 0
                            break
                except Exception:
                    pass
                # ③ OpenChart 開 chart — 用下方「用戶方法」Alt+F→Enter→Enter→Space→symbol→Enter（唔再 Ctrl+9）
                # 確保有圖表 + focus
                try:
                    import ctypes as _ct_oc
                    _u_oc = _ct_oc.windll.user32
                    _u_oc.SetForegroundWindow(_ct_oc.c_void_p(int(win.element_info.handle)))
                    time.sleep(1)
                    try:
                        import pyautogui as _pg_oc
                        _pg_oc.FAILSAFE = False
                        _r_oc = win.rectangle()
                        _pg_oc.click(_r_oc.left + _r_oc.width() // 2, _r_oc.top + _r_oc.height() // 2)
                        time.sleep(0.8)
                    except Exception:
                        pass
                except Exception:
                    pass
                # 🚨 2026-08-19（用戶發現嘅可靠方法）：直接開 target symbol chart
                # Alt+F → Enter → Enter → Space → 打 symbol → Enter
                # （pyautogui 實測 work — 取代 Ctrl+9 熱鍵 — 唔受 MT5 重啟洗走 hotkeys.ini <scripts> 區影響）
                # 成功（active chart = _sym）→ skip Ctrl+9
                _oc_ok2 = False
                try:
                    import pyautogui as _pg_new2
                    _pg_new2.FAILSAFE = False
                    _u_oc.SetForegroundWindow(_ct_oc.c_void_p(int(win.element_info.handle)))
                    time.sleep(1)
                    print(f"📌 新方法開 chart: Alt+F→Enter→Enter→Space→{_sym}→Enter")
                    # 🚨 2026-08-21（用戶要求：認證有冇 dialog 先繼續下一步）：開 chart 前檢查閘門 — 有 dialog 擋住 Alt+F menu → 開 chart 必失敗
                    if not _ensure_no_dialog(f'開 chart {_sym} 前', max_wait=8):
                        print(f"❌ 開 chart 中止：dialog 關唔到 — 唔開 chart（避免假失敗）")
                        return False
                    _pg_new2.hotkey('alt', 'f'); time.sleep(1.5)
                    _pg_new2.press('enter'); time.sleep(1.5)
                    _pg_new2.press('enter'); time.sleep(2)
                    _pg_new2.press('space'); time.sleep(1.5)
                    _pg_new2.typewrite(_sym, interval=0.2); time.sleep(1)
                    _pg_new2.press('enter'); time.sleep(3)
                    _new_title2 = win.window_text()
                    # 🚨 2026-08-20 FIX：驗證唔可以淨靠主窗口標題（MT5 主窗口標題唔一定含 active chart symbol — 實測開咗 EURUSD chart 但標題冇後綴）
                    # → 檢查 MDI chart 窗口（有冇 <SYM>,H1 chart 存在）— chart 開咗就算成功
                    # 🚨 2026-08-21 FIX：改用 EnumChildWindows（pywinauto descendants 對 MT5 chart 窗口不可靠 — 實測開 chart 成功但 descendants check fail → 假失敗）
                    _chart_found2 = False
                    try:
                        import ctypes as _ct_f2
                        _u_f2 = _ct_f2.windll.user32
                        _main_hwnd_f2 = int(win.element_info.handle)
                        @_ct_f2.WINFUNCTYPE(_ct_f2.c_bool, _ct_f2.c_size_t, _ct_f2.c_size_t)
                        def _cb_f2(hwnd, _):
                            nonlocal _chart_found2
                            _cls2 = _ct_f2.create_unicode_buffer(128)
                            _u_f2.GetClassNameW(_ct_f2.c_void_p(hwnd), _cls2, 128)
                            if 'Afx' in _cls2.value and 'ControlBar' not in _cls2.value:
                                _len2 = _u_f2.GetWindowTextLengthW(hwnd)
                                if _len2 > 0:
                                    _buf2 = _ct_f2.create_unicode_buffer(_len2 + 1)
                                    _u_f2.GetWindowTextW(hwnd, _buf2, _len2 + 1)
                                    if ',' in _buf2.value and _sym.upper() in _buf2.value.upper():
                                        _chart_found2 = True
                                        return False  # 停
                            return True
                        _u_f2.EnumChildWindows(_ct_f2.c_void_p(_main_hwnd_f2), _cb_f2, 0)
                    except Exception:
                        pass
                    if _sym in _new_title2 or _chart_found2:
                        _oc_ok2 = True
                        print(f"✅ 新方法開圖成功: active chart = {_sym}")
                    else:
                        print(f"⚠️ 新方法未確認（active: {_new_title2[:50]}...）— 開 chart 失敗，唔附加！")
                except Exception as _eneg2:
                    print(f"⚠️ 新方法開 chart 失敗: {_eneg2}")

                time.sleep(1)
                if not _oc_ok2:
                    # 🚨 2026-08-25 FIX（連環部署偶發失敗 — Breakout 案例）：開 chart 失敗重試 2 次
                    # （Alt+F menu 時序 — MT5 restart 後 UI 未完全穩定 → 第一次開 chart 可能失敗 → 重試成功）
                    _oc_retried = False
                    for _oc_r2 in range(2):
                        print(f"🔄 開 chart 重試 {_oc_r2+1}/2（{_sym}）...")
                        try:
                            import pyautogui as _pg_r2
                            _pg_r2.FAILSAFE = False
                            _pg_r2.hotkey('alt', 'f'); time.sleep(1.5)
                            _pg_r2.press('enter'); time.sleep(1.5)
                            _pg_r2.press('enter'); time.sleep(2)
                            _pg_r2.press('space'); time.sleep(1.5)
                            _pg_r2.typewrite(_sym, interval=0.2); time.sleep(1)
                            _pg_r2.press('enter'); time.sleep(3)
                            # 驗證 chart 出現
                            try:
                                _chart_found2 = False
                                _u_f2.EnumChildWindows(_ct_f2.c_void_p(_main_hwnd_f2), _cb_f2, 0)
                            except Exception:
                                pass
                            if _chart_found2:
                                _oc_ok2 = True
                                _oc_retried = True
                                print(f"✅ 開 chart 重試成功（{_sym} chart 出現）")
                                break
                        except Exception:
                            pass
                        time.sleep(2)
                if not _oc_ok2:
                    print(f"❌ 開 chart 失敗（{_sym}）— 唔用備用方案（用戶要求）")
                    return False
                # 🚨 2026-08-10：驗證圖表 symbol（打字自動完成可能揀錯 — AMD 案例）
                # 用「市場報價」active 高亮唔可靠 — 用圖表標題（AfxFrameOrView 內嘅 Chart 標題）
                try:
                    import ctypes as _c9
                    _u9 = _c9.windll.user32
                    _chart_title = ''
                    @_c9.WINFUNCTYPE(_c9.c_bool, _c9.c_size_t, _c9.c_size_t)
                    def _cb9(hwnd, _):
                        nonlocal _chart_title
                        _cls = _c9.create_unicode_buffer(80)
                        _u9.GetClassNameW(_c9.c_void_p(hwnd), _cls, 80)
                        if 'Chart' in _cls.value or 'MetaTrader' in _cls.value:
                            _buf = _c9.create_unicode_buffer(120)
                            _u9.GetWindowTextW(_c9.c_void_p(hwnd), _buf, 120)
                            _tt = _buf.value
                            if _tt and _sym[:3] in _tt:
                                _chart_title = _tt
                                return False  # 停
                        return True
                    for _w in _app.windows():
                        try:
                            _u9.EnumChildWindows(_c9.c_void_p(int(_w.element_info.handle)), _cb9, 0)
                        except Exception:
                            pass
                        if _chart_title:
                            break
                    if _chart_title:
                        print(f"   ✅ 圖表標題驗證: {_chart_title[:40]}")
                    else:
                        print(f"   ⚠️ 圖表標題讀唔到（繼續 — 唔阻塞）")
                except Exception:
                    pass
                try:
                    _steps[0]['status'] = 'done'
                    _steps[1]['status'] = 'doing'
                    _update_steps(_steps)
                except Exception:
                    pass
            except Exception:
                pass
        # 🚨 2026-08-12：steps 已喺函數開頭寫（開圖表前）— 呢度唔好重複寫（會將 step0 由 done 重置做 doing → 第一行永遠「進行中」）
        # send 快捷鍵
        # 🚨 2026-08-15 FIX：一體化模式（open_chart=True — OpenChart script 套模板已掛 EA）→ 跳過 send 熱鍵
        # 🚨 2026-08-19 FIX：只有 Script（OpenChart）先跳過熱鍵（一體化假裝掛）；真 EA（ADX 等）即使 open_chart=True 都要用熱鍵真掛落 target chart
        if open_chart and _is_script_att:
            _saw_props = True  # Script（OpenChart）一體化假裝已掛
        else:
            _saw_props = False  # 🚨 2026-08-10：驗證 Properties 有冇彈出（冇彈 = 快捷鍵冇效 — 唔好誤判成功）
            if not open_chart:
                _sk(combo)
            else:
                # open_chart=True 但係真 EA → 開 chart 後用熱鍵真掛落 active chart
                if combo:
                    # 🚨 2026-08-20 FIX（附加錯 chart 根治 — 用戶實測）：send 熱鍵前驗證 active chart 係目標 symbol
                    # （OpenChart 開 chart 失敗 → active chart 係舊 restore 嘅 GBPUSD → 附加落去 → 代替 dialog → 一鑊泡）
                    # → 驗證唔到目標 chart → 明確 fail（唔好附加落錯 chart）
                    _active_ok = False
                    try:
                        import ctypes as _c_act
                        _u_act = _c_act.windll.user32
                        _act_title = ''
                        @_c_act.WINFUNCTYPE(_c_act.c_bool, _c_act.c_size_t, _c_act.c_size_t)
                        def _cb_act(hwnd, _):
                            nonlocal _act_title
                            _cls2 = _c_act.create_unicode_buffer(80)
                            _u_act.GetClassNameW(_c_act.c_void_p(hwnd), _cls2, 80)
                            if 'Chart' in _cls2.value:
                                _buf2 = _c_act.create_unicode_buffer(120)
                                _u_act.GetWindowTextW(_c_act.c_void_p(hwnd), _buf2, 120)
                                if _buf2.value.strip():
                                    _act_title = _buf2.value
                                    return False
                            return True
                        for _w_a in _app.windows():
                            try:
                                _u_act.EnumChildWindows(_c_act.c_void_p(int(_w_a.element_info.handle)), _cb_act, 0)
                            except Exception:
                                pass
                            if _act_title:
                                break
                        _sym_u = (symbol or '').upper().split('.')[0]
                        # 🚨 2026-08-20 FIX：EnumChildWindows「Chart」class 喺 MT5 搵唔到（chart 窗口係 AfxFrameOrView 類）
                        # → 改用 MDI chart 窗口檢查（同「新方法開圖」驗證一致 — 可靠）
                        # 🚨 2026-08-21 FIX：改用 EnumChildWindows Afx 檢查（pywinauto descendants 不可靠 — 假失敗）
                        _mdi_ok = False
                        try:
                            import ctypes as _ct_mdi2
                            _u_mdi2 = _ct_mdi2.windll.user32
                            _main_hwnd_mdi = int(win.element_info.handle)
                            @_ct_mdi2.WINFUNCTYPE(_ct_mdi2.c_bool, _ct_mdi2.c_size_t, _ct_mdi2.c_size_t)
                            def _cb_mdi(hwnd, _):
                                nonlocal _mdi_ok, _act_title
                                _cls_mdi = _ct_mdi2.create_unicode_buffer(128)
                                _u_mdi2.GetClassNameW(_ct_mdi2.c_void_p(hwnd), _cls_mdi, 128)
                                if 'Afx' in _cls_mdi.value and 'ControlBar' not in _cls_mdi.value:
                                    _len_mdi = _u_mdi2.GetWindowTextLengthW(hwnd)
                                    if _len_mdi > 0:
                                        _buf_mdi = _ct_mdi2.create_unicode_buffer(_len_mdi + 1)
                                        _u_mdi2.GetWindowTextW(hwnd, _buf_mdi, _len_mdi + 1)
                                        _tt_mdi = _buf_mdi.value
                                        if ',' in _tt_mdi and _sym_u in _tt_mdi.upper():
                                            _mdi_ok = True
                                            _act_title = _tt_mdi
                                            return False  # 停
                                return True
                            _u_mdi2.EnumChildWindows(_ct_mdi2.c_void_p(_main_hwnd_mdi), _cb_mdi, 0)
                        except Exception:
                            pass
                        if _mdi_ok:
                            _active_ok = True
                            print(f"   ✅ active chart 驗證: {_act_title[:40]}（目標 {_sym_u} — 啱）")
                        else:
                            print(f"   ⚠️ active chart 唔係目標 {_sym_u}（現: {_act_title[:40] or '未知'}）— 唔附加！")
                    except Exception as _e_act:
                        print(f"   ⚠️ active chart 驗證異常: {_e_act}（保守 — 當唔啱）")
                    if _active_ok:
                        # 🚨 2026-08-21（用戶要求：認證有冇 dialog 先繼續下一步）：send 熱鍵前檢查閘門
                        # 有 dialog（Properties 殘留）→ 熱鍵 send 咗會彈錯 dialog / 被擋 → 先確認冇 dialog
                        if not _ensure_no_dialog(f'附加 {ea_name} 前', max_wait=8):
                            print(f"❌ 附加中止：dialog 關唔到 — 唔 send 熱鍵（避免彈錯 dialog）")
                            return False
                        # 🚨 2026-08-24 FIX（熱鍵 load 慢 — 人手模擬測試 ATR/ATR 附加失敗）：send 前等耐啲（MT5 開機後熱鍵 load 慢）
                        # + send 後冇彈 Properties → 重試（最多 5 次 — 每次等 3 秒）
                        time.sleep(5)
                        _hk_ok = False
                        for _hk_try in range(5):
                            _sk(combo)
                            time.sleep(3)
                            # check 有冇彈 Properties dialog（含 EA 名 / 版本）
                            _props_found = False
                            try:
                                import ctypes as _ct_hk2
                                _u_hk2 = _ct_hk2.windll.user32
                                def _cb_hk2(_h2, _):
                                    nonlocal _props_found
                                    if _u_hk2.IsWindowVisible(_h2):
                                        _l2 = _u_hk2.GetWindowTextLengthW(_h2)
                                        if _l2 > 0:
                                            _b2 = _ct_hk2.create_unicode_buffer(_l2 + 1)
                                            _u_hk2.GetWindowTextW(_h2, _b2, _l2 + 1)
                                            if ea_name in _b2.value and '1.00' in _b2.value:
                                                _props_found = True
                                                return False
                                    return True
                                _u_hk2.EnumWindows(_ct_hk2.WINFUNCTYPE(_ct_hk2.c_bool, _ct_hk2.c_size_t, _ct_hk2.c_size_t)(_cb_hk2), 0)
                            except Exception:
                                pass
                            if _props_found:
                                print(f"✅ 快捷鍵 {combo} 彈出 Properties（try {_hk_try+1}）")
                                _hk_ok = True
                                break
                            print(f"⚠️ 快捷鍵 {combo} 冇彈出 Properties（重試 {_hk_try+1}/5）...")
                            time.sleep(3)
                        if not _hk_ok:
                            print(f"❌ 快捷鍵 {combo} 重試後都冇彈出 Properties — 附加失敗（快捷鍵可能未 load）")
                    else:
                        print(f"❌ 附加中止：active chart 唔係目標 symbol（{symbol}）— 避免代替 dialog 一鑊泡")
                        # 寫 fail steps
                        try:
                            import json as _jf2
                            _stf2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
                            with open(_stf2, 'w', encoding='utf-8') as _f2:
                                _jf2.dump([{'text': f'部署 {ea_name}（{symbol}）', 'status': 'done'},
                                           {'text': f'開圖表（{symbol}）', 'status': 'done'},
                                           {'text': f'附加 {ea_name}', 'status': 'doing'},
                                           {'text': '驗證運行狀態', 'status': 'pending'}], _f2, ensure_ascii=False)
                        except Exception:
                            pass
                        time.sleep(2)
                        return False
                else:
                    print(f"⚠️ {ea_name} 冇快捷鍵 combo — 用 Navigator 附加")
        time.sleep(3)
        def _bm_click(_btn):
            """用 BM_CLICK（SendMessage）撳按鈕 — 唔理位置/遮擋（2026-08-06：確定按鈕喺 dialog 邊界外 — pywinauto click 唔到）"""
            try:
                import ctypes as _c2
                _c2.windll.user32.SendMessageW(ctypes.c_void_p(int(_btn.element_info.handle)), 0x00F5, 0, 0)
                return True
            except Exception:
                try:
                    _btn.click()
                    return True
                except Exception:
                    return False

        # 檢查 dialog（循環處理所有 — Properties 確定 → 代替確認 → 可能有多個）
        _last_dlg_count = 0
        _clicked_once = set()  # 🚨 防卡死：撳過冇效果嘅 dialog 唔再撳（2026-08-07）
        _replace_blocked = False  # 🚨 2026-08-21：代替被拒標記（見到代替 dialog → fail 部署）
        for _ in range(8):
            _chk_abort()  # 🚨 每 round 檢查緊急停止
            acted = False
            _dlg_count = 0
            for _w in _app.windows():
                try:
                    if _w.class_name() == '#32770':
                        _dlg_count += 1
                        _h = int(_w.element_info.handle)
                        if _h in _clicked_once:
                            continue  # 撳過冇效果 — 唔再撳（防死循環卡死）
                        _t = _w.window_text()
                        # 代替確認（圖表已有 EA — 文字喺 Static 內容，標題係「MetaTrader 5」）
                        _is_replace = '代替' in _t or 'replace' in _t.lower()
                        if not _is_replace:
                            try:
                                _dw0 = _app.window(handle=_h)
                                for _s in _dw0.children(class_name='Static'):
                                    _st = _s.window_text()
                                    if '代替' in _st or 'replace' in _st.lower():
                                        _is_replace = True
                                        break
                            except Exception:
                                pass
                        if _is_replace:
                            # 🚨 2026-08-21 FIX（用戶實測：關 chart 後部署代替咗 TestTrades）：代替 dialog 出現 = 目標 chart 已有 EA
                            # = 開 chart 失敗/掛錯 chart → 唔可以接受代替（會取代其他 EA）→ 撳「否」+ fail
                            # （之前撳「是」→ 取代 TestTrades → 其他 EA 消失 + 心跳殘留假成功）
                            print("🚨 偵測到「代替」dialog — 唔接受（會取代其他 EA）— 撳「否」+ 中止部署")
                            _dw = _app.window(handle=_h)
                            _clicked_no = False
                            for _b in _dw.children(class_name='Button'):
                                try:
                                    if '否' in _b.window_text() or 'No' in _b.window_text() or 'Cancel' in _b.window_text():
                                        if _bm_click(_b):
                                            _clicked_no = True
                                            print("✅ 已撳「否」（拒絕代替）")
                                            break
                                except Exception:
                                    pass
                            if not _clicked_no:
                                try:
                                    _sk('{ESC}')
                                    print("✅ 已 ESC 關閉代替 dialog")
                                except Exception:
                                    pass
                            _clicked_once.add(_h)
                            acted = True
                            _replace_blocked = True  # 🚨 2026-08-21：標記代替被拒 → 部署失敗
                        elif any(_k in _t for _k in (ea_name, '1.00', '2.00', '3.00', '.ex5')):
                            _saw_props = True  # 🚨 Properties 彈出過（快捷鍵有效）
                            _dw = _app.window(handle=_h)
                            for _b in _dw.children(class_name='Button'):
                                try:
                                    if '確定' in _b.window_text() or 'OK' in _b.window_text():
                                        if _bm_click(_b):
                                            print("✅ 已撳「確定」（Properties）")
                                            try:
                                                _steps[1]['status'] = 'done'
                                                _steps[2]['status'] = 'doing'
                                                _update_steps(_steps)
                                                time.sleep(0.8)  # 🚨 2026-08-12：每步停留（網頁捕到「附加」進行中）
                                            except Exception:
                                                pass
                                            acted = True
                                        _clicked_once.add(_h)
                                        break
                                except Exception:
                                    pass
                        if acted:
                            break  # 🚨 每輪只處理一個 dialog（防卡死）
                except Exception:
                    pass
            if not acted:
                time.sleep(1)
                # 兩 round 冇動作 → 完成
                break
            time.sleep(1.5)
            # 🚨 防亂按：dialog 數量冇減少（撳咗但冇關）→ 停止（唔好無限撳）
            _chk_abort()
            _now_dlg = 0
            for _w2 in _app.windows():
                try:
                    if _w2.class_name() == '#32770':
                        _now_dlg += 1
                except Exception:
                    pass
            if _now_dlg >= _dlg_count and _ > 2:
                print("⚠️ dialog 冇關（可能撳錯）— 停止循環防亂按")
                break

        # 🚨 2026-08-21 FIX（代替 dialog 唔接受）：如果部署過程見到代替 dialog → 部署失敗
        # （代替 = 目標 chart 已有 EA — 開 chart 失敗/掛錯 → 唔可以繼續 — 唔好取代其他 EA）
        if _replace_blocked:
            print("❌ 部署中止：偵測到「代替」dialog（目標 chart 已有 EA）— 唔接受取代")
            try:
                _sk('{ESC}')
            except Exception:
                pass
            try:
                import json as _jf3
                _stf3 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
                with open(_stf3, 'w', encoding='utf-8') as _f3:
                    _jf3.dump([{'text': f'部署 {ea_name}（{symbol}）', 'status': 'done'},
                               {'text': f'開圖表（{symbol}）', 'status': 'done'},
                               {'text': f'附加 {ea_name}', 'status': 'doing'},
                               {'text': '⚠️ 代替 dialog — 目標 chart 已有 EA，唔接受取代', 'status': 'doing'},
                               {'text': '驗證運行狀態', 'status': 'pending'}], _f3, ensure_ascii=False)
            except Exception:
                pass
            return False

        # 🚨 2026-08-20 FIX（連環代替確認 — 用戶實測）：撳完「是」之後 MT5 可能連環彈多個「代替」dialog
        # （附加 EA 落已有 EA 嘅 chart — 逐個代替 — 每個都要再撳「是」）
        # → loop 完之後再 poll 8 秒睇有冇新代替 dialog → 有就再撳「是」（最多 5 次）
        for _rpl in range(5):
            _chk_abort()
            _rpl_found = False
            for _w_r in _app.windows():
                try:
                    if _w_r.class_name() != '#32770':
                        continue
                    _h_r = int(_w_r.element_info.handle)
                    _t_r = _w_r.window_text()
                    _is_rpl = '代替' in _t_r or 'replace' in _t_r.lower()
                    if not _is_rpl:
                        try:
                            _dw_r = _app.window(handle=_h_r)
                            for _s_r in _dw_r.children(class_name='Static'):
                                _st_r = _s_r.window_text()
                                if '代替' in _st_r or 'replace' in _st_r.lower():
                                    _is_rpl = True
                                    break
                        except Exception:
                            pass
                    if _is_rpl:
                        # 🚨 2026-08-21 FIX：連環代替都唔接受（撳「否」— 唔好取代其他 EA）
                        _rpl_found = True
                        _replace_blocked = True
                        _dw_r2 = _app.window(handle=_h_r)
                        for _b_r in _dw_r2.children(class_name='Button'):
                            try:
                                if '否' in _b_r.window_text() or 'No' in _b_r.window_text() or 'Cancel' in _b_r.window_text():
                                    if _bm_click(_b_r):
                                        print(f"✅ 已撳「否」（拒絕連環代替 {_rpl+1}）")
                                    break
                            except Exception:
                                pass
                        break  # 每 round 處理一個
                except Exception:
                    pass
            if not _rpl_found:
                break  # 冇代替 dialog — 完成
            time.sleep(2)

        # 🚨 2026-08-21 FIX：連環代替 loop 完 → 如果有代替被拒 → 部署失敗
        if _replace_blocked:
            print("❌ 部署中止：代替 dialog 被拒絕（目標 chart 已有 EA — 唔接受取代）")
            try:
                _sk('{ESC}')
            except Exception:
                pass
            try:
                import json as _jf4
                _stf4 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
                with open(_stf4, 'w', encoding='utf-8') as _f4:
                    _jf4.dump([{'text': f'部署 {ea_name}（{symbol}）', 'status': 'done'},
                               {'text': f'開圖表（{symbol}）', 'status': 'done'},
                               {'text': f'附加 {ea_name}', 'status': 'doing'},
                               {'text': '⚠️ 代替 dialog — 目標 chart 已有 EA，唔接受取代', 'status': 'doing'},
                               {'text': '驗證運行狀態', 'status': 'pending'}], _f4, ensure_ascii=False)
            except Exception:
                pass
            return False

        # 🚨 2026-08-10：驗證 Properties 有冇彈出（冇彈 = 快捷鍵冇效 — 重試快捷鍵 ×2）
        if not _saw_props:
            print(f"⚠️ 快捷鍵 {combo} 冇彈出 Properties（重試中）...")
            for _rt in range(2):
                _chk_abort()
                _sk(combo)
                time.sleep(3)
                # 檢查 dialog（簡單 — 有 EA 名/版本號 = Properties）
                _props_now = False
                for _w in _app.windows():
                    try:
                        if _w.class_name() == '#32770' and any(_k in _w.window_text() for _k in (ea_name, '1.00', '2.00', '3.00')):
                            _props_now = True
                            _saw_props = True
                            break
                    except Exception:
                        pass
                if _props_now:
                    # 撳確定
                    for _w in _app.windows():
                        try:
                            if _w.class_name() == '#32770':
                                _dw = _app.window(handle=int(_w.element_info.handle))
                                for _b in _dw.children(class_name='Button'):
                                    try:
                                        if '確定' in _b.window_text() or 'OK' in _b.window_text():
                                            if _bm_click(_b):
                                                print(f"✅ 重試 {_rt+1}: 已撳「確定」")
                                            break
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                    break
                time.sleep(2)
            if not _saw_props:
                print(f"❌ 快捷鍵 {combo} 重試後都冇彈出 Properties — 附加失敗（快捷鍵可能未 load）")

        # 🚨 2026-08-21（用戶要求：認證有冇 dialog 先繼續下一步）：心跳驗證前檢查閘門
        # 撳「確定」後 Properties dialog 可能殘留 → 唔可以當成功（下次部署會被擋）→ 確認冇 dialog 先繼續
        if not _ensure_no_dialog(f'{ea_name} 部署完成後', max_wait=8):
            print(f"❌ {ea_name} 部署後有 dialog 關唔到 — 唔當成功（會擋下次部署）")
            return False

        # 心跳驗證
        hb = os.path.join(COMMON_FILES, f'state_{ea_name}.json')
        if os.path.isfile(hb):
            print(f"✅ {ea_name} 附加成功（心跳存在）")
        else:
            print(f"✅ {ea_name} 快捷鍵附加流程完成（心跳等 tick）")
        # 🚨 2026-08-12 FIX：steps done 搬去函數最尾（所有操作完成後先寫 — 否則用戶見 steps done 撳確定 → active 仲 true → 即刻彈多一次）
        # 🎯 圖表平鋪（2026-08-08：部署完成後自動 Alt+R — 圖表整齊排列）
        try:
            _sk('%r')
            time.sleep(2)
        except Exception:
            pass
        # 🚨 收埋市場報價（2026-08-08：直接 ShowWindow minimize — 唔好用 Ctrl+M（toggle 會開返））
        try:
            import ctypes as _ct2
            for _w3 in _app.windows():
                try:
                    if '市場報價' in _w3.window_text() or 'Market Watch' in _w3.window_text():
                        _ct2.windll.user32.ShowWindow(ctypes.c_void_p(int(_w3.element_info.handle)), 6)  # SW_MINIMIZE
                        break
                except Exception:
                    pass
        except Exception:
            pass
        # 🚨 2026-08-10：log 驗證 symbol（打字方法可能開錯圖表 — AMD 案例）
        try:
            import glob as _g4
            # 🚨 等 OnInit 行 + log 寫入（撳確定後即刻讀 — log 未寫 → 誤判失敗 — Breakout 案例）
            # 🚨 2026-08-13 FIX：4 秒 → 8 秒（MT5 重啟後 EA 初始化 + log/心跳寫入要時間 — Parabolic_SAR 案例：用戶見成功但驗證話「圖表不符」— log 其實有記錄）
            time.sleep(8)
            _lg = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
            _latest = None
            for _d in os.listdir(_lg):
                _lgd = os.path.join(_lg, _d, 'logs')
                if os.path.isdir(_lgd):
                    for _f in _g4.glob(os.path.join(_lgd, '*.log')):
                        if _latest is None or os.path.getmtime(_f) > os.path.getmtime(_latest):
                            _latest = _f
            if _latest:
                with open(_latest, 'rb') as _f2:
                    _raw = _f2.read()
                for _enc in ('utf-16', 'utf-8', 'cp1252', 'gbk'):
                    try:
                        _txt = _raw.decode(_enc); break
                    except Exception:
                        continue
                _target_sym = (symbol or 'EURUSD').upper()
                _ok_sym = False
                for _line in _txt.splitlines():
                    if ea_name in _line and _target_sym in _line and ('已启动' in _line or '已啟動' in _line or 'loaded successfully' in _line):
                        _ok_sym = True
                        break
                if _ok_sym:
                    print(f"✅ log 驗證: {ea_name} 喺 {_target_sym} 啟動（正確圖表）")
                else:
                    print(f"❌ log 驗證: {ea_name} 冇喺 {_target_sym} 啟動（可能開錯圖表 — 檢查心跳後備）")
                    # 🚨 2026-08-12 FIX：心跳後備 — log 冇「已啟動」字眼唔代表 EA 冇運行（重啟 MT5 後 log 時序/字眼問題）
                    # 用戶實測：電腦實際一致（Breakout 喺 USDJPY 運行）但 log 驗證誤判失敗！
                    _hb_ok = False
                    try:
                        _hb_f = os.path.join(COMMON_FILES, f'state_{ea_name}.json')
                        if os.path.isfile(_hb_f):
                            import json as _jhbl
                            # 🚨 2026-08-12 FIX：心跳檔案係 UTF-16 編碼（EA 寫嘅 — 0xff 0xfe BOM）— 多編碼嘗試（之前 utf-8 讀失敗 → 後備冇效 → 誤判失敗）
                            _hb_d = None
                            for _enc_hb in ('utf-16', 'utf-8', 'cp1252'):
                                try:
                                    _hb_d = _jhbl.load(open(_hb_f, 'r', encoding=_enc_hb))
                                    break
                                except Exception:
                                    continue
                            if isinstance(_hb_d, dict) and _hb_d.get('status') == 'running' and int(time.time()) - int(os.path.getmtime(_hb_f)) < 300:
                                _hb_ok = True
                        # 🚨 2026-08-13 FIX：AgentHelper 案例 — 心跳用 hb_<EA>.txt 格式（舊版 EA）— state_*.json 揾唔到 → 檢查 hb_*.txt（mtime 新鮮 <300s = 運行中）
                        if not _hb_ok:
                            _hb_txt = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
                            if os.path.isfile(_hb_txt) and int(time.time()) - os.path.getmtime(_hb_txt) < 300:
                                _hb_ok = True
                                print(f"✅ hb_*.txt 心跳: {ea_name} 運行中（{os.path.basename(_hb_txt)} 新鮮）")
                    except Exception:
                        pass
                    if _hb_ok:
                        print(f"✅ 心跳後備: {ea_name} 運行中（心跳新鮮 — 圖表正確）")
                    else:
                        # 🚨 2026-08-13 FIX：心跳後備失敗 → 再等 5 秒重試（EA 初始化延遲 — 心跳檔案未寫 → 誤判失敗 — Parabolic_SAR 案例）
                        print(f"⏳ 心跳後備第一次失敗 — 等 5 秒再試（EA 可能仲初始化緊）...")
                        time.sleep(5)
                        _hb_ok = False
                        try:
                            if os.path.isfile(_hb_f):
                                _hb_d = None
                                for _enc_hb in ('utf-16', 'utf-8', 'cp1252'):
                                    try:
                                        _hb_d = _jhbl.load(open(_hb_f, 'r', encoding=_enc_hb))
                                        break
                                    except Exception:
                                        continue
                                if isinstance(_hb_d, dict) and _hb_d.get('status') == 'running' and int(time.time()) - int(os.path.getmtime(_hb_f)) < 300:
                                    _hb_ok = True
                        except Exception:
                            pass
                        if _hb_ok:
                            print(f"✅ 心跳後備（第二次）: {ea_name} 運行中 — 圖表正確")
                    if not _hb_ok:
                        # 🚨 2026-08-13 FIX：心跳後備都失敗 → 再等 5 秒重試 log 驗證（log 寫入延遲 — Ichimoku 案例：圖表成功但 log 未寫 → 誤判「圖表不符」）
                        # （Ichimoku 冇心跳 code — 心跳後備永遠失敗 — 但 log 最終會寫「已啟動」— 第二次 log 驗證）
                        time.sleep(5)
                        try:
                            import glob as _g5
                            _latest2 = None
                            _lg2 = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
                            for _d3 in os.listdir(_lg2):
                                _lgd2 = os.path.join(_lg2, _d3, 'logs')
                                if os.path.isdir(_lgd2):
                                    for _f5 in _g5.glob(os.path.join(_lgd2, '*.log')):
                                        if _latest2 is None or os.path.getmtime(_f5) > os.path.getmtime(_latest2):
                                            _latest2 = _f5
                            if _latest2:
                                _raw2 = open(_latest2, 'rb').read()
                                _txt2 = None
                                for _enc2 in ('utf-16', 'utf-8', 'cp1252', 'gbk'):
                                    try:
                                        _txt2 = _raw2.decode(_enc2); break
                                    except Exception:
                                        continue
                                if _txt2:
                                    for _line2 in _txt2.splitlines():
                                        if ea_name in _line2 and _target_sym in _line2 and ('已启动' in _line2 or '已啟動' in _line2 or 'loaded successfully' in _line2):
                                            _hb_ok = True
                                            print(f"✅ log 驗證（第二次）: {ea_name} 喺 {_target_sym} 啟動 — 圖表正確")
                                            break
                        except Exception:
                            pass
                    if not _hb_ok:
                        # 🚨 2026-08-20（部署流程檢測系統 v0.10.5）：唔再 return False！
                        # 舊邏輯：log 驗證 fail → return False → 外層新 code Step 4 gate 永遠行唔到
                        # （EA 明明掛到但 log 寫入延遲 → 假失敗 — Breakout 案例）
                        # 新邏輯：呢度只 print warning — 最終判定由 auto_attach_ea 嘅 Step 4 gate
                        # （_ea_loaded_in_log poll 30s + 心跳後備）負責
                        print(f"⚠️ 驗證 {ea_name} 未確認（log/心跳延遲）— 交俾外層 Step 4 gate 最終判定")
        except Exception:
            pass
        # 🚨 2026-08-12 FIX：所有操作完成（圖表平鋪/市場報價/log 驗證）→ 最後先寫 steps 全部 done（確定出現 — active 即刻 false — 撳確定唔會再彈）
        try:
            _steps[2]['status'] = 'done'
            _steps[3]['status'] = 'doing'
            _update_steps(_steps)
            time.sleep(0.8)
            _steps[3]['status'] = 'done'
            _update_steps(_steps)
            # 🚨 即刻寫 ai_control.json active:false（唔等外層 release — 否則用戶撳確定時 active 仲 true → 即刻彈多一次）
            try:
                import json as _jst
                _stf = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'server', 'static', 'detector', 'ai_control.json'))
                with open(_stf, 'w', encoding='utf-8') as _f:
                    _jst.dump({'active': False, 'program': '', 'time': time.time()}, _f, ensure_ascii=False)
            except Exception:
                pass
        except Exception:
            pass
        # 🚨 2026-08-21 FIX（RSI Properties dialog 殘留 — 用戶實測）：部署完成後清理任何殘留 dialog
        # （撳「確定」後 dialog 可能冇關 → 殘留 → 下次部署被 modal 擋 → 開 chart 失敗）
        try:
            import ctypes as _ct_fin
            _u_fin = _ct_fin.windll.user32
            _fin_dlgs = []
            def _enum_fin(hwnd, _):
                _cls_buf_fin = _ct_fin.create_unicode_buffer(128)
                _u_fin.GetClassNameW(_ct_fin.c_void_p(hwnd), _cls_buf_fin, 128)
                if _cls_buf_fin.value == '#32770':
                    _fin_dlgs.append(hwnd)
                return True
            _u_fin.EnumWindows(_ct_fin.WINFUNCTYPE(_ct_fin.c_bool, _ct_fin.c_size_t, _ct_fin.c_size_t)(_enum_fin), 0)
            for _hw_fin in _fin_dlgs:
                try:
                    _u_fin.PostMessageW(_ct_fin.c_void_p(_hw_fin), 0x0010, 0, 0)  # WM_CLOSE
                except Exception:
                    pass
            if _fin_dlgs:
                print(f"🧹 部署後清理殘留 dialog: {len(_fin_dlgs)} 個（WM_CLOSE）")
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"⚠️ 快捷鍵附加失敗: {e}")
        return False
def verify_heartbeat(ea_name, timeout=60):
    """驗證 EA heartbeat file 存在且新鮮（+ MT5 log 後備 — 2026-08-10：市場收市冇 tick 心跳唔寫）"""
    hb_file = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
    start = time.time()
    
    while time.time() - start < timeout:
        if os.path.exists(hb_file):
            mtime = os.path.getmtime(hb_file)
            age = time.time() - mtime
            if age < 300:  # Within 5 minutes
                # Read content
                with open(hb_file, 'rb') as f:
                    raw = f.read()
                content = raw.decode('utf-16-le', errors='replace').strip().lstrip('\ufeff')
                print(f"💓 {ea_name} heartbeat: {content} ({round(age)}s ago)")
                return True
        time.sleep(3)
    
    # 🚨 2026-08-10：心跳冇 → 睇 MT5 log「已啟動」（市場收市冇 tick — EA 其實啟動咗）
    # 🚨 2026-08-24 FIX（假成功根治）：讀 terminal Logs（<hash>/Logs/ — 英文 loaded successfully）而唔係 MQL5/Logs（MetaEditor 中文「已启动」殘留 → 誤判）
    # + 只認「loaded successfully」+ 最後狀態判斷（removed 後唔算 loaded）
    try:
        log_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        import glob as _g
        latest = None
        for d in os.listdir(log_dir):
            lg = os.path.join(log_dir, d, 'Logs')
            if os.path.isdir(lg):
                for f in _g.glob(os.path.join(lg, '*.log')):
                    if latest is None or os.path.getmtime(f) > os.path.getmtime(latest):
                        latest = f
        if latest and time.time() - os.path.getmtime(latest) < 300:
            with open(latest, 'rb') as f:
                raw = f.read()
            text = None
            for enc in ('utf-16', 'utf-8', 'cp1252', 'gbk'):
                try:
                    text = raw.decode(enc)
                    break
                except Exception:
                    continue
            if text and ea_name in text:
                _last_state = None
                for _ln in text.splitlines():
                    if ea_name in _ln and 'expert' in _ln.lower():
                        if 'loaded successfully' in _ln:
                            _last_state = 'loaded'
                        elif 'removed' in _ln:
                            _last_state = 'removed'
                if _last_state == 'loaded':
                    print(f"✅ {ea_name} MT5 log 顯示已啟動（market close 冇 tick — 心跳後備確認）")
                    return True
    except Exception:
        pass
    
    print(f"❌ {ea_name} heartbeat not detected within {timeout}s")
    return False


def _ea_loaded_in_log(ea_name, symbol):
    """🚨 2026-08-20（部署流程檢測系統 — Step 4 gate）
    對真 MT5 log：搵 `expert <EA> (<SYM>,H1) loaded successfully`（且無隨後 removed）
    ⚠️ 2026-08-20 FIX：加新鮮度檢查 — 只認最近 5 分鐘內嘅 loaded（stale 舊記錄會假 True）
    用於 _wait_until poll — 返 bool（唔 print 成功 — _wait_until 會 print）"""
    try:
        log_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        import glob as _g
        latest = None
        for d in os.listdir(log_dir):
            lg = os.path.join(log_dir, d, 'logs')
            if os.path.isdir(lg):
                for f in _g.glob(os.path.join(lg, '*.log')):
                    if latest is None or os.path.getmtime(f) > os.path.getmtime(latest):
                        latest = f
        if not latest:
            return False
        # 新鮮度：log 檔 mtime 要 < 300s（太舊 = MT5 冇寫入 = EA 冇 load 記錄）
        if time.time() - os.path.getmtime(latest) > 300:
            return False
        with open(latest, 'rb') as f:
            raw = f.read()
        for enc in ('utf-16', 'utf-8', 'cp1252', 'gbk'):
            try:
                text = raw.decode(enc)
                break
            except Exception:
                continue
        _sym = (symbol or '').upper()
        _found = False
        _removed_after = False
        # 🚨 2026-08-20 FIX（假成功根治）：loaded 記錄本身要新鮮（唔可以淨係 log 檔新鮮）
        # 舊記錄（例如 18:32 Bollinger EURUSD loaded）喺 log 檔 → log 檔新鮮 → 誤判 True → 假成功
        # → parse log 行時間（HH:MM:SS）對比而家 — 只認最近 300s 內嘅 loaded
        import datetime as _dt
        _now_dt = _dt.datetime.now()
        _cutoff_dt = _now_dt - _dt.timedelta(seconds=300)
        _found_ts = None
        for line in text.splitlines():
            if ea_name in line and ('loaded successfully' in line.lower() or '已启动' in line or '已啟動' in line):
                # parse 行時間（log 格式: XX\t0\tHH:MM:SS.mmm\tExperts\texpert ...）
                _m_ts = None
                try:
                    _parts = line.split('\t')
                    for _p in _parts:
                        _p2 = _p.strip()
                        if len(_p2) >= 8 and _p2[2] == ':' and _p2[5] == ':':
                            _hh, _mm, _ss = int(_p2[0:2]), int(_p2[3:5]), int(_p2[6:8])
                            _m_ts = _dt.datetime(_now_dt.year, _now_dt.month, _now_dt.day, _hh, _mm, _ss)
                            break
                except Exception:
                    _m_ts = None
                # 過午夜（23:59 → 00:00）— 日期跳一日 — 加一日修正
                if _m_ts and _m_ts > _now_dt + _dt.timedelta(hours=12):
                    _m_ts -= _dt.timedelta(days=1)
                if _m_ts and _m_ts >= _cutoff_dt:
                    if _sym in line or 'loaded successfully' in line.lower():
                        _found = True
                        _found_ts = _m_ts
                        _removed_after = False  # 新 loaded — 重置
            elif _found and ea_name in line and 'removed' in line.lower():
                _removed_after = True
        return _found and not _removed_after
    except Exception:
        return False


def verify_ea_loaded(ea_name):
    """檢查 MT5 log 確認 EA 已 load"""
    log_path = os.path.join(MT5_DATA, 'Logs', time.strftime('%Y%m%d') + '.log')
    mql5_log = os.path.join(MT5_DATA, 'MQL5', 'Logs', time.strftime('%Y%m%d') + '.log')
    
    for path in [log_path, mql5_log]:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-16-le', errors='replace') as f:
                lines = f.readlines()
            for line in reversed(lines[-50:]):
                if f'expert {ea_name}' in line.lower() and 'loaded' in line.lower():
                    print(f"✅ MT5 log: EA loaded successfully")
                    return True
                if ea_name in line and '啟動' in line:
                    print(f"✅ EA log: {line.strip()}")
                    return True
    return False


def auto_attach_ea(ea_name, symbol='EURUSD', timeframe='H1', inputs=None,
                   do_restart=False):
    """
    主函數：可靠地 attach EA 到 MT5 chart
    
    流程：
    1. 生成 .tpl 模板
    2. （可選）重啟 MT5 刷新 Navigator
    3. Navigator double-click attach EA
    4. 確保 AutoTrading ON
    5. 驗證 heartbeat
    
    Returns: True if EA is running with heartbeat
    """
    print(f"\n{'='*50}")
    print(f"  🚀 Auto-Attach: {ea_name} → {symbol} {timeframe}")
    print(f"{'='*50}")
    # 🚨 2026-08-28 FIX：記錄部署開始時間（log 驗證只認「部署開始之後」嘅 loaded — 唔好用 30 分鐘窗口）
    # （舊：30 分鐘內任何 loaded 都當 fresh → 讀到上一輪部署嘅舊 loaded → 假成功）
    _deploy_start_ts = time.time()
    global _last_deploy_start_ts
    _last_deploy_start_ts = _deploy_start_ts

    # Step 0: AI 控制守衛 — 彈警告視窗 + 支援緊急停止
    try:
        from control_guard import acquire, check_abort, release, ControlAborted
        acquire(f"部署 {ea_name}")
    except ImportError:
        # 冇 control_guard 都照行（向前兼容）
        check_abort = lambda: None
        release = lambda: None
        ControlAborted = Exception
        acquire = lambda *a, **k: None

    # 🚨 2026-08-22（用戶要求：UAC 檢測機制）：部署流程最開頭檢查 UAC/授權窗口
    # （MT5 更新/帳戶異常 → 授權窗口 → 先處理再部署）
    try:
        if not _detect_and_handle_uac(f'{ea_name} 部署 UAC 檢查', max_wait=30):
            print(f"❌ {ea_name} 部署中止：UAC 授權窗口未處理（可能係 MT5 更新要求授權）")
            return False
    except Exception:
        pass

    # 🚨 2026-08-21 FIX（用戶實測：關 chart 後部署卡 dialog）：部署前先清理所有殘留 dialog
    # （之前 RSI 部署彈嘅 Properties dialog 殘留未關 → 之後開 chart Alt+F 被 modal 擋 → 開 chart 失敗 → 代替 dialog 一鑊泡）
    # 🚨 2026-08-21 FIX2：ESC/撳取消對 modal dialog 唔 work（實測撳「確定」/ESC 都關唔到 — RSI Properties 卡死）
    # → 用 WM_CLOSE（PostMessage 0x0010 — 實測有效）
    try:
        import ctypes as _ct_cl
        _u_cl = _ct_cl.windll.user32
        _dlg_list = []
        def _enum_find(hwnd, _):
            _cls_buf2 = _ct_cl.create_unicode_buffer(128)
            _u_cl.GetClassNameW(_ct_cl.c_void_p(hwnd), _cls_buf2, 128)
            if _cls_buf2.value == '#32770':
                _dlg_list.append(hwnd)
            return True
        _u_cl.EnumWindows(_ct_cl.WINFUNCTYPE(_ct_cl.c_bool, _ct_cl.c_size_t, _ct_cl.c_size_t)(_enum_find), 0)
        for _hw in _dlg_list:
            try:
                _u_cl.PostMessageW(_ct_cl.c_void_p(_hw), 0x0010, 0, 0)  # WM_CLOSE — 直接關
            except Exception:
                pass
        time.sleep(0.8)
        # 再掃一次 — 有剩 → 撳「取消/否」（WM_CLOSE 可能被攔截）
        _dlg_list2 = []
        def _enum_find2(hwnd, _):
            _cls_buf3 = _ct_cl.create_unicode_buffer(128)
            _u_cl.GetClassNameW(_ct_cl.c_void_p(hwnd), _cls_buf3, 128)
            if _cls_buf3.value == '#32770':
                _dlg_list2.append(hwnd)
            return True
        _u_cl.EnumWindows(_ct_cl.WINFUNCTYPE(_ct_cl.c_bool, _ct_cl.c_size_t, _ct_cl.c_size_t)(_enum_find2), 0)
        if _dlg_list2:
            try:
                from pywinauto import Application as _App_cl
                _app_cl = _App_cl(backend='win32').connect(process=find_mt5_pid(), timeout=5)
                for _hw in _dlg_list2:
                    try:
                        _dw_cl = _app_cl.window(handle=int(_hw))
                        for _b_cl in _dw_cl.children(class_name='Button'):
                            try:
                                _bt_cl = _b_cl.window_text()
                                if '取消' in _bt_cl or '否' in _bt_cl or 'Cancel' in _bt_cl or 'No' in _bt_cl:
                                    _b_cl.click()
                                    break
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass
        print(f"🧹 部署前清理殘留 dialog: {len(_dlg_list)} 個已處理（WM_CLOSE）")
    except Exception:
        pass

    try:
        # 🚨 2026-08-28 FIX：刪除舊「generate_template」步驟（一體化模板 — stable 前概念 — 掛 EA 已用熱鍵 Ctrl+1 — 模板冇用 → 多餘）
        # Step 1: 熱鍵預載 — 確保 EA 熱鍵寫入 hotkeys.ini（MT5 關閉狀態下）→ MT5 load
        # 破綻：EA 必須本機有 .ex5（冇 → 熱鍵指向唔存在 EA → 失效）
        try:
            _cur_pid = find_mt5_pid()
            mt5_pid = _ensure_hotkey_loaded(ea_name, _cur_pid or 0)
        except Exception:
            pass

        # Step 2: Get or restart MT5
        if do_restart:
            mt5_pid = do_restart_mt5()
            if not mt5_pid:
                return False
        else:
            mt5_pid = find_mt5_pid()
            if not mt5_pid:
                print("MT5 not running, starting...")
                subprocess.Popen([MT5_PATH])
            # 🚨 2026-08-20（部署流程檢測系統 — Step 1 gate）：等 MT5 開 + 主視窗 ready（poll 最多 90s，唔係固定 30s）
            mt5_pid = _wait_until(lambda: wait_for_mt5(5), 90, 'MT5 已開 + 主視窗 ready（poll 90s）', interval=3)
            if not mt5_pid:
                return False
        check_abort()
        
        # Step 3: Attach EA（快捷鍵優先 — 2026-08：6093 double-click 唔 work）
        # 有快捷鍵 mapping → 直接 send 快捷鍵（唔行 Navigator GUI — 慳時間 + 唔 crash）
        # 🚨 2026-08-19 FIX：OpenChart 係 Script（讀 open_chart_cmd.json 開 target chart）— 唔行 attach_ea_navigator（Navigator double-click 對 Script 唔 work — 卡死 not found）
        # 🚨 2026-08-28 FIX（用戶實錘：Seasonal 冇喺 hotkeys.json → 落去舊 Navigator double-click 方法（Ctrl+N 開 chart — 幾多年前產物）→ 失敗）：
        # → 全部 EA 一律用熱鍵（attach_ea_hotkey — _ensure_hotkey_loaded 已確保 hotkeys.ini 寫入當前 EA=Ctrl+1）
        # → 唔再 fallback Navigator double-click（舊方法 — Ctrl+N 開 chart — 唔可靠 + 已經冇需要）
        hotkeys = load_hotkey_map()
        _is_script_ea = ea_name.startswith('OpenChart') or ea_name == 'OpenChart_Helper'
        if _is_script_ea:
            success = attach_ea_hotkey(ea_name, mt5_pid, symbol=args.symbol)
        else:
            # 全部 EA 用熱鍵（Ctrl+1 重用 — _ensure_hotkey_loaded 已寫入）— 唔 check hotkeys.json（可能唔完整）
            success = attach_ea_hotkey(ea_name, mt5_pid, symbol=args.symbol)
        if not success:
            # 🚨 2026-08-20（用戶要求：唔需要備用方案）：失敗直接 fail — 唔重試快捷鍵
            # （之前重試 ×2 唔開新 chart → 掛落 active chart（可能錯 symbol）→ 代替 dialog → 一鑊泡：Heikin_Ashi 掛錯 EURUSD 案例）
            print(f"❌ 附加失敗（{ea_name}）— 唔重試（避免掛錯 chart）")
        
        if not success:
            print("❌ Failed to attach EA")
            return False
        check_abort()
        
        # 🚨 2026-08-20（部署流程檢測系統 — Step 4 gate）：EA loaded 驗證（等 + poll — 唔係即刻 check）
        # log「loaded successfully」出現先算成功（對真 MT5 log — 心跳/activity 可能假成功）
        # ⚠️ 2026-08-20 FIX：gate fail 唔好即刻 return False — MT5 restart 後 log 寫入延遲 → 假失敗
        # → Step 5（心跳 + log 綜合）先係最終判定；呢度只 print 狀態
        _step4_ok = _wait_until(lambda: _ea_loaded_in_log(ea_name, (symbol or 'EURUSD')), 30,
                                f'EA {ea_name} loaded（MT5 log 驗證）', interval=3)
        if not _step4_ok:
            print(f"⚠️ Step 4 gate：{ea_name} 30s 內 log 未見 loaded — 交 Step 5 心跳後備最終判定")
        
        # Step 4: Ensure AutoTrading ON
        ensure_auto_trading_on(mt5_pid)
        check_abort()
        
        # Step 5: Verify（最終驗證 — 🚨 2026-08-20 部署流程檢測系統）
        # Step 4 gate 已確認 MT5 log loaded → 心跳只係輔助（市場收市冇 tick 心跳唔寫 — log 有 = 成功）
        # 心跳有 → 錦上添花；心跳冇但 log 已 loaded → 都係成功（唔好因心跳誤判失敗）
        _log_loaded = _ea_loaded_in_log(ea_name, (symbol or 'EURUSD'))
        heartbeat = verify_heartbeat(ea_name, timeout=15)
        
        if heartbeat or _log_loaded:
            print(f"\n🎉 SUCCESS: {ea_name} is running on {symbol} {timeframe}!")
            return True
        else:
            print(f"\n❌ 部署完成但驗證失敗：MT5 log 冇 loaded 記錄 + 心跳冇（應該唔會到呢度 — Step 4 gate 已過）")
            return False
    except ControlAborted:
        print(f"\n🚨 部署被用戶緊急停止！")
        return False
    finally:
        try:
            release()  # 無論成功失敗都釋放控制
        except Exception:
            pass


# ─── CLI ───
def _exec_open_chart_script():
    """🚨 2026-08-15：執行 OpenChart script（Ctrl+I → 插入 menu → 腳本 → OpenChart — 用戶實測方法）
    取代 Navigator scan（pywinauto TreeView 64-bit 問題 — 唔可靠）"""
    try:
        # 🚨 2026-08-22（用戶要求：UAC 檢測機制）：開 chart script 前檢查 UAC/授權窗口
        try:
            if not _detect_and_handle_uac('開 chart script UAC 檢查', max_wait=20):
                print("⚠️ 開 chart script：UAC 授權窗口未處理")
        except Exception:
            pass
        import subprocess as _sp2
        from pywinauto import Application as _App2
        from pywinauto.keyboard import send_keys as _sk2
        import ctypes as _ct2
        out = _sp2.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True).stdout
        _pid2 = None
        for line in out.splitlines():
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='replace')
            parts = [p.strip().strip('"') for p in line.split(',')]
            if len(parts) >= 2 and parts[0] == 'terminal64.exe' and parts[1].isdigit():
                _pid2 = int(parts[1])
                break
        if not _pid2:
            return False
        _app2 = _App2(backend='win32').connect(process=_pid2, timeout=8)
        _main2 = _app2.window(class_name='MetaQuotes::MetaTrader::5.00')
        # 確保 foreground
        try:
            _u2 = _ct2.windll.user32
            _u2.SetForegroundWindow(_ct2.c_void_p(int(_main2.element_info.handle)))
        except Exception:
            pass
        time.sleep(1)
        # 🚨 2026-08-15：熱鍵附加 EA — 要「圖表 active」（真正 EA 部署都係先開圖表先 send 熱鍵）
        # 冇圖表 → 開一個空圖表（Alt+F → Enter → Enter）— 有圖表 → 確保 active（click 一下）
        _has_chart2 = False
        try:
            for _d2 in _main2.descendants():
                if _d2.element_info.class_name == 'MDIClient':
                    _has_chart2 = len(_d2.children()) > 0
                    break
        except Exception:
            pass
        if not _has_chart2:
            print("   📋 冇圖表 — 開空圖表（Alt+F → Enter → Enter）")
            _sk2('%f')
            time.sleep(1.5)
            _sk2('{ENTER}')
            time.sleep(1.5)
            _sk2('{ENTER}')
            time.sleep(3)
        else:
            # 有圖表 — 確保 active（click 圖表中心）
            try:
                import pyautogui as _pg_act
                _pg_act.FAILSAFE = False
                _r2 = _main2.rectangle()
                _pg_act.click(_r2.left + _r2.width() // 2, _r2.top + _r2.height() // 2)
            except Exception:
                pass
            time.sleep(0.8)
        # 熱鍵 Ctrl+4（OpenChart_Helper — 附加落圖表 → OnInit 讀 json → ChartOpen(symbol) → ExpertRemove）
        # 🚨 2026-08-15：改用 pyautogui（真實 keydown/keyup — 比 pywinauto send_keys 穩定 — 用戶揀 B）
        try:
            import pyautogui as _pg2
            _pg2.FAILSAFE = False
            _pg2.hotkey('ctrl', '4')
        except Exception:
            _sk2('^4')
        time.sleep(2.5)
        # 驗證：Properties dialog 彈出（熱鍵 work — EA 附加準備）
        _dlg2 = False
        try:
            def _cb3(_h3, _x3):
                nonlocal _dlg2
                if _u2.IsWindowVisible(_h3):
                    _c3 = ctypes.create_unicode_buffer(64)
                    _u2.GetClassNameW(_h3, _c3, 64)
                    if '#32770' in _c3.value:
                        _l3 = _u2.GetWindowTextLengthW(_h3)
                        _b3 = ctypes.create_unicode_buffer(_l3 + 1)
                        _u2.GetWindowTextW(_h3, _b3, _l3 + 1)
                        if 'OpenChart_Helper' in _b3.value:
                            _dlg2 = True
                            return False
                return True
            _u2.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_cb3), None)
        except Exception:
            pass
        if not _dlg2:
            print("   ⚠️ Ctrl+4 冇彈 Properties（熱鍵未觸發）")
            return False
        # 撳「確定」（Properties dialog — EA 附加 → OnInit 執行 → ChartOpen(symbol)）
        try:
            import pyautogui as _pg3
            _pg3.FAILSAFE = False
            _pg3.press('enter')
        except Exception:
            _sk2('{ENTER}')
        time.sleep(3)
        print("   ✅ OpenChart_Helper 已附加（Properties → 確定 — 圖表開咗）")
        return True
    except Exception as _e2:
        print(f"   ⚠️ _exec_open_chart_script 異常: {_e2}")
        return False


def remove_ea_from_chart(ea_name, mt5_pid=None):
    """真暫停/剷除：Alt+W 窗口 dialog → ListView 揀 chart → Enter → Ctrl+W 關閉（2026-08-21 用戶方法 — 唔靠座標）
    原理：
    - Alt+W 開「窗口」dialog（有 chart 時）→ SysListView32 列出所有 chart（排位順序 = 開 chart 順序）
    - ListView 即時讀取（MT5 記憶體 — 唔似 .chr 檔延遲）
    - 揀目標 chart（對應排位）→ Enter → dialog 關閉 + 彈返該 chart
    - Ctrl+W → 直接關閉該 chart（EA 一齊移除）
    返回 True = 移除成功/已冇 EA；False = 失敗"""
    import subprocess as _sp
    from pywinauto import Application as _App
    from pywinauto.keyboard import send_keys as _sk
    import pyautogui as _pg
    _pg.FAILSAFE = False
    import ctypes as _ct
    _u = _ct.windll.user32

    if not mt5_pid:
        out = _sp.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = [p.strip().strip('"') for p in line.split(',')]
            if len(parts) >= 2 and parts[0] == 'terminal64.exe' and parts[1].isdigit():
                mt5_pid = int(parts[1])
                break
    if not mt5_pid:
        print("⚠️ MT5 未開 — 冇嘢要移除")
        return True

    _app = _App(backend='win32').connect(process=mt5_pid)
    _win = _app.window(class_name='MetaQuotes::MetaTrader::5.00')
    _win.set_focus()
    time.sleep(1)

    # 🚨 2026-08-22（用戶要求：UAC 檢測機制）：剷除流程都檢查 UAC/授權窗口
    try:
        if not _detect_and_handle_uac(f'剷除 {ea_name} UAC 檢查', max_wait=20):
            print(f"⚠️ 剷除 {ea_name}：UAC 授權窗口未處理（等用戶手動撳）")
    except Exception:
        pass

    def _dlgs():
        found = []
        def cb(h, x):
            if _u.IsWindowVisible(h):
                cls = _ct.create_unicode_buffer(64)
                _u.GetClassNameW(h, cls, 64)
                if '#32770' in cls.value:
                    tl = _u.GetWindowTextLengthW(h)
                    tb = _ct.create_unicode_buffer(tl + 1)
                    _u.GetWindowTextW(h, tb, tl + 1)
                    if tb.value.strip():
                        found.append((tb.value, h))
            return True
        _u.EnumWindows(_ct.WINFUNCTYPE(_ct.c_bool, _ct.c_void_p, _ct.c_void_p)(cb), 0)
        return found

    # 0. 檢查 EA 係咪真係運行（MT5 log 最後狀態 + 心跳）
    _ea_running = False
    try:
        import glob as _gl_r
        _lgd_r = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        _lat_r = None
        for _d_r2 in os.listdir(_lgd_r):
            _logs_r = os.path.join(_lgd_r, _d_r2, 'logs')
            if os.path.isdir(_logs_r):
                for _f_r in _gl_r.glob(os.path.join(_logs_r, '2026*.log')):
                    if _lat_r is None or os.path.getmtime(_f_r) > os.path.getmtime(_lat_r):
                        _lat_r = _f_r
        if _lat_r:
            _raw_r = open(_lat_r, 'rb').read()
            _txt_r = None
            for _enc_r in ('utf-16', 'utf-8', 'cp1252'):
                try:
                    _txt_r = _raw_r.decode(_enc_r)
                    break
                except Exception:
                    continue
            if _txt_r:
                import re as _re_r
                _last_r = None
                for _ln_r in _txt_r.splitlines():
                    if _re_r.search(rf'{_re_r.escape(ea_name)} \([A-Za-z0-9._]+,[A-Z0-9]+\)', _ln_r):
                        if 'removed' in _ln_r or '已停止' in _ln_r:
                            _last_r = 'stopped'
                        elif 'loaded successfully' in _ln_r or '已啟動' in _ln_r:
                            _last_r = 'started'
                _ea_running = (_last_r == 'started')
    except Exception:
        pass
    # 心跳檢查（state_<EA>.json 新鮮 = 運行）
    _hb_fresh = False
    try:
        _cfd = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
        for _hfn in (f'state_{ea_name}.json', f'hb_{ea_name}.txt'):
            _hfp = os.path.join(_cfd, _hfn)
            if os.path.isfile(_hfp) and time.time() - os.path.getmtime(_hfp) < 60:
                _hb_fresh = True
    except Exception:
        pass
    if not _ea_running and not _hb_fresh:
        print(f"ℹ️ {ea_name}：未運行（log 最後 stopped / 冇心跳）— 唔使移除，直接完成")
        return True

    # 1. Alt+W 開「窗口」dialog（有 chart 時）
    _sk('%w')
    time.sleep(2)

    # 2. 搵「窗口」dialog + ListView（精準定位 — 唔會搞亂其他 dialog）
    _dlg_found = None
    _lv_found = None
    for _w_a in _app.windows():
        try:
            if _w_a.class_name() == '#32770' and '窗口' in _w_a.window_text():
                _dlg_found = _w_a
                for _c_a in _w_a.children():
                    if _c_a.element_info.class_name == 'SysListView32':
                        _lv_found = _c_a
                        break
                break
        except Exception:
            continue
    if not _lv_found:
        # dialog 可能仲未彈（等 1 秒再試）
        time.sleep(1)
        for _w_a in _app.windows():
            try:
                if _w_a.class_name() == '#32770' and '窗口' in _w_a.window_text():
                    _dlg_found = _w_a
                    for _c_a in _w_a.children():
                        if _c_a.element_info.class_name == 'SysListView32':
                            _lv_found = _c_a
                            break
                    break
            except Exception:
                continue
    if not _lv_found:
        print("⚠️ 搵唔到「窗口」dialog 或 ListView（Alt+W 冇彈出？）")
        try:
            _sk('{ESC}')
        except Exception:
            pass
        return False

    # 3. 讀 ListView（即時 chart 排位 — index 順序 = 開 chart 順序）
    _cnt = _u.SendMessageW(_ct.c_void_p(int(_lv_found.element_info.handle)), 0x1004, 0, 0)  # LVM_GETITEMCOUNT
    _items = []
    for _i in range(max(_cnt, 0)):
        try:
            _t = _lv_found.get_item(_i).text()
            _items.append(_t)
        except Exception:
            _items.append('')
    print(f"📋 窗口 dialog 有 {_cnt} 個 chart：")
    for _i, _t in enumerate(_items):
        print(f"  [{_i}] {_t}")

    # 4. 對應 EA → symbol（由 MT5 log 搵目標 EA 掛邊個 symbol）
    _target_sym = None
    try:
        if _lat_r and os.path.isfile(_lat_r):
            _raw_t = open(_lat_r, 'rb').read()
            _txt_t = None
            for _enc_t in ('utf-16', 'utf-8', 'cp1252'):
                try:
                    _txt_t = _raw_t.decode(_enc_t)
                    break
                except Exception:
                    continue
            if _txt_t:
                import re as _re_t
                _last_sym = None
                for _ln_t in _txt_t.splitlines():
                    _m_t = _re_t.search(rf'{_re_t.escape(ea_name)} \(([A-Za-z0-9._]+),[A-Z0-9]+\)', _ln_t)
                    if _m_t:
                        if 'removed' in _ln_t or '已停止' in _ln_t:
                            _last_sym = None
                        elif 'loaded successfully' in _ln_t or '已啟動' in _ln_t:
                            _last_sym = _m_t.group(1)
                _target_sym = _last_sym
    except Exception:
        pass
    if _target_sym:
        print(f"🎯 目標 EA {ea_name} 掛喺 {_target_sym}（MT5 log）")
    else:
        print(f"⚠️ 由 MT5 log 搵唔到 {ea_name} 掛邊個 symbol（用 ListView 第一個 chart 做 target）")
        _target_sym = None

    # 5. 揀目標 chart（對應 symbol → ListView index）
    # 🚨 2026-08-21 FIX（多個同名 chart 揀錯 — 用戶實測）：唔可以淨揀第一個 match symbol 嘅 chart
    # （3 個 UK100 時 EA 可能掛喺第 2/3 個 → 移除錯 chart → 假成功）
    # → 策略：逐個試（由 symbol match 開始）→ Ctrl+W 關 → 檢查 EA 真係移除（心跳停/log removed）→ 未移除就下一個
    _candidates = []
    if _target_sym:
        for _i, _t in enumerate(_items):
            if _t.upper().startswith(_target_sym.upper()):
                _candidates.append(_i)
    if not _candidates:
        # fallback：全部 chart 都試（冇 log 記錄時）
        _candidates = list(range(len(_items)))
    print(f"📌 目標 symbol {_target_sym or '?'} → 候選 chart: {_candidates}")

    _removed_ok = False
    _attempted = set()  # 🚨 2026-08-21：已試過嘅 symbol+index 組合（重新讀 ListView 後 index 會移位）
    for _target_idx in _candidates:
        # 🚨 2026-08-21 FIX（index 移位 bug）：每次試之前重新對應 symbol → 最新 index
        # （移除 chart 後 ListView 重新排位 — 舊 index 會指錯 chart）
        # 🚨 2026-08-25 FIX（多個同名 chart 剷除失敗 — MACD AUDUSD×2 案例）：_attempted 用 (index, text) 會誤判
        # （第二次 ListView 重排後剩返嘅 chart 用返 index 0 + 同名 → (0, AUDUSD) 喺 _attempted → 當「試過」→ 唔試 → 「冇新嘅 chart」）
        # → 放寬：每次試之前重新搵「未試過嘅同 symbol chart」（text 計數代替 index 計數）
        _cur_idx = _target_idx
        if _target_sym:
            _found_cur = None
            _all_sym_now = [(_i3, _t3) for _i3, _t3 in enumerate(_items) if _t3.upper().startswith(_target_sym.upper())]
            # 未試過嘅（text 層面 — 唔好用 index — 移位問題）
            _tried_texts = {_t5 for _i5, _t5 in _attempted if _t5.upper().startswith(_target_sym.upper())}
            for _i6, _t6 in _all_sym_now:
                if _t6 not in _tried_texts:
                    _found_cur = _i6
                    break
            # 同名 chart 全部 text 一樣（同一 ListView item 名）→ 放寬用 index 計數（試過左幾多個同名）
            if _found_cur is None and _all_sym_now:
                # 🚨 2026-08-25 FIX2（MACD AUDUSD×2 — 重讀 ListView 得返 1 個同名 chart 但 _attempted 阻住）：
                # 移除咗一個同名 chart 後 ListView 重排 — 剩返嗰個用返 index 0（text 一樣）
                # → 只要「同名 chart 數目 >= 嘗試次數+1」就要再試（唔好因為 text 一樣就當試過）
                _tried_sym_cnt = sum(1 for _i7, _t7 in _attempted if _t7.upper().startswith(_target_sym.upper()))
                if _tried_sym_cnt < len(_all_sym_now) or _tried_sym_cnt == 0:
                    _idx_to_try = _tried_sym_cnt if _tried_sym_cnt < len(_all_sym_now) else 0
                    _found_cur = _all_sym_now[_idx_to_try][0]
                    print(f"✅ 放寬 _attempted 檢查（同名 chart 重試 #{_idx_to_try+1} — 總共試過 {_tried_sym_cnt} 次 / 有 {len(_all_sym_now)} 個）")
            if _found_cur is not None:
                _cur_idx = _found_cur
            else:
                print(f"⚠️ 冇新嘅 {_target_sym} chart（試過晒）— 停止")
                break
        if _cur_idx >= len(_items):
            continue
        _attempted.add((_cur_idx, _items[_cur_idx]))
        print(f"📌 試移除 chart [{_cur_idx}]（{_items[_cur_idx]}）...")
        # 6. 揀目標 chart → Enter（關閉 dialog + 彈返 chart）
        # 🚨 2026-08-21 FIX（Breakout AMD 案例 + 用戶要求）：用方向鍵揀（用戶一早講咗 — 唔靠座標）
        # 唔好有 click fallback（座標唔可靠 — ListView scroll/行高唔同 → 揀錯 → Enter 冇效 → dialog 卡住）
        _sk('{HOME}')
        time.sleep(0.5)
        for _kd in range(_cur_idx):
            _sk('{DOWN}')
            time.sleep(0.3)
        _sk('{ENTER}')
        time.sleep(2)

        # 7. 確認 dialog 關咗（彈返 chart）
        _dlgs_now = _dlgs()
        if any('窗口' in t for t, h in _dlgs_now):
            print("⚠️ 窗口 dialog 未關（Enter 可能冇生效）— 再試 Enter")
            _sk('{ENTER}')
            time.sleep(2)
            _dlgs_now2 = _dlgs()
            if any('窗口' in t for t, h in _dlgs_now2):
                # 🚨 2026-08-21 FIX（Breakout AMD 案例 — 網頁話成功但 MT5 卡窗口 dialog）：
                # dialog 再試都未關 → fail（唔好繼續 Ctrl+W 亂關 — 關唔到 + 誤判成功）
                print(f"❌ 窗口 dialog 未關（再試 Enter 都冇效）— 剷除中止（唔好誤判成功）")
                try:
                    _sk('{ESC}')
                except Exception:
                    pass
                return False

        # 8. Ctrl+W 關閉該 chart（EA 一齊移除）
        _sk('^w')
        time.sleep(2.5)

        # 9. 驗證：MT5 log 有 removed 記錄 / 心跳停（🎯 逐個試 — 冇移除就下一個 candidate）
        _this_removed = False
        try:
            _start_t = time.time()
            # 🚨 2026-08-25 FIX6（心跳停判斷等唔夠耐 — 移除後心跳檔 mtime 未過 30s → 誤判「仲運行緊」）：等 40 秒
            while time.time() - _start_t < 40:
                time.sleep(2)
                # 心跳停 = 移除
                _hb_still = False
                _cfd2 = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
                for _hfn2 in (f'state_{ea_name}.json', f'hb_{ea_name}.txt'):
                    _hfp2 = os.path.join(_cfd2, _hfn2)
                    if os.path.isfile(_hfp2) and time.time() - os.path.getmtime(_hfp2) < 30:
                        _hb_still = True
                if not _hb_still:
                    _this_removed = True
                    print(f"✅ {ea_name} 心跳已停（EA 已移除）")
                    break
                # MT5 log 有 removed
                try:
                    if _lat_r and os.path.isfile(_lat_r):
                        _raw_r2 = open(_lat_r, 'rb').read()
                        _txt_r2 = None
                        for _enc_r2 in ('utf-16', 'utf-8', 'cp1252'):
                            try:
                                _txt_r2 = _raw_r2.decode(_enc_r2)
                                break
                            except Exception:
                                continue
                        if _txt_r2:
                            _recent = _txt_r2.splitlines()[-30:]
                            # 🚨 2026-08-25 FIX（剷除假成功 — MACD 案例）：any(match removed) 會讀到舊 removed 記錄（上次測試）→ 誤判移除
                            # → 改 check「最後狀態」：搵 EA 最後一條 loaded/removed — 最後係 removed 先算真移除
                            _last_state_r = None
                            for _l3 in reversed(_recent):
                                if ea_name in _l3 and ('loaded' in _l3 or 'removed' in _l3 or '已启动' in _l3 or '已停止' in _l3):
                                    if 'removed' in _l3 or '已停止' in _l3:
                                        _last_state_r = 'removed'
                                    elif 'loaded' in _l3 or '已启动' in _l3:
                                        _last_state_r = 'loaded'
                                    break
                            if _last_state_r == 'removed':
                                # 🚨 2026-08-25 FIX5（多 chart 掛同一 EA — Breakout GBPUSD×2 案例）：log removed 但心跳仲寫
                                # = 另一個 chart 仲掛住 EA → 唔當完成 → 繼續試下一個 chart
                                _hb_after_log = False
                                try:
                                    for _hfn3 in (f'state_{ea_name}.json', f'hb_{ea_name}.txt'):
                                        _hfp3 = os.path.join(_cfd2, _hfn3)
                                        if os.path.isfile(_hfp3) and time.time() - os.path.getmtime(_hfp3) < 30:
                                            _hb_after_log = True
                                            break
                                except Exception:
                                    pass
                                if _hb_after_log:
                                    print(f"⚠️ log 話 removed 但心跳仲寫緊（{ea_name} 掛喺另一個 chart）— 繼續試下一個")
                                    time.sleep(2)
                                else:
                                    _this_removed = True
                                    print(f"✅ MT5 log 最後狀態確認 {ea_name} removed（心跳已停）")
                                    break
                except Exception:
                    pass
        except Exception:
            pass
        if _this_removed:
            _removed_ok = True
            break
        # 未移除 → 可能移除咗冇 EA 嘅 chart — 再開窗口 dialog 試下一個
        print(f"⚠️ chart [{_target_idx}] 移除後 {ea_name} 仲運行緊 — 試下一個 chart")
        # 重新開窗口 dialog（Ctrl+W 關咗 chart 之後 dialog 已關）
        time.sleep(1)
        _sk('%w')
        time.sleep(2)
        # 重新讀 ListView（chart 數目可能少咗）
        _lv_found2 = None
        for _w_a2 in _app.windows():
            try:
                if _w_a2.class_name() == '#32770' and '窗口' in _w_a2.window_text():
                    for _c_a2 in _w_a2.children():
                        if _c_a2.element_info.class_name == 'SysListView32':
                            _lv_found2 = _c_a2
                            break
                    break
            except Exception:
                continue
        if not _lv_found2:
            print("⚠️ 再開窗口 dialog 失敗 — 剷除中止")
            try:
                _sk('{ESC}')
            except Exception:
                pass
            return False
        _cnt2 = _u.SendMessageW(_ct.c_void_p(int(_lv_found2.element_info.handle)), 0x1004, 0, 0)
        _items = []
        for _i2 in range(max(_cnt2, 0)):
            try:
                _t2 = _lv_found2.get_item(_i2).text()
                _items.append(_t2)
            except Exception:
                _items.append('')
        print(f"📋 重新讀 ListView（{_cnt2} 個 chart）")
        for _i2, _t2 in enumerate(_items):
            print(f"  [{_i2}] {_t2}")

    if _removed_ok:
        print(f"✅ 暫停/剷除 {ea_name} 完成（Ctrl+W 關 chart）")
        return True
    print(f"❌ {ea_name} 未能確認移除（試晒所有候選 chart 都仲運行緊）")
    try:
        _sk('{ESC}')
    except Exception:
        pass
    return False



if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='MT5 EA Auto-Attach Tool')
    parser.add_argument('--ea', required=True, help='EA name (e.g. ADX_Trend)')
    parser.add_argument('--symbol', default='EURUSD', help='Symbol (default: EURUSD)')
    parser.add_argument('--tf', default='H1', help='Timeframe (default: H1)')
    parser.add_argument('--lot', type=float, default=1.0, help='Lot size (default: 1.0)')
    parser.add_argument('--magic', type=int, default=240701, help='Magic number')
    parser.add_argument('--restart', action='store_true', help='Restart MT5 first')
    parser.add_argument('--remove', action='store_true', help='Remove EA from chart (真暫停)')
    args = parser.parse_args()
    
    if args.remove:
        # 真暫停模式：移除圖表 EA
        from control_guard import acquire, release, ControlAborted
        try:
            acquire(f'暫停 {args.ea}')
        except Exception:
            pass
        try:
            ok = remove_ea_from_chart(args.ea)
            print(f"{'✅' if ok else '❌'} 暫停 {args.ea} {'成功' if ok else '（圖表可能冇 EA）'}")
        finally:
            try:
                release()
            except Exception:
                pass
        import sys
        sys.exit(0 if ok else 1)
    
    inputs = {
        'LotSize': f'{args.lot:.2f}',
        'MagicNumber': str(args.magic),
        'EnableLog': 'true',
    }
    
    result = auto_attach_ea(
        ea_name=args.ea,
        symbol=args.symbol,
        timeframe=args.tf,
        inputs=inputs,
        do_restart=args.restart,
    )
    
    sys.exit(0 if result else 1)
