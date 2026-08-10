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
_all_done_shown = False


def build_window():
    global root, window, _steps_frame, _done_btn
    root = tk.Tk()
    window = root
    root.title("AI 控制中")
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.98)
    root.configure(bg="#18181b")
    # emerald 頂條
    tk.Frame(root, bg="#10b981", height=4).pack(fill="x")
    window._prog_label = tk.Label(root, text="🤖 AI 控制中", bg="#18181b", fg="#fafafa",
             font=("Microsoft JhengHei UI", 16, "bold"))
    window._prog_label.pack(pady=(12, 4))
    tk.Label(root, text="請勿使用滑鼠及鍵盤…", bg="#18181b", fg="#a1a1aa",
             font=("Microsoft JhengHei UI", 11)).pack(pady=(0, 6))
    # 步驟列表 frame（一排排 — 完成 ✅ / 操作中 ⏳ / 等待 ⬜）
    _steps_frame = tk.Frame(root, bg="#18181b")
    _steps_frame.pack(fill="x", padx=16, pady=(0, 6))
    tk.Label(root, text="⚠️ 如非必要請勿操作電腦", bg="#18181b", fg="#fbbf24",
             font=("Microsoft JhengHei UI", 10)).pack(pady=(0, 6))
    # 🚨 2026-08-10：完成後顯示「確定」按鈕（用戶撳先關閉 — 唔會自動消失）
    _done_btn = tk.Button(root, text="✅ 確定", bg="#10b981", fg="#18181b",
             font=("Microsoft JhengHei UI", 12, "bold"), relief="flat",
             command=lambda: root.withdraw())
    root.withdraw()  # 初始隱藏
    # 放右下角
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    w, h = 340, 230
    root.geometry(f"{w}x{h}+{sw - w - 24}+{sh - h - 60}")


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
            window._prog_label.config(text='✅ 已完成')
            if not _all_done_shown:
                _all_done_shown = True
                # 🚨 2026-08-10：完成 → 顯示「確定」按鈕（用戶撳先關 — 唔自動消失）
                if _done_btn is not None and not _done_btn.winfo_ismapped():
                    _done_btn.pack(pady=(0, 10))
                    sw = root.winfo_screenwidth()
                    sh = root.winfo_screenheight()
                    h = 230 + len(data) * 24 + 50
                    root.geometry(f"340x{h}+{sw - 364}+{sh - h - 60}")
        for s in data:
            text = s.get('text', '')
            st = s.get('status', 'pending')
            if st == 'done':
                icon, color = '✅', '#34d399'
            elif st == 'doing':
                icon, color = '⏳', '#fbbf24'
            else:
                icon, color = '⬜', '#71717a'
            tk.Label(_steps_frame, text=f"{icon} {text}", bg="#18181b", fg=color,
                     font=("Microsoft JhengHei UI", 11), anchor="w").pack(fill="x")
        # 高度自動（按步驟數）
        h = 230 + len(data) * 24
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"340x{h}+{sw - 364}+{sh - h - 60}")
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
            elif not has_flag and shown:
                # 🚨 2026-08-10：完成（flag 刪咗）→ 唔即刻隱藏 — 如果顯示緊「確定」等用戶撳
                # 用戶撳確定（_done_btn command → root.withdraw）— 或者 flag 冇咗 + 冇確定顯示 → 隱藏
                if _done_btn is not None and _done_btn.winfo_ismapped():
                    pass  # 等用戶撳確定
                else:
                    root.withdraw()
                    shown = False
                    _last_steps = ''  # 重置（下次重新顯示）
                    _all_done_shown = False
            root.update()
        except Exception:
            pass
        time.sleep(0.5)


if __name__ == '__main__':
    main()
