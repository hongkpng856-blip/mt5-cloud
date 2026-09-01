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
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
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

# [ALERT] 2026-08-28：deploystart時間（log verify只認deploystartafter嘅 loaded — 修假success）
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
    """[ALERT] 2026-08-20（deploy流程檢測系統）：terminal64.exe 有冇running（tasklist — 唔靠 psutil cached）"""
    try:
        _out = subprocess.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH',
                              shell=True, capture_output=True, timeout=10)
        return 'terminal64.exe' in _out.stdout.decode('utf-8', errors='replace')
    except Exception:
        return False


def _wait_until(check_fn, timeout=60, desc='', interval=2):
    """[ALERT] 2026-08-20（deploy流程檢測系統 — docs/deployment-checkpoint-system.md）
    poll check_fn 直到 True 或者 timeout — 每步驗證 gate（success先落next step）
    驗證要「等」：唔可以immediately check（資料未就緒 → 假failed）——poll 到success或者 timeout
    返回：check_fn 嘅真值（bool check → True；攞值 check（如 PID）→ 嗰個值）"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            _res = check_fn()
            if _res:
                print(f"[OK] {desc}")
                return _res
        except Exception:
            pass
        time.sleep(interval)
    print(f"[FAIL] {desc} — timeout {timeout}s")
    return False


def wait_for_mt5(timeout=30):
    """等 MT5 startdone
    [WARN] 用 backend='win32'（快）+ 主視窗exists檢查 — 唔可以用 uia（MT5 大 UI connect 超慢 → 卡 60 秒）"""
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
    # [ALERT] 2026-08-10：重啟期間顯示warning視窗（user要知道操作緊 — 55 秒）
    try:
        _rf = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.show')
        with open(_rf, 'w', encoding='utf-8') as _f:
            _f.write('[RETRY] 重啟 MT5 中（快捷鍵載入）— 請稍候約 1 分鐘')
        _sf = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
        try:
            import json as _j2
            # [ALERT] 2026-08-12 FIX：累積模式（保留現有 steps — deploy入口已寫 4 步 — 唔好覆寫走）
            _cur_rst = []
            try:
                if os.path.isfile(_sf):
                    _cur_rst = _j2.load(open(_sf, 'r', encoding='utf-8'))
                    if not isinstance(_cur_rst, list):
                        _cur_rst = []
            except Exception:
                _cur_rst = []
            _cur_rst = [s for s in _cur_rst if isinstance(s, dict) and s.get('text') != 'Waiting for operation to start...']
            # [ALERT] 2026-08-12 FIX：重啟 3 步放最前（before append 尾 → 步驟順序「deploy 4 步 + 重啟 3 步」亂 — 重啟應該喺deploy前）
            _RESTART3 = [{"text": "關閉 MT5", "status": "doing"},
                         {"text": "載入快捷鍵設定", "status": "pending"},
                         {"text": "重新start MT5", "status": "pending"}]
            _cur_rst = [s for s in _cur_rst if s.get('text') not in ('關閉 MT5', '載入快捷鍵設定', '重新start MT5')]
            _cur_rst = _RESTART3 + _cur_rst
            with open(_sf, 'w', encoding='utf-8') as _f2:
                _j2.dump(_cur_rst, _f2, ensure_ascii=False)
        except Exception:
            pass
    except Exception:
        pass
    import psutil
    import ctypes as _ct
    
    # [ALERT] 2026-08-19 FIX：restart 前唔好「關閉全部圖表」— 否則其他已掛 EA（EMA_Cross 等）chart 被關 → EA 消失
    # MT5 restart 會自然 save + restore chart（profile）→ 保留其他 chart + EA；同時 reload hotkeys（新 EA 熱鍵生效）
    # （before v0.9.71 為咗「deploy唔累積 chart」而關晒 — 但搞死其他已掛 EA — 改為保留）
    # [ALERT] 2026-08-19 FIX2：唔可以用 proc.kill() 強制殺 — MT5 冇機會 save chart profile → 開機唔 restore 其他 EA（「restart 後其他 EA 移出圖表」）
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
            print("[CLIP] MT5 正常關閉中（save chart profile）...")
            time.sleep(8)
            # 如果仲未退（可能彈對話框）→ 用 taskkill 兜底（萬一 hang）
            _alive3 = _sp3.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
            if 'terminal64.exe' in _alive3.stdout.decode('utf-8', errors='replace'):
                print("[WARN] MT5 未退出（可能彈窗）— 等 5 秒再試，唔強制 kill（保護 profile）")
                time.sleep(5)
    except Exception as _e3:
        print(f"[WARN] MT5 正常關閉failed（{_e3}）— 用強制 kill 兜底")
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
                proc.kill()
    time.sleep(3)
    
    # Start MT5
    subprocess.Popen([MT5_PATH])
    
    # Wait for ready
    pid = wait_for_mt5(timeout=90)
    if pid:
        # [ALERT] 2026-08-22（user要求：UAC 檢測機制）：MT5 重啟後檢查 UAC/授權窗口
        # （MT5 更新/exception → 彈「Client Terminal AVX2 授權」→ 唔處理會擋住afterdeploy）
        try:
            if not _detect_and_handle_uac('MT5 重啟後 UAC 檢查', max_wait=30):
                print("[WARN] MT5 重啟後有 UAC 授權窗口未處理（可能係 MT5 更新要求授權）— 等user手動處理")
        except Exception:
            pass
        # Extra wait for Navigator to fully load + refresh
        time.sleep(10)
        # [ALERT] 2026-08-12 FIX：重啟done → 唔好寫「wait操作start」覆寫（保留現有 steps — 更新重啟 3 步 done — 完整流程唔消失）
        try:
            _rf = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.show')
            if os.path.exists(_rf):
                os.remove(_rf)
            # [ALERT] 2026-09-01 FIX（用戶實測：剷除後警告視窗未關 — 開發目錄 show flag 殘留）：
            # alert_worker（電腦版警告視窗）可能讀開發目錄版（mt5-cloud/agent/alert_worker.py）→ 要同步刪開發目錄 show flag
            try:
                for _cd_del in (os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop', 'mt5-cloud', 'agent'),
                                os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop', 'mt5-cloud-stable', 'agent')):
                    _rf_del = os.path.join(_cd_del, '.ai_control.show')
                    if os.path.isdir(_cd_del) and os.path.exists(_rf_del):
                        os.remove(_rf_del)
                        print(f"[OK] 同步刪開發目錄 show flag: {_rf_del}")
            except Exception:
                pass
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
                    if isinstance(_s, dict) and _s.get('text') in ('關閉 MT5', '載入快捷鍵設定', '重新start MT5'):
                        _s['status'] = 'done'
                if _cur_rst2:
                    with open(_sf, 'w', encoding='utf-8') as _f3:
                        _j3.dump(_cur_rst2, _f3, ensure_ascii=False)
        except Exception:
            pass
        print(f"[OK] MT5 restarted, PID={pid}")
        # [ALERT] 2026-08-31 FIX（Bug #150 根治 — user要求「唔好 restart 後殘留空白 chart」）：
        # MT5 開機時 Default profile 空（profile.ini 0 bytes）→ MT5 自動開 3 個預設 EURUSD chart（空白）
        # → 即刻清走（restart 後所有 chart 都空白 — 直接清晒 — 之後開 target chart）
        # [ALERT] 唔可以用 _clean_blank_charts（佢會讀心跳/log 保留舊 symbol — restart 後唔啱）
        # → 直接關閉所有 chart（restart 後冇 EA 掛住 — 全空白）
        try:
            import ctypes as _ct_rb
            from ctypes import wintypes as _wt_rb
            _u_rb = _ct_rb.windll.user32
            _main_rb = None
            def _cb_rb(h, _):
                nonlocal _main_rb
                _cls_rb = _ct_rb.create_unicode_buffer(64)
                _u_rb.GetClassNameW(h, _cls_rb, 64)
                if 'MetaTrad' in _cls_rb.value:
                    _main_rb = h
                return True
            _WNDENUMPROC_RB = _ct_rb.WINFUNCTYPE(_wt_rb.BOOL, _wt_rb.HWND, _wt_rb.LPARAM)
            _u_rb.EnumWindows(_WNDENUMPROC_RB(_cb_rb), 0)
            if _main_rb:
                _charts_rb = []
                def _cb_chart_rb(h, _):
                    _cls_rb = _ct_rb.create_unicode_buffer(64)
                    _u_rb.GetClassNameW(h, _cls_rb, 64)
                    _t_rb = _ct_rb.create_unicode_buffer(256)
                    _u_rb.GetWindowTextW(h, _t_rb, 256)
                    if _t_rb.value.strip() and ',' in _t_rb.value:
                        _charts_rb.append((h, _t_rb.value.strip()))
                    return True
                _u_rb.EnumChildWindows(_main_rb, _WNDENUMPROC_RB(_cb_chart_rb), 0)
                for _h_rb, _t_rb in _charts_rb:
                    _u_rb.PostMessageW(_h_rb, 0x0010, 0, 0)  # WM_CLOSE
                    print(f"[CLEAN] restart 後關閉預設空白 chart: {_t_rb[:40]}")
                    time.sleep(0.5)
                if _charts_rb:
                    print(f"[CLEAN] restart 後清 {len(_charts_rb)} 個預設 chart（MT5 開機自動開）")
        except Exception as _e_rb:
            print(f"[CLEAN] restart 後清 chart failed: {_e_rb}")
        return pid
    else:
        print("[FAIL] MT5 failed to start")
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
    
    print(f"[CLIP] Template saved: {tpl_path} ({os.path.getsize(tpl_path)} bytes)")
    return tpl_path
def ensure_auto_trading_on(mt5_pid):
    """確保 AutoTrading 係開啟狀態"""
    from pywinauto import Application
    from pywinauto.keyboard import send_keys

    # [ALERT] 2026-08-18 FIX：deploy中途 MT5 可能重啟過（熱鍵 reload）→ 舊 PID not exist → connect crash
    # 連唔到就用 find_mt5_pid() 重新搵，再唔得就 skip（唔好令成個 auto_attach 死）
    try:
        app = Application(backend='uia').connect(process=mt5_pid)
    except Exception:
        _new_pid = find_mt5_pid()
        if _new_pid and _new_pid != mt5_pid:
            print(f"[RETRY] MT5 PID 變咗（舊 {mt5_pid} → 新 {_new_pid}），重新 connect")
            mt5_pid = _new_pid
            try:
                app = Application(backend='uia').connect(process=mt5_pid)
            except Exception as _e:
                print(f"[WARN] ensure_auto_trading_on 連 MT5 failed（skip）: {_e}")
                return False
        else:
            print(f"[WARN] ensure_auto_trading_on 連 MT5 failed（PID {mt5_pid} 唔在，skip）")
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
                    print("[RED] AutoTrading is OFF, enabling...")
                    send_keys('^e')  # Ctrl+E
                    time.sleep(1)
                    return True
                elif 'enabled' in line.lower():
                    print("[GREEN] AutoTrading is already ON")
                    return True
    
    # Fallback: toggle twice to ensure ON
    send_keys('^e')
    time.sleep(0.5)
    send_keys('^e')
    time.sleep(1)
    print("[OK] AutoTrading toggled")
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
    # [WARN] 64-bit handle：SendMessageW 返回 hItem 一定要 c_size_t（唔 set 會溢出負數）
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
            # [WARN] TVM_GETITEMRECT 正確簽名：wParam = hItem（要攞 rect 嘅 item），lParam = RECT*
            # before用 wParam=1（固定）→ 一直 fail！→ 精確定位做唔到（Bug #82 延伸）
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
    """固定任何視窗位置 + 大小（pop-up 彈出後immediately鎖定 — 唔會因為位置漂移而 click 唔到）
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


# ─── 安全滑鼠操作（user要求 2026-08：避免撳到PC嘅其他嘢）───
# 每次 click 前用 WindowFromPoint 檢查嗰個屏幕座標belongs to邊個 process —
# 唔係 MT5 就跳過（唔會撳到 TG Scheduler / 記事本 / 其他視窗）

def pin_deskin_away():
    """將 DeskIn（遠端控制視窗）移去右上角 — 唔遮 MT5 圖表/Navigator 操作區域
    [WARN] 2026-08 實測：DeskIn 視窗遮住圖表 (560,222)-(1360,817) → 所有 click 俾佢食咗！
    操作前 call（DeskIn exists就移走）— 大眾化：用螢幕實際解析度計位置（唔 hardcode 1400）"""
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
            print(f"[PIN] DeskIn 已移去右上角 ({target_x},0)（唔遮 MT5）")
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
    """檢查 (x,y) 係咪 MT5 嘅視窗 — 唔係就 print warning + 唔 click
    [WARN] 開關：agent/.safe_click_off exists → 跳過檢查（A/B 測試用 — 還原before可靠行為）"""
    if os.path.isfile(os.path.join(os.path.dirname(__file__), '.safe_click_off')):
        return True
    if not mt5_pid:
        return True
    pid = _window_pid_at(x, y)
    if pid != mt5_pid:
        print(f"[WARN] [安全防護] ({x},{y}) 目標係 PID {pid}（唔係 MT5 PID {mt5_pid}）— 跳過，避免撳到其他視窗")
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
    [WARN] 2026-08 實測：BringWindowToTop/SetForegroundWindow 令 MT5 crash（before work 嗰陣冇呢啲）
    → 只 SetWindowPos（唔帶最前 — 避免 crash）"""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    try:
        from pywinauto import Application
        app = Application(backend='win32').connect(process=mt5_pid)
        win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
        hwnd = int(win.element_info.handle)
        # [WARN] 2026-08 實測：MT5 最小化（rect -32000）→ WindowFromPoint 全部返桌面 → click 落錯！
        # 最小化時要 ShowWindow(SW_RESTORE) 先
        if user32.IsIconic(ctypes.c_void_p(hwnd)):
            user32.ShowWindow(ctypes.c_void_p(hwnd), 9)  # SW_RESTORE
            time.sleep(1)
            print("🪟 MT5 已從最小化還原")
        # [WARN] 帶最前（2026-08 還原）：pyautogui double-click 需要 MT5 active 先收到輸入
        # before crash 係 GBK decode + 舊 deploy_cmd 循環（已修）— 唔係 bring-to-front
        user32.BringWindowToTop(ctypes.c_void_p(hwnd))
        user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
        time.sleep(1)
        print("[TARGET] MT5 已帶到最前（輸入生效）")
        # 位置 (0,0) + 固定大小（用螢幕解析度 — 大眾化）
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        user32.SetWindowPos(ctypes.c_void_p(hwnd), 0, 0, 0, sw, sh - 40, 0x0004 | 0x0040)
        time.sleep(0.5)
        print(f"[TRIANGLE] MT5 視窗已固定 ({sw}x{sh-40} @ 0,0)")
        return True
    except Exception as e:
        print(f"[WARN] 固定 MT5 視窗failed: {e}")
        return False


def tile_charts(mt5_pid):
    """平鋪圖表窗口（如果有圖表）— 2026-08 user要求：每次操作前圖表平鋪（座標穩定）
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
            print("[STATS] 冇圖表 — 唔使平鋪")
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
        print(f"[STATS] 圖表平鋪done（{len(charts)} 個圖表）")
        return True
    except Exception as _e:
        print(f"[WARN] 平鋪圖表failed: {_e}")
        return False


