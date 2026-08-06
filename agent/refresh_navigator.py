#!/usr/bin/env python3
"""
MT5 Navigator Auto-Refresh — 檔案目錄變化後自動 refresh Navigator panel
用途：剷除/新增 EA 後，MT5 Navigator 唔會自動更新，要 refresh 先見到
方法：右 click Navigator tree 空白位置 → click 最底「刷新」menu item（用戶確認嘅方法）

支援三種 Navigator 狀態：
1. Docked（嵌喺 MT5 主窗口左/右邊）— 掃主窗口 descendants
2. Floating（浮動獨立視窗，用戶移動過）— 掃所有 top-level windows
3. 關閉（交叉咗）— 嘗試用 Ctrl+N / Alt+V+N / WM_COMMAND 開返
"""
import sys
import time
import ctypes
import ctypes.wintypes
import subprocess

MT5_EXE = r'C:\Program Files\MetaTrader 5\terminal64.exe'


def find_mt5_pid():
    """搵 MT5 process"""
    try:
        out = subprocess.check_output(
            'tasklist /FI "IMAGENAME eq terminal64.exe" /FO CSV /NH',
            shell=True, timeout=5
        ).decode(errors='ignore')
        for line in out.splitlines():
            parts = [p.strip().strip('"') for p in line.split(',')]
            if len(parts) >= 2 and parts[0] == 'terminal64.exe' and parts[1].isdigit():
                return int(parts[1])
    except Exception:
        pass
    return None


def _find_tree_views():
    """掃所有 top-level windows + 主窗口 descendants 搵 SysTreeView32（Navigator tree）
    支援 docked + floating Navigator
    返回: list of (window, tree_wrapper)
    """
    from pywinauto import Application
    user32 = ctypes.windll.user32

    mt5_pid = find_mt5_pid()
    if not mt5_pid:
        return []

    app = Application(backend='win32').connect(process=mt5_pid)
    results = []

    # 1. 掃所有 top-level windows（浮動 Navigator 係 Afx:MiniFrame）
    def enum_cb(h, l):
        try:
            if user32.IsWindowVisible(int(h)):
                cn_buf = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(int(h), cn_buf, 64)
                cn = cn_buf.value
                if 'Afx' in cn or 'MetaTrader' in cn:
                    try:
                        w = app.window(handle=int(h))
                        for d in w.descendants():
                            if d.element_info.class_name == 'SysTreeView32':
                                try:
                                    if d.is_visible():
                                        results.append((w, d))
                                except:
                                    results.append((w, d))
                    except Exception:
                        pass
        except Exception:
            pass
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    try:
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception:
        pass

    # 2. 主窗口 descendants（docked Navigator）
    try:
        win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
        for d in win.descendants():
            if d.element_info.class_name == 'SysTreeView32':
                try:
                    if d.is_visible():
                        results.append((win, d))
                except:
                    results.append((win, d))
    except Exception:
        pass

    return results


def refresh_navigator(max_retries=3):
    """
    Refresh MT5 Navigator — 模擬用戶手動 refresh：
    右 click Navigator tree 空白位置 → click 最底「刷新」menu item
    支援 docked / floating / 關閉三種狀態
    """
    import pyautogui as _pg
    _pg.FAILSAFE = False
    _pg.PAUSE = 0.2
    user32 = ctypes.windll.user32

    mt5_pid = find_mt5_pid()
    if not mt5_pid:
        print("❌ MT5 唔係運行緊")
        return False

    # 安全防護 helper（用戶要求 2026-08：避免撳到電腦其他嘢）
    # 先將 DeskIn 移去角落（唔遮 MT5 — 2026-08 實測 DeskIn 遮住圖表食晒啲 click）
    try:
        import ctypes as _ct2
        _pt_found = []
        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
        def _cb2(hwnd, _):
            _buf = ctypes.create_unicode_buffer(150)
            ctypes.windll.user32.GetWindowTextW(ctypes.c_void_p(hwnd), _buf, 150)
            if 'DeskIn' in _buf.value:
                _pt_found.append(hwnd)
            return True
        ctypes.windll.user32.EnumWindows(_cb2, 0)
        _sw = ctypes.windll.user32.GetSystemMetrics(0)  # 螢幕寬（大眾化）
        for _h in _pt_found:
            ctypes.windll.user32.SetWindowPos(ctypes.c_void_p(_h), 0, _sw - 520, 0, 500, 400, 0x0004 | 0x0040)
        if _pt_found:
            print("📌 DeskIn 已移去右上角（唔遮 MT5）")
            time.sleep(0.5)
    except Exception:
        pass

    def _is_mt5_window(x, y):
        try:
            pt = ctypes.wintypes.POINT(int(x), int(y))
            hwnd = user32.WindowFromPoint(pt)
            if not hwnd:
                return True
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
            return pid.value == mt5_pid
        except Exception:
            return False

    def _safe_click(x, y, button='left'):
        if not _is_mt5_window(x, y):
            print(f"⚠️ [安全防護] ({x},{y}) 目標唔係 MT5 — 跳過")
            return False
        _pg.click(x, y, button=button)
        return True

    for attempt in range(max_retries):
        try:
            # AI 控制守衛 — 彈警告視窗 + 緊急停止支援
            from control_guard import acquire, check_abort, release, ControlAborted
            acquire("刷新 Navigator")
            try:
                return _do_refresh(mt5_pid, attempt)
            except ControlAborted:
                print("🚨 Navigator refresh 被用戶緊急停止！")
                return False
            finally:
                release()
        except Exception as e:
            print(f"⚠️ refresh attempt {attempt+1} failed: {e}")
            try:
                import pyautogui as _pg
                _pg.press('esc')
            except:
                pass
            time.sleep(3)
    return False


