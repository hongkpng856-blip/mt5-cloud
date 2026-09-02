#!/usr/bin/env python3
"""
Control Guard — AI 控制守衛
當程式/AI 操控電腦（GUI 自動化）時：
1. 彈警告視窗（topmost，顯示邊個程式控制緊）
2. 「[ALERT] 緊急停止」按鈕 → 寫 stop 標記
3. 所有 GUI 自動化每步檢查 → 有標記即刻 abort

用法：
    from control_guard import acquire, check_abort, release, ControlAborted, is_aborted

    acquire("部署 EA")          # 開始控制前
    try:
        do_gui_thing()          # GUI 操作...
        check_abort()           # 每步檢查（可選）
    except ControlAborted:
        print("User pressed EMERGENCY STOP")
        sys.exit(130)
    finally:
        release()               # 完成/失敗都一定要 release
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys
import time
import threading

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCK_FILE = os.path.join(AGENT_DIR, '.ai_control.lock')   # 邊個程式控制緊
STOP_FILE = os.path.join(AGENT_DIR, '.ai_control.stop')   # 緊急停止標記
# 前端 bridge：操控電腦時寫 status JSON → 網站 poll 到就彈警告視窗
STATUS_FILE = os.path.normpath(os.path.join(
    AGENT_DIR, '..', 'server', 'static', 'detector', 'ai_control.json'))

# 警告視窗最少顯示時間（秒）— 動作太快完成都唔會「彈一下」就消失（同網頁版 minShowUntil 一致）
MIN_SHOW_SECONDS = 3.0
# 最後一個動作完成後嘅 idle 關閉時間（秒）— 期間有新動作（acquire）就續命；
# 冇新動作 → 關閉（動作完成 ≈ 視窗關閉，同步）— 細過 watcher poll 週期但 compile 已即刻 queue refresh
IDLE_CLOSE_SECONDS = 2.0


def _write_status(active, program=''):
    """寫 AI 控制狀態去 static JSON（網站 poll 呢個嚟彈/關警告視窗）"""
    try:
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            import json as _json
            _json.dump({'active': active, 'program': program, 'time': time.time()}, f, ensure_ascii=False)
    except Exception:
        pass


class ControlAborted(Exception):
    """User pressed EMERGENCY STOP — GUI 自動化要即刻中止"""
    pass


# ─── 警告視窗（tkinter，常駐視窗 — 獨立 thread 永遠行 mainloop，只 show/hide 切換）───
_window = None
_window_lock = threading.Lock()
_window_thread_started = False  # 常駐 tkinter thread 已起動（永遠唔 destroy）


def acquire(program_name='AI'):
    """開始控制前調用 — 寫 lock + 彈警告視窗（常駐視窗，直接 show）"""
    # stale lock 清理：如果舊 lock 嘅 PID 已經唔存在（process 被 kill 冇 release）→ 覆蓋
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            old_pid = content.split('|')[-1] if '|' in content else ''
            if old_pid.isdigit():
                import subprocess as _sp
                try:
                    _r = _sp.run(['tasklist', '/FI', f'PID eq {old_pid}', '/FO', 'CSV', '/NH'],
                                 capture_output=True, text=True, timeout=5)
                    if old_pid not in _r.stdout:
                        os.remove(LOCK_FILE)  # stale — 清咗先
                        print(f"[DEL] Cleared stale lock (old PID {old_pid} dead)")
                except Exception:
                    pass
    except Exception:
        pass
    try:
        with open(LOCK_FILE, 'w', encoding='utf-8') as f:
            f.write(f"{program_name}|{os.getpid()}")
    except Exception:
        pass
    # 清除舊 stop 標記（新一輪控制開始）
    try:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
    except Exception:
        pass
    _show_window(program_name)
    _write_status(True, program_name)  # 網站 poll 到就彈警告視窗
    print(f"[SHIELD]  [CONTROL] {program_name} started controlling PC (warning window shown)")


def check_abort():
    """每個 GUI 動作前檢查 — 有 stop 標記就 raise"""
    if os.path.exists(STOP_FILE):
        raise ControlAborted("User pressed EMERGENCY STOP")


def is_aborted():
    """非 raise 版本 — 返回 True/False"""
    return os.path.exists(STOP_FILE)


def release():
    """完成/失敗後調用 — 清 lock + 最少顯示 MIN_SHOW_SECONDS 先關視窗 + 清 stop
    期間有新動作（acquire 寫 lock）→ 續命（視窗保持，由新動作接手）"""
    global _window
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass
    # [ALERT] 2026-08-12 FIX：即刻寫 active:false + 關視窗（唔等 5 秒 — 網頁 modal 靠確定撳先關，唔會「彈一下消失」）
    # 之前等 MIN_SHOW(3s)+IDLE(2s) → 完成後網頁一直 active:true → modal「不停出現」→ 用戶 refresh 先消失（「冇確定就關閉」）
    try:
        _hide_window()
        _write_status(False)  # 網站 poll 到就關警告視窗
    except Exception:
        pass
    # 清 stop flag（完成後唔殘留）
    try:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
    except Exception:
        pass
    print("[SHIELD]  [CONTROL] Control ended, warning window closed")
    # 清 steps 已經喺「下一個任務入口」做（compile/部署/剷除開始 — 自動清舊任務）


def _ensure_window_thread():
    """確保常駐 tkinter thread 起動（視窗建好後隱藏，之後只 show/hide 切換）
    常駐視窗 = 唔 destroy → 冇 GC/PhotoImage/Tcl_AsyncDelete 問題（Bug #69：watcher exit code 3）"""
    global _window_thread_started
    if _window_thread_started:
        return
    _window_thread_started = True
    t = threading.Thread(target=_run_tk, daemon=True)
    t.start()