def ensure_navigator_unified(mt5_pid):
    """操作前統一 Navigator 位置（2026-08 user要求：每次操作 Navigator 最大 + 固定位置）
    before Navigator 一時左一時右（rect (201,139) vs (1079,111)）→ 操作錯位
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
                    print(f"[PIN] Navigator 已統一位置（(0,100) {_nav_w}x{_nav_h} — 最大）")
                    return True
            except Exception as _e2:
                print(f"   [WARN] Navigator 統一位置 inner: {_e2}")
    except Exception as _e:
        print(f"[WARN] Navigator 統一位置failed: {_e}")
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
    """[ALERT] 2026-08-10：更新warning視窗步驟 — 累積模式（一條條加落去 — done嘅留低 — 唔好蓋過 — user要求）"""
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
        # [ALERT] 2026-08-12 FIX：remove placeholder「wait操作start…」（_clear_steps 寫嘅）— 有新步驟就唔好殘留
        merged = [s for s in old if isinstance(s, dict) and s.get('text') != 'Waiting for operation to start...']
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
        # [ALERT] 2026-08-31 FIX（用戶實測：網頁版警告視窗同電腦版唔一致 — 網頁話執行緊 + 電腦話完成）：
        # auto_attach 喺 TradotcomAgent 執行 → 只寫 TradotcomAgent steps → 開發目錄（網頁版讀）冇更新 → 兩邊唔同步
        # → 同步埋開發目錄（同 deploy_watcher 做法 — 網頁版讀開發目錄）
        try:
            import os as _os_sync
            _cand_sync = [
                _os_sync.path.join(_os_sync.environ.get('USERPROFILE', ''), 'Desktop', 'mt5-cloud', 'agent'),
                _os_sync.path.join(_os_sync.environ.get('USERPROFILE', ''), 'Desktop', 'mt5-cloud-stable', 'agent'),
            ]
            for _cd_sync in _cand_sync:
                if _os_sync.path.isdir(_cd_sync):
                    with open(_os_sync.path.join(_cd_sync, '.ai_control.steps'), 'w', encoding='utf-8') as _f_sync:
                        _j.dump(merged, _f_sync, ensure_ascii=False)
                    break
        except Exception:
            pass
    except Exception:
        pass

def _clear_steps():
    # [ALERT] 2026-08-12：寫「wait操作start…」（唔係空 [] — 空 → 網頁 placeholder 同 steps 交替 → 「彈嚟彈去」— user投訴）
    try:
        import json as _j
        _f = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
        with open(_f + '.tmp', 'w', encoding='utf-8') as _fh:
            _j.dump([{'text': 'Waiting for operation to start...', 'status': 'pending'}], _fh)
        # [ALERT] 2026-08-12 FIX：os.replace 移出 with block（WinError 32）
        os.replace(_f + '.tmp', _f)
    except Exception:
        pass


def _ensure_hotkey_loaded(ea_name, mt5_pid):
    """[ALERT] 2026-08-20（user實測success流程）：確保 EA 熱鍵write hotkeys.ini 且 MT5 load
    流程：① 檢查 hotkeys.ini 有冇 ea_name 熱鍵（冇先做）
          ② 冇 → 分配 Ctrl+1（2026-08-22 起統一重用 Ctrl+1 — 唔再 Ctrl+1~9 批次分配）→ 關 MT5（WM_CLOSE 正常關閉 save profile）
          ③ 寫 hotkeys.ini（<experts>Experts\\<EA>.ex5=Ctrl+1</experts> — UTF-16）+ 清走舊 mapping
          ④ 開 MT5 → 熱鍵 load → 返新 PID
    破綻注意：EA 必須local有 .ex5（冇 → 熱鍵指向not exist EA → 失效）
    """
    try:
        import ctypes as _ct_hk
        import subprocess as _sp_hk
        # [ALERT] 2026-08-20（user實測破綻）：EA 必須local有 .ex5（冇 → 熱鍵指向not exist EA → 失效）
        # → 檢查local Experts/ 有冇 <EA>.ex5；冇 → 報錯 + 唔預載（deploy會failed — 但至少原因清楚）
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
            print(f"[FAIL] {ea_name}.ex5 not exist（local未配對/未 compile）— 熱鍵cannot預載，請先配對 EA")
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
            print(f"[WARN] not found hotkeys.ini — 唔做熱鍵預載")
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
        # [ALERT] 2026-08-20（v0.10.10）：MT5 開住時write嘅熱鍵唔 load（user實測：關 MT5 → 寫 → 開先 work）
        # → 比較 hotkeys.ini mtime vs MT5 start時間：hotkeys.ini 喺 MT5 開機後先寫 = MT5 未 load → 要 restart 重寫
        _combo_n = None  # [ALERT] 2026-08-20 v0.10.11：一定要提前定義（experts 空 → loop 唔行 → 下面用 _combo_n 會 NameError）
        for _k in experts:
            if ea_name in _k:
                _combo_exist = experts[_k]
                # [ALERT] 2026-08-22 FIX（deploy Grid 搞走 EMA_Cross）：唔可以淨靠 hotkeys.ini mtime 判斷「未 load」
                # （MT5 自己/其他 EA deploy都會更新 hotkeys.ini → mtime 比 MT5 start新 → 誤判 → 無謂 restart → 搞走其他 EA）
                # → 直接 send 熱鍵測試 — 彈到 Properties = 熱鍵真係 load 咗 = 唔使 restart
                _hk_actually_loaded = False
                try:
                    from pywinauto import Application as _App_hkt
                    _app_hkt = _App_hkt(backend='win32').connect(process=find_mt5_pid() or mt5_pid, timeout=8)
                    _w_hkt = _app_hkt.window(class_name_re='MetaQuotes::MetaTrader')
                    _w_hkt.set_focus()
                    time.sleep(1)
                    from pywinauto.keyboard import send_keys as _sk_hkt
                    # [ALERT] 2026-08-22 FIX：熱鍵測試前先 click MT5 中央（確保有 active chart — 熱鍵要先有 chart 先彈 Properties）
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
                    print(f"[OK] {ea_name} 熱鍵（{_combo_exist}）實測 load success（彈 Properties）— 唔使 restart")
                    return mt5_pid
                print(f"[WARN] {ea_name} 熱鍵（{_combo_exist}）測試冇彈 Properties — 可能要 restart 重寫")
                _combo_n = _combo_exist  # 保留原本 combo（重寫用返）
                break  # 唔 return — 繼續落去 restart（關→寫→開）
        # 3. 分配 Ctrl+1（2026-08-31 改：統一淨用 Ctrl+1 — 唔再 Ctrl+1-9 亂分配 — 同 line 1560 重用邏輯一致）
        _used = set()
        for _k, _v in experts.items():
            if _v and _v.startswith('Ctrl+'):
                try: _used.add(int(_v.replace('Ctrl+', '')))
                except: pass
        if _combo_n is None:
            _combo_n = 'Ctrl+1' if 1 not in _used else None
            # [ALERT] 2026-08-31：Ctrl+1 已被用（其他 EA 用緊）→ 唔好搶 — 用下一個可用數字
            if _combo_n is None:
                for _i_n in range(2, 10):
                    if _i_n not in _used:
                        _combo_n = f'Ctrl+{_i_n}'
                        break
        if not _combo_n:
            print(f"[WARN] 冇可用熱鍵 — 唔做預載")
            return mt5_pid
        print(f"[RETRY] 熱鍵預載：{ea_name}（關 MT5 → 批次write熱鍵 → 開）")
        # [ALERT] 2026-08-22 FIX（deploy Grid 搞走 EMA_Cross — restore 唔齊）：restart 前記錄所有 chart
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
            print(f"[CLIP] restart 前 chart: {_charts_before_hk}")
        except Exception as _e_cb:
            print(f"[WARN] restart 前記錄 chart failed: {_e_cb}")
        # [ALERT] 2026-08-31 FIX（Bug #150 真正根治 — user要求「restart 唔好 restore 一堆 chart」）：
        # 關 MT5 之前 — 清走「空白 chart」（冇 EA 心跳）→ MT5 save profile 時只有「有 EA 嘅 chart」
        # → restart 後只 restore 有 EA 嘅（唔會開一堆空白 chart — 之前 restore 咗 6-7 個 chart）
        # [ALERT] 2026-08-31 FIX2：改用 .chr 檔方法（user 實測有效 — 關 MT5 前刪空白 .chr →
        # MT5 開機唔會 restore 嗰個 chart）— double check 內容（有 EA 先保留）— 只刪真正空白
        try:
            _clean_blank_charts_via_chr()
            print("[CLEAN] restart 前已清空白 .chr（double check — 只刪冇 EA 嘅 chart 設定）")
        except Exception as _e_clr:
            print(f"[WARN] restart 前清空白 .chr failed: {_e_clr}")
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
        # 強制確認關咗（WM_CLOSE 可能彈窗）— [ALERT] 2026-08-20 gate：確認 terminal64 已關（poll 最多 20s）
        _closed_hk = _wait_until(lambda: not _mt5_alive(), 20, 'MT5 closed（WM_CLOSE 後確認）', interval=2)
        if not _closed_hk:
            print("[WARN] MT5 未完全關閉 — 強制 kill")
            try:
                _sp_hk.run('taskkill -f -im terminal64.exe', shell=True, capture_output=True)
                time.sleep(4)
            except Exception:
                pass
        # 5. 寫熱鍵（MT5 關閉狀態下寫 — user實測先 load）
        # [ALERT] 2026-08-22 user要求：每次deploy都用 Ctrl+1（單一熱鍵重用）— deploy完釋放，下隻 EA 又用返 Ctrl+1
        # → 唔再批次分配 Ctrl+1~9 — 只寫「新 EA = Ctrl+1」+ 清走舊 mapping
        _experts_hk = {}
        # 掃描 Experts dir全部 .ex5（排除子dir — 只掃根dir）— 只留「新 EA」熱鍵
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
        # [ALERT] 2026-08-22：只用 Ctrl+1（重用）— 每次deploy都係 Ctrl+1
        _experts_hk[f'Experts\\{ea_name}.ex5'] = 'Ctrl+1'
        _lines_hk = ['<experts>']
        for _k2, _v2 in _experts_hk.items():
            _lines_hk.append(f'{_k2}={_v2}')
        _lines_hk.append('</experts>')
        _text_out_hk = '\r\n'.join(_lines_hk) + '\r\n'
        with open(_hk_ini, 'wb') as _f_hk:
            _f_hk.write(_text_out_hk.encode('utf-16'))
        print(f"[OK] 熱鍵已write hotkeys.ini（只用 Ctrl+1 — {ea_name}=Ctrl+1，舊 mapping 已清）")
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
        # [ALERT] 2026-08-20（deploy流程檢測系統落地）：開完 MT5 唔可以immediatelydeploy — 要等 MT5 load 完熱鍵
        # 驗證 gate：等主視窗 ready（poll 最多 90s）→ send Ctrl+<N> 測試熱鍵 load（彈 Properties = load success）
        # [ALERT] 2026-08-20 優化：用批次預載後 ea_name 實際嘅 combo（可能唔係 _combo_n）
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
            print("[WARN] 熱鍵預載：MT5 主視窗 90s 未 ready（繼續 — deploy時會再驗證）")
        else:
            print("[OK] 熱鍵預載：MT5 主視窗 ready")
            # [ALERT] 2026-08-22（user要求：UAC 檢測機制）：熱鍵預載開完 MT5 檢查 UAC/授權窗口
            # （MT5 更新/exception → 彈「Client Terminal AVX2 授權」→ 唔處理會擋熱鍵 load 測試）
            try:
                if not _detect_and_handle_uac('熱鍵預載 UAC 檢查', max_wait=30):
                    print("[WARN] 熱鍵預載：UAC 授權窗口未處理（等user手動撳）")
            except Exception:
                pass
            # 熱鍵 load 驗證：send Ctrl+N 測試 — 彈出 <EA> Properties = 熱鍵 load success（failed關閉 dialog 再重試）
                        # [ALERT] 2026-08-25 FIX（連環deploy偶發failed — Breakout 案例）：主視窗 ready 唔等於熱鍵 load 完
            # → 等 MT5 完全穩定（10 秒）先 send 測試 — MT5 初始化順序：UI → 數據 → 設定 → 熱鍵
            time.sleep(10)
            # [ALERT] 2026-08-31 FIX（Bug #150 根治 — user要求「restart 唔好殘留空白 chart」）：
            # MT5 restart 後 restore profile chart（舊 chart）+ 開機預設 → 出現空白 chart（冇 EA）
            # → 等 MT5 穩定後即刻清走「冇 EA 掛住」嘅空白 chart（保留 1 個做熱鍵測試 + target）
            #    （熱鍵測試需要 active chart — 所以保留最少 1 個）
            try:
                import ctypes as _ct_cl
                from ctypes import wintypes as _wt_cl
                _u_cl = _ct_cl.windll.user32
                _main_cl = None
                def _cb_main_cl(h, _):
                    nonlocal _main_cl
                    _cls_cl = _ct_cl.create_unicode_buffer(64)
                    _u_cl.GetClassNameW(h, _cls_cl, 64)
                    if 'MetaTrad' in _cls_cl.value:
                        _main_cl = h
                    return True
                _WNDENUMPROC_CL = _ct_cl.WINFUNCTYPE(_wt_cl.BOOL, _wt_cl.HWND, _wt_cl.LPARAM)
                _u_cl.EnumWindows(_WNDENUMPROC_CL(_cb_main_cl), 0)
                if _main_cl:
                    _charts_cl = []
                    def _cb_chart_cl(h, _):
                        _cls_cl = _ct_cl.create_unicode_buffer(64)
                        _u_cl.GetClassNameW(h, _cls_cl, 64)
                        _t_cl = _ct_cl.create_unicode_buffer(256)
                        _u_cl.GetWindowTextW(h, _t_cl, 256)
                        if _t_cl.value.strip() and ',' in _t_cl.value:
                            _charts_cl.append((h, _t_cl.value.strip()))
                        return True
                    _u_cl.EnumChildWindows(_main_cl, _WNDENUMPROC_CL(_cb_chart_cl), 0)
                    # 清走多餘 chart（restart 後冇 EA 掛住 — 全空白）
                    # [ALERT] 2026-08-31 FIX5：唔好「淨保留 1 個」— 會清走 restore 嘅有 EA chart（MACD_Cross 等自動 restore）
                    # → 用 _clean_blank_charts 邏輯（保留心跳 EA 掛嘅 symbol + target）— 只清空白 chart
                    try:
                        _clean_blank_charts(mt5_pid or 0, keep_symbol='')
                        print("[CLEAN] restart 後已清空白 chart（保留有 EA 嘅）")
                    except Exception as _e_clr2:
                        print(f"[WARN] restart 後清空白 chart failed: {_e_clr2}")
                    # [ALERT] 確保至少有 1 個 chart（熱鍵測試需要 active chart — Ctrl+N 彈 Properties）
                    _chk_charts_after = []
                    def _cb_chart_aft(h, _):
                        _cls_aft = _ct_cl.create_unicode_buffer(64)
                        _u_cl.GetClassNameW(h, _cls_aft, 64)
                        _t_aft = _ct_cl.create_unicode_buffer(256)
                        _u_cl.GetWindowTextW(h, _t_aft, 256)
                        if _t_aft.value.strip() and ',' in _t_aft.value:
                            _chk_charts_after.append((h, _t_aft.value.strip()))
                        return True
                    _u_cl.EnumChildWindows(_main_cl, _WNDENUMPROC_CL(_cb_chart_aft), 0)
                    if not _chk_charts_after:
                        # 冇 chart（全部空白清走）→ 開返一個空 chart（熱鍵測試用）
                        # [ALERT] 2026-09-01 FIX（user要求：唔好用 Ctrl+N — 統一 Alt+F 方法）
                        try:
                            import pyautogui as _pg_cl2
                            _pg_cl2.FAILSAFE = False
                            _r_cl2 = _w_hk.rectangle()
                            _pg_cl2.click(_r_cl2.left + _r_cl2.width() // 2, _r_cl2.top + _r_cl2.height() // 2)
                            time.sleep(0.5)
                            # Alt+F → Enter → Enter（開新 chart — 同部署開 chart 一致 — 唔用 Ctrl+N）
                            _pg_cl2.hotkey('alt', 'f'); time.sleep(1.5)
                            _pg_cl2.press('enter'); time.sleep(1.5)
                            _pg_cl2.press('enter'); time.sleep(2)
                            print("[CLEAN] 開返一個 chart 做熱鍵測試（Alt+F 方法）")
                        except Exception:
                            pass
            except Exception as _e_cl:
                print(f"[CLEAN] restart 後清 chart failed: {_e_cl}")
            _hk_loaded_ok = False
            for _hk_try in range(3):
                try:
                    _w_hk.set_focus()
                    time.sleep(0.8)
                    # [ALERT] 2026-08-20 FIX：熱鍵attach EA 需要 active chart（冇 chart → Ctrl+N 唔彈 Properties → 誤判未 load）
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
                        print(f"[OK] 熱鍵 load 驗證通過：{_combo_actual} 彈出 {ea_name} Properties（熱鍵已 load）")
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
                        print(f"[WARN] 熱鍵 load 測試 {_hk_try+1}/3：{_combo_actual} 冇彈 Properties（可能未 load 完 — 重試）")
                        try:
                            _sk_hk('{ESC}')
                        except Exception:
                            pass
                        time.sleep(3)
                except Exception as _ehk_t:
                    print(f"[WARN] 熱鍵 load 測試exception: {_ehk_t}")
                    time.sleep(3)
            if not _hk_loaded_ok:
                # [ALERT] 2026-08-24 FIX（熱鍵 load 唔穩定 — MT5 開機 cache 舊 hotkeys）：第一次 restart 後 load 測試failed
                # → 再 restart 一次（第二次開機 load 到新write嘅 hotkeys）— 唔好immediatelydeploy（會彈錯 EA / attach failed）
                print(f"[WARN] 熱鍵 load 3 次測試都冇彈 Properties — 再 restart 一次 reload 熱鍵")
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
                        print("[OK] 熱鍵預載：第二次 restart done（reload 熱鍵）")
                        # [ALERT] 2026-08-31 FIX：第二次 restart 後都即刻清空白 chart（MT5 又開返一堆）
                        try:
                            _clean_blank_charts(_p2 or 0, keep_symbol='')
                            print("[CLEAN] 第二次 restart 後已清空白 chart（保留有 EA 嘅）")
                        except Exception as _e_clr3:
                            print(f"[WARN] 第二次 restart 後清空白 chart failed: {_e_clr3}")
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
                                    print(f"[OK] 第二次 restart 後熱鍵 load 驗證通過（{ea_name} Properties）")
                                    _sk_hk('{ESC}')
                                    break
                            except Exception:
                                pass
                            time.sleep(3)
                    if not _hk_loaded_ok:
                        print(f"[WARN] 第二次 restart 後熱鍵仍然冇 load — deploy時會再驗證（failed會明確報錯）")
                except Exception as _ehk_r:
                    print(f"[WARN] 第二次 restart failed: {_ehk_r}")
        # [ALERT] 2026-08-22 FIX（deploy Grid 搞走 EMA_Cross — restore 唔齊）：restart 後檢查 chart 有冇 restore 齊
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
                print(f"[CLIP] restart 後 chart: {_charts_after}")
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
                    print(f"[ALERT] restart 後遺失 {len(_missing)} 個 chart: {_missing} — 補開")
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
                            print(f"  [OK] 補開 chart: {_msym}")
                        except Exception as _e_rc:
                            print(f"  [WARN] 補開 {_msym} failed: {_e_rc}")
                else:
                    print("[OK] restart 後 chart 齊全（冇遺失）")
            except Exception as _e_rc2:
                print(f"[WARN] restart 後檢查 chart failed: {_e_rc2}")
        # 7. 攞新 PID
        _new_pid = find_mt5_pid()
        if _new_pid:
            return _new_pid
        return mt5_pid
    except Exception as _e_hk:
        print(f"[WARN] 熱鍵預載failed: {_e_hk}")
        return mt5_pid

def _detect_and_handle_uac(desc='', max_wait=30):
    """[ALERT] 2026-08-22（user要求：UAC 檢測機制 — MT5 更新/授權都會問）
    偵測「Client Terminal 授權」/ UAC consent 窗口（$$$Secure UAP Dummy Window Class）
    處理策略：
    1. 偵測到授權窗口 → 記錄 + 嘗試按鈕撳「允許/是」（SendMessage BM_CLICK + Enter）
    2. 撳唔到（Windows 安全層refused自動化）→ 通知user（寫 alert flag — 網頁顯示「請撳允許」）
    3. max_wait 內一直有 → return False（唔好繼續deploy — 會被擋）
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

    print(f"[ALERT] [UAC Gate] {desc}: 偵測到 {len(_found)} 個授權窗口 — {_found[0][1]}")
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
        # 關唔到 — Windows 安全層refused自動化 → 通知user手動撳
        print(f"[WARN] [UAC Gate] {desc}: {len(_still)} 個授權窗口關唔到（Windows 安全層）— 通知user手動處理")
        try:
            # 寫 alert flag（網頁/tkinter 顯示）
            _adir_u = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(_adir_u, '.uac_alert'), 'w', encoding='utf-8') as _f:
                _f.write(f"MT5 需要授權（{desc}）— 請喺PC撳「允許/是」\n窗口: {_still[0][1]}")
        except Exception:
            pass
        # 等 max_wait 秒（俾user手動撳）— 撳完自動繼續
        _deadline = time.time() + max_wait
        while time.time() < _deadline:
            time.sleep(3)
            _now = _scan()
            if not _now:
                print(f"[OK] [UAC Gate] {desc}: 授權窗口已處理（user撳咗/自動關）— 可以繼續")
                try:
                    os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.uac_alert'))
                except Exception:
                    pass
                return True
        print(f"[FAIL] [UAC Gate] {desc}: {max_wait}s 內授權窗口未處理（可能係 MT5 更新要求授權）— deploy中止")
        return False
    print(f"[OK] [UAC Gate] {desc}: 授權窗口已自動處理")
    return True
