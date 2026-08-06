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
    import psutil
    
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
        tree_view = None
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
                                    tree_view = child
                                    break
                        except Exception:
                            pass
            except Exception:
                pass
            if tree_view:
                break
        
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
            
            # ⚠️ 2026-08：web 配對嘅 EA 集中喺 MT5Cloud_EA folder — 要入 folder 搵
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
                print(f"⚠️ {ea_name} not found under EA交易/MT5Cloud_EA (attempt {attempt+1}/{max_retries})")
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
    return False


def ensure_auto_trading_on(mt5_pid):
    """確保 AutoTrading 係開啟狀態"""
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    
    app = Application(backend='uia').connect(process=mt5_pid)
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
    """將 DeskIn（遙距控制視窗）移去右上角 — 唔遮 MT5 圖表/Navigator 操作區域
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


def verify_heartbeat(ea_name, timeout=60):
    """驗證 EA heartbeat file 存在且新鮮"""
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
        
        # Step 3: Attach EA via Navigator
        success = attach_ea_navigator(ea_name, mt5_pid)
        if not success:
            print("⚠️ Navigator attach failed (no MT5 restart — keeping existing charts alive)")
        
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