def _run_tk():
    """常駐 tkinter mainloop — 建視窗 UI 後隱藏，永遠行 mainloop"""
    global _window
    import tkinter as tk
    try:
        root = tk.Tk()
        with _window_lock:
            _window = root
        root.title("AI 控制中")
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.98)
        root.configure(bg="#18181b")  # zinc-900 (card bg, 同網頁一致)

        # ── shadcn 風格 (zinc + emerald，同網頁一致) ──
        # 頂部 emerald 色條
        tk.Frame(root, bg="#10b981", height=4).pack(fill="x")  # emerald-500

        # icon-bot（同網頁版一致 — 用 tkinter Canvas 畫，唔用 PhotoImage）
        try:
            _cv = tk.Canvas(root, width=56, height=56, bg="#18181b", highlightthickness=0)
            _cv.pack(pady=8)
            # 照 Lucide bot.svg（24x24 → 56x56 比例 2.33）
            _cv.create_line(28, 18, 28, 10, fill="#10b981", width=3)   # 天線
            _cv.create_line(28, 10, 19, 10, fill="#10b981", width=3)   # 天線橫
            _cv.create_rectangle(9, 18, 47, 46, outline="#10b981", width=3)  # 頭部
            _cv.create_line(4, 33, 9, 33, fill="#10b981", width=3)     # 左耳
            _cv.create_line(47, 33, 52, 33, fill="#10b981", width=3)   # 右耳
            _cv.create_line(21, 30, 21, 35, fill="#10b981", width=3)   # 左眼
            _cv.create_line(35, 30, 35, 35, fill="#10b981", width=3)   # 右眼
        except Exception:
            tk.Label(root, text="◉", font=("Segoe UI Symbol", 30),
                     fg="#10b981", bg="#18181b", pady=10).pack()

        # 標題（同網頁一致 — 「AI 控制中」）
        tk.Label(root, text="AI 控制中", font=("Microsoft JhengHei", 18, "bold"),
                 fg="#fafafa", bg="#18181b", pady=6).pack(padx=32)

        # 邊個程式（emerald accent，同網頁「正在XXX」一致）
        _prog = tk.Label(root, text="", font=("Microsoft JhengHei", 13, "bold"),
                         fg="#10b981", bg="#18181b")
        _prog.pack(padx=32)
        root._prog_label = _prog  # 保存引用（show 時更新文字）

        # 警告訊息
        tk.Label(root, text="請勿移動滑鼠或按鍵盤！", font=("Microsoft JhengHei", 13, "bold"),
                 fg="#a1a1aa", bg="#18181b", pady=6).pack(padx=32)

        # 緊急停止按鈕（red-600，全寬 — 同網頁 ai-control-stop 一致）
        tk.Button(root, text="[ALERT] 緊急停止", font=("Microsoft JhengHei", 15, "bold"),
                  fg="white", bg="#dc2626", activebackground="#b91c1c", activeforeground="white",
                  relief="flat", bd=0, cursor="hand2", padx=40, pady=12,
                  command=_request_stop).pack(fill="x", padx=32, pady=12)

        # 位置：螢幕右下角（唔置中 — 置中會遮住 Navigator/MetaEditor 令 pyautogui 失效；
        # 右下角唔遮操作區域 → 視窗可以全程顯示，唔使 pause/resume 隱藏 — Bug #72）
        root.update_idletasks()
        w = root.winfo_reqwidth()
        h = root.winfo_reqheight()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = sw - w - 24
        y = sh - h - 80
        root.geometry(f"+{x}+{y}")

        root.withdraw()  # 開始隱藏 — 等 _show_window deiconify 顯示
        root.mainloop()  # 永遠行（daemon thread）— 唔 destroy，冇 GC 問題
    except Exception:
        pass


