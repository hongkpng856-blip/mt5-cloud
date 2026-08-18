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
    
    # 🚨 2026-08-08：先關閉全部圖表（MT5 關機記住圖表 → 開機 restore — 圖表會累積）
    # 關閉圖表先 → MT5 開機乾淨（冇 restore）→ 部署建立新圖表唔會累積
    try:
        import subprocess as _sp
        _out = _sp.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
        for _line in _out.stdout.decode('utf-8', errors='replace').splitlines():
            _parts = [p.strip().strip('"') for p in _line.split(',')]
            if len(_parts) >= 2 and _parts[0] == 'terminal64.exe' and _parts[1].isdigit():
                _pid = int(_parts[1])
                break
        else:
            _pid = None
        if _pid:
            from pywinauto import Application as _App2
            _app2 = _App2(backend='win32').connect(process=_pid, timeout=8)
            _WM_CLOSE = 0x0010
            for _w in _app2.windows():
                try:
                    if 'AfxFrameOrView' in _w.class_name():
                        _ct.windll.user32.PostMessageW(ctypes.c_void_p(int(_w.element_info.handle)), _WM_CLOSE, 0, 0)
                except Exception:
                    pass
            time.sleep(2)
            print("📋 已關閉全部圖表（開機唔 restore）")
    except Exception:
        pass
    
    # Kill existing MT5
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            proc.kill()
    
    time.sleep(3)
    
    # Start MT5
    subprocess.Popen([MT5_PATH])
    
    # Wait for ready
    pid = wait_for_mt5(timeout=90)
    if pid:
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