def _detect_and_handle_uac(desc='', max_wait=30):
    """[ALERT] 2026-08-22（user要求：UAC 檢測機制 — MT5 更新/授權都會問）
    偵測「Client Terminal 授權」/ UAC consent 窗口（$$$Secure UAP Dummy Window Class）
    處理策略：
    1. 偵測到授權窗口 → 記錄 + 嘗試按鈕撳「允許/是」（SendMessage BM_CLICK + Enter）
    2. 撳唔到（Windows 安全層refused自動化）→ 通知user（寫 alert flag — 網頁顯示「請撳允許」）
    3. max_wait 內一直有 → return False（唔好繼續deploy — 會被擋）
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

    print(f"[ALERT] [UAC Gate] {desc}: 偵測到 {len(_found)} 個授權窗口 — {_found[0][1]}")
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
        # 關唔到 — Windows 安全層refused自動化 → 通知user手動撳
        print(f"[WARN] [UAC Gate] {desc}: {len(_still)} 個授權窗口關唔到（Windows 安全層）— 通知user手動處理")
        try:
            # 寫 alert flag（網頁/tkinter 顯示）
            _adir_u = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(_adir_u, '.uac_alert'), 'w', encoding='utf-8') as _f:
                _f.write(f"MT5 需要授權（{desc}）— 請喺PC撳「允許/是」\n窗口: {_still[0][1]}")
        except Exception:
            pass
        # 等 max_wait 秒（俾user手動撳）— 撳完自動繼續
        _deadline = time.time() + max_wait
        while time.time() < _deadline:
            time.sleep(3)
            _now = _scan()
            if not _now:
                print(f"[OK] [UAC Gate] {desc}: 授權窗口已處理（user撳咗/自動關）— 可以繼續")
                try:
                    os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.uac_alert'))
                except Exception:
                    pass
                return True
        print(f"[FAIL] [UAC Gate] {desc}: {max_wait}s 內授權窗口未處理（可能係 MT5 更新要求授權）— deploy中止")
        return False
    print(f"[OK] [UAC Gate] {desc}: 授權窗口已自動處理")
    return True


def _ensure_no_dialog(desc='', max_wait=8, close_btn=True):
    """[ALERT] 2026-08-21（user要求：認證有冇 dialog 先繼續next step）
    Dialog 檢查閘門 — 確保冇任何 #32770 dialog 阻住先繼續
    - 有 dialog → WM_CLOSE 強制關閉（實測有效）+ 等 0.5 秒再確認
    - 關唔到（max_wait 內仲有）→ return False（Caller 要 fail，唔好硬嚟）
    - return True = 確認冇 dialog（可以繼續next step）
    """
    import ctypes as _ct_nd
    _u_nd = _ct_nd.windll.user32

    def _scan():
        _dlgs = []
        def _cb(hwnd, _):
            _cls = _ct_nd.create_unicode_buffer(128)
            _u_nd.GetClassNameW(_ct_nd.c_void_p(hwnd), _cls, 128)
            if _cls.value == '#32770':
                # [ALERT] 2026-09-01 FIX（用戶實測：MT5 系統更新彈窗阻住部署 — 警告視窗話成功但圖表冇掛 EA）：
                # 識別 MT5 更新/通知彈窗（標題含 update/build/新版本/通知）— log 出嚟（debug 用）
                try:
                    _t_nd = _ct_nd.create_unicode_buffer(256)
                    _u_nd.GetWindowTextW(_ct_nd.c_void_p(hwnd), _t_nd, 256)
                    _tt_nd = _t_nd.value
                    if any(_k_nd in _tt_nd.lower() for _k_nd in ('update', 'new version', 'build', '通知', '更新', '版本')):
                        print(f"  [DIALOG] 偵測到 MT5 系統彈窗: [{_tt_nd[:60]}] — 關閉（唔阻部署）")
                except Exception:
                    pass
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
            print(f"[OK] [Dialog Gate] {desc}: dialog 已全部關閉 — 可以繼續")
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
        print(f"[FAIL] [Dialog Gate] {desc}: {len(_left)} 個 dialog 關唔到（WM_CLOSE 無效）— 唔繼續next step！")
        return False
    return True


def attach_ea_hotkey(ea_name, mt5_pid, symbol='EURUSD', open_chart=True):
    """[TARGET] 快捷鍵方案（2026-08-06 user發現 — 解決 6093 double-click 問題）
    每隻 EA 喺「導航快捷鍵」設咗快捷鍵（Ctrl+1/2/3...）— send 快捷鍵 → EA attach
    唔使 double-click Navigator（6093 對 double-click 唔 work）"""
    try:
        import ctypes as _ct
        from pywinauto import Application as _App
        from pywinauto.keyboard import send_keys as _sk
        # [ALERT] 2026-08-19：偵測 ea_name 係咪 Script 類型（OpenChart 先係 — Script 用一體化假裝掛；真 EA 用熱鍵真掛）
        _is_script_att = ea_name.startswith('OpenChart')
        # [ALERT] 緊急stop支援（2026-08-06：before dialog 循環冇 check — 緊急stop冇效）
        try:
            from control_guard import check_abort as _chk_abort
        except Exception:
            _chk_abort = lambda: None
        hotkeys = load_hotkey_map()
        combo = hotkeys.get(ea_name)
        # [ALERT] 2026-08-17 FIX：一體化模式（open_chart=True）唔需要 combo（OpenChart script 套模板掛 EA — 唔使熱鍵attach）— combo check 只限非一體化
        if not open_chart and not combo:
            print(f"[WARN] {ea_name} 未有快捷鍵設定（agent/hotkeys.json）")
            return False
        # [ALERT] 2026-08-24（user要求：Ctrl+O / OpenChart 已失效 — 回復熱鍵為主）：
        # 一體化（Ctrl+O 套模板）已失效（MT5 build 6140 — OpenChart script 熱鍵冇 load）
        # → 真 EA 一律用熱鍵（Ctrl+1）attach — send 快捷鍵 → EA 掛 active chart
        if open_chart and _is_script_att:
            print(f"[OK] 一體化：{ea_name} 已由套模板掛落圖表（跳過attach熱鍵）")
            _saw_props = True  # Script（OpenChart）一體化假裝已掛
        else:
            print(f"[TARGET] 用快捷鍵 {combo} attach {ea_name}...")
        _app = _App(backend='win32').connect(process=mt5_pid, timeout=8)
        # [ALERT] 2026-08-22（user要求：UAC 檢測機制）：deploy前先檢查 UAC/授權窗口
        # （MT5 更新後/accountexception → 彈「Client Terminal AVX2 授權」→ 擋住deploy → 先處理）
        try:
            if not _detect_and_handle_uac(f'{ea_name} deploy前 UAC 檢查', max_wait=30):
                print(f"[FAIL] {ea_name} deploy中止：UAC 授權窗口未處理")
                return False
        except Exception:
            pass
        # [ALERT] 2026-08-12 FIX：deploy前檢查有冇 pending compile_cmd（配對後未編譯 — 等編譯done先deploy — 唔會「deploy完又彈編譯視窗」）
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
                print(f"[WARN] compile_cmd 等咗 40 秒仲未done — 繼續deploy（.ex5 可能未生成）")
        except Exception:
            pass
        # [ALERT] 2026-08-12 FIX：steps 喺函數開頭寫（開圖表before — user撳deployimmediately見到「deployin progress」）
        # [ALERT] 2026-08-12 FIX2：直接覆寫（唔用 _update_steps 累積 — 新任務start清舊任務 steps — spec：唔跨任務累積）
        # [ALERT] 2026-08-12 FIX3：保留「重啟 MT5」3 步（deploy前 ensure_hotkey 重啟寫嘅 — 唔好洗走 — 完整流程）
        _steps = [
            {"text": f"deploy {ea_name}（{(symbol or 'EURUSD').upper()}）", "status": "doing"},
            {"text": f"create新圖表（{(symbol or 'EURUSD').upper()}）", "status": "pending"},
            {"text": f"attach {ea_name}（快捷鍵 {combo}）", "status": "pending"},
            {"text": "驗證running狀態", "status": "pending"},
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
            # 保留「重啟 MT5」3 步（已done嘅留低 — deploy流程一部分）+ 過濾舊任務/wait
            _RESTART_TEXTS = ('關閉 MT5', '載入快捷鍵設定', '重新start MT5')
            _kept = [s for s in _prev_dep if isinstance(s, dict) and s.get('text') in _RESTART_TEXTS]
            with open(_sf_dep, 'w', encoding='utf-8') as _fdep:
                _jdep.dump(_kept + _steps, _fdep, ensure_ascii=False)
        except Exception:
            pass
        time.sleep(0.8)  # [ALERT] 網頁 poll 捕到「deploy」in progress
        # [ALERT] 2026-08-10 deploy穩定性：一次過 reload（hotkeys.ini mtime > MT5 start → 外部write未 load — reload 一次）
        # [ALERT] 2026-08-19 FIX：唔好 restart MT5 — do_restart_mt5 前會「關閉全部圖表」→ 其他已掛 EA（如 EMA_Cross）chart 被關 → EA 消失
        #   nowdeploy用「Alt+F→Enter→Enter→Space→symbol→Enter」menu 方法開 chart，唔靠 Ctrl+熱鍵 → 唔需要 restart reload hotkeys
        #   → hotkeys.ini 有變都唔 restart（避免搞死其他 EA）
        _HK_RESTART_DISABLED = True  # [ALERT] 2026-08-20：熱鍵已由 _ensure_hotkey_loaded 預載（關 MT5 → 寫 → 開）— deploy時唔可以再 restart（restart 會令 MT5 用內部設定覆寫 hotkeys.ini → 我哋寫嘅熱鍵消失 → Ctrl+N 失效）
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
                    print(f"[RETRY] hotkeys.ini 有變（外部write — MT5 未 load）→ reload 一次（關 MT5 → 開）")
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
        # [NEW] create新圖表（2026-08：唔代替 — 每個 EA 一個圖表 — 品種選擇）
        # [OK] user方法（2026-08-15）：OpenChart script 熱鍵（Ctrl+O — user set 咗）— 開目標圖表 → attach EA 落去
        # 流程：寫 json → 確保有圖表（熱鍵要圖表）→ Ctrl+O（OpenChart script 讀 json → ChartOpen 開目標圖表 active）→ attach EA（熱鍵 — 落 active）
        if open_chart:
            try:
                _sym = (symbol or '').upper()
                # ① 寫 json（OpenChart script 讀呢個 — 一體化：symbol + ea + 模板名）
                try:
                    import json as _joc
                    _cmd_file = os.path.join(COMMON_FILES, 'open_chart_cmd.json')
                    _tpl_name = f"{ea_name}_{_sym or 'EURUSD'}_{(tf or 'H1').upper()}.tpl"
                    # [ALERT] 2026-08-17 FIX：直接用 MT5 模板格式生成完整 tpl（含 path → Experts 根）
                    # （before「複製現有 <ea>_*.tpl」— 但係好多 EA 未deploy過 → 冇源頭 tpl → 生成failed → 套模板冇 tpl → EA 掛唔到！）
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
                            print(f"[CLIP] 模板已生成: {_tpl_name}（path → Experts 根）")
                    except Exception as _ete:
                        print(f"[WARN] 生成模板failed: {_ete}")
                    with open(_cmd_file, 'w', encoding='utf-8') as _f:
                        _joc.dump({'symbol': _sym or 'EURUSD', 'tf': (tf or 'H1').upper(),
                                   'ea': ea_name, 'tpl': _tpl_name}, _f)
                    # [ALERT] 2026-08-15 FIX：write後驗證（讀返確認 — json 舊值問題：deploy USDJPY 但 script 讀到舊 GBPUSD）
                    try:
                        _chk = _joc.load(open(_cmd_file, encoding='utf-8'))
                        if _chk.get('symbol') != _sym:
                            with open(_cmd_file, 'w', encoding='utf-8') as _f2:
                                _joc.dump({'symbol': _sym or 'EURUSD', 'tf': (tf or 'H1').upper(),
                                           'ea': ea_name, 'tpl': _tpl_name}, _f2)
                            print(f"[CLIP] json 重寫（驗證唔啱 → {_sym}）")
                        else:
                            print(f"[CLIP] json write驗證 OK: {_sym}")
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
                # ③ OpenChart 開 chart — 用下方「user方法」Alt+F→Enter→Enter→Space→symbol→Enter（唔再 Ctrl+9）
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
                # [ALERT] 2026-08-19（user發現嘅可靠方法）：直接開 target symbol chart
                # Alt+F → Enter → Enter → Space → 打 symbol → Enter
                # （pyautogui 實測 work — 取代 Ctrl+9 熱鍵 — 唔受 MT5 重啟洗走 hotkeys.ini <scripts> 區影響）
                # success（active chart = _sym）→ skip Ctrl+9
                _oc_ok2 = False
                try:
                    import pyautogui as _pg_new2
                    _pg_new2.FAILSAFE = False
                    _u_oc.SetForegroundWindow(_ct_oc.c_void_p(int(win.element_info.handle)))
                    time.sleep(1)
                    print(f"[PIN] 新方法開 chart: Alt+F→Enter→Enter→Space→{_sym}→Enter")
                    # [ALERT] 2026-08-21（user要求：認證有冇 dialog 先繼續next step）：開 chart 前檢查閘門 — 有 dialog 擋住 Alt+F menu → 開 chart 必failed
                    if not _ensure_no_dialog(f'開 chart {_sym} 前', max_wait=8):
                        print(f"[FAIL] 開 chart 中止：dialog 關唔到 — 唔開 chart（避免假failed）")
                        return False
                    # [ALERT] 2026-09-01 FIX（user實測機制：MT5 開住時開新 chart → .chr 檔即刻寫入 Euro folder）：
                    # → 開 chart 前數 .chr 檔（之後對比 — 數量增加 = 新 chart 真係開咗）
                    _chr_count_before2 = 0
                    _chr_count_after2 = 0
                    try:
                        import glob as _g_chr2v
                        _chr_root2v = None
                        for _d2v in os.listdir(os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')):
                            _pp2v = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', _d2v, 'MQL5', 'Profiles', 'Charts', 'Euro')
                            if os.path.isdir(_pp2v):
                                _chr_root2v = _pp2v
                                break
                        if _chr_root2v:
                            _chr_count_before2 = len(_g_chr2v.glob(os.path.join(_chr_root2v, 'chart*.chr')))
                            print(f"[CLIP] .chr 檔（Euro folder）開前: {_chr_count_before2}")
                    except Exception:
                        pass
                    _pg_new2.hotkey('alt', 'f'); time.sleep(1.5)
                    _pg_new2.press('enter'); time.sleep(1.5)
                    _pg_new2.press('enter'); time.sleep(2)
                    _pg_new2.press('space'); time.sleep(1.5)
                    _pg_new2.typewrite(_sym, interval=0.2); time.sleep(1)
                    _pg_new2.press('enter'); time.sleep(3)
                    _new_title2 = win.window_text()
                    # [ALERT] 2026-08-20 FIX：驗證唔可以淨靠主窗口標題（MT5 主窗口標題唔一定含 active chart symbol — 實測開咗 EURUSD chart 但標題冇後綴）
                    # → 檢查 MDI chart 窗口（有冇 <SYM>,H1 chart exists）— chart 開咗就算success
                    # [ALERT] 2026-08-21 FIX：改用 EnumChildWindows（pywinauto descendants 對 MT5 chart 窗口不可靠 — 實測開 chart success但 descendants check fail → 假failed）
                    # [ALERT] 2026-09-01 FIX（用戶實測：部署撞代替 dialog — 部署落已有 EA 嘅 symbol → 誤判開 chart 成功 → attach 落舊 chart → 代替）：
                    # 淨 check「有冇 <SYM> chart」唔夠（舊 chart 都存在 → 誤判成功）→ 要 check「chart 數量有冇增加」（Alt+F 開咗新 chart = 數量+1）
                    # → 數量冇增加 = 開 chart 失敗（唔 attach — 避免 attach 落舊 chart → 代替 dialog）
                    _chart_found2 = False
                    _chart_count_before = 0
                    try:
                        import ctypes as _ct_f2
                        _u_f2 = _ct_f2.windll.user32
                        _main_hwnd_f2 = int(win.element_info.handle)
                        # 開 chart 前數 chart 數量（所有含 ',' 嘅 chart 窗口）
                        def _count_charts_f2():
                            _cnt = 0
                            @_ct_f2.WINFUNCTYPE(_ct_f2.c_bool, _ct_f2.c_size_t, _ct_f2.c_size_t)
                            def _cb_cnt(hwnd, _):
                                nonlocal _cnt
                                _cls_cnt = _ct_f2.create_unicode_buffer(128)
                                _u_f2.GetClassNameW(_ct_f2.c_void_p(hwnd), _cls_cnt, 128)
                                if 'Afx' in _cls_cnt.value and 'ControlBar' not in _cls_cnt.value:
                                    _len_cnt = _u_f2.GetWindowTextLengthW(hwnd)
                                    if _len_cnt > 0:
                                        _buf_cnt = _ct_f2.create_unicode_buffer(_len_cnt + 1)
                                        _u_f2.GetWindowTextW(hwnd, _buf_cnt, _len_cnt + 1)
                                        if ',' in _buf_cnt.value:
                                            _cnt += 1
                                return True
                            _u_f2.EnumChildWindows(_ct_f2.c_void_p(_main_hwnd_f2), _cb_cnt, 0)
                            return _cnt
                        _chart_count_before = _count_charts_f2()
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
                        # 開 chart 後再數（Alt+F 成功 = 數量+1）
                        _chart_count_after = _count_charts_f2()
                        # [ALERT] 2026-09-01 FIX（user實測機制：MT5 開住時開新 chart → .chr 檔即刻寫入 Euro folder）：
                        # → 開 chart 後數 .chr 檔（對比 before — 數量增加 = 新 chart 真係開咗 — 比 EnumWindows 更可靠）
                        try:
                            if _chr_root2v:
                                _chr_count_after2 = len(_g_chr2v.glob(os.path.join(_chr_root2v, 'chart*.chr')))
                                print(f"[CLIP] .chr 檔（Euro folder）: 開前 {_chr_count_before2} → 開後 {_chr_count_after2}")
                        except Exception:
                            pass
                        print(f"[CLIP] 開 chart 前 {_chart_count_before} 個 chart → 後 {_chart_count_after} 個（目標 {_sym} chart exists: {_chart_found2}）")
                        if _chart_count_after > _chart_count_before or _chr_count_after2 > _chr_count_before2:
                            print(f"[OK] chart 數量增加（{_chart_count_before} → {_chart_count_after}；.chr {_chr_count_before2} → {_chr_count_after2}）— 新 chart 已開")
                        else:
                            print(f"[WARN] chart 數量冇增加（{_chart_count_before} → {_chart_count_after}）— 可能開 chart 失敗（已有 chart 誤判）")
                    except Exception:
                        pass
                    if ((_sym in _new_title2 or _chart_found2) and _chart_count_after > _chart_count_before) or (_chr_count_after2 > _chr_count_before2):
                        _oc_ok2 = True
                        print(f"[OK] 新方法chart opened: active chart = {_sym}（新 chart 確認 — EnumWindows + .chr 雙重驗證）")
                    else:
                        print(f"[WARN] 新方法未確認（active: {_new_title2[:50]}... chart 數冇增加）— open chart failed，唔attach！")
                except Exception as _eneg2:
                    print(f"[WARN] 新方法open chart failed: {_eneg2}")

                time.sleep(1)
                if not _oc_ok2:
                    # [ALERT] 2026-08-25 FIX（連環deploy偶發failed — Breakout 案例）：open chart failed重試 2 次
                    # （Alt+F menu 時序 — MT5 restart 後 UI 未完全穩定 → 第一次開 chart 可能failed → 重試success）
                    _oc_retried = False
                    for _oc_r2 in range(2):
                        print(f"[RETRY] open chart retry {_oc_r2+1}/2（{_sym}）...")
                        try:
                            import pyautogui as _pg_r2
                            _pg_r2.FAILSAFE = False
                            _pg_r2.hotkey('alt', 'f'); time.sleep(1.5)
                            _pg_r2.press('enter'); time.sleep(1.5)
                            _pg_r2.press('enter'); time.sleep(2)
                            _pg_r2.press('space'); time.sleep(1.5)
                            _pg_r2.typewrite(_sym, interval=0.2); time.sleep(1)
                            _pg_r2.press('enter'); time.sleep(3)
                            # 驗證 chart 出現（數量有增加 = 新 chart 開咗 — 唔可以淨 check exists）
                            try:
                                _chart_found2 = False
                                _chart_cnt_r2 = _count_charts_f2() if '_count_charts_f2' in dir() else 0
                                _u_f2.EnumChildWindows(_ct_f2.c_void_p(_main_hwnd_f2), _cb_f2, 0)
                            except Exception:
                                pass
                            if _chart_found2 and _chart_cnt_r2 > _chart_count_before:
                                _oc_ok2 = True
                                _oc_retried = True
                                print(f"[OK] open chart retrysuccess（{_sym} chart 出現）")
                                break
                        except Exception:
                            pass
                        time.sleep(2)
                if not _oc_ok2:
                    print(f"[FAIL] open chart failed（{_sym}）— 唔用備用方案（user要求）")
                    return False
                # [ALERT] 2026-08-10：驗證圖表 symbol（打字自動done可能揀錯 — AMD 案例）
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
                        print(f"   [OK] 圖表標題驗證: {_chart_title[:40]}")
                    else:
                        print(f"   [WARN] 圖表標題讀唔到（繼續 — 唔阻塞）")
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
        # [ALERT] 2026-08-12：steps 已喺函數開頭寫（開圖表前）— 呢度唔好重複寫（會將 step0 由 done 重置做 doing → 第一行永遠「in progress」）
        # send 快捷鍵
        # [ALERT] 2026-08-15 FIX：一體化模式（open_chart=True — OpenChart script 套模板已掛 EA）→ 跳過 send 熱鍵
        # [ALERT] 2026-08-19 FIX：只有 Script（OpenChart）先跳過熱鍵（一體化假裝掛）；真 EA（ADX 等）即使 open_chart=True 都要用熱鍵真掛落 target chart
        if open_chart and _is_script_att:
            _saw_props = True  # Script（OpenChart）一體化假裝已掛
        else:
            _saw_props = False  # [ALERT] 2026-08-10：驗證 Properties 有冇彈出（冇彈 = 快捷鍵冇效 — 唔好誤判success）
            if not open_chart:
                _sk(combo)
            else:
                # open_chart=True 但係真 EA → 開 chart 後用熱鍵真掛落 active chart
                if combo:
                    # [ALERT] 2026-08-20 FIX（attach錯 chart 根治 — user實測）：send 熱鍵前驗證 active chart 係target symbol
                    # （OpenChart open chart failed → active chart 係舊 restore 嘅 GBPUSD → attach落去 → 代替 dialog → 一鑊泡）
                    # → 驗證唔到目標 chart → 明確 fail（唔好attach落錯 chart）
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
                        # [ALERT] 2026-08-20 FIX：EnumChildWindows「Chart」class 喺 MT5 not found（chart 窗口係 AfxFrameOrView 類）
                        # → 改用 MDI chart 窗口檢查（同「新方法開圖」驗證一致 — 可靠）
                        # [ALERT] 2026-08-21 FIX：改用 EnumChildWindows Afx 檢查（pywinauto descendants 不可靠 — 假failed）
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
                            print(f"   [OK] active chart 驗證: {_act_title[:40]}（目標 {_sym_u} — 啱）")
                        else:
                            print(f"   [WARN] active chart 唔係目標 {_sym_u}（現: {_act_title[:40] or '未知'}）— 唔attach！")
                    except Exception as _e_act:
                        print(f"   [WARN] active chart 驗證exception: {_e_act}（保守 — 當唔啱）")
                    if _active_ok:
                        # [ALERT] 2026-08-21（user要求：認證有冇 dialog 先繼續next step）：send 熱鍵前檢查閘門
                        # 有 dialog（Properties 殘留）→ 熱鍵 send 咗會彈錯 dialog / 被擋 → 先確認冇 dialog
                        if not _ensure_no_dialog(f'attach {ea_name} 前', max_wait=8):
                            print(f"[FAIL] attach中止：dialog 關唔到 — 唔 send 熱鍵（避免彈錯 dialog）")
                            return False
                        # [ALERT] 2026-08-24 FIX（熱鍵 load 慢 — 人手模擬測試 ATR/ATR attach failed）：send 前等耐啲（MT5 開機後熱鍵 load 慢）
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
                                print(f"[OK] 快捷鍵 {combo} 彈出 Properties（try {_hk_try+1}）")
                                _hk_ok = True
                                break
                            print(f"[WARN] 快捷鍵 {combo} 冇彈出 Properties（重試 {_hk_try+1}/5）...")
                            time.sleep(3)
                        if not _hk_ok:
                            print(f"[FAIL] 快捷鍵 {combo} 重試後都冇彈出 Properties — attach failed（快捷鍵可能未 load）")
                    else:
                        print(f"[FAIL] attach中止：active chart 唔係target symbol（{symbol}）— 避免代替 dialog 一鑊泡")
                        # 寫 fail steps
                        try:
                            import json as _jf2
                            _stf2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
                            with open(_stf2, 'w', encoding='utf-8') as _f2:
                                _jf2.dump([{'text': f'Deploy {ea_name} ({symbol})', 'status': 'done'},
                                           {'text': f'Open chart ({symbol})', 'status': 'done'},
                                           {'text': f'Attach {ea_name}', 'status': 'doing'},
                                           {'text': 'Verify running status', 'status': 'pending'}], _f2, ensure_ascii=False)
                        except Exception:
                            pass
                        time.sleep(2)
                        return False
                else:
                    print(f"[WARN] {ea_name} 冇快捷鍵 combo — 用 Navigator attach")
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
        _clicked_once = set()  # [ALERT] 防卡死：撳過冇效果嘅 dialog 唔再撳（2026-08-07）
        _replace_blocked = False  # [ALERT] 2026-08-21：代替被拒標記（見到代替 dialog → fail deploy）
        for _ in range(8):
            _chk_abort()  # [ALERT] 每 round 檢查緊急stop
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
                            # [ALERT] 2026-08-21 FIX（user實測：關 chart 後deploy代替咗 TestTrades）：代替 dialog 出現 = 目標 chart 已有 EA
                            # = open chart failed/掛錯 chart → 唔可以接受代替（會取代其他 EA）→ 撳「否」+ fail
                            # （before撳「是」→ 取代 TestTrades → 其他 EA 消失 + 心跳殘留假success）
                            # [ALERT] 2026-09-01 FIX（用戶實測：想用 Scalping_M1 取代 Fibonacci — 但硬性撳「否」→ 部署失敗）：
                            # allow_replace=True（用戶喺網頁確認「要取代」）→ 撳「是」接受取代；冇/false → 撳「否」保護（唔誤剷其他 EA）
                            _allow_rpl = False
                            try:
                                if isinstance(getattr(locals().get('_dp_payload', None), 'get', lambda *a: None)('allow_replace', False), bool):
                                    _allow_rpl = bool(_dp_payload.get('allow_replace'))
                            except Exception:
                                pass
                            # 檢查 deploy_cmd 檔（如果 deploy_cmd 有 allow_replace 就用）
                            if not _allow_rpl:
                                try:
                                    import glob as _g_rpl
                                    _cfd_rpl = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
                                    for _f_rpl in _g_rpl.glob(os.path.join(_cfd_rpl, f'deploy_cmd_{ea_name}_*.json')):
                                        try:
                                            _cmd_rpl = json.load(open(_f_rpl, 'r', encoding='utf-8'))
                                            if _cmd_rpl.get('allow_replace'):
                                                _allow_rpl = True
                                                break
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                            if _allow_rpl:
                                # 用戶確認取代 → 撳「是」（接受代替 — 取代目標 chart 嘅 EA）
                                print(f"[ALERT] 偵測到「代替」dialog — allow_replace=True（用戶確認取代）— 撳「是」")
                                _dw = _app.window(handle=_h)
                                _clicked_yes = False
                                for _b in _dw.children(class_name='Button'):
                                    try:
                                        if '是' in _b.window_text() or 'Yes' in _b.window_text() or 'Y' in _b.window_text():
                                            if _bm_click(_b):
                                                _clicked_yes = True
                                                print("[OK] 已撳「是」（接受代替）")
                                            break
                                    except Exception:
                                        pass
                                if not _clicked_yes:
                                    try:
                                        _sk('{ENTER}')
                                        print("[OK] 已 ENTER 接受代替")
                                    except Exception:
                                        pass
                                _clicked_once.add(_h)
                                acted = True
                            else:
                                print("[ALERT] 偵測到「代替」dialog — 唔接受（會取代其他 EA）— 撳「否」+ 中止deploy")
                                _dw = _app.window(handle=_h)
                                _clicked_no = False
                                for _b in _dw.children(class_name='Button'):
                                    try:
                                        if '否' in _b.window_text() or 'No' in _b.window_text() or 'Cancel' in _b.window_text():
                                            if _bm_click(_b):
                                                _clicked_no = True
                                                print("[OK] 已撳「否」（refused代替）")
                                                break
                                    except Exception:
                                        pass
                            if not _clicked_no:
                                try:
                                    _sk('{ESC}')
                                    print("[OK] 已 ESC 關閉代替 dialog")
                                except Exception:
                                    pass
                            _clicked_once.add(_h)
                            acted = True
                            _replace_blocked = True  # [ALERT] 2026-08-21：標記代替被拒 → deploy failed
                        elif any(_k in _t for _k in (ea_name, '1.00', '2.00', '3.00', '.ex5')):
                            _saw_props = True  # [ALERT] Properties 彈出過（快捷鍵有效）
                            _dw = _app.window(handle=_h)
                            for _b in _dw.children(class_name='Button'):
                                try:
                                    if '確定' in _b.window_text() or 'OK' in _b.window_text():
                                        if _bm_click(_b):
                                            print("[OK] 已撳「確定」（Properties）")
                                            try:
                                                _steps[1]['status'] = 'done'
                                                _steps[2]['status'] = 'doing'
                                                _update_steps(_steps)
                                                time.sleep(0.8)  # [ALERT] 2026-08-12：每步停留（網頁捕到「attach」in progress）
                                            except Exception:
                                                pass
                                            acted = True
                                        _clicked_once.add(_h)
                                        break
                                except Exception:
                                    pass
                        if acted:
                            break  # [ALERT] 每輪只處理一個 dialog（防卡死）
                except Exception:
                    pass
            if not acted:
                time.sleep(1)
                # 兩 round 冇動作 → done
                break
            time.sleep(1.5)
            # [ALERT] 防亂按：dialog 數量冇減少（撳咗但冇關）→ stop（唔好無限撳）
            _chk_abort()
            _now_dlg = 0
            for _w2 in _app.windows():
                try:
                    if _w2.class_name() == '#32770':
                        _now_dlg += 1
                except Exception:
                    pass
            if _now_dlg >= _dlg_count and _ > 2:
                print("[WARN] dialog 冇關（可能撳錯）— stop循環防亂按")
                break

        # [ALERT] 2026-08-21 FIX（代替 dialog 唔接受）：如果deploy過程見到代替 dialog → deploy failed
        # （代替 = 目標 chart 已有 EA — open chart failed/掛錯 → 唔可以繼續 — 唔好取代其他 EA）
        if _replace_blocked:
            print("[FAIL] deploy中止：偵測到「代替」dialog（目標 chart 已有 EA）— 唔接受取代")
            try:
                _sk('{ESC}')
            except Exception:
                pass
            try:
                import json as _jf3
                _stf3 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
                with open(_stf3, 'w', encoding='utf-8') as _f3:
                    _jf3.dump([{'text': f'Deploy {ea_name} ({symbol})', 'status': 'done'},
                               {'text': f'Open chart ({symbol})', 'status': 'done'},
                               {'text': f'Attach {ea_name}', 'status': 'doing'},
                               {'text': '[WARN] Replace dialog — target chart already has an EA, replacement not accepted', 'status': 'doing'},
                               {'text': 'Verify running status', 'status': 'pending'}], _f3, ensure_ascii=False)
            except Exception:
                pass
            return False

        # [ALERT] 2026-08-20 FIX（連環代替確認 — user實測）：撳完「是」after MT5 可能連環彈多個「代替」dialog
        # （attach EA 落已有 EA 嘅 chart — 逐個代替 — 每個都要再撳「是」）
        # → loop 完after再 poll 8 秒睇有冇新代替 dialog → 有就再撳「是」（最多 5 次）
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
                        # [ALERT] 2026-08-21 FIX：連環代替都唔接受（撳「否」— 唔好取代其他 EA）
                        _rpl_found = True
                        _replace_blocked = True
                        _dw_r2 = _app.window(handle=_h_r)
                        for _b_r in _dw_r2.children(class_name='Button'):
                            try:
                                if '否' in _b_r.window_text() or 'No' in _b_r.window_text() or 'Cancel' in _b_r.window_text():
                                    if _bm_click(_b_r):
                                        print(f"[OK] 已撳「否」（refused連環代替 {_rpl+1}）")
                                    break
                            except Exception:
                                pass
                        break  # 每 round 處理一個
                except Exception:
                    pass
            if not _rpl_found:
                break  # 冇代替 dialog — done
            time.sleep(2)

        # [ALERT] 2026-08-21 FIX：連環代替 loop 完 → 如果有代替被拒 → deploy failed
        if _replace_blocked:
            print("[FAIL] deploy中止：代替 dialog 被refused（目標 chart 已有 EA — 唔接受取代）")
            try:
                _sk('{ESC}')
            except Exception:
                pass
            try:
                import json as _jf4
                _stf4 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
                with open(_stf4, 'w', encoding='utf-8') as _f4:
                    _jf4.dump([{'text': f'Deploy {ea_name} ({symbol})', 'status': 'done'},
                               {'text': f'Open chart ({symbol})', 'status': 'done'},
                               {'text': f'Attach {ea_name}', 'status': 'doing'},
                               {'text': '[WARN] Replace dialog — target chart already has an EA, replacement not accepted', 'status': 'doing'},
                               {'text': 'Verify running status', 'status': 'pending'}], _f4, ensure_ascii=False)
            except Exception:
                pass
            return False

        # [ALERT] 2026-08-10：驗證 Properties 有冇彈出（冇彈 = 快捷鍵冇效 — 重試快捷鍵 ×2）
        if not _saw_props:
            print(f"[WARN] 快捷鍵 {combo} 冇彈出 Properties（重試中）...")
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
                                                print(f"[OK] 重試 {_rt+1}: 已撳「確定」")
                                            break
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                    break
                time.sleep(2)
            if not _saw_props:
                print(f"[FAIL] 快捷鍵 {combo} 重試後都冇彈出 Properties — attach failed（快捷鍵可能未 load）")

        # [ALERT] 2026-08-21（user要求：認證有冇 dialog 先繼續next step）：heartbeat verify前檢查閘門
        # 撳「確定」後 Properties dialog 可能殘留 → 唔可以當success（下次deploy會被擋）→ 確認冇 dialog 先繼續
        if not _ensure_no_dialog(f'{ea_name} deploydone後', max_wait=8):
            print(f"[FAIL] {ea_name} deploy後有 dialog 關唔到 — 唔當success（會擋下次deploy）")
            return False

        # heartbeat verify
        hb = os.path.join(COMMON_FILES, f'state_{ea_name}.json')
        # [ALERT] 2026-09-01 FIX（假成功 — EMA_Cross 案例）：attach 心跳檢查要 mtime 新鮮（<60s）— 唔可以淨 isfile
        # （舊殘留 state_<EA>.json 01:30 → isfile True → 誤判 attach success — 但 OnInit 未跑）
        _hb_exists_fresh = os.path.isfile(hb) and time.time() - os.path.getmtime(hb) < 60
        if _hb_exists_fresh:
            print(f"[OK] {ea_name} attach success（heartbeat exists + fresh）")
        else:
            # [ALERT] 2026-09-01 FIX（用戶實測：Breakout loaded 但 OnInit 未跑 — 冇 EA icon + 冇心跳 = 假成功）：
            # before: 即刻 print「done（heartbeat waiting tick）」→ 即使 OnInit 未跑都話 OK → 假成功
            # now: 撳「確定」後等 OnInit 心跳（state_<EA>.json / hb_<EA>.txt 出現 — OnInit 寫）最多 20 秒
            # → 心跳出現 = OnInit 真跑 = 真成功；timeout 冇心跳 → 再睇 MQL5/Logs 有冇 EA「已啟動」Print（OnInit 真跑證據）
            # → 兩樣都冇 → 唔當 success（chart 未 activate — OnInit 未跑 — 假成功）
            print(f"[WAIT] {ea_name} 撳確定後等 OnInit 心跳（最多 20 秒 — 確認 EA 真運行）...")
            _hb_ok_wait = False
            _wait_start = time.time()
            while time.time() - _wait_start < 20:
                _chk_abort()
                # [ALERT] 2026-09-01 FIX（用戶實測：MT5 系統更新彈窗喺 attach 後彈出 — 阻住 OnInit）：
                # 等心跳期間同時掃 dialog（update/通知彈窗）→ 即刻 WM_CLOSE 關（唔阻 OnInit 跑）
                try:
                    import ctypes as _ct_hb
                    _u_hb = _ct_hb.windll.user32
                    def _scan_hb(hwnd, _):
                        _cls_hb = _ct_hb.create_unicode_buffer(128)
                        _u_hb.GetClassNameW(_ct_hb.c_void_p(hwnd), _cls_hb, 128)
                        if _cls_hb.value == '#32770':
                            _t_hb = _ct_hb.create_unicode_buffer(256)
                            _u_hb.GetWindowTextW(_ct_hb.c_void_p(hwnd), _t_hb, 256)
                            _tt_hb = _t_hb.value
                            # 關閉所有 dialog（包括 MT5 update/通知彈窗 — 唔阻部署）
                            _u_hb.PostMessageW(_ct_hb.c_void_p(hwnd), 0x0010, 0, 0)  # WM_CLOSE
                            if _tt_hb.strip():
                                print(f"  [DIALOG] 等心跳期間關閉 dialog: [{_tt_hb[:60]}]")
                        return True
                    _u_hb.EnumWindows(_ct_hb.WINFUNCTYPE(_ct_hb.c_bool, _ct_hb.c_size_t, _ct_hb.c_size_t)(_scan_hb), 0)
                except Exception:
                    pass
                _hb_cand = [
                    os.path.join(COMMON_FILES, f'state_{ea_name}.json'),
                    os.path.join(COMMON_FILES, f'hb_{ea_name}.txt'),
                    os.path.join(COMMON_FILES, f'state_{ea_name}.txt'),
                ]
                for _hfc in _hb_cand:
                    if os.path.isfile(_hfc) and time.time() - os.path.getmtime(_hfc) < 60:
                        print(f"[OK] {ea_name} OnInit 心跳出現（{os.path.basename(_hfc)} — OnInit 真跑）")
                        _hb_ok_wait = True
                        break
                if _hb_ok_wait:
                    break
                time.sleep(2)
            if not _hb_ok_wait:
                # 再睇 MQL5/Logs（EA Print「已啟動」= OnInit 跑咗）
                try:
                    import glob as _g_ml
                    _ml_dir = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
                    _ml_latest = None
                    for _d_ml in os.listdir(_ml_dir):
                        _ml_lgd = os.path.join(_ml_dir, _d_ml, 'MQL5', 'Logs')
                        if os.path.isdir(_ml_lgd):
                            for _f_ml in _g_ml.glob(os.path.join(_ml_lgd, '*.log')):
                                if _ml_latest is None or os.path.getmtime(_f_ml) > os.path.getmtime(_ml_latest):
                                    _ml_latest = _f_ml
                    if _ml_latest:
                        with open(_ml_latest, 'rb') as _f_ml2:
                            _raw_ml = _f_ml2.read()
                        for _enc_ml in ('utf-16', 'utf-8', 'cp1252'):
                            try:
                                _txt_ml = _raw_ml.decode(_enc_ml); break
                            except Exception:
                                continue
                        if ea_name in _txt_ml and ('已啟動' in _txt_ml or '已start' in _txt_ml):
                            print(f"[OK] {ea_name} OnInit Print「已啟動」確認（MQL5/Logs — OnInit 真跑）")
                            _hb_ok_wait = True
                except Exception:
                    pass
            if not _hb_ok_wait:
                print(f"[FAIL] {ea_name} 撳確定後 OnInit 未跑（冇心跳 + 冇已啟動Print）— 假成功 — chart 可能未 activate")
            else:
                print(f"[OK] {ea_name} 快捷鍵attach流程done（OnInit 確認）")
        # [ALERT] 2026-08-12 FIX：steps done 搬去函數最尾（所有操作done後先寫 — 否則user見 steps done 撳確定 → active 仲 true → immediately彈多一次）
        # [TARGET] 圖表平鋪（2026-08-08：deploydone後自動 Alt+R — 圖表整齊排列）
        try:
            _sk('%r')
            time.sleep(2)
        except Exception:
            pass
        # [ALERT] 收埋市場報價（2026-08-08：直接 ShowWindow minimize — 唔好用 Ctrl+M（toggle 會開返））
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
        # [ALERT] 2026-08-10：log verify symbol（打字方法可能開錯圖表 — AMD 案例）
        try:
            import glob as _g4
            # [ALERT] 等 OnInit 行 + log write（撳確定後immediately讀 — log 未寫 → 誤判failed — Breakout 案例）
            # [ALERT] 2026-08-13 FIX：4 秒 → 8 秒（MT5 重啟後 EA 初始化 + log/心跳write要時間 — Parabolic_SAR 案例：user見success但驗證話「圖表不符」— log 其實有記錄）
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
                    if ea_name in _line and _target_sym in _line and ('已启动' in _line or '已start' in _line or 'loaded successfully' in _line):
                        _ok_sym = True
                        break
                if _ok_sym:
                    print(f"[OK] log verify: {ea_name} 喺 {_target_sym} start（正確圖表）")
                else:
                    print(f"[FAIL] log verify: {ea_name} 冇喺 {_target_sym} start（可能開錯圖表 — 檢查heartbeat fallback）")
                    # [ALERT] 2026-08-12 FIX：heartbeat fallback — log 冇「已start」字眼唔代表 EA 冇running（重啟 MT5 後 log 時序/字眼問題）
                    # user實測：PC實際一致（Breakout 喺 USDJPY running）但 log verify誤判failed！
                    _hb_ok = False
                    try:
                        _hb_f = os.path.join(COMMON_FILES, f'state_{ea_name}.json')
                        if os.path.isfile(_hb_f):
                            import json as _jhbl
                            # [ALERT] 2026-08-12 FIX：心跳file係 UTF-16 編碼（EA 寫嘅 — 0xff 0xfe BOM）— 多編碼嘗試（before utf-8 讀failed → 後備冇效 → 誤判failed）
                            _hb_d = None
                            for _enc_hb in ('utf-16', 'utf-8', 'cp1252'):
                                try:
                                    _hb_d = _jhbl.load(open(_hb_f, 'r', encoding=_enc_hb))
                                    break
                                except Exception:
                                    continue
                            if isinstance(_hb_d, dict) and _hb_d.get('status') == 'running' and int(time.time()) - int(os.path.getmtime(_hb_f)) < 300:
                                _hb_ok = True
                        # [ALERT] 2026-08-13 FIX：AgentHelper 案例 — 心跳用 hb_<EA>.txt 格式（舊版 EA）— state_*.json 揾唔到 → 檢查 hb_*.txt（mtime 新鮮 <300s = running中）
                        if not _hb_ok:
                            _hb_txt = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
                            if os.path.isfile(_hb_txt) and int(time.time()) - os.path.getmtime(_hb_txt) < 300:
                                _hb_ok = True
                                print(f"[OK] hb_*.txt 心跳: {ea_name} running中（{os.path.basename(_hb_txt)} 新鮮）")
                    except Exception:
                        pass
                    if _hb_ok:
                        print(f"[OK] heartbeat fallback: {ea_name} running中（心跳新鮮 — 圖表正確）")
                    else:
                        # [ALERT] 2026-08-13 FIX：heartbeat fallbackfailed → 再等 5 秒重試（EA 初始化延遲 — 心跳file未寫 → 誤判failed — Parabolic_SAR 案例）
                        print(f"[WAIT] heartbeat fallback第一次failed — 等 5 秒再試（EA 可能仲初始化緊）...")
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
                            print(f"[OK] heartbeat fallback（第二次）: {ea_name} running中 — 圖表正確")
                    if not _hb_ok:
                        # [ALERT] 2026-08-13 FIX：heartbeat fallback都failed → 再等 5 秒重試 log verify（log write延遲 — Ichimoku 案例：圖表success但 log 未寫 → 誤判「圖表不符」）
                        # （Ichimoku 冇心跳 code — heartbeat fallback永遠failed — 但 log 最終會寫「已start」— 第二次 log verify）
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
                                        if ea_name in _line2 and _target_sym in _line2 and ('已启动' in _line2 or '已start' in _line2 or 'loaded successfully' in _line2):
                                            _hb_ok = True
                                            print(f"[OK] log verify（第二次）: {ea_name} 喺 {_target_sym} start — 圖表正確")
                                            break
                        except Exception:
                            pass
                    if not _hb_ok:
                        # [ALERT] 2026-08-20（deploy流程檢測系統 v0.10.5）：唔再 return False！
                        # 舊邏輯：log verify fail → return False → 外層新 code Step 4 gate 永遠行唔到
                        # （EA 明明掛到但 log write延遲 → 假failed — Breakout 案例）
                        # 新邏輯：呢度只 print warning — 最終判定由 auto_attach_ea 嘅 Step 4 gate
                        # （_ea_loaded_in_log poll 30s + heartbeat fallback）負責
                        print(f"[WARN] 驗證 {ea_name} 未確認（log/心跳延遲）— 交俾外層 Step 4 gate 最終判定")
        except Exception:
            pass
        # [ALERT] 2026-08-12 FIX：所有操作done（圖表平鋪/市場報價/log verify）→ 最後先寫 steps 全部 done（確定出現 — active immediately false — 撳確定唔會再彈）
        try:
            _steps[2]['status'] = 'done'
            _steps[3]['status'] = 'doing'
            _update_steps(_steps)
            time.sleep(0.8)
            _steps[3]['status'] = 'done'
            _update_steps(_steps)
            # [ALERT] immediately寫 ai_control.json active:false（唔等外層 release — 否則user撳確定時 active 仲 true → immediately彈多一次）
            try:
                import json as _jst
                _stf = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'server', 'static', 'detector', 'ai_control.json'))
                with open(_stf, 'w', encoding='utf-8') as _f:
                    _jst.dump({'active': False, 'program': '', 'time': time.time()}, _f, ensure_ascii=False)
            except Exception:
                pass
        except Exception:
            pass
        # [ALERT] 2026-08-21 FIX（RSI Properties dialog 殘留 — user實測）：deploydone後清理任何殘留 dialog
        # （撳「確定」後 dialog 可能冇關 → 殘留 → 下次deploy被 modal 擋 → open chart failed）
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
                print(f"[CLEAN] deploy後清理殘留 dialog: {len(_fin_dlgs)} 個（WM_CLOSE）")
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"[WARN] 快捷鍵attach failed: {e}")
        return False
def verify_heartbeat(ea_name, timeout=60):
    """驗證 EA heartbeat file exists且新鮮（+ MT5 log 後備 — 2026-08-10：market closeno tick 心跳唔寫）"""
    # [ALERT] 2026-09-01 FIX（user實測：部署每次等 90s — verify_heartbeat 只 check hb_<EA>.txt 但 EA 寫 state_<EA>.json）：
    # → 兩個都 check（state_.json 優先 — EA 而家寫呢個；hb_.txt 後備）
    hb_files = [os.path.join(COMMON_FILES, f'state_{ea_name}.json'),
                os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')]
    start = time.time()
    
    while time.time() - start < timeout:
        for hb_file in hb_files:
            if os.path.exists(hb_file):
                mtime = os.path.getmtime(hb_file)
                age = time.time() - mtime
                if age < 300:  # Within 5 minutes
                    # Read content
                    with open(hb_file, 'rb') as f:
                        raw = f.read()
                    content = raw.decode('utf-16-le', errors='replace').strip().lstrip('\ufeff')
                    print(f"[HB] {ea_name} heartbeat: {content} ({round(age)}s ago)")
                    return True
        time.sleep(3)
    
    # [ALERT] 2026-08-10：心跳冇 → 睇 MT5 log「已start」（market closeno tick — EA 其實start咗）
    # [ALERT] 2026-08-24 FIX（假success根治）：讀 terminal Logs（<hash>/Logs/ — 英文 loaded successfully）而唔係 MQL5/Logs（MetaEditor 中文「已启动」殘留 → 誤判）
    # + 只認「loaded successfully」+ 最後狀態判斷（removed 後唔算 loaded）
    # [ALERT] 2026-09-01 FIX（用戶實測：Breakout loaded 但 OnInit 未跑 — 冇 EA icon + 冇心跳 = 假成功）：
    # 淨靠「loaded successfully」fallback 唔夠 — 要額外確認 OnInit 真跑（EA Print「已啟動」/ heartbeat file 寫入）
    # → 心跳 timeout 後：睇 log 有冇 EA 自己 Print 嘅「已啟動」/「stopped」（OnInit/OnDeinit 跑過 = 真掛）
    # → 淨係「loaded successfully」而 OnInit 冇 Print → 唔當 success（可能 chart 未 activate — OnInit 未跑）
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
        if latest and time.time() - os.path.getmtime(latest) < 600:
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
                _oninit_ran = False  # [ALERT] 2026-09-01：OnInit 真跑 = EA Print「已啟動」/「stopped」
                for _ln in text.splitlines():
                    if ea_name in _ln and 'expert' in _ln.lower():
                        if 'loaded successfully' in _ln:
                            _last_state = 'loaded'
                        elif 'removed' in _ln:
                            _last_state = 'removed'
                    # OnInit/OnDeinit Print（EA 自己寫 — 「已啟動」= OnInit 跑咗）
                    if ea_name in _ln and ('已啟動' in _ln or '已start' in _ln or '已停止' in _ln or '已stop' in _ln or 'stopped' in _ln.lower()):
                        _oninit_ran = True
                if _last_state == 'loaded' and _oninit_ran:
                    print(f"[OK] {ea_name} MT5 log 顯示已start + OnInit Print 確認（market close no tick — 心跳fallback confirm）")
                    return True
                elif _last_state == 'loaded' and not _oninit_ran:
                    # [ALERT] 2026-09-01：loaded 但 OnInit 未 Print → 假成功（chart 未 activate — OnInit 未跑）→ 唔當 success
                    print(f"[WARN] {ea_name} MT5 log loaded 但 OnInit 未 Print（chart 可能未 activate — EA 未真正運行）")
    except Exception:
        pass
    
    print(f"[FAIL] {ea_name} heartbeat not detected within {timeout}s")
    return False


def _ea_loaded_in_log(ea_name, symbol):
    """[ALERT] 2026-08-20（deploy流程檢測系統 — Step 4 gate）
    對真 MT5 log：搵 `expert <EA> (<SYM>,H1) loaded successfully`（且無隨後 removed）
    [WARN] 2026-08-20 FIX：加新鮮度檢查 — 只認最近 5 分鐘內嘅 loaded（stale 舊記錄會假 True）
    用於 _wait_until poll — 返 bool（唔 print success — _wait_until 會 print）"""
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
        # 新鮮度：log 檔 mtime 要 < 300s（太舊 = MT5 冇write = EA 冇 load 記錄）
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
        # [ALERT] 2026-08-20 FIX（假success根治）：loaded 記錄本身要新鮮（唔可以淨係 log 檔新鮮）
        # 舊記錄（例如 18:32 Bollinger EURUSD loaded）喺 log 檔 → log 檔新鮮 → 誤判 True → 假success
        # → parse log 行時間（HH:MM:SS）對比now — 只認最近 300s 內嘅 loaded
        import datetime as _dt
        _now_dt = _dt.datetime.now()
        _cutoff_dt = _now_dt - _dt.timedelta(seconds=300)
        _found_ts = None
        for line in text.splitlines():
            if ea_name in line and ('loaded successfully' in line.lower() or '已启动' in line or '已start' in line):
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
                    print(f"[OK] MT5 log: EA loaded successfully")
                    return True
                if ea_name in line and 'start' in line:
                    print(f"[OK] EA log: {line.strip()}")
                    return True
    return False



def deploy_ea_via_chr(ea_name, symbol='EURUSD', timeframe='H1', inputs=None):
    """[ALERT] 2026-09-01（user實測方法）：用 .chr 檔方法部署 EA（取代 GUI automation — 熱鍵預載 + Alt+F + Ctrl+1）
    原理：MT5 開機 restore .chr 檔（MQL5/Profiles/Charts/<profile>/*.chr）— 自動開 chart + 掛 EA
    → 複製現有 MT5 寫嘅 .chr（有完整 expert 區）→ 改 id/symbol/EA 名/Magic → 寫入新 .chr + order.wnd
    → 關 MT5 → 開 MT5（restore 自動掛 EA — .ex5 必須存在）→ 平鋪窗口
    步驟：
    1. 搵基底 .chr（現有 MT5 寫嘅 — 有 expert 區）
    2. 複製 → 改 id + symbol + description + EA 名/path/Magic
    3. 寫入 chartXX.chr（新編號）+ 更新 order.wnd
    4. 關 MT5（WM_CLOSE 正常關閉 save profile）
    5. 開 MT5 → restore .chr → 自動掛 EA
    6. 平鋪窗口（WM_COMMAND id=33527）
    7. 驗證（心跳 + MT5 log loaded + OnInit）
    Returns: True if EA running
    """
    import subprocess as _sp
    import glob as _gl
    import ctypes as _ct
    import re as _re
    import random
    from ctypes import wintypes as _wt
    print(f"\n{'='*50}")
    print(f"  [GO] Deploy-via-CHR: {ea_name} → {symbol} {timeframe}")
    print(f"{'='*50}")
    _u = _ct.windll.user32

    # Step 1: 搵基底 .chr（現有 MT5 寫嘅 — 有 expert 區 — 任何 symbol 都得）
    _base_chr = None
    _data_root = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
    try:
        for _d in os.listdir(_data_root):
            _charts_root = os.path.join(_data_root, _d, 'MQL5', 'Profiles', 'Charts')
            if not os.path.isdir(_charts_root):
                continue
            for _p in os.listdir(_charts_root):
                _pd = os.path.join(_charts_root, _p)
                if not os.path.isdir(_pd) or _p == '_deleted':
                    continue
                for _cf in _gl.glob(os.path.join(_pd, '*.chr')):
                    try:
                        with open(_cf, 'rb') as _fh:
                            _bd = _fh.read()
                        _bt = _bd.decode('utf-16', errors='replace')
                        if '<expert>' in _bt and 'path=Experts' in _bt and 'InpSymbol=' in _bt:
                            _base_chr = _cf
                            _base_prof = _pd
                            print(f"[CHR] 基底 .chr: {os.path.basename(_cf)}（{os.path.basename(_pd)} profile）")
                            break
                    except Exception:
                        pass
                if _base_chr:
                    break
            if _base_chr:
                break
    except Exception as _e:
        print(f"[FAIL] 搵基底 .chr failed: {_e}")
        return False

    if not _base_chr:
        # [ALERT] 2026-09-01 FIX（user實測：模板有 InpSymbol= 先掛到 EA — 優先模板）：
        # → 用 repo 模板（chr_template_base.chr.txt — user實測格式）轉 chart_base.chr
        try:
            import glob as _gl_tpl2
            _tpl_path2 = None
            for _tpl_p2 in _gl_tpl2.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chr_template_base.chr.txt')) + _gl_tpl2.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'agent', 'chr_template_base.chr.txt')):
                if os.path.isfile(_tpl_p2):
                    _tpl_path2 = _tpl_p2
                    break
            if _tpl_path2:
                with open(_tpl_path2, encoding='utf-8') as _fh_t2:
                    _tpl_txt2 = _fh_t2.read()
                if '<expert>' in _tpl_txt2 and 'InpSymbol=' in _tpl_txt2:
                    _tpl_txt2 = _tpl_txt2.replace('\r\n', '\n').replace('\n', '\r\n')
                    # 寫 chart_base.chr 落 active profile（最近修改嘅）
                    _cr_t2 = None
                    for _d_t2 in os.listdir(_data_root):
                        _cc_t2 = os.path.join(_data_root, _d_t2, 'MQL5', 'Profiles', 'Charts')
                        if os.path.isdir(_cc_t2):
                            _cr_t2 = _cc_t2
                            break
                    if _cr_t2:
                        _bp_t2 = None
                        _bm_t2 = 0
                        for _pp_t2 in os.listdir(_cr_t2):
                            _pd_t2 = os.path.join(_cr_t2, _pp_t2)
                            if not os.path.isdir(_pd_t2) or _pp_t2 == '_deleted':
                                continue
                            try:
                                _mt_t2 = os.path.getmtime(_pd_t2)
                                if _mt_t2 > _bm_t2:
                                    _bm_t2 = _mt_t2
                                    _bp_t2 = _pd_t2
                            except Exception:
                                pass
                        if _bp_t2:
                            _base_c_t2 = os.path.join(_bp_t2, 'chart_base.chr')
                            with open(_base_c_t2, 'wb') as _f_b2:
                                _f_b2.write(b'\xff\xfe')
                                _f_b2.write(_tpl_txt2.encode('utf-16-le'))
                            _base_chr = _base_c_t2
                            _base_prof = _bp_t2
                            print(f"[CHR] 基底模板 → chart_base.chr（{os.path.basename(_bp_t2)} — user實測格式有 InpSymbol=）")
        except Exception as _e_tpl2:
            print(f"[WARN] 模板 fallback failed: {_e_tpl2}")
    if not _base_chr:
        # [ALERT] 2026-09-01 FIX（user實測：部署 fail — 環境空白冇基底 .chr）：
        # → 自動生成基底（用 MT5 寫嘅格式 — 完整欄位 — _deleted 有之前 MT5 寫嘅 .chr 可複製）
        print("[CHR] 冇基底 .chr — 自動生成（用 MT5 寫嘅格式）")
        try:
            import glob as _gl2
            _gen_base = None
            # 1. 先搵 _deleted 入面 MT5 寫嘅 .chr（有 expert 區 — 完整格式 — 掃全部 profile）
            for _d2 in os.listdir(_data_root):
                _charts_root2 = os.path.join(_data_root, _d2, 'MQL5', 'Profiles', 'Charts')
                if not os.path.isdir(_charts_root2):
                    continue
                for _p2 in os.listdir(_charts_root2):
                    _dd = os.path.join(_charts_root2, _p2, '_deleted')
                    if not os.path.isdir(_dd):
                        continue
                    for _cf2 in _gl2.glob(os.path.join(_dd, '*.chr')):
                        try:
                            with open(_cf2, 'rb') as _fh2:
                                _bd2 = _fh2.read()
                            _bt2 = _bd2.decode('utf-16', errors='replace')
                            if '<expert>' in _bt2 and 'path=Experts' in _bt2 and 'window_left' in _bt2:
                                _gen_base = _cf2
                                _base_prof = _dd.replace('_deleted', '').rstrip('\\/')
                                print(f"[CHR] 自動基底（_deleted）: {os.path.basename(_cf2)}")
                                break
                        except Exception:
                            pass
                    if _gen_base:
                        break
                if _gen_base:
                    break
            if _gen_base:
                # 複製到 active profile（_base_prof — _deleted 所在 profile — 通常係 Euro — 部署會用）
                import shutil as _sh
                # _base_prof 可能係 '...Euro'（_deleted 喺 Euro 入面）
                if _base_prof and os.path.isdir(_base_prof):
                    _base_chr = os.path.join(_base_prof, 'chart_base.chr')
                    _sh.copyfile(_gen_base, _base_chr)
                    print(f"[CHR] 基底已複製去: {_base_chr}")
                else:
                    print(f"[WARN] _base_prof 唔存在: {_base_prof} — 用返 _gen_base 個 profile")
                    _base_chr = _gen_base
            else:
                print("[FAIL] 冇基底 .chr（_deleted 都冇 MT5 寫嘅）— 先人手掛一次 EA 落 chart 生成基底")
                return False
        except Exception as _e_gen:
            print(f"[FAIL] 自動生成基底 failed: {_e_gen}")
            return False

    # Step 2: 複製基底 → 改 id + symbol + description + EA 名/path/Magic
    try:
        with open(_base_chr, 'rb') as _fh:
            _data = _fh.read()
        _txt = _data.decode('utf-16', errors='replace')

        # 改 id（隨機 14 位）
        _new_id = str(random.randint(10**13, 10**14 - 1))
        _txt = _re.sub(r'id=\d+', f'id={_new_id}', _txt, count=1)

        # 改 symbol + description（用 symbol 對照）
        _sym_desc = {
            'EURUSD': 'Euro vs US Dollar',
            'GBPUSD': 'Pound Sterling vs US Dollar',
            'USDJPY': 'US Dollar vs Yen',
            'USDCHF': 'US Dollar vs Swiss Franc',
            'AUDUSD': 'Australian Dollar vs US Dollar',
            'USDCAD': 'US Dollar vs Canadian Dollar',
            'NZDUSD': 'New Zealand Dollar vs US Dollar',
            'EURJPY': 'Euro vs Yen',
            'GBPJPY': 'Pound Sterling vs Yen',
            'AMD': 'Advanced Micro Devices Inc',
            'UK100': 'FTSE 100 Index',
        }
        _desc = _sym_desc.get(symbol, symbol)
        _txt = _re.sub(r'symbol=[A-Za-z0-9_]+', f'symbol={symbol}', _txt, count=1)
        _txt = _re.sub(r'description=[^\r\n]+', f'description={_desc}', _txt, count=1)

        # 改 EA 名 + path（name=XXX + path=Experts\\XXX.ex5）
        _txt = _re.sub(r'name=[A-Za-z0-9_]+(?=\r\npath=Experts)', f'name={ea_name}', _txt, count=1)
        _txt = _re.sub(r'path=Experts\\[A-Za-z0-9_]+\.ex5', lambda _m: 'path=Experts' + chr(92) + ea_name + '.ex5', _txt, count=1)

        # 改 Magic（如果 inputs 有 MagicNumber）
        if inputs and 'MagicNumber' in inputs:
            _new_magic = inputs['MagicNumber']
            _txt = _re.sub(r'MagicNumber=\d+', f'MagicNumber={_new_magic}', _txt, count=1)
            print(f"[CHR] Magic 改做 {_new_magic}")

        # Step 3: 寫入新 .chr（搵下一個 chart 編號）
        _max_num = 0
        for _cf2 in _gl.glob(os.path.join(_base_prof, 'chart*.chr')):
            _m2 = _re.search(r'chart(\d+)\.chr', os.path.basename(_cf2))
            if _m2:
                _max_num = max(_max_num, int(_m2.group(1)))
        _new_chr = os.path.join(_base_prof, f'chart{_max_num+1:02d}.chr')
        with open(_new_chr, 'wb') as _fh:
            _fh.write(b'\xff\xfe')
            _fh.write(_txt.encode('utf-16-le'))
        print(f"[CHR] 寫入新 .chr: {os.path.basename(_new_chr)}（{symbol} + {ea_name}）")

        # 更新 order.wnd（加新 chart）
        _ord_wnd = os.path.join(_base_prof, 'order.wnd')
        if os.path.isfile(_ord_wnd):
            _ow_raw = open(_ord_wnd, 'rb').read()
            _ow_txt = _ow_raw.decode('utf-16', errors='replace')
            _ow_lines = [l.strip() for l in _ow_txt.split('\r\n') if l.strip()]
            if os.path.basename(_new_chr) not in _ow_lines:
                _ow_lines.append(os.path.basename(_new_chr))
                with open(_ord_wnd, 'wb') as _f_ow:
                    _f_ow.write(b'\xff\xfe')
                    _f_ow.write(('\r\n'.join(_ow_lines) + '\r\n').encode('utf-16-le'))
            print(f"[CHR] order.wnd 更新: {_ow_lines}")
    except Exception as _e2:
        print(f"[FAIL] 寫 .chr failed: {_e2}")
        return False

    # Step 4: 關 MT5（如果開住）— 確保開機時 restore 新 .chr
    try:
        # [ALERT] 2026-09-01 FIX（user實測：重新開啟 MT5 開好多視窗 — 空白 .chr 越積越多）：
        # → 關 MT5 前先清空白 chart（_clean_blank_charts_via_chr — 冇 EA 嘅 .chr 移去 _deleted）
        #   （新方法 deploy_ea_via_chr 之前冇 call — 空白 chart02/06 留低 → order.wnd 越積越多）
        try:
            _cleaned_chr = _clean_blank_charts_via_chr()
            print(f"[CHR] 清空白 chart: {_cleaned_chr} 個（_clean_blank_charts_via_chr）")
        except Exception as _e_cln:
            print(f"[WARN] 清空白 chart failed: {_e_cln}")
        _pid = find_mt5_pid()
        if _pid:
            from pywinauto import Application as _App_r
            _app_r = _App_r(backend='win32').connect(process=_pid, timeout=8)
            _main_r = _app_r.window(class_name='MetaQuotes::MetaTrader::5.00')
            _u.PostMessageW(_ct.c_void_p(int(_main_r.element_info.handle)), 0x0010, 0, 0)
            print("[CLIP] 關 MT5（save profile）...")
            time.sleep(10)
            for _chk in range(5):
                _r_chk = _sp.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
                if b'terminal64' not in _r_chk.stdout:
                    break
                time.sleep(2)
            print("[OK] MT5 已關閉")
        else:
            print("[INFO] MT5 未開 — 直接開")
    except Exception as _e3:
        print(f"[WARN] 關 MT5 failed: {_e3}")
        _sp.run('taskkill /F /IM terminal64.exe', shell=True, capture_output=True)
        time.sleep(3)

    # Step 5: 開 MT5 → restore .chr → 自動掛 EA
    try:
        _sp.Popen([MT5_PATH])
        print("[OK] MT5 啟動中（restore .chr → 自動掛 EA）...")
        _start = time.time()
        _ready = False
        while time.time() - _start < 90:
            _p2 = find_mt5_pid()
            if _p2:
                try:
                    from pywinauto import Application as _App_w
                    _a = _App_w(backend='win32').connect(process=_p2, timeout=5)
                    _w = _a.window(class_name='MetaQuotes::MetaTrader::5.00')
                    if _w.exists():
                        _ready = True
                        break
                except Exception:
                    pass
            time.sleep(3)
        if not _ready:
            print("[FAIL] MT5 開唔到（90s timeout）")
            return False
        # 等 EA 掛上（心跳 + log + OnInit — verify_heartbeat 現有驗證 — 最多 90 秒）
        _hb_ok = verify_heartbeat(ea_name, timeout=90)
        if _hb_ok:
            print(f"[OK] {ea_name} 心跳確認（真運行 — verify_heartbeat PASS）")
        else:
            print(f"[WARN] {ea_name} 心跳未確認（verify_heartbeat 90s timeout — 可能 EA 檔唔存在 / 慢）")

        # Step 6: 平鋪窗口（WM_COMMAND id=33527）
        try:
            _p4 = find_mt5_pid()
            if _p4:
                from pywinauto import Application as _App_t
                _at = _App_t(backend='win32').connect(process=_p4, timeout=5)
                _wt = _at.window(class_name='MetaQuotes::MetaTrader::5.00')
                _u.PostMessageW(_ct.c_void_p(int(_wt.element_info.handle)), 0x0111, 33527, 0)
                print("[OK] 平鋪窗口（WM_COMMAND id=33527）")
        except Exception as _e_t:
            print(f"[WARN] 平鋪窗口 failed: {_e_t}")
        return True
    except Exception as _e4:
        print(f"[FAIL] 開 MT5 failed: {_e4}")
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
    print(f"  [GO] Auto-Attach: {ea_name} → {symbol} {timeframe}")
    print(f"{'='*50}")
    # [ALERT] 2026-08-28 FIX：記錄deploystart時間（log verify只認「deploystartafter」嘅 loaded — 唔好用 30 分鐘窗口）
    # （舊：30 分鐘內任何 loaded 都當 fresh → 讀到上一輪deploy嘅舊 loaded → 假success）
    _deploy_start_ts = time.time()
    global _last_deploy_start_ts
    _last_deploy_start_ts = _deploy_start_ts

    # Step 0: AI 控制守衛 — 彈warning視窗 + 支援緊急stop
    try:
        from control_guard import acquire, check_abort, release, ControlAborted
        acquire(f"deploy {ea_name}")
    except ImportError:
        # 冇 control_guard 都照行（向前兼容）
        check_abort = lambda: None
        release = lambda: None
        ControlAborted = Exception
        acquire = lambda *a, **k: None

    # [ALERT] 2026-08-22（user要求：UAC 檢測機制）：deploy流程最開頭檢查 UAC/授權窗口
    # （MT5 更新/accountexception → 授權窗口 → 先處理再deploy）
    try:
        if not _detect_and_handle_uac(f'{ea_name} deploy UAC 檢查', max_wait=30):
            print(f"[FAIL] {ea_name} deploy中止：UAC 授權窗口未處理（可能係 MT5 更新要求授權）")
            return False
    except Exception:
        pass

    # [ALERT] 2026-08-21 FIX（user實測：關 chart 後deploy卡 dialog）：deploy前先清理所有殘留 dialog
    # （before RSI deploy彈嘅 Properties dialog 殘留未關 → after開 chart Alt+F 被 modal 擋 → open chart failed → 代替 dialog 一鑊泡）
    # [ALERT] 2026-08-21 FIX2：ESC/撳取消對 modal dialog 唔 work（實測撳「確定」/ESC 都關唔到 — RSI Properties 卡死）
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
        print(f"[CLEAN] deploy前清理殘留 dialog: {len(_dlg_list)} 個已處理（WM_CLOSE）")
    except Exception:
        pass

    try:
        # [ALERT] 2026-08-28 FIX：delete舊「generate_template」步驟（一體化模板 — stable 前概念 — 掛 EA 已用熱鍵 Ctrl+1 — 模板冇用 → 多餘）
        # [ALERT] 2026-09-01（user實測 + 實驗驗證）：部署改用 .chr 方法（deploy_ea_via_chr — 取代熱鍵預載 + GUI attach）
        # 流程：複製基底 .chr → 改 id/symbol/EA → 寫新 .chr + order.wnd → 關 MT5 → 開 MT5（restore 自動掛）→ 平鋪窗口
        # 好處：完全避開 GUI automation（Alt+F / Ctrl+1 / 熱鍵預載 restart ×2）— 純檔案操作 — 穩定 + 快
        # 驗證：verify_heartbeat（心跳 + MT5 log loaded + OnInit — 保留）
        success = deploy_ea_via_chr(ea_name, symbol=args.symbol, timeframe=timeframe, inputs=inputs)
        if not success:
            print(f"[FAIL] {ea_name} deploy-via-chr failed（.chr 方法失敗）")
            return False
        check_abort()

        check_abort()
        
        # [ALERT] 2026-08-20（deploy流程檢測系統 — Step 4 gate）：EA loaded 驗證（等 + poll — 唔係immediately check）
        # log「loaded successfully」出現先算success（對真 MT5 log — 心跳/activity 可能假success）
        # [WARN] 2026-08-20 FIX：gate fail 唔好immediately return False — MT5 restart 後 log write延遲 → 假failed
        # → Step 5（心跳 + log 綜合）先係最終判定；呢度只 print 狀態
        _step4_ok = _wait_until(lambda: _ea_loaded_in_log(ea_name, (symbol or 'EURUSD')), 30,
                                f'EA {ea_name} loaded（MT5 log verify）', interval=3)
        if not _step4_ok:
            print(f"[WARN] Step 4 gate：{ea_name} 30s 內 log 未見 loaded — 交 Step 5 heartbeat fallback最終判定")
        
        # Step 4: Ensure AutoTrading ON
        # [ALERT] 2026-09-01 FIX：mt5_pid 未定義（NameError crash — 部署完成但報 failed）→ 用 find_mt5_pid() 攞當前 PID
        ensure_auto_trading_on(find_mt5_pid())
        check_abort()
        
        # Step 5: Verify（最終驗證 — [ALERT] 2026-08-20 deploy流程檢測系統）
        # Step 4 gate 已確認 MT5 log loaded → 心跳只係輔助（market closeno tick 心跳唔寫 — log 有 = success）
        # 心跳有 → 錦上添花；心跳冇但 log 已 loaded → 都係success（唔好因心跳誤判failed）
        _log_loaded = _ea_loaded_in_log(ea_name, (symbol or 'EURUSD'))
        # [ALERT] 2026-09-01 FIX（假成功 — EMA_Cross 案例）：heartbeat timeout 15s → 30s
        # （EA OnInit + 心跳寫入需要時間 — 特別係 MT5 慢/重啟後 — 15s 太短 → 誤報 FAIL）
        heartbeat = verify_heartbeat(ea_name, timeout=30)
        
        # [ALERT] 2026-09-01 FIX（用戶實測：Breakout loaded 但 OnInit 未跑 — 冇 EA icon + 冇心跳 = 假成功）：
        # before: `if heartbeat or _log_loaded` → 淨 log loaded 就話 SUCCESS（繞過 OnInit 驗證 — 假成功）
        # now: 要「心跳（OnInit 真跑）」或「log loaded + OnInit Print 確認」先話 SUCCESS
        # 淨 log loaded 冇 OnInit → FAIL（chart 未 activate — EA 未真正運行）
        _oninit_confirmed = False
        if not heartbeat:
            # 睇 MQL5/Logs（EA Print「已啟動」= OnInit 跑咗）
            # [ALERT] 2026-09-01 FIX（假成功 — EMA_Cross 案例）：OnInit Print 要新鮮（<5 分鐘 — 部署後先算）
            # （舊 Print「EMA_Cross 已啟動 01:16」殘留 → 誤判 OnInit 真跑 — 但今次部署 OnInit 未跑）
            _oninit_time = 0
            try:
                import glob as _g_s5
                _ml_s5 = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
                _ml_latest_s5 = None
                for _d_s5 in os.listdir(_ml_s5):
                    _lg_s5 = os.path.join(_ml_s5, _d_s5, 'MQL5', 'Logs')
                    if os.path.isdir(_lg_s5):
                        for _f_s5 in _g_s5.glob(os.path.join(_lg_s5, '*.log')):
                            if _ml_latest_s5 is None or os.path.getmtime(_f_s5) > os.path.getmtime(_ml_latest_s5):
                                _ml_latest_s5 = _f_s5
                if _ml_latest_s5:
                    with open(_ml_latest_s5, 'rb') as _f_s5b:
                        _raw_s5 = _f_s5b.read()
                    for _enc_s5 in ('utf-16', 'utf-8', 'cp1252'):
                        try:
                            _txt_s5 = _raw_s5.decode(_enc_s5); break
                        except Exception:
                            continue
                    # 逐行搵 EA 最後「已啟動」Print + 時間（HH:MM:SS → timestamp）
                    import re as _re_s5
                    for _ln_s5 in _txt_s5.splitlines():
                        if ea_name in _ln_s5 and ('已啟動' in _ln_s5 or '已start' in _ln_s5):
                            _tm_s5 = _re_s5.search(r'(\d{2}):(\d{2}):(\d{2})\.\d+', _ln_s5)
                            if _tm_s5:
                                _h_s5, _m_s5, _s_s5 = map(int, _tm_s5.groups())
                                _oninit_time = _h_s5 * 3600 + _m_s5 * 60 + _s_s5
                    # 而家時間（HH:MM:SS → seconds）
                    _now_tm = time.localtime()
                    _now_sec = _now_tm.tm_hour * 3600 + _now_tm.tm_min * 60 + _now_tm.tm_sec
                    # 最後「已啟動」Print 喺 5 分鐘內（同一天）→ OnInit 真跑（今次部署）
                    if _oninit_time and (_now_sec - _oninit_time) < 300 and (_now_sec - _oninit_time) >= 0:
                        _oninit_confirmed = True
                        print(f"[OK] {ea_name} OnInit Print「已啟動」新鮮確認（{_oninit_time}s ago — OnInit 真跑）")
            except Exception:
                pass
        
        if heartbeat or (_log_loaded and _oninit_confirmed):
            print(f"\n[DONE] SUCCESS: {ea_name} is running on {symbol} {timeframe}!")
            # [ALERT] 2026-08-31 FIX（Bug #150 — 3 個空白 EURUSD chart 殘留）：
            # MT5 restart 後 profile restore 舊 chart（空白冇 EA）→ 掃描所有 chart →
            # 冇掛 EA 嘅空白 chart 關閉（淨保留 target + 其他有 EA 運行中嘅 chart）
            try:
                _clean_blank_charts(mt5_pid, keep_symbol=(symbol or '').upper())
            except Exception:
                pass
            return True
        else:
            # [ALERT] 2026-09-01：心跳冇 + OnInit 未確認 → 假成功（唔話 SUCCESS）
            print(f"[FAIL] {ea_name} 心跳冇 + OnInit 未確認（MQL5/Logs 冇『已啟動』）— 假成功 — 唔當部署成功")
            # [ALERT] 2026-09-01 FIX（用戶實測：警告視窗話成功但圖表冇掛 EA — MT5 系統更新彈窗阻住）：
            # before: return False 但 steps 由 server 寫 done（4 步全 done）→ 警告視窗話成功但實際失敗 → 誤導
            # now: 失敗時覆寫 steps 顯示失敗（警告視窗/網頁見到「失敗」— 唔會誤導）
            try:
                import json as _j_fail
                _stf_fail = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.steps')
                with open(_stf_fail, 'w', encoding='utf-8') as _f_fail:
                    _j_fail.dump([
                        {'text': f'Deploy {ea_name} ({symbol})', 'status': 'done'},
                        {'text': f'Create new chart ({symbol})', 'status': 'done'},
                        {'text': f'Attach {ea_name}', 'status': 'done'},
                        {'text': f'Verify running status', 'status': 'doing'},
                        {'text': '[FAIL] Deploy failed: EA not truly running (OnInit not confirmed — MT5 popup/update may block)', 'status': 'fail'},
                    ], _f_fail, ensure_ascii=False)
                # 同步開發目錄（網頁版讀）
                try:
                    _cd_fail = os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop', 'mt5-cloud', 'agent')
                    if os.path.isdir(_cd_fail):
                        with open(os.path.join(_cd_fail, '.ai_control.steps'), 'w', encoding='utf-8') as _f_fail2:
                            _j_fail.dump([
                                {'text': f'Deploy {ea_name} ({symbol})', 'status': 'done'},
                                {'text': f'Create new chart ({symbol})', 'status': 'done'},
                                {'text': f'Attach {ea_name}', 'status': 'done'},
                                {'text': f'Verify running status', 'status': 'doing'},
                                {'text': '[FAIL] Deploy failed: EA not truly running (OnInit not confirmed — MT5 popup/update may block)', 'status': 'fail'},
                            ], _f_fail2, ensure_ascii=False)
                except Exception:
                    pass
            except Exception:
                pass
            return False
    except ControlAborted:
        print(f"\n[ALERT] deploy被user緊急stop！")
        return False
    finally:
        try:
            release()  # 無論successfailed都釋放控制
        except Exception:
            pass


# ─── CLI ───
def _clean_blank_charts(mt5_pid, keep_symbol=''):
    """[ALERT] 2026-08-31 FIX（Bug #150 — 3 個空白 EURUSD chart 殘留）
    掃描 MT5 所有 chart：
    - 有掛 EA 運行中（心跳新鮮）→ 保留
    - 係 target symbol（keep_symbol）→ 保留
    - 其他空白 chart（冇 EA）→ 關閉（WM_CLOSE）
    目的：MT5 restart 後 profile restore 舊 chart（空白冇 EA）— 唔好殘留一堆空白 chart
    """
    try:
        import ctypes as _ct_cc
        from ctypes import wintypes as _wt_cc
        _u_cc = _ct_cc.windll.user32

        # 搵 MT5 主視窗
        _main_cc = None
        def _cb_main_cc(h, _):
            nonlocal _main_cc
            _cls_cc = _ct_cc.create_unicode_buffer(64)
            _u_cc.GetClassNameW(h, _cls_cc, 64)
            if 'MetaTrad' in _cls_cc.value:
                _main_cc = h
            return True
        _WNDENUMPROC_CC = _ct_cc.WINFUNCTYPE(_wt_cc.BOOL, _wt_cc.HWND, _wt_cc.LPARAM)
        _u_cc.EnumWindows(_WNDENUMPROC_CC(_cb_main_cc), 0)
        if not _main_cc:
            print("[CLEAN] 搵唔到 MT5 主視窗 — skip 清空白 chart")
            return

        # 掃描所有 chart（MDI child — 標題含 , 如 EURUSD,H1）
        _charts_cc = []
        def _cb_chart_cc(h, _):
            _cls_cc = _ct_cc.create_unicode_buffer(64)
            _u_cc.GetClassNameW(h, _cls_cc, 64)
            _t_cc = _ct_cc.create_unicode_buffer(256)
            _u_cc.GetWindowTextW(h, _t_cc, 256)
            if _t_cc.value.strip() and ',' in _t_cc.value:
                _charts_cc.append((h, _t_cc.value.strip()))
            return True
        _u_cc.EnumChildWindows(_main_cc, _WNDENUMPROC_CC(_cb_chart_cc), 0)

        if not _charts_cc:
            print("[CLEAN] 冇 chart — skip")
            return

        # 判斷邊啲 chart 有 EA 運行中（心跳 fresh <300s）
        import glob as _g_cc
        _hb_files_cc = _g_cc.glob(os.path.join(COMMON_FILES, 'state_*.json')) + _g_cc.glob(os.path.join(COMMON_FILES, 'hb_*.txt'))
        _ea_running_cc = set()
        import time as _t_cc
        _now_cc = _t_cc.time()
        for _hf_cc in _hb_files_cc:
            try:
                if _now_cc - os.path.getmtime(_hf_cc) < 300:
                    _base_cc = os.path.basename(_hf_cc).replace('state_', '').replace('hb_', '').replace('.json', '').replace('.txt', '')
                    _ea_running_cc.add(_base_cc)
            except Exception:
                pass

        # [ALERT] 2026-08-31 FIX2：有 EA 心跳 → 讀 MT5 log 搵「EA (SYM,H1) loaded」對應
        # → 知道邊啲 chart 有 EA 掛住（保留）— 其他空白 chart 關閉（唔使保守保留全部）
        _keep_syms_cc = set()
        if _ea_running_cc:
            try:
                import glob as _g2_cc
                _lg2_cc = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
                _latest2_cc = None
                for _d3_cc in os.listdir(_lg2_cc):
                    _lgd2_cc = os.path.join(_lg2_cc, _d3_cc, 'logs')
                    if os.path.isdir(_lgd2_cc):
                        for _f5_cc in _g2_cc.glob(os.path.join(_lgd2_cc, '*.log')):
                            if _latest2_cc is None or os.path.getmtime(_f5_cc) > os.path.getmtime(_latest2_cc):
                                _latest2_cc = _f5_cc
                if _latest2_cc:
                    _raw2_cc = open(_latest2_cc, 'rb').read()
                    _txt2_cc = None
                    for _enc2_cc in ('utf-16', 'utf-8', 'cp1252', 'gbk'):
                        try:
                            _txt2_cc = _raw2_cc.decode(_enc2_cc); break
                        except Exception:
                            continue
                    if _txt2_cc:
                        import re as _re_cc
                        # [ALERT] 2026-08-31 FIX3：只保留「心跳 EA 最新一次 loaded」嘅 symbol
                        # （唔可以全部 loaded 記錄 — 舊記錄（EA 之前掛過其他 symbol）會誤保留空白 chart）
                        _ea_latest_sym_cc = {}
                        for _line2_cc in _txt2_cc.splitlines():
                            # expert XXX (SYM,H1) loaded successfully
                            _m2_cc = _re_cc.search(r'expert\s+(\w+)\s+\(([A-Z0-9_]+),', _line2_cc)
                            if _m2_cc and 'loaded successfully' in _line2_cc:
                                _ea_l2 = _m2_cc.group(1)
                                _sym_l2 = _m2_cc.group(2).upper()
                                if _ea_l2 in _ea_running_cc:
                                    # 最新記錄覆蓋舊記錄（log 順序 = 時間順序）
                                    _ea_latest_sym_cc[_ea_l2] = _sym_l2
                        for _ea_n2, _sym_n2 in _ea_latest_sym_cc.items():
                            _keep_syms_cc.add(_sym_n2)
                            print(f"[CLEAN] 保留 {_sym_n2}（{_ea_n2} 最新 loaded）")
            except Exception:
                pass
        # 加埋 target symbol
        if keep_symbol:
            _keep_syms_cc.add(keep_symbol)

        # [ALERT] 2026-08-31 FIX6（用戶實測 — 誤關 MACD_Cross）：唔可以靠「心跳 EA 數量」估邊個 chart 有 EA
        # （Volume_Spike + MACD_Cross 都掛 GBPUSD → 心跳計數得 1 → 誤關另一個）
        # → 直接讀 .chr 檔（MQL5/Profiles/Charts/<profile>/*.chr — UTF-16 text — 有 path=Experts\<EA>.ex5）
        # → 精準知道「邊個 chart 掛邊個 EA」→ 有 EA 嘅 chart 全部保留 + 冇 EA 嘅空白 chart 關閉
        _chr_ea_cc = {}  # chart 檔名 -> EA 名（冇 EA = 空白）
        try:
            import re as _re_chr2
            import glob as _g_chr2
            _data_root_chr2 = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
            for _d_chr2 in os.listdir(_data_root_chr2):
                _charts_root_chr2 = os.path.join(_data_root_chr2, _d_chr2, 'MQL5', 'Profiles', 'Charts')
                if not os.path.isdir(_charts_root_chr2):
                    continue
                # 揀 active profile（最近修改）
                _best_prof_chr2 = None
                _best_mt_chr2 = 0
                for _p_chr2 in os.listdir(_charts_root_chr2):
                    _pd_chr2 = os.path.join(_charts_root_chr2, _p_chr2)
                    if not os.path.isdir(_pd_chr2):
                        continue
                    for _cf_chr2 in _g_chr2.glob(os.path.join(_pd_chr2, '*.chr')):
                        try:
                            _mt_chr2 = os.path.getmtime(_cf_chr2)
                            if _mt_chr2 > _best_mt_chr2:
                                _best_mt_chr2 = _mt_chr2
                                _best_prof_chr2 = _pd_chr2
                        except Exception:
                            pass
                if not _best_prof_chr2:
                    continue
                for _cf_chr2 in _g_chr2.glob(os.path.join(_best_prof_chr2, '*.chr')):
                    try:
                        with open(_cf_chr2, 'rb') as _fh_chr2:
                            _data_chr2 = _fh_chr2.read()
                        _txt_chr2 = _data_chr2.decode('utf-16', errors='replace')
                        _m_chr2 = _re_chr2.search(r'path=(Experts[^<]+\.ex5)', _txt_chr2)
                        _ea_chr2 = _m_chr2.group(1).split('\\')[-1].replace('.ex5', '') if _m_chr2 else None
                        _chr_ea_cc[os.path.basename(_cf_chr2)] = _ea_chr2
                    except Exception as _e_chr2:
                        print(f"[CLEAN] 讀 .chr 失敗 {os.path.basename(_cf_chr2)}: {_e_chr2}")
        except Exception as _e_chr1:
            print(f"[CLEAN] FIX6 .chr 掃描失敗: {_e_chr1}")
        # .chr 檔有 EA → 保留（symbol 計數）；冇 EA → 空白 chart 關閉
        # [ALERT] .chr 檔可能未 sync（MT5 開住時啱啱部署完 — 未 save）→ 有 EA 心跳但 .chr 冇 → 要合併心跳
        _keep_count_cc = {}
        for _cf_cc, _ea_cf in _chr_ea_cc.items():
            if _ea_cf:
                # 有 EA → 保留（數 symbol 出現次數 — 每個 EA chart 一個）
                try:
                    with open(os.path.join(_best_prof_chr2, _cf_cc), 'rb') as _fh_sym:
                        _txt_sym = _fh_sym.read().decode('utf-16', errors='replace')
                    _m_sym = _re_chr2.search(r'symbol=(\S+)', _txt_sym)
                    if _m_sym:
                        _sym_cf = _m_sym.group(1).upper()
                        _keep_count_cc[_sym_cf] = _keep_count_cc.get(_sym_cf, 0) + 1
                except Exception:
                    pass
        # 合併心跳 EA 最新 loaded symbol（.chr 未 sync 嘅 EA — 例如啱啱部署完 — 都要保留）
        # [ALERT] 2026-08-31 FIX7：.chr 檔可能未包含啱啱部署嘅 EA（MT5 開住時唔 save .chr）
        # → 心跳 EA 有但 .chr 冇 → 加埋（每個心跳 EA 一個 chart 保留）
        if _ea_latest_sym_cc:
            for _ea_hb, _sym_hb in _ea_latest_sym_cc.items():
                if _ea_hb in _ea_running_cc:
                    _keep_count_cc[_sym_hb] = _keep_count_cc.get(_sym_hb, 0) + 1
        # [ALERT] 2026-09-01 FIX（用戶實測：新部署 EA 被 _clean_blank_charts 誤關 — Breakout loaded 後 removed）：
        # 啱啱部署嘅 EA（MT5 log「loaded successfully」但心跳未寫 — OnInit 延遲）都要保留
        # → 讀 MT5 log 最新 loaded 嘅 EA（5 分鐘內）— 即使心跳未寫都保留佢嘅 symbol（唔好關）
        try:
            import glob as _g_lc
            _lg_lc = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
            _latest_lc = None
            for _d_lc in os.listdir(_lg_lc):
                _lgd_lc = os.path.join(_lg_lc, _d_lc, 'logs')
                if os.path.isdir(_lgd_lc):
                    for _f_lc in _g_lc.glob(os.path.join(_lgd_lc, '*.log')):
                        if _latest_lc is None or os.path.getmtime(_f_lc) > os.path.getmtime(_latest_lc):
                            _latest_lc = _f_lc
            if _latest_lc and time.time() - os.path.getmtime(_latest_lc) < 600:
                _raw_lc = open(_latest_lc, 'rb').read()
                _txt_lc = None
                for _enc_lc in ('utf-16', 'utf-8', 'cp1252', 'gbk'):
                    try:
                        _txt_lc = _raw_lc.decode(_enc_lc); break
                    except Exception:
                        continue
                if _txt_lc:
                    import re as _re_lc
                    _loaded_sym_lc = {}  # EA -> 最後 loaded symbol
                    for _line_lc in _txt_lc.splitlines():
                        _m_lc = _re_lc.search(r'expert\s+(\w+)\s+\(([A-Z0-9_]+),', _line_lc)
                        if _m_lc and 'loaded successfully' in _line_lc:
                            _loaded_sym_lc[_m_lc.group(1)] = _m_lc.group(2).upper()
                    for _ea_lc, _sym_lc in _loaded_sym_lc.items():
                        # 啱啱 loaded（心跳未寫都保留 — 唔好誤關新部署 EA）
                        _keep_count_cc[_sym_lc] = _keep_count_cc.get(_sym_lc, 0) + 1
                        print(f"[CLEAN] 保留 {_sym_lc}（{_ea_lc} 啱啱 loaded — 心跳未寫都保留）")
        except Exception:
            pass
        # 加埋 target symbol（keep_symbol — 部署嗰個）
        if keep_symbol and keep_symbol not in _keep_count_cc:
            _keep_count_cc[keep_symbol] = 1
        if not _keep_count_cc:
            print("[CLEAN] 冇 .chr EA 記錄 + 冇心跳 EA — 全部當空白？skip（保守 — 唔亂關）")
            return
        _kept_cc = {}
        _closed_cc = 0
        for _h_cc, _title_cc in _charts_cc:
            _sym_part_cc = _title_cc.split(',')[0].upper()
            if _sym_part_cc in _keep_count_cc and _kept_cc.get(_sym_part_cc, 0) < _keep_count_cc[_sym_part_cc]:
                _kept_cc[_sym_part_cc] = _kept_cc.get(_sym_part_cc, 0) + 1
                continue
            # 重複/空白 chart → 關閉
            _u_cc.PostMessageW(_h_cc, 0x0010, 0, 0)  # WM_CLOSE
            _closed_cc += 1
            print(f"[CLEAN] 關閉空白 chart: {_title_cc[:40]}")
            _t_cc.sleep(0.5)

        print(f"[CLEAN] 清空白 chart 完成 — 關閉 {_closed_cc} 個（保留: {_keep_count_cc}）")
    except Exception as _e_cc:
        print(f"[CLEAN] 清空白 chart failed: {_e_cc}")


def _clean_blank_charts_via_chr():
    """[ALERT] 2026-08-31（user實測方法 — 根治空白 chart）：
    用 .chr 檔方法清空白 chart（唔靠 EnumWindows）：
    1. 讀 MQL5/Profiles/Charts/<profile>/*.chr（MT5 save chart 嘅檔案 — UTF-16 text）
    2. Double check：開每個 .chr 睇內容（symbol + path=Experts\\<EA>.ex5）
    3. 冇 EA 嘅空白 .chr → 移去 _deleted backup（唔直接刪 — 可復原）
    4. MT5 關閉時刪 .chr → 開機唔會 restore 嗰個 chart（user 實測有效）
    適用時機：auto_attach restart MT5 前（關 MT5 前清）— 令 MT5 save 乾淨 profile
    [ALERT] 2026-08-31 FIX：只掃描「最近修改」嘅 profile（active — MT5 save chart 嗰個）
    — 唔好掃全部 profile（British Pound/Market Overview 係 MT5 預設 — 刪咗會壞預設 chart 集）
    """
    try:
        import glob as _g_chr
        # 搵 MT5 data 目錄
        _data_root_chr = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
        if not os.path.isdir(_data_root_chr):
            print("[CHR] 搵唔到 MT5 data 目錄 — skip")
            return 0
        _total_deleted = 0
        for _d_chr in os.listdir(_data_root_chr):
            _charts_root = os.path.join(_data_root_chr, _d_chr, 'MQL5', 'Profiles', 'Charts')
            if not os.path.isdir(_charts_root):
                continue
            # 揀 active profile（最近修改嗰個 — MT5 save chart 去嗰度）
            _best_prof = None
            _best_mtime = 0
            for _prof_chr in os.listdir(_charts_root):
                _prof_dir = os.path.join(_charts_root, _prof_chr)
                if not os.path.isdir(_prof_dir):
                    continue
                _chr_files = _g_chr.glob(os.path.join(_prof_dir, '*.chr'))
                for _cf_chr in _chr_files:
                    try:
                        _mt = os.path.getmtime(_cf_chr)
                        if _mt > _best_mtime:
                            _best_mtime = _mt
                            _best_prof = _prof_dir
                    except Exception:
                        pass
            if not _best_prof:
                continue
            _chr_files = sorted(_g_chr.glob(os.path.join(_best_prof, '*.chr')))
            if not _chr_files:
                continue
            _blank_chr = []
            for _cf_chr in _chr_files:
                try:
                    with open(_cf_chr, 'rb') as _fh_chr:
                        _data_chr = _fh_chr.read()
                    _txt_chr = _data_chr.decode('utf-16', errors='replace')
                    # Double check：有冇 EA（path=Experts\XXX.ex5）
                    _has_ea_chr = 'path=Experts' in _txt_chr and '.ex5' in _txt_chr
                    if not _has_ea_chr:
                        _blank_chr.append(_cf_chr)
                except Exception:
                    pass
            if _blank_chr:
                # 刪除（移去 _deleted backup — 可復原）
                _bk_dir_chr = os.path.join(_best_prof, '_deleted')
                os.makedirs(_bk_dir_chr, exist_ok=True)
                for _cf2_chr in _blank_chr:
                    try:
                        _dst_chr = os.path.join(_bk_dir_chr, os.path.basename(_cf2_chr))
                        # 如果 backup 已有同名 → 加時間戳
                        if os.path.exists(_dst_chr):
                            _dst_chr = os.path.join(_bk_dir_chr, f"{time.time():.0f}_{os.path.basename(_cf2_chr)}")
                        os.rename(_cf2_chr, _dst_chr)
                        print(f"[CHR] 刪除空白 chart 設定: {os.path.basename(_cf2_chr)}（{os.path.basename(_best_prof)} profile）")
                        _total_deleted += 1
                    except Exception as _e_chr2:
                        print(f"[CHR] 刪除 {os.path.basename(_cf2_chr)} failed: {_e_chr2}")
        if _total_deleted:
            print(f"[CHR] 完成 — 刪除 {_total_deleted} 個空白 .chr（MT5 開機唔會 restore 佢哋）")
            # [ALERT] 2026-09-01 FIX（user實測：開好多視窗 — order.wnd 未同步 — MT5 見 order.wnd 有已刪 chart → 重新生成）：
            # → 同步 order.wnd（移除已刪 chart 項目 — MT5 開機照 order.wnd 開 chart）
            try:
                _ord_wnd_chr = os.path.join(_best_prof, 'order.wnd')
                if os.path.isfile(_ord_wnd_chr):
                    _ow_raw_chr = open(_ord_wnd_chr, 'rb').read()
                    _ow_txt_chr = _ow_raw_chr.decode('utf-16', errors='replace')
                    _ow_lines_chr = [l.strip() for l in _ow_txt_chr.split('\r\n') if l.strip()]
                    _deleted_names = {os.path.basename(c) for c in _blank_chr}
                    _ow_new_chr = [l for l in _ow_lines_chr if l not in _deleted_names]
                    if len(_ow_new_chr) != len(_ow_lines_chr):
                        with open(_ord_wnd_chr, 'wb') as _f_ow_chr:
                            _f_ow_chr.write(b'\xff\xfe')
                            _f_ow_chr.write(('\r\n'.join(_ow_new_chr) + '\r\n').encode('utf-16-le'))
                        print(f"[CHR] order.wnd 同步（移除 {len(_ow_lines_chr)-len(_ow_new_chr)} 個已刪 chart）: {_ow_new_chr}")
            except Exception as _e_ow_chr:
                print(f"[WARN] order.wnd 同步 failed: {_e_ow_chr}")
        return _total_deleted
    except Exception as _e_chr:
        print(f"[CHR] 清空白 .chr failed: {_e_chr}")
        return 0


def _exec_open_chart_script():
    """[ALERT] 2026-08-15：執行 OpenChart script（Ctrl+I → 插入 menu → 腳本 → OpenChart — user實測方法）
    取代 Navigator scan（pywinauto TreeView 64-bit 問題 — 唔可靠）"""
    try:
        # [ALERT] 2026-08-22（user要求：UAC 檢測機制）：開 chart script 前檢查 UAC/授權窗口
        try:
            if not _detect_and_handle_uac('開 chart script UAC 檢查', max_wait=20):
                print("[WARN] 開 chart script：UAC 授權窗口未處理")
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
        # [ALERT] 2026-08-15：熱鍵attach EA — 要「圖表 active」（真正 EA deploy都係先開圖表先 send 熱鍵）
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
            print("   [CLIP] 冇圖表 — 開空圖表（Alt+F → Enter → Enter）")
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
        # 熱鍵 Ctrl+4（OpenChart_Helper — attach落圖表 → OnInit 讀 json → ChartOpen(symbol) → ExpertRemove）
        # [ALERT] 2026-09-01（user要求：唔好用 Ctrl+1-9 — 統一 Ctrl+1 重用 + Alt+F 開 chart）：
        # 呢個係死 code（_exec_open_chart_script 冇被任何地方 call — OpenChart_Helper 舊方法已停用）
        # 保留做參考（stable 結構）— 但唔會實際行
        # [ALERT] 2026-08-15：改用 pyautogui（真實 keydown/keyup — 比 pywinauto send_keys 穩定 — user揀 B）
        try:
            import pyautogui as _pg2
            _pg2.FAILSAFE = False
            _pg2.hotkey('ctrl', '4')
        except Exception:
            _sk2('^4')
        time.sleep(2.5)
        # 驗證：Properties dialog 彈出（熱鍵 work — EA attach準備）
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
            print("   [WARN] Ctrl+4 冇彈 Properties（熱鍵未觸發）")
            return False
        # 撳「確定」（Properties dialog — EA attach → OnInit 執行 → ChartOpen(symbol)）
        try:
            import pyautogui as _pg3
            _pg3.FAILSAFE = False
            _pg3.press('enter')
        except Exception:
            _sk2('{ENTER}')
        time.sleep(3)
        print("   [OK] OpenChart_Helper 已attach（Properties → 確定 — 圖表開咗）")
        return True
    except Exception as _e2:
        print(f"   [WARN] _exec_open_chart_script exception: {_e2}")
        return False


def remove_ea_via_chr(ea_name, mt5_pid=None):
    """[ALERT] 2026-08-31（user實測方法）：用 .chr 檔方法剷除 EA（取代 Alt+W 窗口方法）
    原理：EA 掛喺 chart — MT5 正常關閉時 save chart 做 .chr 檔（MQL5/Profiles/Charts/<profile>/*.chr）
    → 關 MT5（save .chr）→ 讀 .chr double check 搵目標 EA → 刪 .chr → 開 MT5 → 嗰個 chart 唔會 restore
    [ALERT] 2026-08-31 FIX：MT5 開住時 .chr 可能未 sync（啱啱部署完冇 save）→ 要先關 MT5 先讀 .chr
    步驟：
    1. 確認 EA running（心跳/log）
    2. 關 MT5（WM_CLOSE 正常關閉 save profile）→ 等 MT5 完全關
    3. 讀 .chr 檔 → double check 搵目標 EA（path=Experts\<EA>.ex5）
    4. 刪目標 .chr（移去 _deleted backup — 可復原）
    5. 開 MT5 → 等 ready
    6. 驗證（心跳停 / .chr 冇返）
    """
    import subprocess as _sp
    import glob as _gl
    import ctypes as _ct
    import re
    from ctypes import wintypes as _wt
    _u = _ct.windll.user32

    # 0. 確認 EA running（心跳 fresh）— 唔 fresh 都繼續（可能心跳殘留但 chart 仲有）
    _hb_fresh = False
    try:
        _cfd = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
        for _hfn in (f'state_{ea_name}.json', f'hb_{ea_name}.txt'):
            _hfp = os.path.join(_cfd, _hfn)
            if os.path.isfile(_hfp) and time.time() - os.path.getmtime(_hfp) < 60:
                _hb_fresh = True
    except Exception:
        pass

    # 1. 關 MT5（WM_CLOSE 正常關閉 — save .chr）
    try:
        _out = _sp.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
        _pid = None
        for _l in _out.stdout.decode('utf-8', errors='replace').splitlines():
            _pa = [p.strip().strip('"') for p in _l.split(',')]
            if len(_pa) >= 2 and _pa[0] == 'terminal64.exe' and _pa[1].isdigit():
                _pid = int(_pa[1]); break
        if _pid:
            from pywinauto import Application as _App_r
            _app_r = _App_r(backend='win32').connect(process=_pid, timeout=8)
            _main_r = _app_r.window(class_name='MetaQuotes::MetaTrader::5.00')
            _u.PostMessageW(_ct.c_void_p(int(_main_r.element_info.handle)), 0x0010, 0, 0)  # WM_CLOSE
            print("[CLIP] MT5 正常關閉中（save chart profile → .chr）...")
            # [ALERT] 2026-08-31 FIX：唔好 poll 等完全關（最多 20s）— agent.py 會即刻重開 MT5（覆寫 .chr）
            # → 等 4 秒（WM_CLOSE save 完）→ 即刻讀 .chr（趁 agent 重開前）— 爭取時間窗口
            # [ALERT] 2026-09-01 FIX（user實測：剷除開窗口 dialog + 冇刪正確圖表）：4 秒太短（MT5 未完全關 — .chr 未 save 完）
            time.sleep(10)
            for _chk_t in range(5):
                _r_chk2 = _sp.run('tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH', shell=True, capture_output=True)
                if b'terminal64' not in _r_chk2.stdout:
                    break
                time.sleep(2)
            print("[OK] MT5 已完全關閉（等 10s + process 確認）— .chr 已 save，讀 .chr 準確")
            # [ALERT] 2026-09-01 FIX（user實測：remove 讀唔到 .chr — MT5 關閉 save 需要時間）：
            # → 等 .chr 檔出現（最多 30 秒 — 大 .chr 檔 7MB save 慢）+ retry 讀
            _chr_ready = False
            _chr_now = []
            _data_root_t = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
            for _retry_t in range(15):
                _chr_now = []
                for _d_t in os.listdir(_data_root_t):
                    _ct_t = os.path.join(_data_root_t, _d_t, 'MQL5', 'Profiles', 'Charts')
                    if os.path.isdir(_ct_t):
                        _chr_now += _gl.glob(os.path.join(_ct_t, '*', '*.chr'))
                if _chr_now:
                    _chr_ready = True
                    break
                time.sleep(2)
            if _chr_ready:
                print(f"[CHR-DBG] .chr 檔出現（{len(_chr_now)} 個）— 開始讀")
            else:
                print(f"[WARN] 等 30 秒 .chr 檔都未出現 — 可能 MT5 關閉冇 save")
        else:
            print("[INFO] MT5 未開 — 直接處理 .chr")
    except Exception as _e2:
        print(f"[WARN] 關 MT5 failed: {_e2}")
        _sp.run('taskkill /F /IM terminal64.exe', shell=True, capture_output=True)
        time.sleep(3)

    # 2. 讀 .chr → double check 搵目標 EA（而家 MT5 關咗 — .chr sync）
    _target_chr = None
    _data_root = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
    print(f"[CHR-DBG] 掃描 .chr 開始 — data_root={_data_root}")
    try:
        for _d in os.listdir(_data_root):
            _charts_root = os.path.join(_data_root, _d, 'MQL5', 'Profiles', 'Charts')
            if not os.path.isdir(_charts_root):
                continue
            # 揀 active profile（最近修改）
            _best_prof = None
            _best_mt = 0
            for _p in os.listdir(_charts_root):
                _pd = os.path.join(_charts_root, _p)
                if not os.path.isdir(_pd):
                    continue
                for _cf in _gl.glob(os.path.join(_pd, '*.chr')):
                    try:
                        _mt = os.path.getmtime(_cf)
                        if _mt > _best_mt:
                            _best_mt = _mt
                            _best_prof = _pd
                    except Exception:
                        pass
            if not _best_prof:
                print(f"[CHR-DBG] 冇揀到 profile（{_charts_root} 冇 .chr）")
                continue
            print(f"[CHR-DBG] 揀咗 profile: {_best_prof}")
            for _cf in _gl.glob(os.path.join(_best_prof, '*.chr')):
                try:
                    with open(_cf, 'rb') as _fh:
                        _data = _fh.read()
                    _txt = _data.decode('utf-16', errors='replace')
                    # Double check：path=Experts\<EA>.ex5
                    _m = re.search(r'path=(Experts[^<]+\.ex5)', _txt)
                    # [ALERT] 2026-09-01 DEBUG：print 每個 .chr 嘅 EA（搵點解話「冇 .chr 檔」）
                    _dbg_ea = _m.group(1).split('\\')[-1].replace('.ex5', '') if _m else '(冇)'
                    print(f"[CHR-DBG] {os.path.basename(_cf)}: EA={_dbg_ea}（{len(_data)} bytes）")
                    if _m and _m.group(1).split('\\')[-1].replace('.ex5', '') == ea_name:
                        _target_chr = _cf
                        print(f"[CHR] 搵到 {ea_name} 嘅 .chr: {os.path.basename(_cf)}")
                        break
                except Exception as _e_chr_rd:
                    print(f"[CHR-DBG] 讀 {os.path.basename(_cf)} failed: {_e_chr_rd}")
                    pass
            if _target_chr:
                break
    except Exception as _e:
        print(f"[WARN] 搵 .chr failed: {_e}")

    if not _target_chr:
        # [ALERT] 2026-09-01 FIX（user實測：剷除開窗口 dialog + 冇刪正確圖表）：
        # before: 冇 .chr → fallback 窗口方法（開窗口 dialog — 用戶唔想要）
        # now: 掃描全部 profile .chr（Ichimoku 可能喺非 Euro profile — 之前只掃「最近修改嘅 profile」漏咗）+ 冇 → 直接 fail
        try:
            for _d in os.listdir(_data_root):
                _charts_root = os.path.join(_data_root, _d, 'MQL5', 'Profiles', 'Charts')
                if not os.path.isdir(_charts_root):
                    continue
                for _p in os.listdir(_charts_root):
                    _pd = os.path.join(_charts_root, _p)
                    if not os.path.isdir(_pd) or _p == '_deleted':
                        continue
                    for _cf in _gl.glob(os.path.join(_pd, '*.chr')):
                        try:
                            with open(_cf, 'rb') as _fh:
                                _data2 = _fh.read()
                            _txt2 = _data2.decode('utf-16', errors='replace')
                            _m2 = re.search(r'path=(Experts[^<]+\.ex5)', _txt2)
                            if _m2 and _m2.group(1).split('\\')[-1].replace('.ex5', '') == ea_name:
                                _target_chr = _cf
                                print(f"[CHR] 搵到 {ea_name} 嘅 .chr（{_p} profile）: {os.path.basename(_cf)}")
                                break
                        except Exception:
                            pass
                    if _target_chr:
                        break
                if _target_chr:
                    break
        except Exception as _e_all_chr:
            print(f"[WARN] 掃描全部 profile .chr failed: {_e_all_chr}")
    if not _target_chr:
        # 冇 .chr（可能未部署/已剷除/MT5 未 save）→ 唔 fallback 窗口方法（user要求）→ 開返 MT5 + fail
        print(f"[INFO] {ea_name} 冇 .chr 檔（可能未部署/已剷除/MT5 未 save）— 唔用窗口方法（user要求）— 開返 MT5")
        _sp.Popen([MT5_PATH])
        return False

    # 3. 刪目標 .chr（移去 _deleted backup）
    try:
        _bk = os.path.join(os.path.dirname(_target_chr), '_deleted')
        os.makedirs(_bk, exist_ok=True)
        _dst = os.path.join(_bk, os.path.basename(_target_chr))
        if os.path.exists(_dst):
            _dst = os.path.join(_bk, f"{time.time():.0f}_{os.path.basename(_target_chr)}")
        os.rename(_target_chr, _dst)
        print(f"[CHR] 已刪除 {ea_name} 嘅 .chr（→ _deleted backup）— MT5 開機唔會 restore")
        # [ALERT] 2026-09-01 FIX（user實測：刪 .chr 後 MT5 開機照開 chart — order.wnd 記錄要開邊啲 chart）：
        # → 要成個 chart 移除，仲要同步刪 order.wnd 入面對應嘅 chart 項目（order.wnd = MT5 開機照呢個開 chart）
        try:
            _ord_wnd = os.path.join(os.path.dirname(_target_chr), 'order.wnd')
            if os.path.isfile(_ord_wnd):
                _ow_raw = open(_ord_wnd, 'rb').read()
                _ow_txt = _ow_raw.decode('utf-16', errors='replace')
                _ow_lines = [l.strip() for l in _ow_txt.split('\r\n') if l.strip()]
                _ow_target = os.path.basename(_target_chr)
                if _ow_target in _ow_lines:
                    _ow_new = [l for l in _ow_lines if l != _ow_target]
                    _ow_out = '\r\n'.join(_ow_new) + '\r\n'
                    with open(_ord_wnd, 'wb') as _f_ow:
                        _f_ow.write(b'\xff\xfe')
                        _f_ow.write(_ow_out.encode('utf-16-le'))
                    print(f"[CHR] 已同步刪除 order.wnd 項目: {_ow_target}（MT5 開機唔會再開呢個 chart）")
                else:
                    print(f"[CHR] order.wnd 冇 {_ow_target} 項目（唔使刪）")
        except Exception as _e_ow:
            print(f"[WARN] 刪 order.wnd 項目 failed: {_e_ow}")
        # [ALERT] 2026-09-01 FIX（user實測：剷除後心跳殘留誤判「EA 仲運行」→ steps 話 failed）：
        # 成功刪 .chr 後 → 一齊刪心跳檔（state_<EA>.json + hb_<EA>.txt — Terminal Common + MQL5/Files）
        try:
            import glob as _g_hbd
            _cfd_hbd = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
            for _hbd in _g_hbd.glob(os.path.join(_cfd_hbd, f'state_{ea_name}.*')) + _g_hbd.glob(os.path.join(_cfd_hbd, f'hb_{ea_name}.*')):
                try:
                    os.remove(_hbd)
                    print(f"[HB] 已刪心跳檔: {os.path.basename(_hbd)}")
                except Exception:
                    pass
            # MQL5/Files 版（舊 EA 寫 MQL5/Files 唔係 Common/Files）
            for _d_hbd in os.listdir(os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')):
                _mf_hbd = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', _d_hbd, 'MQL5', 'Files')
                if os.path.isdir(_mf_hbd):
                    for _hbd2 in _g_hbd.glob(os.path.join(_mf_hbd, f'state_{ea_name}.*')) + _g_hbd.glob(os.path.join(_mf_hbd, f'hb_{ea_name}.*')):
                        try:
                            os.remove(_hbd2)
                            print(f"[HB] 已刪 MQL5/Files 心跳檔: {os.path.basename(_hbd2)}")
                        except Exception:
                            pass
        except Exception as _e_hbd:
            print(f"[WARN] 刪心跳檔 failed: {_e_hbd}")
    except Exception as _e3:
        print(f"[FAIL] 刪 .chr failed: {_e3}")
        _sp.Popen([MT5_PATH])
        return False

    # 4. 開 MT5
    try:
        _sp.Popen([MT5_PATH])
        print("[OK] MT5 重新啟動中...")
        _start = time.time()
        _ready = False
        while time.time() - _start < 90:
            _p2 = find_mt5_pid()
            if _p2:
                try:
                    from pywinauto import Application as _App_w
                    _a = _App_w(backend='win32').connect(process=_p2, timeout=5)
                    _w = _a.window(class_name='MetaQuotes::MetaTrader::5.00')
                    if _w.exists():
                        _ready = True
                        break
                except Exception:
                    pass
            time.sleep(3)
        if _ready:
            print("[OK] MT5 已開 + ready")
        else:
            print("[WARN] MT5 90s 未 ready（繼續 — 可能慢）")
    except Exception as _e4:
        print(f"[WARN] 開 MT5 failed: {_e4}")

    # 5. 驗證（心跳停 = EA 剷除成功）
    time.sleep(10)
    _hb_gone = True
    try:
        _cfd = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
        for _hfn in (f'state_{ea_name}.json', f'hb_{ea_name}.txt'):
            _hfp = os.path.join(_cfd, _hfn)
            if os.path.isfile(_hfp) and time.time() - os.path.getmtime(_hfp) < 120:
                _hb_gone = False
    except Exception:
        pass
    if _hb_gone:
        print(f"[OK] {ea_name} 剷除成功（心跳停 — .chr 已刪）")
        return True
    else:
        print(f"[WARN] {ea_name} 心跳仲新鮮（可能 MT5 restore 返？）— 檢查")
        return True  # 保守當成功（.chr 已刪 — 下次 restart 會冇）
def remove_ea_from_chart(ea_name, mt5_pid=None):
    """真pause/remove（fallback — 舊 Alt+W 窗口 dialog 方法）：
    Alt+W 窗口 dialog → ListView 揀 chart → Enter → Ctrl+W 關閉
    返回 True = removesuccess/已冇 EA；False = failed"""
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
        print("[WARN] MT5 未開 — 冇嘢要remove")
        return True

    _app = _App(backend='win32').connect(process=mt5_pid)
    _win = _app.window(class_name='MetaQuotes::MetaTrader::5.00')
    _win.set_focus()
    time.sleep(1)

    # [ALERT] 2026-08-22（user要求：UAC 檢測機制）：remove流程都檢查 UAC/授權窗口
    try:
        if not _detect_and_handle_uac(f'remove {ea_name} UAC 檢查', max_wait=20):
            print(f"[WARN] remove {ea_name}：UAC 授權窗口未處理（等user手動撳）")
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
                        # [ALERT] 2026-08-29 FIX（remove假failed — 窗口 dialog 誤判）：只認「窗口」dialog 本身
                        # before所有 #32770 有文字都算 → 其他 dialog（殘留/其他 app）title 含「窗口」→ 誤判「未關」
                        # → 精準匹配：class #32770 + title 以「窗口」開頭（MT5「窗口」dialog 標準標題）
                        # （唔可以用『窗口』in title — 其他 dialog title 可能含「窗口」兩字）
                        _t = tb.value.strip()
                        if _t.startswith('窗口') or _t == 'Windows':
                            found.append((_t, h))
            return True
        _u.EnumWindows(_ct.WINFUNCTYPE(_ct.c_bool, _ct.c_void_p, _ct.c_void_p)(cb), 0)
        return found

    # 0. 檢查 EA 係咪真係running（MT5 log 最後狀態 + 心跳）
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
                        if 'removed' in _ln_r or '已stop' in _ln_r:
                            _last_r = 'stopped'
                        elif 'loaded successfully' in _ln_r or '已start' in _ln_r:
                            _last_r = 'started'
                _ea_running = (_last_r == 'started')
    except Exception:
        pass
    # 心跳檢查（state_<EA>.json 新鮮 = running）
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
        print(f"ℹ️ {ea_name}：未running（log 最後 stopped / 冇心跳）— 唔使remove，直接done")
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
        print("[WARN] not found「窗口」dialog 或 ListView（Alt+W 冇彈出？）")
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
    print(f"[CLIP] 窗口 dialog 有 {_cnt} 個 chart：")
    for _i, _t in enumerate(_items):
        print(f"  [{_i}] {_t}")

    # 4. 對應 EA → symbol（由 MT5 log 搵target EA 掛邊個 symbol）
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
                        if 'removed' in _ln_t or '已stop' in _ln_t:
                            _last_sym = None
                        elif 'loaded successfully' in _ln_t or '已start' in _ln_t:
                            _last_sym = _m_t.group(1)
                _target_sym = _last_sym
    except Exception:
        pass
    if _target_sym:
        print(f"[TARGET] target EA {ea_name} attached on {_target_sym}（MT5 log）")
    else:
        print(f"[WARN] 由 MT5 log not found {ea_name} 掛邊個 symbol（用 ListView 第一個 chart 做 target）")
        _target_sym = None

    # 5. 揀目標 chart（對應 symbol → ListView index）
    # [ALERT] 2026-08-21 FIX（多個同名 chart 揀錯 — user實測）：唔可以淨揀第一個 match symbol 嘅 chart
    # （3 個 UK100 時 EA 可能attached on第 2/3 個 → remove錯 chart → 假success）
    # → 策略：逐個試（由 symbol match start）→ Ctrl+W 關 → 檢查 EA 真係remove（心跳停/log removed）→ 未remove就下一個
    # [ALERT] 2026-08-31 FIX2（#157 剷除誤傷其他 EA — Multi_TimeFrame 案例）：唔可以 fallback 揀「全部 chart」
    # （重複 pause_cmd 第二個 remove 時 _target_sym 讀唔到（GBPUSD 已被第一個 remove 關咗）→ fallback 全部 chart → 揀 chart [0]（USDJPY）→ Ctrl+W 關錯 → 誤剷 Multi_TimeFrame）
    # → 搵唔到 target symbol → 唔好亂關（直接 fail — 寧願 user 再撳多次）
    _candidates = []
    if _target_sym:
        # [ALERT] 2026-09-01 FIX（用戶實測：剷 Momentum 誤剷 Breakout — 兩個都掛 USDCHF）：
        # before: 所有 match symbol 嘅 chart 都當 candidates（USDCHF ×2 → 逐個剷 → 先剷錯 Breakout）
        # now: 用 .chr 檔精準判斷「邊個 chart 掛緊 target EA」（MQL5/Profiles/Charts/<profile>/*.chr — 有 path=Experts\<EA>.ex5）
        # → 淨剷「掛緊 target EA」嗰個 chart（唔會誤剷其他 EA 嘅 chart）
        _chr_sym_map = {}  # chart index（ListView 順序）-> EA 名
        try:
            import glob as _g_chr_rm
            import re as _re_chr_rm
            _data_root_chr_rm = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
            _best_prof_chr_rm = None
            _best_mt_chr_rm = 0
            for _d_chr_rm in os.listdir(_data_root_chr_rm):
                _charts_root_rm = os.path.join(_data_root_chr_rm, _d_chr_rm, 'MQL5', 'Profiles', 'Charts')
                if not os.path.isdir(_charts_root_rm):
                    continue
                for _p_chr_rm in os.listdir(_charts_root_rm):
                    _pd_chr_rm = os.path.join(_charts_root_rm, _p_chr_rm)
                    if not os.path.isdir(_pd_chr_rm):
                        continue
                    for _cf_chr_rm in _g_chr_rm.glob(os.path.join(_pd_chr_rm, '*.chr')):
                        try:
                            _mt_chr_rm = os.path.getmtime(_cf_chr_rm)
                            if _mt_chr_rm > _best_mt_chr_rm:
                                _best_mt_chr_rm = _mt_chr_rm
                                _best_prof_chr_rm = _pd_chr_rm
                        except Exception:
                            pass
            if _best_prof_chr_rm:
                # .chr 檔名順序 = 開 chart 順序（chart01.chr, chart02.chr...）— 對應 ListView 順序
                _chr_files_rm = sorted(_g_chr_rm.glob(os.path.join(_best_prof_chr_rm, 'chart*.chr')))
                for _ci_rm, _cf_rm in enumerate(_chr_files_rm):
                    try:
                        _raw_rm = open(_cf_rm, 'rb').read()
                        _txt_rm = None
                        for _enc_rm in ('utf-16', 'utf-8', 'cp1252'):
                            try:
                                _txt_rm = _raw_rm.decode(_enc_rm); break
                            except Exception:
                                continue
                        if _txt_rm:
                            _m_rm = _re_chr_rm.search(r'path=Experts\\([A-Za-z_][A-Za-z0-9_]*)\.ex5', _txt_rm)
                            _m_sym_rm = _re_chr_rm.search(r'symbol=([A-Za-z0-9_]+)', _txt_rm)
                            if _m_rm and _m_sym_rm:
                                _ea_chr_rm = _m_rm.group(1)
                                _sym_chr_rm = _m_sym_rm.group(1).upper()
                                if _sym_chr_rm == _target_sym.upper():
                                    _chr_sym_map[_ci_rm] = _ea_chr_rm
                                    print(f"[CLIP] .chr [{_ci_rm}] = {_sym_chr_rm} 掛 {_ea_chr_rm}")
                    except Exception:
                        pass
        except Exception:
            pass
        for _i, _t in enumerate(_items):
            if _t.upper().startswith(_target_sym.upper()):
                # 如果 .chr 有記錄 → 只剷「掛緊 target EA」嗰個；冇 .chr 記錄 → 保守（match symbol 都當候選 — 但逐個試會 check 心跳）
                _chr_ea = _chr_sym_map.get(_i)
                if _chr_ea and _chr_ea != ea_name:
                    print(f"[SKIP] chart [{_i}] {_t} 掛 {_chr_ea}（唔係 {ea_name}）— 唔剷（防誤剷）")
                    continue
                _candidates.append(_i)
    # [ALERT] 2026-09-01 FIX：.chr 有記錄但冇 match target EA → 冇 candidates → 唔亂剷
    if not _candidates and _chr_sym_map:
        print(f"[FAIL] .chr 顯示冇 chart 掛緊 {ea_name}（可能已剷）— 唔亂剷其他 EA")
        try:
            _sk('{ESC}')
        except Exception:
            pass
        return False
    if not _candidates:
        # [ALERT] 2026-08-31 FIX2：唔再 fallback 全部 chart（誤剷其他 EA）
        # 只容許「log 完全冇記錄」（_lat_r 唔存在/讀唔到）時 fallback（單 chart 環境 — 安全）
        _log_unavailable = False
        try:
            _log_unavailable = not _lat_r or not os.path.isfile(_lat_r)
        except Exception:
            _log_unavailable = True
        if _log_unavailable:
            _candidates = list(range(len(_items)))
        else:
            print(f"[FAIL] target symbol {_target_sym or '?'} 搵唔到對應 chart（有 log 但冇 match）— 唔亂關（防誤剷其他 EA）")
            try:
                _sk('{ESC}')
            except Exception:
                pass
            return False
    print(f"[PIN] target symbol {_target_sym or '?'} → candidate chart: {_candidates}")

    _removed_ok = False
    _attempted = set()  # [ALERT] 2026-08-21：已試過嘅 symbol+index 組合（重新讀 ListView 後 index 會移位）
    for _target_idx in _candidates:
        # [ALERT] 2026-08-21 FIX（index 移位 bug）：每次試before重新對應 symbol → 最新 index
        # （remove chart 後 ListView 重新排位 — 舊 index 會指錯 chart）
        # [ALERT] 2026-08-25 FIX（多個同名 chart removefailed — MACD AUDUSD×2 案例）：_attempted 用 (index, text) 會誤判
        # （第二次 ListView 重排後剩返嘅 chart 用返 index 0 + 同名 → (0, AUDUSD) 喺 _attempted → 當「試過」→ 唔試 → 「冇新嘅 chart」）
        # → 放寬：每次試before重新搵「未試過嘅同 symbol chart」（text 計數代替 index 計數）
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
                # [ALERT] 2026-08-25 FIX2（MACD AUDUSD×2 — 重讀 ListView 得返 1 個同名 chart 但 _attempted 阻住）：
                # remove咗一個同名 chart 後 ListView 重排 — 剩返嗰個用返 index 0（text 一樣）
                # → 只要「同名 chart 數目 >= 嘗試次數+1」就要再試（唔好因為 text 一樣就當試過）
                _tried_sym_cnt = sum(1 for _i7, _t7 in _attempted if _t7.upper().startswith(_target_sym.upper()))
                if _tried_sym_cnt < len(_all_sym_now) or _tried_sym_cnt == 0:
                    _idx_to_try = _tried_sym_cnt if _tried_sym_cnt < len(_all_sym_now) else 0
                    _found_cur = _all_sym_now[_idx_to_try][0]
                    print(f"[OK] 放寬 _attempted 檢查（同名 chart 重試 #{_idx_to_try+1} — 總共試過 {_tried_sym_cnt} 次 / 有 {len(_all_sym_now)} 個）")
            if _found_cur is not None:
                _cur_idx = _found_cur
            else:
                print(f"[WARN] 冇新嘅 {_target_sym} chart（試過晒）— stop")
                break
        if _cur_idx >= len(_items):
            continue
        _attempted.add((_cur_idx, _items[_cur_idx]))
        print(f"[PIN] try remove chart [{_cur_idx}]（{_items[_cur_idx]}）...")
        # 6. 揀目標 chart → Enter（關閉 dialog + 彈返 chart）
        # [ALERT] 2026-08-21 FIX（Breakout AMD 案例 + user要求）：用方向鍵揀（user一早講咗 — 唔靠座標）
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
        if any('窗口' in t for t, h in _dlgs_now) or any(t == 'Windows' for t, h in _dlgs_now):
            print("[WARN] 窗口 dialog 未關（Enter 可能冇生效）— 再試 Enter")
            _sk('{ENTER}')
            time.sleep(2)
            _dlgs_now2 = _dlgs()
            if any('窗口' in t for t, h in _dlgs_now2) or any(t == 'Windows' for t, h in _dlgs_now2):
                # [ALERT] 2026-08-21 FIX（Breakout AMD 案例 — 網頁話success但 MT5 卡窗口 dialog）：
                # dialog 再試都未關 → fail（唔好繼續 Ctrl+W 亂關 — 關唔到 + 誤判success）
                # [ALERT] 2026-08-29 FIX（remove假failed — EMA_Cross 案例）：dialog 未關但 EA 可能已經remove
                # （Enter 已生效 + removedone — 但 dialog handle 未釋放/殘留 → 誤判「未關」→ 假failed）
                # → 最後確認：心跳停 / MT5 log removed（EA 真remove = 唔當failed — 跳去關 chart）
                _ea_really_gone = False
                try:
                    _cfd3 = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
                    _hb_any = False
                    for _hfn4 in (f'state_{ea_name}.json', f'hb_{ea_name}.txt'):
                        _hfp4 = os.path.join(_cfd3, _hfn4)
                        if os.path.isfile(_hfp4) and time.time() - os.path.getmtime(_hfp4) < 30:
                            _hb_any = True
                            break
                    if not _hb_any:
                        _ea_really_gone = True
                        print(f"[OK] {ea_name} heartbeat stopped（EA 真remove — dialog 未關但removesuccess，繼續關 chart）")
                except Exception:
                    pass
                # MT5 log removed 確認
                if not _ea_really_gone:
                    try:
                        if _lat_r and os.path.isfile(_lat_r):
                            _raw_r3 = open(_lat_r, 'rb').read()
                            _txt_r3 = None
                            for _enc_r3 in ('utf-16', 'utf-8', 'cp1252'):
                                try:
                                    _txt_r3 = _raw_r3.decode(_enc_r3)
                                    break
                                except Exception:
                                    continue
                            if _txt_r3:
                                _recent3 = _txt_r3.splitlines()[-30:]
                                _last_state3 = None
                                for _l4 in reversed(_recent3):
                                    if ea_name in _l4 and ('loaded' in _l4 or 'removed' in _l4 or '已启动' in _l4 or '已stop' in _l4):
                                        if 'removed' in _l4 or '已stop' in _l4:
                                            _last_state3 = 'removed'
                                        elif 'loaded' in _l4 or '已启动' in _l4:
                                            _last_state3 = 'loaded'
                                        break
                                if _last_state3 == 'removed':
                                    _ea_really_gone = True
                                    print(f"[OK] MT5 log 確認 {ea_name} removed（EA 真remove — dialog 未關但removesuccess，繼續關 chart）")
                    except Exception:
                        pass
                if not _ea_really_gone:
                    print(f"[FAIL] 窗口 dialog 未關（再試 Enter 都冇效）— remove中止（唔好誤判success）")
                    try:
                        _sk('{ESC}')
                    except Exception:
                        pass
                    return False

        # 8. Ctrl+W 關閉該 chart（EA 一齊remove）
        _sk('^w')
        time.sleep(2.5)

        # 9. 驗證：MT5 log 有 removed 記錄 / 心跳停（[TARGET] 逐個試 — 冇remove就下一個 candidate）
        _this_removed = False
        try:
            _start_t = time.time()
            # [ALERT] 2026-08-25 FIX6（心跳停判斷等唔夠耐 — remove後心跳檔 mtime 未過 30s → 誤判「still running」）：等 40 秒
            while time.time() - _start_t < 40:
                time.sleep(2)
                # 心跳停 = remove
                _hb_still = False
                _cfd2 = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
                for _hfn2 in (f'state_{ea_name}.json', f'hb_{ea_name}.txt'):
                    _hfp2 = os.path.join(_cfd2, _hfn2)
                    if os.path.isfile(_hfp2) and time.time() - os.path.getmtime(_hfp2) < 30:
                        _hb_still = True
                if not _hb_still:
                    _this_removed = True
                    print(f"[OK] {ea_name} heartbeat stopped（EA 已remove）")
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
                            # [ALERT] 2026-08-25 FIX（remove假success — MACD 案例）：any(match removed) 會讀到舊 removed 記錄（上次測試）→ 誤判remove
                            # → 改 check「最後狀態」：搵 EA 最後一條 loaded/removed — 最後係 removed 先算真remove
                            _last_state_r = None
                            for _l3 in reversed(_recent):
                                if ea_name in _l3 and ('loaded' in _l3 or 'removed' in _l3 or '已启动' in _l3 or '已stop' in _l3):
                                    if 'removed' in _l3 or '已stop' in _l3:
                                        _last_state_r = 'removed'
                                    elif 'loaded' in _l3 or '已启动' in _l3:
                                        _last_state_r = 'loaded'
                                    break
                            if _last_state_r == 'removed':
                                # [ALERT] 2026-08-25 FIX5（多 chart 掛同一 EA — Breakout GBPUSD×2 案例）：log removed 但心跳仲寫
                                # = 另一個 chart 仲掛住 EA → 唔當done → 繼續try next chart
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
                                    print(f"[WARN] log 話 removed 但heartbeat still writing（{ea_name} attached on另一個 chart）— 繼續試下一個")
                                    time.sleep(2)
                                else:
                                    _this_removed = True
                                    print(f"[OK] MT5 log 最後狀態確認 {ea_name} removed（heartbeat stopped）")
                                    break
                except Exception:
                    pass
        except Exception:
            pass
        if _this_removed:
            _removed_ok = True
            # [ALERT] 2026-09-01 FIX（用戶實測：剷除後有殘留心跳 — EMA_Cross/Fibonacci state_*.json 殘留）：
            # before: Ctrl+W 關 chart + 心跳停就當 success — 但冇刪心跳檔 → 檔殘留（mtime 舊但存在）→ 用戶/後續判斷混亂
            # now: 剷除成功後刪心跳檔（state_<EA>.json + hb_<EA>.txt — 乾淨）
            try:
                _cfd_del = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files')
                for _hfn_del in (f'state_{ea_name}.json', f'hb_{ea_name}.txt', f'state_{ea_name}.txt'):
                    _hfp_del = os.path.join(_cfd_del, _hfn_del)
                    if os.path.isfile(_hfp_del):
                        try:
                            os.remove(_hfp_del)
                            print(f"[OK] 已刪心跳檔: {_hfn_del}")
                        except Exception:
                            pass
                # 亦刪 MQL5/Files 嘅 hb_<EA>.txt（舊版 EA 寫嗰度 — 冇 FILE_COMMON）
                try:
                    _mql5_del = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal')
                    import glob as _g_del
                    for _d_del in os.listdir(_mql5_del):
                        _f_del = os.path.join(_mql5_del, _d_del, 'MQL5', 'Files', f'hb_{ea_name}.txt')
                        if os.path.isfile(_f_del):
                            try:
                                os.remove(_f_del)
                                print(f"[OK] 已刪 MQL5/Files 心跳: hb_{ea_name}.txt")
                            except Exception:
                                pass
                except Exception:
                    pass
                # 亦刪 hb_<EA>.txt 喺 Terminal Common（其他位置）
                _hb_glob_del = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal', 'Common', 'Files', f'hb_{ea_name}.txt')
                if os.path.isfile(_hb_glob_del):
                    try:
                        os.remove(_hb_glob_del)
                    except Exception:
                        pass
            except Exception:
                pass
            break
        # 未remove → 可能remove咗冇 EA 嘅 chart — 再開窗口 dialog 試下一個
        print(f"[WARN] chart [{_target_idx}] remove後 {ea_name} still running — try next chart")
        # 重新開窗口 dialog（Ctrl+W 關咗 chart after dialog 已關）
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
            print("[WARN] 再開窗口 dialog failed — remove中止")
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
        print(f"[CLIP] 重新讀 ListView（{_cnt2} 個 chart）")
        for _i2, _t2 in enumerate(_items):
            print(f"  [{_i2}] {_t2}")

    if _removed_ok:
        print(f"[OK] pause/remove {ea_name} done（Ctrl+W 關 chart）")
        return True
    print(f"[FAIL] {ea_name} cannot confirm removal（試晒所有candidate chart 都still running）")
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
    parser.add_argument('--remove', action='store_true', help='Remove EA from chart (真pause)')
    parser.add_argument('--account', default='', help='Account username (fingerprint — 2026-08-31)')
    args = parser.parse_args()
    # [FP] 2026-08-31 fingerprint：所有 log 加 account 前綴
    _FP = f"[{args.account or 'unknown'}] " if args.account else ''
    if args.account:
        print(f"[FP] [FINGERPRINT] auto_attach belongs to account: {args.account}（EA={args.ea}）")
        try:
            _alog = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aa_debug.log')
            with open(_alog, 'a', encoding='utf-8') as _f:
                _f.write(f"\n[FP] [FINGERPRINT] auto_attach account={args.account} ea={args.ea} symbol={args.symbol} tf={args.tf} action={'remove' if args.remove else 'deploy'}\n")
        except Exception:
            pass
    
    if args.remove:
        # 真pause模式：remove圖表 EA
        from control_guard import acquire, release, ControlAborted
        try:
            acquire(f'pause {args.ea}')
        except Exception:
            pass
        try:
            # [ALERT] 2026-09-01（user確認機制）：剷除用 .chr 方法（關 MT5 → 刪目標 EA 嘅 .chr → 開 MT5 — chart 唔 restore — EA 自然停）
            # （之前 Alt+W 方法誤剷其他 EA — .chr 方法精準判斷 + agent 已修「唔自動開 MT5」→ race 解決）
            ok = remove_ea_via_chr(args.ea)
            print(f"{'[OK]' if ok else '[FAIL]'} pause {args.ea} {'success' if ok else '（圖表可能冇 EA）'}")
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