def init_window():
    """預先起動警告視窗（獨立 process — 2026-08-07 根治 Tcl_AsyncDelete crash）
    watcher 唔再 import tkinter — 唔會喺退出時 crash"""
    try:
        import subprocess as _sp
        _worker = os.path.join(os.path.dirname(__file__), 'alert_worker.py')
        if os.path.isfile(_worker):
            # 已經有 worker 行緊就唔起多個（用 flag 檔標記）
            _pidf = os.path.join(os.path.dirname(__file__), '.alert_worker.pid')
            _already = False
            try:
                with open(_pidf) as f:
                    _old = int(f.read().strip())
                import psutil as _ps
                _already = _ps.pid_exists(_old)
            except Exception:
                pass
            if not _already:
                _p = _sp.Popen([sys.executable, '-u', _worker],
                               creationflags=getattr(_sp, 'CREATE_NO_WINDOW', 0))
                try:
                    with open(_pidf, 'w') as f:
                        f.write(str(_p.pid))
                except Exception:
                    pass
            return True
    except Exception:
        pass
    return False


def _show_window(program_name):
    """顯示警告視窗（獨立 process — 寫 flag — worker 顯示）"""
    try:
        _flag = os.path.join(os.path.dirname(__file__), '.ai_control.show')
        with open(_flag, 'w', encoding='utf-8') as f:
            f.write(program_name or 'AI 控制中')
    except Exception:
        pass


def _hide_window():
    """隱藏警告視窗（獨立 process — 刪 flag — worker 隱藏）"""
    try:
        _flag = os.path.join(os.path.dirname(__file__), '.ai_control.show')
        if os.path.exists(_flag):
            os.remove(_flag)
    except Exception:
        pass


STEPS_FLAG = os.path.join(AGENT_DIR, '.ai_control.steps')


def update_steps(steps):
    """[ALERT] 2026-08-10：更新操作步驟（警告視窗顯示 — 一排排）
    steps: [{"text": "開新圖表", "status": "done"}, ...]
    status: done=完成 [OK] / doing=操作中 [WAIT] / pending=等待 ⬜"""
    try:
        with open(STEPS_FLAG, 'w', encoding='utf-8') as f:
            json.dump(steps, f, ensure_ascii=False)
    except Exception:
        pass


def clear_steps():
    """清除步驟（操作完成）"""
    try:
        if os.path.exists(STEPS_FLAG):
            os.remove(STEPS_FLAG)
    except Exception:
        pass


def pause_window():
    """GUI 自動化操作前隱藏警告視窗（唔搶滑鼠 click）— 刪 flag
    [ALERT] 2026-08-10：改 no-op — 每次操作刪 flag → 視窗彈吓彈下（心跳咁 — 用戶投訴）
    → 警告視窗喺右下角（唔遮 MT5 操作）— 唔需要 pause — 一直顯示"""
    pass


def resume_window():
    """GUI 操作完成後恢復顯示警告視窗"""
    global _window
    with _window_lock:
        if _window is not None:
            try:
                w = _window
                def _resume():
                    try:
                        w.deiconify()
                        w.attributes("-topmost", True)
                    except Exception:
                        pass
                try:
                    w.after(0, _resume)
                except Exception:
                    _resume()
            except Exception:
                pass


def _request_stop():
    """緊急停止按鈕 handler — 寫 stop 標記"""
    try:
        with open(STOP_FILE, 'w', encoding='utf-8') as f:
            f.write(f"stop|{time.time()}")
        print("[ALERT] [CONTROL] User pressed EMERGENCY STOP！")
    except Exception:
        pass


# ─── CLI 測試 ───
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Control Guard 測試')
    parser.add_argument('--acquire', action='store_true', help='模擬開始控制')
    parser.add_argument('--release', action='store_true', help='模擬結束控制')
    parser.add_argument('--abort-check', action='store_true', help='模擬每步檢查')
    args = parser.parse_args()

    if args.acquire:
        acquire("測試程式")
        print("Control started - warning window should show, press EMERGENCY STOP to test")
        # 模擬 GUI 操作 + 每步檢查
        for i in range(10):
            time.sleep(1)
            try:
                check_abort()
                print(f"  Step {i+1}: OK")
            except ControlAborted:
                print(f"  Step {i+1}: [ALERT] EMERGENCY STOPPED!")
                release()
                sys.exit(130)
        release()
        print("完成（冇被停止）")
    elif args.release:
        release()
        print("已釋放")
    elif args.abort_check:
        print(f"is_aborted={is_aborted()}")
    else:
        print("用法: --acquire / --release / --abort-check")
