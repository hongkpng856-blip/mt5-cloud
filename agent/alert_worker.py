"""獨立警告視窗 process（2026-08-07：根治 Tcl_AsyncDelete crash）
原本 tkinter 喺 watcher 入面嘅獨立 thread — Python 退出時 crash（async handler deleted by wrong thread）
而家：獨立 subprocess — watcher 唔再 import tkinter — 唔會 crash
機制：讀 flag 檔（.ai_control.show）— 有 → 顯示視窗；冇 → 隱藏
🚨 2026-08-10：加操作步驟顯示（.ai_control.steps JSON — 一排排 ✅ 完成 / ⏳ 操作中 / ⬜ 等待）"""
import os
import sys
import time
import json
import tkinter as tk

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHOW_FLAG = os.path.join(AGENT_DIR, '.ai_control.show')
STEPS_FLAG = os.path.join(AGENT_DIR, '.ai_control.steps')

root = None
window = None
_steps_frame = None
_last_steps = ''
_done_btn = None
_stop_btn = None
_btn_frame = None
_all_done_shown = False


def build_window():
    global root, window, _steps_frame, _done_btn, _stop_btn, _btn_frame
    root = tk.Tk()
    window = root
    root.title("AI 控制中")
    # 🚨 2026-08-10：唔用 default tkinter icon（用戶要求）— 用自訂 emerald 色 icon
    try:
        _img = tk.PhotoImage(width=32, height=32)
        _img.put('#10b981', to=(0, 0, 32, 32))  # emerald 色塊
        root.iconphoto(True, _img)
    except Exception:
        pass
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.98)
    root.configure(bg="#18181b")
    # emerald 頂條
    tk.Frame(root, bg="#10b981", height=4).pack(fill="x")
    window._prog_label = tk.Label(root, text="🤖 AI 控制中", bg="#18181b", fg="#fafafa",
             font=("Microsoft JhengHei UI", 16, "bold"))
    window._prog_label.pack(pady=(12, 4))
    # 🚨 2026-08-10：操作名（prog）隱藏 — 已併入步驟第一條（用戶要求：操作名整合步驟列表）
    window._prog_label.pack_forget()
    tk.Label(root, text="請勿使用滑鼠及鍵盤…", bg="#18181b", fg="#a1a1aa",
             font=("Microsoft JhengHei UI", 11)).pack(pady=(0, 6))
    # 步驟列表 frame（一排排 — 完成 ✅ / 操作中 ⏳ / 等待 ⬜）
    _steps_frame = tk.Frame(root, bg="#18181b")
    _steps_frame.pack(fill="x", padx=16, pady=(0, 6))
    tk.Label(root, text="⚠️ 如非必要請勿操作電腦", bg="#18181b", fg="#fbbf24",
             font=("Microsoft JhengHei UI", 10)).pack(pady=(0, 6))
    # 🚨 2026-08-10：完成後顯示「確定」按鈕（用戶撳先關閉 — 唔會自動消失）
    # 🚨 2026-08-10：確定 + 緊急停止同一大細（用戶投訴唔一致）— 並排（frame）
    _btn_frame = tk.Frame(root, bg="#18181b")
    _done_btn = tk.Button(_btn_frame, text="確定", bg="#10b981", fg="#18181b",
             font=("Microsoft JhengHei UI", 12, "bold"), relief="flat", width=10,
             command=lambda: root.withdraw())
    # 🚨 2026-08-10：強制終止（緊急停止）保留 — 撳 → 寫 .ai_control.stop flag（watcher/auto_attach check_abort 偵測）
    def _emergency_stop():
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.ai_control.stop'), 'w') as f:
                f.write('1')
        except Exception:
            pass
    _stop_btn = tk.Button(_btn_frame, text="緊急停止", bg="#dc2626", fg="#fff",
             font=("Microsoft JhengHei UI", 12, "bold"), relief="flat", width=10,
             command=_emergency_stop)
    _done_btn.pack(side="left", padx=4)
    _stop_btn.pack(side="left", padx=4)
    root.withdraw()  # 初始隱藏
    # 放右下角（🚨 2026-08-10：固定高度 380 — 唔好每次 resize — 抽搐根治）
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    w, h = 340, 380
    root.geometry(f"{w}x{h}+{sw - w - 24}+{sh - h - 60}")
    root.minsize(340, 380)
    root.maxsize(340, 380)