def _do_refresh(mt5_pid, attempt):
    """實際 refresh 邏輯（被 control_guard 包住）"""
    import pyautogui as _pg
    # ⚠️ 統一 Navigator 位置（2026-08 用戶要求：操作前 Navigator 最大 + 固定位置）
    try:
        import auto_attach as _aa
        _aa.ensure_navigator_unified(mt5_pid)
    except Exception:
        pass
    _pg.FAILSAFE = False
    _pg.PAUSE = 0.2
    user32 = ctypes.windll.user32
    from control_guard import check_abort, pause_window, resume_window
    # 警告視窗喺右下角（唔遮 Navigator）→ 唔使 pause/resume 隱藏 — 全程顯示（Bug #72）
    # pause_window()/resume_window() 已移除 — 視窗由動作開始顯示到完成

    try:
        # Step 1: 搵 Navigator tree（docked 或 floating）
        trees = _find_tree_views()
        if not trees:
            print("⚠️ 搵唔到 Navigator tree（可能閂咗），嘗試開啟...")
            _open_navigator(user32)
            time.sleep(3)
            check_abort()
            trees = _find_tree_views()
            if not trees:
                print("⚠️ 開唔到 Navigator panel")
                time.sleep(2)
                return False

        # 用第一個可見嘅 tree view
        win, tree = trees[0]
        tree_rect = tree.rectangle()

        # 確保 Navigator 窗口係 foreground（浮動視窗要 focus 先收到 right-click）
        try:
            win.set_focus()
            time.sleep(0.8)
            # 如果係浮動 MiniFrame，click 佢標題欄確保 focus
            try:
                _pg.click(tree_rect.left + 50, tree_rect.top - 15)
                time.sleep(0.8)
            except:
                pass
        except:
            pass

        # 右 click 喺 tree 中間位置（避免底部被工具箱/狀態欄遮住）
        cx = tree_rect.left + min(150, tree_rect.width() // 2)
        cy = tree_rect.top + int(tree_rect.height() * 0.5)
        _pg.click(cx, cy, button='right')
        time.sleep(2)
        check_abort()

        # Step 2: 搵 popup menu window (#32768)
        popup_hwnd = [0]
        def enum_cb(h, l):
            try:
                if user32.IsWindowVisible(int(h)):
                    buf = ctypes.create_unicode_buffer(64)
                    user32.GetClassNameW(int(h), buf, 64)
                    if '#32768' in buf.value:
                        popup_hwnd[0] = h
                        return False
            except Exception:
                pass
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        try:
            user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        except Exception:
            pass

        if not popup_hwnd[0]:
            print("⚠️ 搵唔到 popup menu")
            _pg.press('esc')
            time.sleep(2)
            return False
        check_abort()

        # Step 3: 攞 menu rect → click 最底 item（「刷新」）
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(popup_hwnd[0], ctypes.byref(rect))
        click_x = (rect.left + rect.right) // 2
        click_y = rect.bottom - 11
        _pg.click(click_x, click_y)
        time.sleep(3)

        print(f"🔄 Navigator refreshed (right-click → 刷新) at ({click_x},{click_y})")
        return True
    finally:
        pass  # 警告視窗全程顯示 — 由 acquire/release 控制（Bug #72）


def _open_navigator(user32):
    """嘗試開啟 Navigator（如果閂咗）"""
    from pywinauto import Application
    try:
        app = Application(backend='win32').connect(process=find_mt5_pid())
        win = app.window(class_name='MetaQuotes::MetaTrader::5.00')

        # 方法 1: menu_select（中文 menu）
        try:
            for path in [("查看(&V)", "導航(&N)"), ("View", "Navigator")]:
                try:
                    win.menu_select(f"{path[0]}->{path[1]}")
                    time.sleep(2)
                    return
                except Exception:
                    continue
        except Exception:
            pass

        # 方法 2: 鍵盤 Alt+V,N
        try:
            from pywinauto.keyboard import send_keys
            try:
                win.set_focus()
            except:
                pass
            time.sleep(0.5)
            send_keys('%vn')
            time.sleep(2)
            return
        except Exception:
            pass

        # 方法 3: WM_COMMAND 32845（導航 menu command）
        try:
            hwnd = win.element_info.handle
            user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0111, 32845, 0)
            time.sleep(2)
        except Exception:
            pass
    except Exception as e:
        print(f"   開啟 Navigator 失敗: {e}")


if __name__ == '__main__':
    ok = refresh_navigator()
    sys.exit(0 if ok else 1)