def attach_ea_hotkey(ea_name, mt5_pid, symbol='EURUSD', open_chart=True):
    """🎯 快捷鍵方案（2026-08-06 用戶發現 — 解決 6093 double-click 問題）
    每隻 EA 喺「導航快捷鍵」設咗快捷鍵（Ctrl+1/2/3...）— send 快捷鍵 → EA 附加
    唔使 double-click Navigator（6093 對 double-click 唔 work）"""
    try:
        import ctypes as _ct
        from pywinauto import Application as _App
        from pywinauto.keyboard import send_keys as _sk
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
        # 🚨 2026-08-15 FIX：一體化模式（open_chart=True — OpenChart script 套模板已掛 EA）→ 跳過「附加熱鍵」步驟
        # （之前：套模板掛咗 EA 之後仲行「附加」（send 熱鍵 → 落 active 圖表 — 掛錯圖表 — 用戶部署 Breakout 掛咗 EURUSD 案例）
        if open_chart:
            print(f"✅ 一體化：{ea_name} 已由套模板掛落圖表（跳過附加熱鍵）")
            _saw_props = True  # 當附加完成（套模板已掛）
        else:
            print(f"🎯 用快捷鍵 {combo} 附加 {ea_name}...")
        _app = _App(backend='win32').connect(process=mt5_pid, timeout=8)
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
        # 唔好每次部署同步 reload（之前 server ensure_hotkey sleep 50+55 = 卡 105 秒 — 「第一次冇反應」）
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
                if _mt5_start is not None and _hk_mt > _mt5_start:
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
                # ② 確保有圖表（熱鍵要圖表 active — 用戶實測）
                _has_chart_oc = False
                try:
                    for _d_oc in win.descendants():
                        if _d_oc.element_info.class_name == 'MDIClient':
                            _has_chart_oc = len(_d_oc.children()) > 0
                            break
                except Exception:
                    pass
                if not _has_chart_oc:
                    # 🚨 2026-08-17 FIX：完整開新圖表（Alt+F → Enter ×3 — 第三個 Enter 確認 dialog 開預設 symbol — 確保有「真圖表 window」先可以觸發 Ctrl+9 熱鍵）
                    # （之前只有 2 個 Enter → 只開到 dialog 未真正開圖表 → 冇圖表 active → Ctrl+9 唔觸發 → 開圖表失敗！）
                    print("📋 冇圖表 — 開新圖表（Alt+F → Enter ×3）")
                    _sk('%f')
                    time.sleep(1.5)
                    _sk('{ENTER}')
                    time.sleep(1.5)
                    _sk('{ENTER}')
                    time.sleep(1.5)
                    _sk('{ENTER}')
                    time.sleep(3)
                # ③ 執行 OpenChart script — 熱鍵 Ctrl+9（<scripts> 區 — 用戶實測可行）
                # 🚨 2026-08-17 FIX：每次部署前 CHECK hotkeys.ini 有冇「Scripts\OpenChart.ex5=Ctrl+9」+ 確保 MT5 load（重啟 reload 熱鍵）
                # （用戶：Scripts\OpenChart.ex5=Ctrl+9 喺 hotkeys.ini <scripts> 完全可行 — 但係每次熱鍵可能唔同 → 要先 CHECK + 重啟確保 load）
                _need_restart9 = False
                try:
                    _hk9_path = None
                    _hk9_tdir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
                    if os.path.isdir(_hk9_tdir):
                        for _d9 in os.listdir(_hk9_tdir):
                            _p9 = os.path.join(_hk9_tdir, _d9, 'config', 'hotkeys.ini')
                            if os.path.isfile(_p9):
                                _hk9_path = _p9
                                break
                    if _hk9_path:
                        # 🚨 2026-08-17 FIX：讀寫用 utf-16（自動處理 BOM — utf-16-le 讀唔會剝 BOM → 寫返會冇 BOM → MT5 讀唔到熱鍵！）
                        _hk9_c = open(_hk9_path, encoding='utf-16', errors='ignore').read()
                        # 🚨 檢查「每次熱鍵唔同」：確保<scripts>區有 OpenChart=Ctrl+9（可能有其它熱鍵 — 唔保證 Ctrl+9）
                        if 'Scripts\\OpenChart.ex5=Ctrl+9' in _hk9_c:
                            _hk9_ok = True
                        else:
                            # 寫入/修正 <scripts> Ctrl+9
                            _hk9_def = '<scripts>' + chr(13) + chr(10) + 'Scripts\\OpenChart.ex5=Ctrl+9' + chr(13) + chr(10) + '</scripts>'
                            if '<scripts>' in _hk9_c:
                                import re as _re9
                                _hk9_c = _re9.sub(r'<scripts>.*?</scripts>', _hk9_def, _hk9_c, flags=re.S)
                            else:
                                _hk9_c = _hk9_c.replace('</experts>', '</experts>' + chr(13) + chr(10) + _hk9_def)
                            with open(_hk9_path, 'wb') as _f9:
                                _f9.write(('\ufeff' + _hk9_c).encode('utf-16-le'))
                            print(f"✅ 已寫入 hotkeys.ini: Scripts\\OpenChart.ex5=Ctrl+9（帶 BOM）")
                            _need_restart9 = True  # 改咗熱鍵 → 要重啟 reload
                    # 🚨 2026-08-17 FIX：唔好「每次重啟」— 只喺 hotkeys.ini 真係變咗（寫入咗 Ctrl+9）先重啟
                    # （實測：每次重啟後 Ctrl+9 script 熱鍵未 ready → 開圖表唔work；但你手動環境（MT5 一直運行）Ctrl+9 每次 work
                    #   → 唔好無謂重啟 — MT5 一直運行保持 Ctrl+9 ready；只有 hotkeys.ini 改變先要 reload）
                    # _need_restart9 = True  ← 移除（唔強制每次重啟）
                except Exception as _e9x:
                    print(f"⚠️ hotkeys.ini 檢查失敗: {_e9x}")
                if _need_restart9:
                    try:
                        import subprocess as _sp9
                        _sp9.run('taskkill -f -im terminal64.exe', shell=True, capture_output=True)
                        time.sleep(4)
                        _sp9.run("powershell -Command \"Start-Process 'C:\\Program Files\\MetaTrader 5\\terminal64.exe'\"", shell=True, capture_output=True)
                        time.sleep(25)
                        print("✅ MT5 已重啟（load OpenChart Ctrl+9 熱鍵）")
                    except Exception as _e9:
                        print(f"⚠️ 重啟失敗: {_e9}")
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
                # send Ctrl+9（pyautogui）
                # 🔧 2026-08-18：只 send 一次就驗證目標 chart 存在就 break
                # （之前 for range(2) 每次 deploy 都 send 兩次 → 可能開出第 3 個 chart → 你見到 3 個 chart）
                # 只有目標 chart 未出先 retry 第二次。
                _oc_ok2 = False
                for _ocr in range(2):
                    try:
                        import pyautogui as _pg_oc2
                        _pg_oc2.FAILSAFE = False
                        _pg_oc2.hotkey('ctrl', '9')
                    except Exception:
                        _sk('^9')
                    time.sleep(3.5)
                    # 驗證目標 chart 已開（active 標題含 _sym）→ 成功就唔再 send（避免開第 3 個）
                    _chart_ok_early = False
                    try:
                        def _cb_early(_h3, _x3):
                            nonlocal _chart_ok_early
                            if _u_oc.IsWindowVisible(_h3):
                                _c3 = ctypes.create_unicode_buffer(64)
                                _u_oc.GetClassNameW(_h3, _c3, 64)
                                if 'MetaQuotes::MetaTrader' in _c3.value:
                                    _l3 = _u_oc.GetWindowTextLengthW(_h3)
                                    _b3 = ctypes.create_unicode_buffer(_l3 + 1)
                                    _u_oc.GetWindowTextW(_h3, _b3, _l3 + 1)
                                    if _sym in _b3.value:
                                        _chart_ok_early = True
                                        return False
                            return True
                        _u_oc.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_cb_early), None)
                    except Exception:
                        pass
                    if _chart_ok_early:
                        _oc_ok2 = True
                        break
                    # 目標 chart 未出 → 入面會檢查 dialog / 重試
                    _opt_dlg = False
                    try:
                        def _cb_opt(_h2, _x2):
                            nonlocal _opt_dlg
                            if _u_oc.IsWindowVisible(_h2):
                                _c2 = ctypes.create_unicode_buffer(64)
                                _u_oc.GetClassNameW(_h2, _c2, 64)
                                if '#32770' in _c2.value:
                                    _l2 = _u_oc.GetWindowTextLengthW(_h2)
                                    _b2 = ctypes.create_unicode_buffer(_l2 + 1)
                                    _u_oc.GetWindowTextW(_h2, _b2, _l2 + 1)
                                    if '選項' in _b2.value or 'Option' in _b2.value or '熱鍵' in _b2.value:
                                        _opt_dlg = True
                            return True
                        _u_oc.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_cb_opt), None)
                    except Exception:
                        pass
                    if _opt_dlg:
                        print("⚠️ Ctrl+9 彈咗視窗（script 熱鍵未 load）— 關閉 + 重啟 MT5 reload 熱鍵")
                        try:
                            _sk('{ESC}')
                            time.sleep(1)
                        except Exception:
                            pass
                        # 重啟 MT5（reload 熱鍵）
                        import subprocess as _sp_oc
                        try:
                            _sp_oc.run('taskkill -f -im terminal64.exe', shell=True, capture_output=True)
                            time.sleep(4)
                            _sp_oc.run("powershell -Command \"Start-Process 'C:\\Program Files\\MetaTrader 5\\terminal64.exe'\"", shell=True, capture_output=True)
                            time.sleep(25)
                            print("✅ MT5 已重啟（reload 熱鍵）")
                        except Exception as _eoc_r:
                            print(f"⚠️ 重啟失敗: {_eoc_r}")
                        continue
                    else:
                        # 🚨 2026-08-17 FIX：驗證用「MT5 active 圖表標題 = 目標 symbol」（唔用 log — log 延遲/唔寫 → 誤判「靜默失敗」；active 標題 Ctrl+9 開完 BRING_TO_TOP 即時改 — 準確）
                        _chart_ok = False
                        try:
                            def _cb_title(_h2, _x2):
                                nonlocal _chart_ok
                                if _u_oc.IsWindowVisible(_h2):
                                    _c2 = ctypes.create_unicode_buffer(64)
                                    _u_oc.GetClassNameW(_h2, _c2, 64)
                                    if 'MetaQuotes::MetaTrader' in _c2.value:
                                        _l2 = _u_oc.GetWindowTextLengthW(_h2)
                                        _b2 = ctypes.create_unicode_buffer(_l2 + 1)
                                        _u_oc.GetWindowTextW(_h2, _b2, _l2 + 1)
                                        if _sym in _b2.value:
                                            _chart_ok = True
                                            return False
                                return True
                            _u_oc.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(_cb_title), None)
                        except Exception:
                            pass
                        if not _chart_ok:
                            print(f"⚠️ Ctrl+9 冇開到圖表（{_sym} active 標題未變）— 重試")
                            time.sleep(2)
                            continue
                        _oc_ok2 = True
                        break
                time.sleep(1)
                print(f"📋 OpenChart script 已執行（開 {_sym or 'EURUSD'} 圖表 — active）" if _oc_ok2 else "⚠️ OpenChart script 執行未確認（繼續 — 唔阻塞）")
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
        # 🚨 2026-08-15 FIX：一體化模式（open_chart=True — 套模板已掛 EA）→ 跳過 send 熱鍵（唔好再附加落 active 圖表）
        if open_chart:
            _saw_props = True  # 套模板已掛 — 當附加完成
        else:
            _saw_props = False  # 🚨 2026-08-10：驗證 Properties 有冇彈出（冇彈 = 快捷鍵冇效 — 唔好誤判成功）
            _sk(combo)
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

        # 檢查 dialog（循環處理所有 — Properties 確定 → 代替確認「是」→ 可能有多個）
        _last_dlg_count = 0
        _clicked_once = set()  # 🚨 防卡死：撳過冇效果嘅 dialog 唔再撳（2026-08-07）
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
                            _dw = _app.window(handle=_h)
                            for _b in _dw.children(class_name='Button'):
                                try:
                                    if '是' in _b.window_text() or 'Yes' in _b.window_text():
                                        if _bm_click(_b):
                                            print("✅ 已撳「是」（代替確認）")
                                        acted = True
                                        _clicked_once.add(_h)
                                        break
                                except Exception:
                                    pass
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
                _lgd = os.path.join(_lg, _d, 'MQL5', 'Logs')
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
                    if ea_name in _line and _target_sym in _line and ('已启动' in _line or '已啟動' in _line):
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
                            if isinstance(_hb_d, dict) and _hb_d.get('status') == 'running' and int(time.time()) - int(_hb_d.get('ts', 0)) < 300:
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
                                if isinstance(_hb_d, dict) and _hb_d.get('status') == 'running' and int(time.time()) - int(_hb_d.get('ts', 0)) < 300:
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
                                _lgd2 = os.path.join(_lg2, _d3, 'MQL5', 'Logs')
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
                                        if ea_name in _line2 and _target_sym in _line2 and ('已启动' in _line2 or '已啟動' in _line2):
                                            _hb_ok = True
                                            print(f"✅ log 驗證（第二次）: {ea_name} 喺 {_target_sym} 啟動 — 圖表正確")
                                            break
                        except Exception:
                            pass
                    if not _hb_ok:
                        # 🚨 2026-08-12 FIX：寫失敗 steps（唔係「等待操作開始」）
                        try:
                            import json as _jlv
                            _sf_lv = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
                            _cur_lv = []
                            try:
                                if os.path.isfile(_sf_lv):
                                    _cur_lv = _jlv.load(open(_sf_lv, 'r', encoding='utf-8'))
                                    if not isinstance(_cur_lv, list):
                                        _cur_lv = []
                            except Exception:
                                _cur_lv = []
                            _cur_lv = [s for s in _cur_lv if isinstance(s, dict) and s.get('text') != '等待操作開始…']
                            if not any('失敗' in (s.get('text', '') if isinstance(s, dict) else '') for s in _cur_lv):
                                _cur_lv.append({'text': f'驗證 {ea_name} 啟動失敗（圖表不符）', 'status': 'done'})
                            with open(_sf_lv, 'w', encoding='utf-8') as _f:
                                _jlv.dump(_cur_lv, _f, ensure_ascii=False)
                        except Exception:
                            pass
                        return False
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
    try:
        log_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        import glob as _g
        latest = None
        for d in os.listdir(log_dir):
            lg = os.path.join(log_dir, d, 'MQL5', 'Logs')
            if os.path.isdir(lg):
                for f in _g.glob(os.path.join(lg, '*.log')):
                    if latest is None or os.path.getmtime(f) > os.path.getmtime(latest):
                        latest = f
        if latest and time.time() - os.path.getmtime(latest) < 300:
            with open(latest, 'rb') as f:
                raw = f.read()
            for enc in ('utf-16', 'utf-8', 'cp1252', 'gbk'):
                try:
                    text = raw.decode(enc)
                    break
                except Exception:
                    continue
            if ea_name in text and ('已启动' in text or '已啟動' in text or 'started' in text.lower()):
                print(f"✅ {ea_name} MT5 log 顯示已啟動（市場收市冇 tick — 心跳後備確認）")
                return True
    except Exception:
        pass
    
    print(f"❌ {ea_name} heartbeat not detected within {timeout}s")
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

    try:
        # Step 1: Generate template
        tpl_path = generate_template(ea_name, symbol, timeframe, inputs)
        check_abort()  # 每步檢查緊急停止
        
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
            mt5_pid = wait_for_mt5()
            if not mt5_pid:
                return False
        check_abort()
        
        # Step 2b: 固定 MT5 視窗位置 + 大小（所有操作座標穩定 — 視窗移動/縮放都唔影響）
        try:
            ensure_mt5_window(mt5_pid)
        except Exception:
            pass
        # ⚠️ 統一 Navigator 位置（2026-08 用戶要求：操作前 Navigator 最大 + 固定位置）
        try:
            ensure_navigator_unified(mt5_pid)
        except Exception:
            pass
        # ⚠️ 平鋪圖表（2026-08 用戶要求：有圖表就平鋪 — 座標穩定）
        try:
            tile_charts(mt5_pid)
        except Exception:
            pass
        # Step 2c: 將 DeskIn 移去角落（還原穩定版 — 唔郁 DeskIn — 避免影響 MT5）
        # 2026-08 還原：今日下午加 pin_deskin_away 之後 crash — 暫時唔用（穩定版冇呢個）
        check_abort()
        
        # Step 3: Attach EA（🎯 快捷鍵優先 — 2026-08：6093 double-click 唔 work）
        # 有快捷鍵 mapping → 直接 send 快捷鍵（唔行 Navigator GUI — 慳時間 + 唔 crash）
        hotkeys = load_hotkey_map()
        if ea_name in hotkeys:
            success = attach_ea_hotkey(ea_name, mt5_pid, symbol=args.symbol)
        else:
            success = attach_ea_navigator(ea_name, mt5_pid)
        if not success:
            # 🚨 2026-08-12 FIX：重試時唔建立新圖表（open_chart=False — 重用現有圖表 — 之前每次重試建立新圖表 → 「開好多圖表」）
            print(f"⚠️ 快捷鍵方法失敗 — 自動重試快捷鍵（×2，唔再建立新圖表）...")
            for _rt2 in range(2):
                check_abort()
                success = attach_ea_hotkey(ea_name, mt5_pid, symbol=args.symbol, open_chart=False)
                if success:
                    break
                time.sleep(2)
        if not success:
            print("⚠️ 快捷鍵重試後都失敗（不再試 Navigator — 6093 免疫）")
        
        if not success:
            print("❌ Failed to attach EA")
            return False
        check_abort()
        
        # Step 4: Ensure AutoTrading ON
        ensure_auto_trading_on(mt5_pid)
        check_abort()
        
        # Step 5: Verify
        time.sleep(5)
        loaded = verify_ea_loaded(ea_name)
        # ⚠️ heartbeat timeout 15 秒（唔係 60）— 好多 EA（TestRunner 等）冇 heartbeat 機制 → 白等 60 秒
        heartbeat = verify_heartbeat(ea_name, timeout=15)
        
        if heartbeat:
            print(f"\n🎉 SUCCESS: {ea_name} is running on {symbol} {timeframe}!")
            return True
        else:
            print(f"\n⚠️ {ea_name} may be attached but no heartbeat detected")
            return loaded
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
    """真暫停：GUI 移除圖表上嘅 EA
    方法：right-click 圖表 → Alt+X 開「專家」dialog → 列表揀 EA → 「移除」按鈕
    （比「專家顧問→移除」menu 可靠 — 用戶實測確認）
    返回 True = 移除成功/已冇 EA；False = 失敗"""
    import pyautogui as _pg
    _pg.FAILSAFE = False
    from pywinauto import Application as _App
    from pywinauto.keyboard import send_keys as _sk
    
    if not mt5_pid:
        import subprocess as _sp
        out = _sp.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = [p.strip().strip('"') for p in line.split(',')]
            if len(parts) >= 2 and parts[0] == 'terminal64.exe' and parts[1].isdigit():
                mt5_pid = int(parts[1])
                break
    if not mt5_pid:
        # ⚠️ MT5 未開 → 自動開啟 + 等登入（用戶要求：操作前先開 MT5 + 登入）
        print("MT5 not running, starting...")
        try:
            _sp.Popen([MT5_PATH])
        except Exception as e:
            print(f"⚠️ 開 MT5 失敗: {e}")
            return False
        mt5_pid = wait_for_mt5(timeout=90)
        if not mt5_pid:
            print("⚠️ MT5 開唔到（等 90 秒超時）")
            return False
        print(f"✅ MT5 已開啟（PID {mt5_pid}）+ 登入完成")
    
    app = _App(backend='win32').connect(process=mt5_pid)
    win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
    win.set_focus()
    time.sleep(0.8)
    
    # 固定 MT5 視窗（座標穩定 — 視窗移動/縮放都唔影響）
    try:
        ensure_mt5_window(mt5_pid)
        win.set_focus()
        time.sleep(0.8)
    except Exception:
        pass
    
    # 將 DeskIn 移去角落（還原穩定版 — 唔郁 DeskIn）
    # 2026-08 還原：今日下午加 pin_deskin_away 之後 crash — 暫時唔用（穩定版冇呢個）
    
    # 0. 檢查圖表 window 有冇開 — 冇圖表 = 冇 EA 運行 = 唔使移除（2026-08 實測：MT5 restore 後圖表可能冇開）
    # 大眾化：圖表 title 格式係「SYMBOL,TF」（例如 EURUSD,H1 / GBPCAD,M15）— 用 ',' 判斷任何圖表
    # 🚨 2026-08-14 FIX：圖表 window 檢查不可靠（圖表隱藏/最小化/標題讀唔到 → 誤判「圖表未開」→ 冇移除 → EA 仲運行）
    # → 加 log 判斷：MT5 log 最後「已啟動」（冇「已停止」）→ EA 確實運行 → 一定要移除（唔好直接完成）
    _ea_running_by_log = False
    try:
        import glob as _gl2
        _lgd2 = os.path.join(os.path.dirname(os.path.dirname(MT5_PATH)) if False else os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal'))
        _lat2 = None
        for _d2 in os.listdir(_lgd2):
            _logs2 = os.path.join(_lgd2, _d2, 'MQL5', 'Logs')
            if os.path.isdir(_logs2):
                for _f2 in _gl2.glob(os.path.join(_logs2, '2026*.log')):
                    if _lat2 is None or os.path.getmtime(_f2) > os.path.getmtime(_lat2):
                        _lat2 = _f2
        if _lat2:
            _raw2 = open(_lat2, 'rb').read()
            _txt2 = None
            for _enc2 in ('utf-16', 'utf-8', 'cp1252'):
                try:
                    _txt2 = _raw2.decode(_enc2)
                    break
                except Exception:
                    continue
            if _txt2:
                import re as _re2
                _last_state2 = None
                for _ln2 in _txt2.splitlines():
                    if re.search(rf'{re.escape(ea_name)} \([A-Za-z0-9._]+,[A-Z0-9]+\)', _ln2):
                        if '已停止' in _ln2 or 'removed' in _ln2:
                            _last_state2 = 'stopped'
                        elif '已啟動' in _ln2:
                            _last_state2 = 'started'
                _ea_running_by_log = (_last_state2 == 'started')
    except Exception:
        pass
    has_chart = False
    for _w in app.windows():
        try:
            if 'Afx' in _w.class_name() and ',' in _w.window_text():
                _cr = _w.rectangle()
                if _cr.width() > 100 and _cr.height() > 50:
                    has_chart = True
                    break
        except Exception:
            pass
    if not has_chart:
        # 🚨 2026-08-14 FIX：心跳新鮮（state_<EA>.json / hb_<EA>.txt <30s）= EA 確實運行（最可靠）→ 圖表檢查錯 → 唔好直接完成 — 繼續移除流程
        _hb_fresh = False
        try:
            _cfd = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
            for _hfn in (f'state_{ea_name}.json', f'hb_{ea_name}.txt'):
                _hfp = os.path.join(_cfd, _hfn)
                if os.path.isfile(_hfp) and time.time() - os.path.getmtime(_hfp) < 30:
                    _hb_fresh = True
        except Exception:
            pass
        if _ea_running_by_log or _hb_fresh:
            print(f"⚠️ {ea_name}：圖表 window 檢查唔到但心跳/log 顯示運行緊（多圖表或隱藏）— 繼續移除流程")
            has_chart = True
        else:
            print(f"ℹ️ {ea_name}：圖表未開（冇 EA 運行）— 唔使移除，直接完成")
            return True
    
    # 1. right-click 圖表（用圖表 window（EURUSD,H1 Afx）實際 rect — 2026-08 實測：主視窗 offset 唔可靠，
    # 圖表係獨立 Afx window 而且可能好細/唔同位置；DeskIn/其他視窗遮住時 WindowFromPoint 會食錯）
    # 每個位置：right-click → click「專家列表」位置 → 檢查「專家」dialog 開咗未
    r = win.rectangle()
    # 搵圖表 window（大眾化：title 含 ',' = SYMBOL,TF 格式 — 任何 symbol 都得）
    chart_rects = []
    for _w in app.windows():
        try:
            if 'Afx' in _w.class_name() and ',' in _w.window_text():
                _cr = _w.rectangle()
                if _cr.width() > 100 and _cr.height() > 50:
                    chart_rects.append(_cr)
        except Exception:
            pass
    if chart_rects:
        # 用第一個圖表 rect 嘅幾個位置
        cr = chart_rects[0]
        positions = [
            (cr.left + cr.width() // 2, cr.top + cr.height() // 2),        # 中央
            (cr.left + cr.width() // 2, cr.top + int(cr.height() * 0.7)), # 下部
            (cr.left + int(cr.width() * 0.3), cr.top + int(cr.height() * 0.4)),
        ]
        print(f"📊 圖表 rect: ({cr.left},{cr.top})-({cr.right},{cr.bottom})")
    else:
        # fallback：主視窗 offset
        positions = [
            (r.left + r.width() // 2, r.top + 550),
            (r.left + r.width() // 3, r.top + 350),
            (r.left + r.width() * 2 // 3, r.top + 400),
            (r.left + r.width() // 2, r.top + 650),
        ]
    expert_dlg = None
    for (px, py) in positions:
        try:
            _sk('{ESC}')
            time.sleep(0.5)
        except Exception:
            pass
        _pg.rightClick(px, py)
        time.sleep(2)
        # ⚠️ Menu 彈出後（用戶實測：right-click 會彈 menu）→ 直接 click 第 7 項「專家列表」
        # 唔靠 Alt+X（menu 可能冇 focus — 快捷鍵冇效）；item 高度 ~22px，第 7 項 ≈ +132px
        _pg.click(px + 100, py + 142)
        time.sleep(2.5)
        # 檢查「專家」dialog（click 專家列表 → 直接彈 dialog — 用戶實測「撳入去有 test runner + 刪除按鈕」）
        for w in app.windows():
            try:
                if w.class_name() == '#32770' and ('專家' in w.window_text() or 'Expert' in w.window_text()):
                    expert_dlg = w
                    break
            except Exception:
                pass
        if not expert_dlg:
            # fallback：Alt+X
            _pg.hotkey('alt', 'x')
            time.sleep(2.5)
            for w in app.windows():
                try:
                    if w.class_name() == '#32770' and ('專家' in w.window_text() or 'Expert' in w.window_text()):
                        expert_dlg = w
                        break
                except Exception:
                    pass
        if expert_dlg:
            print(f"🎯 開到「專家」dialog @ ({px},{py})")
            break
        # 關閉可能彈出嘅「對象」視窗/menu
        try:
            _sk('{ESC}')
            time.sleep(0.5)
        except Exception:
            pass
    if not expert_dlg:
        print("⚠️ 搵唔到「專家」dialog（4 個位置都試過）")
        try:
            _sk('{ESC}')
        except Exception:
            pass
        return False
    
    # 固定「專家」dialog 位置 + 大小（每次彈出都鎖定 — 唔會漂移）
    try:
        pin_window(int(expert_dlg.element_info.handle), 800, 300, 540, 380)
        time.sleep(0.5)
    except Exception:
        pass
    
    # 4. 喺列表揀 EA（列表第一行 = 圖表唯一 EA）
    list_view = None
    remove_btn = None
    for c in expert_dlg.children():
        try:
            cls = c.element_info.class_name
            if cls == 'SysListView32':
                list_view = c
            elif cls == 'Button' and ('移除' in c.window_text() or 'Remove' in c.window_text()):
                remove_btn = c
        except Exception:
            pass
    
    if list_view:
        # 檢查列表有冇 EA（item count > 0）
        import ctypes as _ct
        lv_hwnd = int(list_view.element_info.handle)
        cnt = _ct.windll.user32.SendMessageW(_ct.c_void_p(lv_hwnd), 0x1004, 0, 0)  # LVM_GETITEMCOUNT
        if cnt <= 0:
            print(f"ℹ️ {ea_name} 已經唔喺圖表（列表空）")
            # 關 dialog
            for b in expert_dlg.children():
                try:
                    if b.element_info.class_name == 'Button' and '關閉' in b.window_text():
                        b.click()
                        time.sleep(1)
                        break
                except Exception:
                    pass
            return True
        # click 列表第一行（EA）
        rect = list_view.rectangle()
        _pg.click(rect.left + 80, rect.top + 20)
        time.sleep(1)
    
    # 5. click「移除」按鈕
    if remove_btn:
        try:
            remove_btn.click()
            time.sleep(2)
            print(f"✅ 已從圖表移除 {ea_name}")
        except Exception as e:
            print(f"⚠️ 移除按鈕 click 失敗: {e}")
            return False
    else:
        print("⚠️ 搵唔到「移除」按鈕")
        try:
            _sk('{ESC}')
        except Exception:
            pass
        return False
    
    # 6. 關閉 dialog（如果有）
    try:
        for w in app.windows():
            if w.class_name() == '#32770' and ('專家' in w.window_text() or 'Expert' in w.window_text()):
                for b in w.children():
                    try:
                        if b.element_info.class_name == 'Button' and '關閉' in b.window_text():
                            b.click()
                            time.sleep(1)
                            break
                    except Exception:
                        pass
                break
    except Exception:
        pass
    
    return True


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