def render_steps(steps):
    """更新步驟列表（一排排 — ✅ 完成 / ⏳ 操作中 / ⬜ 等待）
    🚨 2026-08-10：全部完成 → 標題顯示「✅ 已完成」"""
    global _last_steps
    try:
        data = json.loads(steps) if steps else []
        key = json.dumps(data, ensure_ascii=False)
        if key == _last_steps:
            return
        _last_steps = key
        for w in _steps_frame.winfo_children():
            w.destroy()
        if not data:
            return
        all_done = bool(data) and all(s.get('status') == 'done' for s in data)
        if all_done:
            # 🚨 2026-08-10：唔用 emoji（用戶要求）— 純文字「已完成」；prog 完成先顯示（平時隱藏 — 併入步驟）
            window._prog_label.config(text='已完成')
            try:
                if not window._prog_label.winfo_ismapped():
                    window._prog_label.pack(pady=(12, 4))
            except Exception:
                pass
            if not _all_done_shown:
                _all_done_shown = True
                # 🚨 2026-08-10：完成 → 顯示「確定」按鈕（用戶撳先關 — 唔自動消失）
                # 🚨 2026-08-10：完成後緊急停止消失（用戶要求 — 操作完成唔使再強制終止 — 只留確定）
                if _stop_btn is not None:
                    try:
                        _stop_btn.pack_forget()
                    except Exception:
                        pass
                if _btn_frame is not None and not _btn_frame.winfo_ismapped():
                    _btn_frame.pack(pady=(0, 8))
                if _done_btn is not None and not _done_btn.winfo_ismapped():
                    _done_btn.pack(side="left", padx=4)
        for s in data:
            st = s.get('status', 'pending')
            # 🚨 2026-08-10：唔用 emoji icon（用戶要求）— 用文字標記
            if st == 'done':
                mark, color = '完成', '#34d399'
            elif st == 'doing':
                mark, color = '進行中', '#fbbf24'
            else:
                mark, color = '等待', '#71717a'
            tk.Label(_steps_frame, text=f"[{mark}] {text}", bg="#18181b", fg=color,
                     font=("Microsoft JhengHei UI", 11), anchor="w").pack(fill="x")
        # 🚨 2026-08-10：移除「高度自動」— 固定高度 380（每次 resize → 視窗抽搐 — 用戶投訴）
    except Exception:
        pass


def main():
    global _all_done_shown
    build_window()
    shown = False
    last_prog = ''
    while True:
        try:
            has_flag = os.path.isfile(SHOW_FLAG)
            if has_flag:
                # 🚨 每次 poll 都讀 flag 更新程式名（唔理 shown 狀態 — 連續操作唔會顯示舊名）
                try:
                    with open(SHOW_FLAG, 'r', encoding='utf-8') as f:
                        prog = f.read().strip() or 'AI 控制中'
                    if prog != last_prog:
                        window._prog_label.config(text=prog)
                        last_prog = prog
                except Exception:
                    pass
                # 🚨 步驟列表（.ai_control.steps）
                try:
                    if os.path.isfile(STEPS_FLAG):
                        with open(STEPS_FLAG, 'r', encoding='utf-8') as f:
                            render_steps(f.read())
                    else:
                        render_steps('')
                except Exception:
                    pass
                if not shown:
                    window_state = root.state()
                    if window_state == 'withdrawn':
                        root.deiconify()
                    else:
                        root.lift()
                    shown = True
                    # 🚨 2026-08-10：強制終止（緊急停止）操作期間都顯示（用戶要求保留）
                    if _btn_frame is not None and not _btn_frame.winfo_ismapped():
                        _btn_frame.pack(pady=(0, 8))
            elif not has_flag and shown:
                # 🚨 2026-08-10：警告視窗唔自動關閉（用戶要求）— 一定要撳「確定」先關
                # 操作完成/中斷 → 一直顯示（確定按鈕顯示 — 用戶撳先關）+ 緊急停止消失（完成咗）
                if _stop_btn is not None:
                    try:
                        _stop_btn.pack_forget()
                    except Exception:
                        pass
                if _btn_frame is not None and not _btn_frame.winfo_ismapped():
                    try:
                        _btn_frame.pack(pady=(0, 8))
                    except Exception:
                        pass
                if _done_btn is not None and not _done_btn.winfo_ismapped():
                    try:
                        _done_btn.pack(side="left", padx=4)
                    except Exception:
                        pass
            root.update()
        except Exception:
            pass
        time.sleep(0.5)


if __name__ == '__main__':
    main()
